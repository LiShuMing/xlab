"""Check exclusions and the actual index without changing Git hooks or staging."""

import subprocess
from pathlib import Path

from llm_observe.paths import ROOT

SOURCE_DIRS = {"config", "scripts", "src", "tests"}
SOURCE_FILES = {
    ".gitignore",
    "AGENTS.md",
    "README.md",
    "DESIGN.md",
    "pyproject.toml",
    "requirements.lock",
    "releases.json",
    "Makefile",
}


def source_allowed(relative: Path) -> bool:
    if any(part in {".local", "thirdparty", "vendor", "__pycache__"} for part in relative.parts):
        return False
    if relative.name.endswith((".log", ".jsonl", ".tar.gz", ".zip", ".sqlite", ".db", ".pyc")):
        return False
    if relative.name.startswith(".env"):
        return False
    return (len(relative.parts) == 1 and relative.name in SOURCE_FILES) or (
        len(relative.parts) > 1
        and relative.parts[0] in SOURCE_DIRS
        and relative.suffix in {".py", ".sh", ".in", ".md", ".txt"}
    )


def check_git() -> None:
    repo = Path(
        subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "--show-toplevel"], text=True
        ).strip()
    )
    prefix = ROOT.relative_to(repo)
    tracked = (
        subprocess.check_output(["git", "-C", str(repo), "ls-files", "-z", "--", str(prefix)])
        .decode()
        .split("\0")
    )
    forbidden = [
        name for name in tracked if name and not source_allowed(Path(name).relative_to(prefix))
    ]
    if forbidden:
        raise RuntimeError("Generated/non-source files in Git index: " + ", ".join(forbidden))
    candidates = [
        ".local/downloads/source.tar.gz",
        ".local/opt/upstream/source.py",
        ".local/logs/server.log",
        ".local/data/prometheus/wal/000001",
        ".local/artifacts/private/trace.json",
        ".local/venv/pyvenv.cfg",
    ]
    for name in candidates:
        result = subprocess.run(
            ["git", "-C", str(repo), "check-ignore", "-q", "--", str(prefix / name)]
        )
        if result.returncode:
            raise RuntimeError(f"Runtime exclusion missing: {name}")
    print("Git index contains no forbidden lab artifacts; runtime paths are ignored")
