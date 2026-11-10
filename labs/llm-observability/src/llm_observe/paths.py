"""All generated state stays below the ignored lab-local directory."""

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / ".local"


def prepare_local() -> None:
    os.umask(0o077)
    for name in ("downloads", "opt", "run", "logs", "data", "artifacts"):
        (LOCAL / name).mkdir(parents=True, exist_ok=True)


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


def local_origin(value: str) -> str:
    url = urlsplit(value)
    if (
        url.scheme != "http"
        or url.hostname not in {"localhost", "127.0.0.1", "::1"}
        or url.username is not None
        or url.password is not None
        or url.path not in {"", "/"}
        or url.query
        or url.fragment
    ):
        raise ValueError("Expected a localhost HTTP origin without credentials or path")
    if url.port is not None and not 1 <= url.port <= 65535:
        raise ValueError("Invalid origin port")
    return value.rstrip("/")
