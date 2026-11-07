"""Prepare a pinned Ubuntu amd64 Bubblewrap helper locally, without system installation."""

from __future__ import annotations

import hashlib
import platform
import subprocess
import sys
from pathlib import Path
from urllib import request

SHA256 = "2461f1beee9cb04c8942739fe1a2b37e7b7c2a3d518f0779dc75f9245baa3094"
URL = (
    "https://archive.ubuntu.com/ubuntu/pool/main/b/bubblewrap/bubblewrap_0.9.0-1ubuntu0.3_amd64.deb"
)


def main() -> None:
    if sys.platform != "linux" or platform.machine() != "x86_64":
        raise SystemExit(
            "This helper is for Ubuntu amd64; use a distro-supported Bubblewrap otherwise"
        )
    project = Path(__file__).resolve().parents[1]
    cache, tools = project / ".cache", project / ".tools"
    for path in (cache, tools):
        if not path.resolve().is_relative_to(project):
            raise SystemExit("Dependency directory resolves outside the project")
        path.mkdir(exist_ok=True)
    archive = cache / "bubblewrap_0.9.0-1ubuntu0.3_amd64.deb"
    if archive.exists():
        payload = archive.read_bytes()
    else:
        with request.urlopen(URL, timeout=60) as response:
            payload = response.read(1_000_001)
    if hashlib.sha256(payload).hexdigest() != SHA256:
        raise SystemExit("Package SHA256 mismatch; refusing extraction")
    if not archive.exists():
        with archive.open("xb") as handle:
            handle.write(payload)
    destination = tools / "bwrap"
    if not destination.resolve().is_relative_to(project):
        raise SystemExit("Extraction target resolves outside the project")
    subprocess.run(["dpkg-deb", "-x", str(archive), str(destination)], check=True, timeout=30)
    from llm_benchmark.isolated_python import IsolatedPython

    sandbox = IsolatedPython(destination / "usr/bin/bwrap")
    sandbox.preflight()
    print("Verified package and isolation policy; helper prepared without system installation.")


if __name__ == "__main__":
    main()
