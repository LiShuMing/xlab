import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { loadReports, normalizeReport } from "../src/loader.ts";
import { renderHtml, renderMarkdown } from "../src/render.ts";

test("normalizes slatedb-oss and duckdb-oss-compare JSON reports", () => {
  const slate = normalizeReport(
    {
      lab: "slatedb-oss",
      backend: "oss",
      bucket: "xlab-slatedb-dev",
      value_bytes: 256,
      flush_sweep: [
        {
          flush_interval_ms: 50,
          ops: 32,
          concurrency: 8,
          wall_ms: 420.5,
          ops_per_sec: 76.1,
          latency: { p50_ms: 82.1, p99_ms: 145.3 },
          store_delta: { put_ops: 5, put_bytes: 9400 },
        },
      ],
      cache_comparison: [
        {
          cache_mode: "foyer_memory",
          phase: "round2_warm",
          reads: 24,
          wall_ms: 1.2,
          latency: { p50_ms: 0.04, p99_ms: 0.1 },
          store_delta: { get_ops: 0, get_range_ops: 0, get_bytes: 0 },
        },
      ],
      detached_workers: {
        l0_flushes: 3,
        compactor_ok: true,
        gc_ok: true,
        wall_ms: 910.0,
      },
    },
    "slatedb.json",
  );

  assert.equal(slate.lab, "slatedb-oss");
  assert.equal(slate.sections.length, 3);
  assert.equal(slate.sections[1]?.rows[0]?.metrics["oss_get_ops"], 0);

  const duck = normalizeReport(
    {
      lab: "duckdb-oss-compare",
      bucket: "xlab-slatedb-dev",
      rows: 10000,
      batch_parquet_write_ms: 350.2,
      point_queries: 5,
      point_lookup_p50_ms: 95.4,
      point_lookup_mean_ms: 101.2,
      full_groupby_scan_ms: 140.8,
    },
    "duckdb.json",
  );

  const md = renderMarkdown([slate, duck]);
  assert.match(md, /Flush Interval Sweep/);
  assert.match(md, /DuckDB \+ Parquet on OSS/);

  const html = renderHtml([slate, duck]);
  assert.match(html, /<svg /);
  assert.match(html, /slatedb-oss/);
  assert.match(html, /duckdb-oss-compare/);
});

test("loads generic JSON benchmark files from directory", () => {
  const dir = mkdtempSync(join(tmpdir(), "lab-viewer-test-"));
  try {
    writeFileSync(
      join(dir, "cache.json"),
      JSON.stringify({
        lab: "cache",
        workload: "zipf",
        results: [
          { policy: "LRU", hit_rate: 0.72 },
          { policy: "W-TinyLFU", hit_rate: 0.85 },
        ],
      }),
      "utf8",
    );

    const reports = loadReports([dir]);
    assert.equal(reports.length, 1);
    assert.equal(reports[0]?.lab, "cache");
    assert.equal(reports[0]?.sections[0]?.rows.length, 2);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
