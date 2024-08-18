# Project Rules and Standards

## Overview

This document defines the engineering standards, coding conventions, and best practices for the RDB (Rust Database) project.

## Code Style

### Rust Standards

- **Rust Edition**: 2021
- **Formatting**: `cargo fmt` with default settings
- **Linting**: `cargo clippy` with strict settings (`-D warnings`)

### Commands

```bash
# Format code
cargo fmt

# Check formatting
cargo fmt -- --check

# Run lints
cargo clippy -- -D warnings

# Build
cargo build

# Test
cargo test
```

## Architecture Standards

### Module Organization

```
src/
├── main.rs              # Async runtime entry point
├── parser/              # SQL parsing
│   ├── mod.rs
│   └── ast.rs           # AST definitions
├── analyzer/            # Semantic analysis
│   └── mod.rs
├── planner/             # Query planning
│   └── mod.rs
├── executor/            # Query execution
│   └── mod.rs
└── storage/             # Storage engine
    ├── mod.rs           # Storage traits
    ├── catalog.rs       # Metadata management
    ├── segment.rs       # Segment storage
    ├── column_reader.rs # Column I/O
    ├── delete_vector.rs # Delete tracking
    ├── index.rs         # Index structures
    ├── manifest.rs      # Storage manifest
    ├── compaction.rs    # Compaction logic
    ├── txn.rs           # Transactions
    └── object_store.rs  # Storage abstraction
```

### Naming Conventions

- **Modules**: `snake_case`
- **Types/Structs**: `PascalCase` (e.g., `QueryPlan`, `StorageEngine`)
- **Traits**: `PascalCase` descriptive (e.g., `Executor`, `Storage`)
- **Functions/Methods**: `snake_case`
- **Constants**: `SCREAMING_SNAKE_CASE`
- **Generic Parameters**: Single uppercase (e.g., `T`, `K`, `V`)

### Type Naming

- `Expr` - Expression nodes
- `Plan` - Query plan nodes
- `Operator` - Physical operators
- `Page` / `Block` - Storage units
- `Segment` - Collection of pages
- `Tuple` / `Row` - Data records
- `Column` / `Field` - Schema elements

## Error Handling

### Error Types

Define custom error types for each module:

```rust
#[derive(Debug, Error)]
pub enum StorageError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("Corrupted data at offset {offset}: {message}")]
    Corruption { offset: u64, message: String },

    #[error("Page not found: {0}")]
    PageNotFound(PageId),
}
```

### Error Guidelines

1. Use `thiserror` for error definitions
2. Implement `From` for standard errors
3. Include context in error messages
4. Never use `unwrap()` or `expect()` in library code
5. Use `?` operator for error propagation

### Async Error Handling

```rust
pub async fn read_page(&self, id: PageId) -> Result<Page, StorageError> {
    let data = self.file.read_exact(...).await
        .map_err(StorageError::Io)?;
    Page::decode(&data)?
}
```

## Async/Await Patterns

### Runtime

- Use `tokio` as the async runtime
- Enable only needed features in Cargo.toml

### Async Guidelines

1. Mark async functions with `async fn`
2. Use `.await` for async calls
3. Prefer `&self` over `self` in async methods
4. Use `Arc<Mutex<T>>` for shared state
5. Use `parking_lot::Mutex` for better performance

```rust
use parking_lot::Mutex;
use std::sync::Arc;

pub struct StorageEngine {
    catalog: Arc<Mutex<Catalog>>,
}

impl StorageEngine {
    pub async fn create_table(&self, schema: Schema) -> Result<TableId> {
        let mut catalog = self.catalog.lock();
        catalog.create_table(schema)
    }
}
```

## Storage Engine Standards

### Column-Oriented Design

RDB uses column-oriented storage:

```rust
pub struct ColumnChunk {
    pub column_id: ColumnId,
    pub data: Bytes,
    pub null_bitmap: Option<RoaringBitmap>,
    pub statistics: ColumnStats,
}
```

### Segment Structure

```rust
pub struct Segment {
    pub id: SegmentId,
    pub columns: Vec<ColumnChunk>,
    pub delete_vector: DeleteVector,
    pub metadata: SegmentMetadata,
}
```

### Persistence Rules

1. Write to WAL first, then apply to storage
2. Use checksums for all disk writes
3. Support compression (zstd for cold, lz4 for hot)
4. Maintain manifest for storage state
5. Implement proper fsync sequences

## Query Processing

### AST Design

```rust
pub enum Statement {
    Select(SelectStmt),
    Insert(InsertStmt),
    Update(UpdateStmt),
    Delete(DeleteStmt),
    CreateTable(CreateTableStmt),
    DropTable(DropTableStmt),
}

pub struct SelectStmt {
    pub projection: Vec<Expr>,
    pub from: Vec<TableRef>,
    pub filter: Option<Expr>,
    pub group_by: Vec<Expr>,
    pub having: Option<Expr>,
    pub order_by: Vec<OrderByExpr>,
    pub limit: Option<Limit>,
}
```

### Plan Nodes

```rust
pub enum PlanNode {
    Scan(ScanNode),
    Filter(FilterNode),
    Project(ProjectNode),
    Join(JoinNode),
    Aggregate(AggregateNode),
    Sort(SortNode),
    Limit(LimitNode),
}
```

### Execution Model

- Pull-based (volcano) iterator model
- Each operator implements `next()` method
- Batch processing for vectorized execution

```rust
pub trait Executor {
    fn next(&mut self) -> Result<Option<Batch>>;
    fn schema(&self) -> &Schema;
}
```

## Testing Standards

### Test Organization

```
src/
├── storage/
│   ├── mod.rs
│   └── tests/           # Module tests
│       └── mod.rs
tests/
├── integration_tests.rs # Integration tests
└── fixtures/
    └── test_data.sql
```

### Unit Tests

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_segment_write_read() {
        let segment = create_test_segment();
        let bytes = segment.encode();
        let decoded = Segment::decode(&bytes).unwrap();
        assert_eq!(segment.id, decoded.id);
    }

    #[tokio::test]
    async fn test_async_storage() {
        let storage = StorageEngine::new(temp_dir()).await.unwrap();
        // test async operations
    }
}
```

### Test Data

- Use deterministic data for reproducibility
- Clean up temp directories after tests
- Use `tempfile` crate for temp directories

## Documentation

### Code Documentation

- All public items must have doc comments
- Include examples for complex APIs
- Document panics and errors

```rust
/// Reads a column chunk from storage.
///
/// # Arguments
/// * `segment_id` - The segment containing the column
/// * `column_id` - The column to read
///
/// # Returns
/// The column chunk data or an error.
///
/// # Errors
/// Returns `StorageError::PageNotFound` if segment doesn't exist.
///
/// # Example
/// ```
/// let chunk = storage.read_column(seg_id, col_id).await?;
/// ```
pub async fn read_column(&self, segment_id: SegmentId, column_id: ColumnId)
    -> Result<ColumnChunk, StorageError>;
```

### Architecture Documentation

Document in `docs/architecture/`:
- Storage format specification
- Query execution overview
- Transaction model
- Recovery protocol

## Unsafe Code

### Guidelines

1. Minimize unsafe code usage
2. Encapsulate unsafe in safe abstractions
3. Document all safety invariants

```rust
/// # Safety
/// Caller must ensure:
/// - ptr is non-null and properly aligned
/// - ptr points to valid memory of at least `len` bytes
pub unsafe fn read_bytes_unchecked(ptr: *const u8, len: usize) -> &[u8] {
    std::slice::from_raw_parts(ptr, len)
}
```

## Performance Guidelines

### Critical Paths

- Minimize allocations in hot paths
- Use object pools for frequently allocated objects
- Prefer stack allocation for small fixed-size data
- Use `Bytes` for zero-copy buffer sharing

### Compression

- zstd for cold storage (better compression)
- lz4 for hot data (faster decompression)
- Compress at segment boundaries

### Caching

- Cache hot segments in memory
- Use LRU eviction policy
- Track cache hit/miss metrics

## Commit Message Convention

Format: `<type>(<scope>): <description>`

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting
- `refactor`: Code restructuring
- `perf`: Performance improvement
- `test`: Test changes
- `chore`: Maintenance

Scopes:
- `parser`, `analyzer`, `planner`, `executor`, `storage`

Examples:
```
feat(storage): add segment compression with zstd
fix(parser): handle escaped quotes in strings
perf(executor): reduce allocations in hash join
```

## CI/CD Requirements

Required checks:
- `cargo fmt -- --check`
- `cargo clippy -- -D warnings`
- `cargo test`
- `cargo doc --no-deps`

## Dependencies Policy

### Allowed Dependencies

- `tokio` - Async runtime
- `serde` / `bincode` - Serialization
- `bytes` - Buffer management
- `parking_lot` - Synchronization
- `roaring` - Bitmap operations
- `zstd` / `lz4_flex` - Compression
- `crc32fast` / `xxhash-rust` - Hashing
- `uuid` - Unique identifiers

### Adding Dependencies

1. Check if functionality exists in std
2. Evaluate: maintenance, size, license
3. Pin to specific version in Cargo.toml
4. Document why it's needed

## Security Considerations

1. Validate all input sizes before allocation
2. Use checked arithmetic for size calculations
3. Limit recursion depth in parser
4. Sanitize file paths in object store
5. Use constant-time comparison for sensitive data
