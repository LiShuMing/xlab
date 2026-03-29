# Vectorized Query Engine (vagg) Agent Guide

This file provides guidance for AI agents working on the vagg project.

## Project Overview

vagg is a vectorized query engine for hash aggregation in modern C++20. It demonstrates columnar execution, vectorized operations, and hash-based aggregation optimized for analytical workloads.

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
   - `Vector<T>`: Typed column vector
   - `ValidityBitmap`: Null handling
   - `SelectionVector`: Filtered rows without copying

2. **HashTable**: Robin Hood hashing for aggregation
   - Open addressing for cache efficiency
   - Control bytes for SIMD-friendly probing
   - Find-or-insert for aggregation

3. **Operators**: Pull-based execution
   - `ScanOp`: Read data from source
   - `AggregateOp`: Hash aggregation
   - `SinkOp`: Output results

4. **Chunk**: Row batch (N rows, typically 1024/4096)
   - Collection of column vectors
   - Unit of operator processing

### Execution Model

```
ScanOp → [Filter] → AggregateOp → SinkOp

1. Scan reads chunks from data source
2. Optional filter applies predicates
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

### Vector<T>

Columnar data container:
- Contiguous storage: `T* data()`
- Null handling: `ValidityBitmap`
- Type-safe templated interface

```cpp
FlatVector<int64_t> keys(1024);
keys.SetValue(0, 42);
keys.SetNull(1);
```

### HashTable

Robin Hood hash table:
- Open addressing with linear probing
- Control bytes for SIMD comparison
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
    return Status::OK();
}
```

### Vectorized Processing

```cpp
Status AggregateOp::Next(Chunk* out) {
    Chunk input;
    VAGG_RETURN_NOT_OK(child_->Next(&input));

    // Process entire chunk vectorized
    for (int i = 0; i < input.num_rows(); ++i) {
        // Aggregate update
    }
    return Status::OK();
}
```

### Hash Table Usage

```cpp
// Aggregation
HashTable ht;
for (auto& row : chunk) {
    auto* entry = ht.FindOrInsert(row.key);
    entry->sum += row.value;
}
```

## Common Tasks

### Adding a New Operator

1. Create header in `include/vagg/ops/`
2. Create implementation in `src/ops/`
3. Add to CMakeLists.txt
4. Create tests in `tests/`
5. Document in AGENTS.md

### Adding a Vector Type

1. Add specialization in `include/vagg/vector/`
2. Implement type-specific operations
3. Add type to test matrix

### Adding Aggregation Functions

1. Add function enum in `include/vagg/agg/`
2. Implement update logic in AggregateOp
3. Add tests for new function

## Performance Considerations

- **Batch size**: 1024 or 4096 rows typical
- **Cache efficiency**: Columnar layout, SoA structures
- **Branch prediction**: Minimize branches in hot loops
- **SIMD**: Use control bytes for vectorized compare
- **Prefetching**: Preload hash table entries

## References

- [Project README](./README.md)
- [Coding Standards](./RULES.md)
- [API Documentation](./docs/api/)
- [Architecture Documentation](./docs/architecture/)
- [TODOs](./TODOS.md)
