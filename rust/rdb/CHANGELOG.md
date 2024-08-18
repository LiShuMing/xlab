# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- INSERT statement support
- UPDATE/DELETE statements
- CREATE TABLE statement
- B-tree index implementation
- Transaction isolation levels
- WAL (Write-Ahead Logging)
- Recovery protocol

## [0.1.0] - 2024-XX-XX

### Added
- Initial database implementation with modular architecture
- **Parser module** (`src/parser/`)
  - AST definitions for SQL statements
  - Basic SELECT query parsing
  - Support for: SELECT, FROM, WHERE, ORDER BY, LIMIT

- **Analyzer module** (`src/analyzer/`)
  - Semantic analysis framework
  - Table resolution
  - Type checking infrastructure

- **Planner module** (`src/planner/`)
  - Logical query plan generation
  - Plan node types: Scan, Filter, Project
  - Cost-based optimization framework

- **Executor module** (`src/executor/`)
  - Pull-based (volcano) iterator execution model
  - Scan, Filter, Project operators
  - Batch-oriented processing

- **Storage module** (`src/storage/`)
  - Column-oriented storage engine
  - Segment-based storage organization
  - Catalog for metadata management
  - Column reader for I/O operations
  - Delete vector for soft deletes (using roaring bitmaps)
  - Index infrastructure
  - Storage manifest for state tracking
  - Compaction strategy framework
  - Transaction management (MVCC foundation)
  - Object store abstraction for pluggable backends

### Storage Features
- Column chunk encoding/decoding
- Compression support (zstd, lz4 via dependencies)
- Checksum verification (crc32fast, xxhash-rust)
- Async I/O with tokio
- Memory-mapped file support ready

### Dependencies
- `tokio` - Async runtime
- `uuid` - Unique identifiers
- `roaring` - Bitmap operations for delete vectors
- `bytes` - Zero-copy buffer management
- `parking_lot` - High-performance synchronization
- `serde` / `bincode` - Serialization
- `zstd` / `lz4_flex` - Compression
- `crc32fast` / `xxhash-rust` - Hashing and checksums
- `async-trait` / `async-recursion` - Async utilities

### Project Structure
```
rdb/
├── Cargo.toml
├── src/
│   ├── main.rs
│   ├── parser/
│   │   ├── mod.rs
│   │   └── ast.rs
│   ├── analyzer/
│   │   └── mod.rs
│   ├── planner/
│   │   └── mod.rs
│   ├── executor/
│   │   └── mod.rs
│   └── storage/
│       ├── mod.rs
│       ├── catalog.rs
│       ├── segment.rs
│       ├── column_reader.rs
│       ├── delete_vector.rs
│       ├── index.rs
│       ├── manifest.rs
│       ├── compaction.rs
│       ├── txn.rs
│       └── object_store.rs
└── README.md
```

### Example Usage
```rust
// Parse SQL
let sql = "SELECT * FROM users WHERE id = 1";
let ast = parser::parse(sql)?;

// Analyze
let analyzed = analyzer::analyze(ast)?;

// Plan
let plan = planner::plan(analyzed)?;

// Execute
let results = executor::execute(plan).await?;
```

## [0.0.1] - 2024-XX-XX

### Added
- Project initialization
- Cargo project setup
- README with architecture overview
- Initial module structure
