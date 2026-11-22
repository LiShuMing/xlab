"""M4.1: Single-GPU Sharing & Noisy-Neighbor Interference Benchmark (CUDA Streams + Multi-Process).

Measures on a single RTX 5070 Ti:
  1. CUDA Stream Priority: high-priority latency-sensitive decode GEMV stream running alongside
     a low-priority heavy GEMM background stream (demonstrates SM preemption/scheduling limits).
  2. Multi-Process GPU Sharing (Noisy Neighbor): two OS processes sharing the same RTX 5070 Ti
     concurrently — measures isolated latency vs contended P99 latency degradation and aggregate
     throughput gain (highlighting why consumer GPUs without hardware MIG exhibit tail-latency
     interference even when aggregate utilization rises).
"""

from __future__ import annotations

import datetime as dt
import json
import multiprocessing as mp
from pathlib import Path
import statistics
import sys
import time
from typing import Any

import torch

LAB_ROOT = Path(__file__).resolve().parent.parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from common.timing import create_run_dir, probe_gpu_env, write_json


def percentile(vals: list[float], p: float) -> float:
    s = sorted(vals)
    return s[min(len(s) - 1, int(p * (len(s) - 1)))]


def bench_stream_priority() -> dict[str, Any]:
    """Compare solo high-priority decode step vs concurrent background heavy GEMM stream."""
    a_dec = torch.randn((8, 4096), device="cuda", dtype=torch.bfloat16)
    w_dec = torch.randn((4096, 4096), device="cuda", dtype=torch.bfloat16)

    a_bg = torch.randn((2048, 4096), device="cuda", dtype=torch.bfloat16)
    w_bg = torch.randn((4096, 4096), device="cuda", dtype=torch.bfloat16)

    # PyTorch stream priority: -1 is higher priority, 0 is default/lower.
    hi_stream = torch.cuda.Stream(priority=-1)
    lo_stream = torch.cuda.Stream(priority=0)

    # Warmup
    for _ in range(10):
        _ = a_dec @ w_dec
        _ = a_bg @ w_bg
    torch.cuda.synchronize()

    # 1. Solo decode latency on hi_stream
    solo_ms: list[float] = []
    for _ in range(60):
        ev0, ev1 = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
        with torch.cuda.stream(hi_stream):
            ev0.record(hi_stream)
            _ = a_dec @ w_dec
            ev1.record(hi_stream)
        hi_stream.synchronize()
        solo_ms.append(ev0.elapsed_time(ev1))

    # 2. Contended: enqueue heavy GEMMs on lo_stream while timing decode GEMVs on hi_stream
    contended_hi_ms: list[float] = []
    for _ in range(60):
        with torch.cuda.stream(lo_stream):
            for _ in range(3):
                _ = a_bg @ w_bg
        ev0, ev1 = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
        with torch.cuda.stream(hi_stream):
            ev0.record(hi_stream)
            _ = a_dec @ w_dec
            ev1.record(hi_stream)
        hi_stream.synchronize()
        contended_hi_ms.append(ev0.elapsed_time(ev1))
    torch.cuda.synchronize()

    return {
        "solo_median_ms": round(statistics.median(solo_ms), 4),
        "solo_p99_ms": round(percentile(solo_ms, 0.99), 4),
        "contended_hi_median_ms": round(statistics.median(contended_hi_ms), 4),
        "contended_hi_p99_ms": round(percentile(contended_hi_ms, 0.99), 4),
        "p99_inflation_ratio": round(
            percentile(contended_hi_ms, 0.99) / max(1e-6, percentile(solo_ms, 0.99)), 2
        ),
    }


def _worker_latency_probe(
    ready_evt,
    start_evt,
    stop_evt,
    out_q,
    iters: int,
) -> None:
    """Latency-sensitive process: runs repeated decode-like GEMVs and records per-step wall ms."""
    a = torch.randn((8, 4096), device="cuda", dtype=torch.bfloat16)
    w = torch.randn((4096, 4096), device="cuda", dtype=torch.bfloat16)
    for _ in range(10):
        _ = a @ w
    torch.cuda.synchronize()
    ready_evt.set()
    start_evt.wait()

    times_ms: list[float] = []
    for _ in range(iters):
        t0 = time.perf_counter()
        for _ in range(8):  # 8 linear layers per micro-step
            _ = a @ w
        torch.cuda.synchronize()
        times_ms.append((time.perf_counter() - t0) * 1000.0)
    stop_evt.set()
    out_q.put(times_ms)


def _worker_noisy_neighbor(ready_evt, start_evt, stop_evt, out_q) -> None:
    """Background batch process: saturates GPU with large 4096^3 BF16 GEMMs until stop_evt."""
    a = torch.randn((4096, 4096), device="cuda", dtype=torch.bfloat16)
    b = torch.randn((4096, 4096), device="cuda", dtype=torch.bfloat16)
    for _ in range(5):
        _ = a @ b
    torch.cuda.synchronize()
    ready_evt.set()
    start_evt.wait()

    gemms = 0
    t0 = time.perf_counter()
    while not stop_evt.is_set():
        _ = a @ b
        torch.cuda.synchronize()
        gemms += 1
    dt_s = time.perf_counter() - t0
    out_q.put({"bg_gemms": gemms, "bg_tflops": round((gemms * 2 * 4096**3) / max(dt_s, 1e-6) / 1e12, 1)})


def bench_multiprocess_noisy_neighbor() -> dict[str, Any]:
    """Compare solo process latency vs 2-process concurrent GPU sharing (no hardware MIG)."""
    ctx = mp.get_context("spawn")
    iters = 50

    # 1. Solo latency-sensitive process
    r1, s1, stop1, q1 = ctx.Event(), ctx.Event(), ctx.Event(), ctx.Queue()
    p_solo = ctx.Process(target=_worker_latency_probe, args=(r1, s1, stop1, q1, iters))
    p_solo.start()
    r1.wait()
    s1.set()
    solo_times: list[float] = q1.get()
    p_solo.join()

    # 2. Concurrent latency-sensitive process + noisy-neighbor heavy GEMM process
    r_lat, r_bg = ctx.Event(), ctx.Event()
    go_evt, stop_evt = ctx.Event(), ctx.Event()
    q_lat, q_bg = ctx.Queue(), ctx.Queue()

    p_lat = ctx.Process(target=_worker_latency_probe, args=(r_lat, go_evt, stop_evt, q_lat, iters))
    p_bg = ctx.Process(target=_worker_noisy_neighbor, args=(r_bg, go_evt, stop_evt, q_bg))
    p_lat.start()
    p_bg.start()
    r_lat.wait()
    r_bg.wait()
    go_evt.set()

    shared_times: list[float] = q_lat.get()
    bg_stats: dict[str, Any] = q_bg.get()
    p_lat.join()
    p_bg.join()

    return {
        "solo_median_ms": round(statistics.median(solo_times), 3),
        "solo_p99_ms": round(percentile(solo_times, 0.99), 3),
        "shared_median_ms": round(statistics.median(shared_times), 3),
        "shared_p99_ms": round(percentile(shared_times, 0.99), 3),
        "p99_inflation_ratio": round(
            percentile(shared_times, 0.99) / max(1e-6, percentile(solo_times, 0.99)), 2
        ),
        "bg_concurrent_tflops": bg_stats["bg_tflops"],
        "bg_gemms_completed": bg_stats["bg_gemms"],
    }


def main() -> None:
    env = probe_gpu_env()
    print(f"Device: {env['device_name']} (sm_{env['compute_capability'].replace('.', '')})")

    stream_res = bench_stream_priority()
    print("\n=== 1. CUDA Stream Priority (Hi-Priority Decode vs Lo-Priority Heavy GEMM) ===")
    print(json.dumps(stream_res, indent=2))

    mp_res = bench_multiprocess_noisy_neighbor()
    print("\n=== 2. Multi-Process GPU Sharing (Noisy Neighbor Tail Latency) ===")
    print(json.dumps(mp_res, indent=2))

    run_dir = create_run_dir(LAB_ROOT, "gpu-sharing")
    out_path = run_dir / "gpu_sharing.json"
    write_json(
        out_path,
        {
            "environment": env,
            "stream_priority": stream_res,
            "multiprocess_noisy_neighbor": mp_res,
        },
    )
    print(f"\nARTIFACT={out_path}")


if __name__ == "__main__":
    main()
