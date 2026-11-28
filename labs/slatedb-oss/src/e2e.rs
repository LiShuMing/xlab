use std::sync::Arc;
use std::time::{Duration, Instant};

use anyhow::{bail, Context, Result};
use bytes::Bytes;
use object_store::path::Path as ObjectPath;
use object_store::{ObjectStore, ObjectStoreExt, PutMode, PutOptions, PutPayload};
use slatedb::admin::AdminBuilder;
use slatedb::config::{CheckpointOptions, DbReaderOptions, FlushOptions, FlushType};
use slatedb::{CloseReason, Db, DbReader, DbReaderMode, ErrorKind, WriteBatch};

use crate::store::{inspect_layout, LayoutSummary};

#[derive(Debug, Clone)]
pub struct StageResult {
    pub name: &'static str,
    pub duration_ms: u128,
    pub detail: String,
}

#[derive(Debug, Clone)]
pub struct E2eReport {
    pub db_prefix: String,
    pub stages: Vec<StageResult>,
    pub layout: LayoutSummary,
}

/// Execute the full 6-stage SlateDB end-to-end verification against `store`.
pub async fn run_e2e(store: Arc<dyn ObjectStore>, db_prefix: &str) -> Result<E2eReport> {
    let mut stages = Vec::with_capacity(6);

    // Stage 1: Verify PutMode::Create atomic exclusivity before opening SlateDB.
    let t0 = Instant::now();
    verify_atomic_create_cas(&store, db_prefix).await?;
    stages.push(StageResult {
        name: "1. ObjectStore PutMode::Create (CAS)",
        duration_ms: t0.elapsed().as_millis(),
        detail: "first create succeeded, duplicate rejected with AlreadyExists, payload intact"
            .to_string(),
    });

    // Stage 2: Basic KV CRUD, WriteBatch, Range Scan, Seek, and MemTable L0 SST Flush.
    let t0 = Instant::now();
    verify_crud_scan_and_flush(Arc::clone(&store), db_prefix).await?;
    stages.push(StageResult {
        name: "2. SlateDB CRUD + WriteBatch + Scan + L0 Flush",
        duration_ms: t0.elapsed().as_millis(),
        detail: "put/get/delete/batch/scan/seek + WAL & MemTable L0 SST flush verified".to_string(),
    });

    // Stage 3: Cold reopen durability & object layout inspection.
    let t0 = Instant::now();
    let layout = verify_reopen_and_layout(Arc::clone(&store), db_prefix).await?;
    stages.push(StageResult {
        name: "3. Cold Reopen & OSS Layout Inspection",
        duration_ms: t0.elapsed().as_millis(),
        detail: format!(
            "reopened cleanly; {} objects ({} bytes), dirs={:?}",
            layout.total_objects, layout.total_bytes, layout.by_subdir
        ),
    });

    // Stage 4: Stateless DbReader (FollowLatest) reading committed data.
    let t0 = Instant::now();
    verify_stateless_reader(Arc::clone(&store), db_prefix).await?;
    stages.push(StageResult {
        name: "4. Stateless DbReader (Single-Writer / Multi-Reader)",
        duration_ms: t0.elapsed().as_millis(),
        detail: "DbReader(FollowLatest) read committed keys & tombstones".to_string(),
    });

    // Stage 5: Writer Fencing (split-brain protection via atomic manifest/WAL creation).
    let t0 = Instant::now();
    verify_writer_fencing(Arc::clone(&store), db_prefix).await?;
    stages.push(StageResult {
        name: "5. Writer Fencing (Split-Brain Protection)",
        duration_ms: t0.elapsed().as_millis(),
        detail:
            "stale writer fenced with ErrorKind::Closed(CloseReason::Fenced); new writer intact"
                .to_string(),
    });

    // Stage 6: Detached Checkpoint & Pinned Historical Read.
    let t0 = Instant::now();
    let cp_detail = verify_checkpoint_isolation(Arc::clone(&store), db_prefix).await?;
    stages.push(StageResult {
        name: "6. Detached Checkpoint & Snapshot Isolation",
        duration_ms: t0.elapsed().as_millis(),
        detail: cp_detail,
    });

    let final_layout = inspect_layout(&store, db_prefix).await?;

    Ok(E2eReport {
        db_prefix: db_prefix.to_string(),
        stages,
        layout: final_layout,
    })
}

/// Stage 1: Directly verify that `PutMode::Create` enforces atomic no-overwrite.
///
/// On Alibaba Cloud OSS, this fails loudly if the target bucket has versioning
/// enabled (because `x-oss-forbid-overwrite: true` is ignored on versioned buckets).
async fn verify_atomic_create_cas(store: &Arc<dyn ObjectStore>, db_prefix: &str) -> Result<()> {
    let probe_path = ObjectPath::from(format!("{db_prefix}/_cas_probe"));
    let create_opts = PutOptions::from(PutMode::Create);

    store
        .put_opts(
            &probe_path,
            PutPayload::from_static(b"v1-original"),
            create_opts.clone(),
        )
        .await
        .context("first PutMode::Create failed unexpectedly")?;

    let dup_res = store
        .put_opts(
            &probe_path,
            PutPayload::from_static(b"v2-overwrite"),
            create_opts,
        )
        .await;

    match dup_res {
        Err(object_store::Error::AlreadyExists { .. }) => {}
        Ok(_) => {
            let _ = store.delete(&probe_path).await;
            bail!(
                "CAS VIOLATION: duplicate PutMode::Create succeeded instead of returning \
                 AlreadyExists (check whether OSS bucket versioning is enabled!)"
            );
        }
        Err(other) => {
            let _ = store.delete(&probe_path).await;
            bail!("unexpected error on duplicate PutMode::Create: {other:?}");
        }
    }

    let got = store
        .get(&probe_path)
        .await
        .context("failed to read back CAS probe object")?
        .bytes()
        .await?;
    if got != Bytes::from_static(b"v1-original") {
        let _ = store.delete(&probe_path).await;
        bail!("CAS probe payload was mutated: got {got:?}");
    }

    store
        .delete(&probe_path)
        .await
        .context("failed to delete CAS probe object")?;
    Ok(())
}

/// Stage 2: Exercise put/get/delete, WriteBatch, scan, seek, and explicit L0 SST flush.
async fn verify_crud_scan_and_flush(store: Arc<dyn ObjectStore>, db_prefix: &str) -> Result<()> {
    let db = Db::open(db_prefix, store)
        .await
        .context("failed to open SlateDB writer in stage 2")?;

    db.put(b"alpha", b"v1").await?;
    assert_eq!(db.get(b"alpha").await?, Some(Bytes::from_static(b"v1")));

    db.put(b"ephemeral", b"to-be-deleted").await?;
    db.delete(b"ephemeral").await?;
    assert_eq!(db.get(b"ephemeral").await?, None);

    let mut batch = WriteBatch::new();
    for i in 1..=5 {
        batch.put(
            format!("k{i:02}").as_bytes(),
            format!("val-{i:02}").as_bytes(),
        );
    }
    db.write(batch).await?;

    // Bounded range scan
    let mut iter = db.scan("k02"..="k04").await?;
    let mut seen = Vec::new();
    while let Some(kv) = iter.next().await? {
        seen.push((
            String::from_utf8(kv.key.to_vec())?,
            String::from_utf8(kv.value.to_vec())?,
        ));
    }
    assert_eq!(
        seen,
        vec![
            ("k02".to_string(), "val-02".to_string()),
            ("k03".to_string(), "val-03".to_string()),
            ("k04".to_string(), "val-04".to_string()),
        ]
    );

    // Seek test
    let mut seek_iter = db.scan(..).await?;
    seek_iter.seek(b"k05").await?;
    let kv = seek_iter.next().await?.context("expected k05 after seek")?;
    assert_eq!(kv.key, Bytes::from_static(b"k05"));
    assert_eq!(kv.value, Bytes::from_static(b"val-05"));

    // Flush WAL and MemTable so both wal/ and compacted/ L0 SST objects materialize on OSS.
    db.flush().await?;
    db.flush_with_options(FlushOptions {
        flush_type: FlushType::MemTable,
    })
    .await?;

    db.close().await?;
    Ok(())
}

/// Stage 3: Inspect OSS directory layout and verify cold reopen recovers all data.
async fn verify_reopen_and_layout(
    store: Arc<dyn ObjectStore>,
    db_prefix: &str,
) -> Result<LayoutSummary> {
    let layout = inspect_layout(&store, db_prefix).await?;
    if !layout.by_subdir.contains_key("manifest") {
        bail!(
            "expected `manifest/` objects on store, found {:?}",
            layout.by_subdir
        );
    }
    if !layout.by_subdir.contains_key("compacted") {
        bail!(
            "expected `compacted/` L0 SST objects after MemTable flush, found {:?}",
            layout.by_subdir
        );
    }

    let db = Db::open(db_prefix, store)
        .await
        .context("failed to reopen SlateDB from cold state")?;
    assert_eq!(db.get(b"alpha").await?, Some(Bytes::from_static(b"v1")));
    assert_eq!(db.get(b"ephemeral").await?, None);
    assert_eq!(db.get(b"k03").await?, Some(Bytes::from_static(b"val-03")));
    db.close().await?;

    Ok(layout)
}

/// Stage 4: Verify stateless DbReader reads committed state independently.
async fn verify_stateless_reader(store: Arc<dyn ObjectStore>, db_prefix: &str) -> Result<()> {
    let reader = DbReader::open(
        db_prefix,
        store,
        DbReaderMode::FollowLatest,
        DbReaderOptions::default(),
    )
    .await
    .context("failed to open stateless DbReader")?;

    assert_eq!(reader.get(b"alpha").await?, Some(Bytes::from_static(b"v1")));
    assert_eq!(reader.get(b"ephemeral").await?, None);
    assert_eq!(
        reader.get(b"k05").await?,
        Some(Bytes::from_static(b"val-05"))
    );

    reader.close().await?;
    Ok(())
}

/// Stage 5: Verify that opening a second writer fences the stale writer via OSS CAS.
async fn verify_writer_fencing(store: Arc<dyn ObjectStore>, db_prefix: &str) -> Result<()> {
    let writer_a = Db::open(db_prefix, Arc::clone(&store))
        .await
        .context("failed to open writer_a")?;
    writer_a.put(b"fence_key", b"from_a_before_fence").await?;
    writer_a.flush().await?;

    // Opening writer_b bumps writer_epoch in manifest via PutMode::Create and
    // fences writer_a's next WAL/manifest write.
    let writer_b = Db::open(db_prefix, Arc::clone(&store))
        .await
        .context("failed to open writer_b")?;
    writer_b.put(b"fence_key", b"from_b_winner").await?;
    writer_b.flush().await?;

    // Stale writer_a attempts to write and flush — must observe Fenced.
    let stale_result = async {
        writer_a.put(b"fence_key", b"from_a_zombie").await?;
        writer_a
            .flush_with_options(FlushOptions {
                flush_type: FlushType::MemTable,
            })
            .await
    }
    .await;

    match stale_result {
        Err(err) if err.kind() == ErrorKind::Closed(CloseReason::Fenced) => {}
        Err(err) => {
            bail!(
                "expected ErrorKind::Closed(CloseReason::Fenced) for stale writer_a, got {:?}: {}",
                err.kind(),
                err
            );
        }
        Ok(()) => {
            bail!("FENCING FAILURE: stale writer_a wrote & flushed after writer_b took over!");
        }
    }

    // Confirm writer_b remains healthy and zombie write did not overwrite winner value.
    assert_eq!(
        writer_b.get(b"fence_key").await?,
        Some(Bytes::from_static(b"from_b_winner"))
    );
    writer_b
        .flush_with_options(FlushOptions {
            flush_type: FlushType::MemTable,
        })
        .await?;
    writer_b.close().await?;

    // Cleanly ignore already-fenced error on close of writer_a.
    let _ = writer_a.close().await;
    Ok(())
}

/// Stage 6: Verify detached checkpoints pin historical state across subsequent mutations.
async fn verify_checkpoint_isolation(
    store: Arc<dyn ObjectStore>,
    db_prefix: &str,
) -> Result<String> {
    let admin = AdminBuilder::new(db_prefix, Arc::clone(&store)).build();
    let cp = admin
        .create_detached_checkpoint(&CheckpointOptions {
            lifetime: Some(Duration::from_secs(3600)),
            ..Default::default()
        })
        .await
        .context("failed to create detached checkpoint")?;

    // Mutate live DB after checkpoint creation.
    let writer = Db::open(db_prefix, Arc::clone(&store)).await?;
    writer.put(b"alpha", b"v2-after-checkpoint").await?;
    writer
        .flush_with_options(FlushOptions {
            flush_type: FlushType::MemTable,
        })
        .await?;
    writer.close().await?;

    // Pinned checkpoint reader must still observe v1.
    let pinned_reader = DbReader::open(
        db_prefix,
        Arc::clone(&store),
        DbReaderMode::Checkpoint(cp.id),
        DbReaderOptions::default(),
    )
    .await
    .context("failed to open checkpoint-pinned DbReader")?;
    assert_eq!(
        pinned_reader.get(b"alpha").await?,
        Some(Bytes::from_static(b"v1"))
    );
    pinned_reader.close().await?;

    // Latest reader must observe v2.
    let latest_reader = DbReader::open(
        db_prefix,
        store,
        DbReaderMode::FollowLatest,
        DbReaderOptions::default(),
    )
    .await?;
    assert_eq!(
        latest_reader.get(b"alpha").await?,
        Some(Bytes::from_static(b"v2-after-checkpoint"))
    );
    latest_reader.close().await?;

    Ok(format!(
        "checkpoint {} (manifest #{}) preserved alpha=v1 while latest saw v2",
        cp.id, cp.manifest_id
    ))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::store::{build_memory_store, cleanup_prefix};

    #[tokio::test]
    async fn full_e2e_passes_on_in_memory_store() -> Result<()> {
        let store = build_memory_store();
        let prefix = "test-db";

        let report = run_e2e(Arc::clone(&store), prefix).await?;
        assert_eq!(report.stages.len(), 6);
        assert!(report.layout.total_objects > 0);
        assert!(report.layout.by_subdir.contains_key("manifest"));
        assert!(report.layout.by_subdir.contains_key("compacted"));

        let deleted = cleanup_prefix(&store, prefix).await?;
        assert_eq!(deleted, report.layout.total_objects);

        let after = inspect_layout(&store, prefix).await?;
        assert_eq!(after.total_objects, 0);
        Ok(())
    }
}
