"""Initialize an isolated loopback PostgreSQL cluster, never an existing service."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def main() -> None:
    if os.environ.get("PANMING_DATABASE_URL"):
        print("使用显式配置的盘铭数据库。")
        return
    pg_ctl = shutil.which("pg_ctl")
    if not pg_ctl:
        candidate = Path("/opt/homebrew/opt/postgresql@17/bin/pg_ctl")
        if candidate.exists():
            pg_ctl = str(candidate)
    if not pg_ctl:
        raise SystemExit(
            "需要 PostgreSQL（例如 brew install postgresql@17），或设置 PANMING_DATABASE_URL。"
        )
    pg_bin = Path(pg_ctl).parent
    DATA.mkdir(parents=True, exist_ok=True)
    DATA.chmod(0o700)
    cluster = DATA / "postgres"
    socket = DATA / "pg-socket"
    socket.mkdir(exist_ok=True)
    socket.chmod(0o700)
    runtime = DATA / "runtime.json"
    if not runtime.exists():
        password = secrets.token_hex(24)
        runtime.write_text(
            json.dumps(
                {
                    "database_url": f"postgresql+psycopg://panming:{password}@127.0.0.1:55432/panming",
                    "pg_bin": str(pg_bin),
                    "password": password,
                }
            )
        )
        runtime.chmod(0o600)
    config = json.loads(runtime.read_text())
    if not (cluster / "PG_VERSION").exists():
        password_file = DATA / "init-password"
        try:
            password_file.write_text(config["password"])
            password_file.chmod(0o600)
            subprocess.run(
                [
                    str(pg_bin / "initdb"),
                    "-D",
                    str(cluster),
                    "-U",
                    "panming",
                    "--auth-local=trust",
                    "--auth-host=scram-sha-256",
                    "--pwfile",
                    str(password_file),
                    "--encoding=UTF8",
                    "--locale=C",
                ],
                check=True,
                stdout=subprocess.DEVNULL,
            )
        finally:
            password_file.unlink(missing_ok=True)
    status = subprocess.run(
        [str(pg_bin / "pg_ctl"), "-D", str(cluster), "status"], stdout=subprocess.DEVNULL
    )
    if status.returncode:
        subprocess.run(
            [
                str(pg_bin / "pg_ctl"),
                "-D",
                str(cluster),
                "-l",
                str(DATA / "postgres.log"),
                "-o",
                f"-h 127.0.0.1 -p 55432 -k {socket}",
                "-w",
                "start",
            ],
            check=True,
        )
    db_list = subprocess.run(
        [
            str(pg_bin / "psql"),
            "-h",
            str(socket),
            "-p",
            "55432",
            "-U",
            "panming",
            "-d",
            "postgres",
            "-Atc",
            "SELECT datname FROM pg_database WHERE datname='panming'",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    if not db_list.stdout.strip():
        subprocess.run(
            [
                str(pg_bin / "createdb"),
                "-h",
                str(socket),
                "-p",
                "55432",
                "-U",
                "panming",
                "panming",
            ],
            check=True,
        )
    print("盘铭专用 PostgreSQL 已就绪（本机 55432）。")


if __name__ == "__main__":
    main()
