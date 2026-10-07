"""Stop only this project's server and its isolated database."""

from __future__ import annotations

import json
import os
import signal
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def main() -> None:
    pid_file = DATA / "server.pid"
    if pid_file.exists():
        pid = int(pid_file.read_text())
        info = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True
        )
        if "uvicorn panming.app:app" in info.stdout or ("panming.server" in info.stdout and f"--workspace-root {ROOT}" in info.stdout):
            os.kill(pid, signal.SIGTERM)
        pid_file.unlink(missing_ok=True)
    config_path = DATA / "runtime.json"
    if config_path.exists() and not os.environ.get("PANMING_DATABASE_URL"):
        config = json.loads(config_path.read_text())
        subprocess.run(
            [
                str(Path(config["pg_bin"]) / "pg_ctl"),
                "-D",
                str(DATA / "postgres"),
                "-m",
                "fast",
                "-w",
                "stop",
            ],
            check=False,
        )


if __name__ == "__main__":
    main()
