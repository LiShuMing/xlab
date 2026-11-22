"""M1.2: Correctness parity and VRAM bandwidth benchmark for Fused RMSNorm & Softmax.

Compares:
  - PyTorch Eager (unfused multi-pass ops)
  - PyTorch Built-in (`F.rms_norm`, `torch.softmax`)
  - Hand-written Triton fused kernels (`triton_ops.py`)
  - Hand-written CUDA C++ kernels (`bin/cuda_fused_ops`, when built)
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import subprocess
import sys

import torch
import torch.nn.functional as F

LAB_ROOT = Path(__file__).resolve().parent.parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from common.timing import (
    benchmark_cuda_fn,
    create_run_dir,
    ensure_triton_cache,
    probe_gpu_env,
    write_json,
)

# Ensure Triton cache resides inside labs/gpu-kernel/.local before importing triton_ops.
ensure_triton_cache(LAB_ROOT)

from fused_ops.triton_ops import triton_rmsnorm, triton_softmax


@dataclass(frozen=True)
class KernelBenchRow:
    op: str
    impl: str
    rows: int
    cols: int
    dtype: str
    median_ms: float
    effective_bw_gb_s: float
    speedup_vs_eager: float


def eager_rmsnorm(x: torch.Tensor, weight: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    """Reference unfused PyTorch eager RMSNorm (multiple HBM round-trips)."""
    x_fp32 = x.float()
    var = x_fp32.pow(2).mean(dim=-1, keepdim=True)
    y = x_fp32 * torch.rsqrt(var + eps)
    return (y * weight.float()).to(x.dtype)


def eager_softmax(x: torch.Tensor) -> torch.Tensor:
    """Reference unfused 3-pass PyTorch eager Softmax."""
    x_fp32 = x.float()
    x_max = x_fp32.max(dim=-1, keepdim=True).values
    exp_x = torch.exp(x_fp32 - x_max)
    return (exp_x / exp_x.sum(dim=-1, keepdim=True)).to(x.dtype)


def run_parity_tests() -> None:
    """Verify Triton kernels against FP32 references across pow2, non-pow2, and extreme inputs."""
    torch.manual_seed(42)
    eps = 1e-6
    test_shapes = [
        (7, 127),
        (16, 513),
        (32, 1024),
        (32, 3584),
        (64, 4096),
        (16, 8192),
    ]

    for dtype, rms_tol, sm_tol in [
        (torch.float32, 1e-5, 1e-5),
        (torch.bfloat16, 3e-2, 2e-2),
    ]:
        for rows, cols in test_shapes:
            x = torch.randn((rows, cols), device="cuda", dtype=dtype) * 5.0
            w = torch.randn((cols,), device="cuda", dtype=dtype) * 0.5 + 1.0

            ref_rms = eager_rmsnorm(x.float(), w.float(), eps)
            got_rms = triton_rmsnorm(x, w, eps).float()
            rms_err = (got_rms - ref_rms).abs().max().item()
            assert rms_err <= rms_tol, (
                f"RMSNorm parity failed: dtype={dtype} shape=({rows},{cols}) max_err={rms_err}"
            )

            # Include extreme values (+50 / -50) to verify numerical stability of softmax.
            x_ext = x.clone()
            x_ext[0, 0] = 50.0
            x_ext[0, -1] = -50.0
            ref_sm = torch.softmax(x_ext.float(), dim=-1)
            got_sm = triton_softmax(x_ext).float()
            sm_err = (got_sm - ref_sm).abs().max().item()
            row_sum_err = (got_sm.sum(dim=-1) - 1.0).abs().max().item()
            assert sm_err <= sm_tol and row_sum_err <= sm_tol, (
                f"Softmax parity failed: dtype={dtype} shape=({rows},{cols}) "
                f"max_err={sm_err} row_sum_err={row_sum_err}"
            )

    print("PASS: All Triton RMSNorm & Softmax numerical parity tests passed (FP32 & BF16).")


def run_cuda_binary_bench(op: str, rows: int, cols: int) -> tuple[float, float] | None:
    """Invoke compiled CUDA C++ binary if present and parse its JSON timing result."""
    bin_path = LAB_ROOT / "fused_ops" / "bin" / "cuda_fused_ops"
    if not bin_path.is_file():
        return None
    out = subprocess.check_output(
        [
            str(bin_path),
            "--bench",
            op,
            "--rows",
            str(rows),
            "--cols",
            str(cols),
            "--iters",
            "50",
        ],
        text=True,
    )
    for line in reversed(out.strip().splitlines()):
        if line.startswith("{"):
            data = json.loads(line)
            return float(data["median_ms"]), float(data["bw_gb_s"])
    return None


def run_benchmarks() -> list[KernelBenchRow]:
    """Benchmark BF16 RMSNorm and Softmax across LLM-relevant hidden sizes."""
    shapes = [
        (4096, 2048),  # Qwen3-1.7B hidden size, 4K tokens
        (4096, 4096),  # Qwen3-8B / Llama-8B hidden size, 4K tokens
        (4096, 8192),  # 70B hidden / large attention row
    ]
    dtype = torch.bfloat16
    elem_bytes = 2
    eps = 1e-6
    rows_out: list[KernelBenchRow] = []

    for rows, cols in shapes:
        x = torch.randn((rows, cols), device="cuda", dtype=dtype)
        w = torch.ones((cols,), device="cuda", dtype=dtype)

        # --- RMSNorm ---
        rms_bytes = (2 * rows * cols + cols) * elem_bytes
        rms_impls = [
            ("pytorch_eager", lambda: eager_rmsnorm(x, w, eps)),
            ("pytorch_builtin", lambda: F.rms_norm(x, (cols,), w, eps)),
            ("triton_fused", lambda: triton_rmsnorm(x, w, eps)),
        ]
        eager_ms = 0.0
        for impl_name, fn in rms_impls:
            stats = benchmark_cuda_fn(fn, warmup=15, iters=50, l2_flush_mb=64)
            bw = rms_bytes / (stats.median_ms * 1e-3) / 1e9
            if impl_name == "pytorch_eager":
                eager_ms = stats.median_ms
            rows_out.append(
                KernelBenchRow(
                    op="rmsnorm",
                    impl=impl_name,
                    rows=rows,
                    cols=cols,
                    dtype="bf16",
                    median_ms=round(stats.median_ms, 4),
                    effective_bw_gb_s=round(bw, 1),
                    speedup_vs_eager=round(eager_ms / stats.median_ms, 2),
                )
            )

        cuda_rms = run_cuda_binary_bench("rmsnorm", rows, cols)
        if cuda_rms is not None:
            med_ms, bw = cuda_rms
            rows_out.append(
                KernelBenchRow(
                    op="rmsnorm",
                    impl="cuda_cpp",
                    rows=rows,
                    cols=cols,
                    dtype="bf16",
                    median_ms=round(med_ms, 4),
                    effective_bw_gb_s=round(bw, 1),
                    speedup_vs_eager=round(eager_ms / med_ms, 2),
                )
            )

        # --- Softmax ---
        sm_bytes = (2 * rows * cols) * elem_bytes
        sm_impls = [
            ("pytorch_eager", lambda: eager_softmax(x)),
            ("pytorch_builtin", lambda: torch.softmax(x, dim=-1)),
            ("triton_fused", lambda: triton_softmax(x)),
        ]
        eager_sm_ms = 0.0
        for impl_name, fn in sm_impls:
            stats = benchmark_cuda_fn(fn, warmup=15, iters=50, l2_flush_mb=64)
            bw = sm_bytes / (stats.median_ms * 1e-3) / 1e9
            if impl_name == "pytorch_eager":
                eager_sm_ms = stats.median_ms
            rows_out.append(
                KernelBenchRow(
                    op="softmax",
                    impl=impl_name,
                    rows=rows,
                    cols=cols,
                    dtype="bf16",
                    median_ms=round(stats.median_ms, 4),
                    effective_bw_gb_s=round(bw, 1),
                    speedup_vs_eager=round(eager_sm_ms / stats.median_ms, 2),
                )
            )

        cuda_sm = run_cuda_binary_bench("softmax", rows, cols)
        if cuda_sm is not None:
            med_ms, bw = cuda_sm
            rows_out.append(
                KernelBenchRow(
                    op="softmax",
                    impl="cuda_cpp",
                    rows=rows,
                    cols=cols,
                    dtype="bf16",
                    median_ms=round(med_ms, 4),
                    effective_bw_gb_s=round(bw, 1),
                    speedup_vs_eager=round(eager_sm_ms / med_ms, 2),
                )
            )

    return rows_out


def main() -> None:
    parser = argparse.ArgumentParser(description="Fused RMSNorm & Softmax parity and benchmark.")
    parser.add_argument("--test-only", action="store_true", help="Run parity tests only.")
    parser.add_argument("--no-report", action="store_true", help="Skip saving JSON artifacts.")
    args = parser.parse_args()

    env = probe_gpu_env()
    run_parity_tests()
    if args.test_only:
        return

    results = run_benchmarks()
    print(f"\nDevice: {env['device_name']} (sm_{env['compute_capability'].replace('.', '')})")
    print(
        f"{'Op':<9} {'Shape':>11} {'Impl':<16} {'Median(ms)':>11} {'EffBW(GB/s)':>12} {'vs Eager':>9}"
    )
    for r in results:
        print(
            f"{r.op:<9} {f'{r.rows}x{r.cols}':>11} {r.impl:<16} "
            f"{r.median_ms:>11.4f} {r.effective_bw_gb_s:>12.1f} {r.speedup_vs_eager:>8.2f}x"
        )

    if not args.no_report:
        run_dir = create_run_dir(LAB_ROOT, "fused-ops")
        out_path = run_dir / "fused_ops.json"
        write_json(
            out_path,
            {"environment": env, "results": [asdict(r) for r in results]},
        )
        print(f"ARTIFACT={out_path}")


if __name__ == "__main__":
    main()
