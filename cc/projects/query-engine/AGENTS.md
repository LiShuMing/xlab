# Vectorized Query Engine (vagg) Agent Guide

This file provides guidance for AI agents working on the vagg project.

## Project Overview

vagg is a vectorized query engine lab in modern C++20. It currently focuses on
typed key-value chunks, hash aggregation, prototype hash join, in-memory sort,
Top-N, and benchmark-driven OLAP execution experiments.

## Build Commands

### Prerequisites

- CMake 3.16+
- C++20 compatible compiler (GCC 10+, Clang 12+)
- Local thirdparty dependencies in `cc/thirdparty/` (googletest, benchmark)

### Build

```bash
cd cc/projects/query-engine
mkdir -p build && cd build
cmake ..
make -j$(nproc)
```

### Build Types

```bash
# Release build (default)
cmake -DCMAKE_BUILD_TYPE=Release ..

# Debug build
cmake -DCMAKE_BUILD_TYPE=Debug ..

# With sanitizers
cmake -DCMAKE_BUILD_TYPE=Debug -DCMAKE_CXX_FLAGS="-fsanitize=address,undefined" ..
```

## Test Commands

### Run All Tests

```bash
cd cc/projects/query-engine/build
ctest --output-on-failure
```

### Run Specific Tests

```bash
# Run individual test suites
./test_hash_table
./test_aggregation
./test_vector
./test_hash_join
./test_sort

# Run with verbose output
./test_hash_table --gtest_verbose=1
```

## Benchmark Commands

```bash
# Build benchmarks
make bench_aggregation

# Run benchmarks
./bench_aggregation
```

## Directory Structure

```
cc/projects/query-engine/
├── include/vagg/            # Public headers
│   ├── common/              # Status, Slice, utilities
│   ├── vector/              # Columnar vector types
│   ├── ht/                  # Hash table implementation
│   ├── ops/                 # Query operators
│   ├── exec/                # Execution context
│   ├── agg/                 # Aggregation functions
│   └── io/                  # Data source I/O
├── src/                     # Source files
│   ├── common/              # Common utilities
│   ├── vector/              # Vector implementations
│   ├── ht/                  # Hash table code
│   └── ops/                 # Operator implementations
├── tests/                   # Unit tests
├── bench/                   # Benchmarks
├── docs/                    # Documentation
│   ├── api/                 # API reference
│   └── architecture/        # Design documents
├── CMakeLists.txt           # Build configuration
└── README.md                # Project documentation
```

## Dependencies

- **googletest**: Unit testing framework (from cc/thirdparty/googletest)
- **benchmark**: Microbenchmarking library (from cc/thirdparty/benchmark)
- **CMake**: Build system

## Architecture Overview

vagg implements a vectorized query execution engine:

### Core Components

1. **Vector**: Columnar data representation
   - `FlatVector<T>`: Typed column vector
   - `ValidityBitmap`: Null handling
   - `SelectionVector`: Filtered rows without copying

2. **HashTable**: Open-addressing hash table for aggregation
   - Open addressing for cache efficiency
   - Current implementation uses linear probing
   - Robin Hood/control bytes are future design-track items
   - Find-or-insert for aggregation

3. **Operators**: Pull-based execution
   - `ScanOp`: Read data from source
   - `HashAggregateOp`: Hash aggregation
   - `HashJoinOp`: Prototype single-key inner join
   - `SortOp` / `TopNOp`: In-memory ordering prototypes
   - `SinkOp`: Output results

4. **Chunk**: Row batch (N rows, typically 1024/4096)
   - Collection of column vectors
   - Unit of operator processing

### Execution Model

```
ScanOp → [Filter] → HashAggregateOp → SinkOp

1. Scan reads chunks from data source
2. Optional filter applies predicates (planned)
3. Aggregate builds hash table, updates aggregates
4. Sink collects final results
```

### Key Optimizations

- **Vectorized execution**: Process chunks, not rows
- **Columnar layout**: Cache-friendly data access
- **SIMD-friendly hash table**: Control bytes for fast probing
- **Selection vectors**: Avoid copying filtered data
- **Prefetching**: Reduce cache misses in hash table

## Key Components

### FlatVector<T>

Columnar data container:
- Contiguous storage: `T* data()`
- Null handling: `ValidityBitmap`
- Type-safe templated interface

```cpp
FlatVector<int64_t> keys(1024);
keys.ValueAt(0) = 42;
keys.SetNull(1);
```

### HashTable

Open-addressing hash table:
- Current baseline uses linear probing
- Robin Hood displacement is planned
- Control bytes for SIMD comparison are planned
- Load factor management
- Supports both aggregation and join modes

### Operator

Base class for query operators:
```cpp
class Operator {
public:
    virtual ~Operator() = default;
    virtual Status Prepare(ExecContext*) = 0;
    virtual Status Next(Chunk* out) = 0;
};
```

### Status

Error handling:
```cpp
Status s = op->Next(&chunk);
if (!s.ok()) { /* handle error */ }
```

## Coding Patterns

### Error Handling

```cpp
Status HashTable::Insert(const Slice& key, Entry** entry) {
    if (key.empty()) {
        return Status::InvalidArgument("Empty key");
    }
    // ... implementation
    return Status::Ok();
}
```

### Vectorized Processing

```cpp
Status MyOp::Next(Chunk* out) {
    KeyValueChunk input;
    RETURN_IF_ERROR(child_->Next(&input));

    // Process the whole chunk instead of asking the child row by row.
    for (size_t i = 0; i < input.num_rows(); ++i) {
        // Operator-specific update.
    }
    return Status::Ok();
}
```

### Hash Table Usage

```cpp
// Aggregation
HashTable<int32_t, int64_t> ht;
for (size_t i = 0; i < chunk.num_rows(); ++i) {
    auto* entry = ht.FindOrInsert(chunk.GetColumn<0>().ValueAt(i));
    entry->value += chunk.GetColumn<1>().ValueAt(i);
}
```

## Common Tasks

### Adding a New Operator

1. Create header in `include/vagg/ops/`
2. Create implementation in `src/ops/` if it is not intentionally header-only
3. Add implementation file to CMakeLists.txt when needed
4. Create tests in `tests/`
5. Document in AGENTS.md

### Adding a Vector Type

1. Add specialization in `include/vagg/vector/`
2. Implement type-specific operations
3. Add type to test matrix

### Adding Aggregation Functions

1. Add a small aggregate descriptor or function class
2. Implement update logic in `HashAggregateOp`
3. Add tests for new function

## Performance Considerations

- **Batch size**: 1024 or 4096 rows typical
- **Cache efficiency**: Columnar layout, SoA structures
- **Branch prediction**: Minimize branches in hot loops
- **SIMD**: control bytes/vectorized compare are future experiments
- **Prefetching**: Preload hash table entries

## References

- [Project README](./README.md)
- [Coding Standards](./RULES.md)
- [API Documentation](./docs/api/)
- [Architecture Documentation](./docs/architecture/)
- [TODOs](./TODOS.md)
