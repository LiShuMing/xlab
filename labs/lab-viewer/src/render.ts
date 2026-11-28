import type { MetricRow, NormalizedReport } from "./loader.ts";

function escapeHtml(text: string): string {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function collectColumns(rows: readonly MetricRow[]): string[] {
  const cols = new Set<string>();
  for (const row of rows) {
    for (const key of Object.keys(row.metrics)) {
      cols.add(key);
    }
  }
  return [...cols];
}

export function renderMarkdown(reports: readonly NormalizedReport[]): string {
  const lines: string[] = ["# xlab Benchmark Report Summary", ""];
  if (reports.length === 0) {
    lines.push("No JSON reports found.");
    return lines.join("\n") + "\n";
  }

  for (const report of reports) {
    lines.push(`## ${report.title}`);
    lines.push(`- Source: \`${report.sourceFile}\` (\`${report.lab}\`)`);
    const summaryPairs = Object.entries(report.summary)
      .map(([k, v]) => `\`${k}=${String(v)}\``)
      .join(" | ");
    if (summaryPairs.length > 0) {
      lines.push(`- Summary: ${summaryPairs}`);
    }
    lines.push("");

    for (const section of report.sections) {
      lines.push(`### ${section.heading}`);
      const cols = collectColumns(section.rows);
      lines.push(`| Case | ${cols.join(" | ")} |`);
      lines.push(`| --- | ${cols.map(() => "---").join(" | ")} |`);
      for (const row of section.rows) {
        const vals = cols.map((c) => {
          const val = row.metrics[c];
          return val === undefined ? "-" : String(val);
        });
        lines.push(`| ${row.label} | ${vals.join(" | ")} |`);
      }
      lines.push("");
    }
  }
  return lines.join("\n");
}

function renderBarSvg(rows: readonly MetricRow[], metricKey: string): string {
  const points = rows
    .map((r) => ({ label: r.label, val: r.metrics[metricKey] }))
    .filter((p): p is { label: string; val: number } => typeof p.val === "number");
  if (points.length === 0) return "";

  const maxVal = Math.max(...points.map((p) => p.val), 1);
  const rowH = 28;
  const height = points.length * rowH + 16;
  const labelW = 170;
  const barMaxW = 320;
  const bars = points
    .map((p, i) => {
      const y = i * rowH + 8;
      const w = Math.max(2, Math.round((p.val / maxVal) * barMaxW));
      return [
        `<text x="0" y="${y + 15}" fill="#cbd5e1" font-size="12">${escapeHtml(p.label)}</text>`,
        `<rect x="${labelW}" y="${y + 3}" width="${w}" height="16" rx="4" fill="#38bdf8" />`,
        `<text x="${labelW + w + 8}" y="${y + 15}" fill="#e2e8f0" font-size="12">${p.val}</text>`,
      ].join("");
    })
    .join("");

  return `<div class="chart"><div class="chart-title">${escapeHtml(metricKey)}</div><svg width="100%" viewBox="0 0 580 ${height}">${bars}</svg></div>`;
}

export function renderHtml(reports: readonly NormalizedReport[]): string {
  const cards = reports
    .map((report) => {
      const badges = Object.entries(report.summary)
        .map(
          ([k, v]) =>
            `<span class="badge"><strong>${escapeHtml(k)}:</strong> ${escapeHtml(String(v))}</span>`,
        )
        .join("");

      const sectionsHtml = report.sections
        .map((sec) => {
          const cols = collectColumns(sec.rows);
          const firstNumericCol = cols.find((c) =>
            sec.rows.some((r) => typeof r.metrics[c] === "number"),
          );
          const chart = firstNumericCol ? renderBarSvg(sec.rows, firstNumericCol) : "";
          const headCells = ["Case", ...cols].map((c) => `<th>${escapeHtml(c)}</th>`).join("");
          const bodyRows = sec.rows
            .map((r) => {
              const cells = [
                `<td>${escapeHtml(r.label)}</td>`,
                ...cols.map((c) => `<td>${escapeHtml(String(r.metrics[c] ?? "-"))}</td>`),
              ].join("");
              return `<tr>${cells}</tr>`;
            })
            .join("");
          return `<section><h3>${escapeHtml(sec.heading)}</h3>${chart}<table><thead><tr>${headCells}</tr></thead><tbody>${bodyRows}</tbody></table></section>`;
        })
        .join("");

      return `<article class="card"><h2>${escapeHtml(report.title)}</h2><div class="meta">${escapeHtml(report.sourceFile)} · ${escapeHtml(report.lab)}</div><div class="badges">${badges}</div>${sectionsHtml}</article>`;
    })
    .join("");

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>xlab Benchmark Report Viewer</title>
<style>
  body { margin: 0; font-family: ui-sans-serif, system-ui, sans-serif; background: #0f172a; color: #e2e8f0; }
  main { max-width: 1080px; margin: 0 auto; padding: 32px 20px; }
  h1 { margin: 0 0 8px; font-size: 26px; }
  .subtitle { color: #94a3b8; margin-bottom: 24px; }
  .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; margin-bottom: 24px; }
  .meta { color: #94a3b8; font-size: 13px; margin-bottom: 12px; }
  .badges { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
  .badge { background: #0f172a; border: 1px solid #334155; border-radius: 999px; padding: 4px 10px; font-size: 12px; }
  .chart { background: #0f172a; border-radius: 8px; padding: 12px; margin: 10px 0 14px; }
  .chart-title { color: #94a3b8; font-size: 12px; margin-bottom: 6px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 16px; }
  th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #334155; }
  th { color: #94a3b8; font-weight: 600; }
</style>
</head>
<body>
<main>
  <h1>xlab Benchmark Report Viewer</h1>
  <div class="subtitle">Generated offline from ${reports.length} JSON report(s)</div>
  ${cards || "<p>No reports loaded.</p>"}
</main>
</body>
</html>
`;
}
