# AI Agent Guidelines

## Overview

This document provides guidelines for AI Agents working on the RDB (Rust Database) project.

## Project Architecture

RDB is a minimal relational database implementation demonstrating core RDBMS components:

```
rdb/
├── src/
│   ├── main.rs          # Entry point with async runtime
│   ├── parser/          # SQL parser (AST-based)
│   ├── analyzer/        # Semantic analysis
│   ├── planner/         # Query planner (logical plans)
│   ├── executor/        # Query execution engine
│   └── storage/         # Storage engine
│       ├── mod.rs
│       ├── catalog.rs       # Table/schema metadata
│       ├── segment.rs       # Storage segments
│       ├── column_reader.rs # Column-oriented reads
│       ├── delete_vector.rs # Soft delete tracking
│       ├── index.rs         # Index structures
│       ├── manifest.rs      # Storage manifest
│       ├── compaction.rs    # Compaction strategy
│       ├── txn.rs           # Transaction management
│       └── object_store.rs  # Object storage abstraction
```

## Key Components

### Parser (`src/parser/`)
- Parses SQL into AST (Abstract Syntax Tree)
- Currently supports basic SELECT
- Extendable for INSERT, UPDATE, DELETE, CREATE TABLE

### Analyzer (`src/analyzer/`)
- Semantic analysis on AST
- Type checking, table resolution
- Validation of query structure

### Planner (`src/planner/`)
- Converts AST to logical query plan
- Optimization passes
- Plan node types: Scan, Filter, Project, Join, Aggregate

### Executor (`src/executor/`)
- Executes query plans
- Pull-based (volcano) or push-based execution
- Handles data flow between operators

### Storage (`src/storage/`)
- Column-oriented storage design
- Segment-based organization
- Compression support (zstd, lz4)
- Transaction support with MVCC
- Index support (B-tree, bitmap)

## Dependencies

| Crate | Purpose |
|-------|---------|
| `tokio` | Async runtime |
| `uuid` | Unique identifiers |
| `roaring` | Bitmap operations for delete vectors |
| `bytes` | Byte buffer management |
| `parking_lot` | Fast synchronization primitives |
| `serde` | Serialization |
| `zstd` / `lz4_flex` | Compression |
| `crc32fast` / `xxhash-rust` | Checksums and hashing |
| `async-trait` / `async-recursion` | Async utilities |
| `bincode` | Binary serialization |

## Building and Testing

```bash
# Build
cargo build
cargo build --release

# Run
cargo run

# Test
cargo test

# Check
cargo check
cargo clippy -- -D warnings
cargo fmt -- --check
```

## Coding Standards

1. **Async/Await**: Use tokio for async operations
2. **Error Handling**: Use `Result<T, E>` with custom error types
3. **Type Safety**: Leverage Rust's type system for correctness
4. **Documentation**: Document all public APIs with examples
5. **Testing**: Write unit tests for all storage and execution code

## Common Tasks

### Adding a New SQL Statement

1. Extend AST in `src/parser/ast.rs`
2. Add parser logic in `src/parser/mod.rs`
3. Add analysis in `src/analyzer/mod.rs`
4. Add plan node in `src/planner/mod.rs`
5. Add execution in `src/executor/mod.rs`

### Extending Storage

1. Modify appropriate module in `src/storage/`
2. Update `Segment` or `Catalog` if schema changes
3. Ensure backward compatibility or add migration
4. Add tests for persistence and recovery

### Adding an Operator

1. Define plan node in `src/planner/mod.rs`
2. Implement execution in `src/executor/mod.rs`
3. Add optimizer rules if applicable
4. Test with integration tests

## Prohibited Actions

1. **DO NOT** use blocking I/O in async context
2. **DO NOT** ignore errors with `unwrap()` in production code
3. **DO NOT** break storage format compatibility without migration
4. **DO NOT** skip tests for storage engine changes
5. **DO NOT** use `unsafe` without detailed safety comments

## Performance Considerations

- Storage is column-oriented - favor column-wise operations
- Use roaring bitmaps for delete vectors efficiently
- Consider compression for cold data
- Minimize allocations in hot paths
- Use `parking_lot` locks for better performance

## Testing Strategy

- Unit tests for each component
- Integration tests for query execution
- Property-based testing for storage operations
- Benchmarks for performance-critical paths

## Reading Order for New Contributors

1. `src/main.rs` - Entry point and high-level flow
2. `src/parser/ast.rs` - AST definitions
3. `src/storage/mod.rs` - Storage abstractions
4. `src/executor/mod.rs` - Execution model
5. Example queries in tests

## Communication Style

- Be precise about data structures and lifetimes
- Reference specific modules and types
- Include code examples for complex logic
- Explain the "why" behind architectural decisions
