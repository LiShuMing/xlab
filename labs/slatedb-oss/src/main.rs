use std::net::SocketAddr;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::Duration;

use anyhow::Result;
use clap::{Parser, Subcommand, ValueEnum};
use object_store::ObjectStore;
use slatedb::config::Settings;
use slatedb::db_cache::foyer::FoyerCache;
use slatedb::Db;
use uuid::Uuid;

use slatedb_oss::bench::{run_bench, BenchConfig};
use slatedb_oss::config::{OssConfig, DEFAULT_OSS_BUCKET};
use slatedb_oss::e2e::run_e2e;
use slatedb_oss::kv_server::{serve_until_ctrl_c, KvServerState};
use slatedb_oss::store::{
    build_memory_store, build_oss_store, cleanup_prefix, ensure_cas_supported, inspect_layout,
    CountingObjectStore,
};

#[derive(Debug, Clone, Copy, ValueEnum)]
enum Backend {
    Oss,
    Memory,
}

#[derive(Debug, Parser)]
#[command(
    name = "slatedb-oss",
    about = "SlateDB over Alibaba Cloud OSS via OpenDAL: E2E verification, benchmarks, and thin KV HTTP server"
)]
struct Cli {
    #[command(subcommand)]
    command: Option<Command>,

    /// Storage backend to test against (used when no subcommand is given, defaults to `e2e`).
    #[arg(long, value_enum, default_value_t = Backend::Oss)]
    backend: Backend,

    /// Override target OSS bucket (defaults to SLATEDB_OSS_BUCKET or `xlab-slatedb-dev`).
    #[arg(long)]
    bucket: Option<String>,

    /// Override OSS endpoint (defaults to SLATEDB_OSS_ENDPOINT or DB_RADAR_OSS_ENDPOINT).
    #[arg(long)]
    endpoint: Option<String>,

    /// Database prefix inside the bucket/store (defaults to a unique `e2e/<uuid>` path).
    #[arg(long)]
    prefix: Option<String>,

    /// Optional dotenv file path (defaults to `$HOME/.env` if present).
    #[arg(long)]
    env_file: Option<PathBuf>,

    /// Keep created objects after verification for manual inspection.
    #[arg(long, default_value_t = false)]
    keep_data: bool,
}

#[derive(Debug, Subcommand)]
enum Command {
    /// Run the 6-stage E2E correctness verification.
    E2e {
        #[arg(long, value_enum, default_value_t = Backend::Oss)]
        backend: Backend,
        #[arg(long)]
        bucket: Option<String>,
        #[arg(long)]
        endpoint: Option<String>,
        #[arg(long)]
        prefix: Option<String>,
        #[arg(long)]
        env_file: Option<PathBuf>,
        #[arg(long, default_value_t = false)]
        keep_data: bool,
    },
    /// Run flush_interval, Foyer cache, and detached Compactor/GC benchmarks.
    Bench {
        #[arg(long, value_enum, default_value_t = Backend::Oss)]
        backend: Backend,
        #[arg(long)]
        bucket: Option<String>,
        #[arg(long)]
        endpoint: Option<String>,
        #[arg(long)]
        prefix: Option<String>,
        #[arg(long)]
        env_file: Option<PathBuf>,
        /// Number of puts per flush_interval sweep run.
        #[arg(long, default_value_t = 32)]
        write_ops: usize,
        /// Concurrent writer tasks for group-commit testing.
        #[arg(long, default_value_t = 8)]
        concurrency: usize,
        /// Payload size in bytes per key.
        #[arg(long, default_value_t = 256)]
        value_bytes: usize,
        /// Number of keys for Foyer cache vs uncached read comparison.
        #[arg(long, default_value_t = 24)]
        read_keys: usize,
        /// Comma-separated flush intervals in ms.
        #[arg(long, default_value = "50,200,1000")]
        flush_intervals_ms: String,
        /// Optional path to write structured JSON benchmark report.
        #[arg(long)]
        json_out: Option<PathBuf>,
        #[arg(long, default_value_t = false)]
        keep_data: bool,
    },
    /// Run a thin single-writer HTTP KV service over SlateDB + Foyer cache.
    Serve {
        #[arg(long, value_enum, default_value_t = Backend::Oss)]
        backend: Backend,
        #[arg(long)]
        bucket: Option<String>,
        #[arg(long)]
        endpoint: Option<String>,
        #[arg(long, default_value = "kv-service/default")]
        prefix: String,
        #[arg(long)]
        env_file: Option<PathBuf>,
        #[arg(long, default_value = "127.0.0.1:8088")]
        bind: SocketAddr,
        #[arg(long, default_value_t = 100)]
        flush_interval_ms: u64,
    },
}

fn open_backend(
    backend: Backend,
    env_file: Option<&std::path::Path>,
    bucket: Option<&str>,
    endpoint: Option<&str>,
) -> Result<(Arc<dyn ObjectStore>, String, String)> {
    match backend {
        Backend::Memory => Ok((
            build_memory_store(),
            "memory".to_string(),
            "in-memory".to_string(),
        )),
        Backend::Oss => {
            let cfg = OssConfig::load(env_file, bucket, Some("/"), endpoint)?;
            println!("Backend : Aliyun OSS via OpenDAL (Route 1, no s3s)");
            println!("Endpoint: {}", cfg.endpoint);
            println!("Bucket  : {}", cfg.bucket);
            let store = build_oss_store(&cfg)?;
            Ok((store, "oss".to_string(), cfg.bucket))
        }
    }
}

async fn handle_e2e(
    backend: Backend,
    bucket: Option<String>,
    endpoint: Option<String>,
    prefix: Option<String>,
    env_file: Option<PathBuf>,
    keep_data: bool,
) -> Result<()> {
    let run_prefix = prefix.unwrap_or_else(|| format!("e2e/run-{}", Uuid::new_v4().simple()));
    let (store, _, _) = open_backend(
        backend,
        env_file.as_deref(),
        bucket.as_deref(),
        endpoint.as_deref(),
    )?;
    println!("Prefix  : {run_prefix}");

    let run_result = run_e2e(Arc::clone(&store), &run_prefix).await;

    match &run_result {
        Ok(report) => {
            println!("\n=== E2E Stages ===");
            for stage in &report.stages {
                println!("[PASS] {} ({} ms)", stage.name, stage.duration_ms);
                println!("       {}", stage.detail);
            }
            println!("\n=== Persisted Object Layout ===");
            println!(
                "Total: {} objects, {} bytes",
                report.layout.total_objects, report.layout.total_bytes
            );
            for (dir, count) in &report.layout.by_subdir {
                println!("  {dir}/ : {count}");
            }
            println!("Sample keys:");
            for key in &report.layout.sample_paths {
                println!("  - {key}");
            }
        }
        Err(err) => {
            eprintln!("\n[FAIL] E2E verification failed: {err:#}");
        }
    }

    if keep_data {
        println!("\n[--keep-data] Preserving objects under `{run_prefix}`.");
    } else {
        let deleted = cleanup_prefix(&store, &run_prefix).await?;
        let remaining = inspect_layout(&store, &run_prefix).await?;
        println!(
            "\n[CLEANUP] Deleted {deleted} objects under `{run_prefix}`; remaining = {}.",
            remaining.total_objects
        );
    }

    run_result.map(|_| ())
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();

    match cli.command {
        None => {
            handle_e2e(
                cli.backend,
                cli.bucket,
                cli.endpoint,
                cli.prefix,
                cli.env_file,
                cli.keep_data,
            )
            .await
        }
        Some(Command::E2e {
            backend,
            bucket,
            endpoint,
            prefix,
            env_file,
            keep_data,
        }) => handle_e2e(backend, bucket, endpoint, prefix, env_file, keep_data).await,
        Some(Command::Bench {
            backend,
            bucket,
            endpoint,
            prefix,
            env_file,
            write_ops,
            concurrency,
            value_bytes,
            read_keys,
            flush_intervals_ms,
            json_out,
            keep_data,
        }) => {
            let run_prefix =
                prefix.unwrap_or_else(|| format!("bench/run-{}", Uuid::new_v4().simple()));
            let (store, backend_name, bucket_name) = open_backend(
                backend,
                env_file.as_deref(),
                bucket.as_deref(),
                endpoint.as_deref(),
            )?;
            println!("Prefix  : {run_prefix}");

            let intervals: Vec<u64> = flush_intervals_ms
                .split(',')
                .filter(|s| !s.trim().is_empty())
                .map(|s| s.trim().parse::<u64>())
                .collect::<std::result::Result<_, _>>()?;

            let cfg = BenchConfig {
                backend: backend_name,
                bucket: bucket_name,
                prefix: run_prefix.clone(),
                write_ops,
                concurrency,
                value_bytes,
                read_keys,
                flush_intervals_ms: intervals,
            };

            let bench_res = run_bench(Arc::clone(&store), &cfg).await;

            if let Ok(ref report) = bench_res {
                println!("\n=== Flush Interval Sweep (Group Commit vs OSS PUTs) ===");
                for r in &report.flush_sweep {
                    println!(
                        "flush={:>4}ms | ops={} (c={}) | wall={:.1}ms | {:.1} ops/s | p50={:.1}ms p99={:.1}ms | OSS PUTs={} ({} B)",
                        r.flush_interval_ms,
                        r.ops,
                        r.concurrency,
                        r.wall_ms,
                        r.ops_per_sec,
                        r.latency.p50_ms,
                        r.latency.p99_ms,
                        r.store_delta.put_ops,
                        r.store_delta.put_bytes,
                    );
                }
                println!("\n=== Foyer Cache vs Uncached Reads ===");
                for r in &report.cache_comparison {
                    println!(
                        "cache={:<12} | phase={:<11} | reads={} | wall={:.1}ms | p50={:.1}ms p99={:.1}ms | OSS GETs={} range_GETs={} ({} B)",
                        r.cache_mode,
                        r.phase,
                        r.reads,
                        r.wall_ms,
                        r.latency.p50_ms,
                        r.latency.p99_ms,
                        r.store_delta.get_ops,
                        r.store_delta.get_range_ops,
                        r.store_delta.get_bytes,
                    );
                }
                println!("\n=== Detached Compactor + GC ===");
                println!(
                    "l0_flushes={} | compactor_ok={} | gc_ok={} | wall={:.1}ms | PUTs={} GETs={} LISTs={}",
                    report.detached_workers.l0_flushes,
                    report.detached_workers.compactor_ok,
                    report.detached_workers.gc_ok,
                    report.detached_workers.wall_ms,
                    report.detached_workers.store_delta.put_ops,
                    report.detached_workers.store_delta.get_ops,
                    report.detached_workers.store_delta.list_ops,
                );

                if let Some(out_path) = json_out {
                    if let Some(parent) = out_path.parent() {
                        if !parent.as_os_str().is_empty() {
                            std::fs::create_dir_all(parent)?;
                        }
                    }
                    std::fs::write(&out_path, serde_json::to_string_pretty(report)?)?;
                    println!("\n[JSON] Wrote benchmark report to {}", out_path.display());
                }
            }

            if !keep_data {
                let deleted = cleanup_prefix(&store, &run_prefix).await?;
                let remaining = inspect_layout(&store, &run_prefix).await?;
                println!(
                    "\n[CLEANUP] Deleted {deleted} objects under `{run_prefix}`; remaining = {}.",
                    remaining.total_objects
                );
            }

            bench_res.map(|_| ())
        }
        Some(Command::Serve {
            backend,
            bucket,
            endpoint,
            prefix,
            env_file,
            bind,
            flush_interval_ms,
        }) => {
            let resolved_bucket = bucket.unwrap_or_else(|| DEFAULT_OSS_BUCKET.to_string());
            let (raw_store, _, _) = open_backend(
                backend,
                env_file.as_deref(),
                Some(resolved_bucket.as_str()),
                endpoint.as_deref(),
            )?;
            // Fail-fast CAS startup guard before opening SlateDB writer.
            ensure_cas_supported(&raw_store, &prefix).await?;
            let counted = CountingObjectStore::new(raw_store);
            let db = Arc::new(
                Db::builder(prefix.as_str(), counted.clone())
                    .with_settings(Settings {
                        flush_interval: Some(Duration::from_millis(flush_interval_ms)),
                        ..Settings::default()
                    })
                    .with_db_cache(Arc::new(FoyerCache::new()), 1)
                    .build()
                    .await?,
            );
            serve_until_ctrl_c(bind, KvServerState { db, counted }).await
        }
    }
}
