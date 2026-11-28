import { readdirSync, readFileSync, statSync } from "node:fs";
import { basename, extname, join, resolve } from "node:path";

export interface MetricRow {
  readonly label: string;
  readonly metrics: Readonly<Record<string, string | number | boolean>>;
}

export interface NormalizedReport {
  readonly sourceFile: string;
  readonly lab: string;
  readonly title: string;
  readonly summary: Readonly<Record<string, string | number | boolean>>;
  readonly sections: ReadonlyArray<{
    readonly heading: string;
    readonly rows: readonly MetricRow[];
  }>;
}

interface RawSlateDbBench {
  lab: "slatedb-oss";
  backend?: string;
  bucket?: string;
  value_bytes?: number;
  flush_sweep?: Array<{
    flush_interval_ms: number;
    ops: number;
    concurrency: number;
    wall_ms: number;
    ops_per_sec: number;
    latency: { p50_ms: number; p99_ms: number };
    store_delta: { put_ops: number; put_bytes: number };
  }>;
  cache_comparison?: Array<{
    cache_mode: string;
    phase: string;
    reads: number;
    wall_ms: number;
    latency: { p50_ms: number; p99_ms: number };
    store_delta: { get_ops: number; get_range_ops: number; get_bytes: number };
  }>;
  detached_workers?: {
    l0_flushes: number;
    compactor_ok: boolean;
    gc_ok: boolean;
    wall_ms: number;
  };
}

interface RawDuckDbCompare {
  lab: "duckdb-oss-compare";
  bucket?: string;
  rows?: number;
  batch_parquet_write_ms?: number;
  point_queries?: number;
  point_lookup_p50_ms?: number;
  point_lookup_mean_ms?: number;
  full_groupby_scan_ms?: number;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isPrimitive(value: unknown): value is string | number | boolean {
  return typeof value === "string" || typeof value === "number" || typeof value === "boolean";
}

function normalizeSlateDb(raw: RawSlateDbBench, sourceFile: string): NormalizedReport {
  const sections: Array<{ heading: string; rows: MetricRow[] }> = [];

  if (Array.isArray(raw.flush_sweep) && raw.flush_sweep.length > 0) {
    sections.push({
      heading: "Flush Interval Sweep (Group Commit vs OSS PUTs)",
      rows: raw.flush_sweep.map((r) => ({
        label: `${r.flush_interval_ms}ms`,
        metrics: {
          ops: r.ops,
          concurrency: r.concurrency,
          wall_ms: r.wall_ms,
          ops_per_sec: r.ops_per_sec,
          p50_ms: r.latency.p50_ms,
          p99_ms: r.latency.p99_ms,
          oss_put_ops: r.store_delta.put_ops,
          oss_put_bytes: r.store_delta.put_bytes,
        },
      })),
    });
  }

  if (Array.isArray(raw.cache_comparison) && raw.cache_comparison.length > 0) {
    sections.push({
      heading: "Foyer Cache vs Uncached Reads",
      rows: raw.cache_comparison.map((r) => ({
        label: `${r.cache_mode} / ${r.phase}`,
        metrics: {
          reads: r.reads,
          wall_ms: r.wall_ms,
          p50_ms: r.latency.p50_ms,
          p99_ms: r.latency.p99_ms,
          oss_get_ops: r.store_delta.get_ops,
          oss_range_gets: r.store_delta.get_range_ops,
          oss_get_bytes: r.store_delta.get_bytes,
        },
      })),
    });
  }

  if (raw.detached_workers) {
    sections.push({
      heading: "Detached Compactor + GC",
      rows: [
        {
          label: "standalone-workers",
          metrics: {
            l0_flushes: raw.detached_workers.l0_flushes,
            compactor_ok: raw.detached_workers.compactor_ok,
            gc_ok: raw.detached_workers.gc_ok,
            wall_ms: raw.detached_workers.wall_ms,
          },
        },
      ],
    });
  }

  return {
    sourceFile,
    lab: "slatedb-oss",
    title: `SlateDB on ${raw.backend ?? "unknown"} (${raw.bucket ?? "n/a"})`,
    summary: {
      backend: raw.backend ?? "unknown",
      bucket: raw.bucket ?? "n/a",
      value_bytes: raw.value_bytes ?? 0,
    },
    sections,
  };
}

function normalizeDuckDb(raw: RawDuckDbCompare, sourceFile: string): NormalizedReport {
  return {
    sourceFile,
    lab: "duckdb-oss-compare",
    title: `DuckDB + Parquet on OSS (${raw.bucket ?? "n/a"})`,
    summary: {
      bucket: raw.bucket ?? "n/a",
      rows: raw.rows ?? 0,
      batch_parquet_write_ms: raw.batch_parquet_write_ms ?? 0,
      point_lookup_p50_ms: raw.point_lookup_p50_ms ?? 0,
      full_groupby_scan_ms: raw.full_groupby_scan_ms ?? 0,
    },
    sections: [
      {
        heading: "Columnar Parquet Operations over OSS",
        rows: [
          {
            label: "batch_write",
            metrics: { rows: raw.rows ?? 0, latency_ms: raw.batch_parquet_write_ms ?? 0 },
          },
          {
            label: "point_lookup",
            metrics: {
              queries: raw.point_queries ?? 0,
              p50_ms: raw.point_lookup_p50_ms ?? 0,
              mean_ms: raw.point_lookup_mean_ms ?? 0,
            },
          },
          {
            label: "full_groupby_scan",
            metrics: { rows: raw.rows ?? 0, latency_ms: raw.full_groupby_scan_ms ?? 0 },
          },
        ],
      },
    ],
  };
}

function normalizeGeneric(raw: Record<string, unknown>, sourceFile: string): NormalizedReport {
  const lab = typeof raw["lab"] === "string" ? raw["lab"] : basename(sourceFile, ".json");
  const summary: Record<string, string | number | boolean> = {};
  const sections: Array<{ heading: string; rows: MetricRow[] }> = [];

  for (const [key, value] of Object.entries(raw)) {
    if (isPrimitive(value)) {
      summary[key] = value;
    } else if (Array.isArray(value)) {
      const rows: MetricRow[] = [];
      for (const [idx, item] of value.entries()) {
        if (!isRecord(item)) continue;
        const metrics: Record<string, string | number | boolean> = {};
        let label = `#${idx + 1}`;
        for (const [k, v] of Object.entries(item)) {
          if ((k === "name" || k === "policy" || k === "label" || k === "id") && typeof v === "string") {
            label = v;
          } else if (isPrimitive(v)) {
            metrics[k] = v;
          }
        }
        rows.push({ label, metrics });
      }
      if (rows.length > 0) {
        sections.push({ heading: key, rows });
      }
    }
  }

  return {
    sourceFile,
    lab,
    title: typeof raw["title"] === "string" ? raw["title"] : lab,
    summary,
    sections,
  };
}

export function normalizeReport(parsed: unknown, sourceFile: string): NormalizedReport {
  if (!isRecord(parsed)) {
    throw new Error(`Expected JSON object in ${sourceFile}`);
  }
  if (parsed["lab"] === "slatedb-oss") {
    return normalizeSlateDb(parsed as unknown as RawSlateDbBench, sourceFile);
  }
  if (parsed["lab"] === "duckdb-oss-compare") {
    return normalizeDuckDb(parsed as unknown as RawDuckDbCompare, sourceFile);
  }
  return normalizeGeneric(parsed, sourceFile);
}

export function discoverJsonFiles(inputs: readonly string[]): string[] {
  const found: string[] = [];
  for (const rawPath of inputs) {
    const abs = resolve(rawPath);
    const st = statSync(abs);
    if (st.isFile() && extname(abs).toLowerCase() === ".json") {
      found.push(abs);
    } else if (st.isDirectory()) {
      for (const entry of readdirSync(abs).sort()) {
        const child = join(abs, entry);
        if (statSync(child).isFile() && extname(child).toLowerCase() === ".json") {
          found.push(child);
        }
      }
    }
  }
  return found;
}

export function loadReports(inputs: readonly string[]): NormalizedReport[] {
  const files = discoverJsonFiles(inputs);
  return files.map((filePath) => {
    const raw = JSON.parse(readFileSync(filePath, "utf8")) as unknown;
    return normalizeReport(raw, basename(filePath));
  });
}
