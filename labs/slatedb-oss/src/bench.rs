use std::sync::Arc;
use std::time::{Duration, Instant};

use anyhow::{Context, Result};
use object_store::ObjectStore;
use serde::{Deserialize, Serialize};
use slatedb::config::{
    CompactorOptions, DbReaderOptions, FlushOptions, FlushType, GarbageCollectorOptions, Settings,
};
use slatedb::db_cache::foyer::FoyerCache;
use slatedb::{CompactorBuilder, Db, DbReader, DbReaderMode, GarbageCollectorBuilder};

use crate::store::{ensure_cas_supported, CountingObjectStore, ObjectStoreCounters};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LatencySummaryMs {
    pub p50_ms: f64,
    pub p95_ms: f64,
    pub p99_ms: f64,
    pub mean_ms: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FlushIntervalRun {
    pub flush_interval_ms: u64,
    pub ops: usize,
    pub concurrency: usize,
    pub wall_ms: f64,
    pub ops_per_sec: f64,
    pub latency: LatencySummaryMs,
    pub store_delta: ObjectStoreCounters,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CacheReadRun {
    pub cache_mode: String,
    pub phase: String,
    pub reads: usize,
    pub wall_ms: f64,
    pub latency: LatencySummaryMs,
    pub store_delta: ObjectStoreCounters,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DetachedWorkerRun {
    pub l0_flushes: usize,
    pub compactor_ok: bool,
    pub gc_ok: bool,
    pub wall_ms: f64,
    pub store_delta: ObjectStoreCounters,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BenchReport {
    pub lab: String,
    pub backend: String,
    pub bucket: String,
    pub prefix: String,
    pub value_bytes: usize,
    pub flush_sweep: Vec<FlushIntervalRun>,
    pub cache_comparison: Vec<CacheReadRun>,
    pub detached_workers: DetachedWorkerRun,
}

#[derive(Debug, Clone)]
pub struct BenchConfig {
    pub backend: String,
    pub bucket: String,
    pub prefix: String,
    pub write_ops: usize,
    pub concurrency: usize,
    pub value_bytes: usize,
    pub read_keys: usize,
    pub flush_intervals_ms: Vec<u64>,
}

/// Run the 3-part SlateDB benchmark suite over `raw_store`.
pub async fn run_bench(raw_store: Arc<dyn ObjectStore>, cfg: &BenchConfig) -> Result<BenchReport> {
    eprintln!("[bench] verifying PutMode::Create CAS...");
    ensure_cas_supported(&raw_store, &cfg.prefix).await?;
    eprintln!("[bench] CAS verified.");

    let counted = CountingObjectStore::new(raw_store);
    let store: Arc<dyn ObjectStore> = counted.clone();

    let mut flush_sweep = Vec::with_capacity(cfg.flush_intervals_ms.len());
    for &interval_ms in &cfg.flush_intervals_ms {
        eprintln!("[bench] running flush_interval={interval_ms}ms...");
        let sub_prefix = format!("{}/flush_{interval_ms}ms", cfg.prefix);
        let run = bench_flush_interval(
            Arc::clone(&store),
            &counted,
            &sub_prefix,
            interval_ms,
            cfg.write_ops,
            cfg.concurrency,
            cfg.value_bytes,
        )
        .await?;
        flush_sweep.push(run);
    }

    eprintln!("[bench] running foyer cache comparison...");
    let cache_prefix = format!("{}/cache_bench", cfg.prefix);
    let cache_comparison = bench_foyer_cache(
        Arc::clone(&store),
        &counted,
        &cache_prefix,
        cfg.read_keys,
        cfg.value_bytes,
    )
    .await?;

    eprintln!("[bench] running detached compactor + gc check...");
    let workers_prefix = format!("{}/detached_workers", cfg.prefix);
    let detached_workers =
        bench_detached_workers(Arc::clone(&store), &counted, &workers_prefix).await?;

    Ok(BenchReport {
        lab: "slatedb-oss".to_string(),
        backend: cfg.backend.clone(),
        bucket: cfg.bucket.clone(),
        prefix: cfg.prefix.clone(),
        value_bytes: cfg.value_bytes,
        flush_sweep,
        cache_comparison,
        detached_workers,
    })
}

async fn bench_flush_interval(
    store: Arc<dyn ObjectStore>,
    counted: &CountingObjectStore,
    db_prefix: &str,
    flush_interval_ms: u64,
    total_ops: usize,
    concurrency: usize,
    value_bytes: usize,
) -> Result<FlushIntervalRun> {
    let settings = Settings {
        flush_interval: Some(Duration::from_millis(flush_interval_ms)),
        compactor_options: None,
        garbage_collector_options: None,
        ..Settings::default()
    };
    let db = Arc::new(
        Db::builder(db_prefix, store)
            .with_settings(settings)
            .build()
            .await
            .with_context(|| {
                format!("failed to open Db for flush_interval={flush_interval_ms}ms")
            })?,
    );

    let before = counted.snapshot();
    let payload = vec![b'x'; value_bytes];
    let workers = concurrency.max(1).min(total_ops.max(1));
    let start = Instant::now();

    let mut handles = Vec::with_capacity(workers);
    for w in 0..workers {
        let db = Arc::clone(&db);
        let val = payload.clone();
        handles.push(tokio::spawn(async move {
            let mut lats = Vec::new();
            let mut idx = w;
            while idx < total_ops {
                let key = format!("k_{idx:06}");
                let t0 = Instant::now();
                let handle = db.put(key.as_bytes(), &val).await?;
                handle.await_durable().await?;
                lats.push(t0.elapsed().as_secs_f64() * 1000.0);
                idx += workers;
            }
            Ok::<Vec<f64>, anyhow::Error>(lats)
        }));
    }

    let mut all_lats = Vec::with_capacity(total_ops);
    for h in handles {
        all_lats.extend(h.await??);
    }
    let wall_ms = start.elapsed().as_secs_f64() * 1000.0;
    let after = counted.snapshot();

    db.close().await?;

    let ops_per_sec = if wall_ms > 0.0 {
        (total_ops as f64) / (wall_ms / 1000.0)
    } else {
        0.0
    };

    Ok(FlushIntervalRun {
        flush_interval_ms,
        ops: total_ops,
        concurrency: workers,
        wall_ms: round2(wall_ms),
        ops_per_sec: round2(ops_per_sec),
        latency: summarize_latencies(&mut all_lats),
        store_delta: after.delta_since(&before),
    })
}

async fn bench_foyer_cache(
    store: Arc<dyn ObjectStore>,
    counted: &CountingObjectStore,
    db_prefix: &str,
    num_keys: usize,
    value_bytes: usize,
) -> Result<Vec<CacheReadRun>> {
    // Seed keys and force MemTable flush so reads hit compacted L0 SST blocks on OSS.
    let writer = Db::builder(db_prefix, Arc::clone(&store))
        .with_settings(Settings {
            compactor_options: None,
            garbage_collector_options: None,
            ..Settings::default()
        })
        .build()
        .await?;

    let val = vec![b'v'; value_bytes];
    for i in 0..num_keys {
        let key = format!("hot_{i:05}");
        writer.put(key.as_bytes(), &val).await?;
    }
    writer
        .flush_with_options(FlushOptions {
            flush_type: FlushType::MemTable,
        })
        .await?;
    writer.close().await?;

    let mut results = Vec::with_capacity(4);

    // Mode 1: Cache disabled (every read hits object store)
    let uncached = DbReader::builder(db_prefix, Arc::clone(&store))
        .with_reader_mode(DbReaderMode::FollowLatest)
        .with_options(DbReaderOptions {
            skip_wal_replay: true,
            ..DbReaderOptions::default()
        })
        .with_db_cache_disabled()
        .build()
        .await?;
    for phase in ["round1_cold", "round2_warm"] {
        results.push(measure_reader_pass(&uncached, counted, "disabled", phase, num_keys).await?);
    }
    uncached.close().await?;

    // Mode 2: Foyer in-memory cache enabled (round1 fills blocks, round2 serves from RAM)
    let foyer_cache = Arc::new(FoyerCache::new());
    let cached = DbReader::builder(db_prefix, store)
        .with_reader_mode(DbReaderMode::FollowLatest)
        .with_options(DbReaderOptions {
            skip_wal_replay: true,
            ..DbReaderOptions::default()
        })
        .with_db_cache(foyer_cache, 1)
        .build()
        .await?;
    for phase in ["round1_cold", "round2_warm"] {
        results.push(measure_reader_pass(&cached, counted, "foyer_memory", phase, num_keys).await?);
    }
    cached.close().await?;

    Ok(results)
}

async fn measure_reader_pass(
    reader: &DbReader,
    counted: &CountingObjectStore,
    cache_mode: &str,
    phase: &str,
    num_keys: usize,
) -> Result<CacheReadRun> {
    let before = counted.snapshot();
    let start = Instant::now();
    let mut lats = Vec::with_capacity(num_keys);

    for i in 0..num_keys {
        let key = format!("hot_{i:05}");
        let t0 = Instant::now();
        let got = reader.get(key.as_bytes()).await?;
        anyhow::ensure!(got.is_some(), "missing expected key {key}");
        lats.push(t0.elapsed().as_secs_f64() * 1000.0);
    }

    let wall_ms = start.elapsed().as_secs_f64() * 1000.0;
    let after = counted.snapshot();

    Ok(CacheReadRun {
        cache_mode: cache_mode.to_string(),
        phase: phase.to_string(),
        reads: num_keys,
        wall_ms: round2(wall_ms),
        latency: summarize_latencies(&mut lats),
        store_delta: after.delta_since(&before),
    })
}

/// Verify detached Compactor + GarbageCollector running independently of the Db writer.
async fn bench_detached_workers(
    store: Arc<dyn ObjectStore>,
    counted: &CountingObjectStore,
    db_prefix: &str,
) -> Result<DetachedWorkerRun> {
    let before = counted.snapshot();
    let start = Instant::now();

    let writer = Db::builder(db_prefix, Arc::clone(&store))
        .with_settings(Settings {
            compactor_options: None,
            garbage_collector_options: None,
            ..Settings::default()
        })
        .build()
        .await?;

    let l0_flushes = 3usize;
    for batch_idx in 0..l0_flushes {
        for k in 0..5 {
            let key = format!("w_{batch_idx}_{k}");
            writer
                .put(key.as_bytes(), b"detached-worker-payload")
                .await?;
        }
        writer
            .flush_with_options(FlushOptions {
                flush_type: FlushType::MemTable,
            })
            .await?;
    }
    writer.close().await?;

    let compactor = Arc::new(
        CompactorBuilder::new(db_prefix, Arc::clone(&store))
            .with_options(CompactorOptions {
                poll_interval: Duration::from_millis(200),
                ..CompactorOptions::default()
            })
            .build(),
    );
    let mut comp_handle = {
        let c = Arc::clone(&compactor);
        tokio::spawn(async move { c.run().await })
    };

    // Wait briefly so Compactor::start() finishes registering its task on remote OSS,
    // then retry stop() until run() exits cleanly (avoids early-stop race).
    let compactor_ok = tokio::time::timeout(Duration::from_secs(20), async {
        tokio::time::sleep(Duration::from_millis(800)).await;
        loop {
            let _ = compactor.stop().await;
            tokio::select! {
                res = &mut comp_handle => {
                    return res.map(|inner| inner.is_ok()).unwrap_or(false);
                }
                _ = tokio::time::sleep(Duration::from_millis(250)) => {}
            }
        }
    })
    .await
    .unwrap_or_else(|_| {
        comp_handle.abort();
        false
    });

    // GarbageCollector provides deterministic one-shot execution without background races.
    let gc = GarbageCollectorBuilder::new(db_prefix, store)
        .with_options(GarbageCollectorOptions::default())
        .build();
    gc.run_gc_once().await;
    let gc_ok = true;

    let after = counted.snapshot();
    Ok(DetachedWorkerRun {
        l0_flushes,
        compactor_ok,
        gc_ok,
        wall_ms: round2(start.elapsed().as_secs_f64() * 1000.0),
        store_delta: after.delta_since(&before),
    })
}

fn summarize_latencies(samples: &mut [f64]) -> LatencySummaryMs {
    if samples.is_empty() {
        return LatencySummaryMs {
            p50_ms: 0.0,
            p95_ms: 0.0,
            p99_ms: 0.0,
            mean_ms: 0.0,
        };
    }
    samples.sort_by(|a, b| a.total_cmp(b));
    let mean = samples.iter().sum::<f64>() / (samples.len() as f64);
    LatencySummaryMs {
        p50_ms: round2(percentile(samples, 0.50)),
        p95_ms: round2(percentile(samples, 0.95)),
        p99_ms: round2(percentile(samples, 0.99)),
        mean_ms: round2(mean),
    }
}

fn percentile(sorted: &[f64], p: f64) -> f64 {
    let idx = ((sorted.len().saturating_sub(1)) as f64 * p).round() as usize;
    sorted[idx.min(sorted.len() - 1)]
}

fn round2(v: f64) -> f64 {
    (v * 100.0).round() / 100.0
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::store::{build_memory_store, cleanup_prefix};

    #[tokio::test]
    async fn bench_suite_runs_cleanly_in_memory() -> Result<()> {
        let store = build_memory_store();
        let cfg = BenchConfig {
            backend: "memory".to_string(),
            bucket: "in-memory".to_string(),
            prefix: "bench-test".to_string(),
            write_ops: 12,
            concurrency: 4,
            value_bytes: 128,
            read_keys: 12,
            flush_intervals_ms: vec![10, 50],
        };
        let report = run_bench(Arc::clone(&store), &cfg).await?;
        assert_eq!(report.flush_sweep.len(), 2);
        assert_eq!(report.cache_comparison.len(), 4);
        assert!(report.detached_workers.compactor_ok);
        assert!(report.detached_workers.gc_ok);

        // Warm foyer reads should issue zero backend GETs after round1_cold fills cache.
        let warm_foyer = report
            .cache_comparison
            .iter()
            .find(|r| r.cache_mode == "foyer_memory" && r.phase == "round2_warm")
            .expect("missing foyer warm phase");
        assert_eq!(warm_foyer.store_delta.get_ops, 0);
        assert_eq!(warm_foyer.store_delta.get_range_ops, 0);

        cleanup_prefix(&store, &cfg.prefix).await?;
        Ok(())
    }
}
