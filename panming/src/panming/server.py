"""Loopback server with a lifetime lock and no PID write until the port is owned."""

from __future__ import annotations

import argparse
import fcntl
import os
import socket
from pathlib import Path

import uvicorn

from .storage import DATA, ROOT


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8788)
    args = parser.parse_args()
    if args.workspace_root.resolve() != ROOT:
        raise SystemExit("工作空间路径不匹配")
    DATA.mkdir(parents=True, exist_ok=True)
    with (DATA / "server.lock").open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise SystemExit("盘铭服务已运行；不会覆盖有效 PID") from error
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", args.port))
                sock.listen(128)
            except OSError as error:
                raise SystemExit(f"端口 {args.port} 不可用；未登记 PID") from error
            pid_file = DATA / "server.pid"
            pid = str(os.getpid())
            pid_file.write_text(pid)
            pid_file.chmod(0o600)
            try:
                print(f"打开盘铭：http://127.0.0.1:{args.port}", flush=True)
                uvicorn.Server(
                    uvicorn.Config("panming.app:app", host="127.0.0.1", port=args.port)
                ).run(sockets=[sock])
            except KeyboardInterrupt:
                pass  # Uvicorn has already completed graceful shutdown.
            finally:
                if pid_file.exists() and pid_file.read_text() == pid:
                    pid_file.unlink()


if __name__ == "__main__":
    main()
