"""Boundary, concurrency and provenance audit. Known failures stay explicit (strict xfail)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier, Event

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from test_workflow import capture  # noqa: I001
from test_workflow import client as client

from panming.app import today
from panming.content import digest


def state(client):
    return client.get("/api/v1/bootstrap").json()


def blog(client, source=None):
    source = source or capture(client)
    return client.post(
        "/api/v1/blogs", json={"title": "审计文章", "material_ids": [source["id"]]}
    ).json()


def accepted_proposal(client):
    draft = blog(client)
    accepted = client.post(
        f"/api/v1/blogs/{draft['id']}/accept", json={"revision": draft["revision"]}
    ).json()
    proposal = client.post("/api/v1/library/proposals", json={"blog_id": draft["id"]}).json()
    return accepted, proposal


@pytest.mark.parametrize(
    "payload",
    [
        {"title": ""},
        {"title": "x" * 201},
        {"title": "正常", "topic": "unknown"},
        {"title": "正常", "kind": "script"},
        {"title": "正常", "url": "file:///etc/passwd"},
        {"title": "正常", "url": "https://user:password@example.org"},
        {"title": "正常", "content": "x" * 500_001},
    ],
)
def test_invalid_capture_rejected_without_metadata(client, payload):
    assert client.post("/api/v1/captures", json=payload).status_code == 422
    assert state(client)["materials"] == []


@pytest.mark.parametrize(
    "raw", [b"", b"\xff\x00\x80", b"x" * 500_001], ids=["empty", "binary", "over-text-limit"]
)
def test_unparseable_file_keeps_exact_original(client, raw):
    response = client.post("/api/v1/captures/files", files={"file": ("audit.bin", raw)})
    assert response.status_code == 200
    item = response.json()
    assert item["parse_state"] == "stored_only"
    assert client.get(f"/api/v1/materials/{item['id']}/original").content == raw
    duplicate = client.post("/api/v1/captures/files", files={"file": ("audit.bin", raw)})
    assert duplicate.json()["id"] == item["id"]


def test_file_size_limit_and_utf8_bom(client):
    too_big = client.post(
        "/api/v1/captures/files", files={"file": ("big.bin", b"x" * (8 * 1024 * 1024 + 1))}
    )
    assert too_big.status_code == 413 and not state(client)["materials"]
    raw = b"\xef\xbb\xbf" + "UTF8 原文应该保留字节，正文去除 BOM 方便阅读。".encode()
    item = client.post("/api/v1/captures/files", files={"file": ("bom.md", raw)}).json()
    assert not item["content"].startswith("\ufeff")
    assert client.get(f"/api/v1/materials/{item['id']}/original").content == raw


def test_parallel_capture_idempotency(client):
    def send(_):
        return client.post(
            "/api/v1/captures",
            json={"title": "并发", "content": "同一份请求内容"},
            headers={"Idempotency-Key": "parallel"},
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(send, range(8)))
    assert [r.status_code for r in results] == [200] * 8
    assert len({r.json()["id"] for r in results}) == 1
    assert len(state(client)["materials"]) == 1


def test_parallel_blog_edit_has_one_winner(client):
    draft = blog(client)

    def save(index):
        return client.post(
            f"/api/v1/blogs/{draft['id']}/revisions",
            json={"title": "编辑", "body": f"版本 {index}", "revision": draft["revision"]},
        )

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(save, range(6)))
    assert sorted(r.status_code for r in results) == [200, 409, 409, 409, 409, 409]
    assert state(client)["blogs"][0]["revision"] == 2


def test_parallel_report_and_proposal_adoption(client):
    capture(client)
    with ThreadPoolExecutor(max_workers=5) as pool:
        reports = list(
            pool.map(
                lambda _: client.post("/api/v1/reports/runs", json={"date": today()}), range(5)
            )
        )
    assert all(r.status_code == 200 for r in reports)
    assert len({r.json()["id"] for r in reports}) == 1
    assert sorted(r.json()["revision"] for r in reports) == [1, 2, 3, 4, 5]
    _, proposal = accepted_proposal(client)
    with ThreadPoolExecutor(max_workers=5) as pool:
        entries = list(
            pool.map(
                lambda _: client.post(f"/api/v1/library/proposals/{proposal['id']}/accept"),
                range(5),
            )
        )
    assert all(r.status_code == 200 for r in entries)
    assert len({r.json()["id"] for r in entries}) == 1
    assert len(state(client)["entries"]) == 1


def test_stale_proposal_cannot_adopt_and_old_entry_stays_frozen(client):
    accepted, proposal = accepted_proposal(client)
    entry = client.post(f"/api/v1/library/proposals/{proposal['id']}/accept").json()
    old_body = entry["body"]
    changed = client.post(
        f"/api/v1/blogs/{accepted['id']}/revisions",
        json={
            "title": "更新",
            "body": "新观点不能悄悄覆盖图书馆。",
            "revision": accepted["revision"],
        },
    ).json()
    assert state(client)["entries"][0]["body"] == old_body
    client.post(f"/api/v1/blogs/{accepted['id']}/accept", json={"revision": changed["revision"]})
    new_proposal = client.post("/api/v1/library/proposals", json={"blog_id": accepted["id"]}).json()
    latest = state(client)["blogs"][0]
    client.post(
        f"/api/v1/blogs/{accepted['id']}/revisions",
        json={"title": "再次修改", "body": "提案已失效。", "revision": latest["revision"]},
    )
    assert client.post(f"/api/v1/library/proposals/{new_proposal['id']}/accept").status_code == 409


def test_cross_day_carryover_and_revised_content(client):
    source = capture(client)
    yesterday = (date.fromisoformat(today()) - timedelta(days=1)).isoformat()
    store = client.app.state.store
    with store.transaction() as conn:
        store.update(conn, {**source, "day": yesterday}, source["revision"])
    without = client.post(
        "/api/v1/reports/runs", json={"date": today(), "include_carryover": False}
    ).json()
    assert not without["sources"]
    old = client.post("/api/v1/reports/runs", json={"date": yesterday}).json()
    assert old["sources"][0]["id"] == source["id"]
    covered = client.post("/api/v1/reports/runs", json={"date": today()}).json()
    assert covered["coverage_state"] == "no_updates"
    changed = state(client)["materials"][0]
    client.post(
        f"/api/v1/materials/{source['id']}/revisions",
        json={
            "title": source["title"],
            "body": "前日素材补充的新正文，应纳入今日而不改写旧报告。",
            "revision": changed["revision"],
        },
    )
    new_report = client.post("/api/v1/reports/runs", json={"date": today()}).json()
    assert new_report["sources"][0]["inclusion_reason"] == "carryover"
    assert new_report["sources"][0]["content"] != old["sources"][0]["content"]


@pytest.mark.parametrize("grade,days", [("clear", 30), ("fuzzy", 7), ("forgot", 3)])
def test_review_interval_and_unknown_objects(client, grade, days):
    _, proposal = accepted_proposal(client)
    entry = client.post(f"/api/v1/library/proposals/{proposal['id']}/accept").json()
    revised = client.post(
        f"/api/v1/library/entries/{entry['id']}/reviews", json={"grade": grade}
    ).json()
    assert revised["due_day"] == (date.fromisoformat(today()) + timedelta(days=days)).isoformat()
    assert client.get("/api/v1/export/missing").status_code == 404
    assert (
        client.post(
            f"/api/v1/materials/{entry['id']}/feedback", json={"value": "useful"}
        ).status_code
        == 404
    )


def test_host_remote_client_and_security_headers(client):
    assert client.get("/api/v1/bootstrap", headers={"Host": "evil.example"}).status_code == 400
    with TestClient(client.app, client=("203.0.113.1", 1234)) as remote:
        assert remote.get("/api/v1/bootstrap").status_code == 403
    headers = client.get("/").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"


def test_future_report_and_evidence_subset_rejected(client):
    future = (date.fromisoformat(today()) + timedelta(days=1)).isoformat()
    assert client.post("/api/v1/reports/runs", json={"date": future}).status_code == 422
    capture(client, "已纳入")
    report = client.post("/api/v1/reports/runs", json={"date": today()}).json()
    late = capture(client, "未纳入")
    assert (
        client.post(
            "/api/v1/blogs",
            json={"title": "不属于快照", "material_ids": [late["id"]], "report_id": report["id"]},
        ).status_code
        == 422
    )


def test_source_and_settings_persistence(client):
    response = client.post(
        "/api/v1/sources",
        json={"title": "测试 RSS", "kind": "rss", "url": "https://example.org/feed"},
    )
    assert response.status_code == 200
    assert response.json()["enabled"] is False and response.json()["status"] == "manual"
    assert (
        client.post(
            "/api/v1/sources", json={"title": "本地文件", "url": "file:///etc/passwd"}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            "/api/v1/settings", json={"display_name": "研究工作台", "report_time": "24:00"}
        ).status_code
        == 422
    )
    first = client.patch(
        "/api/v1/settings", json={"display_name": "研究工作台", "report_time": "20:15"}
    ).json()
    second = client.patch(
        "/api/v1/settings", json={"display_name": "研究工作台二", "report_time": "20:15"}
    ).json()
    assert second["revision"] == first["revision"] + 1
    assert state(client)["settings"]["display_name"] == "研究工作台二"


def test_parallel_distinct_captures_with_same_key_have_one_conflict(client):
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda index: client.post(
                    "/api/v1/captures",
                    json={"title": f"不同素材 {index}", "content": "不能共用一个幂等标识。"},
                    headers={"Idempotency-Key": "same-key"},
                ),
                range(2),
            )
        )
    assert sorted(r.status_code for r in results) == [200, 409]
    assert len(state(client)["materials"]) == 1


def test_invalid_material_revision_does_not_mutate_original(client):
    source = capture(client)
    empty = client.post(
        f"/api/v1/materials/{source['id']}/revisions",
        json={"title": source["title"], "body": "   ", "revision": source["revision"]},
    )
    stale = client.post(
        f"/api/v1/materials/{source['id']}/revisions",
        json={
            "title": source["title"],
            "body": "正文不应该覆盖。",
            "revision": source["revision"] + 1,
        },
    )
    assert empty.status_code == 422 and stale.status_code == 409
    assert state(client)["materials"][0]["revision"] == 1
    assert client.get(f"/api/v1/materials/{source['id']}/original?revision=99").status_code == 404


def test_blog_source_list_deduplicates_and_wrong_revision_rejected(client):
    source = capture(client)
    report = client.post("/api/v1/reports/runs", json={"date": today()}).json()
    repeated = client.post(
        "/api/v1/blogs", json={"title": "重复列表", "material_ids": [source["id"], source["id"]]}
    ).json()
    assert repeated["material_ids"] == [source["id"]]
    assert (
        client.post(
            "/api/v1/blogs",
            json={
                "title": "不存在报告版本",
                "material_ids": [source["id"]],
                "report_id": report["id"],
                "report_revision": 99,
            },
        ).status_code
        == 404
    )
    assert (
        client.post(f"/api/v1/blogs/{repeated['id']}/accept", json={"revision": 99}).status_code
        == 409
    )


def test_server_recreation_keeps_saved_metadata_and_blobs(client):
    from panming.app import create_app

    source = capture(client)
    with TestClient(create_app(client.app.state.store)) as reopened:
        assert state(reopened)["materials"][0]["id"] == source["id"]
        assert reopened.get(f"/api/v1/materials/{source['id']}/original").text == source["content"]


def test_blob_write_dedup_and_rollback(client):
    store = client.app.state.store
    payload = b"audit-only immutable bytes"
    with ThreadPoolExecutor(max_workers=5) as pool:
        digests = list(pool.map(lambda _: store.put_blob(payload), range(5)))
    assert len(set(digests)) == 1
    files = [p for p in (store.data_dir / "blobs").rglob("*") if p.is_file()]
    assert len(files) == 1 and files[0].read_bytes() == payload
    with pytest.raises(RuntimeError, match="audit abort"):
        with store.transaction() as conn:
            store.insert(conn, "material", {"id": "audit_rollback", "object_kind": "material"})
            raise RuntimeError("audit abort")
    with store.transaction() as conn:
        assert store.get(conn, "audit_rollback") is None
        assert not store.revisions(conn, "audit_rollback")


# v0.2 audit regressions, now ordinary passing tests (no xfail suppression).
def test_report_brief_with_31_sources_is_actionable(client):
    for index in range(31):
        capture(client, f"数据库线索 {index}")
    report = client.post("/api/v1/reports/runs", json={"date": today()}).json()
    brief = report["briefs"][0]
    assert (
        client.post(
            "/api/v1/blogs",
            json={
                "title": brief["title"],
                "material_ids": brief["material_ids"],
                "report_id": report["id"],
                "report_revision": report["revision"],
            },
        ).status_code
        == 200
    )


def test_historical_report_export_respects_requested_revision(client):
    capture(client, "第一版素材")
    report = client.post("/api/v1/reports/runs", json={"date": today()}).json()
    capture(client, "只在第二版出现")
    client.post("/api/v1/reports/runs", json={"date": today()})
    exported = client.get(f"/api/v1/export/{report['id']}?revision=1")
    assert "只在第二版出现" not in exported.text
    assert "版本 1" in exported.text


def test_general_export_does_not_lose_binary_material(client):
    raw = b"\xff\x00\x80"
    source = client.post("/api/v1/captures/files", files={"file": ("raw.bin", raw)}).json()
    exported = client.get(f"/api/v1/export/{source['id']}")
    assert exported.status_code == 200 and exported.content == raw


def test_blank_capture_is_rejected(client):
    assert client.post("/api/v1/captures", json={"title": "   ", "content": ""}).status_code == 422


def test_nul_content_returns_validation_error(client):
    with TestClient(client.app, raise_server_exceptions=False) as safe:
        assert (
            safe.post(
                "/api/v1/captures", json={"title": "NUL", "content": "before\u0000after"}
            ).status_code
            == 422
        )


def test_malformed_origin_is_rejected_without_500(client):
    with TestClient(client.app, raise_server_exceptions=False) as safe:
        assert (
            safe.post(
                "/api/v1/captures",
                json={"title": "拒绝"},
                headers={"Origin": "http://localhost:not-a-port"},
            ).status_code
            == 403
        )


def test_malformed_url_is_validation_error_not_conflict(client):
    assert (
        client.post("/api/v1/captures", json={"title": "链接", "url": "https://["}).status_code
        == 422
    )


def test_proposal_identifier_type_is_validated(client):
    with TestClient(client.app, raise_server_exceptions=False) as safe:
        assert (
            safe.post("/api/v1/library/proposals", json={"blog_id": ["unexpected"]}).status_code
            == 422
        )


def test_parallel_initial_settings_save_has_no_server_error(client):
    barrier = Barrier(2)

    def save(index):
        barrier.wait(timeout=10)
        return client.patch(
            "/api/v1/settings", json={"display_name": f"窗口 {index}", "report_time": "21:30"}
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(save, range(2)))
    assert sorted(r.status_code for r in responses) == [200, 200]
    assert sorted(r.json()["revision"] for r in responses) == [1, 2]


def test_tilde_code_fence_is_not_natural_language_evidence():
    content = "~~~python\npassword = 'only-test-content'\n~~~\n\n这是一段真正的正文，应成为摘录而不是代码。"
    assert [q["text"] for q in digest(content)["excerpts"]] == [
        "这是一段真正的正文，应成为摘录而不是代码。"
    ]


def test_report_cutoff_does_not_claim_excluded_committed_input(client):
    capture(client, "已读到")
    store = client.app.state.store
    read_inputs, resume = Event(), Event()

    def synchronize(conn, cursor, statement, params, context, executemany):
        if "FROM pm_objects WHERE kind=" in statement and params.get("kind") == "report":
            read_inputs.set()
            if not resume.wait(timeout=10):
                raise TimeoutError("report synchronization timed out")

    event.listen(store.engine, "after_cursor_execute", synchronize)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            report_future = pool.submit(client.post, "/api/v1/reports/runs", json={"date": today()})
            if not read_inputs.wait(timeout=10):
                raise TimeoutError("report did not reach input snapshot")
            try:
                late_future = pool.submit(capture, client, "冻结过程中提交")
            finally:
                resume.set()
            report = report_future.result(timeout=10).json()
            late = late_future.result(timeout=10)
        assert late["created_at"] > report["cutoff_at"]
        assert late["id"] not in {source["id"] for source in report["sources"]}
    finally:
        resume.set()
        event.remove(store.engine, "after_cursor_execute", synchronize)


def test_invalid_capture_does_not_leave_unreferenced_blob(client):
    result = client.post(
        "/api/v1/captures",
        json={"title": "非法主题", "content": "应在落盘前拒绝这份素材。", "topic": "not-a-topic"},
    )
    assert result.status_code == 422
    assert not [p for p in client.app.state.store.data_dir.rglob("*") if p.is_file()]
