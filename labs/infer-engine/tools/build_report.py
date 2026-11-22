"""Build unified offline HTML observability report for labs/infer-engine (M2.1 - M2.4)."""

from __future__ import annotations

import datetime as dt
import html
import json
from pathlib import Path
import sys

LAB_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    runs_dir = LAB_ROOT / ".local" / "runs"
    matches = sorted(runs_dir.glob("*/infer_engine.json")) if runs_dir.is_dir() else []
    if not matches:
        print("ERROR: No infer_engine.json found. Run `make bench` first.", file=sys.stderr)
        sys.exit(1)

    src = matches[-1]
    data = json.loads(src.read_text(encoding="utf-8"))
    env = data["environment"]
    m21 = data["m21_concat_vs_static"]
    m22 = data["m22_fragmentation"]
    m23a = data["m23a_chunked_prefill"]
    m23b = data["m23b_preemption"]
    m24a = data["m24a_prefix_cache"]
    m24b = data["m24b_speculative"]

    built_utc = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>Mini Inference Engine Report (M2.1–M2.4) — {html.escape(env['device_name'])}</title>
<style>
:root {{ --ink:#172c40; --muted:#5e7081; --line:#dce5ed; --accent:#11666b; --paper:#f3f6fa; --header:#112f41; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--paper); color:var(--ink); font:14px/1.65 system-ui,-apple-system,"Segoe UI","PingFang SC",sans-serif; }}
header {{ padding:28px max(24px,calc((100vw - 1280px)/2)); background:var(--header); color:#f3fafc; }}
header .muted {{ color:#b8cbd4; font-size:13px; }}
main {{ max-width:1328px; margin:auto; padding:20px 24px 48px; }}
section {{ background:#fff; border:1px solid var(--line); border-radius:10px; padding:22px; margin-bottom:18px; }}
h1 {{ margin:8px 0; font-size:26px; }}
h2 {{ margin:0 0 12px; font-size:19px; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:12px; margin:12px 0; }}
.card {{ border:1px solid var(--line); border-top:3px solid var(--accent); border-radius:6px; padding:12px 14px; background:#fafcfe; }}
.card .k {{ font-size:12px; color:var(--muted); }}
.card strong {{ display:block; font-size:24px; margin-top:4px; font-variant-numeric:tabular-nums; }}
.card small {{ color:var(--muted); font-size:12px; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; font-variant-numeric:tabular-nums; margin-top:8px; }}
th,td {{ border-bottom:1px solid #e6edf3; padding:7px 10px; text-align:right; }}
th {{ background:#f3f7f9; }}
th:first-child,td:first-child {{ text-align:left; }}
.callout {{ border-left:4px solid var(--accent); background:#e6f4f4; padding:11px 14px; border-radius:4px; margin-top:12px; font-size:13px; }}
</style>
</head>
<body>
<header>
  <div style="letter-spacing:.12em;font-size:11px;color:#8ddad1">XLAB / LABS/INFER-ENGINE · PHASE 2 REPORT</div>
  <h1>单机迷你推理引擎实测报告（M2.1–M2.4）</h1>
  <div class="muted">{html.escape(env['device_name'])} (sm_{html.escape(env['compute_capability'].replace('.',''))}, {env['total_memory_gib']} GiB) · PyTorch {html.escape(env['torch_version'])} · {built_utc}</div>
</header>
<main>
  <section>
    <h2>核心指标总览</h2>
    <div class="cards">
      <div class="card"><div class="k">M2.2 Paged KV 并发提升</div><strong>{m22['concurrency_gain']}×</strong><small>碎片率 {m22['static_waste_pct']}% → {m22['paged_waste_pct']}%</small></div>
      <div class="card"><div class="k">M2.3a Chunked Prefill P99 ITL</div><strong>{m23a['chunked_64']['decode_p99_itl_ms']} ms</strong><small>未分块 {m23a['unchunked_2048']['decode_p99_itl_ms']} ms</small></div>
      <div class="card"><div class="k">M2.4a Prefix Cache (LFU)</div><strong>{m24a['lfu']['block_hit_rate_pct']}%</strong><small>扫描后热点 TTFT: {m24a['lfu']['phase3_hot_ttft_ms']} ms vs LRU {m24a['lru']['phase3_hot_ttft_ms']} ms</small></div>
      <div class="card"><div class="k">M2.4b 投机解码 (75% Accept)</div><strong>{m24b['aligned_75pct_draft']['speedup_vs_target']}×</strong><small>Target 调用 {m24b['target_only']['target_calls']} → {m24b['aligned_75pct_draft']['target_calls']} 次</small></div>
    </div>
  </section>

  <section>
    <h2>M2.1 Static KV vs Concat KV（0.6B 架构, Prompt=256, Gen=128）</h2>
    <table>
      <thead><tr><th>方案</th><th>TTFT (ms)</th><th>Median ITL (ms)</th><th>P99 ITL (ms)</th><th>总耗时 (ms)</th><th>吞吐 (tok/s)</th></tr></thead>
      <tbody>
        <tr><td>Concat KV (每步 torch.cat)</td><td>{m21['concat']['ttft_ms']}</td><td>{m21['concat']['median_itl_ms']}</td><td>{m21['concat']['p99_itl_ms']}</td><td>{m21['concat']['total_ms']}</td><td>{m21['concat']['tok_per_s']}</td></tr>
        <tr><td>Static KV (预分配定长槽位)</td><td>{m21['static']['ttft_ms']}</td><td>{m21['static']['median_itl_ms']}</td><td>{m21['static']['p99_itl_ms']}</td><td>{m21['static']['total_ms']}</td><td>{m21['static']['tok_per_s']}</td></tr>
      </tbody>
    </table>
  </section>

  <section>
    <h2>M2.2 Paged KV vs Static KV 显存碎片与并发上限（固定 8192 token 预算）</h2>
    <table>
      <thead><tr><th>方案</th><th>最大并发请求数</th><th>内部碎片浪费率</th><th>相对并发增益</th></tr></thead>
      <tbody>
        <tr><td>Static KV (按 max_len=1024 预留)</td><td>{m22['static_max_concurrent_seqs']}</td><td>{m22['static_waste_pct']}%</td><td>1.00×</td></tr>
        <tr><td>Paged KV (block_size=16 按需分配)</td><td><b>{m22['paged_max_concurrent_seqs']}</b></td><td><b>{m22['paged_waste_pct']}%</b></td><td><b>{m22['concurrency_gain']}×</b></td></tr>
      </tbody>
    </table>
  </section>

  <section>
    <h2>M2.3 Continuous Batching：Chunked Prefill 与抢占（Recompute vs CPU Swap）</h2>
    <table>
      <thead><tr><th>调度策略</th><th>Token Budget</th><th>Decode Median ITL (ms)</th><th>Decode P99 ITL (ms)</th><th>Decode Max ITL (ms)</th><th>长 Prefill TTFT (ms)</th></tr></thead>
      <tbody>
        <tr><td>未分块 Prefill</td><td>{m23a['unchunked_2048']['token_budget']}</td><td>{m23a['unchunked_2048']['decode_median_itl_ms']}</td><td>{m23a['unchunked_2048']['decode_p99_itl_ms']}</td><td>{m23a['unchunked_2048']['decode_max_itl_ms']}</td><td>{m23a['unchunked_2048']['long_prefill_ttft_ms']}</td></tr>
        <tr><td>Chunked Prefill</td><td>{m23a['chunked_64']['token_budget']}</td><td>{m23a['chunked_64']['decode_median_itl_ms']}</td><td><b>{m23a['chunked_64']['decode_p99_itl_ms']}</b></td><td><b>{m23a['chunked_64']['decode_max_itl_ms']}</b></td><td>{m23a['chunked_64']['long_prefill_ttft_ms']}</td></tr>
      </tbody>
    </table>
    <table style="margin-top:14px">
      <thead><tr><th>抢占模式（24 块紧张池）</th><th>总耗时 (ms)</th><th>抢占次数</th><th>重算 Tokens</th><th>Swap Out (ms)</th><th>Swap In (ms)</th></tr></thead>
      <tbody>
        <tr><td>Recompute</td><td>{m23b['recompute']['total_wall_ms']}</td><td>{m23b['recompute']['preemptions']}</td><td>{m23b['recompute']['recomputed_tokens']}</td><td>0.0</td><td>0.0</td></tr>
        <tr><td>CPU Swap</td><td>{m23b['swap']['total_wall_ms']}</td><td>{m23b['swap']['preemptions']}</td><td>0</td><td>{m23b['swap']['swap_out_ms']}</td><td>{m23b['swap']['swap_in_ms']}</td></tr>
      </tbody>
    </table>
  </section>

  <section>
    <h2>M2.4 Radix Prefix Cache（LRU vs LFU）与 Speculative Decoding（0.6B + 4B）</h2>
    <table>
      <thead><tr><th>前缀缓存策略（热点 + 扫描污染）</th><th>块命中率</th><th>命中 Tokens</th><th>淘汰块数</th><th>扫描后热点 TTFT (ms)</th></tr></thead>
      <tbody>
        <tr><td>无缓存</td><td>{m24a['none']['block_hit_rate_pct']}%</td><td>{m24a['none']['total_hit_tokens']}</td><td>0</td><td>{m24a['none']['phase3_hot_ttft_ms']}</td></tr>
        <tr><td>Radix Tree + LRU</td><td>{m24a['lru']['block_hit_rate_pct']}%</td><td>{m24a['lru']['total_hit_tokens']}</td><td>{m24a['lru']['evictions']}</td><td>{m24a['lru']['phase3_hot_ttft_ms']}</td></tr>
        <tr><td>Radix Tree + LFU（频率感知）</td><td><b>{m24a['lfu']['block_hit_rate_pct']}%</b></td><td><b>{m24a['lfu']['total_hit_tokens']}</b></td><td>{m24a['lfu']['evictions']}</td><td><b>{m24a['lfu']['phase3_hot_ttft_ms']}</b></td></tr>
      </tbody>
    </table>
    <table style="margin-top:14px">
      <thead><tr><th>解码方式（Target={m24b['target_weight_mb']}MB, Draft={m24b['draft_weight_mb']}MB, γ={m24b['gamma']}）</th><th>Accept Rate</th><th>Target Forward 次数</th><th>总耗时 (ms)</th><th>吞吐 (tok/s)</th><th>相对 Target 加速</th></tr></thead>
      <tbody>
        <tr><td>Target-Only 自回归</td><td>—</td><td>{m24b['target_only']['target_calls']}</td><td>{m24b['target_only']['wall_ms']}</td><td>{m24b['target_only']['tok_per_s']}</td><td>1.00×</td></tr>
        <tr><td>Speculative (未对齐随机 Draft — 退化反例)</td><td>{m24b['unaligned_0pct_draft']['accept_rate_pct']}%</td><td>{m24b['unaligned_0pct_draft']['target_calls']}</td><td>{m24b['unaligned_0pct_draft']['wall_ms']}</td><td>{m24b['unaligned_0pct_draft']['tok_per_s']}</td><td>{m24b['unaligned_0pct_draft']['speedup_vs_target']}×</td></tr>
        <tr><td>Speculative (75% 接受率对齐 Draft · 100% Parity={m24b['aligned_75pct_draft']['parity_ok']})</td><td><b>{m24b['aligned_75pct_draft']['accept_rate_pct']}%</b></td><td><b>{m24b['aligned_75pct_draft']['target_calls']}</b></td><td><b>{m24b['aligned_75pct_draft']['wall_ms']}</b></td><td><b>{m24b['aligned_75pct_draft']['tok_per_s']}</b></td><td><b>{m24b['aligned_75pct_draft']['speedup_vs_target']}×</b></td></tr>
      </tbody>
    </table>
    <div class="callout">
      <strong>边界说明：</strong>本实验采用 Qwen3 真实架构维度（GQA + RoPE + RMSNorm + SwiGLU）的确定性离线权重在单卡 RTX 5070 Ti 上实测系统机制；75% 接受率组完整执行了 24 层 0.6B GPU Draft 前向计算并仅对齐 top-1 概率以复现真实代码/数学负载的接受率区间，不代表特定开源 checkpoint 的语言质量。
    </div>
  </section>
</main>
</body>
</html>
"""
    out = LAB_ROOT / ".local" / "report.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    print(f"REPORT={out}")


if __name__ == "__main__":
    main()
