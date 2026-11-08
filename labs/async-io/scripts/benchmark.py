"""Bounded, repeatable native benchmarks with raw evidence and a Markdown report."""

import argparse
import hashlib
import json
import os
import platform
import random
import re
import resource
import shutil
import signal
import statistics
import subprocess
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from integration_test import server, snapshot


def run_json(command, timeout=20):
    result = subprocess.run(
        list(map(str, command)),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"{Path(str(command[0])).name} failed ({result.returncode}): "
            f"{result.stderr[-1000:]}"
        )
    return json.loads(result.stdout)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def http_syscall_diagnostic(build, backend, cpus, output):
    """Attach only in a separate diagnostic run; never publish its rate as performance."""
    result = {"backend": backend, "available": False}
    if not shutil.which("strace"):
        result["reason"] = "strace unavailable"
        return result
    trace = output / f"strace-http-{backend}.txt"
    traced_calls = (
        "epoll_ctl,epoll_wait,ioctl,fstat,newfstatat,getsockopt,"
        "recvfrom,sendto,accept,accept4"
    )
    with server(build / "server/ringserver", backend, "-m", "basic", cpu=cpus[0]) as (
        process,
        port,
    ):
        tracer = subprocess.Popen(
            [
                "strace",
                "-f",
                "-qq",
                "-e",
                f"trace={traced_calls}",
                "-o",
                str(trace),
                "-p",
                str(process.pid),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                status = Path(f"/proc/{process.pid}/status").read_text()
                if re.search(rf"^TracerPid:\s+{tracer.pid}$", status, re.MULTILINE):
                    break
                if tracer.poll() is not None:
                    result["reason"] = "strace attach failed"
                    return result
                time.sleep(0.01)
            else:
                result["reason"] = "strace attach deadline exceeded"
                return result
            before = snapshot(process)
            measured = run_json(
                [
                    "taskset",
                    "-c",
                    cpus[1],
                    build / "server/ringserver_bench",
                    port,
                    1,
                    200,
                ]
            )
            after = snapshot(process)
            assert measured["success"] == after["success"] - before["success"], measured
            assert after["errors"] == 0 and after["active"] == 0, after
            assert after["fd_count"] == before["fd_count"], after
            result.update(available=True, success=measured["success"], connections=1)
        finally:
            if tracer.poll() is None:
                tracer.send_signal(signal.SIGINT)
            try:
                tracer.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                tracer.kill()
                tracer.communicate(timeout=3)
            tracer.stderr.close()
    calls = defaultdict(int)
    # Bound the trace duration above and parse incrementally rather than loading it all.
    with trace.open() as stream:
        for line in stream:
            match = re.search(r"(?:^|\s)(\w+)\(", line)
            if match:
                calls[match[1]] += 1
            command = re.search(r"epoll_ctl\([^,]+,\s*(EPOLL_CTL_\w+)", line)
            if command:
                calls[command[1]] += 1
    result["calls"] = dict(calls)
    result["calls_per_request"] = {
        name: count / result["success"] for name, count in calls.items()
    }
    return result


def render(rows, environment, output):
    groups = defaultdict(list)
    for row in rows:
        if row["kind"] == "uring":
            key = (
                "uring",
                row["mode"],
                row["depth"],
                row["batch"],
                row["detailed"],
                row.get("workload", "nop"),
            )
        else:
            key = ("http", row["backend"], row["connections"], row["detailed"])
        groups[key].append(row)
    summary = []
    for key, values in groups.items():
        rate = "ops_s" if key[0] == "uring" else "requests_s"
        rates = [v[rate] for v in values]
        entry = {
            "case": key,
            "runs": len(values),
            "median_rate": statistics.median(rates),
            "min_rate": min(rates),
            "max_rate": max(rates),
            "cv_percent": statistics.stdev(rates) / statistics.mean(rates) * 100
            if len(rates) > 1
            else None,
            "total_success": sum(v["success"] for v in values),
            "errors": sum(v["errors"] for v in values),
        }
        for name in (
            "p50_ns",
            "p95_ns",
            "p99_ns",
            "cpu_ns_op",
            "server_cpu_ns_req",
            "client_cpu_ns_req",
            "server_cpu_cores",
            "client_cpu_cores",
            "syscalls_per_success",
            "server_context_switches_kreq",
            "max_rss_kib",
            "completions_per_poll",
            "ops_per_submission",
            "server_threads",
        ):
            available = [v[name] for v in values if name in v]
            if available:
                entry[name] = statistics.median(available)
        summary.append(entry)
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = [
        "# async-io 本机可观测性报告",
        "",
        f"生成时间：{environment['time']}",
        "",
        "## 测量边界",
        "",
        "- 原始记录：`results.jsonl`；运行环境与二进制/源码摘要：`environment.json`。",
        "- Linux 本机 loopback、单事件循环、客户端与服务端固定在不同 CPU；不是跨机结果。",
        "- HTTP 每连接一个在途请求，固定 1024 B body，逐响应核验状态、长度和全部内容。",
        "- 客户端是闭环负载；延迟不代表固定到达率下的排队或生产 SLO。",
        "- p50/p95/p99 是有界直方图的桶上界，量化误差至多 12.5%；表中是各轮分位数的中位数。",
        "- HTTP 延迟来自客户端；服务端内部耗时包含用户态处理/等待，不称为纯内核时间。",
        "- 微基准包含 ring/task 初始化与销毁；NOP 不代表真实网络/磁盘吞吐。",
        "- basic 保留计数；detailed 增加计时/直方图，观测成本由两者对照体现。",
        "- CPU 来源 getrusage；RSS 为进程生命周期峰值，含预热；perf 缺失不影响这些指标。",
        "- 系统调用次数不由提交次数推算；独立 strace 诊断不混入吞吐/延迟结果。",
        "- kqueue-compat（若启用）是 Linux libkqueue/epoll 兼容层，不是 macOS/BSD 原生 kqueue。",
        "- 单事件循环不等于全进程单线程；libkqueue 会创建内部资源监控线程，进程 CPU 包括它。",
        "- epoll-recreate 在返回每个就绪事件前 DEL、下次 ADD；epoll 保留 EPOLLONESHOT 注册、下次 MOD。",
        "- kqueue-compat 使用 EV_ONESHOT 删除对象；dispatch 使用 EV_DISPATCH + EV_ENABLE 保留对象。",
        "- libkqueue 的 dispatch 在 Linux 仍通过 epoll DEL/ADD 停用/启用，不等于内核 EPOLLONESHOT。",
        "- 各路径均逐项更新监听、批量收取完成；未在同轮混入批量变更、立即读写等其他优化。",
        "",
        "## 环境",
        "",
        f"- 内核基础版本：{environment['kernel_base']}；glibc：{environment['glibc']}",
        f"- io_uring：{len(environment['uring']['opcodes'])} 个受支持操作；liburing 2.6。",
        f"- 锁页内存 soft/hard：{environment['memlock_bytes']} B；CPU：{environment['cpus']}。",
        (
            f"- HTTP 每轮预热 {environment['warmup_ms']} ms，测量 {environment['duration_ms']} ms，"
            f"每组 {environment['repeats']} 轮；请求排空时间计入实际时长。"
        ),
        "",
        "## 微基准",
        "",
        "| 负载 | 模式 | 深度/批量 | ops/s 中位数 | min–max | 波动 CV | CPU ns/op | p99 µs |",
        "| --- | --- | --- | ---: | --- | ---: | ---: | ---: |",
    ]
    for entry in summary:
        key = entry["case"]
        if key[0] != "uring" or not key[4]:
            continue
        variation = (
            f"{entry['cv_percent']:.1f}%" if entry["cv_percent"] is not None else "n/a"
        )
        lines.append(
            f"| {key[5]} | {key[1]} | {key[2]}/{key[3]} | {entry['median_rate']:,.0f} | "
            f"{entry['min_rate']:,.0f}–{entry['max_rate']:,.0f} | {variation} | "
            f"{entry['cpu_ns_op']:.0f} | {entry['p99_ns'] / 1000:.2f} |"
        )
    lines += [
        "",
        "## HTTP（detailed）",
        "",
        "| 后端 | 连接 | req/s 中位数 | min–max | p99 µs | 服务 CPU ns/req | 客户端 CPU 核 | RSS KiB | 进程线程 |",
        "| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for entry in summary:
        key = entry["case"]
        if key[0] == "http" and key[3]:
            lines.append(
                f"| {key[1]} | {key[2]} | {entry['median_rate']:,.0f} | "
                f"{entry['min_rate']:,.0f}–{entry['max_rate']:,.0f} | {entry['p99_ns'] / 1000:.1f} | "
                f"{entry['server_cpu_ns_req']:.0f} | {entry['client_cpu_cores']:.2f} | "
                f"{entry['max_rss_kib']:.0f} | {entry.get('server_threads', 'n/a')} |"
            )
    lines += [
        "",
        "## 观测成本（HTTP）",
        "",
        "| 后端 | 连接 | basic req/s | detailed req/s | detailed 相对变化 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    index = {tuple(entry["case"]): entry for entry in summary}
    for entry in summary:
        key = entry["case"]
        if key[0] == "http" and key[3]:
            basic = index[(*key[:3], False)]["median_rate"]
            detail = entry["median_rate"]
            lines.append(
                f"| {key[1]} | {key[2]} | {basic:,.0f} | {detail:,.0f} | "
                f"{(detail / basic - 1) * 100:+.2f}% |"
            )
    lines += [
        "",
        "## 完整性与解释限制",
        "",
        (
            f"- 共 {len(rows)} 个有效测量，{sum(r['success'] for r in rows):,} 次成功操作/请求，"
            f"错误 {sum(r['errors'] for r in rows)}。不同负载的总量只用于审计，不用于性能比较。"
        ),
        "- 每个 HTTP 测量都核对客户端成功数 = 服务端成功完成数，且无残留活动连接。",
        "- 客户端 CPU 接近 1 核时，结果可能受发压能力限制，不能外推服务器最大吞吐。",
        "- 正负变化可能来自共享机器噪声；单变量收益必须结合 min–max 和重复轮次判断。",
        "- 不宣称旧版到新版的性能提升：旧版不能提供有效基线。本报告比较新实现的路径。",
        "- 服务器 io_uring 后端为取消安全而复制缓冲并复用操作对象；不要将差异全归因于内核。",
        "- 未验证 macOS 原生 kqueue、真实磁盘、远程网络、TLS、多事件循环或高级 ring 模式。",
        "",
    ]
    lines += [
        "## 事件与资源成本（HTTP detailed）",
        "",
        "| 后端 | 连接 | 完成数/轮询 | 上下文切换/千请求 | 后端对象新增/请求 | 缓冲复制 B/请求 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for entry in summary:
        key = entry["case"]
        if key[0] == "http" and key[3]:
            matching = [
                r
                for r in rows
                if r["kind"] == "http_client"
                and r["backend"] == key[1]
                and r["connections"] == key[2]
                and r["detailed"]
            ]
            allocs = statistics.median(
                r["server_delta"]["operation_allocations"] / r["success"]
                for r in matching
            )
            copies = statistics.median(
                r["server_delta"]["copied_bytes"] / r["success"] for r in matching
            )
            lines.append(
                f"| {key[1]} | {key[2]} | {entry['completions_per_poll']:.2f} | "
                f"{entry['server_context_switches_kreq']:.2f} | {allocs:.6f} | {copies:.0f} |"
            )
    lines += [
        "",
        "后端对象新增仅统计 io_uring Operation，不等于全程序 malloc 次数。",
        "",
        "## 独立系统调用诊断",
        "",
        (
            "strace 跟踪轮次不用于性能比较。旧版 strace 的 `-c` 会漏掉新系统调用，"
            "这里解析完整 trace 的 `io_uring_enter`（x86_64 上也识别 `syscall_0x1aa`）。"
        ),
        "",
        "| 模式 | 深度/批量 | NOP 成功数 | 实际 enter 次数 | enter/op |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for item in json.loads((output / "syscall-diagnostic.json").read_text()):
        if item["available"]:
            lines.append(
                f"| {item['mode']} | 32/{item['batch']} | {item['success']} | "
                f"{item['io_uring_enter_calls']} | {item['enter_per_op']:.5f} |"
            )
    lines += [
        "",
        (
            "setup/register、用户态函数调用与 io_uring_enter 分开计数；"
            "本表不代表 HTTP 的全量系统调用数。"
        ),
        "",
    ]
    diagnostic_path = output / "http-syscall-diagnostic.json"
    if diagnostic_path.exists():
        lines += [
            "## HTTP 独立系统调用诊断",
            "",
            "每后端独立运行：1 连接、200 ms、basic；跟踪轮次不参与上面的吞吐/延迟统计。",
            "次数按完整有效响应归一化，包含连接建立、排空和关闭开销；用于解释路径，不是纯稳态精确常数。",
            "",
            "| 后端 | 成功请求 | ADD/请求 | MOD/请求 | DEL/请求 | ioctl/请求 | fstat/请求 | getsockopt/请求 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for item in json.loads(diagnostic_path.read_text()):
            if not item["available"]:
                lines.append(
                    f"- {item['backend']}: {item.get('reason', 'unavailable')}"
                )
                continue
            calls = item["calls_per_request"]
            stat_calls = calls.get("fstat", 0) + calls.get("newfstatat", 0)
            lines.append(
                f"| {item['backend']} | {item['success']} | "
                f"{calls.get('EPOLL_CTL_ADD', 0):.3f} | {calls.get('EPOLL_CTL_MOD', 0):.3f} | "
                f"{calls.get('EPOLL_CTL_DEL', 0):.3f} | {calls.get('ioctl', 0):.3f} | "
                f"{stat_calls:.3f} | {calls.get('getsockopt', 0):.3f} |"
            )
        lines.append("")
    (output / "report.md").write_text("\n".join(lines))


def main():
    if not __debug__:
        raise RuntimeError(
            "run without Python -O: integrity assertions must remain enabled"
        )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=Path("build"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--duration-ms", type=int, default=2000)
    parser.add_argument("--warmup-ms", type=int, default=300)
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
    args.backends = list(dict.fromkeys(args.backends))
    if not 1 <= args.repeats <= 20 or not 100 <= args.duration_ms <= 10000:
        parser.error("repeats must be 1..20 and duration-ms 100..10000")
    if not 1 <= args.warmup_ms <= 10000:
        parser.error("warmup-ms must be 1..10000")
    build = args.build.resolve()
    cpus = sorted(os.sched_getaffinity(0))
    if len(cpus) < 2:
        parser.error("two allowed CPUs required for separate server/client placement")
    cpus = cpus[:2]
    args.out.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    source_hash = hashlib.sha256()
    for name in (
        "Makefile",
        "uring/build.sh",
        "uring/CMakeLists.txt",
        "server/CMakeLists.txt",
    ):
        source_hash.update(name.encode())
        source_hash.update((root / name).read_bytes())
    for directory in (
        "common",
        "uring/include",
        "uring/tests",
        "uring/bench",
        "server/src",
        "server/include",
        "server/tests",
        "server/bench",
        "scripts",
    ):
        for path in sorted((root / directory).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                source_hash.update(str(path.relative_to(root)).encode())
                source_hash.update(path.read_bytes())
    environment = {
        "time": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "kernel_base": platform.release().split("-")[0],
        "glibc": platform.libc_ver()[1],
        "cpus": cpus,
        "memlock_bytes": resource.getrlimit(resource.RLIMIT_MEMLOCK),
        "duration_ms": args.duration_ms,
        "warmup_ms": args.warmup_ms,
        "repeats": args.repeats,
        "http_backends": args.backends,
        "load_average_start": os.getloadavg(),
        "base_revision": subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, timeout=3
        ).strip(),
        "topic_dirty": bool(
            subprocess.check_output(
                ["git", "-C", str(root), "status", "--porcelain", "--", "."],
                text=True,
                timeout=3,
            ).strip()
        ),
        "source_sha256": source_hash.hexdigest(),
        "uring": run_json([build / "uring/uring_probe"]),
        "binaries_sha256": {
            name: digest(build / name)
            for name in (
                "uring/uring_bench",
                "server/ringserver",
                "server/ringserver_bench",
            )
        },
    }
    # Capture public compiler version numbers, not local toolchain paths or vendor suffixes.
    cache = (build / "uring/CMakeCache.txt").read_text()
    compiler = re.search(
        r"^CMAKE_CXX_COMPILER:(?:FILEPATH|STRING)=(.+)$", cache, re.MULTILINE
    )
    if compiler:
        version = subprocess.check_output(
            [compiler[1], "--version"], text=True, timeout=3
        )
        environment["compiler_version"] = re.search(r"\d+\.\d+\.\d+", version)[0]
    if any(backend.startswith("kqueue-compat") for backend in args.backends):
        server_cache = (build / "server/CMakeCache.txt").read_text()
        library = re.search(
            r"^KQUEUE_LIBRARY:FILEPATH=(.+)$", server_cache, re.MULTILINE
        )
        if not library:
            raise RuntimeError("kqueue-compat requires a configured libkqueue library")
        environment["libkqueue_library_sha256"] = digest(Path(library[1]))
    (args.out / "environment.json").write_text(json.dumps(environment, indent=2) + "\n")
    rows = []
    with (args.out / "results.jsonl").open("x") as stream:

        def record(row):
            rows.append(row)
            stream.write(json.dumps(row) + "\n")
            stream.flush()

        for repeat in range(args.repeats):
            micro = [
                (mode, depth, batch, detailed, "nop")
                for depth, batch in (
                    (1, 1),
                    (8, 1),
                    (8, 8),
                    (32, 1),
                    (32, 32),
                    (128, 32),
                )
                for mode in ("raw", "coroutine")
                for detailed in (False, True)
            ]
            micro += [
                (mode, depth, depth, detailed, "socketpair")
                for depth in (1, 32)
                for mode in ("raw", "coroutine")
                for detailed in (False, True)
            ]
            random.Random(1700 + repeat).shuffle(micro)
            for mode, depth, batch, detailed, workload in micro:
                command = [
                    "taskset",
                    "-c",
                    cpus[0],
                    build / "uring/uring_bench",
                    mode,
                    depth,
                    batch,
                    131072,
                    int(detailed),
                    workload,
                ]
                row = run_json(command)
                row.update(repeat=repeat, workload=workload)
                row["ops_per_submission"] = row["success"] / row["submissions"]
                record(row)
            http = [
                (backend, count, detailed)
                for backend in args.backends
                for count in (1, 16, 64, 256)
                for detailed in (False, True)
            ]
            random.Random(2700 + repeat).shuffle(http)
            for backend, count, detailed in http:
                with server(
                    build / "server/ringserver",
                    backend,
                    "-m",
                    "detailed" if detailed else "basic",
                    cpu=cpus[0],
                ) as (process, port):
                    client = [
                        "taskset",
                        "-c",
                        cpus[1],
                        build / "server/ringserver_bench",
                        port,
                        count,
                    ]
                    run_json([*client, args.warmup_ms])
                    time.sleep(0.02)
                    before = snapshot(process)
                    row = run_json([*client, args.duration_ms])
                    time.sleep(0.02)
                    after = snapshot(process)
                    delta = {
                        name: after[name] - before[name]
                        for name in (
                            "success",
                            "errors",
                            "cpu_ns",
                            "context_switches",
                            "polls",
                            "empty_polls",
                            "submit_calls",
                            "submitted",
                            "completed",
                            "time_ns",
                            "operation_allocations",
                            "copied_bytes",
                        )
                    }
                    assert (
                        delta["success"] == row["success"] and delta["errors"] == 0
                    ), (row, delta)
                    assert (
                        after["active"] == 0 and after["fd_count"] == before["fd_count"]
                    ), after
                    row.update(
                        backend=backend,
                        detailed=detailed,
                        repeat=repeat,
                        server_delta=delta,
                        fd_count_before=before["fd_count"],
                        server_after=after,
                        server_cpu_ns_req=delta["cpu_ns"] / row["success"],
                        server_cpu_cores=delta["cpu_ns"] / delta["time_ns"],
                        client_cpu_cores=row["client_cpu_ns_req"]
                        * row["requests_s"]
                        / 1e9,
                        server_context_switches_kreq=delta["context_switches"]
                        * 1000
                        / row["success"],
                        max_rss_kib=after["max_rss_kib"],
                        server_threads=after["thread_count"],
                        completions_per_poll=delta["completed"]
                        / max(1, delta["polls"]),
                    )
                    record(row)
                print(
                    f"round {repeat + 1}/{args.repeats}: {backend} c={count} "
                    f"detailed={detailed} {row['requests_s']:,.0f} req/s",
                    flush=True,
                )
    diagnostics = []
    if shutil.which("strace"):
        for mode in ("raw", "coroutine"):
            for batch in (1, 32):
                trace = args.out / f"strace-{mode}-{batch}.txt"
                result = subprocess.run(
                    [
                        "strace",
                        "-o",
                        str(trace),
                        str(build / "uring/uring_bench"),
                        mode,
                        "32",
                        str(batch),
                        "2048",
                        "0",
                        "nop",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=20,
                    check=False,
                )
                if result.returncode:
                    diagnostics.append(
                        {"mode": mode, "batch": batch, "available": False}
                    )
                    continue
                text = trace.read_text()
                # strace 4.24 prints unknown calls but omits them from -c summaries.
                enter = len(re.findall(r"^io_uring_enter\(", text, re.MULTILINE))
                if platform.machine() == "x86_64":
                    enter += len(re.findall(r"^syscall_0x1aa\(", text, re.MULTILINE))
                diagnostics.append(
                    {
                        "mode": mode,
                        "batch": batch,
                        "available": True,
                        "success": 2048,
                        "io_uring_enter_calls": enter,
                        "enter_per_op": enter / 2048,
                    }
                )
    (args.out / "syscall-diagnostic.json").write_text(
        json.dumps(diagnostics, indent=2) + "\n"
    )
    http_diagnostics = [
        http_syscall_diagnostic(build, backend, cpus, args.out)
        for backend in args.backends
        if backend != "uring"
    ]
    (args.out / "http-syscall-diagnostic.json").write_text(
        json.dumps(http_diagnostics, indent=2) + "\n"
    )
    render(rows, environment, args.out)
    print(f"Report: {args.out / 'report.md'}", flush=True)


if __name__ == "__main__":
    main()
