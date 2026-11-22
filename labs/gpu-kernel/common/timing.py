"""Shared CUDA timing, hardware probing, and report helpers for labs/gpu-kernel."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import datetime as dt
import json
import os
from pathlib import Path
import statistics
from typing import Any, Callable

import torch


@dataclass(frozen=True)
class TimingStats:
    """Summary of CUDA event timings in milliseconds."""

    median_ms: float
    min_ms: float
    p95_ms: float
    mean_ms: float
    iters: int


def ensure_triton_cache(lab_root: Path) -> Path:
    """Ensure Triton writes its cache inside the lab's ignored .local directory."""
    cache_dir = Path(os.environ.get("TRITON_CACHE_DIR", str(lab_root / ".local" / "triton_cache")))
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ["TRITON_CACHE_DIR"] = str(cache_dir)
    return cache_dir


def probe_gpu_env() -> dict[str, Any]:
    """Collect reproducible hardware and runtime metadata for the active CUDA device."""
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA device is required for labs/gpu-kernel benchmarks.")
    props = torch.cuda.get_device_properties(0)
    cc_major, cc_minor = torch.cuda.get_device_capability(0)
    return {
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "device_name": props.name,
        "compute_capability": f"{cc_major}.{cc_minor}",
        "sm_count": props.multi_processor_count,
        "total_memory_gib": round(props.total_memory / (1024**3), 2),
        "torch_version": torch.__version__,
        "cuda_version": torch.version.cuda,
    }


def benchmark_cuda_fn(
    fn: Callable[[], Any],
    *,
    warmup: int = 10,
    iters: int = 50,
    l2_flush_mb: int = 64,
) -> TimingStats:
    """Measure pure GPU execution time using CUDA events with optional L2 cache flush.

    Flushing L2 between iterations prevents small memory-bound benchmarks from reporting
    artificially inflated L2-hit bandwidth when measuring steady-state VRAM performance.
    """
    flush_buf: torch.Tensor | None = None
    if l2_flush_mb > 0:
        flush_buf = torch.empty(
            (l2_flush_mb * 1024 * 1024) // 4,
            dtype=torch.int32,
            device="cuda",
        )

    for _ in range(warmup):
        fn()
    torch.cuda.synchronize()

    starts = [torch.cuda.Event(enable_timing=True) for _ in range(iters)]
    ends = [torch.cuda.Event(enable_timing=True) for _ in range(iters)]

    for i in range(iters):
        if flush_buf is not None:
            flush_buf.zero_()
        starts[i].record()
        fn()
        ends[i].record()

    torch.cuda.synchronize()
    times_ms = sorted(s.elapsed_time(e) for s, e in zip(starts, ends))
    p95_idx = min(len(times_ms) - 1, int(0.95 * (len(times_ms) - 1)))
    return TimingStats(
        median_ms=statistics.median(times_ms),
        min_ms=times_ms[0],
        p95_ms=times_ms[p95_idx],
        mean_ms=statistics.fmean(times_ms),
        iters=iters,
    )


def create_run_dir(lab_root: Path, suite_name: str) -> Path:
    """Create a timestamped output directory under .local/runs/."""
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    run_dir = lab_root / ".local" / "runs" / f"{stamp}-{suite_name}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write formatted JSON artifact."""
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def stats_to_dict(stats: TimingStats) -> dict[str, Any]:
    """Convert TimingStats to a JSON-serializable dictionary."""
    return asdict(stats)
