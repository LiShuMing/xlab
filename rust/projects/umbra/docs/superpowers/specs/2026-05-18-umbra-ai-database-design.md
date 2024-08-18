# Umbra AI Database — Design Spec

**Status**: Draft
**Date**: 2026-05-18
**Author**: Li ShuMing

## 1. Overview

Transform umbra from a Cranelift JIT PoC into an AI-native memory database built on
DataFusion + Apache Iceberg + Lance.

### Positioning

A **Mem0-style memory search service** — independent gRPC/Arrow Flight SQL server in
pure Rust. Core is a storage+retrieval engine without built-in LLM calls. LLM extraction
and summarization are left to upper-layer callers.

### Non-Goals (MVP)

- No built-in LLM extraction/summarization
- No distributed consensus (single-node service)
- No auth/native multi-tenancy enforcement (relies on filter-level scoping)
- No Python SDK (gRPC only, with Arrow Flight SQL for analytics)

---

## 2. Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Query Engine | DataFusion | Rust-native SQL + extensible TableProvider/UDTF/UDF |
| Table Format | Apache Iceberg | Schema evolution, snapshots, time travel, partition pruning |
| File Format (structured) | Parquet | Standard for history/messages tables |
| File Format (vector) | Lance | Columnar with IVF-PQ/HNSW vector index + Tantivy FTS |
| Vector Index | Lance ANN (IVF-PQ default) | In-file vector index, no separate vector DB |
| Full-Text Search | Lance FTS (Tantivy) | BM25 keyword search on text_lemma column |
| Embedding | OpenAI-compatible API | text-embedding-3-small (1536d), pluggable provider |
| gRPC Framework | tonic | Pure Rust, async, protobuf |
| Flight SQL | DataFusion FlightSQLService | Standard Arrow protocol for BI/analytics |

### Lance + DataFusion Native Support

Lance already provides:
- `LanceTableProvider` implementing `datafusion::datasource::TableProvider`
  (projection/filter/limit pushdown, ordered scan)
- `FtsTableProvider` UDTF for full-text search
- `Dataset::scanner().nearest()` for ANN vector search (Rust API, no SQL UDTF yet)

We leverage `LanceTableProvider` directly for standard scans. Vector ANN search is
exposed through a custom UDTF (`umbra_search`).

---

## 3. Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    umbra-server                           │
│                                                          │
│  ┌──────────────────┐   ┌───────────────────────────┐   │
│  │MemoryService gRPC│   │  Arrow Flight SQL Service │   │
│  │port: 9090        │   │  port: 9091               │   │
│  └────────┬─────────┘   └─────────────┬─────────────┘   │
│           │                            │                  │
│  ┌────────▼────────────────────────────▼─────────────┐   │
│  │                  MemoryOps (核心引擎)               │   │
│  │  add / search / get / update / delete / history    │   │
│  │  ┌───────────┬──────────────┬───────────────────┐ │   │
│  │  │ Embedder  │RetrievalFusion│ EntityLinker      │ │   │
│  │  └───────────┴──────────────┴───────────────────┘ │   │
│  └──────────────────────┬───────────────────────────┘   │
│                         │                                │
│  ┌──────────────────────▼───────────────────────────┐   │
│  │              DataFusion SessionContext             │   │
│  │  ┌──────────────┬──────────────┬──────────────┐ │   │
│  │  │Iceberg Catalog│LanceTableProv│ UDTF/UDF     │ │   │
│  │  └──────────────┴──────────────┴──────────────┘ │   │
│  └──────────────────────┬───────────────────────────┘   │
│                         │                                │
│  ┌──────────────────────▼───────────────────────────┐   │
│  │                Object Store                        │   │
│  │           file:///data/umbra or S3://              │   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

---

## 4. Data Model

### 4.1 memories (Lance)

```sql
CREATE TABLE umbra.memories (
    id           STRING NOT NULL,
    memory       STRING NOT NULL,
    hash         STRING NOT NULL,
    text_lemma   STRING,
    embedding    FIXED_BINARY(1536),
    user_id      STRING,
    agent_id     STRING,
    run_id       STRING,
    actor_id     STRING,
    role         STRING,
    created_at   TIMESTAMP NOT NULL,
    updated_at   TIMESTAMP NOT NULL,
    metadata     MAP<STRING, STRING>,
    attributed_to STRING
)
USING lance
PARTITIONED BY (user_id, HOUR(created_at))
SORTED BY (created_at DESC)
```

- `embedding` stored as FIXED_BINARY for optimal Lance vector layout
- `hash` is MD5(memory), used for dedup
- `text_lemma` is lemmatized text for BM25 indexing
- Partitioned by user_id first (primary filter dimension), then hour

### 4.2 entities (Lance)

```sql
CREATE TABLE umbra.entities (
    id                STRING NOT NULL,
    entity_text       STRING NOT NULL,
    entity_type       STRING NOT NULL,
    embedding         FIXED_BINARY(1536),
    linked_memory_ids LIST<STRING>,
    num_linked        INT,
    user_id           STRING,
    agent_id          STRING,
    run_id            STRING,
    created_at        TIMESTAMP NOT NULL
)
USING lance
PARTITIONED BY (user_id)
```

Entity-memory bipartite graph: entity → linked_memory_ids provides reverse lookup
for entity-based retrieval boosting.

### 4.3 history (Parquet)

```sql
CREATE TABLE umbra.history (
    id           STRING NOT NULL,
    memory_id    STRING NOT NULL,
    old_memory   STRING,
    new_memory   STRING,
    event        STRING NOT NULL,          -- ADD | UPDATE | DELETE
    actor_id     STRING,
    user_id      STRING,
    agent_id     STRING,
    run_id       STRING,
    is_deleted   INT DEFAULT 0,
    created_at   TIMESTAMP NOT NULL,
    updated_at   TIMESTAMP NOT NULL
)
USING parquet
PARTITIONED BY (user_id, DAY(created_at))
```

Append-only event log. Supports Iceberg time travel and incremental reads.

### 4.4 messages (Parquet)

```sql
CREATE TABLE umbra.messages (
    id             STRING NOT NULL,
    session_scope  STRING NOT NULL,
    role           STRING NOT NULL,
    content        STRING NOT NULL,
    name           STRING,
    created_at     TIMESTAMP NOT NULL
)
USING parquet
PARTITIONED BY (session_scope)
```

Sliding window of 10 most recent messages per session scope.

### 4.5 sessions (Parquet)

```sql
CREATE TABLE umbra.sessions (
    session_scope STRING NOT NULL PRIMARY KEY,
    user_id       STRING,
    agent_id      STRING,
    run_id        STRING,
    created_at    TIMESTAMP NOT NULL,
    last_seen_at  TIMESTAMP NOT NULL
)
USING parquet
```

---

## 5. Storage Layer: Iceberg + Lance Integration

### Integration Model

Iceberg manages table metadata (schema, partitions, snapshots). Lance files are the
physical data format for the memories and entities tables.

```
Iceberg Table "memories"
├── metadata/
│   ├── v1.metadata.json       ← schema, partition spec, snapshot
│   └── snap-*.avro            ← manifest list
├── data/
│   ├── user_id=u1/hour=2026-05-17-14/
│   │   ├── a1f3b2.lance       ← Lance data file
│   │   └── _indices/          ← Lance vector indices
│   │       ├── ivf_pq.idx
│   │       └── bm25.idx
│   └── user_id=u2/...
└── _iceberg/manifests/
    └── manifest-*.avro         ← Iceberg manifest
```

### Write Path

1. RecordBatch partitioned by (user_id, HOUR(created_at))
2. Per-partition Lance Dataset::append(batch) → new .lance file + updated indices
3. Iceberg CAS commit (register new data file, advance snapshot)

### Read Path (standard scan)

1. Iceberg resolve snapshot → manifest filtering by partition
2. Extract .lance file paths
3. Lance scanner with projection/filter/limit pushdown → RecordBatch stream

### Read Path (vector search)

1. Partition filter → determine relevant Lance datasets
2. Per-partition Lance `scanner().nearest("embedding", query_vec, top_k)`
3. Global merge + rank

### Vector Index Config

- IVF-PQ: num_partitions = floor(sqrt(row_count)), num_sub_vectors = 96
- Cosine distance
- Incremental index update on append, periodic compaction rebuild

---

## 6. Query Layer: DataFusion Integration

### TableProvider

Use Lance's existing `LanceTableProvider` (implements `TableProvider` with Exact
filter/projection/limit pushdown). An Iceberg catalog layer routes to the correct
Lance Dataset files per partition.

### Vector Search UDTF

```sql
umbra_search(query, top_k, threshold, filters_json) → table(id, score, ...)
```

Registered as a DataFusion TableFunction. Internally calls
`Dataset::scanner().nearest()` with Lance IVF-PQ index.

### UDFs

- `cosine_similarity(embedding, embedding) → float64`
- `vector_distance(embedding, embedding) → float64`
- `entity_boost(memory_id, entity_text) → float64`

### Optimizer Rules

1. `UmbraPartitionPruneRule` — filter → Iceberg partition filter pushdown
2. `UmbraSearchLimitPushdown` — LIMIT → top_k pushdown to Lance ANN
3. `UmbraScoreThresholdPushdown` — score > threshold → Lance pre-filter

---

## 7. Retrieval Pipeline: Multi-Signal Fusion

### Overview

```
search(query, filters, top_k, threshold)
  │
  ├─ Phase 0: Preprocessing
  │    query → embedding + lemmatize + extract entities
  │
  ├─ Phase 1: Three-way parallel retrieval
  │    ├─ Semantic ANN (Lance IVF-PQ, over-fetch 4x)
  │    ├─ BM25 keyword (Lance FTS/Tantivy)
  │    └─ Entity graph boost (entity store ANN → linked memories)
  │
  ├─ Phase 2: Score fusion
  │    final = 0.5*semantic + 0.3*bm25 + 0.2*entity_boost
  │
  └─ Phase 3: Filter + truncate
       score >= threshold, ORDER BY score DESC LIMIT top_k
```

### Entity Boost Attenuation

`attenuation = 1 / (1 + 0.001 * (n_linked - 1)^2)`

Entities linked to many memories carry less discriminative value ("Bob" linked to
10K memories has near-zero boost per memory).

### BM25 Normalization

Sigmoid mapping of raw BM25 scores to [0, 1] for cross-query comparability:
`normalized = 1 / (1 + exp(-steepness * (raw - midpoint)))`

---

## 8. Core Operations

### add(messages, filters, metadata)

1. Parse messages, filter system messages
2. Batch embed (OpenAI-compatible API)
3. Hash dedup: MD5(memory), check existing hashes in Lance + batch-internal
4. Build RecordBatch with full payload (data, hash, lemma, timestamps, filters)
5. Lance Dataset::append(batch)
6. Iceberg commit (new snapshot)
7. Insert into history table (event=ADD)
8. Extract entities → search entity store → upsert links
9. Save messages (sliding window of 10 per session_scope)

### search(query, filters, top_k, threshold, rerank)

1. Embed query, lemmatize, extract entities
2. Parallel: semantic ANN (internal_limit=max(4*top_k, 60)), BM25, entity boost
3. Score fusion: final = α·sem + β·bm25 + γ·entity
4. Filter score >= threshold, truncate top_k
5. (Optional) rerank

### get(memory_id), update(memory_id, data), delete(memory_id)

- get: direct lookup by id in Lance
- update: append new version to Lance (immutable), mark old as deleted, log to history
- delete: soft delete (mark in Lance + history with is_deleted=1)

### get_history(memory_id)

Standard SQL query on history table, ORDER BY created_at ASC.

---

## 9. External API

### gRPC MemoryService (port 9090)

```protobuf
service MemoryService {
  rpc Add(AddRequest) returns (AddResponse);
  rpc Search(SearchRequest) returns (SearchResponse);
  rpc Get(GetRequest) returns (GetResponse);
  rpc Update(UpdateRequest) returns (UpdateResponse);
  rpc Delete(DeleteRequest) returns (DeleteResponse);
  rpc DeleteAll(DeleteAllRequest) returns (DeleteAllResponse);
  rpc GetHistory(GetHistoryRequest) returns (GetHistoryResponse);
}
```

Session scoping via filters: at least one of {user_id, agent_id, run_id} required.

### Arrow Flight SQL (port 9091)

DataFusion's built-in `FlightSQLService`. Supports:
- Standard SQL: `SELECT * FROM memories WHERE user_id = 'u1'`
- umbra_search UDTF: `SELECT * FROM umbra_search(...)`
- Iceberg time travel: `FOR TIMESTAMP AS OF '...'`
- Metadata: `GetTables`, `GetSchema`, etc.

---

## 10. Configuration

```toml
[server]
grpc_port = 9090
flight_sql_port = 9091

[storage]
base_path = "file:///data/umbra"
catalog_type = "memory"              # memory | rest | hive

[embedding]
provider = "openai"
model = "text-embedding-3-small"
dimensions = 1536
api_key = "${UMBRA_OPENAI_API_KEY}"
base_url = "https://api.openai.com/v1"
batch_size = 100

[table.memories.index.vector]
type = "ivf_pq"
distance = "cosine"
num_partitions = 100
num_sub_vectors = 96

[search]
semantic_weight = 0.5
bm25_weight = 0.3
entity_boost_weight = 0.2
default_top_k = 20
default_threshold = 0.1
overfetch_multiplier = 4
```

---

## 11. Crate Structure

```
umbra/
├── umbra-core/              # Core engine crate
│   ├── catalog/             # Iceberg Catalog integration
│   │   ├── mod.rs
│   │   ├── schema.rs        # Schema ↔ Arrow Schema conversion
│   │   └── snapshot.rs      # Snapshot management + time travel
│   ├── storage/             # Lance physical storage
│   │   ├── mod.rs           # Dataset lifecycle
│   │   ├── write.rs         # Batch append
│   │   ├── scan.rs          # Scan with pushdown
│   │   └── compaction.rs    # Compaction strategy
│   ├── index/               # Index layer
│   │   ├── mod.rs
│   │   ├── vector.rs        # Lance ANN search
│   │   ├── fulltext.rs      # BM25 search
│   │   └── entity.rs        # Entity graph boost
│   ├── query/               # DataFusion integration
│   │   ├── mod.rs           # Table registration
│   │   ├── tablefunc.rs     # umbra_search UDTF
│   │   ├── udf.rs           # Vector UDFs
│   │   └── optimizer.rs     # Custom optimizer rules
│   ├── ops/                 # Memory operations
│   │   ├── mod.rs           # MemoryOps trait
│   │   ├── add.rs           # Write pipeline
│   │   ├── search.rs        # Multi-signal fusion
│   │   ├── crud.rs          # get/update/delete
│   │   └── history.rs       # History queries
│   ├── embedding/           # Embedding abstraction
│   │   ├── mod.rs           # Embedder trait
│   │   └── openai.rs        # OpenAI-compatible provider
│   └── entity/              # Entity extraction (MVP: rules + dictionary)
│       └── mod.rs
├── umbra-server/            # gRPC + Flight SQL server
│   ├── proto/
│   │   └── umbra.proto
│   ├── service.rs           # MemoryService impl
│   ├── flight.rs            # Flight SQL server
│   └── main.rs
└── Cargo.toml               # Workspace
```

---

## 12. Key Dependencies

```toml
[workspace.dependencies]
# Query engine
datafusion = "XX"
# Table format
iceberg = { git = "https://github.com/apache/iceberg-rust" }
# Storage + vector index
lance = "XX"
lance-datafusion = "XX"
# Common
arrow = "XX"
# gRPC
tonic = "XX"
prost = "XX"
# Serialization
serde = { version = "1", features = ["derive"] }
serde_json = "1"
# Async runtime
tokio = { version = "1", features = ["full"] }
# Utils
uuid = { version = "1", features = ["v4"] }
chrono = "XX"
```

---

## 13. Design Decisions Log

| Decision | Rationale |
|----------|-----------|
| All Rust (no Python/Go service layer) | Single binary, zero FFI overhead, matching user preference |
| Independent service (not embedded library) | Multi-client support, gRPC + Flight SQL dual interface |
| Pure storage engine (no LLM) in MVP | Clear boundary, LLM is caller's concern, faster iteration |
| Lance for vectors, Parquet for structured logs | Lance excels at ANN + FTS; Parquet is standard for historical/audit data |
| Iceberg for metadata management | Snapshots, time travel, partition evolution — all free with iceberg-rust |
| Entity bipartite graph (not a graph DB) | Mem0 proved this is sufficient; no Neo4j/TigerGraph dependency needed |
| MD5 dedup (not content-addressable) | Simple, fast, sufficient; collision risk negligible for memory text |
| Overfetch 4x for fusion candidate pool | Balance recall vs. latency; configurable multiplier |
| config.toml (figment/config crate) | Standard Rust config loading with env var interpolation |
