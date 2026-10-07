"""CLI contracts tested through the real isolated FastAPI app, without an external service."""

import json

import httpx
import pytest
from click.testing import CliRunner
from test_workflow import client as client

from panming.app import today
from panming.cli import main


@pytest.fixture()
def cli(client, monkeypatch):
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, **kw: client.post(url, **{k: v for k, v in kw.items() if k != "timeout"}),
    )
    monkeypatch.setattr(httpx, "get", lambda url, **kw: client.get(url))
    monkeypatch.setattr(
        httpx,
        "patch",
        lambda url, **kw: client.patch(url, **{k: v for k, v in kw.items() if k != "timeout"}),
    )
    return CliRunner()


def test_cli_note_and_markdown_export(cli, tmp_path):
    result = cli.invoke(
        main, ["capture", "note", "--title", "CLI 输入", "--text", "原始内容完全一致。"]
    )
    assert result.exit_code == 0
    item = json.loads(result.output)
    target = tmp_path / "nested" / "note.md"
    exported = cli.invoke(main, ["export", item["id"], "--output", str(target)])
    assert exported.exit_code == 0 and target.read_text() == "原始内容完全一致。"


def test_cli_file_and_link_are_real_captures(cli, tmp_path, client):
    # A generated fixture is not a source edit.
    path = tmp_path / "input.md"
    path.write_text("# 测试输入\n\n命令行文件上传与 Web 使用同一个业务接口。")
    uploaded = cli.invoke(main, ["capture", "file", str(path)])
    assert uploaded.exit_code == 0
    item = json.loads(uploaded.output)
    assert client.get(f"/api/v1/materials/{item['id']}/original").content == path.read_bytes()
    linked = cli.invoke(main, ["capture", "url", "https://example.org/cli", "--title", "CLI 链接"])
    assert linked.exit_code == 0 and json.loads(linked.output)["parse_state"] == "needs_input"


def test_cli_report_and_invalid_date(cli):
    good = cli.invoke(main, ["report", "--date", today()])
    bad = cli.invoke(main, ["report", "--date", "not-a-date"])
    assert good.exit_code == 0 and json.loads(good.output)["coverage_state"] == "no_updates"
    assert bad.exit_code != 0 and "422" in bad.output


def test_cli_missing_original_and_missing_object_are_not_silent(cli, tmp_path):
    assert cli.invoke(main, ["capture", "file", str(tmp_path / "missing")]).exit_code != 0
    destination = tmp_path / "missing.md"
    exported = cli.invoke(main, ["export", "missing", "--output", str(destination)])
    assert exported.exit_code != 0 and not destination.exists()


def test_cli_network_error_is_readable(monkeypatch):
    def unavailable(*args, **kwargs):
        raise httpx.ConnectError("本机服务未启动")

    monkeypatch.setattr(httpx, "post", unavailable)
    result = CliRunner().invoke(main, ["capture", "note", "--title", "输入", "--text", "正文"])
    assert result.exit_code == 1 and "本机服务未启动" in result.output


def test_cli_help_matches_available_commands():
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0
    assert all(command in result.output for command in ["capture", "report", "export", "demo"])


def test_cli_raw_export_preserves_binary_and_will_not_clobber(cli, client, tmp_path):
    raw = b"\xff\x00\x80"
    source = client.post("/api/v1/captures/files", files={"file": ("raw.bin", raw)}).json()
    target = tmp_path / "raw.bin"
    first = cli.invoke(
        main,
        ["export", source["id"], "--format", "raw", "--revision", "1", "--output", str(target)],
    )
    assert first.exit_code == 0 and target.read_bytes() == raw
    second = cli.invoke(main, ["export", source["id"], "--output", str(target)])
    assert second.exit_code != 0 and target.read_bytes() == raw


def test_cli_workspace_backup_creates_zip(cli, client, tmp_path):
    import zipfile

    target = tmp_path / "workspace.zip"
    result = cli.invoke(main, ["workspace", "backup", "--output", str(target)])
    assert result.exit_code == 0
    with zipfile.ZipFile(target) as archive:
        assert "metadata.json" in archive.namelist()
    verified = cli.invoke(main, ["workspace", "verify", str(target)])
    assert verified.exit_code == 0 and json.loads(verified.output)["valid"]


def test_cli_digest_status_cancel_retry_and_historical_version(cli, client):
    from test_workflow import capture

    source = capture(client)
    client.post(
        f"/api/v1/materials/{source['id']}/revisions",
        json={
            "title": source["title"],
            "body": "第二版不能偷偷进入第一版消化的证据。",
            "revision": 1,
        },
    )
    result = cli.invoke(main, ["digest", source["id"], "--revision", "1"])
    assert result.exit_code == 0
    job = json.loads(result.output)
    assert job["source_refs"][0]["material_revision"] == 1
    listed = cli.invoke(main, ["jobs", "list"])
    assert listed.exit_code == 0 and json.loads(listed.output)["jobs"][0]["id"] == job["id"]
    assert (
        json.loads(cli.invoke(main, ["jobs", "cancel", job["id"]]).output)["state"] == "cancelled"
    )
    assert json.loads(cli.invoke(main, ["jobs", "retry", job["id"]]).output)["state"] == "queued"


def test_cli_digest_rejects_non_material_and_ambiguous_revision(cli, client):
    report = client.post("/api/v1/reports/runs", json={"date": today()}).json()
    assert cli.invoke(main, ["digest", report["id"]]).exit_code != 0
    assert cli.invoke(main, ["digest", "a", "b", "--revision", "1"]).exit_code != 0


def test_cli_real_provider_requires_explicit_flags_and_does_not_print_credentials(cli, client):
    from test_llm import SECRET, install
    from test_workflow import capture

    install(client)
    source = capture(client)
    status = cli.invoke(main, ["llm", "status"])
    assert status.exit_code == 0 and SECRET not in status.output
    args = ["material", "policy", source["id"], "--revision", "1", "--policy", "cloud_allowed"]
    assert cli.invoke(main, args).exit_code != 0
    grant = cli.invoke(main, [*args, "--confirm-cloud"])
    assert grant.exit_code == 0 and SECRET not in grant.output
    args = ["digest", source["id"], "--provider", "openai_compatible"]
    assert cli.invoke(main, args).exit_code != 0
    submitted = cli.invoke(main, [*args, "--allow-cloud"])
    assert submitted.exit_code == 0
    jid = json.loads(submitted.output)["id"]
    cli.invoke(main, ["jobs", "cancel", jid])
    assert cli.invoke(main, ["jobs", "retry", jid]).exit_code != 0
    assert cli.invoke(main, ["jobs", "retry", jid, "--allow-cloud"]).exit_code == 0
