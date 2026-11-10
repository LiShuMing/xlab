"""Offline HTML review of one run; all model output is escaped."""

from __future__ import annotations

import html
import json
from pathlib import Path

from .data import read_jsonl


def chart(rows: list[dict], field: str, title: str) -> str:
    """把一个字段画成内联 SVG 折线，离线报告不依赖 JS 图表库。

    坐标是手算的：x 从 30 到 630 均分，y 把 [low, high] 压到 [150, 30]。
    span 用 `or` 兜底，防止所有点等值时除零。
    """
    values = [row[field] for row in rows if isinstance(row.get(field), (int, float))]
    if not values:
        return ""
    low, high = min(values), max(values)
    span = high - low or max(abs(high), 1)
    points = " ".join(
        f"{30 + i * 600 / max(1, len(values) - 1):.2f},{150 - (value - low) / span * 120:.2f}"
        for i, value in enumerate(values)
    )
    return (
        f"<section><h2>{html.escape(title)}</h2>"
        f"<p>min={low:.5g} · max={high:.5g} · n={len(values)}</p>"
        f'<svg viewBox="0 0 660 175" role="img" aria-label="{html.escape(title)}">'
        '<path d="M30 15 V150 H640" fill="none" stroke="#ccc"/>'
        f'<polyline points="{points}" fill="none" stroke="#176b86" stroke-width="2"/>'
        "</svg></section>"
    )


def render(run: Path) -> Path:
    """把一次 run 的 JSON/JSONL 渲成单文件 index.html。

    来自模型的文本全部过 html.escape：模型完全可能输出 <script>，
    报告要能在浏览器里安全打开。每个评测文件只展示前 30 条，
    避免大 run 生成上百 MB 的 HTML。
    """

    def read(name):
        path = run / name
        return json.loads(path.read_text()) if path.exists() else {}

    cfg, summary, status = read("config.json"), read("summary.json"), read("status.json")
    metrics = read_jsonl(run / "metrics.jsonl") if (run / "metrics.jsonl").exists() else []
    system = read_jsonl(run / "system.jsonl") if (run / "system.jsonl").exists() else []
    sections = [
        chart(metrics, field, title)
        for field, title in [
            ("loss", "Training loss"),
            ("reward_mean", "Group reward"),
            ("update_seconds", "Seconds per update"),
            ("grad_norm", "Gradient norm before clipping"),
            ("cached_full_logprob_gap_max", "Cached/full logprob maximum gap"),
        ]
    ]
    sections.extend(
        chart(system, field, title)
        for field, title in [
            ("rss_bytes", "RSS bytes"),
            ("mps_driver_bytes", "MPS driver bytes (sampled)"),
            ("swap_growth_bytes", "System swap growth bytes"),
        ]
    )
    samples = []
    paths = sorted(run.glob("eval/**/responses.jsonl"))
    if (run / "responses.jsonl").exists():
        paths.insert(0, run / "responses.jsonl")
    for path in paths:
        for row in read_jsonl(path)[:30]:
            samples.append(
                f"<details><summary>{html.escape(row.get('reason', 'sample'))} · "
                f"{html.escape(row.get('task_id', '')[:12])}</summary>"
                f"<pre>{html.escape(row.get('prompt', ''))}</pre>"
                f"<pre>{html.escape(row.get('output', ''))}</pre></details>"
            )
    body = "".join(sections)
    text = f"""<!doctype html><html lang="en"><meta charset="utf-8">
<title>Reasoning Lab experiment</title><style>
body{{font:16px system-ui;max-width:1100px;margin:40px auto;padding:0 24px;color:#18313d}}
.charts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}}
section,details{{border:1px solid #d5e0e4;border-radius:12px;padding:16px;margin:8px 0}}
svg{{width:100%}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}}
summary{{cursor:pointer}}h2{{font-size:18px}}
</style><h1>Reasoning Lab · {html.escape(cfg.get("stage", "run"))}</h1>
<p>Sampled memory and synchronized wall time. These charts do not show Metal kernel utilization.</p>
<details open><summary>Status and results</summary>
<pre>{html.escape(json.dumps({"status": status, "summary": summary}, indent=2))}</pre></details>
<div class="charts">{body}</div><details><summary>Effective configuration</summary>
<pre>{html.escape(json.dumps(cfg, indent=2))}</pre></details>
<h2>Samples (up to 30 per evaluation file)</h2>{"".join(samples)}</html>"""
    output = run / "index.html"
    output.write_text(text)
    return output
