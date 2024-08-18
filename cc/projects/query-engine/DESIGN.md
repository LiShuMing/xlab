# Vectorized Query Engine Design

`vagg` is a focused C++20 lab for understanding OLAP execution internals by
building the hot path directly: columnar batches, pull-based operators, hash
aggregation, joins, sorting, and benchmarks.

The project is intentionally not a full SQL database yet. The current design
keeps SQL parsing, catalog management, and cost-based optimization out of scope
until the operator and vector contracts are solid.

## Design Goals

1. **Learn by measuring**: every performance-oriented change should have a
   benchmark before and after.
2. **Keep the first execution model small**: use a typed key-value workload
   before generalizing to arbitrary schemas.
3. **Prefer correctness before cleverness**: SIMD, control bytes, and external
   sort come after semantic tests for joins, sorting, nulls, and chunking.
4. **Mirror real OLAP engines at reduced scale**: the concepts should map to
   DuckDB, Velox, ClickHouse, and DataFusion, but the implementation remains
   readable.

## Current Architecture

```text
DataSource
    |
    v
ScanOp
    |
    v
TransformOperator(s)
    |
    v
SinkOp / ResultCollectorOp
```

The execution model is pull-based. Each operator exposes:

```cpp
Status Prepare(ExecContext* ctx);
Status Next(Chunk* out);
```

`Prepare()` initializes state and may consume children for blocking operators
such as hash aggregation, hash join build, and in-memory sort. `Next()` returns
one output chunk at a time and uses `Status::EndOfFile()` to signal completion.

## Data Model

The current implementation uses typed chunks:

- `KeyValueChunk`: `(int32_t key, int64_t value)`
- `JoinOutputChunk`: `(int32_t key, int64_t left_value, int64_t right_value)`

This is a deliberate MVP trade-off. It keeps the aggregation/join/sort path
simple enough to benchmark and reason about. General `Schema` and dynamic
column access already have small foundations, but most operators still assume
`KeyValueChunk`.

### Vector Layout

`FlatVector<T>` stores values contiguously in `std::vector<T>` and carries a
`ValidityBitmap` for null tracking. This gives a columnar layout suitable for
batch processing and later SIMD experiments.

Known gap: growing a vector currently recreates the validity bitmap instead of
preserving existing null bits. Fix this before null-aware operators are added.

## Operators

### Scan

`ScanOp` reads a `DataSource` into `KeyValueChunk` batches.

Implemented data sources:

- `MemoryDataSource`: deterministic vectors supplied by tests.
- `GeneratedDataSource`: uniform, Zipf-like, or sequential benchmark data.

Immediate design cleanup:

- Validate equal key/value lengths.
- Allow deterministic seeding for benchmark reproducibility.

### Hash Aggregation

`HashAggregateOp` implements:

```sql
SELECT key, SUM(value) FROM input GROUP BY key
```

It consumes all input during `Prepare()`, updates `HashTable<int32_t, int64_t>`,
then materializes output chunks.

Current hash table behavior is linear probing with resize and statistics. Some
comments refer to Robin Hood/control-byte probing as a target design; those
should not be treated as implemented behavior.

### Hash Join

`HashJoinOp` is currently a prototype for single-key inner join. It builds a
hash table from the build side and probes with the probe side.

Important semantic limitation: duplicate build keys are aggregated into one
`int64_t` value. That is useful as a toy example but not correct relational
join behavior. Before adding outer joins, replace the build table with a
structure that stores all build rows per key.

Target build-side structure:

```cpp
struct BuildRow {
  int32_t key;
  int64_t value;
  bool matched = false;
};

std::unordered_map<int32_t, std::vector<BuildRow>> build_rows;
```

The project can later replace this with a custom vectorized join hash table.
The first priority is correct N:M semantics and chunked output.

### Sort and Top-N

`SortOp` is an in-memory blocking sort for `KeyValueChunk`. It flattens all
input, sorts row indices, and emits sorted chunks.

`TopNOp` uses `std::partial_sort` for the top N rows.

Current semantic limits:

- Only column 0 is effectively sorted.
- Multi-key sort specifications are not honored.
- Null ordering is represented in the API but not implemented.
- External sorting is not implemented and should wait.

## Hash Table Design Track

The hash table is the central performance playground.

### Baseline

- Open addressing
- Power-of-two capacity
- Linear probing
- Stored full hash
- Resize at configurable load factor
- Basic probe/collision/resize stats

### Next Experiments

1. Deterministic benchmark distributions.
2. Probe length histograms.
3. Explicit prefetch in find/insert loops.
4. Robin Hood displacement.
5. Control bytes and SIMD group probing.
6. Partitioned/local aggregation.

Each step should land with tests and benchmarks. Avoid mixing multiple
optimizations in one change; this project is more valuable as a lab notebook
when each performance hypothesis is isolated.

## Near-Term Milestones

### Milestone 1: Honest MVP

- Fix docs to match current APIs.
- Make generated data deterministic.
- Add source validation and vector resize/null tests.
- Clarify linear probing versus future Robin Hood design.

### Milestone 2: Minimal Pipeline

Add enough streaming operators to form:

```text
MemoryDataSource -> ScanOp -> FilterOp -> ProjectOp -> HashAggregateOp -> SinkOp
```

This milestone is about execution ergonomics, not performance.

### Milestone 3: Correct Join

- Preserve duplicate build keys.
- Emit all N:M inner join rows.
- Add LEFT join after matched-row tracking exists.
- Add chunk-boundary tests for large join output.

### Milestone 4: Meaningful Benchmarks

- Add low/high/Zipf/sequential data distributions.
- Record unique key count and hash table stats in benchmarks.
- Compare custom hash table against `std::unordered_map`.
- Keep benchmark output stable enough for regression tracking.

### Milestone 5: Generalization

Only after the typed path is correct:

- Introduce runtime schema-aware chunks.
- Add general vector access APIs.
- Add multi-column keys and additional aggregate functions.
- Consider a tiny logical-plan layer.

## Non-Goals for Now

- Full SQL parser.
- Cost-based optimizer.
- Parquet/ORC reader.
- Distributed execution.
- External sort.
- LLVM/codegen.

These are good future projects, but they would obscure the current goal:
understanding vectorized execution and hash-heavy OLAP operators from first
principles.
