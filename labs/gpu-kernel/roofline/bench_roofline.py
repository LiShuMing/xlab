"""M1.1: Empirical GPU Roofline calibration (VRAM bandwidth + GEMM compute sweep).

Measures:
  1. Memory hierarchy bandwidth across working-set sizes (L2 hit -> VRAM saturation)
     using both device-to-device copy and STREAM-like triad (`z = x + a * y`).
  2. GEMM throughput across decode-like batch sizes M in [1 .. 4096] for LLM projection
     shapes (e.g., 4096x4096 and 4096x14336) in FP32, TF32, BF16, and FP16.
  3. Empirical Roofline ridge point (FLOPs/Byte) and self-contained offline SVG/HTML report.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import html
import math
from pathlib import Path
import sys

import torch

LAB_ROOT = Path(__file__).resolve().parent.parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from common.timing import benchmark_cuda_fn, create_run_dir, probe_gpu_env, write_json


@dataclass(frozen=True)
class BandwidthPoint:
    op: str
    size_mb: float
    bytes_moved: int
    median_ms: float
    bandwidth_gb_s: float


@dataclass(frozen=True)
class GemmPoint:
    dtype: str
    m: int
    n: int
    k: int
    flops: int
    bytes_moved: int
    arithmetic_intensity: float
    median_ms: float
    tflops: float
    effective_bw_gb_s: float
    regime: str


def measure_bandwidth() -> list[BandwidthPoint]:
    """Sweep working-set sizes from L2-resident (2 MB) to VRAM-bound (256 MB)."""
    sizes_mb = [2, 8, 32, 64, 128, 256]
    results: list[BandwidthPoint] = []
    alpha = 1.25

    for size_mb in sizes_mb:
        num_elems = (size_mb * 1024 * 1024) // 4
        x = torch.randn(num_elems, dtype=torch.float32, device="cuda")
        y = torch.randn(num_elems, dtype=torch.float32, device="cuda")
        z = torch.empty_like(x)

        copy_bytes = 2 * num_elems * 4
        flush_mb = 64 if size_mb >= 64 else 0
        copy_stats = benchmark_cuda_fn(
            lambda: z.copy_(x), warmup=10, iters=40, l2_flush_mb=flush_mb
        )
        copy_bw = copy_bytes / (copy_stats.median_ms * 1e-3) / 1e9
        results.append(
            BandwidthPoint(
                op="copy",
                size_mb=float(size_mb),
                bytes_moved=copy_bytes,
                median_ms=round(copy_stats.median_ms, 4),
                bandwidth_gb_s=round(copy_bw, 1),
            )
        )

        triad_bytes = 3 * num_elems * 4
        triad_stats = benchmark_cuda_fn(
            lambda: torch.add(x, y, alpha=alpha, out=z),
            warmup=10,
            iters=40,
            l2_flush_mb=flush_mb,
        )
        triad_bw = triad_bytes / (triad_stats.median_ms * 1e-3) / 1e9
        results.append(
            BandwidthPoint(
                op="triad",
                size_mb=float(size_mb),
                bytes_moved=triad_bytes,
                median_ms=round(triad_stats.median_ms, 4),
                bandwidth_gb_s=round(triad_bw, 1),
            )
        )

    return results


def measure_gemm_sweep(peak_bw_gb_s: float) -> list[GemmPoint]:
    """Sweep M from decode (M=1) to prefill/large-batch (M=4096) across dtypes."""
    results: list[GemmPoint] = []
    configs = [
        ("bf16", torch.bfloat16, False, [1, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 4096], 4096, 4096),
        ("fp16", torch.float16, False, [1, 16, 64, 128, 512, 4096], 4096, 4096),
        ("fp32_tf32", torch.float32, True, [1, 16, 64, 256, 4096], 4096, 4096),
        ("fp32_ieee", torch.float32, False, [1, 16, 64, 256, 4096], 4096, 4096),
        ("bf16_ffn", torch.bfloat16, False, [1, 8, 32, 128, 512, 2048], 14336, 4096),
    ]

    orig_tf32 = torch.backends.cuda.matmul.allow_tf32
    try:
        for label, dtype, allow_tf32, m_list, n, k in configs:
            torch.backends.cuda.matmul.allow_tf32 = allow_tf32
            elem_bytes = torch.tensor([], dtype=dtype).element_size()
            b = torch.randn((k, n), dtype=dtype, device="cuda")

            local_points: list[tuple[int, int, int, float, float, float, float]] = []
            for m in m_list:
                a = torch.randn((m, k), dtype=dtype, device="cuda")
                out = torch.empty((m, n), dtype=dtype, device="cuda")
                stats = benchmark_cuda_fn(
                    lambda: torch.mm(a, b, out=out),
                    warmup=10,
                    iters=40,
                    l2_flush_mb=64,
                )
                flops = 2 * m * n * k
                bytes_moved = (m * k + k * n + m * n) * elem_bytes
                ai = flops / bytes_moved
                tflops = flops / (stats.median_ms * 1e-3) / 1e12
                eff_bw = bytes_moved / (stats.median_ms * 1e-3) / 1e9
                local_points.append((m, flops, bytes_moved, ai, stats.median_ms, tflops, eff_bw))

            peak_tflops = max(p[5] for p in local_points)
            ridge_ai = (peak_tflops * 1e12) / (peak_bw_gb_s * 1e9)
            for m, flops, bytes_moved, ai, med_ms, tflops, eff_bw in local_points:
                regime = "memory-bound" if ai < ridge_ai else "compute-bound"
                results.append(
                    GemmPoint(
                        dtype=label,
                        m=m,
                        n=n,
                        k=k,
                        flops=flops,
                        bytes_moved=bytes_moved,
                        arithmetic_intensity=round(ai, 2),
                        median_ms=round(med_ms, 4),
                        tflops=round(tflops, 2),
                        effective_bw_gb_s=round(eff_bw, 1),
                        regime=regime,
                    )
                )
    finally:
        torch.backends.cuda.matmul.allow_tf32 = orig_tf32

    return results


def render_roofline_svg(
    peak_bw_gb_s: float,
    peak_bf16_tflops: float,
    bf16_points: list[GemmPoint],
) -> str:
    """Render a self-contained log-log Roofline SVG for BF16 GEMM."""
    width, height = 760, 400
    ml, mr, mt, mb = 72, 30, 32, 54
    pw, ph = width - ml - mr, height - mt - mb

    x_min, x_max = 0.5, 4096.0
    y_min, y_max = 0.2, max(200.0, peak_bf16_tflops * 1.8)

    def sx(val: float) -> float:
        t = (math.log10(max(val, x_min)) - math.log10(x_min)) / (
            math.log10(x_max) - math.log10(x_min)
        )
        return ml + t * pw

    def sy(val: float) -> float:
        t = (math.log10(max(val, y_min)) - math.log10(y_min)) / (
            math.log10(y_max) - math.log10(y_min)
        )
        return mt + ph - t * ph

    ridge = (peak_bf16_tflops * 1e12) / (peak_bw_gb_s * 1e9)
    bw_y_start = (peak_bw_gb_s * x_min) / 1000.0
    roof_pts = [
        (sx(x_min), sy(min(bw_y_start, peak_bf16_tflops))),
        (sx(ridge), sy(peak_bf16_tflops)),
        (sx(x_max), sy(peak_bf16_tflops)),
    ]
    roof_path = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in roof_pts)

    grid_lines: list[str] = []
    for xv in [1, 4, 16, 64, 256, 1024]:
        gx = sx(xv)
        grid_lines.append(
            f'<line x1="{gx:.1f}" y1="{mt}" x2="{gx:.1f}" y2="{mt+ph}" '
            'stroke="#e2e8f0" stroke-width="1"/>'
            f'<text x="{gx:.1f}" y="{mt+ph+18}" text-anchor="middle" '
            f'font-size="11" fill="#475569">{xv}</text>'
        )
    for yv in [0.5, 1, 5, 10, 50, 100]:
        if yv > y_max:
            continue
        gy = sy(yv)
        grid_lines.append(
            f'<line x1="{ml}" y1="{gy:.1f}" x2="{ml+pw}" y2="{gy:.1f}" '
            'stroke="#e2e8f0" stroke-width="1"/>'
            f'<text x="{ml-8}" y="{gy+4:.1f}" text-anchor="end" '
            f'font-size="11" fill="#475569">{yv}</text>'
        )

    dots: list[str] = []
    for pt in bf16_points:
        cx, cy = sx(pt.arithmetic_intensity), sy(pt.tflops)
        color = "#0284c7" if pt.dtype == "bf16" else "#ea580c"
        dots.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4.5" fill="{color}"/>'
            f'<text x="{cx+6:.1f}" y="{cy-5:.1f}" font-size="10" fill="#1e293b">M={pt.m}</text>'
        )

    rx, ry = sx(ridge), sy(peak_bf16_tflops)
    return f"""<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}"
     xmlns="http://www.w3.org/2000/svg" style="background:#ffffff;border:1px solid #cbd5e1;border-radius:8px">
  {"".join(grid_lines)}
  <line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt+ph}" stroke="#334155" stroke-width="1.5"/>
  <line x1="{ml}" y1="{mt+ph}" x2="{ml+pw}" y2="{mt+ph}" stroke="#334155" stroke-width="1.5"/>
  <path d="{roof_path}" fill="none" stroke="#0f172a" stroke-width="2.5"/>
  <line x1="{rx:.1f}" y1="{ry:.1f}" x2="{rx:.1f}" y2="{mt+ph}" stroke="#dc2626" stroke-dasharray="4 4" stroke-width="1.5"/>
  <text x="{rx+6:.1f}" y="{ry+16:.1f}" font-size="11" fill="#dc2626">Ridge ≈ {ridge:.1f} FLOPs/B</text>
  <text x="{ml+pw-6}" y="{ry-8:.1f}" text-anchor="end" font-size="11" fill="#0f172a">Peak BF16 ≈ {peak_bf16_tflops:.1f} TFLOPS</text>
  <text x="{sx(2.5):.1f}" y="{sy((peak_bw_gb_s*2.5)/1000.0)-10:.1f}" font-size="11" fill="#0f172a">VRAM BW ≈ {peak_bw_gb_s:.1f} GB/s</text>
  {"".join(dots)}
  <text x="{ml + pw/2:.1f}" y="{height - 12}" text-anchor="middle" font-size="12" fill="#0f172a">Arithmetic Intensity (FLOPs / Byte, log scale)</text>
  <text x="18" y="{mt + ph/2:.1f}" text-anchor="middle" font-size="12" fill="#0f172a" transform="rotate(-90 18 {mt + ph/2:.1f})">Achieved TFLOPS (log scale)</text>
</svg>"""


def write_html_report(
    path: Path,
    env: dict[str, object],
    bw_points: list[BandwidthPoint],
    gemm_points: list[GemmPoint],
    peak_bw_gb_s: float,
    peak_bf16_tflops: float,
) -> None:
    """Write a self-contained offline HTML Roofline report."""
    bf16_pts = [p for p in gemm_points if p.dtype == "bf16"]
    svg = render_roofline_svg(peak_bw_gb_s, peak_bf16_tflops, bf16_pts)
    ridge = (peak_bf16_tflops * 1e12) / (peak_bw_gb_s * 1e9)

    bw_rows = "\n".join(
        f"<tr><td>{p.op}</td><td>{p.size_mb:.0f} MB</td><td>{p.median_ms:.4f}</td><td>{p.bandwidth_gb_s:.1f}</td></tr>"
        for p in bw_points
    )
    gemm_rows = "\n".join(
        f"<tr><td>{html.escape(p.dtype)}</td><td>{p.m}×{p.k}×{p.n}</td>"
        f"<td>{p.arithmetic_intensity:.2f}</td><td>{p.median_ms:.4f}</td>"
        f"<td>{p.tflops:.2f}</td><td>{p.effective_bw_gb_s:.1f}</td><td>{p.regime}</td></tr>"
        for p in gemm_points
    )

    doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>GPU Roofline Report — {html.escape(str(env['device_name']))}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 28px auto; max-width: 960px; color: #0f172a; line-height: 1.5; }}
  h1, h2 {{ border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; }}
  .cards {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 16px 0; }}
  .card {{ background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px; }}
  .card .k {{ font-size: 12px; color: #64748b; }}
  .card .v {{ font-size: 20px; font-weight: 700; margin-top: 4px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 12px 0 24px; font-size: 13px; }}
  th, td {{ border: 1px solid #cbd5e1; padding: 6px 10px; text-align: right; }}
  th:first-child, td:first-child, th:last-child, td:last-child {{ text-align: left; }}
  th {{ background: #f1f5f9; }}
</style>
</head>
<body>
<h1>GPU Roofline 实测报告</h1>
<p>设备：{html.escape(str(env['device_name']))} (sm_{html.escape(str(env['compute_capability']).replace('.', ''))}, {env['sm_count']} SMs, {env['total_memory_gib']} GiB) · PyTorch {html.escape(str(env['torch_version']))} · CUDA {html.escape(str(env['cuda_version']))} · UTC {html.escape(str(env['timestamp_utc']))}</p>
<div class="cards">
  <div class="card"><div class="k">实测 VRAM 峰值带宽</div><div class="v">{peak_bw_gb_s:.1f} GB/s</div></div>
  <div class="card"><div class="k">实测 BF16 GEMM 峰值</div><div class="v">{peak_bf16_tflops:.1f} TFLOPS</div></div>
  <div class="card"><div class="k">BF16 Roofline 拐点</div><div class="v">{ridge:.1f} FLOPs/B</div></div>
  <div class="card"><div class="k">4B-BF16 Decode 理论极限</div><div class="v">~{peak_bw_gb_s/8.0:.0f} tok/s</div></div>
</div>
<h2>BF16 Roofline (M×4096×4096)</h2>
{svg}
<h2>1. 显存带宽与 L2 缓存阶梯</h2>
<table><thead><tr><th>算子</th><th>单张量大小</th><th>Median (ms)</th><th>有效带宽 (GB/s)</th></tr></thead><tbody>{bw_rows}</tbody></table>
<h2>2. GEMM 算术强度与 Decode→Prefill 迁移</h2>
<table><thead><tr><th>精度/形状</th><th>M×K×N</th><th>AI (FLOPs/B)</th><th>Median (ms)</th><th>TFLOPS</th><th>有效带宽 (GB/s)</th><th>区间</th></tr></thead><tbody>{gemm_rows}</tbody></table>
</body>
</html>
"""
    path.write_text(doc, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Empirical GPU Roofline calibration.")
    parser.add_argument("--no-report", action="store_true", help="Skip writing HTML/JSON files.")
    args = parser.parse_args()

    env = probe_gpu_env()
    print(
        f"Device: {env['device_name']} (sm_{env['compute_capability'].replace('.', '')}, "
        f"{env['sm_count']} SMs, {env['total_memory_gib']} GiB)"
    )

    bw_points = measure_bandwidth()
    vram_bw_points = [p for p in bw_points if p.size_mb >= 64]
    peak_bw_gb_s = max(p.bandwidth_gb_s for p in vram_bw_points)

    print("\n=== 1. Memory Bandwidth Sweep ===")
    print(f"{'Op':<8} {'Size':>8} {'Median(ms)':>12} {'BW(GB/s)':>10}")
    for p in bw_points:
        print(f"{p.op:<8} {p.size_mb:>6.0f}MB {p.median_ms:>12.4f} {p.bandwidth_gb_s:>10.1f}")
    print(f"Peak steady-state VRAM bandwidth (>=64MB): {peak_bw_gb_s:.1f} GB/s")

    gemm_points = measure_gemm_sweep(peak_bw_gb_s)
    peak_bf16_tflops = max(p.tflops for p in gemm_points if p.dtype == "bf16")
    ridge_ai = (peak_bf16_tflops * 1e12) / (peak_bw_gb_s * 1e9)

    print("\n=== 2. GEMM Roofline Sweep ===")
    print(
        f"{'Dtype':<10} {'Shape':>16} {'AI':>8} {'Median(ms)':>11} "
        f"{'TFLOPS':>8} {'EffBW':>9}  Regime"
    )
    for p in gemm_points:
        shape = f"{p.m}x{p.k}x{p.n}"
        print(
            f"{p.dtype:<10} {shape:>16} {p.arithmetic_intensity:>8.2f} "
            f"{p.median_ms:>11.4f} {p.tflops:>8.2f} {p.effective_bw_gb_s:>7.1f}GB/s  {p.regime}"
        )
    print(
        f"\nSummary: Peak VRAM BW = {peak_bw_gb_s:.1f} GB/s | "
        f"Peak BF16 GEMM = {peak_bf16_tflops:.1f} TFLOPS | "
        f"BF16 Ridge = {ridge_ai:.1f} FLOPs/Byte"
    )

    if not args.no_report:
        run_dir = create_run_dir(LAB_ROOT, "roofline")
        write_json(
            run_dir / "roofline.json",
            {
                "environment": env,
                "summary": {
                    "peak_vram_bw_gb_s": peak_bw_gb_s,
                    "peak_bf16_tflops": peak_bf16_tflops,
                    "bf16_ridge_flops_per_byte": round(ridge_ai, 2),
                },
                "bandwidth": [asdict(p) for p in bw_points],
                "gemm": [asdict(p) for p in gemm_points],
            },
        )
        report_path = run_dir / "report.html"
        write_html_report(
            report_path, env, bw_points, gemm_points, peak_bw_gb_s, peak_bf16_tflops
        )
        print(f"REPORT={report_path}")


if __name__ == "__main__":
    main()
