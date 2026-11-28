use std::collections::BTreeMap;
use std::fmt;
use std::ops::Range;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;

use anyhow::{bail, Context, Result};
use async_trait::async_trait;
use bytes::Bytes;
use futures::stream::BoxStream;
use futures::TryStreamExt;
use object_store::memory::InMemory;
use object_store::path::Path as ObjectPath;
use object_store::{
    CopyOptions, GetOptions, GetResult, ListResult, MultipartUpload, ObjectMeta, ObjectStore,
    ObjectStoreExt, PutMode, PutMultipartOptions, PutOptions, PutPayload, PutResult, RenameOptions,
};
use object_store_opendal::OpendalStore;
use opendal::services::Oss;
use opendal::Operator;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::config::OssConfig;

/// Build an in-memory [`ObjectStore`] for fast offline verification.
pub fn build_memory_store() -> Arc<dyn ObjectStore> {
    Arc::new(InMemory::new())
}

/// Build an [`ObjectStore`] backed by Alibaba Cloud OSS via Apache OpenDAL.
///
/// OpenDAL's native OSS service maps `object_store::PutMode::Create`
/// (`if_not_exists(true)`) to `x-oss-forbid-overwrite: true` and converts OSS
/// `409 FileAlreadyExists` back to `object_store::Error::AlreadyExists`.
pub fn build_oss_store(cfg: &OssConfig) -> Result<Arc<dyn ObjectStore>> {
    let builder = Oss::default()
        .endpoint(&cfg.endpoint)
        .bucket(&cfg.bucket)
        .root(&cfg.root)
        .access_key_id(&cfg.access_key_id)
        .access_key_secret(&cfg.access_key_secret);

    let operator = Operator::new(builder).context("failed to initialize OpenDAL OSS operator")?;

    Ok(Arc::new(OpendalStore::new(operator)))
}

/// Fail-fast startup guard verifying that `PutMode::Create` is strictly atomic.
///
/// Reusable across `vela/storage` or downstream services: fails immediately if
/// an Alibaba Cloud OSS bucket has versioning enabled/suspended (which silently
/// disables `x-oss-forbid-overwrite: true`).
pub async fn ensure_cas_supported(store: &Arc<dyn ObjectStore>, prefix: &str) -> Result<()> {
    let probe_path = ObjectPath::from(format!(
        "{}/_cas_probe_{}",
        prefix.trim_matches('/'),
        Uuid::new_v4().simple()
    ));
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

/// Wire-level object store operation counters captured beneath SlateDB.
#[derive(Debug, Default, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct ObjectStoreCounters {
    pub put_ops: u64,
    pub put_create_ops: u64,
    pub put_bytes: u64,
    pub get_ops: u64,
    pub get_range_ops: u64,
    pub get_bytes: u64,
    pub list_ops: u64,
    pub delete_ops: u64,
}

impl ObjectStoreCounters {
    pub fn delta_since(&self, earlier: &Self) -> Self {
        Self {
            put_ops: self.put_ops.saturating_sub(earlier.put_ops),
            put_create_ops: self.put_create_ops.saturating_sub(earlier.put_create_ops),
            put_bytes: self.put_bytes.saturating_sub(earlier.put_bytes),
            get_ops: self.get_ops.saturating_sub(earlier.get_ops),
            get_range_ops: self.get_range_ops.saturating_sub(earlier.get_range_ops),
            get_bytes: self.get_bytes.saturating_sub(earlier.get_bytes),
            list_ops: self.list_ops.saturating_sub(earlier.list_ops),
            delete_ops: self.delete_ops.saturating_sub(earlier.delete_ops),
        }
    }
}

#[derive(Default)]
struct AtomicCounters {
    put_ops: AtomicU64,
    put_create_ops: AtomicU64,
    put_bytes: AtomicU64,
    get_ops: AtomicU64,
    get_range_ops: AtomicU64,
    get_bytes: AtomicU64,
    list_ops: AtomicU64,
    delete_ops: AtomicU64,
}

/// Thin `ObjectStore` decorator that records exact backend request and byte counts.
pub struct CountingObjectStore {
    inner: Arc<dyn ObjectStore>,
    counters: Arc<AtomicCounters>,
}

impl CountingObjectStore {
    pub fn new(inner: Arc<dyn ObjectStore>) -> Arc<Self> {
        Arc::new(Self {
            inner,
            counters: Arc::new(AtomicCounters::default()),
        })
    }

    pub fn snapshot(&self) -> ObjectStoreCounters {
        ObjectStoreCounters {
            put_ops: self.counters.put_ops.load(Ordering::Relaxed),
            put_create_ops: self.counters.put_create_ops.load(Ordering::Relaxed),
            put_bytes: self.counters.put_bytes.load(Ordering::Relaxed),
            get_ops: self.counters.get_ops.load(Ordering::Relaxed),
            get_range_ops: self.counters.get_range_ops.load(Ordering::Relaxed),
            get_bytes: self.counters.get_bytes.load(Ordering::Relaxed),
            list_ops: self.counters.list_ops.load(Ordering::Relaxed),
            delete_ops: self.counters.delete_ops.load(Ordering::Relaxed),
        }
    }
}

impl fmt::Display for CountingObjectStore {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "CountingObjectStore({})", self.inner)
    }
}

impl fmt::Debug for CountingObjectStore {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("CountingObjectStore")
            .field("counters", &self.snapshot())
            .finish()
    }
}

#[async_trait]
impl ObjectStore for CountingObjectStore {
    async fn put_opts(
        &self,
        location: &ObjectPath,
        payload: PutPayload,
        opts: PutOptions,
    ) -> object_store::Result<PutResult> {
        let len = payload.content_length() as u64;
        self.counters.put_ops.fetch_add(1, Ordering::Relaxed);
        if matches!(opts.mode, PutMode::Create) {
            self.counters.put_create_ops.fetch_add(1, Ordering::Relaxed);
        }
        self.counters.put_bytes.fetch_add(len, Ordering::Relaxed);
        self.inner.put_opts(location, payload, opts).await
    }

    async fn put_multipart_opts(
        &self,
        location: &ObjectPath,
        opts: PutMultipartOptions,
    ) -> object_store::Result<Box<dyn MultipartUpload>> {
        self.counters.put_ops.fetch_add(1, Ordering::Relaxed);
        self.inner.put_multipart_opts(location, opts).await
    }

    async fn get_opts(
        &self,
        location: &ObjectPath,
        options: GetOptions,
    ) -> object_store::Result<GetResult> {
        self.counters.get_ops.fetch_add(1, Ordering::Relaxed);
        let res = self.inner.get_opts(location, options).await?;
        let nbytes = res.range.end.saturating_sub(res.range.start);
        self.counters.get_bytes.fetch_add(nbytes, Ordering::Relaxed);
        Ok(res)
    }

    async fn get_ranges(
        &self,
        location: &ObjectPath,
        ranges: &[Range<u64>],
    ) -> object_store::Result<Vec<Bytes>> {
        self.counters.get_range_ops.fetch_add(1, Ordering::Relaxed);
        let out = self.inner.get_ranges(location, ranges).await?;
        let total: u64 = out.iter().map(|b| b.len() as u64).sum();
        self.counters.get_bytes.fetch_add(total, Ordering::Relaxed);
        Ok(out)
    }

    fn delete_stream(
        &self,
        locations: BoxStream<'static, object_store::Result<ObjectPath>>,
    ) -> BoxStream<'static, object_store::Result<ObjectPath>> {
        let counters = Arc::clone(&self.counters);
        let tracked = locations.map_ok(move |path| {
            counters.delete_ops.fetch_add(1, Ordering::Relaxed);
            path
        });
        self.inner.delete_stream(Box::pin(tracked))
    }

    fn list(
        &self,
        prefix: Option<&ObjectPath>,
    ) -> BoxStream<'static, object_store::Result<ObjectMeta>> {
        self.counters.list_ops.fetch_add(1, Ordering::Relaxed);
        self.inner.list(prefix)
    }

    async fn list_with_delimiter(
        &self,
        prefix: Option<&ObjectPath>,
    ) -> object_store::Result<ListResult> {
        self.counters.list_ops.fetch_add(1, Ordering::Relaxed);
        self.inner.list_with_delimiter(prefix).await
    }

    async fn copy_opts(
        &self,
        from: &ObjectPath,
        to: &ObjectPath,
        options: CopyOptions,
    ) -> object_store::Result<()> {
        self.counters.put_ops.fetch_add(1, Ordering::Relaxed);
        self.inner.copy_opts(from, to, options).await
    }

    async fn rename_opts(
        &self,
        from: &ObjectPath,
        to: &ObjectPath,
        options: RenameOptions,
    ) -> object_store::Result<()> {
        self.counters.put_ops.fetch_add(1, Ordering::Relaxed);
        self.counters.delete_ops.fetch_add(1, Ordering::Relaxed);
        self.inner.rename_opts(from, to, options).await
    }
}

/// Summary of object paths persisted under a SlateDB prefix.
#[derive(Debug, Default, Clone, Serialize, Deserialize)]
pub struct LayoutSummary {
    pub total_objects: usize,
    pub total_bytes: u64,
    pub by_subdir: BTreeMap<String, usize>,
    pub sample_paths: Vec<String>,
}

/// Inspect the objects currently persisted under `prefix`.
pub async fn inspect_layout(store: &Arc<dyn ObjectStore>, prefix: &str) -> Result<LayoutSummary> {
    let list_prefix = ObjectPath::from(prefix);
    let metas: Vec<_> = store
        .list(Some(&list_prefix))
        .try_collect()
        .await
        .with_context(|| format!("failed to list objects under prefix `{prefix}`"))?;

    let trimmed_prefix = prefix.trim_matches('/');
    let mut summary = LayoutSummary::default();

    for meta in metas {
        summary.total_objects += 1;
        summary.total_bytes += meta.size;

        let full = meta.location.to_string();
        let rel = full
            .strip_prefix(trimmed_prefix)
            .unwrap_or(&full)
            .trim_start_matches('/');
        let bucket_dir = rel
            .split('/')
            .next()
            .filter(|s| !s.is_empty())
            .unwrap_or("<root>")
            .to_string();
        *summary.by_subdir.entry(bucket_dir).or_insert(0) += 1;

        if summary.sample_paths.len() < 12 {
            summary.sample_paths.push(full);
        }
    }

    Ok(summary)
}

/// Delete all objects under `prefix` and return the count of deleted objects.
pub async fn cleanup_prefix(store: &Arc<dyn ObjectStore>, prefix: &str) -> Result<usize> {
    let list_prefix = ObjectPath::from(prefix);
    let metas: Vec<_> = store
        .list(Some(&list_prefix))
        .try_collect()
        .await
        .with_context(|| format!("failed to list objects for cleanup under `{prefix}`"))?;

    let mut deleted = 0usize;
    for meta in metas {
        store
            .delete(&meta.location)
            .await
            .with_context(|| format!("failed to delete object `{}`", meta.location))?;
        deleted += 1;
    }

    Ok(deleted)
}
