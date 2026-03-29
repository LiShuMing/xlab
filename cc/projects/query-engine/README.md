# Vectorized Query Engine (vagg)

[![C++20](https://img.shields.io/badge/C%2B%2B-20-blue.svg)](https://isocpp.org/std/the-standard)
[![CMake](https://img.shields.io/badge/CMake-3.16%2B-green.svg)](https://cmake.org)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A high-performance vectorized query engine for hash aggregation in modern C++20. Demonstrates columnar execution, vectorized operations, and analytical query processing optimized for OLAP workloads.

## Features

- **Vectorized Execution**: Process data in columnar chunks (1024/4096 rows)
- **Columnar Storage**: Cache-friendly data layout with contiguous arrays
- **Robin Hood Hash Table**: Efficient hash aggregation with open addressing
- **SIMD-Friendly Design**: Control bytes for vectorized probing
- **Modern C++20**: Concepts, constexpr, and zero-cost abstractions
- **Comprehensive Testing**: Unit tests and microbenchmarks

## Quick Start

### Prerequisites

- CMake 3.16 or higher
- C++20 compatible compiler (GCC 10+, Clang 12+, MSVC 2019+)
- Local thirdparty dependencies (googletest, benchmark in `cc/thirdparty/`)

### Build

```bash
cd cc/projects/query-engine
mkdir -p build && cd build
cmake ..
make -j$(nproc)
```

### Run Tests

```bash
ctest --output-on-failure
```

### Run Benchmarks

```bash
make bench_aggregation
./bench_aggregation
```

## Example Usage

```cpp
#include <vagg/ops/scan_op.h>
#include <vagg/ops/aggregate_op.h>
#include <vagg/vector/vector.h>
#include <iostream>

int main() {
    // Create data source (CSV, memory, etc.)
    auto source = std::make_unique<CsvSource>("data.csv");

    // Build operator pipeline
    auto scan = std::make_unique<ScanOp>(std::move(source));
    auto agg = std::make_unique<AggregateOp>(
        std::move(scan),
        AggregateOp::Options{.group_by = 0, .aggregate = 1}
    );

    // Execute query
    Chunk result;
    while (agg->Next(&result).ok()) {
        // Process results
        auto keys = result.Column(0)->As<FlatVector<int64_t>>();
        auto sums = result.Column(1)->As<FlatVector<int64_t>>();

        for (int i = 0; i < result.num_rows(); ++i) {
            std::cout << "Key: " << keys->Value(i)
                      << " Sum: " << sums->Value(i) << std::endl;
        }
    }

    return 0;
}
```

## Architecture

vagg implements a vectorized query execution engine inspired by modern analytical databases.

### Core Components

| Component | Description | Key Features |
|-----------|-------------|--------------|
| `Vector<T>` | Columnar data storage | Contiguous arrays, null handling |
| `Chunk` | Row batch | Collection of vectors, N rows |
| `HashTable` | Aggregation hash table | Robin Hood, open addressing |
| `Operator` | Query operators | Pull-based execution |

### Execution Model

```
┌─────────┐    ┌─────────┐    ┌─────────────┐    ┌─────────┐
│ ScanOp  │───→│ Filter  │───→│ AggregateOp │───→│ SinkOp  │
└─────────┘    └─────────┘    └─────────────┘    └─────────┘
   (CSV)          (Pred)         (Hash Agg)       (Output)
```

1. **Scan**: Read data in chunks from source
2. **Filter**: Apply predicates using selection vectors
3. **Aggregate**: Build hash table, update aggregates
4. **Sink**: Collect and output results

### Key Optimizations

- **Columnar Layout**: Contiguous memory for SIMD
- **Selection Vectors**: Filter without copying
- **Robin Hood Hashing**: Cache-friendly probing
- **Prefetching**: Reduce cache misses
- **Chunk Processing**: Amortize overhead

## Project Structure

```
cc/projects/query-engine/
├── include/vagg/            # Public headers
│   ├── common/              # Status, Slice
│   ├── vector/              # Columnar vectors
│   ├── ht/                  # Hash table
│   ├── ops/                 # Query operators
│   ├── exec/                # Execution context
│   ├── agg/                 # Aggregation functions
│   └── io/                  # Data sources
├── src/                     # Implementation
│   ├── common/              # Status, utilities
│   ├── vector/              # Vector types
│   ├── ht/                  # Hash table code
│   └── ops/                 # Operators
├── tests/                   # Unit tests
├── bench/                   # Benchmarks
├── docs/                    # Documentation
│   ├── api/                 # API reference
│   └── architecture/        # Design docs
└── CMakeLists.txt           # Build config
```

## Performance

Benchmarks on Intel i7-9700K (GCC 11, -O3):

| Workload | Throughput | Notes |
|----------|------------|-------|
| Hash Aggregation (low cardinality) | ~50M rows/sec | Few groups |
| Hash Aggregation (high cardinality) | ~10M rows/sec | Many groups |
| Hash Table Insert | ~20M ops/sec | Single-threaded |
| Hash Table Probe | ~30M ops/sec | Single-threaded |

*Results vary by hardware and data distribution.*

## Development

### Code Style

- **Classes**: `PascalCase` (e.g., `HashTable`, `AggregateOp`)
- **Functions**: `camelCase` (e.g., `findOrInsert()`)
- **Variables**: `snake_case` (e.g., `hash_table_`)
- **Constants**: `kPascalCase` (e.g., `kMaxLoadFactor`)

See [RULES.md](./RULES.md) for complete standards.

### Adding an Operator

```cpp
class MyOp : public Operator {
public:
    explicit MyOp(std::unique_ptr<Operator> child);
    Status Prepare(ExecContext* ctx) override;
    Status Next(Chunk* out) override;
};
```

### Building with Sanitizers

```bash
cmake -DCMAKE_CXX_FLAGS="-fsanitize=address,undefined" ..
make
```

## Roadmap

- [x] Core: Vector, Chunk, HashTable
- [x] Operators: Scan, Aggregate, Sink
- [x] Tests: Hash table, aggregation, vector
- [ ] Join: Hash join implementation
- [ ] Sort: External sort operator
- [ ] SIMD: Vectorized hash table probing
- [ ] Optimizer: Simple query planner
- [ ] Parquet: Columnar file format support

## Documentation

- [API Reference](./docs/api/)
- [Architecture Documentation](./docs/architecture/)
- [Agent Guide](./AGENTS.md)
- [Coding Standards](./RULES.md)
- [TODOs](./TODOS.md)

## Acknowledgments

- Design inspired by Velox, DuckDB, and ClickHouse
- Built for learning columnar execution internals

---

*Original Chinese documentation: See [README.md.bak](./README.md.bak) for the original Chinese version with detailed design notes.*
