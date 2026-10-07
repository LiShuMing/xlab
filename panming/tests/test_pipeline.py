"""Offline v0.4 evidence, fencing, budget and restore contracts on real PostgreSQL."""

import copy
import hashlib
import io
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from test_reliability import empty_store as empty_store
from test_workflow import capture
from test_workflow import client as client

from panming.app import source_ref, today
from panming.backup import BackupError, export_workspace, inspect_archive, restore_workspace
from panming.pipeline import (
    MAX_ATTEMPTS,
    MockProvider,
    Pipeline,
    PipelineError,
    chunks_for,
    validate_output,
)


def submit(client, material=None):
    material = material or capture(client)
    response = client.post("/api/v1/digest/jobs", json={"source_refs": [source_ref(material)]})
    assert response.status_code == 202, response.text
    return response.json()


def state(client):
    return client.get("/api/v1/processing").json()


def test_submit_is_durable_frozen_and_automatic_delivery_is_idempotent(client):
    material = capture(client)
    pipeline = client.app.state.pipeline
    blog = client.post(
        "/api/v1/blogs", json={"title": "自己的判断", "source_refs": [source_ref(material)]}
    ).json()
    report = client.post("/api/v1/reports/runs", json={"date": today()}).json()
    job = submit(client, material)
    assert "chunks" not in job and job["checkpoint"] == "input_frozen"
    revised = client.post(
        f"/api/v1/materials/{material['id']}/revisions",
        json={
            "title": material["title"],
            "body": "修改后的观点，不得覆盖原来版本的引用。",
            "revision": 1,
        },
    ).json()
    assert submit(client, material)["id"] == job["id"]
    assert pipeline.run_once()
    assert not pipeline.run_once()
    result = state(client)
    assert result["jobs"][0]["state"] == "succeeded"
    artifact = result["digests"][0]
    assert artifact["source_refs"] == [source_ref(material)]
    assert artifact["chunks"][0]["text"] == material["content"]
    assert artifact["validation"] == "reference_and_verbatim_quote_only_not_entailment"
    assert client.get(f"/api/v1/objects/{blog['id']}").json() == blog
    assert client.get(f"/api/v1/objects/{report['id']}").json() == report
    # Current source differs: an old digest is not silently rebased into a report.
    new_report = client.post("/api/v1/reports/runs", json={"date": today()}).json()
    assert new_report["evidence_digests"] == []
    assert revised["blob_hash"] != material["blob_hash"]


def test_report_includes_completed_exact_version_digest_only_on_manual_update(client):
    material = capture(client)
    old = client.post("/api/v1/reports/runs", json={"date": today()}).json()
    submit(client, material)
    client.app.state.pipeline.run_once()
    new = client.post("/api/v1/reports/runs", json={"date": today()}).json()
    assert len(new["evidence_digests"]) == 1 and new["generation_mode"] == "mock_evidence"
    history = client.get(f"/api/v1/objects/{old['id']}?revision=1").json()
    assert not history["evidence_digests"]
    body = client.get(f"/api/v1/export/{new['id']}?revision=2").text
    assert "本地 mock" in body and material["blob_hash"] in body and "?revision=1" in body
    digest_id = new["evidence_digests"][0]["id"]
    assert "来源陈述" in client.get(f"/api/v1/export/{digest_id}").text


def test_parallel_submission_reserves_once(client):
    material = capture(client)
    pipeline = client.app.state.pipeline
    with ThreadPoolExecutor(max_workers=6) as pool:
        jobs = list(pool.map(lambda _: pipeline.submit([source_ref(material)]), range(6)))
    assert len({j["id"] for j in jobs}) == 1
    result = state(client)
    assert len(result["jobs"]) == 1
    assert result["processing"]["budget"]["reserved"] == jobs[0]["estimate_units"]


def test_cancellation_fences_running_worker_and_retry_publishes_once(client):
    pipeline = client.app.state.pipeline
    job = submit(client)
    claimed = pipeline.claim("stale-worker")
    cancelled = pipeline.action(job["id"], "cancel")
    assert cancelled["fence"] > claimed["fence"]
    assert not pipeline.finish(claimed, MockProvider().generate(claimed["chunks"]))
    assert not pipeline.heartbeat(claimed)
    assert not state(client)["digests"]
    assert state(client)["processing"]["budget"]["reserved"] == 0
    pipeline.action(job["id"], "retry")
    current = pipeline.claim("new-worker")
    assert pipeline.finish(current, MockProvider().generate(current["chunks"]))
    assert not pipeline.finish(current, MockProvider().generate(current["chunks"]))
    assert len(state(client)["digests"]) == 1


def test_queued_cancel_and_success_cannot_be_retried_or_cancelled_into_new_state(client):
    pipeline = client.app.state.pipeline
    job = submit(client)
    assert pipeline.action(job["id"], "cancel")["state"] == "cancelled"
    assert not pipeline.run_once()
    pipeline.action(job["id"], "retry")
    pipeline.run_once()
    assert pipeline.action(job["id"], "retry")["state"] == "succeeded"
    assert pipeline.action(job["id"], "cancel")["state"] == "succeeded"


def test_expired_lease_recovered_by_new_pipeline_and_old_delivery_rejected(client):
    clock = [datetime.now(timezone.utc)]
    store = client.app.state.store
    first = Pipeline(store, clock=lambda: clock[0])
    first.submit([source_ref(capture(client))])
    old = first.claim("dead-process")
    clock[0] += timedelta(seconds=31)
    assert not first.finish(old, MockProvider().generate(old["chunks"]))
    restarted = Pipeline(store, clock=lambda: clock[0])
    current = restarted.claim("replacement")
    assert current["fence"] > old["fence"] and current["attempts"] == 2
    assert not first.finish(old, MockProvider().generate(old["chunks"]))
    assert restarted.finish(current, MockProvider().generate(current["chunks"]))


def test_heartbeat_renews_lease_without_granting_stale_worker_ownership(client):
    clock = [datetime.now(timezone.utc)]
    pipeline = Pipeline(client.app.state.store, clock=lambda: clock[0])
    pipeline.submit([source_ref(capture(client))])
    job = pipeline.claim("owner")
    clock[0] += timedelta(seconds=25)
    assert pipeline.heartbeat(job)
    clock[0] += timedelta(seconds=20)
    assert pipeline.claim("another") is None
    assert pipeline.finish(job, MockProvider().generate(job["chunks"]))


def test_lease_expiry_attempt_limit_releases_reservation(client):
    clock = [datetime.now(timezone.utc)]
    pipeline = Pipeline(client.app.state.store, clock=lambda: clock[0])
    jid = pipeline.submit([source_ref(capture(client))])["id"]
    for attempt in range(MAX_ATTEMPTS):
        assert pipeline.claim("dies")["attempts"] == attempt + 1
        clock[0] += timedelta(seconds=31)
    assert pipeline.claim("replacement") is None
    assert state(client)["jobs"][0]["error_code"] == "LEASE_EXHAUSTED"
    assert state(client)["processing"]["budget"]["reserved"] == 0
    with pytest.raises(PipelineError, match="3 次"):
        pipeline.action(jid, "retry")


def test_budget_failure_release_retry_and_daily_ledger(client):
    clock = [datetime.now(timezone.utc)]
    pipeline = Pipeline(client.app.state.store, daily_limit=25_000, clock=lambda: clock[0])
    source = capture(client)
    job = pipeline.submit([source_ref(source)])
    with pytest.raises(PipelineError) as error:
        pipeline.submit([source_ref(capture(client, "超出额度"))])
    assert error.value.code == "BUDGET_EXCEEDED"
    claimed = pipeline.claim("owner")
    pipeline.finish(claimed, error_code="PROVIDER_FAILED")
    assert state(client)["jobs"][0]["reserved_units"] == 0
    with pipeline.store.transaction() as conn:
        previous = pipeline.budget(conn)
    assert previous["used"] == len(source["content"])
    clock[0] += timedelta(days=1)
    pipeline.action(job["id"], "retry")
    pipeline.run_once()
    with pipeline.store.transaction() as conn:
        assert pipeline.budget(conn, previous["day"])["used"] == previous["used"]
        assert pipeline.budget(conn)["used"] > previous["used"]


def test_provider_call_does_not_hold_workspace_transaction(client):
    store = client.app.state.store

    class Probe(MockProvider):
        def generate(self, chunks):
            with store.transaction() as conn:
                assert conn.execute(
                    text(
                        "SELECT pg_try_advisory_xact_lock(hashtext(current_schema() || '/workspace'))"
                    )
                ).scalar()
            return super().generate(chunks)

    pipeline = Pipeline(store, providers={"mock": Probe()})
    pipeline.submit([source_ref(capture(client))])
    pipeline.run_once()
    assert state(client)["jobs"][0]["state"] == "succeeded"


def test_report_cutoff_includes_only_committed_evidence_deliveries(client, monkeypatch):
    import threading
    from concurrent.futures import TimeoutError

    pipeline = client.app.state.pipeline
    submit(client)
    job = pipeline.claim("delivering")
    entered, release, finish_started = threading.Event(), threading.Event(), threading.Event()
    original_list = pipeline.store.list

    def blocked_list(conn, kind):
        if kind == "material" and threading.current_thread().name.startswith("report-freeze"):
            entered.set()
            assert release.wait(5)
        return original_list(conn, kind)

    monkeypatch.setattr(pipeline.store, "list", blocked_list)

    def freeze():
        from datetime import date

        from panming.app import ReportRequest, build_report

        with pipeline.store.transaction() as conn:
            return build_report(
                pipeline.store, conn, ReportRequest(date=date.fromisoformat(today()))
            )

    def deliver():
        finish_started.set()
        return pipeline.finish(job, MockProvider().generate(job["chunks"]))

    with (
        ThreadPoolExecutor(max_workers=1, thread_name_prefix="report-freeze") as reports,
        ThreadPoolExecutor(max_workers=1) as workers,
    ):
        frozen = reports.submit(freeze)
        assert entered.wait(5)
        delivery = workers.submit(deliver)
        assert finish_started.wait(5)
        try:
            with pytest.raises(TimeoutError):
                delivery.result(timeout=0.05)
        finally:
            release.set()
        report = frozen.result(timeout=5)
        assert delivery.result(timeout=5)
    assert not report["evidence_digests"]
    assert state(client)["digests"][0]["created_at"] >= report["cutoff_at"]
    assert client.post("/api/v1/reports/runs", json={"date": today()}).json()["evidence_digests"]


@pytest.mark.parametrize("corrupt", [False, True])
def test_missing_or_corrupt_original_blocks_submission_without_reservation(client, corrupt):
    source = capture(client)
    path = client.app.state.store.data_dir / "blobs" / source["blob_hash"][:2] / source["blob_hash"]
    if corrupt:
        path.write_bytes(b"synthetic corrupted original")
    else:
        path.unlink()
    response = client.post("/api/v1/digest/jobs", json={"source_refs": [source_ref(source)]})
    assert response.status_code == 422 and response.json()["code"] == "SOURCE_BLOB_INVALID"
    assert not state(client)["jobs"] and not state(client)["processing"]["budget"]["reserved"]


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown_chunk",
        "false_quote",
        "no_citations",
        "personal_judgment",
        "nul",
        "unknown_field",
        "huge",
        "empty",
    ],
)
def test_invalid_provider_result_never_published(client, mutation):
    class Invalid(MockProvider):
        def generate(self, chunks):
            output = super().generate(chunks)
            claim = output["claims"][0]
            if mutation == "unknown_chunk":
                claim["citations"][0]["chunk_id"] = "foreign_chunk"
            elif mutation == "false_quote":
                claim["citations"][0]["quote"] = "原文中不存在这句话"
            elif mutation == "no_citations":
                claim["citations"] = []
            elif mutation == "personal_judgment":
                claim["kind"] = "personal_observation"
            elif mutation == "nul":
                claim["text"] = "a\x00b"
            elif mutation == "unknown_field":
                output["tools"] = [{"delete_all": True}]
            elif mutation == "huge":
                output["questions"] = ["x" * 25000]
            elif mutation == "empty":
                claim["text"] = " "
            return output

    pipeline = Pipeline(client.app.state.store, providers={"mock": Invalid()})
    pipeline.submit([source_ref(capture(client))])
    pipeline.run_once()
    result = state(client)
    assert result["jobs"][0]["error_code"] == "INVALID_EVIDENCE"
    assert not result["digests"] and result["processing"]["budget"]["reserved"] == 0


def test_cloud_policy_guard_prevents_call_and_environment_does_not_enable_provider(
    client, monkeypatch
):
    class Cloud(MockProvider):
        locality = "cloud"

        def generate(self, chunks):
            pytest.fail("private source must never reach cloud provider")

    source = capture(client)
    pipeline = Pipeline(client.app.state.store, providers={"mock": Cloud()})
    with pytest.raises(PipelineError) as error:
        pipeline.submit([source_ref(source)])
    assert error.value.code == "POLICY_BLOCKED"
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-not-a-real-key")
    response = client.post(
        "/api/v1/digest/jobs", json={"source_refs": [source_ref(source)], "provider": "openai"}
    )
    assert response.status_code == 422
    assert state(client)["processing"]["external_calls_enabled"] is False


@pytest.mark.parametrize("case", ["hash", "revision", "duplicate", "pending", "too_large"])
def test_invalid_input_does_not_reserve_budget_or_create_job(client, case):
    source = capture(client)
    refs = [source_ref(source)]
    if case == "hash":
        refs[0]["blob_hash"] = "a" * 64
    elif case == "revision":
        refs[0]["material_revision"] = 999
    elif case == "duplicate":
        refs *= 2
    elif case == "pending":
        pending = client.post(
            "/api/v1/captures",
            json={"title": "无正文", "url": "https://example.org", "kind": "web_page"},
        ).json()
        refs = [source_ref(pending)]
    elif case == "too_large":
        large = client.post(
            "/api/v1/captures", json={"title": "长文", "content": "中" * 60001}
        ).json()
        refs = [source_ref(large)]
    assert client.post("/api/v1/digest/jobs", json={"source_refs": refs}).status_code == 422
    assert not state(client)["jobs"] and state(client)["processing"]["budget"]["reserved"] == 0


def test_code_only_is_visible_failure_not_false_completed_digest(client):
    source = client.post(
        "/api/v1/captures",
        json={"title": "代码", "content": "```\n" + "abcdefghijklmnop\n" * 300 + "```"},
    ).json()
    submit(client, source)
    client.app.state.pipeline.run_once()
    assert state(client)["jobs"][0]["error_code"] == "NO_EVIDENCE"


def test_mixed_sources_show_partial_excerpt_coverage(client):
    prose = capture(client)
    code = client.post(
        "/api/v1/captures", json={"title": "纯代码", "content": "```\nabcdefghijklmnop\n```"}
    ).json()
    client.app.state.pipeline.submit([source_ref(prose), source_ref(code)])
    client.app.state.pipeline.run_once()
    result = state(client)["digests"][0]
    assert result["coverage_state"] == "partial"
    assert {s["material_id"] for s in result["source_coverage"] if s["status"] == "no_excerpt"} == {
        code["id"]
    }


def test_worker_runs_in_app_lifespan_and_survives_page_close(client):
    from fastapi.testclient import TestClient

    from panming.app import create_app

    job = submit(client)
    with TestClient(create_app(client.app.state.store, start_worker=True)) as worker_app:
        # Wait on the visible API contract, not sleeps or wall-time assertions.
        for _ in range(100):
            status = worker_app.get(f"/api/v1/objects/{job['id']}").json()
            if status["state"] == "succeeded":
                break
        assert status["state"] == "succeeded"
    assert state(client)["jobs"][0]["state"] == "succeeded"


def test_chunks_cover_unicode_long_lines_exactly_and_are_stable():
    source = {
        "id": "material_unicode",
        "revision": 1,
        "blob_hash": "a" * 64,
        "title": "中文🌟",
        "topic": "thinking",
        "content": "🦀中文\r\n" + "汉" * 7000 + "\n末尾",
    }
    chunks = chunks_for(source)
    assert "".join(c["text"] for c in chunks) == source["content"]
    assert chunks == chunks_for(source)
    for c in chunks:
        assert c["text"] == source["content"][c["offset"] : c["end"]]
        assert hashlib.sha256(c["text"].encode()).hexdigest() == c["chunk_hash"]
    newer = chunks_for({**source, "revision": 2})
    assert {c["chunk_id"] for c in chunks}.isdisjoint(c["chunk_id"] for c in newer)


def test_pipeline_backup_preserves_completed_evidence_and_pauses_active_jobs(client, empty_store):
    submit(client)
    client.app.state.pipeline.run_once()
    queued = submit(client, capture(client, "等待中的任务"))
    running = submit(client, capture(client, "正在执行"))
    client.app.state.pipeline.claim("old-worker")
    before = state(client)
    raw = export_workspace(client.app.state.store)
    inspect_archive(raw)
    result = restore_workspace(empty_store, raw)
    assert result["paused_jobs"] == 2
    restored = Pipeline(empty_store)
    assert not restored.run_once()
    with empty_store.transaction() as conn:
        jobs = empty_store.list(conn, "job")
        assert empty_store.list(conn, "digest") == before["digests"]
    for job in jobs:
        if job["id"] in {queued["id"], running["id"]}:
            assert job["state"] == "paused" and job["reserved_units"] == 0
    assert restored.action(queued["id"], "retry")["state"] == "queued"
    restored.run_once()
    inspect_archive(export_workspace(empty_store))


@pytest.mark.parametrize(
    "mutation", ["chunk_text", "output_quote", "output_ref", "embedded", "budget"]
)
def test_tampered_pipeline_archive_refused_before_restore(client, empty_store, mutation):
    submit(client)
    client.app.state.pipeline.run_once()
    client.post("/api/v1/reports/runs", json={"date": today()})
    raw = export_workspace(client.app.state.store)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        files = {n: archive.read(n) for n in archive.namelist()}
    metadata = json.loads(files["metadata.json"])
    artifact = next(o for o in metadata["objects"] if o["kind"] == "digest")
    if mutation == "chunk_text":
        artifact["data"]["chunks"][0]["text"] = "伪造原文"
    elif mutation == "output_quote":
        artifact["data"]["output"]["claims"][0]["citations"][0]["quote"] = "伪造引用"
    elif mutation == "output_ref":
        artifact["data"]["job_fence"] = 999
    elif mutation == "embedded":
        artifact = next(o for o in metadata["objects"] if o["kind"] == "report")
        artifact["data"]["evidence_digests"][0]["output"]["claims"][0]["text"] = "篡改报告里的消化"
    elif mutation == "budget":
        artifact = next(o for o in metadata["objects"] if o["kind"] == "job")
        artifact["data"]["used_units"] = -1
    for revision in metadata["revisions"]:
        if revision["object_id"] == artifact["id"] and revision["revision"] == artifact["revision"]:
            revision["data"] = copy.deepcopy(artifact["data"])
    files["metadata.json"] = json.dumps(metadata, ensure_ascii=False).encode()
    manifest = json.loads(files["manifest.json"])
    manifest["files"]["metadata.json"] = hashlib.sha256(files["metadata.json"]).hexdigest()
    files["manifest.json"] = json.dumps(manifest).encode()
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for name, body in files.items():
            archive.writestr(name, body)
    with pytest.raises(BackupError):
        restore_workspace(empty_store, out.getvalue())
    with empty_store.transaction() as conn:
        assert not empty_store.list(conn, "job") and not empty_store.list(conn, "material")


def test_legacy_schema1_backup_still_restores(client, empty_store):
    capture(client)
    raw = export_workspace(client.app.state.store)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        files = {n: archive.read(n) for n in archive.namelist()}
    manifest = json.loads(files["manifest.json"])
    manifest["schema_version"] = 1
    files["manifest.json"] = json.dumps(manifest).encode()
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for name, body in files.items():
            archive.writestr(name, body)
    assert restore_workspace(empty_store, out.getvalue())["objects"] == 1


@pytest.mark.parametrize("index", range(30))
def test_synthetic_evidence_corpus_mechanical_validity_not_semantic_quality(index):
    contents = [
        "# Grace Hash Join\n\nBuild 与 Probe 应遵守相同的分区规则，使相同键在同一分区相遇。",
        "# 不同条件\n\n同一个热点键无法靠增加哈希位拆开，更多分区不保证解决倾斜。",
        "用户：模型推断可能不正确，我会先留下出处，再通过实验验证该结论。",
        "```\nnot_a_fact_from_a_code_block\n```\n\n这是代码之后的正文段落，只能作为来源陈述而非已验证事实。",
        "# 方法\n\n- 先写自己的中心问题，再整理材料中的线索，不能以摘录代替理解。",
    ]
    source = {
        "id": f"material_eval_{index}",
        "revision": 1,
        "blob_hash": "a" * 64,
        "title": "合成评估输入",
        "topic": "database",
        "content": contents[index % len(contents)],
    }
    chunks = chunks_for(source)
    output = validate_output(MockProvider().generate(chunks), chunks)
    assert all(c["kind"] == "source_statement" for c in output["claims"])
    assert all(
        cite["quote"] in source["content"] for c in output["claims"] for cite in c["citations"]
    )
