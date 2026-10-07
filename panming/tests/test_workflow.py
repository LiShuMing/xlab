"""Real PostgreSQL workflows, isolated in disposable test schemas."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from panming.app import create_app, today
from panming.storage import Store, database_url


@pytest.fixture()
def client(tmp_path):
    schema = "panming_test_" + uuid.uuid4().hex
    admin = create_engine(database_url())
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    store = Store(database_url(), tmp_path, {"options": f"-csearch_path={schema}"})
    with TestClient(create_app(store)) as http:
        yield http
    store.engine.dispose()
    with admin.begin() as conn:
        conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    admin.dispose()


def capture(client, title="测试素材"):
    response = client.post(
        "/api/v1/captures",
        json={
            "title": title,
            "content": "分区恢复时应该重建局部状态。这个结论需要通过可复现的实验进一步验证。",
            "topic": "database",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_capture_idempotency_and_original_file(client, tmp_path):
    payload = {"title": "原件", "content": "原始文字不要因为模型生成而被覆盖。"}
    headers = {"Idempotency-Key": "retry-1"}
    first = client.post("/api/v1/captures", json=payload, headers=headers)
    repeated = client.post("/api/v1/captures", json=payload, headers=headers)
    assert first.json()["id"] == repeated.json()["id"]
    assert len(client.get("/api/v1/bootstrap").json()["materials"]) == 1
    mismatch = client.post(
        "/api/v1/captures", json={**payload, "content": "不同正文"}, headers=headers
    )
    assert mismatch.status_code == 409
    original = client.get(f"/api/v1/export/{first.json()['id']}")
    assert original.text == payload["content"]


def test_report_freezes_input_and_preserves_revisions(client):
    capture(client, "早到素材")
    first = client.post("/api/v1/reports/runs", json={"date": today()}).json()
    capture(client, "晚到素材")
    frozen = client.get("/api/v1/bootstrap").json()["reports"][0]
    assert len(frozen["sources"]) == 1
    second = client.post("/api/v1/reports/runs", json={"date": today()}).json()
    assert first["id"] == second["id"]
    assert second["revision"] == 2 and len(second["sources"]) == 2
    history = client.get(f"/api/v1/objects/{first['id']}/revisions").json()
    assert len(history) == 2 and len(history[1]["sources"]) == 1


def test_blog_save_conflict_and_library_adoption(client):
    material = capture(client)
    blog = client.post(
        "/api/v1/blogs", json={"title": "我的理解", "material_ids": [material["id"]]}
    ).json()
    assert client.post("/api/v1/library/proposals", json={"blog_id": blog["id"]}).status_code == 422
    edit = {
        "title": "我的理解",
        "body": "# 我自己的论点\n\n实测待补充。",
        "revision": blog["revision"],
    }
    saved = client.post(f"/api/v1/blogs/{blog['id']}/revisions", json=edit).json()
    assert client.post(f"/api/v1/blogs/{blog['id']}/revisions", json=edit).status_code == 409
    accepted = client.post(
        f"/api/v1/blogs/{blog['id']}/accept", json={"revision": saved["revision"]}
    ).json()
    proposal = client.post("/api/v1/library/proposals", json={"blog_id": accepted["id"]}).json()
    first = client.post(f"/api/v1/library/proposals/{proposal['id']}/accept", json={}).json()
    second = client.post(f"/api/v1/library/proposals/{proposal['id']}/accept", json={}).json()
    assert first["id"] == second["id"] and first["body"] == edit["body"]
    review = client.post(
        f"/api/v1/library/entries/{first['id']}/reviews", json={"grade": "clear"}
    ).json()
    assert len(review["reviews"]) == 1 and review["due_day"] > today()


def test_links_are_stored_without_claiming_to_have_read_them(client):
    material = client.post(
        "/api/v1/captures",
        json={"title": "仅链接", "kind": "web_page", "url": "https://example.org/private"},
    ).json()
    assert material["parse_state"] == "needs_input"
    report = client.post("/api/v1/reports/runs", json={"date": today()}).json()
    assert report["coverage_state"] == "partial" and report["ready_count"] == 0
    assert report["briefs"] == []


def test_cross_site_and_unsafe_scheme_rejected(client):
    assert (
        client.post(
            "/api/v1/demo", json={}, headers={"Origin": "https://malicious.example"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/captures", json={"title": "不安全", "url": "javascript:alert(1)"}
        ).status_code
        == 422
    )


def test_demo_is_explicitly_marked_and_repeatable(client):
    assert client.post("/api/v1/demo", json={}).json()["seeded"]
    assert not client.post("/api/v1/demo", json={}).json()["seeded"]
    state = client.get("/api/v1/bootstrap").json()
    assert len(state["materials"]) == 5
    assert all(m["is_demo"] for m in state["materials"])
    assert len(state["reports"]) == 1 and len(state["entries"]) == 1


def test_revised_source_does_not_change_old_report_or_original(client):
    source = capture(client)
    old = client.post("/api/v1/reports/runs", json={"date": today()}).json()
    revised = client.post(
        f"/api/v1/materials/{source['id']}/revisions",
        json={
            "title": source["title"],
            "body": "这是一段修订后的正文，旧报告应继续保留原始引用。",
            "revision": source["revision"],
        },
    ).json()
    client.post("/api/v1/reports/runs", json={"date": today()})
    draft = client.post(
        "/api/v1/blogs",
        json={
            "title": "基于旧版写作",
            "material_ids": [source["id"]],
            "report_id": old["id"],
            "report_revision": 1,
        },
    ).json()
    assert draft["source_snapshots"][0]["content"] == source["content"]
    assert revised["content"] != source["content"]
    assert (
        client.get(f"/api/v1/materials/{source['id']}/original?revision=1").text
        == source["content"]
    )
