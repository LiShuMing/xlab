use std::collections::HashMap;
use std::sync::Arc;
use async_trait::async_trait;
use crate::embedding::Embedder;
use crate::index::IndexConfig;
use crate::storage::StorageConfig;
use crate::types::*;
use crate::UmbraResult;
use crate::UmbraError;

pub mod add;
pub mod crud;
pub mod history;
pub mod search;

/// Core memory operations trait.
#[async_trait]
pub trait MemoryOps: Send + Sync {
    async fn add(
        &self,
        messages: Vec<Message>,
        filters: MemoryFilters,
        metadata: HashMap<String, String>,
    ) -> UmbraResult<Vec<AddResult>>;

    async fn search(
        &self,
        query: &str,
        filters: MemoryFilters,
        top_k: usize,
        threshold: f64,
        rerank: bool,
    ) -> UmbraResult<Vec<SearchResult>>;

    async fn get(&self, memory_id: &str) -> UmbraResult<Option<SearchResult>>;

    async fn update(&self, memory_id: &str, data: &str) -> UmbraResult<()>;

    async fn delete(&self, memory_id: &str) -> UmbraResult<()>;

    async fn delete_all(&self, filters: MemoryFilters) -> UmbraResult<u64>;

    async fn get_history(&self, memory_id: &str) -> UmbraResult<Vec<HistoryRecord>>;
}

/// Concrete implementation of MemoryOps.
pub struct MemoryOpsImpl {
    pub embedder: Arc<dyn Embedder>,
    pub index_config: IndexConfig,
    pub storage_config: StorageConfig,
}

impl MemoryOpsImpl {
    pub fn new(
        embedder: Arc<dyn Embedder>,
        index_config: IndexConfig,
        storage_config: StorageConfig,
    ) -> Self {
        Self { embedder, index_config, storage_config }
    }
}

// Simple utilities
fn content_hash(s: &str) -> String {
    use std::hash::{Hash, Hasher};
    use std::collections::hash_map::DefaultHasher;
    let mut h = DefaultHasher::new();
    s.hash(&mut h);
    format!("{:x}", h.finish())
}

#[allow(dead_code)]
fn lemmatize(s: &str) -> String {
    s.to_lowercase().trim().to_string()
}

#[async_trait]
impl MemoryOps for MemoryOpsImpl {
    async fn add(
        &self,
        messages: Vec<Message>,
        filters: MemoryFilters,
        _metadata: HashMap<String, String>,
    ) -> UmbraResult<Vec<AddResult>> {
        filters.validate()?;

        // Phase 1: Parse messages — filter system, extract content
        let valid: Vec<&Message> = messages.iter().filter(|m| m.role != "system").collect();
        if valid.is_empty() {
            return Ok(vec![]);
        }

        // Phase 2: Batch embed
        let texts: Vec<&str> = valid.iter().map(|m| m.content.as_str()).collect();
        let _embeddings = self.embedder.embed_batch(&texts).await?;

        // Phase 3: Hash dedup (batch-internal only — cross-batch requires storage)
        let mut results = Vec::new();
        let mut seen = std::collections::HashSet::new();

        for msg in valid.iter() {
            let hash = content_hash(&msg.content);
            if !seen.insert(hash.clone()) {
                continue; // Batch-internal duplicate
            }

            let memory_id = uuid::Uuid::new_v4().to_string();

            results.push(AddResult {
                id: memory_id,
                memory: msg.content.clone(),
                event: "ADD".to_string(),
                actor_id: msg.name.clone(),
                role: Some(msg.role.clone()),
            });
        }

        Ok(results)
    }

    async fn search(
        &self,
        _query: &str,
        filters: MemoryFilters,
        _top_k: usize,
        _threshold: f64,
        _rerank: bool,
    ) -> UmbraResult<Vec<SearchResult>> {
        filters.validate()?;
        // Stub: full impl when storage is wired
        Ok(vec![])
    }

    async fn get(&self, _memory_id: &str) -> UmbraResult<Option<SearchResult>> {
        Ok(None)
    }

    async fn update(&self, _memory_id: &str, _data: &str) -> UmbraResult<()> {
        Err(UmbraError::Internal("not implemented".into()))
    }

    async fn delete(&self, _memory_id: &str) -> UmbraResult<()> {
        Err(UmbraError::Internal("not implemented".into()))
    }

    async fn delete_all(&self, filters: MemoryFilters) -> UmbraResult<u64> {
        filters.validate()?;
        Ok(0)
    }

    async fn get_history(&self, _memory_id: &str) -> UmbraResult<Vec<HistoryRecord>> {
        Ok(vec![])
    }
}
