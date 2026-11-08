"""Real loopback checks; every child is owned, bounded, and reaped."""

import argparse
import contextlib
import json
import select
import signal
import socket
import subprocess
import threading
import time
from pathlib import Path


def read_json(process, timeout=8):
    ready, _, _ = select.select([process.stdout], [], [], timeout)
    if not ready:
        raise RuntimeError("server output deadline exceeded")
    line = process.stdout.readline()
    if not line:
        process.wait(timeout=2)
        raise RuntimeError(
            f"server exited: {process.returncode}: {process.stderr.read()}"
        )
    return json.loads(line)


def snapshot(process):
    process.send_signal(signal.SIGUSR1)
    result = read_json(process)
    assert result["kind"] == "server_snapshot", result
    descriptors = Path(f"/proc/{process.pid}/fd")
    result["fd_count"] = (
        len(list(descriptors.iterdir())) if descriptors.is_dir() else None
    )
    tasks = Path(f"/proc/{process.pid}/task")
    result["thread_count"] = len(list(tasks.iterdir())) if tasks.is_dir() else None
    return result


@contextlib.contextmanager
def server(binary, backend, *options, cpu=None):
    command = [str(binary), "-b", backend, "-p", "0", *map(str, options)]
    if cpu is not None:
        command = ["taskset", "-c", str(cpu), *command]
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1
    )
    try:
        ready = read_json(process)
        assert ready["kind"] == "ready" and ready["backend"] == backend, ready
        yield process, ready["port"]
        process.terminate()
        final = read_json(process)
        assert final["kind"] == "server_snapshot" and final["active"] == 0, final
        process.wait(timeout=8)
        assert process.returncode == 0, process.stderr.read()
        assert final["submitted"] == final["completed"] + (
            final["cancelled"] if backend != "uring" else 0
        ), final
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        process.stdout.close()
        process.stderr.close()


def connect(port):
    connection = socket.create_connection(("127.0.0.1", port), timeout=3)
    connection.settimeout(3)
    return connection


def response(connection, pending=b""):
    while b"\r\n\r\n" not in pending:
        chunk = connection.recv(4096)
        assert chunk, "EOF before response header"
        pending += chunk
    header, body = pending.split(b"\r\n\r\n", 1)
    length = int(
        next(
            line.split(b":", 1)[1]
            for line in header.split(b"\r\n")
            if line.lower().startswith(b"content-length:")
        )
    )
    while len(body) < length:
        chunk = connection.recv(4096)
        assert chunk, "EOF before full body"
        body += chunk
    return header, body[:length], body[length:]


def check(binary, backend):
    with server(binary, backend, "-w", 7) as (process, port):
        with connect(port) as connection:
            connection.sendall(b"GET / HTTP/1.1\r\nHost: local")
            connection.settimeout(0.03)
            try:
                premature = connection.recv(1)
            except TimeoutError:
                premature = b""
            assert not premature, "responded before complete header"
            connection.settimeout(3)
            connection.sendall(
                b"\r\n\r\n"
                + b"GET / HTTP/1.1\r\n\r\n" * 2
                + b"GET / HTTP/1.1\r\nConnection: close\r\n\r\n"
            )
            pending = b""
            for _ in range(4):
                header, body, pending = response(connection, pending)
                assert header.startswith(b"HTTP/1.1 200") and body == b"x" * 1024
            assert not pending and connection.recv(1) == b"", "close not honored"
        for request in [
            b"POST / HTTP/1.1\r\n\r\n",
            b"GET / HTTP/1.1\r\nContent-Length: 2\r\n\r\n",
            b"GET / HTTP/1.1\r\nTransfer-Encoding: chunked\r\n\r\n",
            b"x" * 16384,
        ]:
            with connect(port) as connection:
                connection.sendall(request)
                header, _, _ = response(connection)
                assert header.startswith(b"HTTP/1.1 400"), header
                assert connection.recv(1) == b"", "bad request was kept alive"
        for _ in range(100):
            connection = connect(port)
            connection.sendall(b"GET /")
            connection.close()
        time.sleep(0.1)
        result = snapshot(process)
        assert result["success"] == 4 and result["short_writes"] > 0, result
        assert result["errors"] == 4, result
    with server(binary, backend, "-c", 2) as (process, port):
        first, second = connect(port), connect(port)
        try:
            first.sendall(b"GET / HTTP/1.1\r\n\r\n")
            response(first)
            second.sendall(b"GET / HTTP/1.1\r\n\r\n")
            response(second)
            with connect(port) as extra:
                assert extra.recv(1) == b"", "connection cap not enforced"
            result = snapshot(process)
            assert result["peak_connections"] == 2 and result["rejected"] >= 1, result
        finally:
            first.close()
            second.close()
    # Idle I/O must be cancelled at shutdown without leaking or hanging.
    idle = []
    try:
        with server(binary, backend) as (process, port):
            idle = [connect(port) for _ in range(32)]
            time.sleep(0.05)
            assert snapshot(process)["active"] == 32
    finally:
        for connection in idle:
            connection.close()
    with server(binary, backend) as (process, port):
        with connect(port) as slow:
            slow.sendall(b"GET /")
            slow.settimeout(7)
            assert slow.recv(1) == b"", "slow client timeout not enforced"
        assert snapshot(process)["rejected"] == 1


def main():
    if not __debug__:
        raise RuntimeError(
            "run without Python -O: integrity assertions must remain enabled"
        )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=Path("build/server"))
    parser.add_argument(
        "--backends",
        nargs="+",
        choices=(
            "epoll",
            "epoll-recreate",
            "uring",
            "kqueue-compat",
            "kqueue-compat-dispatch",
        ),
        default=["epoll", "uring"],
    )
    args = parser.parse_args()
    binary = args.build.resolve() / "ringserver"
    for backend in dict.fromkeys(args.backends):
        check(binary, backend)
        print(
            f"PASS {backend}: fragmented/pipelined requests, short writes, malformed input, "
            "FD churn, connection cap, cancellation and clean shutdown"
        )
    for flags in [("-t", "2"), ("-p", "-1"), ("-b", "unknown"), ("-B", "0")]:
        result = subprocess.run(
            [str(binary), *flags], capture_output=True, timeout=3, check=False
        )
        assert result.returncode != 0, flags
    print("PASS invalid CLI options rejected")
    # A load generator that accepts corrupt/empty output would make every rate meaningless.
    for payload in (
        b"",
        b"HTTP/1.1 200 OK\r\nContent-Length: 1024\r\n"
        b"Connection: keep-alive\r\n\r\n" + b"y" * 1024,
    ):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            listener.settimeout(3)
            port = listener.getsockname()[1]

            def corrupt_peer(payload=payload, listener=listener):
                connection, _ = listener.accept()
                with connection:
                    connection.settimeout(3)
                    connection.recv(4096)
                    if payload:
                        connection.sendall(payload)

            worker = threading.Thread(target=corrupt_peer)
            worker.start()
            try:
                result = subprocess.run(
                    [
                        str(args.build.resolve() / "ringserver_bench"),
                        str(port),
                        "1",
                        "100",
                    ],
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
                expected = b"mismatch" if payload else b"unexpected EOF"
                assert result.returncode != 0 and expected in result.stderr, (
                    result.stderr
                )
            finally:
                worker.join(timeout=4)
                assert not worker.is_alive(), "mock peer leaked"
    print("PASS native load generator rejects corrupt and empty responses")


if __name__ == "__main__":
    main()
