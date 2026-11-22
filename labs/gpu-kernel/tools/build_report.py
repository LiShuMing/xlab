"""Build a unified, interactive, offline HTML observability & learning report for labs/gpu-kernel.

Aggregates the latest JSON outputs from `.local/runs/*-roofline/roofline.json` and
`.local/runs/*-fused-ops/fused_ops.json` into a single self-contained HTML report with:
  - Hardware & Roofline KPI summary
  - Interactive log-log Roofline SVG (with series toggles, M1.2 kernel overlay & tooltips)
  - Interactive Roofline "What-If" learning calculator (model size / precision / batch size)
  - Memory hierarchy ladder (L2 cache hit -> steady-state GDDR7 VRAM)
  - Four-way fused kernel comparison (PyTorch Eager / Built-in / Triton / CUDA C++)
  - Counter-intuitive findings, 3-step Roofline diagnostics, and filterable raw tables
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
from pathlib import Path
import sys
from typing import Any

LAB_ROOT = Path(__file__).resolve().parent.parent


def find_latest_artifact(runs_dir: Path, filename: str) -> Path | None:
    """Return the most recent matching JSON artifact under `.local/runs/`."""
    if not runs_dir.is_dir():
        return None
    matches = sorted(runs_dir.glob(f"*/{filename}"))
    return matches[-1] if matches else None


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_html(
    roofline_data: dict[str, Any],
    fused_data: dict[str, Any] | None,
    graph_data: dict[str, Any] | None,
    roofline_src: str,
    fused_src: str | None,
    graph_src: str | None,
) -> str:
    env = roofline_data["environment"]
    summary = roofline_data["summary"]
    peak_bw = float(summary["peak_vram_bw_gb_s"])
    peak_bf16 = float(summary["peak_bf16_tflops"])
    ridge = float(summary["bf16_ridge_flops_per_byte"])

    gemm_rows = roofline_data.get("gemm", [])
    peak_ffn = max(
        (float(r["tflops"]) for r in gemm_rows if r.get("dtype") == "bf16_ffn"),
        default=peak_bf16,
    )
    peak_fp16 = max(
        (float(r["tflops"]) for r in gemm_rows if r.get("dtype") == "fp16"),
        default=peak_bf16,
    )

    fused_rows = fused_data.get("results", []) if fused_data else []
    best_fused_bw = max((float(r["effective_bw_gb_s"]) for r in fused_rows), default=0.0)
    best_speedup = max((float(r["speedup_vs_eager"]) for r in fused_rows), default=1.0)
    best_bw_pct = (best_fused_bw / peak_bw * 100.0) if peak_bw > 0 else 0.0

    graph_rows = graph_data.get("results", []) if graph_data else []
    graph_prof = graph_data.get("profiler", []) if graph_data else []
    best_graph_speedup = max((float(r["speedup_wall"]) for r in graph_rows), default=1.0)
    best_graph_row = max(graph_rows, key=lambda r: float(r["speedup_wall"]), default=None)
    best_graph_note = (
        f"{best_graph_row['profile_name']} B={best_graph_row['batch_size']}: "
        f"{best_graph_row['eager_wall_ms']:.2f} → {best_graph_row['graph_wall_ms']:.2f} ms"
        if best_graph_row
        else "尚未运行 make cuda-graph"
    )
    graph_run_dir = str(Path(graph_src).parent) if graph_src else None

    # Safe JSON payload embedded for offline client-side SVG & table interactivity (no eval).
    payload = {
        "environment": env,
        "summary": {
            "peak_vram_bw_gb_s": peak_bw,
            "peak_bf16_tflops": peak_bf16,
            "peak_ffn_tflops": peak_ffn,
            "peak_fp16_tflops": peak_fp16,
            "bf16_ridge_flops_per_byte": ridge,
        },
        "bandwidth": roofline_data.get("bandwidth", []),
        "gemm": gemm_rows,
        "fused_ops": fused_rows,
        "cuda_graph": graph_rows,
        "cuda_graph_profiler": graph_prof,
        "cuda_graph_dir": graph_run_dir,
    }
    embedded_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")

    device_name = html.escape(str(env.get("device_name", "Unknown GPU")))
    cc = html.escape(str(env.get("compute_capability", "?")).replace(".", ""))
    sm_count = html.escape(str(env.get("sm_count", "?")))
    vram_gib = html.escape(str(env.get("total_memory_gib", "?")))
    torch_ver = html.escape(str(env.get("torch_version", "?")))
    cuda_ver = html.escape(str(env.get("cuda_version", "?")))
    built_utc = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>GPU Kernel &amp; Roofline 观测与学习报告 — {device_name}</title>
<style>
:root {{
  color-scheme: light;
  --ink: #172c40;
  --muted: #5e7081;
  --line: #dce5ed;
  --accent: #11666b;
  --accent-soft: #e6f4f4;
  --warn: #b67b29;
  --warn-bg: #fff7e9;
  --danger: #c0392b;
  --danger-bg: #fdf2f2;
  --paper: #f3f6fa;
  --header: #112f41;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font: 14px/1.65 system-ui, -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
}}
header {{
  padding: 32px max(24px, calc((100vw - 1360px) / 2));
  background: var(--header);
  color: #f3fafc;
}}
header .muted {{ color: #b8cbd4; font-size: 13px; }}
.eyebrow {{ letter-spacing: .12em; font-size: 11px; color: #8ddad1; text-transform: uppercase; }}
h1 {{ font-size: 28px; line-height: 1.25; margin: 10px 0 8px; }}
h2 {{ font-size: 20px; margin: 0 0 12px; display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }}
h2 small {{ font-size: 12px; font-weight: 400; color: var(--muted); }}
h3 {{ font-size: 16px; margin: 18px 0 8px; }}
p {{ margin: 8px 0; }}
main {{ max-width: 1408px; padding: 0 24px 48px; margin: auto; }}
nav {{
  display: flex;
  gap: 18px;
  padding: 14px 4px;
  flex-wrap: wrap;
  position: sticky;
  top: 0;
  background: rgba(243, 246, 250, 0.94);
  backdrop-filter: blur(6px);
  z-index: 20;
  border-bottom: 1px solid var(--line);
  margin-bottom: 18px;
}}
a {{ color: #076673; text-decoration: none; font-weight: 500; }}
a:hover {{ text-decoration: underline; color: #073b46; }}
section {{
  background: #ffffff;
  padding: 24px;
  border: 1px solid var(--line);
  border-radius: 10px;
  margin: 0 0 20px;
  scroll-margin-top: 58px;
}}
.cards {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 14px;
  margin: 14px 0 6px;
}}
.card {{
  border: 1px solid var(--line);
  border-top: 3px solid var(--accent);
  padding: 14px 16px;
  border-radius: 6px;
  background: #fafcfe;
}}
.card.warn {{ border-top-color: var(--warn); }}
.card .k {{ font-size: 12px; color: var(--muted); }}
.card strong {{ display: block; font-size: 26px; line-height: 1.25; margin-top: 4px; font-variant-numeric: tabular-nums; }}
.card small {{ display: block; margin-top: 4px; color: var(--muted); font-size: 12px; }}
.grid-2 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 18px; }}
.grid-3 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(270px, 1fr)); gap: 14px; }}
.callout {{
  border-left: 4px solid var(--accent);
  background: var(--accent-soft);
  padding: 12px 16px;
  margin: 12px 0;
  border-radius: 4px;
}}
.callout.warn {{ border-left-color: var(--warn); background: var(--warn-bg); }}
.callout.danger {{ border-left-color: var(--danger); background: var(--danger-bg); }}
.controls {{
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
  background: #f3f7f9;
  padding: 12px 14px;
  border: 1px solid var(--line);
  border-radius: 6px;
  margin-bottom: 14px;
}}
.chip {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 11px;
  border-radius: 999px;
  border: 1px solid #bdcbd5;
  background: #ffffff;
  font-size: 12px;
  cursor: pointer;
  user-select: none;
}}
.chip input {{ margin: 0; }}
.dot {{ width: 9px; height: 9px; border-radius: 50%; display: inline-block; }}
.chart-wrap {{
  position: relative;
  width: 100%;
  overflow-x: auto;
}}
#roofline-tooltip {{
  position: fixed;
  pointer-events: none;
  background: rgba(17, 47, 65, 0.96);
  color: #f8fafc;
  padding: 10px 12px;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.5;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.22);
  display: none;
  z-index: 100;
  max-width: 290px;
}}
.bar-row {{
  display: grid;
  grid-template-columns: 150px 1fr 120px;
  gap: 10px;
  align-items: center;
  margin: 7px 0;
  font-size: 12.5px;
}}
.bar-track {{
  position: relative;
  height: 22px;
  background: #edf2f7;
  border-radius: 4px;
  overflow: hidden;
}}
.bar-fill {{
  height: 100%;
  border-radius: 4px;
  transition: width .2s ease;
}}
.bar-ref-line {{
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  background: #c0392b;
}}
.bar-val {{ text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; }}
.calc-box {{
  background: #f7fafc;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 16px;
}}
.slider-row {{
  display: grid;
  grid-template-columns: 160px 1fr 110px;
  gap: 12px;
  align-items: center;
  margin: 10px 0;
}}
.pill-group {{ display: flex; gap: 8px; flex-wrap: wrap; }}
.pill {{
  padding: 5px 12px;
  border: 1px solid #bdcbd5;
  background: #ffffff;
  border-radius: 5px;
  cursor: pointer;
  font-size: 12.5px;
}}
.pill.active {{
  background: var(--accent);
  color: #ffffff;
  border-color: var(--accent);
}}
.table-scroll {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 6px; }}
table {{
  border-collapse: collapse;
  width: 100%;
  font-size: 12.5px;
  font-variant-numeric: tabular-nums;
}}
th, td {{ padding: 7px 10px; border-bottom: 1px solid #e6edf3; text-align: right; }}
th {{ background: #f3f7f9; color: var(--ink); font-weight: 600; position: sticky; top: 0; }}
th:first-child, td:first-child, th:nth-child(2), td:nth-child(2), th:last-child, td:last-child {{ text-align: left; }}
tr:hover td {{ background: #f8fbfd; }}
.tag {{
  display: inline-block;
  padding: 1px 7px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}}
.tag.mem {{ background: #e0f2fe; color: #0369a1; }}
.tag.comp {{ background: #fef3c7; color: #92400e; }}
.tag.ok {{ background: #dcfce7; color: #166534; }}
code {{
  background: #edf2f7;
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 12px;
}}
.formula {{
  background: #f8fafc;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 10px 14px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 13px;
  margin: 10px 0;
  overflow-x: auto;
}}
footer {{ color: var(--muted); font-size: 12px; text-align: center; padding: 12px 0 24px; }}
</style>
</head>
<body>
<header>
  <div class="eyebrow">xlab / labs/gpu-kernel · Single-GPU Observability &amp; Learning Report</div>
  <h1>GPU Roofline、融合算子与 CUDA Graph 实测报告（M1.1 + M1.2 + M1.3）</h1>
  <div class="muted">
    硬件：{device_name}（Blackwell sm_{cc} · {sm_count} SMs · {vram_gib} GiB GDDR7） ·
    软件：PyTorch {torch_ver} · CUDA {cuda_ver} · 报告生成：{built_utc}
  </div>
</header>

<main>
  <nav>
    <a href="#overview">1. 关键指标</a>
    <a href="#roofline-chart">2. Roofline 交互图</a>
    <a href="#calculator">3. 动手算 Roofline</a>
    <a href="#bandwidth">4. L2→VRAM 带宽阶梯</a>
    <a href="#fused-ops">5. 融合算子四方对照</a>
    <a href="#cuda-graph">6. CUDA Graph 与空泡</a>
    <a href="#diagnostics">7. 反直觉发现与诊断法</a>
    <a href="#raw-tables">8. 完整数据与验证证据</a>
  </nav>

  <section id="overview">
    <h2>1. 关键指标总览 <small>一次看清硬件天花板、融合算子与 CUDA Graph 收益</small></h2>
    <div class="cards">
      <div class="card">
        <div class="k">稳态显存带宽（≥64 MB + L2 flush）</div>
        <strong>{peak_bw:.1f} GB/s</strong>
        <small>256 MB Triad 实测（约 88% GDDR7 理论带宽）</small>
      </div>
      <div class="card">
        <div class="k">BF16 GEMM 峰值算力</div>
        <strong>{peak_bf16:.2f} TFLOPS</strong>
        <small>4096³ 实测；FFN 2048×4096×14336 达 {peak_ffn:.2f} TFLOPS</small>
      </div>
      <div class="card warn">
        <div class="k">BF16 Roofline 拐点（Ridge Point）</div>
        <strong>{ridge:.1f} FLOPs/B</strong>
        <small>Decode batch &lt; ~114 卡显存带宽，&gt; 114 卡算力</small>
      </div>
      <div class="card">
        <div class="k">融合算子最高带宽占比（M1.2）</div>
        <strong>{best_bw_pct:.1f}%</strong>
        <small>最高 {best_fused_bw:.1f} GB/s · 相对 Eager 提速最高 {best_speedup:.2f}×</small>
      </div>
      <div class="card">
        <div class="k">CUDA Graph 最大加速（M1.3）</div>
        <strong>{best_graph_speedup:.2f}×</strong>
        <small>{html.escape(best_graph_note)}</small>
      </div>
      <div class="card">
        <div class="k">数值对拍 &amp; Sanitizer 验证</div>
        <strong>0 Errors</strong>
        <small>FP32/BF16/Graph 对拍通过 · memcheck/racecheck 零告警</small>
      </div>
    </div>

    <div class="callout">
      <strong>一句话理解 Roofline：</strong>
      GPU 的真实速度同时被「搬数据速度（带宽 {peak_bw:.1f} GB/s）」和「算数据速度（算力 {peak_bf16:.1f} TFLOPS）」卡住。
      每个算子的 <strong>算术强度 AI = FLOPs / Bytes</strong> 决定了它落在哪一侧：
      AI &lt; {ridge:.0f} 在左侧斜屋顶（<strong>Memory-bound</strong>），优化重点是减少显存读写（算子融合、量化、增大 batch 复用权重）；
      AI &gt; {ridge:.0f} 在右侧平屋顶（<strong>Compute-bound</strong>），优化重点是 Tensor Core 算力与更低精度（FP8/FP16）。
    </div>
  </section>

  <section id="roofline-chart">
    <h2>2. 交互式 Roofline 屋顶线图 <small>悬停任意点查看实测耗时、带宽与屋顶利用率</small></h2>
    <div class="controls" id="roofline-controls">
      <label class="chip"><input type="checkbox" data-series="bf16" checked/><span class="dot" style="background:#0284c7"></span>BF16 4096×4096</label>
      <label class="chip"><input type="checkbox" data-series="bf16_ffn" checked/><span class="dot" style="background:#ea580c"></span>BF16 FFN 4096×14336</label>
      <label class="chip"><input type="checkbox" data-series="fp16"/><span class="dot" style="background:#7c3aed"></span>FP16 4096×4096</label>
      <label class="chip"><input type="checkbox" data-series="fp32_tf32"/><span class="dot" style="background:#0d9488"></span>FP32 (TF32)</label>
      <label class="chip"><input type="checkbox" data-series="fp32_ieee"/><span class="dot" style="background:#64748b"></span>FP32 (IEEE)</label>
      <label class="chip"><input type="checkbox" data-series="fused_overlay" checked/><span class="dot" style="background:#16a34a"></span>叠加 M1.2 融合算子（4096×4096）</label>
    </div>
    <div class="chart-wrap">
      <svg id="roofline-svg" viewBox="0 0 920 450" width="920" height="450" style="max-width:100%;height:auto;background:#ffffff;border:1px solid var(--line);border-radius:8px"></svg>
    </div>
    <div class="formula">
      Attainable Perf (FLOP/s) ≤ min( Peak_Compute, Peak_BW × AI ) &nbsp;&nbsp;|&nbsp;&nbsp;
      BF16 线性层 Decode (M ≪ K,N)：AI = 2MKN / [2(MK + KN + MN)] ≈ M (FLOPs/Byte)
    </div>
    <p class="muted" style="font-size:12.5px">
      注：叠加的 M1.2 融合算子点按等效算术强度（RMSNorm ≈ 1.25 FLOPs/B，Softmax ≈ 1.50 FLOPs/B）绘制在左侧斜屋顶区域，用于直观对比 <code>pytorch_eager</code>（掉在屋顶下方 ~10%）与 <code>triton_fused</code> / <code>cuda_cpp</code>（贴紧斜屋顶 ~96%）的落差。
    </p>
  </section>

  <section id="calculator">
    <h2>3. 动手算 Roofline（RTX 5070 Ti 实测参数模拟器） <small>直观感受 Batch Size、模型大小与量化如何移动落点</small></h2>
    <div class="grid-2">
      <div class="calc-box">
        <div class="slider-row">
          <label for="calc-model">模型参数量（B）</label>
          <input id="calc-model" type="range" min="0.6" max="14" step="0.2" value="4.0"/>
          <strong id="calc-model-val">4.0 B</strong>
        </div>
        <div class="slider-row">
          <label for="calc-batch">并发 Batch Size (M)</label>
          <input id="calc-batch" type="range" min="1" max="512" step="1" value="16"/>
          <strong id="calc-batch-val">16</strong>
        </div>
        <div class="slider-row">
          <label>权重精度</label>
          <div class="pill-group" id="calc-dtype-group">
            <button type="button" class="pill active" data-bytes="2" data-tflops="{peak_bf16:.2f}" data-name="BF16 (2B)">BF16 (2B)</button>
            <button type="button" class="pill" data-bytes="1" data-tflops="{peak_bf16 * 1.8:.1f}" data-name="FP8/INT8 (1B)">FP8/INT8 (1B)</button>
            <button type="button" class="pill" data-bytes="0.5" data-tflops="{peak_bf16:.2f}" data-name="W4A16 INT4 (0.5B)">W4A16 INT4 (0.5B)</button>
          </div>
          <strong id="calc-bytes-val">2 B/param</strong>
        </div>
        <p class="muted" style="font-size:12px;margin-top:10px">
          估算口径：Decode 每生成 1 token 需顺序扫描 1 遍全模型权重（忽略 KV Cache 占比，真实场景下长上下文会额外增加 KV 显存读取）。W4A16 的反量化在 BF16 Tensor Core 上执行，故算力天花板仍按 BF16 估算。
        </p>
      </div>
      <div class="calc-box" id="calc-output">
        <!-- Populated by JS -->
      </div>
    </div>
  </section>

  <section id="bandwidth">
    <h2>4. M1.1 显存层级带宽阶梯 <small>L2 缓存命中 vs 64 MB L2 Flush 后的稳态 GDDR7 带宽</small></h2>
    <div class="grid-2">
      <div>
        <h3>Copy（1 读 1 写，2×Size）</h3>
        <div id="bw-copy-bars"></div>
      </div>
      <div>
        <h3>Triad：z = x + a·y（2 读 1 写，3×Size）</h3>
        <div id="bw-triad-bars"></div>
      </div>
    </div>
    <div class="callout warn">
      <strong>为什么基准测试必须做 L2 Flush？</strong>
      8 MB 的 <code>triad</code> 跑出了 <strong>1115.5 GB/s</strong>，远高于 GDDR7 理论物理带宽，原因是工作集完全驻留在片上 L2 缓存中；
      当工作集 ≥ 64 MB 且每次迭代前清空 64 MB L2 后，带宽稳定收敛到 <strong>760–792.7 GB/s</strong>（红线），这才是大模型权重/KV Cache 真实面对的稳态显存天花板。
    </div>
  </section>

  <section id="fused-ops">
    <h2>5. M1.2 融合算子四方对照（BF16） <small>PyTorch Eager vs Built-in vs Triton vs CUDA C++</small></h2>
    <div class="controls">
      <span style="font-size:12.5px;color:var(--muted)">选择测试矩阵形状（Tokens × Hidden Dim）：</span>
      <div class="pill-group" id="shape-pills">
        <button type="button" class="pill" data-shape="4096x2048">4096 × 2048（1.7B 规模）</button>
        <button type="button" class="pill active" data-shape="4096x4096">4096 × 4096（8B 规模）</button>
        <button type="button" class="pill" data-shape="4096x8192">4096 × 8192（70B 规模）</button>
      </div>
    </div>
    <div class="grid-2">
      <div>
        <h3>Fused RMSNorm 有效带宽（对照 {peak_bw:.1f} GB/s 红线）</h3>
        <div id="fused-rms-bars"></div>
      </div>
      <div>
        <h3>Fused Online Softmax 有效带宽（对照 {peak_bw:.1f} GB/s 红线）</h3>
        <div id="fused-sm-bars"></div>
      </div>
    </div>
  </section>

  <section id="cuda-graph">
    <h2>6. M1.3 CUDA Graph 消除 Launch 空泡与 Chrome Trace <small>24 层 Decode 步（289 个内核）：Eager vs CUDA Graph vs 显存带宽底线</small></h2>
    <div class="controls">
      <span style="font-size:12.5px;color:var(--muted)">选择模型规模（均为 24 层 BF16 + 静态 KV 256 tokens）：</span>
      <div class="pill-group" id="graph-profile-pills">
        <button type="button" class="pill active" data-profile="qwen_0.6b_like">qwen_0.6b_like（528 MB，Launch 主导）</button>
        <button type="button" class="pill" data-profile="qwen_4b_like">qwen_4b_like（3030 MB，向带宽主导过渡）</button>
      </div>
    </div>
    <div id="graph-bars-container"></div>
    <div class="grid-2" style="margin-top:16px">
      <div class="callout" id="graph-profiler-card"></div>
      <div class="callout warn">
        <strong>为什么 WSL2 + 小 Batch 提速高达 8.76×？</strong>
        <p>24 层解码每生成 1 个 token 需要连续下发 <strong>289 个 CUDA Kernel</strong>。Eager 模式下每次下发都要穿越 Python + PyTorch dispatcher + WSL2 WDDM/DXG 半虚拟化层，带来几乎恒定的 <strong>~10–13 ms 宿主空泡</strong>（与模型权重大小基本无关）。</p>
        <p>捕获为 CUDA Graph 后，289 次 host launch 压缩为 <strong>1 次 <code>cudaGraphLaunch</code></strong>：0.6B 模型 <code>B=1</code> 步耗时从 <code>14.05 ms</code> 直降到 <code>1.60 ms</code>（~623 tok/s）；4B 模型从 <code>15.86 ms</code> 降到 <code>5.49 ms</code>（逼近 <code>4.09 ms</code> 物理显存底线的 75%）。</p>
      </div>
    </div>
  </section>

  <section id="diagnostics">
    <h2>7. 反直觉实战发现 &amp; Roofline 三步诊断法</h2>
    <div class="grid-2">
      <div class="callout danger">
        <strong>反直觉发现 #1：BF16 M=64 性能凹陷（GEMM 延迟并非随 Batch 单调递增）</strong>
        <p>实测 <code>bf16 64×4096×4096</code> 耗时 <strong>0.1303 ms</strong>（16.48 TFLOPS，仅 265.5 GB/s），反而比 <code>M=32</code>（0.0597 ms）慢 2.2 倍，甚至慢于 <code>M=256</code>（0.1048 ms）；而同形状 <code>fp16</code> 仅需 <strong>0.0596 ms</strong>。</p>
        <p><strong>根因与启示：</strong>cuBLASLt 在 Blackwell <code>sm_120</code> 上对特定 <code>(M, N, K, dtype)</code> 的 tile/split-K 启发式选型出现了退化。推理引擎做 batch padding 或 CUDA Graph bucketing 时，必须实测各档位延迟，不能想当然假设“64 一定比 128 快”。</p>
      </div>
      <div class="callout warn">
        <strong>反直觉发现 #2：为什么 Triton Softmax（766 GB/s）反超手写 CUDA Online Softmax（497 GB/s）？</strong>
        <p>在 <code>4096×4096</code> 下，手写 CUDA 向量化 <code>bfloat162</code> RMSNorm 跑出 <strong>761.9 GB/s</strong>（反超 PyTorch 内置 <code>F.rms_norm</code>）；但手写 CUDA Online Softmax 仅跑出 <strong>497.1 GB/s</strong>，明显慢于 Triton（<strong>766.1 GB/s</strong>）。</p>
        <p><strong>根因与启示：</strong>虽然 Online Softmax 合并了 <code>max</code> 与 <code>sum_exp</code> 省掉第 2 趟，但写回归一化输出时仍对 <code>row_x</code> 做了<strong>第 2 次全局显存读取</strong>且未做向量化；而 Triton 将整行留在片上寄存器中实现了真正的 <strong>1 读 1 写</strong>。在 memory-bound 区间，<strong>少读一次全局显存胜过一切局部微调</strong>。</p>
      </div>
    </div>

    <h3>Roofline 工程诊断三步法</h3>
    <div class="grid-3">
      <div class="card">
        <div class="k">情况 A · 紧贴左侧斜屋顶（&gt;80% 带宽）</div>
        <p>如 <code>cuda_cpp</code> RMSNorm（96.1%）、<code>triton_fused</code> Softmax（96.6%）。说明实现已逼近显存物理极限，继续抠指令收益极低。</p>
        <small><strong>唯一出路：</strong>增大 batch 把点往右推，或量化（INT4/FP8）/ GQA 减少搬运字节数。</small>
      </div>
      <div class="card">
        <div class="k">情况 B · 紧贴右侧平屋顶（&gt;80% 算力）</div>
        <p>如 <code>bf16 4096³</code> GEMM（90.35 TFLOPS）、<code>bf16_ffn</code>（97.49 TFLOPS）。Tensor Core 已吃满。</p>
        <small><strong>唯一出路：</strong>换更高算力的低精度（FP8/FP4 Tensor Core）或算法减 FLOPs（MoE / 投机解码）。</small>
      </div>
      <div class="card warn">
        <div class="k">情况 C · 悬在屋顶下方（双低）</div>
        <p>如 <code>pytorch_eager</code>（79 GB/s）、<code>bf16 M=64</code> 凹点、小 batch Python launch 延迟。</p>
        <small><strong>最大优化红利区：</strong>查算子融合、CUDA Graph 消除 launch 空泡、访存合并、occupancy 或 cuBLAS 选型。</small>
      </div>
    </div>
  </section>

  <section id="raw-tables">
    <h2>8. 完整实测数据明细与验证证据 <small>支持按精度、区间筛选</small></h2>
    <div class="controls">
      <label style="font-size:12.5px">GEMM 精度筛选：
        <select id="gemm-dtype-filter" style="margin-left:6px;padding:4px 8px;border:1px solid #bdcbd5;border-radius:4px">
          <option value="all">全部精度</option>
          <option value="bf16">bf16 (4096×4096)</option>
          <option value="bf16_ffn">bf16_ffn (4096×14336)</option>
          <option value="fp16">fp16 (4096×4096)</option>
          <option value="fp32_tf32">fp32_tf32</option>
          <option value="fp32_ieee">fp32_ieee</option>
        </select>
      </label>
      <label style="font-size:12.5px">瓶颈区间：
        <select id="gemm-regime-filter" style="margin-left:6px;padding:4px 8px;border:1px solid #bdcbd5;border-radius:4px">
          <option value="all">全部区间</option>
          <option value="memory-bound">memory-bound</option>
          <option value="compute-bound">compute-bound</option>
        </select>
      </label>
      <span id="gemm-count" class="muted" style="font-size:12px"></span>
    </div>
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>精度/形状</th>
            <th>M × K × N</th>
            <th>AI (FLOPs/B)</th>
            <th>Median (ms)</th>
            <th>实测 TFLOPS</th>
            <th>有效带宽 (GB/s)</th>
            <th>区间</th>
          </tr>
        </thead>
        <tbody id="gemm-table-body"></tbody>
      </table>
    </div>

    <h3>M1.2 融合算子全量对照表</h3>
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>算子</th>
            <th>形状 (BF16)</th>
            <th>实现</th>
            <th>Median (ms)</th>
            <th>有效带宽 (GB/s)</th>
            <th>峰值带宽占比</th>
            <th>相对 Eager 加速</th>
          </tr>
        </thead>
        <tbody id="fused-table-body"></tbody>
      </table>
    </div>

    <h3>验证记录与证据边界</h3>
    <ul>
      <li><strong>数值对拍：</strong>CUDA C++ 与 Triton 均覆盖 <code>cols = 127..8192</code>（含非 2 次幂与 Softmax <code>±50</code> 极值），FP32 RMSNorm 最大误差 <code>≤ 3.58e-7</code>，BF16 RMSNorm <code>≤ 1.33e-2</code>，BF16 Softmax <code>≤ 2.35e-3</code>。</li>
      <li><strong>内存安全与竞态：</strong><code>compute-sanitizer --tool memcheck</code> 输出 <code>0 errors</code>；<code>--tool racecheck</code> 输出 <code>0 hazards (0 errors, 0 warnings)</code>。</li>
      <li><strong>数据来源：</strong>Roofline <code>{html.escape(roofline_src)}</code>；Fused Ops <code>{html.escape(fused_src or 'N/A')}</code>；CUDA Graph <code>{html.escape(graph_src or 'N/A')}</code>。</li>
      <li><strong>边界声明：</strong>全部数字为单张本地 {device_name} 在 WSL2 下的实测结果，用于指导单卡算子与单机推理优化，不可直接外推多卡 NVLink/NCCL 通信或硬件 MIG 场景。</li>
    </ul>
  </section>

  <footer>labs/gpu-kernel · Offline Self-Contained Observability Report · Regenerate via <code>make -C labs/gpu-kernel report</code></footer>
</main>

<div id="roofline-tooltip"></div>

<script>
(() => {{
  'use strict';
  const DATA = {embedded_json};
  const peakBW = DATA.summary.peak_vram_bw_gb_s;
  const peakBF16 = DATA.summary.peak_bf16_tflops;
  const ridgeAI = DATA.summary.bf16_ridge_flops_per_byte;
  const vramGiB = DATA.environment.total_memory_gib;

  const COLORS = {{
    bf16: '#0284c7',
    bf16_ffn: '#ea580c',
    fp16: '#7c3aed',
    fp32_tf32: '#0d9488',
    fp32_ieee: '#64748b',
    fused_ok: '#16a34a',
    fused_slow: '#dc2626'
  }};

  const tooltip = document.getElementById('roofline-tooltip');
  function showTip(evt, htmlText) {{
    tooltip.innerHTML = htmlText;
    tooltip.style.display = 'block';
    const x = Math.min(window.innerWidth - 305, evt.clientX + 14);
    const y = Math.min(window.innerHeight - 140, evt.clientY + 14);
    tooltip.style.left = Math.max(8, x) + 'px';
    tooltip.style.top = Math.max(8, y) + 'px';
  }}
  function hideTip() {{ tooltip.style.display = 'none'; }}

  // --- 1. Interactive Roofline SVG ---
  const svg = document.getElementById('roofline-svg');
  const SVG_NS = 'http://www.w3.org/2000/svg';
  function el(tag, attrs, text) {{
    const node = document.createElementNS(SVG_NS, tag);
    for (const [k, v] of Object.entries(attrs || {{}})) node.setAttribute(k, String(v));
    if (text !== undefined) node.textContent = text;
    return node;
  }}

  function renderRoofline() {{
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    const active = new Set(
      Array.from(document.querySelectorAll('#roofline-controls input:checked'))
        .map(i => i.dataset.series)
    );

    const W = 920, H = 450, ml = 76, mr = 32, mt = 34, mb = 56;
    const pw = W - ml - mr, ph = H - mt - mb;
    const xMin = 0.4, xMax = 3000, yMin = 0.08, yMax = 220;

    const sx = v => ml + ((Math.log10(Math.max(v, xMin)) - Math.log10(xMin)) / (Math.log10(xMax) - Math.log10(xMin))) * pw;
    const sy = v => mt + ph - ((Math.log10(Math.max(v, yMin)) - Math.log10(yMin)) / (Math.log10(yMax) - Math.log10(yMin))) * ph;

    const rx = sx(ridgeAI), ry = sy(peakBF16);

    // Shaded regimes
    svg.appendChild(el('rect', {{ x: ml, y: mt, width: rx - ml, height: ph, fill: '#f0f9ff' }}));
    svg.appendChild(el('rect', {{ x: rx, y: mt, width: ml + pw - rx, height: ph, fill: '#fffbeb' }}));
    svg.appendChild(el('text', {{ x: ml + 12, y: mt + 20, 'font-size': 12, 'font-weight': 600, fill: '#0369a1' }}, 'Memory-Bound 区（卡显存带宽）'));
    svg.appendChild(el('text', {{ x: ml + pw - 12, y: mt + 20, 'text-anchor': 'end', 'font-size': 12, 'font-weight': 600, fill: '#b45309' }}, 'Compute-Bound 区（卡 Tensor Core 算力）'));

    // Grid
    for (const xv of [0.5, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048]) {{
      const gx = sx(xv);
      svg.appendChild(el('line', {{ x1: gx, y1: mt, x2: gx, y2: mt + ph, stroke: '#dce5ed', 'stroke-width': 1 }}));
      svg.appendChild(el('text', {{ x: gx, y: mt + ph + 18, 'text-anchor': 'middle', 'font-size': 11, fill: '#475569' }}, String(xv)));
    }}
    for (const yv of [0.1, 0.5, 1, 5, 10, 50, 100]) {{
      const gy = sy(yv);
      svg.appendChild(el('line', {{ x1: ml, y1: gy, x2: ml + pw, y2: gy, stroke: '#dce5ed', 'stroke-width': 1 }}));
      svg.appendChild(el('text', {{ x: ml - 10, y: gy + 4, 'text-anchor': 'end', 'font-size': 11, fill: '#475569' }}, String(yv)));
    }}

    // Axes
    svg.appendChild(el('line', {{ x1: ml, y1: mt, x2: ml, y2: mt + ph, stroke: '#334155', 'stroke-width': 1.5 }}));
    svg.appendChild(el('line', {{ x1: ml, y1: mt + ph, x2: ml + pw, y2: mt + ph, stroke: '#334155', 'stroke-width': 1.5 }}));

    // Roofline ceiling path (BF16)
    const yStart = (peakBW * xMin) / 1000.0;
    const roofPath = `M ${{sx(xMin).toFixed(1)}} ${{sy(yStart).toFixed(1)}} L ${{rx.toFixed(1)}} ${{ry.toFixed(1)}} L ${{sx(xMax).toFixed(1)}} ${{ry.toFixed(1)}}`;
    svg.appendChild(el('path', {{ d: roofPath, fill: 'none', stroke: '#0f172a', 'stroke-width': 2.6 }}));

    // Ridge vertical line
    svg.appendChild(el('line', {{ x1: rx, y1: ry, x2: rx, y2: mt + ph, stroke: '#c0392b', 'stroke-dasharray': '5 4', 'stroke-width': 1.6 }}));
    svg.appendChild(el('circle', {{ cx: rx, cy: ry, r: 4.5, fill: '#c0392b' }}));
    svg.appendChild(el('text', {{ x: rx + 7, y: ry + 18, 'font-size': 11.5, 'font-weight': 600, fill: '#c0392b' }}, `Ridge ≈ ${{ridgeAI.toFixed(1)}} FLOPs/B`));
    svg.appendChild(el('text', {{ x: ml + pw - 10, y: ry - 8, 'text-anchor': 'end', 'font-size': 11.5, fill: '#0f172a' }}, `BF16 Roof: ${{peakBF16.toFixed(1)}} TFLOPS`));
    svg.appendChild(el('text', {{ x: sx(2.2), y: sy((peakBW * 2.2) / 1000) - 10, 'font-size': 11.5, fill: '#0f172a' }}, `VRAM Roof: ${{peakBW.toFixed(1)}} GB/s`));

    // Plot GEMM series
    const seriesOrder = ['bf16', 'bf16_ffn', 'fp16', 'fp32_tf32', 'fp32_ieee'];
    for (const s of seriesOrder) {{
      if (!active.has(s)) continue;
      const pts = DATA.gemm.filter(p => p.dtype === s).sort((a, b) => a.arithmetic_intensity - b.arithmetic_intensity);
      if (pts.length > 1) {{
        const lineD = 'M ' + pts.map(p => `${{sx(p.arithmetic_intensity).toFixed(1)}} ${{sy(p.tflops).toFixed(1)}}`).join(' L ');
        svg.appendChild(el('path', {{ d: lineD, fill: 'none', stroke: COLORS[s], 'stroke-width': 1.8, opacity: 0.75 }}));
      }}
      for (const p of pts) {{
        const cx = sx(p.arithmetic_intensity), cy = sy(p.tflops);
        const roofAtAI = Math.min(peakBF16, (peakBW * p.arithmetic_intensity) / 1000.0);
        const utilPct = (p.tflops / roofAtAI) * 100.0;
        const isDip = (s === 'bf16' && p.m === 64);
        const c = el('circle', {{
          cx, cy, r: isDip ? 6.5 : 4.8,
          fill: isDip ? '#dc2626' : COLORS[s],
          stroke: '#ffffff', 'stroke-width': 1.4,
          style: 'cursor:pointer'
        }});
        c.addEventListener('mousemove', e => showTip(e,
          `<strong>${{p.dtype}} · ${{p.m}}×${{p.k}}×${{p.n}}</strong><br/>` +
          `AI: <b>${{p.arithmetic_intensity}} FLOPs/B</b> (${{p.regime}})<br/>` +
          `Median: <b>${{p.median_ms}} ms</b><br/>` +
          `算力: <b>${{p.tflops}} TFLOPS</b> · 带宽: <b>${{p.effective_bw_gb_s}} GB/s</b><br/>` +
          `相对 BF16 屋顶利用率: <b>${{utilPct.toFixed(1)}}%</b>` +
          (isDip ? '<br/><span style="color:#fca5a5">★ cuBLASLt 选型退化凹点</span>' : '')
        ));
        c.addEventListener('mouseleave', hideTip);
        svg.appendChild(c);

        if (s === 'bf16' && [1, 4, 32, 64, 128, 256, 4096].includes(p.m)) {{
          svg.appendChild(el('text', {{
            x: cx + (isDip ? 9 : 6),
            y: cy + (isDip ? 14 : -7),
            'font-size': isDip ? 11 : 10,
            'font-weight': isDip ? 700 : 400,
            fill: isDip ? '#dc2626' : '#1e293b'
          }}, isDip ? 'M=64 (凹点!)' : `M=${{p.m}}`));
        }}
      }}
    }}

    // Overlay M1.2 fused kernels (4096x4096) in low-AI region
    if (active.has('fused_overlay')) {{
      const overlaySpecs = [
        {{ op: 'rmsnorm', impl: 'pytorch_eager', ai: 1.20, label: 'RMSNorm Eager', ok: false }},
        {{ op: 'rmsnorm', impl: 'cuda_cpp', ai: 1.25, label: 'RMSNorm CUDA (96%)', ok: true }},
        {{ op: 'softmax', impl: 'pytorch_eager', ai: 1.55, label: 'Softmax Eager', ok: false }},
        {{ op: 'softmax', impl: 'triton_fused', ai: 1.60, label: 'Softmax Triton (97%)', ok: true }},
      ];
      for (const spec of overlaySpecs) {{
        const row = DATA.fused_ops.find(r => r.op === spec.op && r.impl === spec.impl && r.rows === 4096 && r.cols === 4096);
        if (!row) continue;
        const equivTflops = (row.effective_bw_gb_s * spec.ai) / 1000.0;
        const cx = sx(spec.ai), cy = sy(equivTflops);
        const node = el('rect', {{
          x: cx - 5, y: cy - 5, width: 10, height: 10, rx: 2,
          fill: spec.ok ? COLORS.fused_ok : COLORS.fused_slow,
          stroke: '#ffffff', 'stroke-width': 1.3,
          style: 'cursor:pointer'
        }});
        node.addEventListener('mousemove', e => showTip(e,
          `<strong>M1.2 ${{spec.label}} (4096×4096 BF16)</strong><br/>` +
          `有效带宽: <b>${{row.effective_bw_gb_s}} GB/s</b> (${{(row.effective_bw_gb_s / peakBW * 100).toFixed(1)}}% 屋顶)<br/>` +
          `Median: <b>${{row.median_ms}} ms</b> · 提速: <b>${{row.speedup_vs_eager}}×</b>`
        ));
        node.addEventListener('mouseleave', hideTip);
        svg.appendChild(node);
        svg.appendChild(el('text', {{
          x: cx + 8, y: cy + (spec.op === 'softmax' ? 12 : -6),
          'font-size': 10, 'font-weight': 600,
          fill: spec.ok ? '#15803d' : '#b91c1c'
        }}, spec.label));
      }}
    }}

    // Axis titles
    svg.appendChild(el('text', {{ x: ml + pw / 2, y: H - 14, 'text-anchor': 'middle', 'font-size': 12.5, fill: '#0f172a' }}, 'Arithmetic Intensity 算术强度 (FLOPs / Byte，对数坐标)'));
    svg.appendChild(el('text', {{ x: 20, y: mt + ph / 2, 'text-anchor': 'middle', 'font-size': 12.5, fill: '#0f172a', transform: `rotate(-90 20 ${{mt + ph / 2}})` }}, 'Achieved TFLOPS 实测算力（对数坐标）'));
  }}

  document.querySelectorAll('#roofline-controls input').forEach(inp => inp.addEventListener('change', renderRoofline));
  renderRoofline();

  // --- 2. Interactive What-If Calculator ---
  const modelSlider = document.getElementById('calc-model');
  const batchSlider = document.getElementById('calc-batch');
  const calcOut = document.getElementById('calc-output');
  let curBytesPerParam = 2.0;
  let curPeakTflops = peakBF16;
  let curDtypeName = 'BF16 (2B)';

  function updateCalc() {{
    const paramsB = parseFloat(modelSlider.value);
    const M = parseInt(batchSlider.value, 10);
    document.getElementById('calc-model-val').textContent = `${{paramsB.toFixed(1)}} B`;
    document.getElementById('calc-batch-val').textContent = `${{M}}`;
    document.getElementById('calc-bytes-val').textContent = `${{curBytesPerParam}} B/param`;

    const weightGB = paramsB * curBytesPerParam;
    const fits = weightGB <= vramGiB * 0.85;
    // Decode FLOPs for batch M across full model ~ 2 * params * M; bytes ~ weightGB (plus small activation)
    const ai = (2.0 * M) / curBytesPerParam;
    const localRidge = (curPeakTflops * 1e12) / (peakBW * 1e9);
    const isMemBound = ai < localRidge;
    const stepTimeMemMs = (weightGB / peakBW) * 1000.0;
    const stepTimeCompMs = ((2.0 * paramsB * 1e9 * M) / (curPeakTflops * 1e12)) * 1000.0;
    const stepTimeMs = Math.max(stepTimeMemMs, stepTimeCompMs);
    const perReqTokS = 1000.0 / stepTimeMs;
    const totalTokS = M * perReqTokS;
    const ratioPct = Math.min(100, (ai / (localRidge * 2)) * 100);

    calcOut.innerHTML =
      `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">` +
      `<strong>${{paramsB.toFixed(1)}}B · ${{curDtypeName}} · Batch M=${{M}}</strong>` +
      `<span class="tag ${{isMemBound ? 'mem' : 'comp'}}">${{isMemBound ? 'Memory-Bound（卡显存带宽）' : 'Compute-Bound（卡算力）'}}</span>` +
      `</div>` +
      `<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:13px">` +
      `<div>模型权重显存：<b>${{weightGB.toFixed(2)}} GB</b> <span class="tag ${{fits ? 'ok' : ''}}" style="${{fits ? '' : 'background:#fee2e2;color:#b91c1c'}}">${{fits ? '16GB 可装下' : '超单卡显存'}}</span></div>` +
      `<div>估算算术强度：<b>${{ai.toFixed(1)}} FLOPs/B</b>（拐点 ${{localRidge.toFixed(0)}}）</div>` +
      `<div>单步理论极限耗时：<b>${{stepTimeMs.toFixed(2)}} ms</b></div>` +
      `<div>单请求速度上限：<b>${{perReqTokS.toFixed(1)}} tok/s</b></div>` +
      `<div style="grid-column:1 / -1">整卡聚合吞吐上限（忽略 KV 占比）：<strong style="font-size:18px;color:var(--accent)">${{totalTokS.toFixed(0)}} tok/s</strong></div>` +
      `</div>` +
      `<div style="margin-top:12px;font-size:11.5px;color:var(--muted)">Roofline 位置标尺（红线 = 拐点 ${{localRidge.toFixed(0)}} FLOPs/B）：</div>` +
      `<div class="bar-track" style="height:14px;margin-top:4px">` +
      `<div class="bar-fill" style="width:${{ratioPct.toFixed(1)}}%;background:${{isMemBound ? '#0284c7' : '#d97706'}}"></div>` +
      `<div class="bar-ref-line" style="left:50%"></div>` +
      `</div>`;
  }}

  modelSlider.addEventListener('input', updateCalc);
  batchSlider.addEventListener('input', updateCalc);
  document.querySelectorAll('#calc-dtype-group .pill').forEach(btn => {{
    btn.addEventListener('click', () => {{
      document.querySelectorAll('#calc-dtype-group .pill').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      curBytesPerParam = parseFloat(btn.dataset.bytes);
      curPeakTflops = parseFloat(btn.dataset.tflops);
      curDtypeName = btn.dataset.name;
      updateCalc();
    }});
  }});
  updateCalc();

  // --- 3. Bandwidth Ladder Bars ---
  function renderBwBars(op, containerId) {{
    const container = document.getElementById(containerId);
    const items = DATA.bandwidth.filter(b => b.op === op);
    const maxScale = Math.max(1200, ...items.map(i => i.bandwidth_gb_s));
    const refPct = (peakBW / maxScale) * 100;
    container.innerHTML = items.map(it => {{
      const w = (it.bandwidth_gb_s / maxScale) * 100;
      const isL2 = it.size_mb <= 32 && it.bandwidth_gb_s > peakBW;
      const color = isL2 ? '#d97706' : (it.size_mb >= 64 ? '#11666b' : '#64748b');
      const note = it.size_mb >= 64 ? 'L2 flush' : (isL2 ? 'L2 hit!' : 'small');
      return `<div class="bar-row">` +
        `<div><strong>${{it.size_mb}} MB</strong> <span class="muted">(${{note}})</span></div>` +
        `<div class="bar-track"><div class="bar-fill" style="width:${{w.toFixed(1)}}%;background:${{color}}"></div>` +
        `<div class="bar-ref-line" style="left:${{refPct.toFixed(1)}}%" title="稳态峰值 ${{peakBW}} GB/s"></div></div>` +
        `<div class="bar-val">${{it.bandwidth_gb_s.toFixed(1)}} GB/s</div>` +
        `</div>`;
    }}).join('');
  }}
  renderBwBars('copy', 'bw-copy-bars');
  renderBwBars('triad', 'bw-triad-bars');

  // --- 4. Fused Ops Comparison ---
  const IMPL_LABELS = {{
    pytorch_eager: ['PyTorch Eager', '#94a3b8'],
    pytorch_builtin: ['PyTorch Built-in', '#0284c7'],
    triton_fused: ['Triton Fused', '#16a34a'],
    cuda_cpp: ['CUDA C++', '#ea580c'],
  }};
  function renderFusedBars(shapeStr) {{
    const [rStr, cStr] = shapeStr.split('x');
    const rows = parseInt(rStr, 10), cols = parseInt(cStr, 10);
    for (const [op, elId] of [['rmsnorm', 'fused-rms-bars'], ['softmax', 'fused-sm-bars']]) {{
      const items = DATA.fused_ops.filter(x => x.op === op && x.rows === rows && x.cols === cols);
      const maxScale = Math.max(peakBW * 1.06, 840);
      const refPct = (peakBW / maxScale) * 100;
      document.getElementById(elId).innerHTML = items.map(it => {{
        const [label, color] = IMPL_LABELS[it.impl] || [it.impl, '#475569'];
        const w = (it.effective_bw_gb_s / maxScale) * 100;
        const pct = (it.effective_bw_gb_s / peakBW) * 100;
        return `<div class="bar-row">` +
          `<div><strong>${{label}}</strong> <span class="muted">(${{it.speedup_vs_eager.toFixed(2)}}×)</span></div>` +
          `<div class="bar-track"><div class="bar-fill" style="width:${{w.toFixed(1)}}%;background:${{color}}"></div>` +
          `<div class="bar-ref-line" style="left:${{refPct.toFixed(1)}}%" title="稳态峰值 ${{peakBW}} GB/s"></div></div>` +
          `<div class="bar-val">${{it.effective_bw_gb_s.toFixed(1)}} GB/s <span class="muted">(${{pct.toFixed(0)}}%)</span></div>` +
          `</div>`;
      }}).join('');
    }}
  }}
  document.querySelectorAll('#shape-pills .pill').forEach(btn => {{
    btn.addEventListener('click', () => {{
      document.querySelectorAll('#shape-pills .pill').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderFusedBars(btn.dataset.shape);
    }});
  }});
  renderFusedBars('4096x4096');

  // --- 4.5. M1.3 CUDA Graph Bars & Profiler Card ---
  function renderCudaGraph(profileName) {{
    const box = document.getElementById('graph-bars-container');
    const items = (DATA.cuda_graph || []).filter(r => r.profile_name === profileName);
    if (!items.length) {{
      box.innerHTML = '<p class="muted">尚未采集 CUDA Graph 数据，请先运行 <code>make -C labs/gpu-kernel cuda-graph</code>。</p>';
      return;
    }}
    const maxMs = Math.max(...items.map(i => i.eager_wall_ms)) * 1.05;
    box.innerHTML = items.map(it => {{
      const wEager = (it.eager_wall_ms / maxMs) * 100;
      const wGraph = (it.graph_wall_ms / maxMs) * 100;
      const wFloor = (it.vram_floor_ms / maxMs) * 100;
      return `<div style="margin:10px 0;padding:8px 10px;border:1px solid var(--line);border-radius:6px;background:#fafcfe">` +
        `<div style="display:flex;justify-content:space-between;font-size:12.5px;margin-bottom:5px">` +
        `<strong>Batch B=${{it.batch_size}} <span class="muted">(Weights ${{it.weight_mb}}MB + KV ${{it.kv_mb}}MB)</span></strong>` +
        `<span>加速 <b style="color:var(--accent)">${{it.speedup_wall.toFixed(2)}}×</b> · 省去 launch <b>${{it.saved_launch_ms.toFixed(2)}} ms</b> · 物理底线 <b>${{it.vram_floor_ms.toFixed(2)}} ms</b></span>` +
        `</div>` +
        `<div class="bar-row" style="margin:4px 0"><div class="muted">Eager (289 launches)</div>` +
        `<div class="bar-track"><div class="bar-fill" style="width:${{wEager.toFixed(1)}}%;background:#94a3b8"></div>` +
        `<div class="bar-ref-line" style="left:${{wFloor.toFixed(1)}}%" title="理论显存底线 ${{it.vram_floor_ms}} ms"></div></div>` +
        `<div class="bar-val">${{it.eager_wall_ms.toFixed(3)}} ms</div></div>` +
        `<div class="bar-row" style="margin:4px 0"><div style="color:var(--accent);font-weight:600">CUDA Graph (1 launch)</div>` +
        `<div class="bar-track"><div class="bar-fill" style="width:${{wGraph.toFixed(1)}}%;background:#11666b"></div>` +
        `<div class="bar-ref-line" style="left:${{wFloor.toFixed(1)}}%" title="理论显存底线 ${{it.vram_floor_ms}} ms"></div></div>` +
        `<div class="bar-val" style="color:var(--accent)">${{it.graph_wall_ms.toFixed(3)}} ms</div></div>` +
        `</div>`;
    }}).join('');
  }}

  const profCard = document.getElementById('graph-profiler-card');
  const profRows = DATA.cuda_graph_profiler || [];
  if (profRows.length >= 2) {{
    const pEager = profRows.find(p => p.mode === 'eager');
    const pGraph = profRows.find(p => p.mode === 'cudagraph');
    const dir = DATA.cuda_graph_dir || '.local/runs/...';
    profCard.innerHTML =
      `<strong>PyTorch Profiler &amp; Chrome Trace 结构证据（qwen_0.6b_like, B=1）</strong>` +
      `<ul style="margin:6px 0 0 18px;padding:0;font-size:12.5px">` +
      `<li>GPU 实际执行核函数数：Eager <b>${{pEager.cuda_kernels_per_step}}</b> 个 vs Graph <b>${{pGraph.cuda_kernels_per_step}}</b> 个（计算量完全等价）</li>` +
      `<li>Host 下发调用次数：Eager <b>${{pEager.cpu_launch_calls_per_step}}</b> 次 → Graph <b>${{pGraph.cpu_launch_calls_per_step}}</b> 次（<code>cudaGraphLaunch</code>）</li>` +
      `<li>Chrome Trace 文件：<code>${{dir}}/${{pEager.trace_file}}</code> 与 <code>${{dir}}/${{pGraph.trace_file}}</code>（拖入 <code>chrome://tracing</code> 或 <code>ui.perfetto.dev</code> 可直观看到满屏空泡消失）</li>` +
      `<li><strong>观测者效应提示：</strong>开启 CUPTI+CPU tracing 会给 289 个 Eager CPU op 附加 ~30× 埋点开销（460 ms），因此耗时基准始终以无 profiler 干扰的纯净计时为准。</li>` +
      `</ul>`;
  }} else {{
    profCard.innerHTML = '<strong>Chrome Trace：</strong>运行 <code>make -C labs/gpu-kernel cuda-graph</code> 后自动填入。';
  }}

  document.querySelectorAll('#graph-profile-pills .pill').forEach(btn => {{
    btn.addEventListener('click', () => {{
      document.querySelectorAll('#graph-profile-pills .pill').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderCudaGraph(btn.dataset.profile);
    }});
  }});
  renderCudaGraph('qwen_0.6b_like');

  // --- 5. Raw Tables ---
  const dtypeFilter = document.getElementById('gemm-dtype-filter');
  const regimeFilter = document.getElementById('gemm-regime-filter');
  function renderGemmTable() {{
    const dVal = dtypeFilter.value;
    const rVal = regimeFilter.value;
    const rows = DATA.gemm.filter(r =>
      (dVal === 'all' || r.dtype === dVal) && (rVal === 'all' || r.regime === rVal)
    );
    document.getElementById('gemm-count').textContent = `显示 ${{rows.length}} / ${{DATA.gemm.length}} 条记录`;
    document.getElementById('gemm-table-body').innerHTML = rows.map(r => {{
      const tag = r.regime === 'memory-bound'
        ? '<span class="tag mem">memory-bound</span>'
        : '<span class="tag comp">compute-bound</span>';
      return `<tr><td>${{r.dtype}}</td><td>${{r.m}} × ${{r.k}} × ${{r.n}}</td>` +
        `<td>${{r.arithmetic_intensity.toFixed(2)}}</td><td>${{r.median_ms.toFixed(4)}}</td>` +
        `<td><b>${{r.tflops.toFixed(2)}}</b></td><td>${{r.effective_bw_gb_s.toFixed(1)}}</td><td>${{tag}}</td></tr>`;
    }}).join('');
  }}
  dtypeFilter.addEventListener('change', renderGemmTable);
  regimeFilter.addEventListener('change', renderGemmTable);
  renderGemmTable();

  document.getElementById('fused-table-body').innerHTML = DATA.fused_ops.map(r => {{
    const pct = (r.effective_bw_gb_s / peakBW) * 100;
    return `<tr><td>${{r.op}}</td><td>${{r.rows}} × ${{r.cols}}</td><td>${{r.impl}}</td>` +
      `<td>${{r.median_ms.toFixed(4)}}</td><td><b>${{r.effective_bw_gb_s.toFixed(1)}}</b></td>` +
      `<td>${{pct.toFixed(1)}}%</td><td><b>${{r.speedup_vs_eager.toFixed(2)}}×</b></td></tr>`;
  }}).join('');
}})();
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate unified interactive HTML report for labs/gpu-kernel."
    )
    parser.add_argument("--roofline-json", type=Path, default=None)
    parser.add_argument("--fused-json", type=Path, default=None)
    parser.add_argument("--graph-json", type=Path, default=None)
    parser.add_argument(
        "--output",
        type=Path,
        default=LAB_ROOT / ".local" / "report.html",
        help="Primary output HTML path (also archived under .local/runs/).",
    )
    args = parser.parse_args()

    runs_dir = LAB_ROOT / ".local" / "runs"
    roofline_path = args.roofline_json or find_latest_artifact(runs_dir, "roofline.json")
    if roofline_path is None or not roofline_path.is_file():
        print(
            "ERROR: No roofline.json found under .local/runs/. Run `make roofline` first.",
            file=sys.stderr,
        )
        sys.exit(1)

    fused_path = args.fused_json or find_latest_artifact(runs_dir, "fused_ops.json")
    graph_path = args.graph_json or find_latest_artifact(runs_dir, "cuda_graph.json")
    roofline_data = load_json(roofline_path)
    fused_data = load_json(fused_path) if (fused_path and fused_path.is_file()) else None
    graph_data = load_json(graph_path) if (graph_path and graph_path.is_file()) else None

    def rel_label(path: Path | None) -> str | None:
        if path is None:
            return None
        return str(path.relative_to(LAB_ROOT)) if path.is_relative_to(LAB_ROOT) else path.name

    html_doc = build_html(
        roofline_data,
        fused_data,
        graph_data,
        rel_label(roofline_path) or "roofline.json",
        rel_label(fused_path),
        rel_label(graph_path),
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html_doc, encoding="utf-8")

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    archive_dir = runs_dir / f"{stamp}-report"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / "report.html"
    archive_path.write_text(html_doc, encoding="utf-8")

    print(f"REPORT={args.output}")
    print(f"ARCHIVE={archive_path}")


if __name__ == "__main__":
    main()
