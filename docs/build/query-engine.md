# query-engine Project (C++)

## Overview

A vectorized query engine implementation in C++20 for learning high-performance OLAP execution.

**Goal:** Build an extensible query engine framework with focus on performance optimization.

## Goals

1. **Columnar Execution** - Vectorized operators for high throughput
2. **High-Performance HashTable** - Optimized for aggregation and joins
3. **Extensible Framework** - Plugin-style operator architecture
4. **Performance Verification** - Benchmarks + macOS Instruments profiling

## Knowledge Dependencies

### C++ Systems Programming
- [C++20 Features](../learn/cpp20-features.md)
- [Memory Layout & Cache](../learn/memory-cache.md)
- [SIMD/Vectorization](../learn/simd-vectorization.md)
- [Hash Table Design](../learn/hash-table-design.md)

### Database Execution
- [Vectorized Execution](../learn/vectorized-execution.md)
- [Query Execution](../learn/query-execution.md)
- [Columnar Storage](../learn/columnar-storage.md)
- [Aggregation Algorithms](../learn/aggregation-algorithms.md)

### Performance Engineering
- [Benchmarking](../learn/benchmarking.md)
- [Profiling with Instruments](../learn/instruments-profiling.md)
- [Cache Optimization](../learn/cache-optimization.md)
- [Branch Prediction](../learn/branch-prediction.md)

### Reference Implementations
- [ClickHouse](../read/code/clickhouse/)
- [DuckDB](../read/code/duckdb/)
- [Velox](../read/code/velox/)
- [DataFusion](../read/code/datafusion/)

## Key Decisions

| Decision | Context | Rationale |
|----------|---------|-----------|
| C++20 | 现代特性，性能优先 | Concepts, ranges, coroutines |
| Columnar layout | OLAP workload | Cache-friendly, SIMD-friendly |
| Robin Hood Hash | Agg + Join reuse | Cache-friendly probing |
| Open addressing | Simplicity + speed | vs Chaining for cache |
| Control bytes | SIMD optimization | SwissTable-style tags |
| Arena allocator | Memory management | Reduce allocation overhead |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Query Engine                        │
├─────────────────────────────────────────────────────────┤
│  Operators                                               │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │
│  │ ScanOp  │─▶│ FilterOp│─▶│ProjectOp│─▶│HashAggOp│   │
│  └─────────┘  └─────────┘  └─────────┘  └────┬────┘   │
│                                               │        │
│  Pipeline/Driver                             ▼        │
│  ┌─────────────────────────────────────────────────┐  │
│  │              Execution Context                   │  │
│  └─────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│  Data Layer                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │FlatVector<T>│  │  Chunk/Batch│  │ HashTable   │     │
│  │+ Bitmap     │  │  (vectors)  │  │ (agg/join)  │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
├─────────────────────────────────────────────────────────┤
│  IO & Storage                                           │
│  ┌─────────────┐  ┌─────────────┐                       │
│  │ CSV Reader  │  │Memory Source│                       │
│  └─────────────┘  └─────────────┘                       │
└─────────────────────────────────────────────────────────┘
```

## Performance Phases

### Phase 1: Correctness ✅
- [x] Scalar hash aggregation
- [x] Basic open addressing hash table
- [x] Unit tests + basic benchmark

### Phase 2: Reduce Overhead 🔄
- [ ] Batch hash computation
- [ ] Prefetch in probe loop
- [ ] Benchmark improvements

### Phase 3: SIMD + Locality 🔴
- [ ] Control bytes + SIMD compare (NEON/AVX2)
- [ ] Cache-friendly SoA layout
- [ ] Local pre-aggregation
- [ ] High/low cardinality benchmarks

## Learnings

### What Worked
- First principles thinking guides design
- Benchmarks validate hypotheses (not guessing)
- Columnar layout enables vectorization
- Hash table is core - worth deep optimization

### What Didn't
- Premature optimization without measurement
- Complex abstractions before simple works
- Ignoring memory layout early

### Key Insights
1. **Cache is king** - Data layout matters more than algorithm
2. **Branch prediction** - Reduce branches in hot loops
3. **Prefetch** - Hide latency with explicit prefetch
4. **Batch processing** - Amortize overhead across rows

## Code

- **Location:** [../../cc/projects/query-engine/](../../cc/projects/query-engine/)
- **Build:** `cmake -B build && cmake --build build`
- **Tests:** `ctest --test-dir build`
- **Benchmarks:** `build/bench/benchmarks`

## Benchmarking

### Data Generators
- Uniform keys (high cardinality)
- Zipf keys (hot spots)
- Low cardinality (high repetition)
- Sorted keys (locality effects)

### Metrics
- Throughput (rows/s)
- CPU utilization
- Cache miss rate
- Branch miss rate
- Hash table probe length

### Profiling (macOS Instruments)
1. CPU Counters - cache misses, branch misses
2. Time Profiler - hot functions
3. Memory - allocation patterns

## Related Projects

- [py-toydb](./py-toydb.md) - Python版本对比学习
- [mini-seastar](../../cc/projects/mini-seastar/) - 异步框架

## Resources

### Papers
- [MonetDB/X100: Hyper-Pipelining Query Execution](../read/papers/monetdb-x100.md)
- [Everything You Always Wanted to Know About Compiled and Vectorized Queries](../read/papers/compiled-vectorized.md)

### Code References
- [ClickHouse Aggregator](https://github.com/ClickHouse/ClickHouse/tree/master/src/Interpreters/Aggregator.cpp)
- [DuckDB Hash Aggregation](https://github.com/duckdb/duckdb/tree/master/src/execution/operator/aggregate)
- [Velox Vectorized Execution](https://github.com/facebookincubator/velox/tree/main/velox/exec)

## Comparison with py-toydb

| Aspect | query-engine (C++) | py-toydb |
|--------|-------------------|----------|
| Focus | Performance | Simplicity |
| Execution | Vectorized (batch) | Iterator (row) |
| Storage | Columnar | Row-oriented |
| Hash Table | Optimized (SIMD) | Simple dict |
| Profiling | Instruments, benchmarks | Basic timing |
| Use Case | Performance experiments | Concept learning |
