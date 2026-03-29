# vagg TODOs

This file tracks missing tests, incomplete features, and technical debt for vagg.

## Missing Tests

The following tests need enhancement:

### High Priority

- [ ] `Vector<T>` edge cases
  - Test with different types (int32, int64, double)
  - Test null handling
  - Test resize operations
  - Test memory alignment

- [ ] `HashTable` stress tests
  - High load factor scenarios
  - Collision handling
  - Rehash verification
  - Iterator stability

### Medium Priority

- [ ] `ScanOp` tests
  - Different data sources
  - Error handling
  - Chunk boundaries

- [ ] `AggregateOp` tests
  - Multiple aggregate functions
  - Group by with nulls
  - Empty input handling

- [ ] Benchmark improvements
  - More data distributions (uniform, zipf, sorted)
  - Memory usage tracking
  - Cache miss profiling

## Incomplete Features

### Operators

- [ ] `FilterOp` - Predicate pushdown
- [ ] `ProjectOp` - Column selection/expression
- [ ] `HashJoinOp` - Hash join implementation
- [ ] `SortOp` - External sorting

### Hash Table Enhancements

- [ ] SIMD probing with AVX2/NEON
- [ ] Parallel hash table (for partitioned aggregation)
- [ ] String key support
- [ ] Multi-column keys

### Vector Types

- [ ] `DictionaryVector` - Dictionary encoding
- [ ] `ConstantVector` - Constant values
- [ ] `LazyVector` - On-demand decoding

### I/O

- [ ] `ParquetSource` - Parquet file reader
- [ ] `OrcSource` - ORC file reader
- [ ] `MemorySource` - In-memory data

## Code Quality Improvements

- [ ] Apply clang-format to all files
- [ ] Run clang-tidy and fix warnings
- [ ] Add [[nodiscard]] to status returns
- [ ] Add noexcept to move operations
- [ ] Review exception safety
- [ ] Add Doxygen comments

## Documentation Improvements

- [ ] Add detailed API docs for each component
  - [ ] vector.md
  - [ ] hashtable.md
  - [ ] operators.md
  - [ ] execution.md

- [ ] Add architecture docs
  - [ ] vectorized-execution.md
  - [ ] hashtable-design.md
  - [ ] operator-framework.md

## Performance Optimizations

- [ ] Implement prefetching in hash table
- [ ] Add local aggregation for high-cardinality
- [ ] Vectorized filter evaluation
- [ ] Columnar-to-row conversion optimization

## CI/CD Setup

- [ ] Create `.github/workflows/query-engine-ci.yml`
  - Build matrix
  - Run all tests
  - Run benchmarks
  - clang-tidy check

## Notes

- Core hash aggregation is functional
- Hash join tests exist but implementation may be incomplete
- Sort tests exist but may need work
- Strong foundation for OLAP query processing
