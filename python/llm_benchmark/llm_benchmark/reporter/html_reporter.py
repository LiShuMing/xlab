"""HTML report generator — produces self-contained HTML with Chart.js visualizations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RESULT_VIS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LLM Benchmark Report — {{ dataset }} / {{ model }}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {
    --bg: #f8f9fa;
    --surface: #ffffff;
    --text: #1a1a2e;
    --text-secondary: #64748b;
    --border: #e2e8f0;
    --accent: #2563eb;
    --accent-2: #7c3aed;
    --success: #059669;
    --warning: #d97706;
    --danger: #dc2626;
    --radius: 12px;
    --shadow: 0 1px 3px rgba(0,0,0,.08), 0 1px 2px rgba(0,0,0,.06);
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0f172a;
      --surface: #1e293b;
      --text: #e2e8f0;
      --text-secondary: #94a3b8;
      --border: #334155;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    * { animation: none !important; transition: none !important; }
  }
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 24px;
  }
  .container { max-width: 960px; margin: 0 auto; }
  h1 { font-size: 1.75rem; font-weight: 700; margin-bottom: 4px; }
  .subtitle { color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 24px; }
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px;
    margin-bottom: 24px;
    box-shadow: var(--shadow);
  }
  .card h2 { font-size: 1.1rem; font-weight: 600; margin-bottom: 16px; }
  .metric-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 16px;
    margin-bottom: 8px;
  }
  .metric-item {
    text-align: center;
    padding: 16px;
    background: var(--bg);
    border-radius: 8px;
  }
  .metric-value { font-size: 2rem; font-weight: 700; color: var(--accent); }
  .metric-label { font-size: 0.8rem; color: var(--text-secondary); margin-top: 4px; }
  .chart-wrap { position: relative; max-height: 400px; }
  .chart-wrap canvas { max-height: 400px; }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
  }
  th, td {
    padding: 10px 12px;
    text-align: left;
    border-bottom: 1px solid var(--border);
  }
  th { font-weight: 600; color: var(--text-secondary); font-size: 0.8rem; text-transform: uppercase; }
  .score-bar {
    display: inline-block;
    height: 8px;
    border-radius: 4px;
    background: var(--accent);
    vertical-align: middle;
    margin-right: 8px;
  }
  .score-good { background: var(--success); }
  .score-mid { background: var(--warning); }
  .score-low { background: var(--danger); }
  footer { text-align: center; color: var(--text-secondary); font-size: 0.75rem; margin-top: 32px; }
</style>
</head>
<body>
<div class="container">
  <h1>LLM Benchmark Report</h1>
  <p class="subtitle">{{ dataset }} &middot; {{ model }} &middot; {{ timestamp }}</p>

  <div class="card">
    <h2>Overall Score</h2>
    <div class="metric-grid">
      <div class="metric-item">
        <div class="metric-value">{{ overall_pct }}</div>
        <div class="metric-label">Overall Score</div>
      </div>
      <div class="metric-item">
        <div class="metric-value">{{ std_dev }}</div>
        <div class="metric-label">Std Dev ({{ repeat }} runs)</div>
      </div>
      <div class="metric-item">
        <div class="metric-value">{{ num_samples }}</div>
        <div class="metric-label">Samples</div>
      </div>
      <div class="metric-item">
        <div class="metric-value">{{ total_tokens }}</div>
        <div class="metric-label">Total Tokens</div>
      </div>
    </div>
  </div>

  {% if has_per_repeat %}
  <div class="card">
    <h2>Run Stability</h2>
    <div class="chart-wrap">
      <canvas id="stabilityChart"></canvas>
    </div>
  </div>
  {% endif %}

  {% if has_radar %}
  <div class="card">
    <h2>Capability Radar</h2>
    <div class="chart-wrap">
      <canvas id="radarChart"></canvas>
    </div>
  </div>
  {% endif %}

  {% if has_difficulty %}
  <div class="card">
    <h2>Difficulty Breakdown</h2>
    <div class="chart-wrap">
      <canvas id="difficultyChart"></canvas>
    </div>
  </div>
  {% endif %}

  <div class="card">
    <h2>Metric Details</h2>
    <table>
      <thead>
        <tr><th>Metric</th><th>Score</th></tr>
      </thead>
      <tbody>
        {% for name, score in metric_scores.items() %}
        <tr>
          <td>{{ name }}</td>
          <td>
            <span class="score-bar {{ score_class(score) }}" style="width: {{ bar_width(score) }}px"></span>
            {{ "%.2f%%" | format(score * 100) }}
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  <footer>
    Benchmark v{{ version }} &middot; Commit {{ commit_hash }} &middot; Generated {{ timestamp }}
  </footer>
</div>

<script>
(function() {
  const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const textColor = isDark ? '#94a3b8' : '#64748b';
  const gridColor = isDark ? '#334155' : '#e2e8f0';
  Chart.defaults.color = textColor;
  Chart.defaults.borderColor = gridColor;

  {% if has_per_repeat %}
  new Chart(document.getElementById('stabilityChart'), {
    type: 'bar',
    data: {
      labels: {{ per_repeat_labels | tojson }},
      datasets: [{
        label: 'Score',
        data: {{ per_repeat_values | tojson }},
        backgroundColor: '{{ accent }}',
        borderRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { min: 0, max: 1, ticks: { callback: v => (v * 100).toFixed(0) + '%' } }
      }
    }
  });
  {% endif %}

  {% if has_radar %}
  new Chart(document.getElementById('radarChart'), {
    type: 'radar',
    data: {
      labels: {{ radar_labels | tojson }},
      datasets: [{
        label: '{{ model }}',
        data: {{ radar_values | tojson }},
        borderColor: '{{ accent }}',
        backgroundColor: '{{ accent }}33',
        pointBackgroundColor: '{{ accent }}'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: { r: { min: 0, max: 1, ticks: { callback: v => (v * 100).toFixed(0) + '%', backdropColor: 'transparent' } } }
    }
  });
  {% endif %}

  {% if has_difficulty %}
  new Chart(document.getElementById('difficultyChart'), {
    type: 'bar',
    data: {
      labels: {{ difficulty_labels | tojson }},
      datasets: [{
        label: 'Score',
        data: {{ difficulty_values | tojson }},
        backgroundColor: [
          '{{ accent }}99', '{{ accent }}bb', '{{ accent }}dd', '{{ accent }}', '{{ accent_2 }}'
        ],
        borderRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { min: 0, max: 1, ticks: { callback: v => (v * 100).toFixed(0) + '%' } } }
    }
  });
  {% endif %}
})();
</script>
</body>
</html>"""


def _score_class(score: float) -> str:
    if score >= 0.8:
        return "score-good"
    if score >= 0.5:
        return "score-mid"
    return "score-low"


def _bar_width(score: float, max_width: int = 120) -> int:
    return max(4, int(score * max_width))


def generate_html_report(result: dict[str, Any]) -> str:
    """Generate a self-contained HTML report from benchmark result JSON.

    Args:
        result: The benchmark result dict (from build_result_json or loaded from file).

    Returns:
        Complete HTML string ready to write to a file.
    """
    from jinja2 import Template

    meta = result["meta"]
    results = result["results"]

    template = Template(RESULT_VIS_HTML)
    return template.render(
        dataset=meta["dataset"],
        model=meta["model"],
        timestamp=meta["timestamp"],
        version=meta["benchmark_version"],
        commit_hash=meta["commit_hash"],
        overall_pct=f"{results['overall_score'] * 100:.1f}%",
        std_dev=f"{results['std_dev']:.4f}",
        repeat=meta["repeat"],
        num_samples=meta["num_samples"],
        total_tokens=results.get("total_tokens", 0),
        metric_scores=results["metric_scores"],
        has_per_repeat=len(results.get("per_repeat", [])) > 1,
        per_repeat_labels=[f"Run {i+1}" for i in range(len(results.get("per_repeat", [])))],
        per_repeat_values=results.get("per_repeat", []),
        accent="#2563eb",
        accent_2="#7c3aed",
        has_radar=bool(results.get("metric_scores")),
        radar_labels=list(results.get("metric_scores", {}).keys()),
        radar_values=list(results.get("metric_scores", {}).values()),
        has_difficulty=bool(results.get("by_difficulty")),
        difficulty_labels=list(results.get("by_difficulty", {}).keys()),
        difficulty_values=list(results.get("by_difficulty", {}).values()),
        score_class=_score_class,
        bar_width=_bar_width,
    )


def save_html_report(result: dict[str, Any], output_path: Path) -> Path:
    """Save benchmark results as an HTML report.

    Returns the path to the saved file.
    """
    html = generate_html_report(result)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)
    return output_path