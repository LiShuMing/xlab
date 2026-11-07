#!/usr/bin/env python3
"""Fetch a verified official Python OCI rootfs without a Docker daemon."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import ssl
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REGISTRY = "https://public.ecr.aws"
REPOSITORY = "docker/library/python"
TAG = "3.11-slim-bookworm"
ACCEPT = ", ".join(
    [
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    ]
)


class Registry:
    def __init__(self, ca: Path):
        self.context = ssl.create_default_context(cafile=str(ca))
        self.token = None

    def open(self, url: str):
        headers = {"Accept": ACCEPT, "User-Agent": "xlab-daft-lab/1"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            return urllib.request.urlopen(
                urllib.request.Request(url, headers=headers), context=self.context, timeout=60
            )
        except urllib.error.HTTPError as error:
            if error.code != 401 or self.token:
                raise
            fields = dict(re.findall(r'(\w+)="([^"]+)"', error.headers["www-authenticate"]))
            realm = fields.pop("realm")
            token_url = realm + "?" + urllib.parse.urlencode(fields)
            with urllib.request.urlopen(token_url, context=self.context, timeout=60) as response:
                token_data = json.load(response)
            self.token = token_data.get("token") or token_data["access_token"]
            return self.open(url)

    def manifest(self, ref: str) -> tuple[dict, str]:
        with self.open(f"{REGISTRY}/v2/{REPOSITORY}/manifests/{ref}") as response:
            content = response.read()
        digest = "sha256:" + hashlib.sha256(content).hexdigest()
        if ref.startswith("sha256:") and digest != ref:
            raise ValueError("OCI manifest digest mismatch")
        return json.loads(content), digest

    def blob(self, digest: str, destination: Path) -> None:
        if destination.exists() and sha256(destination) == digest:
            return
        partial = destination.with_suffix(".partial")
        for attempt in range(3):
            try:
                with self.open(f"{REGISTRY}/v2/{REPOSITORY}/blobs/{digest}") as response:
                    with partial.open("wb") as output:
                        shutil.copyfileobj(response, output, 1024 * 1024)
                if sha256(partial) != digest:
                    raise ValueError("OCI layer digest mismatch")
                partial.replace(destination)
                return
            except (OSError, urllib.error.URLError):
                if attempt == 2:
                    raise
                time.sleep(2)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def extract_layer(blob: Path, root: Path) -> None:
    """Keep every extracted path and link inside this private rootfs."""
    with tarfile.open(blob) as archive:
        for member in archive:
            relative = Path(member.name)
            if relative == Path(".") and member.isdir():
                continue
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"Unsafe layer member: {member.name}")
            target = root / relative
            if not target.parent.resolve().is_relative_to(root):
                raise ValueError(f"Layer parent escapes rootfs: {member.name}")
            if target.name == ".wh..wh..opq":
                for child in target.parent.iterdir():
                    if child.is_dir() and not child.is_symlink():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
                continue
            if target.name.startswith(".wh."):
                removed_name = target.name[4:]
                if removed_name in {"", ".", ".."}:
                    raise ValueError(f"Unsafe whiteout: {member.name}")
                removed = target.with_name(removed_name)
                if removed.is_dir() and not removed.is_symlink():
                    shutil.rmtree(removed)
                else:
                    removed.unlink(missing_ok=True)
                continue
            if member.issym():
                link_target = (
                    root / member.linkname.lstrip("/")
                    if member.linkname.startswith("/")
                    else target.parent / member.linkname
                )
                if not link_target.resolve().is_relative_to(root):
                    raise ValueError(f"Layer symlink escapes rootfs: {member.name}")
                # Relative links have identical semantics after chroot and remain safe to inspect outside it.
                member.linkname = os.path.relpath(link_target, target.parent)
            elif member.islnk():
                if not (root / member.linkname).resolve().is_relative_to(root):
                    raise ValueError(f"Layer hardlink escapes rootfs: {member.name}")
            elif not (member.isfile() or member.isdir()):
                raise ValueError(f"Unsupported layer member: {member.name}")
            if target.is_symlink() and not member.issym():
                target.unlink()
            archive.extract(member, root, set_attrs=True)


def verify_ready(root: Path, lock_file: Path) -> None:
    """Refuse stale runtime provenance without deleting an existing environment."""
    marker = root / ".daft-lab-ready"
    if not marker.is_file() or not lock_file.is_file():
        raise SystemExit("Rootfs or image lock missing; run bootstrap.py first")
    expected = json.loads(lock_file.read_text())["manifest_digest"]
    if marker.read_text().strip() != expected:
        raise SystemExit("Rootfs image differs from image.lock.json; preserve and inspect it before rebuilding")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ca", type=Path, default=Path("/etc/pki/tls/certs/ca-bundle.crt"))
    args = parser.parse_args()
    project = Path(__file__).resolve().parent
    local = project / ".local"
    root = local / "rootfs"
    lock_file = project / "image.lock.json"
    marker = root / ".daft-lab-ready"
    if marker.exists():
        verify_ready(root, lock_file)
        print(f"Rootfs ready: {root}", flush=True)
        return
    if root.exists():
        raise SystemExit(f"Incomplete rootfs retained at {root}; inspect it before retrying.")
    registry = Registry(args.ca)
    if lock_file.exists():
        lock = json.loads(lock_file.read_text())
        manifest, digest = registry.manifest(lock["manifest_digest"])
    else:
        manifest, digest = registry.manifest(TAG)
        if "manifests" in manifest:
            selected = next(
                item
                for item in manifest["manifests"]
                if item.get("platform", {}).get("os") == "linux"
                and item.get("platform", {}).get("architecture") == "amd64"
            )
            manifest, digest = registry.manifest(selected["digest"])
        lock = {
            "registry": REGISTRY,
            "repository": REPOSITORY,
            "tag": TAG,
            "manifest_digest": digest,
            "layers": manifest["layers"],
        }
        lock_file.write_text(json.dumps(lock, indent=2) + "\n")
    blobs = local / "oci-blobs"
    blobs.mkdir(parents=True, exist_ok=True)
    for layer in manifest["layers"]:
        path = blobs / layer["digest"].split(":")[1]
        print(f"Fetch layer {path.name[:12]} ({layer['size'] / 1024**2:.1f} MiB)", flush=True)
        registry.blob(layer["digest"], path)
    root.mkdir()
    for layer in manifest["layers"]:
        extract_layer(blobs / layer["digest"].split(":")[1], root)
    for directory in ["lab", "source", "proc", "dev", "tmp"]:
        (root / directory).mkdir(exist_ok=True)
    shutil.copyfile("/etc/resolv.conf", root / "etc/resolv.conf")
    shutil.copyfile(args.ca, root / "etc/ssl/certs/ca-certificates.crt")
    shutil.copyfile(shutil.which("uv"), root / "usr/local/bin/uv")
    (root / "usr/local/bin/uv").chmod(0o755)
    marker.write_text(digest + "\n")
    print(f"Rootfs ready: {root}", flush=True)


if __name__ == "__main__":
    main()
