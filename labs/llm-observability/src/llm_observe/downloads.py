"""Fetch fixed upstream release assets, verifying them before extraction."""

import hashlib
import json
import os
import platform
import shutil
import tarfile
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

from llm_observe.paths import LOCAL, ROOT, prepare_local, write_json


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def platform_name() -> str:
    system = platform.system().lower()
    machine = {"aarch64": "arm64", "x86_64": "amd64"}.get(platform.machine(), platform.machine())
    name = f"{system}-{machine}"
    if name not in {"darwin-arm64", "darwin-amd64", "linux-arm64", "linux-amd64"}:
        raise ValueError(f"Unsupported release platform: {name}")
    return name


def install_release(name: str, release: dict, target: str, previous: dict | None = None) -> dict:
    asset = release["asset"].format(version=release["version"], platform=target)
    expected = release["sha256"][target]
    archive = LOCAL / "downloads" / asset
    url = (
        f"https://github.com/{release['repository']}/releases/download/"
        f"v{release['version']}/{asset}"
    )
    if not archive.exists() or digest(archive) != expected:
        partial = archive.with_suffix(archive.suffix + ".part")
        print(f"Downloading {asset}", flush=True)
        try:
            request = Request(url, headers={"User-Agent": "xlab-llm-observability/0.1"})
            with urlopen(request, timeout=60) as response, partial.open("wb") as stream:
                shutil.copyfileobj(response, stream)
            if digest(partial) != expected:
                raise ValueError(f"SHA256 mismatch for {asset}; asset not installed")
            partial.replace(archive)
        finally:
            partial.unlink(missing_ok=True)
    destination = LOCAL / "opt" / f"{name}-{release['version']}-{target}"
    if (
        previous is not None
        and previous["archive_sha256"] == expected
        and previous["version"] == release["version"]
        and previous["platform"] == target
        and all(
            (destination / binary).is_file()
            and previous["executables"][binary]["path"] == str(destination / binary)
            and digest(destination / binary) == previous["executables"][binary]["sha256"]
            for binary in release["executables"]
        )
    ):
        # Preserve live executables and any OS execution approval on an unchanged install.
        return previous
    with tempfile.TemporaryDirectory(dir=LOCAL / "opt") as temporary:
        staging = Path(temporary)
        with tarfile.open(archive) as bundle:
            # Extract only known executables/licenses. Never expand archive paths or links.
            for binary in release["executables"]:
                members = [
                    member
                    for member in bundle.getmembers()
                    if member.isfile() and Path(member.name).name == binary
                ]
                if len(members) != 1:
                    raise ValueError(f"Expected exactly one {binary} in {asset}")
                source = bundle.extractfile(members[0])
                assert source is not None
                with source, (staging / binary).open("wb") as stream:
                    shutil.copyfileobj(source, stream)
                (staging / binary).chmod(0o755)
            for member in bundle.getmembers():
                if member.isfile() and Path(member.name).name in {"LICENSE", "NOTICE"}:
                    source = bundle.extractfile(member)
                    assert source is not None
                    with source, (staging / Path(member.name).name).open("wb") as stream:
                        shutil.copyfileobj(source, stream)
        destination.mkdir(exist_ok=True)
        for path in staging.iterdir():
            os.replace(path, destination / path.name)
    return {
        "version": release["version"],
        "platform": target,
        "url": url,
        "archive_sha256": expected,
        "executables": {
            binary: {"path": str(destination / binary), "sha256": digest(destination / binary)}
            for binary in release["executables"]
        },
    }


def download() -> None:
    prepare_local()
    releases = json.loads((ROOT / "releases.json").read_text())
    target = platform_name()
    receipt = LOCAL / "opt" / "installed.json"
    previous = json.loads(receipt.read_text()) if receipt.exists() else {}
    records = {
        name: install_release(name, release, target, previous.get(name))
        for name, release in releases.items()
    }
    write_json(LOCAL / "opt" / "installed.json", records)
    print(f"Verified releases installed under {LOCAL / 'opt'}")


def binaries() -> dict[str, str]:
    if not (LOCAL / "opt" / "installed.json").exists():
        raise RuntimeError("Run scripts/download.sh first")
    records = json.loads((LOCAL / "opt" / "installed.json").read_text())
    releases = json.loads((ROOT / "releases.json").read_text())
    result = {}
    for name, release in releases.items():
        record = records[name]
        if (
            record["version"] != release["version"]
            or record["platform"] != platform_name()
            or record["archive_sha256"] != release["sha256"][platform_name()]
        ):
            raise ValueError("Release lock changed; rerun scripts/download.sh")
        for binary in release["executables"]:
            item = record["executables"][binary]
            path = Path(item["path"])
            if not path.is_relative_to(LOCAL / "opt") or digest(path) != item["sha256"]:
                raise ValueError(f"Installed executable changed: {binary}; rerun download.sh")
            result[binary] = str(path)
    return result
