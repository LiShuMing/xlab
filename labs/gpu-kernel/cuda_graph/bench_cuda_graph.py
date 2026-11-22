"""M1.3: CUDA Graph vs Eager launch-overhead benchmark & PyTorch Profiler Chrome Trace.

Models a stacked Transformer decode step (RMSNorm -> QKV/O projections -> SwiGLU FFN -> Residual)
with static pre-allocated buffers to isolate and quantify CPU kernel-launch bubbles on a single GPU.

Key verification & metrics:
  1. Multi-input parity check: verifies that replaying the captured CUDA Graph with different
     inputs copied into `static_x` matches Eager output (no stale-buffer bug).
  2. Batch sweep (M = 1..64) across two model scales (`qwen_0.6b_like` and `qwen_4b_like`):
     measures end-to-end wall-clock ITL (CPU + GPU), speedup vs Eager, and gap to theoretical
     VRAM-bandwidth floor.
  3. PyTorch Profiler (CPU + CUDA) capture for M=1: exports Chrome Trace JSON files
     (`trace_eager.json`, `trace_cudagraph.json`) openable in `chrome://tracing` or Perfetto UI,
     and computes exact CUDA kernel count, GPU active time, and GPU bubble ratio.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import statistics
import sys
import time
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.profiler import ProfilerActivity, profile

LAB_ROOT = Path(__file__).resolve().parent.parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from common.timing import create_run_dir, probe_gpu_env, write_json


class DecodeBlock(nn.Module):
    """Single Transformer decoder layer for steady-state decode-step launch profiling.

    Uses F.rms_norm, linear projections (QKV + O), and SwiGLU MLP (gate/up/down).
    Attention score over KV cache is represented by a lightweight batched projection on
    pre-allocated static KV tensors to keep the focus on per-layer kernel launch count
    and memory traffic without dynamic allocation inside graph capture.
    """

    def __init__(self, hidden: int, ffn: int, num_heads: int, kv_len: int) -> None:
        super().__init__()
        self.hidden = hidden
        self.num_heads = num_heads
        self.head_dim = hidden // num_heads
        self.kv_len = kv_len

        self.norm1_w = nn.Parameter(torch.ones(hidden))
        self.q_proj = nn.Linear(hidden, hidden, bias=False)
        self.o_proj = nn.Linear(hidden, hidden, bias=False)

        self.norm2_w = nn.Parameter(torch.ones(hidden))
        self.gate_proj = nn.Linear(hidden, ffn, bias=False)
        self.up_proj = nn.Linear(hidden, ffn, bias=False)
        self.down_proj = nn.Linear(ffn, hidden, bias=False)

    def forward(
        self,
        x: torch.Tensor,
        k_cache: torch.Tensor,
        v_cache: torch.Tensor,
    ) -> torch.Tensor:
        # x: [B, 1, H], k_cache / v_cache: [B, heads, kv_len, head_dim]
        h = F.rms_norm(x, (self.hidden,), self.norm1_w, 1e-6)
        q = self.q_proj(h).view(x.shape[0], self.num_heads, 1, self.head_dim)
        attn_out = F.scaled_dot_product_attention(q, k_cache, v_cache)
        attn_out = attn_out.transpose(1, 2).reshape(x.shape[0], 1, self.hidden)
        x = x + self.o_proj(attn_out)

        h2 = F.rms_norm(x, (self.hidden,), self.norm2_w, 1e-6)
        ffn_out = self.down_proj(F.silu(self.gate_proj(h2)) * self.up_proj(h2))
        return x + ffn_out


class StackedDecodeModel(nn.Module):
    """Stack of N decoder blocks sharing fixed static KV caches for one decode step."""

    def __init__(
        self,
        num_layers: int,
        hidden: int,
        ffn: int,
        num_heads: int,
        kv_len: int,
    ) -> None:
        super().__init__()
        self.num_layers = num_layers
        self.hidden = hidden
        self.num_heads = num_heads
        self.head_dim = hidden // num_heads
        self.kv_len = kv_len
        self.layers = nn.ModuleList(
            [DecodeBlock(hidden, ffn, num_heads, kv_len) for _ in range(num_layers)]
        )
        self.final_norm_w = nn.Parameter(torch.ones(hidden))

    def forward(
        self,
        x: torch.Tensor,
        k_caches: list[torch.Tensor],
        v_caches: list[torch.Tensor],
    ) -> torch.Tensor:
        for idx, layer in enumerate(self.layers):
            x = layer(x, k_caches[idx], v_caches[idx])
        return F.rms_norm(x, (self.hidden,), self.final_norm_w, 1e-6)

    def weight_bytes(self) -> int:
        return sum(p.numel() * p.element_size() for p in self.parameters())


@dataclass(frozen=True)
class ModelSpec:
    name: str
    num_layers: int
    hidden: int
    ffn: int
    num_heads: int
    kv_len: int


@dataclass(frozen=True)
class GraphBenchRow:
    profile_name: str
    batch_size: int
    num_layers: int
    hidden: int
    weight_mb: float
    kv_mb: float
    eager_wall_ms: float
    graph_wall_ms: float
    eager_gpu_ms: float
    graph_gpu_ms: float
    speedup_wall: float
    saved_launch_ms: float
    vram_floor_ms: float
    eager_bw_eff_pct: float
    graph_bw_eff_pct: float


@dataclass(frozen=True)
class ProfilerSummary:
    mode: str
    profile_name: str
    batch_size: int
    steps_profiled: int
    wall_ms_per_step: float
    gpu_busy_ms_per_step: float
    gpu_duty_cycle_pct: float
    gpu_bubble_pct: float
    cuda_kernels_per_step: float
    cpu_launch_calls_per_step: float
    trace_file: str


def build_static_kv(
    spec: ModelSpec,
    batch_size: int,
    dtype: torch.dtype,
) -> tuple[list[torch.Tensor], list[torch.Tensor]]:
    shape = (batch_size, spec.num_heads, spec.kv_len, spec.hidden // spec.num_heads)
    k_caches = [torch.randn(shape, device="cuda", dtype=dtype) for _ in range(spec.num_layers)]
    v_caches = [torch.randn(shape, device="cuda", dtype=dtype) for _ in range(spec.num_layers)]
    return k_caches, v_caches


def capture_decode_graph(
    model: StackedDecodeModel,
    static_x: torch.Tensor,
    k_caches: list[torch.Tensor],
    v_caches: list[torch.Tensor],
) -> tuple[torch.cuda.CUDAGraph, torch.Tensor]:
    """Warm up on a side stream and capture the full decode step into a CUDA Graph."""
    s = torch.cuda.Stream()
    s.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(s), torch.no_grad():
        for _ in range(3):
            _ = model(static_x, k_caches, v_caches)
    torch.cuda.current_stream().wait_stream(s)
    torch.cuda.synchronize()

    graph = torch.cuda.CUDAGraph()
    with torch.cuda.graph(graph), torch.no_grad():
        static_out = model(static_x, k_caches, v_caches)
    torch.cuda.synchronize()
    return graph, static_out


def measure_wall_and_gpu_ms(
    fn,
    *,
    warmup: int = 10,
    iters: int = 40,
) -> tuple[float, float]:
    """Measure per-step end-to-end wall time and GPU event time (synchronized per step).

    Synchronizing per step models an autoregressive token loop where the host must read
    the sampled token ID (or check EOS) before deciding the next decode step.
    """
    for _ in range(warmup):
        fn()
    torch.cuda.synchronize()

    wall_times: list[float] = []
    gpu_times: list[float] = []
    for _ in range(iters):
        ev_start = torch.cuda.Event(enable_timing=True)
        ev_end = torch.cuda.Event(enable_timing=True)
        t0 = time.perf_counter()
        ev_start.record()
        fn()
        ev_end.record()
        torch.cuda.synchronize()
        t1 = time.perf_counter()
        wall_times.append((t1 - t0) * 1000.0)
        gpu_times.append(ev_start.elapsed_time(ev_end))

    return statistics.median(wall_times), statistics.median(gpu_times)


def run_parity_test() -> None:
    """Verify CUDA Graph replay matches Eager across multiple distinct input tensors."""
    torch.manual_seed(123)
    spec = ModelSpec("parity_check", num_layers=6, hidden=512, ffn=1536, num_heads=8, kv_len=64)
    dtype = torch.bfloat16
    model = StackedDecodeModel(
        spec.num_layers, spec.hidden, spec.ffn, spec.num_heads, spec.kv_len
    ).to(device="cuda", dtype=dtype).eval()
    k_caches, v_caches = build_static_kv(spec, batch_size=4, dtype=dtype)
    static_x = torch.randn((4, 1, spec.hidden), device="cuda", dtype=dtype)

    graph, static_out = capture_decode_graph(model, static_x, k_caches, v_caches)

    prev_out: torch.Tensor | None = None
    for trial in range(3):
        new_x = torch.randn((4, 1, spec.hidden), device="cuda", dtype=dtype) * (trial + 1)
        with torch.no_grad():
            ref_out = model(new_x, k_caches, v_caches).clone()

        static_x.copy_(new_x)
        graph.replay()
        torch.cuda.synchronize()
        got_out = static_out.clone()

        max_err = (got_out.float() - ref_out.float()).abs().max().item()
        assert max_err <= 2e-2, f"CUDA Graph parity failed on trial {trial}: max_err={max_err}"
        if prev_out is not None:
            diff_prev = (got_out.float() - prev_out.float()).abs().max().item()
            assert diff_prev > 1e-2, "CUDA Graph output did not change after updating static_x!"
        prev_out = got_out

    print("PASS: CUDA Graph multi-input numerical parity verified (3 distinct inputs).")


def analyze_chrome_trace(trace_path: Path, steps: int, wall_ms_total: float) -> tuple[float, float, float]:
    """Compute union of GPU kernel active intervals (ms/step), kernel count, and launch count."""
    data = json.loads(trace_path.read_text(encoding="utf-8"))
    events = data.get("traceEvents", [])

    gpu_intervals: list[tuple[float, float]] = []
    kernel_count = 0
    launch_count = 0

    for ev in events:
        if ev.get("ph") != "X":
            continue
        cat = str(ev.get("cat", "")).lower()
        name = str(ev.get("name", ""))
        dur = float(ev.get("dur", 0.0))
        ts = float(ev.get("ts", 0.0))
        if cat in ("kernel", "gpu_memcpy", "gpu_memset"):
            if dur > 0.0:
                gpu_intervals.append((ts, ts + dur))
            if cat == "kernel":
                kernel_count += 1
        elif cat == "cuda_runtime" and (
            "LaunchKernel" in name or "GraphLaunch" in name
        ):
            launch_count += 1

    # Merge overlapping GPU intervals to get exact GPU busy time in microseconds.
    gpu_intervals.sort()
    busy_us = 0.0
    if gpu_intervals:
        cur_s, cur_e = gpu_intervals[0]
        for s, e in gpu_intervals[1:]:
            if s <= cur_e:
                if e > cur_e:
                    cur_e = e
            else:
                busy_us += cur_e - cur_s
                cur_s, cur_e = s, e
        busy_us += cur_e - cur_s

    gpu_busy_ms_per_step = (busy_us / 1000.0) / steps
    return gpu_busy_ms_per_step, kernel_count / steps, launch_count / steps


def profile_mode(
    mode: str,
    spec: ModelSpec,
    batch_size: int,
    fn,
    out_dir: Path,
    steps: int = 8,
) -> ProfilerSummary:
    """Capture a PyTorch Profiler Chrome Trace and summarize GPU duty cycle vs bubbles."""
    for _ in range(5):
        fn()
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    with profile(
        activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA],
        record_shapes=False,
        with_stack=False,
    ) as prof:
        for _ in range(steps):
            fn()
            torch.cuda.synchronize()
    wall_ms_total = (time.perf_counter() - t0) * 1000.0

    trace_name = f"trace_{mode}.json"
    trace_path = out_dir / trace_name
    prof.export_chrome_trace(str(trace_path))

    gpu_busy_ms, kernels_per_step, launches_per_step = analyze_chrome_trace(
        trace_path, steps, wall_ms_total
    )
    wall_per_step = wall_ms_total / steps
    duty_pct = min(100.0, (gpu_busy_ms / wall_per_step) * 100.0) if wall_per_step > 0 else 0.0
    bubble_pct = max(0.0, 100.0 - duty_pct)

    return ProfilerSummary(
        mode=mode,
        profile_name=spec.name,
        batch_size=batch_size,
        steps_profiled=steps,
        wall_ms_per_step=round(wall_per_step, 4),
        gpu_busy_ms_per_step=round(gpu_busy_ms, 4),
        gpu_duty_cycle_pct=round(duty_pct, 1),
        gpu_bubble_pct=round(bubble_pct, 1),
        cuda_kernels_per_step=round(kernels_per_step, 1),
        cpu_launch_calls_per_step=round(launches_per_step, 1),
        trace_file=trace_name,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="M1.3: CUDA Graph vs Eager launch-overhead benchmark and Chrome Trace."
    )
    parser.add_argument("--test-only", action="store_true", help="Run parity test only.")
    parser.add_argument(
        "--peak-bw",
        type=float,
        default=792.7,
        help="Measured steady-state VRAM bandwidth in GB/s for floor reference.",
    )
    parser.add_argument("--no-report", action="store_true", help="Skip writing JSON/trace files.")
    args = parser.parse_args()

    env = probe_gpu_env()
    run_parity_test()
    if args.test_only:
        return

    specs = [
        ModelSpec("qwen_0.6b_like", num_layers=24, hidden=1024, ffn=3072, num_heads=16, kv_len=256),
        ModelSpec("qwen_4b_like", num_layers=24, hidden=2560, ffn=6912, num_heads=20, kv_len=256),
    ]
    batch_sizes = [1, 2, 4, 8, 16, 32, 64]
    dtype = torch.bfloat16

    rows: list[GraphBenchRow] = []
    prof_summaries: list[ProfilerSummary] = []
    run_dir = None if args.no_report else create_run_dir(LAB_ROOT, "cuda-graph")

    print(f"\nDevice: {env['device_name']} (sm_{env['compute_capability'].replace('.', '')})")
    print(
        f"{'Profile':<15} {'B':>3} {'Weights':>8} {'Eager(ms)':>10} {'Graph(ms)':>10} "
        f"{'Speedup':>8} {'Saved(ms)':>10} {'Floor(ms)':>10}"
    )

    for spec in specs:
        model = StackedDecodeModel(
            spec.num_layers, spec.hidden, spec.ffn, spec.num_heads, spec.kv_len
        ).to(device="cuda", dtype=dtype).eval()
        weight_bytes = model.weight_bytes()
        weight_mb = weight_bytes / (1024**2)

        for bs in batch_sizes:
            k_caches, v_caches = build_static_kv(spec, bs, dtype)
            kv_bytes = sum(t.numel() * t.element_size() for t in k_caches + v_caches)
            kv_mb = kv_bytes / (1024**2)

            static_x = torch.randn((bs, 1, spec.hidden), device="cuda", dtype=dtype)
            input_x = torch.randn_like(static_x)

            def run_eager() -> None:
                with torch.no_grad():
                    _ = model(input_x, k_caches, v_caches)

            graph, _static_out = capture_decode_graph(model, static_x, k_caches, v_caches)

            def run_graph() -> None:
                static_x.copy_(input_x)
                graph.replay()

            eager_wall, eager_gpu = measure_wall_and_gpu_ms(run_eager, warmup=10, iters=40)
            graph_wall, graph_gpu = measure_wall_and_gpu_ms(run_graph, warmup=10, iters=40)

            total_read_bytes = weight_bytes + kv_bytes
            vram_floor_ms = (total_read_bytes / (args.peak_bw * 1e9)) * 1000.0
            speedup = eager_wall / graph_wall
            saved_ms = eager_wall - graph_wall
            eager_eff = min(100.0, (vram_floor_ms / eager_wall) * 100.0)
            graph_eff = min(100.0, (vram_floor_ms / graph_wall) * 100.0)

            row = GraphBenchRow(
                profile_name=spec.name,
                batch_size=bs,
                num_layers=spec.num_layers,
                hidden=spec.hidden,
                weight_mb=round(weight_mb, 1),
                kv_mb=round(kv_mb, 1),
                eager_wall_ms=round(eager_wall, 4),
                graph_wall_ms=round(graph_wall, 4),
                eager_gpu_ms=round(eager_gpu, 4),
                graph_gpu_ms=round(graph_gpu, 4),
                speedup_wall=round(speedup, 2),
                saved_launch_ms=round(saved_ms, 4),
                vram_floor_ms=round(vram_floor_ms, 4),
                eager_bw_eff_pct=round(eager_eff, 1),
                graph_bw_eff_pct=round(graph_eff, 1),
            )
            rows.append(row)
            print(
                f"{spec.name:<15} {bs:>3} {weight_mb:>6.0f}MB {eager_wall:>10.3f} "
                f"{graph_wall:>10.3f} {speedup:>7.2f}x {saved_ms:>10.3f} {vram_floor_ms:>10.3f}"
            )

            # Capture Chrome Traces at B=1 for qwen_0.6b_like (the clearest launch-bubble case).
            if run_dir is not None and spec.name == "qwen_0.6b_like" and bs == 1:
                prof_summaries.append(profile_mode("eager", spec, bs, run_eager, run_dir))
                prof_summaries.append(profile_mode("cudagraph", spec, bs, run_graph, run_dir))

            del graph, _static_out, k_caches, v_caches, static_x, input_x
            torch.cuda.empty_cache()

        del model
        torch.cuda.empty_cache()

    if prof_summaries:
        print("\n=== PyTorch Profiler Chrome Trace Summary (qwen_0.6b_like, B=1) ===")
        print(
            f"{'Mode':<11} {'Wall(ms)':>9} {'GPU Busy':>9} {'Duty%':>7} "
            f"{'Bubble%':>8} {'Kernels':>8} {'HostLaunch':>11}  Trace"
        )
        for p in prof_summaries:
            print(
                f"{p.mode:<11} {p.wall_ms_per_step:>9.3f} {p.gpu_busy_ms_per_step:>9.3f} "
                f"{p.gpu_duty_cycle_pct:>6.1f}% {p.gpu_bubble_pct:>7.1f}% "
                f"{p.cuda_kernels_per_step:>8.1f} {p.cpu_launch_calls_per_step:>11.1f}  {p.trace_file}"
            )

    if run_dir is not None:
        out_path = run_dir / "cuda_graph.json"
        write_json(
            out_path,
            {
                "environment": env,
                "peak_vram_bw_gb_s": args.peak_bw,
                "results": [asdict(r) for r in rows],
                "profiler": [asdict(p) for p in prof_summaries],
            },
        )
        print(f"ARTIFACT={out_path}")


if __name__ == "__main__":
    main()
