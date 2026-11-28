#!/usr/bin/env python3
"""Minimal TCP and UDP load generator for Experiment 4 (stdlib only)."""

import argparse
import socket
import time


def run_tcp_server(bind: str, port: int, timeout: float) -> None:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((bind, port))
    srv.listen(4)
    srv.settimeout(timeout)
    total = 0
    try:
        conn, _ = srv.accept()
        conn.settimeout(timeout)
        t0 = time.monotonic()
        while True:
            chunk = conn.recv(65536)
            if not chunk:
                break
            total += len(chunk)
        elapsed = time.monotonic() - t0
        conn.close()
        mb_s = (total / (1024 * 1024)) / max(elapsed, 1e-6)
        print(f"tcp_server rx_bytes={total} elapsed_s={elapsed:.3f} mb_s={mb_s:.2f}")
    finally:
        srv.close()


def run_tcp_client(host: str, port: int, total_mb: float) -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    t0 = time.monotonic()
    s.connect((host, port))
    payload = b"A" * 16384
    remaining = int(total_mb * 1024 * 1024)
    sent = 0
    while sent < remaining:
        n = min(len(payload), remaining - sent)
        s.sendall(payload[:n])
        sent += n
    s.shutdown(socket.SHUT_WR)
    s.close()
    elapsed = time.monotonic() - t0
    mb_s = (sent / (1024 * 1024)) / max(elapsed, 1e-6)
    print(f"tcp_client tx_bytes={sent} elapsed_s={elapsed:.3f} mb_s={mb_s:.2f}")


def run_udp_server(bind: str, port: int, duration: float) -> None:
    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((bind, port))
    srv.settimeout(0.2)
    rx = 0
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        try:
            data, _ = srv.recvfrom(2048)
            if data:
                rx += 1
        except socket.timeout:
            continue
    srv.close()
    print(f"udp_server app_received={rx}")


def run_udp_client(host: str, port: int, count: int, rate_pps: int) -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    payload = b"XDP-PROBE-PAYLOAD"
    interval = 1.0 / rate_pps if rate_pps > 0 else 0.0
    t0 = time.monotonic()
    for i in range(count):
        s.sendto(payload, (host, port))
        if interval > 0:
            target = t0 + (i + 1) * interval
            now = time.monotonic()
            if target > now:
                time.sleep(target - now)
    elapsed = time.monotonic() - t0
    s.close()
    print(f"udp_client tx_pkts={count} elapsed_s={elapsed:.3f} actual_pps={count / max(elapsed, 1e-6):.1f}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("role", choices=["tcp-server", "tcp-client", "udp-server", "udp-client"])
    p.add_argument("--host", default="10.200.0.1")
    p.add_argument("--port", type=int, default=19999)
    p.add_argument("--mb", type=float, default=4.0)
    p.add_argument("--count", type=int, default=1000)
    p.add_argument("--pps", type=int, default=1000)
    p.add_argument("--duration", type=float, default=2.5)
    args = p.parse_args()

    if args.role == "tcp-server":
        run_tcp_server(args.host, args.port, args.duration)
    elif args.role == "tcp-client":
        run_tcp_client(args.host, args.port, args.mb)
    elif args.role == "udp-server":
        run_udp_server(args.host, args.port, args.duration)
    elif args.role == "udp-client":
        run_udp_client(args.host, args.port, args.count, args.pps)


if __name__ == "__main__":
    main()
