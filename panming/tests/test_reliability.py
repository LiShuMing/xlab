"""v0.3 provenance, full restore and startup safety regression tests."""

import fcntl
import hashlib
import io
import json
import os
import socket
import subprocess
import sys
import uuid
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from test_workflow import capture
from test_workflow import client as client

from panming.app import create_app, source_ref, today
from panming.backup import BackupError, export_workspace, restore_workspace
from panming.storage import ROOT, Store, database_url


@pytest.fixture()
def empty_store(tmp_path):
    schema = "panming_test_restore_" + uuid.uuid4().hex
    admin = create_engine(database_url())
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    store = Store(database_url(), tmp_path / "restored", {"options": f"-csearch_path={schema}"})
    try:
        yield store
    finally:
        store.engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def archive_files(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def zip_files(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, raw in files.items():
            archive.writestr(name, raw)
    return output.getvalue()


def test_old_source_refs_are_used_outside_report(client):
    source = capture(client)
    client.post(
        f"/api/v1/materials/{source['id']}/revisions",
        json={"title": source["title"], "body": "新版原文不应该偷偷替换博客证据。", "revision": 1},
    )
    draft = client.post(
        "/api/v1/blogs", json={"title": "旧版继续写作", "source_refs": [source_ref(source)]}
    ).json()
    assert draft["source_snapshots"][0]["content"] == source["content"]
    assert "?revision=1)" in draft["body"]
    assert (
        client.get(f"/api/v1/objects/{source['id']}?revision=1").json()["content"]
        == source["content"]
    )
    invalid = {**source_ref(source), "blob_hash": "a" * 64}
    assert (
        client.post("/api/v1/blogs", json={"title": "伪造", "source_refs": [invalid]}).status_code
        == 422
    )


@pytest.mark.parametrize("count", [31, 50, 100])
def test_large_report_splits_actionable_briefs(client, count):
    for index in range(count):
        capture(client, f"资料 {index}")
    report = client.post("/api/v1/reports/runs", json={"date": today()}).json()
    assert sum(len(b["material_ids"]) for b in report["briefs"]) == count
    for brief in report["briefs"]:
        assert len(brief["material_ids"]) <= 30
        assert (
            client.post(
                "/api/v1/blogs",
                json={
                    "title": brief["title"],
                    "material_ids": brief["material_ids"],
                    "report_id": report["id"],
                    "report_revision": 1,
                },
            ).status_code
            == 200
        )


def test_full_workspace_restore_keeps_history_relations_raw_and_idempotency(client, empty_store):
    payload = {"title": "可恢复原件", "content": "第一版原始内容需要完整保留。"}
    first = client.post(
        "/api/v1/captures", json=payload, headers={"Idempotency-Key": "restore-key"}
    ).json()
    client.post("/api/v1/reports/runs", json={"date": today()})
    client.post(
        f"/api/v1/materials/{first['id']}/revisions",
        json={"title": first["title"], "body": "第二版的判断与第一版不一样。", "revision": 1},
    )
    client.post("/api/v1/reports/runs", json={"date": today()})
    binary = client.post(
        "/api/v1/captures/files", files={"file": ("raw.bin", b"\xff\x00\x80")}
    ).json()
    blog = client.post(
        "/api/v1/blogs", json={"title": "恢复博客", "source_refs": [source_ref(first)]}
    ).json()
    accepted = client.post(f"/api/v1/blogs/{blog['id']}/accept", json={"revision": 1}).json()
    proposal = client.post("/api/v1/library/proposals", json={"blog_id": accepted["id"]}).json()
    entry = client.post(f"/api/v1/library/proposals/{proposal['id']}/accept").json()
    client.post(f"/api/v1/library/entries/{entry['id']}/reviews", json={"grade": "clear"})
    client.patch("/api/v1/settings", json={"display_name": "恢复验证", "report_time": "20:15"})
    response = client.get("/api/v1/workspace/backup")
    assert response.status_code == 200
    assert response.headers["x-content-sha256"] == hashlib.sha256(response.content).hexdigest()
    files = archive_files(response.content)
    assert set(files) - {"manifest.json", "metadata.json"} == {
        "blobs/" + key
        for key in [
            first["blob_hash"],
            binary["blob_hash"],
            client.get(f"/api/v1/objects/{first['id']}").json()["blob_hash"],
        ]
    }
    assert not any("runtime" in name or ".env" in name for name in files)
    with TestClient(create_app(empty_store)) as restored:
        result = restored.post(
            "/api/v1/workspace/restore", files={"file": ("workspace.zip", response.content)}
        )
        assert result.status_code == 200 and result.json()["restored"]
        before = client.get("/api/v1/bootstrap").json()
        after = restored.get("/api/v1/bootstrap").json()
        for key in ["materials", "reports", "blogs", "entries", "proposals", "sources"]:
            assert sorted(before[key], key=lambda item: item["id"]) == sorted(
                after[key], key=lambda item: item["id"]
            )
        assert before["settings"] == after["settings"]
        assert (
            restored.get(f"/api/v1/materials/{first['id']}/original?revision=1").text
            == payload["content"]
        )
        assert restored.get(f"/api/v1/materials/{binary['id']}/original").content == b"\xff\x00\x80"
        assert (
            restored.get(f"/api/v1/objects/{first['id']}/revisions").json()
            == client.get(f"/api/v1/objects/{first['id']}/revisions").json()
        )
        assert (
            restored.post(
                "/api/v1/captures", json=payload, headers={"Idempotency-Key": "restore-key"}
            ).json()
            == first
        )
        assert (
            restored.post(
                "/api/v1/workspace/restore", files={"file": ("again.zip", response.content)}
            ).status_code
            == 422
        )


@pytest.mark.parametrize(
    "tamper",
    [
        "bytes",
        "path",
        "missing",
        "duplicate",
        "schema",
        "head",
        "lineage",
        "date",
        "huge_revision",
        "shape",
    ],
)
def test_corrupt_or_unsafe_backup_is_rejected_without_writes(client, empty_store, tamper):
    capture(client)
    files = archive_files(export_workspace(client.app.state.store))
    blob = next(name for name in files if name.startswith("blobs/"))
    if tamper == "bytes":
        files[blob] = b"corrupted"
    if tamper == "path":
        files["../escape"] = b"no"
    if tamper == "missing":
        files.pop(blob)
    if tamper in {"schema", "head", "lineage", "date", "huge_revision", "shape"}:
        manifest = json.loads(files["manifest.json"])
        if tamper == "schema":
            manifest["schema_version"] = 99
        else:
            metadata = json.loads(files["metadata.json"])
            if tamper == "head":
                metadata["objects"][0]["data"]["title"] = "head not equal to history"
            if tamper == "lineage":
                metadata["objects"][0]["data"]["material_ids"] = ["missing"]
                metadata["revisions"][0]["data"]["material_ids"] = ["missing"]
            if tamper == "date":
                metadata["objects"][0]["created_at"] = "not-a-timestamp"
            if tamper == "huge_revision":
                metadata["objects"][0]["revision"] = 10**15
            if tamper == "shape":
                metadata["objects"][0]["data"].pop("content")
                metadata["revisions"][0]["data"].pop("content")
            files["metadata.json"] = json.dumps(metadata).encode()
            manifest["files"]["metadata.json"] = hashlib.sha256(files["metadata.json"]).hexdigest()
        files["manifest.json"] = json.dumps(manifest).encode()
    raw = zip_files(files)
    if tamper == "duplicate":
        output = io.BytesIO(raw)
        with zipfile.ZipFile(output, "a") as archive:
            archive.writestr(blob, files[blob])
        raw = output.getvalue()
    with pytest.raises(BackupError):
        restore_workspace(empty_store, raw)
    with empty_store.transaction() as conn:
        assert not empty_store.list(conn, "material")
    assert not [path for path in empty_store.data_dir.rglob("*") if path.is_file()]


def test_missing_original_blocks_false_successful_backup(client):
    source = capture(client)
    store = client.app.state.store
    # Only an isolated synthetic fixture, never an owner's original.
    (store.data_dir / "blobs" / source["blob_hash"][:2] / source["blob_hash"]).unlink()
    assert client.get("/api/v1/workspace/backup").status_code == 422


def test_busy_port_does_not_overwrite_pid(tmp_path):
    (tmp_path / "server.pid").write_text("previous-owner")
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        port = occupied.getsockname()[1]
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "panming.server",
                "--workspace-root",
                str(ROOT),
                "--port",
                str(port),
            ],
            env={**os.environ, "PANMING_DATA_DIR": str(tmp_path)},
            capture_output=True,
            text=True,
            timeout=10,
        )
    assert result.returncode != 0 and "未登记 PID" in result.stderr
    assert (tmp_path / "server.pid").read_text() == "previous-owner"


def test_lifetime_lock_does_not_overwrite_pid(tmp_path):
    (tmp_path / "server.pid").write_text("previous-owner")
    with (tmp_path / "server.lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = subprocess.run(
            [sys.executable, "-m", "panming.server", "--workspace-root", str(ROOT)],
            env={**os.environ, "PANMING_DATA_DIR": str(tmp_path)},
            capture_output=True,
            text=True,
            timeout=10,
        )
    assert result.returncode != 0 and "不会覆盖有效 PID" in result.stderr
    assert (tmp_path / "server.pid").read_text() == "previous-owner"


def test_legacy_body_links_export_pinned_without_overwriting_authored_body(client):
    source = capture(client)
    created = client.post(
        "/api/v1/blogs", json={"title": "旧链接", "material_ids": [source["id"]]}
    ).json()
    body = f"[旧版引用](#/materials/{source['id']})"
    saved = client.post(
        f"/api/v1/blogs/{created['id']}/revisions",
        json={"title": created["title"], "body": body, "revision": 1},
    ).json()
    exported = client.get(f"/api/v1/export/{created['id']}")
    assert "?revision=1)" in exported.text
    assert saved["body"] == body


def test_material_list_nul_and_file_nul_handled_without_500(client):
    assert (
        client.post(
            "/api/v1/blogs", json={"title": "无效ID", "material_ids": ["bad\x00id"]}
        ).status_code
        == 422
    )
    raw = b"before\x00after"
    source = client.post("/api/v1/captures/files", files={"file": ("nul.bin", raw)}).json()
    assert source["parse_state"] == "stored_only"
    assert client.get(f"/api/v1/export/{source['id']}").content == raw


def test_integrity_detects_unreferenced_blob_without_deleting_it(client):
    source = capture(client)
    store = client.app.state.store
    orphan = store.put_blob(b"only-test-orphan")
    checked = client.get("/api/v1/workspace/integrity").json()
    assert checked["ok"] and checked["orphan_count"] == 1 and checked["referenced_blobs"] == 1
    assert (store.data_dir / "blobs" / orphan[:2] / orphan).exists()
    (store.data_dir / "blobs" / source["blob_hash"][:2] / source["blob_hash"]).unlink()
    assert client.get("/api/v1/workspace/integrity").json()["missing"] == [source["blob_hash"]]
