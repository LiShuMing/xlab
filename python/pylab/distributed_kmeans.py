#!/usr/bin/env python3
"""Auditable synchronous K-means with persistent, shard-owning processes.

Run this file for serial/parallel, uneven-shard, straggler and failure experiments.
Only NumPy and the Python standard library are required. This is not a cluster.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import os
import pickle
import platform
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from multiprocessing.connection import wait
from pathlib import Path

import numpy as np


class WorkerFailure(RuntimeError):
    """A whole computation failed; owned processes are reaped before propagation."""

    worker_pids: tuple[int, ...] = ()
    worker_exitcodes: tuple[int | None, ...] = ()


@dataclass(frozen=True)
class Fault:
    """One explicit teaching/test fault, never a retry policy."""

    worker_id: int = 0
    round_id: int = 0
    action: str = "delay"
    seconds: float = 0.2


@dataclass
class KMeansResult:
    centers: np.ndarray
    labels: np.ndarray
    counts: np.ndarray
    sse: float
    converged: bool
    history: list[dict]
    shard_sizes: tuple[int, ...]
    worker_pids: tuple[int, ...]
    worker_exitcodes: tuple[int | None, ...]
    startup_seconds: float
    evaluation_seconds: float
    shutdown_seconds: float
    total_seconds: float


def _integer(value, name: str, lower: int, upper: int) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise ValueError(f"{name} must be an integer")
    if not lower <= value <= upper:
        raise ValueError(f"{name} must be in [{lower}, {upper}]")
    return int(value)


def _number(value, name: str, positive: bool = False) -> float:
    if isinstance(value, (bool, np.bool_)) or not np.isscalar(value):
        raise ValueError(f"{name} must be a finite number")
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not np.isfinite(value) or value < 0 or (positive and value == 0):
        raise ValueError(f"{name} must be finite and {'positive' if positive else 'nonnegative'}")
    return value


def _batches(points: np.ndarray, centers: np.ndarray, batch_size: int):
    # Bound the B*K*D temporary to <= 2**20 float64 values (8 MiB).
    width = min(batch_size, max(1, 2**20 // centers.size))
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        for start in range(0, len(points), width):
            block = points[start : start + width]
            delta = block[:, None, :] - centers[None, :, :]
            distances = np.einsum("bkd,bkd->bk", delta, delta)
            if not np.isfinite(distances).all():
                raise ValueError("nonfinite squared distance")
            labels = distances.argmin(axis=1)  # First index wins ties.
            yield start, block, labels, distances[np.arange(len(block)), labels]


def _local_stats(points: np.ndarray, centers: np.ndarray, batch_size: int) -> dict:
    started = time.perf_counter()
    sums = np.zeros_like(centers)
    counts = np.zeros(len(centers), dtype=np.int64)
    sse = 0.0
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        for _, block, labels, distances in _batches(points, centers, batch_size):
            np.add.at(sums, labels, block)
            counts += np.bincount(labels, minlength=len(centers))
            sse += float(distances.sum())
    if not np.isfinite(sums).all() or not np.isfinite(sse):
        raise ValueError("nonfinite local statistics")
    return {
        "sums": sums,
        "counts": counts,
        "sse": sse,
        "compute_seconds": time.perf_counter() - started,
    }


def _reduce_round(messages: list[dict], sizes: tuple[int, ...], centers: np.ndarray, round_id: int):
    """Validate the whole round before using any partial result."""
    if len(messages) != len(sizes):
        raise WorkerFailure("missing or extra shard statistics")
    indexed = {}
    for message in messages:
        shard = message.get("shard_id")
        if type(shard) is not int or not 0 <= shard < len(sizes) or shard in indexed:
            raise WorkerFailure("invalid or duplicate shard statistics")
        if type(message.get("round_id")) is not int or message["round_id"] != round_id:
            raise WorkerFailure("wrong round_id in statistics")
        sums, counts = message.get("sums"), message.get("counts")
        if (
            not isinstance(sums, np.ndarray)
            or sums.dtype != np.float64
            or sums.shape != centers.shape
            or not np.isfinite(sums).all()
            or not isinstance(counts, np.ndarray)
            or counts.dtype != np.int64
            or counts.shape != (len(centers),)
            or np.any(counts < 0)
            or np.any(counts > sizes[shard])
            or int(counts.sum()) != sizes[shard]
            or np.any(sums[counts == 0] != 0)
        ):
            raise WorkerFailure("invalid shard shape, count or numeric statistics")
        try:
            _number(message.get("sse"), "sse")
            _number(message.get("compute_seconds"), "compute_seconds")
            _number(message.get("delay_seconds", 0.0), "delay_seconds")
        except ValueError as exc:
            raise WorkerFailure("nonfinite or negative shard metric") from exc
        indexed[shard] = message
    total_sums = np.zeros_like(centers)
    total_counts = np.zeros(len(centers), dtype=np.int64)
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        for shard in range(len(sizes)):
            total_sums += indexed[shard]["sums"]
            total_counts += indexed[shard]["counts"]
        updated = centers.copy()
        occupied = total_counts > 0
        updated[occupied] = total_sums[occupied] / total_counts[occupied, None]
        shift = float(np.sqrt(np.square(updated - centers).sum(axis=1)).max())
    if (
        int(total_counts.sum()) != sum(sizes)
        or not np.isfinite(updated).all()
        or not np.isfinite(shift)
    ):
        raise WorkerFailure("invalid global statistics")
    return updated, total_counts, shift


def _send(connection, message: dict) -> int:
    payload = pickle.dumps(message, protocol=5)
    connection.send_bytes(payload)
    return len(payload)


def _worker(connection, shard_id: int, points: np.ndarray, batch_size: int, fault: Fault | None):
    try:
        _send(connection, {"kind": "ready", "shard_id": shard_id, "pid": os.getpid()})
        while True:
            message = pickle.loads(connection.recv_bytes(262144))
            if message["kind"] == "stop":
                return
            round_id = message["round_id"]
            delay = 0.0
            inject = (
                fault is not None and fault.worker_id == shard_id and fault.round_id == round_id
            )
            if inject and fault.action == "exit":
                os._exit(7)  # Only this explicitly owned worker exits.
            if inject and fault.action == "delay":
                delay = fault.seconds
                time.sleep(delay)
            stats = _local_stats(points, message["centers"], batch_size)
            _send(
                connection,
                {
                    "kind": "stats",
                    "shard_id": shard_id,
                    "pid": os.getpid(),
                    "round_id": round_id - 1 if inject and fault.action == "stale" else round_id,
                    "delay_seconds": delay,
                    **stats,
                },
            )
    except (EOFError, BrokenPipeError):
        return
    except Exception as exc:
        try:
            _send(connection, {"kind": "error", "error_type": type(exc).__name__})
        except (EOFError, OSError):
            pass
    finally:
        connection.close()


def _collect(connections, processes, timeout: float, kind: str):
    pending = {connection: shard for shard, connection in enumerate(connections)}
    deadline = time.monotonic() + timeout
    messages, received = [], 0
    while pending:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise WorkerFailure(f"{kind} timeout; missing shards {sorted(pending.values())}")
        ready = wait([*pending, *(p.sentinel for p in processes)], timeout=remaining)
        for process in processes:
            if process.sentinel in ready:
                raise WorkerFailure(f"worker exited during {kind}")
        for connection in list(pending):
            if connection not in ready:
                continue
            shard = pending.pop(connection)
            try:
                payload = connection.recv_bytes(262144)
                message = pickle.loads(payload)
            except (EOFError, OSError, pickle.UnpicklingError) as exc:
                raise WorkerFailure(f"worker connection closed during {kind}") from exc
            received += len(payload)
            if (
                not isinstance(message, dict)
                or message.get("kind") != kind
                or message.get("shard_id") != shard
            ):
                raise WorkerFailure(f"invalid worker reply during {kind}")
            if message.get("pid") != processes[shard].pid:
                raise WorkerFailure("reply PID does not match owned process")
            messages.append(message)
    return messages, received


def _close_workers(connections, processes, failed: bool) -> tuple:
    if not failed:
        for connection in connections:
            try:
                _send(connection, {"kind": "stop"})
            except (BrokenPipeError, OSError):
                pass
    for connection in connections:
        connection.close()
    # Each stage has one shared deadline, not a per-worker accumulated wait.
    for action in (None, "terminate", "kill"):
        for process in processes:
            if process.is_alive() and action is not None:
                getattr(process, action)()
        deadline = time.monotonic() + (0.0 if failed and action is None else 1.0)
        for process in processes:
            process.join(max(0.0, deadline - time.monotonic()))
        if all(not process.is_alive() for process in processes):
            break
    if any(process.is_alive() for process in processes):
        raise RuntimeError("owned workers could not be reaped")
    return tuple(process.exitcode for process in processes)


def fit_kmeans(
    points,
    initial_centers,
    *,
    workers: int = 0,
    shard_sizes=None,
    max_iter: int = 100,
    tol: float = 1e-6,
    batch_size: int = 1024,
    round_timeout: float = 30.0,
    fault: Fault | None = None,
) -> KMeansResult:
    """Fit Lloyd K-means; workers=0 is serial, workers>0 uses persistent spawn.

    Input validation precedes spawning. No retry or partial-round continuation.
    All final labels and SSE are evaluated against the returned centers.
    """
    points = np.asarray(points, dtype=np.float64)
    centers = np.array(initial_centers, dtype=np.float64, copy=True)
    if (
        points.ndim != 2
        or not all(points.shape)
        or points.size > 2_000_000
        or centers.ndim != 2
        or not all(centers.shape)
        or centers.shape[1] != points.shape[1]
        or len(centers) > len(points)
        or centers.size > 1024
        or not np.isfinite(points).all()
        or not np.isfinite(centers).all()
    ):
        raise ValueError("require finite N*D points and K*D centers, 1 <= K <= N, within budgets")
    workers = _integer(workers, "workers", 0, 32)
    max_iter = _integer(max_iter, "max_iter", 1, 10000)
    batch_size = _integer(batch_size, "batch_size", 1, 65536)
    tol = _number(tol, "tol")
    round_timeout = _number(round_timeout, "round_timeout", positive=True)
    count = workers or 1
    if shard_sizes is None:
        sizes = tuple(len(part) for part in np.array_split(points, count))
    else:
        sizes = tuple(_integer(size, "shard size", 0, len(points)) for size in shard_sizes)
        if len(sizes) != count or sum(sizes) != len(points):
            raise ValueError("shard_sizes must assign every point exactly once")
    if fault is not None:
        if (
            not workers
            or not isinstance(fault, Fault)
            or fault.action not in {"delay", "exit", "stale"}
        ):
            raise ValueError("fault requires parallel workers and a supported action")
        _integer(fault.worker_id, "fault worker", 0, workers - 1)
        _integer(fault.round_id, "fault round", 0, max_iter - 1)
        _number(fault.seconds, "fault seconds")
    started = time.perf_counter()
    connections, processes, history = [], [], []
    error, result = None, None
    try:
        if workers:
            context = mp.get_context("spawn")
            offset = 0
            for shard, size in enumerate(sizes):
                parent, child = context.Pipe()
                process = context.Process(
                    target=_worker,
                    name=f"kmeans-{shard}",
                    args=(child, shard, points[offset : offset + size], batch_size, fault),
                )
                connections.append(parent)
                try:
                    process.start()
                    processes.append(process)
                finally:
                    child.close()
                offset += size
            _collect(connections, processes, 15.0, "ready")
        startup_seconds = time.perf_counter() - started if workers else 0.0
        converged = False
        for round_id in range(max_iter):
            round_started = time.perf_counter()
            sent = received = 0
            if workers:
                for connection in connections:
                    sent += _send(
                        connection, {"kind": "step", "round_id": round_id, "centers": centers}
                    )
                remaining = round_timeout - (time.perf_counter() - round_started)
                messages, received = _collect(connections, processes, remaining, "stats")
            else:
                messages = [
                    {
                        "shard_id": 0,
                        "round_id": round_id,
                        "pid": os.getpid(),
                        "delay_seconds": 0.0,
                        **_local_stats(points, centers, batch_size),
                    }
                ]
            reduce_started = time.perf_counter()
            centers, counts, shift = _reduce_round(messages, sizes, centers, round_id)
            reduce_seconds = time.perf_counter() - reduce_started
            sse = sum(message["sse"] for message in messages)
            if not np.isfinite(sse):
                raise ValueError("nonfinite global SSE")
            history.append(
                {
                    "round_id": round_id,
                    "counts": counts.tolist(),
                    "sse_before_update": sse,
                    "center_shift": shift,
                    "round_seconds": time.perf_counter() - round_started,
                    "reduce_seconds": reduce_seconds,
                    "sent_payload_bytes": sent,
                    "received_payload_bytes": received,
                    "workers": [
                        {
                            "shard_id": m["shard_id"],
                            "pid": m["pid"],
                            "compute_seconds": m["compute_seconds"],
                            "delay_seconds": m["delay_seconds"],
                        }
                        for m in sorted(messages, key=lambda m: m["shard_id"])
                    ],
                }
            )
            if shift <= tol:
                converged = True
                break
        evaluation_started = time.perf_counter()
        labels = np.empty(len(points), dtype=np.int64)
        final_sse = 0.0
        for start, block, assigned, distances in _batches(points, centers, batch_size):
            labels[start : start + len(block)] = assigned
            final_sse += float(distances.sum())
        if not np.isfinite(final_sse):
            raise ValueError("nonfinite final SSE")
        result = KMeansResult(
            centers,
            labels,
            np.bincount(labels, minlength=len(centers)),
            final_sse,
            converged,
            history,
            sizes,
            tuple(p.pid for p in processes),
            (),
            startup_seconds,
            time.perf_counter() - evaluation_started,
            0.0,
            0.0,
        )
    except BaseException as exc:
        error = exc
        raise
    finally:
        shutdown_started = time.perf_counter()
        codes = _close_workers(connections, processes, error is not None)
        if isinstance(error, WorkerFailure):
            error.worker_pids = tuple(p.pid for p in processes)
            error.worker_exitcodes = codes
        if result is not None:
            result.worker_exitcodes = codes
            result.shutdown_seconds = time.perf_counter() - shutdown_started
            result.total_seconds = time.perf_counter() - started
            if any(code != 0 for code in codes):
                raise WorkerFailure("worker did not exit normally after successful computation")
    return result


def make_dataset(rows: int = 10000):
    rows = _integer(rows, "rows", 10, 1_000_000)
    rng = np.random.default_rng(42)
    locations = np.array([[-6.0, -6.0], [0.0, 6.0], [6.0, -6.0]])
    points = locations[np.arange(rows) % 3] + rng.normal(0, 0.65, (rows, 2))
    indices = np.random.default_rng(42).choice(rows, 3, replace=False)
    return points, points[indices].copy()


def _summary(result: KMeansResult) -> dict:
    return {
        "centers": result.centers.tolist(),
        "counts": result.counts.tolist(),
        "labels_sha256": hashlib.sha256(result.labels.tobytes()).hexdigest(),
        "sse": result.sse,
        "converged": result.converged,
        "rounds": len(result.history),
        "history": result.history,
        "shard_sizes": result.shard_sizes,
        "worker_pids": result.worker_pids,
        "worker_exitcodes": result.worker_exitcodes,
        "startup_seconds": result.startup_seconds,
        "evaluation_seconds": result.evaluation_seconds,
        "shutdown_seconds": result.shutdown_seconds,
        "total_seconds": result.total_seconds,
    }


def _require(condition: bool, message: str) -> None:
    # Unlike assert, the experiment's acceptance gates also run under python -O.
    if not condition:
        raise AssertionError(message)


def run_experiments(rows: int, record: dict) -> None:
    points, initial = make_dataset(rows)
    record.update(
        {
            "schema_version": 1,
            "status": "running",
            "rows": rows,
            "seed": 42,
            "dimensions": 2,
            "clusters": 3,
            "initial_centers": initial.tolist(),
            "input_bytes": points.nbytes,
            "input_sha256": hashlib.sha256(points.tobytes()).hexdigest(),
            "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "environment": {
                "python": platform.python_version(),
                "numpy": np.__version__,
                "system": platform.system(),
                "machine": platform.machine(),
                "libc": platform.libc_ver(),
                "start_method": "spawn",
                "numeric_thread_environment": {
                    name: os.environ.get(name)
                    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")
                },
                "cpu_affinity": sorted(os.sched_getaffinity(0))
                if hasattr(os, "sched_getaffinity")
                else None,
            },
            "runs": {},
            "expected_failures": {},
        }
    )
    baseline = fit_kmeans(points, initial)
    record["runs"]["serial"] = _summary(baseline)
    if not baseline.converged:
        raise AssertionError("synthetic baseline did not converge")
    # The synthetic generator puts its first three samples in different groups.
    # This is a controlled quality comparison, NOT a general initializer.
    control = fit_kmeans(points, points[:3])
    record["initialization_control"] = {
        "method": "first sample from each known synthetic group; not a general initializer",
        "initial_centers": points[:3].tolist(),
        "result": _summary(control),
    }
    skew = (rows * 7 // 10, rows // 10, rows // 10)
    cases = [
        ("processes-2", {"workers": 2}),
        ("processes-4", {"workers": 4}),
        ("uneven-4", {"workers": 4, "shard_sizes": (*skew, rows - sum(skew))}),
        ("slow-4", {"workers": 4, "fault": Fault(seconds=0.2)}),
    ]
    for name, options in cases:
        result = fit_kmeans(points, initial, **options)
        record["runs"][name] = _summary(result)
        np.testing.assert_allclose(result.centers, baseline.centers, rtol=1e-6, atol=1e-8)
        np.testing.assert_allclose(result.sse, baseline.sse, rtol=1e-6, atol=1e-8)
        np.testing.assert_array_equal(result.labels, baseline.labels)
        _require(result.converged, "parallel result did not converge")
        _require(len(set(result.worker_pids)) == options["workers"], "workers are not distinct")
        _require(os.getpid() not in result.worker_pids, "coordinator used as a worker")
        _require(all(sum(row["counts"]) == rows for row in result.history), "count mismatch")
        _require(
            all(
                tuple(w["pid"] for w in row["workers"]) == result.worker_pids
                for row in result.history
            ),
            "workers did not persist across rounds",
        )
        if name == "slow-4":
            _require(result.history[0]["round_seconds"] >= 0.2, "slow worker skipped barrier")
    for name, fault, timeout, expected in [
        ("exit", Fault(action="exit"), 30.0, "worker"),
        ("stale", Fault(action="stale"), 30.0, "round_id"),
        ("timeout", Fault(seconds=2.0), 0.1, "stats timeout"),
    ]:
        started = time.perf_counter()
        try:
            fit_kmeans(points, initial, workers=4, fault=fault, round_timeout=timeout)
        except WorkerFailure as exc:
            _require(expected in str(exc), str(exc))
            _require(
                len(exc.worker_pids) == 4 and all(c is not None for c in exc.worker_exitcodes),
                "failed workers were not reaped",
            )
            _require(
                not set(exc.worker_pids) & {p.pid for p in mp.active_children()},
                "owned workers are still active",
            )
            record["expected_failures"][name] = {
                "status": "observed",
                "error": str(exc),
                "worker_pids": exc.worker_pids,
                "worker_exitcodes": exc.worker_exitcodes,
                "total_seconds": time.perf_counter() - started,
            }
        else:
            raise AssertionError(f"{name} did not fail")
    record["status"] = "passed"


def _report(record: dict) -> str:
    lines = [
        "# K-means 本地多进程实验",
        "",
        f"状态：{record['status']}",
        "",
        "单次运行；不是跨机器或框架性能比较。总耗时包含启动、迭代、最终评估和回收。",
        "",
        "| 模式 | 轮数 | 最终 SSE | 启动秒 | 总秒 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, result in record.get("runs", {}).items():
        lines.append(
            f"| {name} | {result['rounds']} | {result['sse']:.8f} | "
            f"{result['startup_seconds']:.6f} | {result['total_seconds']:.6f} |"
        )
    if "initialization_control" in record:
        control = record["initialization_control"]["result"]
        lines += [
            "",
            f"受控初始化对照 SSE：{control['sse']:.8f}，{control['rounds']} 轮。",
            "它利用了合成数据的已知分组顺序，不是通用初始化方法。",
            "并行与串行结果相同，只证明计算等价；收敛不保证全局最优。",
        ]
    lines += ["", "故障注入："]
    for name, result in record.get("expected_failures", {}).items():
        lines.append(f"- {name}: {result['status']}；{result['error']}；全部自有进程已回收。")
    if "error" in record:
        lines += ["", f"未通过：{record['error']}"]
    lines += [
        "",
        "完整轮次、实际 PID、退出码、数据/代码哈希及序列化 payload 字节数见 result.json。",
        "payload 字节数不含进程启动数据、Pipe framing 或真实网络协议。",
        "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=10000)
    parser.add_argument("--output", type=Path, help="new evidence directory; never overwritten")
    args = parser.parse_args(argv)
    if not 10 <= args.rows <= 1_000_000:
        parser.error("--rows must be in [10, 1000000]")
    if args.output is None:
        local = Path(__file__).resolve().parent / ".local"
        if local.is_symlink() or (local / "kmeans").is_symlink():
            parser.error("default output parent must not be a symlink")
        name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        args.output = local / "kmeans" / name
    try:
        args.output.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        parser.error(f"cannot create new evidence directory: {exc.strerror}")
    record = {"status": "running"}
    code = 0
    try:
        run_experiments(args.rows, record)
    except (Exception, KeyboardInterrupt) as exc:
        record.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        code = 130 if isinstance(exc, KeyboardInterrupt) else 1
    (args.output / "result.json").write_text(
        json.dumps(record, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    report = _report(record)
    (args.output / "report.md").write_text(report, encoding="utf-8")
    print(report)
    print(f"Evidence: {args.output.resolve()}")
    return code


if __name__ == "__main__":
    sys.exit(main())
