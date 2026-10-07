"""No real network: compatible API, privacy, usage and restart failure contracts."""

import asyncio
import copy
import hashlib
import io
import json
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from test_reliability import empty_store as empty_store
from test_workflow import capture
from test_workflow import client as client

from panming.app import source_ref, today
from panming.backup import BackupError, export_workspace, inspect_archive, restore_workspace
from panming.llm import (
    LLMConfig,
    LLMConfigError,
    LLMError,
    OpenAICompatibleProvider,
    env_values,
    load_config,
)
from panming.pipeline import MockProvider, Pipeline, PipelineError

SECRET = "synthetic-test-credential-not-real"


def config(**kwargs):
    return LLMConfig(
        api_key=SECRET,
        base_url="https://api.example/compatible-mode/v1",
        model="qwen-test",
        **kwargs,
    )


def completion(request, *, mode="ok", usage=True):
    data = json.loads(request.content)
    assert request.url.path == "/compatible-mode/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer " + SECRET
    assert data["response_format"] == {"type": "json_object"}
    assert data["max_tokens"] == 4096 and data["enable_thinking"] is False
    assert "tools" not in data and data["stream"] is False
    chunks = json.loads(data["messages"][1]["content"])["source_chunks"]
    output = MockProvider().generate(chunks)
    output["claims"][0]["text"] = "来源认为分区恢复需要重建局部状态；适用条件仍需实验。"
    if mode == "citation":
        output["claims"][0]["citations"][0]["quote"] = "原文中不存在的引用"
    if mode == "secret":
        output["claims"][0]["text"] = SECRET
    content = "not JSON" if mode == "json" else json.dumps(output, ensure_ascii=False)
    raw = {
        "id": "chatcmpl-synthetic",
        "choices": [
            {
                "finish_reason": "length" if mode == "length" else "stop",
                "message": {"content": content},
            }
        ],
    }
    if usage:
        raw["usage"] = {"prompt_tokens": 100, "completion_tokens": 80, "total_tokens": 180}
    return httpx.Response(200, json=raw)


def install(client, handler=None, **config_kwargs):
    provider = OpenAICompatibleProvider(
        config(**config_kwargs), transport=httpx.MockTransport(handler or completion)
    )
    pipeline = Pipeline(
        client.app.state.store, providers={"mock": MockProvider(), "openai_compatible": provider}
    )
    client.app.state.pipeline = pipeline
    return pipeline, provider


def authorize(client, source):
    profile = client.app.state.pipeline.providers["openai_compatible"].profile()
    response = client.patch(
        f"/api/v1/materials/{source['id']}/policy",
        json={
            "revision": source["revision"],
            "processing_policy": "cloud_allowed",
            "provider_profile": profile["profile_id"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def submit_cloud(client, source):
    profile = client.app.state.pipeline.providers["openai_compatible"].profile()
    response = client.post(
        "/api/v1/digest/jobs",
        json={
            "source_refs": [source_ref(source)],
            "provider": "openai_compatible",
            "cloud_consent": True,
            "provider_profile": profile["profile_id"],
        },
    )
    assert response.status_code == 202, response.text
    return response.json()


def processing(client):
    return client.get("/api/v1/processing").json()


def test_env_file_is_data_whitelist_process_priority_and_redacted(tmp_path):
    path = tmp_path / "input.env"
    marker = tmp_path / "must-not-exist"
    path.write_text(
        f"IGNORED_COMMAND=$(touch {marker})\nexport LLM_API_KEY='{SECRET}' # comment\nLLM_MODEL=qwen-file\nLLM_BASE_URL=https://api.example/compatible-mode/v1\nLLM_TIMEOUT=300\nDATABASE_PASSWORD=synthetic-private\n"
    )
    loaded = load_config({}, path)
    assert loaded.model == "qwen-file" and loaded.timeout == 300
    process = load_config(
        {
            "LLM_MODEL": "qwen-process",
            "LLM_API_KEY": SECRET,
            "LLM_BASE_URL": "https://process.example/v1",
            "LLM_TIMEOUT": "120",
        },
        path,
    )
    assert (
        process.model == "qwen-process"
        and process.base_url == "https://process.example/v1"
        and process.timeout == 120
    )
    with pytest.raises(LLMConfigError, match="INCOMPLETE"):
        load_config({"LLM_MODEL": "qwen-process"}, path)
    assert SECRET not in repr(loaded) and SECRET not in json.dumps(loaded.profile())
    assert set(env_values(path)) == {"LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL", "LLM_TIMEOUT"}
    assert not marker.exists()
    assert load_config({"PANMING_LLM_DISABLED": "1"}, path) is None


@pytest.mark.parametrize("field", ["LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "LLM_TIMEOUT"])
def test_partial_environment_cannot_mix_file_credentials_with_new_endpoint(tmp_path, field):
    path = tmp_path / "profile.env"
    path.write_text(
        f"LLM_API_KEY={SECRET}\nLLM_BASE_URL=https://file.example/v1\nLLM_MODEL=qwen-file\nLLM_TIMEOUT=120\n"
    )
    value = {
        "LLM_API_KEY": "process-credential",
        "LLM_BASE_URL": "https://other.example/v1",
        "LLM_MODEL": "other-model",
        "LLM_TIMEOUT": "20",
    }[field]
    with pytest.raises(LLMConfigError, match="INCOMPLETE"):
        load_config({field: value}, path)


def test_dotenv_bom_hash_comments_and_invalid_profile_syntax(tmp_path):
    path = tmp_path / "profile.env"
    path.write_text(
        "\ufeffexport LLM_API_KEY=synthetic#credential # a real comment\r\nLLM_BASE_URL='https://file.example/v1'\r\nLLM_MODEL=qwen-file\r\nLLM_TIMEOUT=120\r\n"
    )
    assert load_config({}, path).api_key == "synthetic#credential"
    path.write_text("LLM_MODEL=first\nLLM_MODEL=second\n")
    with pytest.raises(LLMConfigError, match="DUPLICATE"):
        load_config({}, path)
    path.write_text("LLM_API_KEY='${UNRELATED_SECRET}'\n")
    with pytest.raises(LLMConfigError, match="EXPANSION"):
        load_config({}, path)


@pytest.mark.parametrize(
    "values",
    [
        {"LLM_API_KEY": SECRET},
        {"LLM_API_KEY": SECRET, "LLM_BASE_URL": "http://api.example/v1", "LLM_MODEL": "qwen-test"},
        {
            "LLM_API_KEY": SECRET,
            "LLM_BASE_URL": "https://user:password@api.example/v1",
            "LLM_MODEL": "qwen-test",
        },
        {
            "LLM_API_KEY": SECRET,
            "LLM_BASE_URL": "https://api.example/v1?key=secret",
            "LLM_MODEL": "qwen-test",
        },
        {
            "LLM_API_KEY": SECRET,
            "LLM_BASE_URL": "https://api.example/v1",
            "LLM_MODEL": "qwen-test",
            "LLM_TIMEOUT": "nan",
        },
    ],
)
def test_invalid_config_fail_closed_no_value_in_diagnostic(tmp_path, values):
    with pytest.raises(LLMConfigError) as error:
        load_config(values, tmp_path / "absent")
    assert SECRET not in str(error.value)


def test_private_default_and_destination_confirmation_prevent_requests(client):
    calls = []
    pipeline, provider = install(client, lambda req: calls.append(req) or completion(req))
    source = capture(client)
    refs = [source_ref(source)]
    with pytest.raises(PipelineError) as error:
        pipeline.submit(refs, "openai_compatible")
    assert error.value.code == "CLOUD_CONSENT_REQUIRED"
    with pytest.raises(PipelineError) as error:
        pipeline.submit(
            refs,
            "openai_compatible",
            cloud_consent=True,
            provider_profile=provider.profile()["profile_id"],
        )
    assert error.value.code == "POLICY_BLOCKED"
    assert not calls and not processing(client)["jobs"]
    assert (
        client.patch(
            f"/api/v1/materials/{source['id']}/policy",
            json={
                "revision": 1,
                "processing_policy": "cloud_allowed",
                "provider_profile": "a" * 64,
            },
        ).status_code
        == 409
    )
    allowed = authorize(client, source)
    assert allowed["revision"] == 2 and allowed["content"] == source["content"]
    assert (
        client.get(f"/api/v1/materials/{source['id']}/original?revision=1").text
        == source["content"]
    )
    assert not calls  # Granting policy is not a model call.
    response = client.post(
        "/api/v1/digest/jobs",
        json={
            "source_refs": [source_ref(allowed)],
            "provider": "openai_compatible",
            "cloud_consent": True,
            "provider_profile": "b" * 64,
        },
    )
    assert response.status_code == 403 and not calls


def test_real_protocol_delivery_usage_export_report_and_secret_free_backup(client, empty_store):
    pipeline, provider = install(client)
    source = authorize(client, capture(client))
    blog = client.post(
        "/api/v1/blogs", json={"title": "人工内容", "source_refs": [source_ref(source)]}
    ).json()
    job = submit_cloud(client, source)
    assert submit_cloud(client, source)["id"] == job["id"]
    before = processing(client)["processing"]["budget"]["cloud"]
    assert before["reserved_requests"] == 1 and before["requests"] == 0
    assert pipeline.run_once()
    result = processing(client)
    assert result["jobs"][0]["state"] == "succeeded"
    artifact = result["digests"][0]
    assert artifact["mode"] == "cloud_llm" and artifact["model"] == provider.config.model
    assert artifact["provider_profile"] == provider.profile()
    assert artifact["call_attempts"][0]["usage"]["total_tokens"] == 180
    budget = result["processing"]["budget"]
    assert budget["cost"] is None and budget["cloud"]["actual_tokens"] == 180
    assert budget["cloud"]["reserved_tokens"] == 0
    assert budget["cloud"]["requests"] == 1
    assert client.get(f"/api/v1/objects/{blog['id']}").json() == blog
    report = client.post("/api/v1/reports/runs", json={"date": today()}).json()
    assert report["generation_mode"] == "llm_evidence" and len(report["evidence_digests"]) == 1
    exported = client.get(f"/api/v1/export/{artifact['id']}").text
    assert "真实模型" in exported and f"?revision={source['revision']}" in exported
    raw = export_workspace(pipeline.store)
    metadata, _ = inspect_archive(raw)
    assert SECRET not in json.dumps(metadata) and SECRET not in json.dumps(result)
    assert restore_workspace(empty_store, raw)["restored"]
    inspect_archive(export_workspace(empty_store))


@pytest.mark.parametrize(
    "mode,code",
    [
        ("citation", "INVALID_EVIDENCE"),
        ("json", "LLM_INVALID_RESPONSE"),
        ("length", "LLM_OUTPUT_INCOMPLETE"),
        ("secret", "LLM_CREDENTIAL_ECHO"),
    ],
)
def test_invalid_llm_output_rejected_but_actual_usage_not_erased(client, mode, code):
    pipeline, _ = install(client, lambda req: completion(req, mode=mode))
    source = authorize(client, capture(client))
    submit_cloud(client, source)
    pipeline.run_once()
    state = processing(client)
    assert state["jobs"][0]["error_code"] == code and not state["digests"]
    assert state["processing"]["budget"]["cloud"]["actual_tokens"] == 180
    assert SECRET not in json.dumps(state)


def test_missing_usage_keeps_conservative_charge_not_zero(client):
    pipeline, _ = install(client, lambda req: completion(req, usage=False))
    submit_cloud(client, authorize(client, capture(client)))
    pipeline.run_once()
    state = processing(client)
    assert state["jobs"][0]["state"] == "succeeded"
    quota = state["processing"]["budget"]["cloud"]
    assert quota["actual_tokens"] == 0 and quota["uncertain_tokens"] > 0
    assert quota["reserved_tokens"] == 0 and state["processing"]["budget"]["cost"] is None


@pytest.mark.parametrize(
    "status,code,uncertain",
    [
        (401, "LLM_AUTH_FAILED", False),
        (429, "LLM_RATE_LIMIT", False),
        (503, "LLM_HTTP_FAILED", True),
        (307, "LLM_REDIRECT_BLOCKED", False),
    ],
)
def test_upstream_error_no_auto_retry_no_body_or_key_leak(client, status, code, uncertain):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status,
            text=f"sensitive echo {SECRET}",
            headers={"Location": "https://other.example/steal"},
        )

    pipeline, _ = install(client, handler)
    submit_cloud(client, authorize(client, capture(client)))
    pipeline.run_once()
    state = processing(client)
    assert len(calls) == 1 and state["jobs"][0]["error_code"] == code
    quota = state["processing"]["budget"]["cloud"]
    assert quota["requests"] == 1 and bool(quota["uncertain_tokens"]) == uncertain
    assert SECRET not in json.dumps(state) and not state["digests"]


def test_absolute_timeout_and_cooperative_cancellation_no_hidden_retry():
    calls = []

    async def handler(request):
        calls.append(request)
        await asyncio.sleep(10)
        return completion(request)

    chunks = [{"chunk_id": "chunk_test", "text": "这是足够长的合成输入，用于验证取消和总超时。"}]
    provider = OpenAICompatibleProvider(
        config(timeout=0.05), transport=httpx.MockTransport(handler)
    )
    with pytest.raises(LLMError) as error:
        provider.generate_with_usage(chunks, lambda: False)
    assert error.value.code == "LLM_TIMEOUT" and len(calls) == 1
    cancelled = threading.Event()
    started = threading.Event()

    async def cancellable(request):
        started.set()
        await asyncio.sleep(10)
        return completion(request)

    provider = OpenAICompatibleProvider(config(), transport=httpx.MockTransport(cancellable))
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(provider.generate_with_usage, chunks, cancelled.is_set)
        assert started.wait(2)
        cancelled.set()
        with pytest.raises(LLMError) as error:
            future.result(timeout=2)
    assert error.value.code == "CALL_CANCELLED"


def test_cancelled_late_result_is_settled_but_not_published(client):
    started, release = threading.Event(), threading.Event()

    async def handler(request):
        started.set()
        while not release.is_set():
            await asyncio.sleep(0.01)
        return completion(request)

    pipeline, _ = install(client, handler)
    job = submit_cloud(client, authorize(client, capture(client)))
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(pipeline.run_once)
        assert started.wait(2)
        assert pipeline.action(job["id"], "cancel")["state"] == "cancelled"
        assert processing(client)["processing"]["budget"]["cloud"]["reserved_tokens"] > 0
        release.set()
        assert future.result(timeout=3)
    result = processing(client)
    assert result["jobs"][0]["state"] == "cancelled" and not result["digests"]
    assert result["processing"]["budget"]["cloud"]["actual_tokens"] == 180


def test_shutdown_aborts_call_keeps_uncertain_ledger_for_restart(client):
    started, stop = threading.Event(), threading.Event()

    async def handler(request):
        started.set()
        await asyncio.sleep(10)
        return completion(request)

    pipeline, _ = install(client, handler)
    submit_cloud(client, authorize(client, capture(client)))
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(pipeline.run_once, "stopping", stop)
        assert started.wait(2)
        stop.set()
        assert future.result(timeout=3)
    state = processing(client)
    assert state["jobs"][0]["error_code"] == "CALL_CANCELLED"
    assert state["processing"]["budget"]["cloud"]["uncertain_tokens"] > 0
    assert not pipeline.run_once()


def test_expired_paid_request_never_auto_reissued_and_restore_retains_quota(client, empty_store):
    calls = []
    pipeline, provider = install(client, lambda req: calls.append(req) or completion(req))
    clock = [datetime.now(timezone.utc)]
    pipeline.clock = lambda: clock[0]
    job = submit_cloud(client, authorize(client, capture(client)))
    claimed = pipeline.claim("dead")
    call = pipeline.begin_call(claimed)
    raw = export_workspace(pipeline.store)
    assert restore_workspace(empty_store, raw)["paused_jobs"] == 1
    restored = Pipeline(
        empty_store, providers={"mock": MockProvider(), "openai_compatible": provider}
    )
    assert not restored.run_once()
    with empty_store.transaction() as conn:
        saved = empty_store.get(conn, job["id"])
        assert saved["call_attempts"][0]["state"] == "uncertain"
        assert restored.budget(conn)["cloud"]["uncertain_tokens"] == call["token_reservation"]
    clock[0] += timedelta(seconds=31)
    assert not pipeline.run_once() and not calls
    assert processing(client)["jobs"][0]["error_code"] == "CALL_INTERRUPTED"
    assert not pipeline.finish(claimed, MockProvider().generate(claimed["chunks"]))
    inspect_archive(export_workspace(empty_store))


def test_retry_requires_fresh_cloud_confirmation_and_limits_apply(client):
    pipeline, provider = install(client, lambda req: httpx.Response(401), daily_requests=1)
    source = authorize(client, capture(client))
    job = submit_cloud(client, source)
    pipeline.run_once()
    with pytest.raises(PipelineError) as error:
        pipeline.action(job["id"], "retry")
    assert error.value.code == "CLOUD_CONSENT_REQUIRED"
    with pytest.raises(PipelineError) as error:
        pipeline.action(
            job["id"],
            "retry",
            cloud_consent=True,
            provider_profile=provider.profile()["profile_id"],
        )
    assert error.value.code == "LLM_BUDGET_EXCEEDED"
    assert processing(client)["jobs"][0]["state"] == "failed"


def test_parallel_cloud_submit_reserves_once_and_second_input_is_blocked(client):
    pipeline, provider = install(client, daily_requests=1)
    source = authorize(client, capture(client))

    def submit(_):
        return pipeline.submit(
            [source_ref(source)],
            "openai_compatible",
            cloud_consent=True,
            provider_profile=provider.profile()["profile_id"],
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = list(pool.map(submit, range(4)))
    assert len({j["id"] for j in jobs}) == 1
    other = authorize(client, capture(client, "不同输入"))
    with pytest.raises(PipelineError) as error:
        pipeline.submit(
            [source_ref(other)],
            "openai_compatible",
            cloud_consent=True,
            provider_profile=provider.profile()["profile_id"],
        )
    assert error.value.code == "LLM_BUDGET_EXCEEDED"
    assert processing(client)["processing"]["budget"]["cloud"]["reserved_requests"] == 1


def test_body_edit_revokes_consent_cancels_pending_job_and_old_blob_survives(client):
    pipeline, _ = install(client)
    source = authorize(client, capture(client))
    submit_cloud(client, source)
    revised = client.post(
        f"/api/v1/materials/{source['id']}/revisions",
        json={
            "title": source["title"],
            "body": "新的私人内容，不能继承上一版本的云端许可。",
            "revision": source["revision"],
        },
    ).json()
    assert revised["processing_policy"] == "local_only" and revised["cloud_allowed_profile"] is None
    assert processing(client)["jobs"][0]["state"] == "cancelled"
    assert not pipeline.run_once()
    assert (
        client.get(f"/api/v1/materials/{source['id']}/original?revision=2").text
        == source["content"]
    )


def test_service_profile_change_does_not_route_old_job_to_new_host(client):
    pipeline, _ = install(client)
    source = authorize(client, capture(client))
    submit_cloud(client, source)
    new = OpenAICompatibleProvider(
        LLMConfig(api_key=SECRET, base_url="https://new.example/v1", model="qwen-test"),
        transport=httpx.MockTransport(
            lambda req: pytest.fail("old consent cannot reach new service")
        ),
    )
    pipeline.providers["openai_compatible"] = new
    pipeline.run_once()
    assert not processing(client)["digests"]
    assert processing(client)["jobs"][0]["error_code"] in {
        "LLM_PROFILE_CHANGED",
        "POLICY_DESTINATION_BLOCKED",
    }


@pytest.mark.parametrize("field", ["credential", "usage", "consent"])
def test_cloud_archive_tampering_refused_before_writes(client, empty_store, field):
    pipeline, _ = install(client)
    submit_cloud(client, authorize(client, capture(client)))
    pipeline.run_once()
    raw = export_workspace(pipeline.store)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        files = {n: archive.read(n) for n in archive.namelist()}
    metadata = json.loads(files["metadata.json"])
    job = next(o for o in metadata["objects"] if o["kind"] == "job")
    if field == "credential":
        job["data"]["provider_profile"]["api_key"] = "must-not-import"
    elif field == "usage":
        job["data"]["call_attempts"][0]["usage"]["total_tokens"] = -1
    else:
        job["data"]["cloud_consent"] = False
    for rev in metadata["revisions"]:
        if rev["object_id"] == job["id"] and rev["revision"] == job["revision"]:
            rev["data"] = copy.deepcopy(job["data"])
    files["metadata.json"] = json.dumps(metadata).encode()
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
        assert not empty_store.list(conn, "material")
