# Vectorized Query Engine (vagg)

[![C++20](https://img.shields.io/badge/C%2B%2B-20-blue.svg)](https://isocpp.org/std/the-standard)
[![CMake](https://img.shields.io/badge/CMake-3.16%2B-green.svg)](https://cmake.org)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A compact vectorized query engine lab in modern C++20. The current engine focuses on
typed key-value batches, hash aggregation, prototype hash join, in-memory sort,
Top-N, and benchmark-driven OLAP execution experiments.

## Features

- **Vectorized Execution**: Process data in columnar chunks (1024/4096 rows)
- **Columnar Storage**: Cache-friendly data layout with contiguous arrays
- **Open-Addressing Hash Table**: Linear probing baseline for aggregation experiments
- **Prototype Join and Sort**: Single-key inner hash join, in-memory sort, and Top-N
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
#include <vagg/ops/aggregate_op.h>
#include <vagg/ops/scan_op.h>
#include <vagg/ops/sink_op.h>
#include <vagg/vector/vector.h>

#include <iostream>
#include <memory>
#include <vector>

int main() {
    std::vector<int32_t> keys = {1, 2, 1, 3, 2};
    std::vector<int64_t> values = {10, 20, 30, 40, 50};

    auto source = std::make_unique<vagg::MemoryDataSource>(keys, values, 1024);
    auto scan = std::make_unique<vagg::ScanOp>(std::move(source));
    auto agg = std::make_unique<vagg::HashAggregateOp>(std::move(scan));

    vagg::ExecContext ctx;
    auto status = agg->Prepare(&ctx);
    if (!status.ok()) {
        std::cerr << status.ToString() << std::endl;
        return 1;
    }

    vagg::KeyValueChunk out;
    while (true) {
        status = agg->Next(&out);
        if (status.code() == vagg::StatusCode::kEndOfFile) {
            break;
        }
        if (!status.ok()) {
            std::cerr << status.ToString() << std::endl;
            return 1;
        }

        auto& out_keys = out.GetColumn<0>();
        auto& sums = out.GetColumn<1>();
        for (size_t i = 0; i < out.num_rows(); ++i) {
            std::cout << out_keys.ValueAt(i) << "\t" << sums.ValueAt(i) << "\n";
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
| `FlatVector<T>` | Columnar data storage | Contiguous arrays, null handling |
| `Chunk` | Row batch | Collection of vectors, N rows |
| `HashTable` | Aggregation hash table | Open addressing, linear probing baseline |
| `Operator` | Query operators | Pull-based execution |

### Execution Model

```
┌─────────┐    ┌─────────┐    ┌─────────────┐    ┌─────────┐
│ ScanOp  │───→│ Filter  │───→│ HashAggOp   │───→│ SinkOp  │
└─────────┘    └─────────┘    └─────────────┘    └─────────┘
   (CSV)          (Pred)         (Hash Agg)       (Output)
```

1. **Scan**: Read data in chunks from source
2. **Filter**: Apply predicates using selection vectors (planned)
3. **Aggregate**: Build hash table, update aggregates
4. **Sink**: Collect and output results

### Key Optimizations

- **Columnar Layout**: Contiguous memory for SIMD
- **Selection Vectors**: Filter without copying
- **Linear-Probing Baseline**: Simple hash table suitable for measured improvements
- **Prefetching**: Planned experiment to reduce cache misses
- **Chunk Processing**: Amortize overhead

## Project Structure

```
cc/projects/query-engine/
├── include/vagg/            # Public headers
│   ├── common/              # Status, Slice
│   ├── vector/              # Columnar vectors
│   ├── ht/                  # Hash table
│   ├── ops/                 # Query operators
│   └── exec/                # Execution context
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

- **Classes**: `PascalCase` (e.g., `HashTable`, `HashAggregateOp`)
- **Functions**: `camelCase` (e.g., `findOrInsert()`)
- **Variables**: `snake_case` (e.g., `hash_table_`)
- **Constants**: `kPascalCase` (e.g., `kMaxLoadFactor`)

See [RULES.md](./RULES.md) for complete standards.

### Adding an Operator

```cpp
class MyOp : public TransformOperator {
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
- [x] Tests: Hash table, aggregation, vector, hash join, sort
- [x] Join: Prototype single-key inner hash join
- [x] Sort: In-memory sort and Top-N prototypes
- [ ] Pipeline: Filter, Project, Limit
- [ ] Join: Correct duplicate-key semantics and LEFT join
- [ ] Sort: Multi-key sort and complete Top-N semantics
- [ ] SIMD: Vectorized hash table probing
- [ ] Optimizer: Tiny logical plan after operator semantics stabilize
- [ ] Storage: General memory source before Parquet/ORC

## Documentation

- [API Reference](./docs/api/)
- [Architecture Documentation](./docs/architecture/)
- [Design](./DESIGN.md)
- [Agent Guide](./AGENTS.md)
- [Coding Standards](./RULES.md)
- [TODOs](./TODOS.md)

## Acknowledgments

- Design inspired by Velox, DuckDB, and ClickHouse
- Built for learning columnar execution internals
