import hashlib
import io
import tarfile

import pytest

from llm_observe import downloads


def archive_with_program(path):
    with tarfile.open(path, "w:gz") as archive:
        for name, data in [("bundle/tool", b"program"), ("../../unwanted.py", b"source")]:
            item = tarfile.TarInfo(name)
            item.size = len(data)
            archive.addfile(item, io.BytesIO(data))


def release(archive):
    return {
        "asset": "tool-{version}-{platform}.tar.gz",
        "version": "1",
        "repository": "test/test",
        "executables": ["tool"],
        "sha256": {"darwin-arm64": downloads.digest(archive)},
    }


def test_extracts_only_verified_executable_not_upstream_source(monkeypatch, tmp_path):
    monkeypatch.setattr(downloads, "LOCAL", tmp_path)
    (tmp_path / "downloads").mkdir()
    (tmp_path / "opt").mkdir()
    archive = tmp_path / "downloads/tool-1-darwin-arm64.tar.gz"
    archive_with_program(archive)
    record = downloads.install_release("tool", release(archive), "darwin-arm64")
    installed = tmp_path / "opt/tool-1-darwin-arm64"
    assert {p.name for p in installed.iterdir()} == {"tool"}
    assert record["executables"]["tool"]["sha256"] == hashlib.sha256(b"program").hexdigest()
    assert not (tmp_path / "unwanted.py").exists()
    before = (installed / "tool").stat().st_ino
    second = downloads.install_release("tool", release(archive), "darwin-arm64", record)
    assert second == record
    assert (installed / "tool").stat().st_ino == before


def test_corrupt_download_is_not_installed(monkeypatch, tmp_path):
    monkeypatch.setattr(downloads, "LOCAL", tmp_path)
    (tmp_path / "downloads").mkdir()
    (tmp_path / "opt").mkdir()
    archive = tmp_path / "expected.tar.gz"
    archive_with_program(archive)
    monkeypatch.setattr(downloads, "urlopen", lambda *_args, **_kwargs: io.BytesIO(b"corrupt"))
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        downloads.install_release("tool", release(archive), "darwin-arm64")
    assert not list((tmp_path / "opt").iterdir())
    assert not list((tmp_path / "downloads").iterdir())
