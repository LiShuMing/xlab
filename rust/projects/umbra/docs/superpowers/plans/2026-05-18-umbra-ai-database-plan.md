# Umbra AI Database — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform umbra from a Cranelift JIT PoC into an AI-native memory database service (DataFusion + Iceberg + Lance), exposing gRPC + Arrow Flight SQL interfaces.

**Architecture:** Three-layer Rust workspace. `umbra-core` (engine: embedding, storage, index, query, ops). `umbra-server` (tonic gRPC + DataFusion Flight SQL). Lance handles vector/physical storage; Iceberg manages table metadata; DataFusion provides SQL querying.

**Tech Stack:** Rust 2021, DataFusion, Lance (with lance-datafusion), iceberg-rust, tonic/prost, Arrow, tokio, figment (config), uuid, chrono.

---

## File Structure Map

```
umbra/
├── Cargo.toml                         # Workspace root (MODIFY)
├── src/main.rs                         # DELETE (old JIT PoC)
├── umbra-core/
│   ├── Cargo.toml
│   └── src/
│       ├── lib.rs                      # Core crate root, re-exports
│       ├── types.rs                    # Shared data types (Message, MemoryFilters, etc.)
│       ├── embedding/
│       │   ├── mod.rs                  # Embedder trait
│       │   └── openai.rs              # OpenAI-compatible provider
│       ├── storage/
│       │   ├── mod.rs                  # StorageLayer: open/create/manage datasets
│       │   ├── catalog.rs             # Iceberg catalog wrapper
│       │   ├── write.rs               # Batch append to Lance + Iceberg commit
│       │   └── scan.rs                # Scan with pushdown
│       ├── index/
│       │   ├── mod.rs                  # Index traits
│       │   ├── vector.rs              # Lance ANN search wrapper
│       │   ├── fulltext.rs            # Lance FTS/BM25 wrapper
│       │   └── entity.rs             # Entity store + boost computation
│       ├── query/
│       │   ├── mod.rs                  # DataFusion table + UDF registration
│       │   ├── tablefunc.rs           # umbra_search UDTF
│       │   └── udf.rs                 # Vector/similarity UDFs
│       └── ops/
│           ├── mod.rs                  # MemoryOps trait
│           ├── add.rs                 # Write pipeline
│           ├── search.rs             # Multi-signal fusion retrieval
│           ├── crud.rs               # get/update/delete/delete_all
│           └── history.rs            # get_history
└── umbra-server/
    ├── Cargo.toml
    ├── proto/
    │   └── umbra.proto                # MemoryService protobuf
    ├── build.rs                       # tonic-build for protobuf
    └── src/
        ├── lib.rs                     # Server crate root
        ├── config.rs                  # Configuration loading (figment)
        ├── service.rs                 # gRPC MemoryService impl
        ├── flight.rs                  # Arrow Flight SQL server
        └── main.rs                    # Server entry point
```

---

### Task 0: Workspace Scaffold

**Files:**
- Modify: `Cargo.toml`
- Create: `umbra-core/Cargo.toml`, `umbra-core/src/lib.rs`
- Create: `umbra-server/Cargo.toml`, `umbra-server/build.rs`, `umbra-server/src/lib.rs`, `umbra-server/src/main.rs`
- Create: `umbra-server/proto/umbra.proto` (placeholder)
- Delete: `src/main.rs`

- [ ] **Step 1: Rewrite root Cargo.toml as workspace**

```toml
[workspace]
members = ["umbra-core", "umbra-server"]
resolver = "2"

[workspace.package]
version = "0.1.0"
edition = "2021"
license = "MIT"

[workspace.dependencies]
tokio = { version = "1", features = ["full"] }
tonic = "0.12"
prost = "0.13"
tonic-prost = "0.12"
arrow = "53"
arrow-schema = "53"
arrow-array = "53"
lance = "0.20"
lance-datafusion = "0.20"
datafusion = "43"
iceberg = "0.4"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
uuid = { version = "1", features = ["v4"] }
chrono = { version = "0.4", features = ["serde"] }
figment = { version = "0.10", features = ["toml", "env"] }
reqwest = { version = "0.12", features = ["json"] }
anyhow = "1"
thiserror = "2"
tracing = "0.1"
tracing-subscriber = "0.3"
```

- [ ] **Step 2: Create umbra-core Cargo.toml**

```toml
[package]
name = "umbra-core"
version.workspace = true
edition.workspace = true

[dependencies]
tokio.workspace = true
arrow.workspace = true
arrow-schema.workspace = true
arrow-array.workspace = true
lance.workspace = true
lance-datafusion.workspace = true
datafusion.workspace = true
iceberg.workspace = true
serde.workspace = true
serde_json.workspace = true
uuid.workspace = true
chrono.workspace = true
reqwest.workspace = true
anyhow.workspace = true
thiserror.workspace = true
tracing.workspace = true
```

- [ ] **Step 3: Create umbra-server Cargo.toml**

```toml
[package]
name = "umbra-server"
version.workspace = true
edition.workspace = true

[dependencies]
umbra-core = { path = "../umbra-core" }
tokio.workspace = true
tonic.workspace = true
prost.workspace = true
datafusion.workspace = true
figment.workspace = true
serde.workspace = true
serde_json.workspace = true
anyhow.workspace = true
tracing.workspace = true
tracing-subscriber.workspace = true

[build-dependencies]
tonic-prost.workspace = true
```

- [ ] **Step 4: Create umbra-server/build.rs**

```rust
fn main() -> Result<(), Box<dyn std::error::Error>> {
    tonic_prost::configure::configure()
        .build_server(true)
        .build_client(false)
        .compile_protos(&["proto/umbra.proto"], &["proto/"])?;
    Ok(())
}
```

- [ ] **Step 5: Create placeholder files**

Create umbra-core/src/lib.rs:
```rust
//! Umbra AI memory database — core engine.
```

Create umbra-server/src/lib.rs:
```rust
//! Umbra AI memory database — gRPC + Flight SQL server.

pub mod config;
pub mod flight;
pub mod service;
```

Create umbra-server/src/main.rs:
```rust
fn main() {
    println!("umbra-server placeholder");
}
```

Create umbra-server/proto/umbra.proto:
```protobuf
syntax = "proto3";
package umbra;
```

- [ ] **Step 6: Delete old single-crate files**

```bash
rm -rf /Users/lism/work/xlab/rust/projects/umbra/src
```

- [ ] **Step 7: Build check**

Run: `cargo check`
Expected: Compiles successfully with placeholder files.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: scaffold umbra workspace with umbra-core + umbra-server crates"
```

---

### Task 1: Core Types

**Files:**
- Create: `umbra-core/src/types.rs`
- Modify: `umbra-core/src/lib.rs`

- [ ] **Step 1: Write types.rs**

```rust
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// A chat message.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    pub role: String,
    pub content: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
}

/// Session scoping filters. At least one of user_id, agent_id, run_id must be set.
#[derive(Debug, Clone, Default)]
pub struct MemoryFilters {
    pub user_id: Option<String>,
    pub agent_id: Option<String>,
    pub run_id: Option<String>,
}

impl MemoryFilters {
    /// Build deterministic session scope string for message windowing.
    pub fn to_session_scope(&self) -> String {
        let mut parts = Vec::new();
        let mut keys = Vec::new();
        if self.user_id.is_some() { keys.push(("user_id", self.user_id.as_ref().unwrap())); }
        if self.agent_id.is_some() { keys.push(("agent_id", self.agent_id.as_ref().unwrap())); }
        if self.run_id.is_some() { keys.push(("run_id", self.run_id.as_ref().unwrap())); }
        keys.sort_by_key(|k| k.0);
        for (k, v) in keys {
            parts.push(format!("{}={}", k, v));
        }
        parts.join("&")
    }

    /// Validate at least one entity ID is present.
    pub fn validate(&self) -> Result<(), crate::UmbraError> {
        if self.user_id.is_none() && self.agent_id.is_none() && self.run_id.is_none() {
            return Err(crate::UmbraError::Validation(
                "At least one of user_id, agent_id, run_id must be provided".into()
            ));
        }
        Ok(())
    }

    pub fn to_payload_pairs(&self) -> Vec<(String, String)> {
        let mut pairs = Vec::new();
        if let Some(ref v) = self.user_id { pairs.push(("user_id".into(), v.clone())); }
        if let Some(ref v) = self.agent_id { pairs.push(("agent_id".into(), v.clone())); }
        if let Some(ref v) = self.run_id { pairs.push(("run_id".into(), v.clone())); }
        pairs
    }
}

/// Result of an add operation.
#[derive(Debug, Clone, Serialize)]
pub struct AddResult {
    pub id: String,
    pub memory: String,
    pub event: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub actor_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub role: Option<String>,
}

/// Result of a search operation.
#[derive(Debug, Clone, Serialize)]
pub struct SearchResult {
    pub id: String,
    pub memory: String,
    pub score: f64,
    pub created_at: Option<String>,
    pub updated_at: Option<String>,
    pub user_id: Option<String>,
    pub agent_id: Option<String>,
    pub run_id: Option<String>,
    pub actor_id: Option<String>,
    pub role: Option<String>,
    pub metadata: HashMap<String, String>,
}

/// Internal scored memory during retrieval.
#[derive(Debug, Clone)]
pub struct ScoredMemory {
    pub id: String,
    pub memory: String,
    pub score: f64,
    pub payload: HashMap<String, String>,
}

/// A history record for a memory change.
#[derive(Debug, Clone, Serialize)]
pub struct HistoryRecord {
    pub id: String,
    pub memory_id: String,
    pub old_memory: Option<String>,
    pub new_memory: Option<String>,
    pub event: String,
    pub actor_id: Option<String>,
    pub created_at: Option<String>,
    pub is_deleted: i32,
}

/// Error type for the umbra-core crate.
#[derive(Debug, thiserror::Error)]
pub enum UmbraError {
    #[error("validation error: {0}")]
    Validation(String),
    #[error("not found: {0}")]
    NotFound(String),
    #[error("storage error: {0}")]
    Storage(String),
    #[error("embedding error: {0}")]
    Embedding(String),
    #[error("internal error: {0}")]
    Internal(String),
    #[error("iceberg error: {0}")]
    Iceberg(String),
}
```

- [ ] **Step 2: Update lib.rs to export types**

```rust
pub mod types;
pub mod error;
pub use types::*;
pub use error::*;
```

Wait — we defined UmbraError inside types.rs. Let me split it into a separate error module:

- [ ] **Step 3: Create umbra-core/src/error.rs**

```rust
#[derive(Debug, thiserror::Error)]
pub enum UmbraError {
    #[error("validation error: {0}")]
    Validation(String),
    #[error("not found: {0}")]
    NotFound(String),
    #[error("storage error: {0}")]
    Storage(String),
    #[error("embedding error: {0}")]
    Embedding(String),
    #[error("internal error: {0}")]
    Internal(String),
    #[error("iceberg error: {0}")]
    Iceberg(String),
}

pub type UmbraResult<T> = Result<T, UmbraError>;
```

- [ ] **Step 4: Update lib.rs**

```rust
pub mod error;
pub mod types;

pub use error::{UmbraError, UmbraResult};
pub use types::*;
```

- [ ] **Step 5: Build check**

Run: `cargo check`
Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add umbra-core/src/
git commit -m "feat: add core types (Message, MemoryFilters, Result types, UmbraError)"
```

---

### Task 2: Embedding Abstraction

**Files:**
- Create: `umbra-core/src/embedding/mod.rs`
- Create: `umbra-core/src/embedding/openai.rs`
- Modify: `umbra-core/src/lib.rs`

- [ ] **Step 1: Write Embedder trait (mod.rs)**

```rust
use async_trait::async_trait;
use crate::UmbraResult;

/// A batch of embedding vectors. Each inner Vec has dimension D.
pub type EmbeddingBatch = Vec<Vec<f32>>;

#[async_trait]
pub trait Embedder: Send + Sync {
    /// Embed a single text into a vector.
    async fn embed(&self, text: &str) -> UmbraResult<Vec<f32>>;

    /// Embed multiple texts. Default implementation calls embed() in a loop.
    async fn embed_batch(&self, texts: &[&str]) -> UmbraResult<EmbeddingBatch> {
        let mut results = Vec::with_capacity(texts.len());
        for text in texts {
            results.push(self.embed(text).await?);
        }
        Ok(results)
    }

    /// Dimension of the embedding vectors.
    fn dimension(&self) -> usize;
}
```

- [ ] **Step 2: Write OpenAI provider (openai.rs)**

```rust
use async_trait::async_trait;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use crate::{UmbraError, UmbraResult};
use super::Embedder;

#[derive(Debug, Clone)]
pub struct OpenAIEmbedder {
    client: Client,
    api_key: String,
    model: String,
    base_url: String,
    dimension: usize,
}

#[derive(Serialize)]
struct EmbeddingRequest {
    model: String,
    input: EmbeddingInput,
    encoding_format: String,
}

#[derive(Serialize)]
#[serde(untagged)]
enum EmbeddingInput {
    Single(String),
    Batch(Vec<String>),
}

#[derive(Deserialize)]
struct EmbeddingResponse {
    data: Vec<EmbeddingData>,
}

#[derive(Deserialize)]
struct EmbeddingData {
    embedding: Vec<f32>,
}

impl OpenAIEmbedder {
    pub fn new(api_key: String, model: String, base_url: String, dimension: usize) -> Self {
        Self {
            client: Client::new(),
            api_key,
            model,
            base_url,
            dimension,
        }
    }
}

#[async_trait]
impl Embedder for OpenAIEmbedder {
    async fn embed(&self, text: &str) -> UmbraResult<Vec<f32>> {
        let req = EmbeddingRequest {
            model: self.model.clone(),
            input: EmbeddingInput::Single(text.to_string()),
            encoding_format: "float".to_string(),
        };
        let url = format!("{}/embeddings", self.base_url.trim_end_matches('/'));
        let resp = self.client
            .post(&url)
            .header("Authorization", format!("Bearer {}", self.api_key))
            .json(&req)
            .send()
            .await
            .map_err(|e| UmbraError::Embedding(format!("request failed: {e}")))?;
        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            return Err(UmbraError::Embedding(format!("HTTP {status}: {body}")));
        }
        let emb: EmbeddingResponse = resp
            .json()
            .await
            .map_err(|e| UmbraError::Embedding(format!("parse response: {e}")))?;
        emb.data
            .into_iter()
            .next()
            .map(|d| d.embedding)
            .ok_or_else(|| UmbraError::Embedding("empty response data".into()))
    }

    async fn embed_batch(&self, texts: &[&str]) -> UmbraResult<super::EmbeddingBatch> {
        if texts.is_empty() {
            return Ok(vec![]);
        }
        let req = EmbeddingRequest {
            model: self.model.clone(),
            input: EmbeddingInput::Batch(texts.iter().map(|s| s.to_string()).collect()),
            encoding_format: "float".to_string(),
        };
        let url = format!("{}/embeddings", self.base_url.trim_end_matches('/'));
        let resp = self.client
            .post(&url)
            .header("Authorization", format!("Bearer {}", self.api_key))
            .json(&req)
            .send()
            .await
            .map_err(|e| UmbraError::Embedding(format!("batch request failed: {e}")))?;
        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            return Err(UmbraError::Embedding(format!("HTTP {status}: {body}")));
        }
        let emb: EmbeddingResponse = resp
            .json()
            .await
            .map_err(|e| UmbraError::Embedding(format!("parse batch response: {e}")))?;
        let results: Vec<Vec<f32>> = emb.data.into_iter().map(|d| d.embedding).collect();
        Ok(results)
    }

    fn dimension(&self) -> usize {
        self.dimension
    }
}

/// Mock embedder for testing — returns deterministic vectors based on text hash.
pub struct MockEmbedder {
    dimension: usize,
}

impl MockEmbedder {
    pub fn new(dimension: usize) -> Self {
        Self { dimension }
    }
}

#[async_trait]
impl Embedder for MockEmbedder {
    async fn embed(&self, text: &str) -> UmbraResult<Vec<f32>> {
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};
        // Generate a pseudo-random-but-deterministic vector from text hash
        let mut hasher = DefaultHasher::new();
        text.hash(&mut hasher);
        let seed = hasher.finish();
        let mut vec = Vec::with_capacity(self.dimension);
        for i in 0..self.dimension {
            let val = ((seed.wrapping_mul(i as u64 + 1)) % 1000) as f32 / 1000.0;
            vec.push(val);
        }
        // L2 normalize
        let norm: f32 = vec.iter().map(|x| x * x).sum::<f32>().sqrt();
        if norm > 0.0 {
            vec.iter_mut().for_each(|x| *x /= norm);
        }
        Ok(vec)
    }

    fn dimension(&self) -> usize {
        self.dimension
    }
}
```

- [ ] **Step 3: Update umbra-core/src/lib.rs**

Add:
```rust
pub mod embedding;
```

- [ ] **Step 4: Build check**

Run: `cargo check`
Expected: No errors. Note: `async-trait` needs to be in Cargo.toml.

- [ ] **Step 5: Add async-trait to umbra-core/Cargo.toml dep**

```toml
async-trait = "0.1"
```

- [ ] **Step 6: Build check again**

Run: `cargo check`
Expected: No errors.

- [ ] **Step 7: Commit**

```bash
git add umbra-core/
git commit -m "feat: add Embedder trait + OpenAI and Mock providers"
```

---

### Task 3: Entity Extraction (MVP: rules + dictionary)

**Files:**
- Create: `umbra-core/src/entity/mod.rs`
- Modify: `umbra-core/src/lib.rs`

- [ ] **Step 1: Write entity/mod.rs**

```rust
use std::collections::HashSet;

/// Extracted entity with type and text.
pub type Entity = (String, String); // (entity_type, entity_text)

/// Extract entities from text using rules.
/// MVP: regex patterns for dates, emails, URLs + a small dictionary for common names.
pub fn extract_entities(text: &str) -> Vec<Entity> {
    let mut entities = Vec::new();
    let mut seen = HashSet::new();

    // Email pattern
    let email_re = regex_lite::Regex::new(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
        .expect("valid email regex");
    for m in email_re.find_iter(text) {
        let key = ("EMAIL".to_string(), m.as_str().to_string());
        if seen.insert(format!("EMAIL:{}", m.as_str())) {
            entities.push(key);
        }
    }

    // URL pattern
    let url_re = regex_lite::Regex::new(r"https?://[^\s]+").expect("valid url regex");
    for m in url_re.find_iter(text) {
        let key = ("URL".to_string(), m.as_str().to_string());
        if seen.insert(format!("URL:{}", m.as_str())) {
            entities.push(key);
        }
    }

    // Date pattern (ISO: 2026-05-18, US: 05/18/2026)
    let date_re = regex_lite::Regex::new(r"\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}")
        .expect("valid date regex");
    for m in date_re.find_iter(text) {
        let key = ("DATE".to_string(), m.as_str().to_string());
        if seen.insert(format!("DATE:{}", m.as_str())) {
            entities.push(key);
        }
    }

    // Simple dictionary: match common English first names (small list for MVP)
    const COMMON_NAMES: &[&str] = &[
        "Bob", "Alice", "John", "Mary", "David", "Sarah", "Michael", "Emma",
        "James", "Linda", "Robert", "Jennifer", "William", "Lisa", "Richard",
    ];
    for name in COMMON_NAMES {
        if text.contains(name) && seen.insert(format!("PERSON:{}", name)) {
            entities.push(("PERSON".to_string(), name.to_string()));
        }
    }

    entities
}

/// Batch extract entities from multiple texts.
/// Returns one Vec<Entity> per input text (parallel arrays).
pub fn extract_entities_batch(texts: &[&str]) -> Vec<Vec<Entity>> {
    texts.iter().map(|t| extract_entities(t)).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_email() {
        let entities = extract_entities("Contact Bob at bob@example.com for more info");
        assert!(entities.iter().any(|(t, v)| t == "EMAIL" && v == "bob@example.com"));
        assert!(entities.iter().any(|(t, v)| t == "PERSON" && v == "Bob"));
    }

    #[test]
    fn test_extract_date() {
        let entities = extract_entities("Meeting on 2026-05-18");
        assert!(entities.iter().any(|(t, v)| t == "DATE" && v == "2026-05-18"));
    }

    #[test]
    fn test_no_duplicates() {
        let entities = extract_entities("bob@x.com bob@x.com");
        let emails: Vec<_> = entities.iter().filter(|(t, _)| t == "EMAIL").collect();
        assert_eq!(emails.len(), 1);
    }
}
```

- [ ] **Step 2: Add regex-lite dep to umbra-core/Cargo.toml**

```toml
regex-lite = "0.1"
```

- [ ] **Step 3: Update umbra-core/src/lib.rs**

Add:
```rust
pub mod entity;
```

- [ ] **Step 4: Build check**

Run: `cargo check`
Expected: No errors.

- [ ] **Step 5: Run tests**

Run: `cargo test -p umbra-core`
Expected: entity tests pass.

- [ ] **Step 6: Commit**

```bash
git add umbra-core/
git commit -m "feat: add rule-based entity extraction (regex + dictionary)"
```

---

### Task 4: Storage Layer — Iceberg Catalog + Lance Dataset Management

**Files:**
- Create: `umbra-core/src/storage/mod.rs`
- Create: `umbra-core/src/storage/catalog.rs`
- Create: `umbra-core/src/storage/write.rs`
- Create: `umbra-core/src/storage/scan.rs`
- Modify: `umbra-core/src/lib.rs`

- [ ] **Step 1: Write storage/mod.rs — StorageLayer struct**

```rust
use std::sync::Arc;
use lance::dataset::Dataset;
use lance::Dataset as LanceDataset;
use crate::UmbraResult;

pub mod catalog;
pub mod scan;
pub mod write;

/// Storage configuration.
#[derive(Debug, Clone)]
pub struct StorageConfig {
    pub base_path: String,
    pub catalog_type: CatalogType,
}

#[derive(Debug, Clone)]
pub enum CatalogType {
    Memory,
}

/// Manages Lance datasets and Iceberg catalog for the umbra tables.
pub struct StorageLayer {
    pub config: StorageConfig,
    /// Table name → Arc<Dataset>
    datasets: std::collections::HashMap<String, Arc<LanceDataset>>,
}

pub const MEMORIES_TABLE: &str = "memories";
pub const ENTITIES_TABLE: &str = "entities";
pub const HISTORY_TABLE: &str = "history";
pub const MESSAGES_TABLE: &str = "messages";

impl StorageLayer {
    /// Create a new storage layer. Opens existing datasets or creates new ones.
    pub async fn open(config: StorageConfig) -> UmbraResult<Self> {
        let mut datasets = std::collections::HashMap::new();

        for name in &[MEMORIES_TABLE, ENTITIES_TABLE, HISTORY_TABLE, MESSAGES_TABLE] {
            let path = format!("{}/{}", &config.base_path, name);
            let ds = match LanceDataset::open(&path).await {
                Ok(ds) => Arc::new(ds),
                Err(_) => {
                    tracing::info!("Table '{}' not found at {}, will be created on first write", name, path);
                    continue;
                }
            };
            datasets.insert(name.to_string(), ds);
        }

        Ok(Self { config, datasets })
    }

    /// Get or create a dataset by name.
    pub async fn get_or_create(&mut self, name: &str, schema: &arrow_schema::Schema) -> UmbraResult<Arc<LanceDataset>> {
        if let Some(ds) = self.datasets.get(name) {
            return Ok(ds.clone());
        }
        let path = format!("{}/{}", &self.config.base_path, name);
        std::fs::create_dir_all(&path).map_err(|e| {
            crate::UmbraError::Storage(format!("create dir {path}: {e}"))
        })?;
        let ds = Arc::new(
            LanceDataset::create(&path, schema.clone(), None)
                .await
                .map_err(|e| crate::UmbraError::Storage(format!("create dataset {path}: {e}")))?
        );
        self.datasets.insert(name.to_string(), ds.clone());
        Ok(ds)
    }

    pub fn get(&self, name: &str) -> Option<Arc<LanceDataset>> {
        self.datasets.get(name).cloned()
    }
}
```

- [ ] **Step 2: Write storage/write.rs — Batch append**

```rust
use arrow_array::RecordBatch;
use arrow_schema::SchemaRef;
use lance::dataset::WriteParams;
use std::sync::Arc;
use crate::{UmbraError, UmbraResult};
use super::StorageLayer;

impl StorageLayer {
    /// Append a batch to the named table. Uses Lance's write_params with Append mode.
    pub async fn append(
        &mut self,
        table_name: &str,
        batch: RecordBatch,
        schema: SchemaRef,
    ) -> UmbraResult<()> {
        let ds = self.get_or_create(table_name, &schema).await?;

        let write_params = WriteParams {
            mode: lance::dataset::WriteMode::Append,
            ..Default::default()
        };

        lance::dataset::write::write_fragments(
            ds.as_ref(),
            vec![batch],
            None,
            Some(write_params),
        )
        .await
        .map_err(|e| UmbraError::Storage(format!("append to {table_name}: {e}")))?;

        Ok(())
    }

    /// Append to memories table specifically — preserves Lance vector index.
    pub async fn append_memories(
        &mut self,
        batch: RecordBatch,
        schema: SchemaRef,
    ) -> UmbraResult<()> {
        self.append(super::MEMORIES_TABLE, batch, schema).await
    }
}
```

- [ ] **Step 3: Write storage/scan.rs — Scan with pushdown**

```rust
use arrow_array::RecordBatch;
use arrow_schema::SchemaRef;
use lance::dataset::scanner::Scanner;
use std::sync::Arc;
use crate::{UmbraError, UmbraResult};
use super::StorageLayer;

impl StorageLayer {
    /// Create a scanner for the given table with column projection.
    pub async fn scan(
        &self,
        table_name: &str,
        columns: Option<&[&str]>,
    ) -> UmbraResult<Scanner> {
        let ds = self.get(table_name)
            .ok_or_else(|| UmbraError::NotFound(format!("table {table_name} not found")))?;

        let mut scanner = ds.scan();
        if let Some(cols) = columns {
            scanner.project(cols)
                .map_err(|e| UmbraError::Storage(format!("project columns: {e}")))?;
        }
        Ok(scanner)
    }

    /// Scan and collect all record batches.
    pub async fn scan_all(
        &self,
        table_name: &str,
        columns: Option<&[&str]>,
    ) -> UmbraResult<Vec<RecordBatch>> {
        use futures::TryStreamExt;
        let mut scanner = self.scan(table_name, columns).await?;
        let stream = scanner.scan().await
            .map_err(|e| UmbraError::Storage(format!("scan {table_name}: {e}")))?;
        stream.try_collect::<Vec<_>>().await
            .map_err(|e| UmbraError::Storage(format!("collect {table_name}: {e}")))
    }
}
```

- [ ] **Step 4: Write storage/catalog.rs — Iceberg catalog placeholder (MVP: memory)**

```rust
use std::collections::HashMap;
use std::sync::Mutex;
use serde::{Deserialize, Serialize};

/// Simplified iceberg catalog for MVP.
/// Stores table metadata in memory (no persistence between restarts).
#[derive(Debug, Default)]
pub struct MemoryCatalog {
    tables: Mutex<HashMap<String, TableMetadata>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TableMetadata {
    pub name: String,
    pub location: String,
    pub schema_json: String,
    pub current_snapshot_id: i64,
}

impl MemoryCatalog {
    pub fn new() -> Self {
        Self { tables: Mutex::new(HashMap::new()) }
    }

    pub fn register_table(&self, meta: TableMetadata) {
        let mut tables = self.tables.lock().unwrap();
        tables.insert(meta.name.clone(), meta);
    }

    pub fn get_table(&self, name: &str) -> Option<TableMetadata> {
        let tables = self.tables.lock().unwrap();
        tables.get(name).cloned()
    }
}
```

- [ ] **Step 5: Update umbra-core/src/lib.rs**

Add:
```rust
pub mod storage;
```

- [ ] **Step 6: Build check**

Run: `cargo check -p umbra-core`
Expected: Fix any issues with lance API differences. Lance may use different WriteMode or module paths — adjust per actual crate version.

- [ ] **Step 7: Commit**

```bash
git add umbra-core/
git commit -m "feat: add StorageLayer with Lance dataset management and Iceberg placeholder"
```

---

### Task 5: DataFusion Integration — Table Registration + UDTF Stub

**Files:**
- Create: `umbra-core/src/query/mod.rs`
- Create: `umbra-core/src/query/tablefunc.rs`
- Create: `umbra-core/src/query/udf.rs`
- Modify: `umbra-core/src/lib.rs`

- [ ] **Step 1: Write query/mod.rs**

```rust
use std::sync::Arc;
use datafusion::execution::context::SessionContext;
use crate::UmbraResult;

pub mod tablefunc;
pub mod udf;

/// Register all umbra tables, UDTFs, and UDFs on a DataFusion SessionContext.
pub fn register_all(ctx: &SessionContext) -> UmbraResult<()> {
    udf::register_udfs(ctx)?;
    tablefunc::register_table_functions(ctx)?;
    Ok(())
}
```

- [ ] **Step 2: Write query/udf.rs**

```rust
use std::sync::Arc;
use datafusion::execution::context::SessionContext;
use datafusion::logical_expr::{ScalarUDF, Volatility};
use datafusion::prelude::ColumnarValue;
use datafusion::arrow::datatypes::DataType;
use datafusion::arrow::array::{Float64Array, FixedSizeBinaryArray};
use crate::UmbraResult;

/// Register all UDFs.
pub fn register_udfs(ctx: &SessionContext) -> UmbraResult<()> {
    // cosine_similarity(embedding, embedding) -> float64
    let cosine = ScalarUDF::new(
        "cosine_similarity",
        &|args: &[ColumnarValue]| {
            // For now, return a simple placeholder that errors if called
            // Full implementation after we have vector types wired
            let len = match &args[0] {
                ColumnarValue::Array(a) => a.len(),
                ColumnarValue::Scalar(_) => 1,
            };
            Ok(ColumnarValue::Array(Arc::new(
                Float64Array::from(vec![0.0f64; len])
            )))
        },
        vec![DataType::FixedSizeBinary(1536), DataType::FixedSizeBinary(1536)],
        DataType::Float64,
        Volatility::Immutable,
    );
    ctx.register_udf(Arc::new(cosine));

    Ok(())
}
```

- [ ] **Step 3: Write query/tablefunc.rs (stub)**

```rust
use std::sync::Arc;
use datafusion::catalog::TableFunctionImpl;
use datafusion::common::Result as DFResult;
use datafusion::datasource::TableProvider;
use datafusion::execution::context::SessionContext;
use datafusion::logical_expr::Expr;
use crate::UmbraResult;
use std::any::Any;

/// umbra_search(query, top_k, threshold, filters_json) -> table(id, memory, score, ...)
/// Stub implementation for now — returns an empty table.
#[derive(Debug)]
pub struct UmbraSearchFunction;

impl UmbraSearchFunction {
    pub fn new() -> Self {
        Self
    }
}

impl TableFunctionImpl for UmbraSearchFunction {
    fn call(&self, _args: &[Expr]) -> DFResult<Arc<dyn TableProvider>> {
        // Stub: real implementation in Task 8
        Err(datafusion::error::DataFusionError::NotImplemented(
            "umbra_search not yet implemented".to_string()
        ))
    }
}

pub fn register_table_functions(ctx: &SessionContext) -> UmbraResult<()> {
    ctx.register_udtf(
        "umbra_search",
        Arc::new(UmbraSearchFunction::new()),
    );
    Ok(())
}
```

- [ ] **Step 4: Update umbra-core/src/lib.rs**

Add:
```rust
pub mod query;
```

- [ ] **Step 5: Build check**

Run: `cargo check -p umbra-core`
Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add umbra-core/
git commit -m "feat: add DataFusion integration stub (UDFs + umbra_search UDTF)"
```

---

### Task 6: Index Layer — Vector + BM25 + Entity Boost

**Files:**
- Create: `umbra-core/src/index/mod.rs`
- Create: `umbra-core/src/index/vector.rs`
- Create: `umbra-core/src/index/fulltext.rs`
- Create: `umbra-core/src/index/entity.rs`
- Modify: `umbra-core/src/lib.rs`

- [ ] **Step 1: Write index/mod.rs**

```rust
use std::collections::HashMap;
use crate::types::{ScoredMemory, MemoryFilters};
use crate::UmbraResult;

pub mod vector;
pub mod fulltext;
pub mod entity;

/// Index configuration.
#[derive(Debug, Clone)]
pub struct IndexConfig {
    pub vector: VectorIndexConfig,
    pub fulltext: FulltextConfig,
    pub entity: EntityIndexConfig,
}

#[derive(Debug, Clone)]
pub struct VectorIndexConfig {
    pub num_partitions: usize,
    pub num_sub_vectors: usize,
    pub distance: String,
}

#[derive(Debug, Clone)]
pub struct FulltextConfig {
    pub enabled: bool,
    pub column: String,
}

#[derive(Debug, Clone)]
pub struct EntityIndexConfig {
    // Entity boost weight in fusion: default 0.2
    pub weight: f64,
}

impl Default for IndexConfig {
    fn default() -> Self {
        Self {
            vector: VectorIndexConfig {
                num_partitions: 100,
                num_sub_vectors: 96,
                distance: "cosine".to_string(),
            },
            fulltext: FulltextConfig {
                enabled: true,
                column: "text_lemma".to_string(),
            },
            entity: EntityIndexConfig { weight: 0.2 },
        }
    }
}
```

- [ ] **Step 2: Write index/vector.rs — Lance ANN search**

```rust
use std::sync::Arc;
use lance::dataset::Dataset as LanceDataset;
use crate::types::{ScoredMemory, MemoryFilters};
use crate::UmbraResult;
use std::collections::HashMap;

/// Perform ANN vector search using Lance's native IVF-PQ index.
pub async fn ann_search(
    dataset: &LanceDataset,
    embedding_column: &str,
    query_vec: &[f32],
    top_k: usize,
    filters: Option<&MemoryFilters>,
) -> UmbraResult<Vec<ScoredMemory>> {
    let mut scanner = dataset.scanner();
    scanner
        .nearest(embedding_column, query_vec, top_k)
        .map_err(|e| crate::UmbraError::Internal(format!("nearest: {e}")))?;

    if let Some(f) = filters {
        // Apply string filter for session scoping
        let mut conditions = Vec::new();
        if let Some(ref uid) = f.user_id {
            conditions.push(format!("user_id = '{}'", uid));
        }
        if let Some(ref aid) = f.agent_id {
            conditions.push(format!("agent_id = '{}'", aid));
        }
        if let Some(ref rid) = f.run_id {
            conditions.push(format!("run_id = '{}'", rid));
        }
        if !conditions.is_empty() {
            let filter_str = conditions.join(" AND ");
            scanner
                .filter(&filter_str)
                .map_err(|e| crate::UmbraError::Internal(format!("filter: {e}")))?;
        }
    }

    let stream = scanner
        .scan()
        .await
        .map_err(|e| crate::UmbraError::Internal(format!("scan: {e}")))?;

    use futures::TryStreamExt;
    let batches: Vec<_> = stream
        .try_collect()
        .await
        .map_err(|e| crate::UmbraError::Internal(format!("collect: {e}")))?;

    let mut results = Vec::new();
    for batch in batches {
        use arrow_array::Array;
        let id_arr = batch.column_by_name("id").and_then(|c| c.as_any().downcast_ref::<arrow_array::StringArray>());
        let mem_arr = batch.column_by_name("memory").and_then(|c| c.as_any().downcast_ref::<arrow_array::StringArray>());
        // _distance is returned by Lance nearest() as the last column
        let score_arr = batch.column_by_name("_distance")
            .or_else(|| batch.column(batch.num_columns() - 1))
            .and_then(|c| c.as_any().downcast_ref::<arrow_array::Float32Array>());

        for row in 0..batch.num_rows() {
            let id = id_arr.map(|a| a.value(row).to_string()).unwrap_or_default();
            let memory = mem_arr.map(|a| a.value(row).to_string()).unwrap_or_default();
            let dist: f32 = score_arr.map(|a| a.value(row)).unwrap_or(1.0);
            // Convert cosine distance to similarity
            let score = (1.0 - dist) as f64;

            let mut payload = HashMap::new();
            for col in batch.schema().fields() {
                if let Some(arr) = batch.column_by_name(col.name()) {
                    if let Some(sa) = arr.as_any().downcast_ref::<arrow_array::StringArray>() {
                        if !sa.is_null(row) {
                            payload.insert(col.name().to_string(), sa.value(row).to_string());
                        }
                    }
                }
            }

            results.push(ScoredMemory { id, memory, score, payload });
        }
    }

    Ok(results)
}
```

- [ ] **Step 3: Write index/fulltext.rs — BM25 search via Lance FTS**

```rust
use std::sync::Arc;
use std::collections::HashMap;
use lance::dataset::Dataset as LanceDataset;
use lance_index::scalar::FullTextSearchQuery;
use crate::types::{ScoredMemory, MemoryFilters};
use crate::UmbraResult;

/// Perform BM25 full-text search and return memory_id → normalized score.
pub async fn bm25_search(
    dataset: &LanceDataset,
    query_text: &str,
    top_k: usize,
    filters: Option<&MemoryFilters>,
) -> UmbraResult<HashMap<String, f64>> {
    let query = FullTextSearchQuery::new(query_text.to_string());
    let mut scanner = dataset.scanner();
    scanner
        .full_text_search(query)
        .map_err(|e| crate::UmbraError::Internal(format!("fts: {e}")))?;
    scanner
        .limit(Some(top_k as i64), None)
        .map_err(|e| crate::UmbraError::Internal(format!("limit: {e}")))?;

    if let Some(f) = filters {
        let mut conditions = Vec::new();
        if let Some(ref uid) = f.user_id {
            conditions.push(format!("user_id = '{}'", uid));
        }
        if let Some(ref aid) = f.agent_id {
            conditions.push(format!("agent_id = '{}'", aid));
        }
        if let Some(ref rid) = f.run_id {
            conditions.push(format!("run_id = '{}'", rid));
        }
        if !conditions.is_empty() {
            scanner
                .filter(&conditions.join(" AND "))
                .map_err(|e| crate::UmbraError::Internal(format!("filter: {e}")))?;
        }
    }

    use futures::TryStreamExt;
    let stream = scanner
        .scan()
        .await
        .map_err(|e| crate::UmbraError::Internal(format!("fts scan: {e}")))?;
    let batches: Vec<_> = stream.try_collect().await
        .map_err(|e| crate::UmbraError::Internal(format!("fts collect: {e}")))?;

    let mut scores = HashMap::new();
    for batch in batches {
        use arrow_array::Array;
        let id_arr = batch.column_by_name("id").and_then(|c| c.as_any().downcast_ref::<arrow_array::StringArray>());
        let score_arr = batch.column_by_name("_score")
            .and_then(|c| c.as_any().downcast_ref::<arrow_array::Float32Array>());

        for row in 0..batch.num_rows() {
            if let (Some(id_a), Some(score_a)) = (id_arr, score_arr) {
                let id = id_a.value(row).to_string();
                let raw = score_a.value(row) as f64;
                // Simple sigmoid normalization for BM25
                let norm = if raw > 0.0 {
                    1.0 / (1.0 + (-2.0 * (raw - 1.0)).exp())
                } else {
                    0.0
                };
                scores.insert(id, norm);
            }
        }
    }
    Ok(scores)
}
```

- [ ] **Step 4: Write index/entity.rs — Entity graph boost**

```rust
use std::sync::Arc;
use std::collections::HashMap;
use lance::dataset::Dataset as LanceDataset;
use crate::types::MemoryFilters;
use crate::entity::Entity;
use crate::embedding::Embedder;
use crate::UmbraResult;

const ENTITY_BOOST_WEIGHT: f64 = 0.2;
const ENTITY_SIMILARITY_THRESHOLD: f64 = 0.5;

/// Compute entity-based retrieval boost for each memory.
/// Returns memory_id → boost score [0, 0.2].
pub async fn compute_entity_boosts(
    entity_dataset: &LanceDataset,
    query_entities: &[Entity],
    embedder: &dyn Embedder,
    filters: &MemoryFilters,
) -> UmbraResult<HashMap<String, f64>> {
    if query_entities.is_empty() {
        return Ok(HashMap::new());
    }

    // Deduplicate entities (max 8)
    let mut seen = std::collections::HashSet::new();
    let deduped: Vec<_> = query_entities
        .iter()
        .take(8)
        .filter(|(typ, text)| {
            let key = format!("{}:{}", typ, text.to_lowercase());
            seen.insert(key)
        })
        .collect();

    let mut memory_boosts: HashMap<String, f64> = HashMap::new();

    for (_etype, entity_text) in &deduped {
        let vec = match embedder.embed(entity_text).await {
            Ok(v) => v,
            Err(_) => continue,
        };

        let mut scanner = entity_dataset.scanner();
        // Search entity store for matching entities
        if let Err(_) = scanner.nearest("embedding", &vec, 500) {
            continue;
        }

        let mut conditions = Vec::new();
        if let Some(ref uid) = filters.user_id { conditions.push(format!("user_id = '{}'", uid)); }
        if let Some(ref aid) = filters.agent_id { conditions.push(format!("agent_id = '{}'", aid)); }
        if let Some(ref rid) = filters.run_id { conditions.push(format!("run_id = '{}'", rid)); }
        if !conditions.is_empty() {
            let _ = scanner.filter(&conditions.join(" AND "));
        }

        let stream = match scanner.scan().await {
            Ok(s) => s,
            Err(_) => continue,
        };

        use futures::TryStreamExt;
        let batches: Vec<_> = match stream.try_collect().await {
            Ok(b) => b,
            Err(_) => continue,
        };

        for batch in batches {
            use arrow_array::Array;
            let score_arr = batch.column(batch.num_columns() - 1)
                .and_then(|c| c.as_any().downcast_ref::<arrow_array::Float32Array>())
                .cloned();
            let linked_arr = batch.column_by_name("linked_memory_ids")
                .and_then(|c| c.as_any().downcast_ref::<arrow_array::ListArray>())
                .cloned();

            for row in 0..batch.num_rows() {
                let similarity: f64 = score_arr.as_ref()
                    .map(|a| (1.0 - a.value(row)) as f64)
                    .unwrap_or(0.0);
                if similarity < ENTITY_SIMILARITY_THRESHOLD {
                    continue;
                }

                if let Some(ref linked) = linked_arr {
                    let list = linked.value(row);
                    if let Some(str_list) = list.as_any().downcast_ref::<arrow_array::StringArray>() {
                        let n_linked = str_list.len().max(1) as f64;
                        let attenuation = 1.0 / (1.0 + 0.001 * (n_linked - 1.0).powi(2));
                        let boost = similarity * ENTITY_BOOST_WEIGHT * attenuation;

                        for i in 0..str_list.len() {
                            let mem_id = str_list.value(i).to_string();
                            memory_boosts
                                .entry(mem_id)
                                .and_modify(|v| *v = v.max(boost))
                                .or_insert(boost);
                        }
                    }
                }
            }
        }
    }

    Ok(memory_boosts)
}
```

- [ ] **Step 5: Update umbra-core/src/lib.rs**

Add:
```rust
pub mod index;
```

- [ ] **Step 6: Build check**

Run: `cargo check -p umbra-core`
Expected: Fix any API mismatches with the lance crate's actual API surface.

- [ ] **Step 7: Commit**

```bash
git add umbra-core/
git commit -m "feat: add index layer (ANN search, BM25, entity boost)"
```

---

### Task 7: MemoryOps Trait + Add Operation

**Files:**
- Create: `umbra-core/src/ops/mod.rs`
- Create: `umbra-core/src/ops/add.rs`
- Create: `umbra-core/src/ops/search.rs`
- Create: `umbra-core/src/ops/crud.rs`
- Create: `umbra-core/src/ops/history.rs`
- Modify: `umbra-core/src/lib.rs`

- [ ] **Step 1: Write ops/mod.rs — MemoryOps trait + struct**

```rust
use std::sync::Arc;
use async_trait::async_trait;
use crate::embedding::Embedder;
use crate::index::IndexConfig;
use crate::storage::StorageConfig;
use crate::types::*;
use crate::UmbraResult;

pub mod add;
pub mod crud;
pub mod history;
pub mod search;

/// Core memory operations trait.
#[async_trait]
pub trait MemoryOps: Send + Sync {
    async fn add(&self, messages: Vec<Message>, filters: MemoryFilters, metadata: std::collections::HashMap<String, String>) -> UmbraResult<Vec<AddResult>>;
    async fn search(&self, query: &str, filters: MemoryFilters, top_k: usize, threshold: f64, rerank: bool) -> UmbraResult<Vec<SearchResult>>;
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
    // Will hold StorageLayer + DataFusion context references
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
```

- [ ] **Step 2: Write ops/add.rs — Write pipeline**

```rust
use std::collections::HashMap;
use chrono::Utc;
use crate::entity::extract_entities_batch;
use crate::types::*;
use crate::UmbraResult;
use super::MemoryOpsImpl;
use crate::ops::MemoryOps;

// Simple MD5 hash for dedup
fn md5_hash(s: &str) -> String {
    use std::hash::{Hash, Hasher};
    use std::collections::hash_map::DefaultHasher;
    let mut h = DefaultHasher::new();
    s.hash(&mut h);
    format!("{:x}", h.finish())
}

// Simple lemmatization: lowercase + trim (MVP; later replace with proper lemming)
fn lemmatize(s: &str) -> String {
    s.to_lowercase().trim().to_string()
}

#[async_trait::async_trait]
impl MemoryOps for MemoryOpsImpl {
    async fn add(
        &self,
        messages: Vec<Message>,
        filters: MemoryFilters,
        metadata: HashMap<String, String>,
    ) -> UmbraResult<Vec<AddResult>> {
        filters.validate()?;

        // Phase 1: Parse messages — filter system, extract content
        let valid: Vec<&Message> = messages.iter().filter(|m| m.role != "system").collect();
        if valid.is_empty() {
            return Ok(vec![]);
        }

        // Phase 2: Batch embed
        let texts: Vec<&str> = valid.iter().map(|m| m.content.as_str()).collect();
        let embeddings = self.embedder.embed_batch(&texts).await?;

        // Phase 3: Hash dedup (batch-internal only — cross-batch dedup requires storage integration)
        let mut results = Vec::new();
        let mut seen_hashes = std::collections::HashSet::new();

        let now = Utc::now().to_rfc3339();
        let session_scope = filters.to_session_scope();

        for (i, msg) in valid.iter().enumerate() {
            let hash = md5_hash(&msg.content);
            if !seen_hashes.insert(hash.clone()) {
                continue; // Batch-internal duplicate
            }

            let memory_id = uuid::Uuid::new_v4().to_string();
            let lemma = lemmatize(&msg.content);

            results.push(AddResult {
                id: memory_id.clone(),
                memory: msg.content.clone(),
                event: "ADD".to_string(),
                actor_id: msg.name.clone(),
                role: Some(msg.role.clone()),
            });

            // In full impl: build RecordBatch, write to Lance, commit Iceberg, update history, entity linking
            // For MVP: return results. Full storage integration wired in Task 10.
        }

        Ok(results)
    }
}
```

- [ ] **Step 3: Write ops/search.rs — Multi-signal fusion stub**

```rust
use std::collections::HashMap;
use crate::types::*;
use crate::UmbraResult;
use super::MemoryOpsImpl;
use crate::ops::MemoryOps;

/// Default fusion weights.
const SEMANTIC_WEIGHT: f64 = 0.5;
const BM25_WEIGHT: f64 = 0.3;
const ENTITY_WEIGHT: f64 = 0.2;

/// Score fusion for memory retrieval.
pub fn score_and_rank(
    semantic: Vec<ScoredMemory>,
    bm25_scores: &HashMap<String, f64>,
    entity_boosts: &HashMap<String, f64>,
    threshold: f64,
    top_k: usize,
) -> Vec<SearchResult> {
    let mut fused = Vec::new();
    for mem in semantic {
        let kw = bm25_scores.get(&mem.id).copied().unwrap_or(0.0);
        let ent = entity_boosts.get(&mem.id).copied().unwrap_or(0.0);
        let score = SEMANTIC_WEIGHT * mem.score + BM25_WEIGHT * kw + ENTITY_WEIGHT * ent;

        if score >= threshold {
            fused.push(SearchResult {
                id: mem.id,
                memory: mem.memory,
                score,
                created_at: mem.payload.get("created_at").cloned(),
                updated_at: mem.payload.get("updated_at").cloned(),
                user_id: mem.payload.get("user_id").cloned(),
                agent_id: mem.payload.get("agent_id").cloned(),
                run_id: mem.payload.get("run_id").cloned(),
                actor_id: mem.payload.get("actor_id").cloned(),
                role: mem.payload.get("role").cloned(),
                metadata: mem.payload,
            });
        }
    }
    fused.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap_or(std::cmp::Ordering::Equal));
    fused.truncate(top_k);
    fused
}
```

- [ ] **Step 4: Write ops/search.rs — MemoryOps::search**

```rust
#[async_trait::async_trait]
impl MemoryOps for MemoryOpsImpl {
    async fn search(
        &self,
        query: &str,
        filters: MemoryFilters,
        top_k: usize,
        threshold: f64,
        _rerank: bool,
    ) -> UmbraResult<Vec<SearchResult>> {
        filters.validate()?;

        // Full implementation requires StorageLayer to access Lance datasets.
        // MVP: return empty results.
        Ok(vec![])
    }
}
```

- [ ] **Step 5: Write ops/crud.rs — get/update/delete stub**

```rust
use crate::types::*;
use crate::UmbraResult;
use super::MemoryOpsImpl;
use crate::ops::MemoryOps;

#[async_trait::async_trait]
impl MemoryOps for MemoryOpsImpl {
    async fn get(&self, _memory_id: &str) -> UmbraResult<Option<SearchResult>> {
        Ok(None)
    }

    async fn update(&self, _memory_id: &str, _data: &str) -> UmbraResult<()> {
        Err(crate::UmbraError::NotFound("update not yet implemented".into()))
    }

    async fn delete(&self, _memory_id: &str) -> UmbraResult<()> {
        Err(crate::UmbraError::NotFound("delete not yet implemented".into()))
    }

    async fn delete_all(&self, _filters: MemoryFilters) -> UmbraResult<u64> {
        Ok(0)
    }
}
```

- [ ] **Step 6: Write ops/history.rs — get_history stub**

```rust
use crate::types::*;
use crate::UmbraResult;
use super::MemoryOpsImpl;
use crate::ops::MemoryOps;

#[async_trait::async_trait]
impl MemoryOps for MemoryOpsImpl {
    async fn get_history(&self, _memory_id: &str) -> UmbraResult<Vec<HistoryRecord>> {
        Ok(vec![])
    }
}
```

**NOTE**: Since MemoryOps is a trait and we're implementing it across multiple files, we need a single `impl` block. Let's restructure — put all impl blocks in mod.rs.

- [ ] **Step 7: Restructure: move all impls into mod.rs**

Consolidate all MemoryOps trait implementations into `ops/mod.rs`:

```rust
use std::collections::HashMap;
use std::sync::Arc;
use async_trait::async_trait;
use chrono::Utc;
use crate::embedding::Embedder;
use crate::entity::extract_entities_batch;
use crate::index::IndexConfig;
use crate::storage::StorageConfig;
use crate::types::*;
use crate::UmbraResult;

pub mod add;      // utility functions for add pipeline
pub mod search;   // score_and_rank + utility functions
pub mod crud;     // utility functions
pub mod history;  // utility functions

/// Core memory operations trait.
#[async_trait]
pub trait MemoryOps: Send + Sync {
    async fn add(&self, messages: Vec<Message>, filters: MemoryFilters, metadata: HashMap<String, String>) -> UmbraResult<Vec<AddResult>>;
    async fn search(&self, query: &str, filters: MemoryFilters, top_k: usize, threshold: f64, rerank: bool) -> UmbraResult<Vec<SearchResult>>;
    async fn get(&self, memory_id: &str) -> UmbraResult<Option<SearchResult>>;
    async fn update(&self, memory_id: &str, data: &str) -> UmbraResult<()>;
    async fn delete(&self, memory_id: &str) -> UmbraResult<()>;
    async fn delete_all(&self, filters: MemoryFilters) -> UmbraResult<u64>;
    async fn get_history(&self, memory_id: &str) -> UmbraResult<Vec<HistoryRecord>>;
}

/// Concrete implementation.
pub struct MemoryOpsImpl {
    pub embedder: Arc<dyn Embedder>,
    pub index_config: IndexConfig,
    pub storage_config: StorageConfig,
}

impl MemoryOpsImpl {
    pub fn new(embedder: Arc<dyn Embedder>, index_config: IndexConfig, storage_config: StorageConfig) -> Self {
        Self { embedder, index_config, storage_config }
    }
}

// Simple utilities
fn md5_hash(s: &str) -> String {
    use std::hash::{Hash, Hasher};
    use std::collections::hash_map::DefaultHasher;
    let mut h = DefaultHasher::new();
    s.hash(&mut h);
    format!("{:x}", h.finish())
}

fn lemmatize(s: &str) -> String {
    s.to_lowercase().trim().to_string()
}

#[async_trait]
impl MemoryOps for MemoryOpsImpl {
    async fn add(&self, messages: Vec<Message>, filters: MemoryFilters, metadata: HashMap<String, String>) -> UmbraResult<Vec<AddResult>> {
        filters.validate()?;
        let valid: Vec<&Message> = messages.iter().filter(|m| m.role != "system").collect();
        if valid.is_empty() { return Ok(vec![]); }

        let texts: Vec<&str> = valid.iter().map(|m| m.content.as_str()).collect();
        let embeddings = self.embedder.embed_batch(&texts).await?;

        let mut results = Vec::new();
        let mut seen = std::collections::HashSet::new();
        let now = Utc::now().to_rfc3339();

        for (i, msg) in valid.iter().enumerate() {
            let hash = md5_hash(&msg.content);
            if !seen.insert(hash.clone()) { continue; }

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

    async fn search(&self, query: &str, filters: MemoryFilters, top_k: usize, threshold: f64, rerank: bool) -> UmbraResult<Vec<SearchResult>> {
        filters.validate()?;
        // Stub: full impl in Task 10 after storage wiring
        Ok(vec![])
    }

    async fn get(&self, memory_id: &str) -> UmbraResult<Option<SearchResult>> {
        Ok(None)
    }

    async fn update(&self, memory_id: &str, data: &str) -> UmbraResult<()> {
        Err(UmbraError::NotFound("not implemented".into()))
    }

    async fn delete(&self, memory_id: &str) -> UmbraResult<()> {
        Err(UmbraError::NotFound("not implemented".into()))
    }

    async fn delete_all(&self, filters: MemoryFilters) -> UmbraResult<u64> {
        Ok(0)
    }

    async fn get_history(&self, memory_id: &str) -> UmbraResult<Vec<HistoryRecord>> {
        Ok(vec![])
    }
}
```

- [ ] **Step 8: Simplify add.rs, search.rs, crud.rs, history.rs to utility-only modules**

ops/add.rs:
```rust
// Utility functions for the add pipeline (entity linking, hash management, etc.)
// Wired in later tasks when storage is integrated.
```

ops/search.rs:
```rust
use std::collections::HashMap;
use crate::types::*;

pub const SEMANTIC_WEIGHT: f64 = 0.5;
pub const BM25_WEIGHT: f64 = 0.3;
pub const ENTITY_WEIGHT: f64 = 0.2;

pub fn score_and_rank(
    semantic: Vec<ScoredMemory>,
    bm25_scores: &HashMap<String, f64>,
    entity_boosts: &HashMap<String, f64>,
    threshold: f64,
    top_k: usize,
) -> Vec<SearchResult> {
    let mut fused = Vec::new();
    for mem in semantic {
        let kw = bm25_scores.get(&mem.id).copied().unwrap_or(0.0);
        let ent = entity_boosts.get(&mem.id).copied().unwrap_or(0.0);
        let score = SEMANTIC_WEIGHT * mem.score + BM25_WEIGHT * kw + ENTITY_WEIGHT * ent;
        if score >= threshold {
            fused.push(SearchResult {
                id: mem.id,
                memory: mem.memory,
                score,
                created_at: mem.payload.get("created_at").cloned(),
                updated_at: mem.payload.get("updated_at").cloned(),
                user_id: mem.payload.get("user_id").cloned(),
                agent_id: mem.payload.get("agent_id").cloned(),
                run_id: mem.payload.get("run_id").cloned(),
                actor_id: mem.payload.get("actor_id").cloned(),
                role: mem.payload.get("role").cloned(),
                metadata: mem.payload,
            });
        }
    }
    fused.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap_or(std::cmp::Ordering::Equal));
    fused.truncate(top_k);
    fused
}
```

ops/crud.rs and ops/history.rs — empty placeholder modules for now.

- [ ] **Step 9: Update umbra-core/src/lib.rs**

Add:
```rust
pub mod ops;
```

- [ ] **Step 10: Build check**

Run: `cargo check -p umbra-core`
Expected: No errors.

- [ ] **Step 11: Commit**

```bash
git add umbra-core/
git commit -m "feat: add MemoryOps trait + impl with add pipeline"
```

---

### Task 8: Protobuf Definition + gRPC Service

**Files:**
- Modify: `umbra-server/proto/umbra.proto`
- Modify: `umbra-server/src/service.rs`
- Modify: `umbra-server/build.rs`
- Modify: `umbra-server/Cargo.toml`

- [ ] **Step 1: Write complete proto file**

```protobuf
syntax = "proto3";
package umbra;

service MemoryService {
  rpc Add(AddRequest) returns (AddResponse);
  rpc Search(SearchRequest) returns (SearchResponse);
  rpc Get(GetRequest) returns (GetResponse);
  rpc Update(UpdateRequest) returns (UpdateResponse);
  rpc Delete(DeleteRequest) returns (DeleteResponse);
  rpc DeleteAll(DeleteAllRequest) returns (DeleteAllResponse);
  rpc GetHistory(GetHistoryRequest) returns (GetHistoryResponse);
}

message Message {
  string role = 1;
  string content = 2;
  optional string name = 3;
}

// ============== Add ==============
message AddRequest {
  repeated Message messages = 1;
  optional string user_id = 2;
  optional string agent_id = 3;
  optional string run_id = 4;
  map<string, string> metadata = 5;
}

message AddResult {
  string id = 1;
  string memory = 2;
  string event = 3;
  optional string actor_id = 4;
  optional string role = 5;
}

message AddResponse {
  repeated AddResult results = 1;
}

// ============== Search ==============
message SearchRequest {
  string query = 1;
  int32 top_k = 2;
  double threshold = 3;
  map<string, string> filters = 4;
  bool rerank = 5;
}

message SearchResult {
  string id = 1;
  string memory = 2;
  double score = 3;
  optional string created_at = 4;
  optional string updated_at = 5;
  optional string user_id = 6;
  optional string agent_id = 7;
  optional string run_id = 8;
  optional string actor_id = 9;
  optional string role = 10;
  map<string, string> metadata = 11;
}

message SearchResponse {
  repeated SearchResult results = 1;
}

// ============== Get ==============
message GetRequest {
  string memory_id = 1;
}

message GetResponse {
  optional SearchResult result = 1;
}

// ============== Update ==============
message UpdateRequest {
  string memory_id = 1;
  string data = 2;
  map<string, string> metadata = 3;
}

message UpdateResponse {
  string message = 1;
}

// ============== Delete ==============
message DeleteRequest {
  string memory_id = 1;
}

message DeleteResponse {
  string message = 1;
}

// ============== DeleteAll ==============
message DeleteAllRequest {
  optional string user_id = 1;
  optional string agent_id = 2;
  optional string run_id = 3;
}

message DeleteAllResponse {
  uint64 deleted_count = 1;
}

// ============== GetHistory ==============
message GetHistoryRequest {
  string memory_id = 1;
}

message HistoryRecord {
  string id = 1;
  string memory_id = 2;
  optional string old_memory = 3;
  optional string new_memory = 4;
  string event = 5;
  optional string actor_id = 6;
  optional string created_at = 7;
  int32 is_deleted = 8;
}

message GetHistoryResponse {
  repeated HistoryRecord records = 1;
}
```

- [ ] **Step 2: Write service.rs — gRPC MemoryService implementation**

```rust
use std::sync::Arc;
use tonic::{Request, Response, Status};
use umbra_core::ops::MemoryOps;
use umbra_core::types::{MemoryFilters, Message};

use crate::umbra_proto::{
    memory_service_server::MemoryService as MemoryServiceTrait,
    *,
};

pub struct UmbraMemoryService {
    ops: Arc<dyn MemoryOps>,
}

impl UmbraMemoryService {
    pub fn new(ops: Arc<dyn MemoryOps>) -> Self {
        Self { ops }
    }
}

fn to_core_message(msg: &Message) -> umbra_core::types::Message {
    umbra_core::types::Message {
        role: msg.role.clone(),
        content: msg.content.clone(),
        name: msg.name.clone(),
    }
}

fn from_core_add_result(r: umbra_core::types::AddResult) -> AddResult {
    AddResult {
        id: r.id,
        memory: r.memory,
        event: r.event,
        actor_id: r.actor_id,
        role: r.role,
    }
}

fn from_core_search_result(r: umbra_core::types::SearchResult) -> SearchResult {
    SearchResult {
        id: r.id,
        memory: r.memory,
        score: r.score,
        created_at: r.created_at,
        updated_at: r.updated_at,
        user_id: r.user_id,
        agent_id: r.agent_id,
        run_id: r.run_id,
        actor_id: r.actor_id,
        role: r.role,
        metadata: r.metadata,
    }
}

fn to_core_history_record(r: HistoryRecord) -> umbra_core::types::HistoryRecord {
    umbra_core::types::HistoryRecord {
        id: r.id,
        memory_id: r.memory_id,
        old_memory: r.old_memory,
        new_memory: r.new_memory,
        event: r.event,
        actor_id: r.actor_id,
        created_at: r.created_at,
        is_deleted: r.is_deleted,
    }
}

fn from_core_history_record(r: &umbra_core::types::HistoryRecord) -> HistoryRecord {
    HistoryRecord {
        id: r.id.clone(),
        memory_id: r.memory_id.clone(),
        old_memory: r.old_memory.clone(),
        new_memory: r.new_memory.clone(),
        event: r.event.clone(),
        actor_id: r.actor_id.clone(),
        created_at: r.created_at.clone(),
        is_deleted: r.is_deleted,
    }
}

#[tonic::async_trait]
impl MemoryServiceTrait for UmbraMemoryService {
    async fn add(&self, request: Request<AddRequest>) -> Result<Response<AddResponse>, Status> {
        let req = request.into_inner();
        let messages: Vec<Message> = req.messages.iter().map(to_core_message).collect();
        let filters = MemoryFilters {
            user_id: req.user_id,
            agent_id: req.agent_id,
            run_id: req.run_id,
        };
        let results = self.ops
            .add(messages, filters, req.metadata)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(AddResponse {
            results: results.into_iter().map(from_core_add_result).collect(),
        }))
    }

    async fn search(&self, request: Request<SearchRequest>) -> Result<Response<SearchResponse>, Status> {
        let req = request.into_inner();
        let filters = MemoryFilters {
            user_id: req.filters.get("user_id").cloned(),
            agent_id: req.filters.get("agent_id").cloned(),
            run_id: req.filters.get("run_id").cloned(),
        };
        let results = self.ops
            .search(&req.query, filters, req.top_k as usize, req.threshold, req.rerank)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(SearchResponse {
            results: results.into_iter().map(from_core_search_result).collect(),
        }))
    }

    async fn get(&self, request: Request<GetRequest>) -> Result<Response<GetResponse>, Status> {
        let req = request.into_inner();
        let result = self.ops.get(&req.memory_id).await.map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(GetResponse {
            result: result.map(from_core_search_result),
        }))
    }

    async fn update(&self, request: Request<UpdateRequest>) -> Result<Response<UpdateResponse>, Status> {
        let req = request.into_inner();
        self.ops.update(&req.memory_id, &req.data).await.map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(UpdateResponse { message: "ok".into() }))
    }

    async fn delete(&self, request: Request<DeleteRequest>) -> Result<Response<DeleteResponse>, Status> {
        let req = request.into_inner();
        self.ops.delete(&req.memory_id).await.map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(DeleteResponse { message: "ok".into() }))
    }

    async fn delete_all(&self, request: Request<DeleteAllRequest>) -> Result<Response<DeleteAllResponse>, Status> {
        let req = request.into_inner();
        let filters = MemoryFilters {
            user_id: req.user_id,
            agent_id: req.agent_id,
            run_id: req.run_id,
        };
        let count = self.ops.delete_all(filters).await.map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(DeleteAllResponse { deleted_count: count }))
    }

    async fn get_history(&self, request: Request<GetHistoryRequest>) -> Result<Response<GetHistoryResponse>, Status> {
        let req = request.into_inner();
        let records = self.ops.get_history(&req.memory_id).await.map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(GetHistoryResponse {
            records: records.iter().map(from_core_history_record).collect(),
        }))
    }
}
```

- [ ] **Step 3: Update umbra-server/Cargo.toml (ensure tonic-prost types)**

```toml
[build-dependencies]
tonic-prost.workspace = true

[dependencies]
# ... existing deps plus:
prost.workspace = true
tonic-prost.workspace = true
```

- [ ] **Step 4: Add proto include path in build.rs**

```rust
fn main() -> Result<(), Box<dyn std::error::Error>> {
    tonic_prost::configure::configure()
        .build_server(true)
        .build_client(false)
        .compile_protos(
            &["proto/umbra.proto"],
            &["proto/"], // include path for proto imports
        )?;
    Ok(())
}
```

- [ ] **Step 5: Update umbra-server/src/lib.rs**

```rust
pub mod config;
pub mod flight;
pub mod service;

// Include generated proto code
pub mod umbra_proto {
    tonic::include_proto!("umbra");
}
```

- [ ] **Step 6: Build check**

Run: `cargo check -p umbra-server`
Expected: May fail because tonic-prost path needs adjustment. Check the actual generated module paths. In tonic 0.12 with prost, the generated code module is accessed via `tonic::include_proto!`.

- [ ] **Step 7: Commit**

```bash
git add umbra-server/
git commit -m "feat: add protobuf definition + gRPC MemoryService implementation"
```

---

### Task 9: Configuration Loading + Flight SQL + Main Server

**Files:**
- Create: `umbra-server/src/config.rs`
- Modify: `umbra-server/src/flight.rs`
- Modify: `umbra-server/src/main.rs`

- [ ] **Step 1: Write config.rs using figment**

```rust
use figment::{Figment, providers::{Toml, Env}};
use serde::Deserialize;

#[derive(Debug, Clone, Deserialize)]
pub struct ServerConfig {
    pub grpc_port: u16,
    pub flight_sql_port: u16,
    #[serde(default = "default_graceful_timeout")]
    pub graceful_timeout_secs: u64,
}

fn default_graceful_timeout() -> u64 { 30 }

#[derive(Debug, Clone, Deserialize)]
pub struct StorageConfig {
    pub base_path: String,
    #[serde(default = "default_catalog_type")]
    pub catalog_type: String,
}

fn default_catalog_type() -> String { "memory".to_string() }

#[derive(Debug, Clone, Deserialize)]
pub struct EmbeddingConfig {
    pub provider: String,
    pub model: String,
    pub dimensions: usize,
    pub api_key: String,
    #[serde(default = "default_base_url")]
    pub base_url: String,
    #[serde(default = "default_batch_size")]
    pub batch_size: usize,
}

fn default_base_url() -> String { "https://api.openai.com/v1".to_string() }
fn default_batch_size() -> usize { 100 }

#[derive(Debug, Clone, Deserialize)]
pub struct AppConfig {
    pub server: ServerConfig,
    pub storage: StorageConfig,
    pub embedding: EmbeddingConfig,
    #[serde(default)]
    pub search: SearchConfig,
}

#[derive(Debug, Clone, Deserialize)]
pub struct SearchConfig {
    #[serde(default = "default_semantic_weight")]
    pub semantic_weight: f64,
    #[serde(default = "default_bm25_weight")]
    pub bm25_weight: f64,
    #[serde(default = "default_entity_weight")]
    pub entity_boost_weight: f64,
    #[serde(default = "default_top_k")]
    pub default_top_k: usize,
    #[serde(default = "default_threshold")]
    pub default_threshold: f64,
}

fn default_semantic_weight() -> f64 { 0.5 }
fn default_bm25_weight() -> f64 { 0.3 }
fn default_entity_weight() -> f64 { 0.2 }
fn default_top_k() -> usize { 20 }
fn default_threshold() -> f64 { 0.1 }

impl Default for SearchConfig {
    fn default() -> Self {
        Self {
            semantic_weight: 0.5,
            bm25_weight: 0.3,
            entity_boost_weight: 0.2,
            default_top_k: 20,
            default_threshold: 0.1,
        }
    }
}

impl AppConfig {
    pub fn load() -> Result<Self, figment::Error> {
        Figment::new()
            .merge(Toml::file("config.toml"))
            .merge(Env::prefixed("UMBRA_").split("__"))
            .extract()
    }
}
```

- [ ] **Step 2: Write flight.rs — Flight SQL server**

```rust
use std::sync::Arc;
use datafusion::execution::context::SessionContext;
use anyhow::Result;

pub async fn serve_flight_sql(ctx: Arc<SessionContext>, addr: std::net::SocketAddr) -> Result<()> {
    use datafusion::execution::flight::sql::server::FlightSqlServer;

    let server = FlightSqlServer::new(ctx)
        .listen(addr)
        .await?;

    tracing::info!("Arrow Flight SQL listening on {}", addr);
    server.serve().await?;
    Ok(())
}
```

**Note**: The exact `FlightSqlServer` API depends on the datafusion version. Adjust API calls as needed.

- [ ] **Step 3: Write main.rs — Server entry point**

```rust
use std::sync::Arc;
use umbra_server::config::AppConfig;
use umbra_server::service::UmbraMemoryService;
use umbra_server::umbra_proto::memory_service_server::MemoryServiceServer;
use umbra_core::embedding::openai::OpenAIEmbedder;
use umbra_core::embedding::Embedder;
use umbra_core::ops::{MemoryOpsImpl, MemoryOps};
use umbra_core::index::IndexConfig;
use umbra_core::storage::StorageConfig as CoreStorageConfig;
use datafusion::execution::context::SessionContext;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt::init();

    let config = AppConfig::load()?;
    tracing::info!("Loaded config: grpc={}, flight={}", config.server.grpc_port, config.server.flight_sql_port);

    // Init embedder
    let embedder: Arc<dyn Embedder> = match config.embedding.provider.as_str() {
        "openai" => Arc::new(OpenAIEmbedder::new(
            config.embedding.api_key.clone(),
            config.embedding.model.clone(),
            config.embedding.base_url.clone(),
            config.embedding.dimensions,
        )),
        _ => {
            tracing::warn!("Unknown embedding provider '{}', using mock", config.embedding.provider);
            Arc::new(umbra_core::embedding::openai::MockEmbedder::new(config.embedding.dimensions))
        }
    };

    let index_config = IndexConfig::default();
    let storage_config = CoreStorageConfig {
        base_path: config.storage.base_path.clone(),
        catalog_type: umbra_core::storage::CatalogType::Memory,
    };

    // Init DataFusion context
    let ctx = Arc::new(SessionContext::new());
    umbra_core::query::register_all(&ctx)?;

    // Build MemoryOps
    let ops: Arc<dyn MemoryOps> = Arc::new(MemoryOpsImpl::new(embedder, index_config, storage_config));

    // Start gRPC server
    let grpc_addr = format!("0.0.0.0:{}", config.server.grpc_port).parse()?;
    let service = UmbraMemoryService::new(ops);
    let grpc_handle = tokio::spawn(async move {
        tonic::transport::Server::builder()
            .add_service(MemoryServiceServer::new(service))
            .serve(grpc_addr)
            .await
            .expect("gRPC server failed");
    });

    // Start Flight SQL
    let flight_addr = format!("0.0.0.0:{}", config.server.flight_sql_port).parse()?;
    let flight_handle = tokio::spawn(async move {
        umbra_server::flight::serve_flight_sql(ctx, flight_addr).await
            .expect("Flight SQL server failed");
    });

    tracing::info!("Umbra server started — gRPC: {}, Flight SQL: {}", config.server.grpc_port, config.server.flight_sql_port);

    tokio::signal::ctrl_c().await?;
    grpc_handle.abort();
    flight_handle.abort();

    tracing::info!("Umbra server shut down");
    Ok(())
}
```

- [ ] **Step 4: Create config.toml at repo root**

```toml
[server]
grpc_port = 9090
flight_sql_port = 9091

[storage]
base_path = "file:///tmp/umbra-data"
catalog_type = "memory"

[embedding]
provider = "openai"
model = "text-embedding-3-small"
dimensions = 1536
api_key = "${UMBRA_OPENAI_API_KEY}"
base_url = "https://api.openai.com/v1"
batch_size = 100

[search]
semantic_weight = 0.5
bm25_weight = 0.3
entity_boost_weight = 0.2
default_top_k = 20
default_threshold = 0.1
```

- [ ] **Step 5: Add futures dependency to umbra-core/Cargo.toml**

```toml
futures = "0.3"
```

- [ ] **Step 6: Build check**

Run: `cargo check`
Expected: Identify and fix any remaining API mismatches.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: add config loading, Flight SQL server, main entry point"
```

---

## Future Tasks (Post-MVP)

These tasks are defined but NOT in current scope:

- **T10: Storage Integration** — Wire StorageLayer into MemoryOps. Build real RecordBatch from add(), write to Lance, commit Iceberg. Full vector/BM25/entity retrieval pipeline.
- **T11: Integrations Tests** — Docker Compose with umbra + test client. Test add → search roundtrip.
- **T12: Performance** — Vector index compaction, partition pruning benchmarks, fusion weight tuning.
- **T13: LLM Plugin** — Embedder-like trait for LLM extraction/inference on write path.
- **T14: Auth & Multi-tenancy** — API key auth, per-tenant rate limiting.

---

## Self-Review Note

After implementation of Tasks 0-9, the server compiles and starts, gRPC accept requests, and add() returns results. search() returns empty results. The full storage-to-retrieval pipeline requires wiring StorageLayer into MemoryOps (Task 10), which depends on Lance API surface validation during implementation.
