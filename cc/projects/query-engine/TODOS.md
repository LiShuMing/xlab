# vagg TODOs

This file tracks the executable roadmap for `cc/projects/query-engine`.
The project is currently a small C++20 vectorized execution lab with typed
`KeyValueChunk` batches, an open-addressing hash table, hash aggregation,
in-memory scan sources, a prototype hash join, in-memory sort, and Top-N.

## Current State

### Done

- [x] `FlatVector<T>`, `ValidityBitmap`, `SelectionVector`
- [x] `KeyValueChunk` and `JoinOutputChunk`
- [x] `DataSource`, `MemoryDataSource`, `GeneratedDataSource`
- [x] `ScanOp`, `HashAggregateOp`, `SimpleHashAggregateOp`, `SinkOp`
- [x] `HashTable<int32_t, int64_t>` with resize and basic stats
- [x] Prototype `HashJoinOp` for one-key inner join
- [x] Prototype `SortOp` and `TopNOp` for key-value chunks
- [x] GoogleTest suites for vector, hash table, aggregation, hash join, sort
- [x] Google Benchmark aggregation/hash-table benchmark

### Known Design Limits

- [ ] The operator API is fixed to `KeyValueChunk` in most implementations.
- [ ] `HashJoinOp` aggregates duplicate build keys instead of preserving row multiplicity.
- [ ] `HashJoinOp` advertises LEFT/RIGHT/FULL joins, but only INNER join is usable.
- [ ] `SortOp` and `TopNOp` sort only column 0 and ignore multi-key/null specifications.
- [ ] `GeneratedDataSource` uses nondeterministic seeding for uniform data.
- [ ] `HashTable` is linear probing; comments mention Robin Hood/control bytes before they exist.
- [ ] `ValidityBitmap` resize currently resets existing validity state when growing.
- [ ] Some README/agent snippets may still describe future APIs; prefer code over docs when in doubt.

## P0: Make the Existing Engine Honest and Stable

- [ ] Rename or document `HashTable` as linear probing until Robin Hood/control bytes are implemented.
- [ ] Add deterministic seed support to `GeneratedDataSource`.
- [ ] Add explicit key/value size validation in `MemoryDataSource`.
- [ ] Add bounds assertions or status checks for typed chunk casts in operators.
- [ ] Fix `ValidityBitmap` growth so existing null bits survive `FlatVector::Resize`.
- [ ] Add regression tests for null preservation after vector resize.
- [ ] Add tests for empty input in `HashAggregateOp`.
- [ ] Add tests for mismatched `MemoryDataSource` key/value lengths.

## P1: Complete the Minimal Relational Pipeline

- [ ] Add `FilterOp` over `KeyValueChunk`
  - [ ] Predicate interface: `bool(int32_t key, int64_t value)`
  - [ ] Selection-vector based implementation first
  - [ ] Tests for all-pass, all-drop, mixed, empty input, multiple chunks
- [ ] Add `ProjectOp` over `KeyValueChunk`
  - [ ] Column reorder/subset for key-value chunks
  - [ ] Simple computed expression support, e.g. `value * constant`
  - [ ] Tests for projection order and row preservation
- [ ] Add `LimitOp`
  - [ ] Stop pulling after N rows
  - [ ] Tests across chunk boundaries
- [ ] Update README examples to show `Scan -> Filter -> Project -> Aggregate -> Sink` once these exist.

## P2: Fix Join Semantics

- [ ] Replace `HashTable<int32_t, int64_t>` in `HashJoinOp` with a build-side row table.
- [ ] Preserve duplicate build keys and produce N:M join output.
- [ ] Track matched build row ids for outer joins.
- [ ] Implement LEFT OUTER join.
- [ ] Decide whether RIGHT/FULL joins belong in this project or should remain explicit TODOs.
- [ ] Add tests for duplicate keys on both sides.
- [ ] Add tests for chunked probe output where matches exceed one output chunk.
- [ ] Add stats that distinguish build rows, build keys, probe rows, matches, and output rows.

## P3: Make Sorting Semantics Real

- [ ] Make `SortOp` honor `SortKey::column_index`.
- [ ] Add multi-key ordering for `(key, value)`.
- [ ] Preserve key/value pairing through sorting and Top-N.
- [ ] Add explicit NULL handling once nullable execution is supported by operators.
- [ ] Add tests for duplicate keys with value tie-breakers.
- [ ] Add tests for `TopNOp` with duplicate keys and `n > row_count`.
- [ ] Consider external sort only after in-memory sort semantics are correct.

## P4: Hash Table Performance Track

- [ ] Add benchmark data distributions: low-cardinality, high-cardinality, Zipf, sequential/sorted.
- [ ] Add benchmark counters for unique keys, load factor, average probes, resizes.
- [ ] Add high-load-factor stress tests.
- [ ] Add collision-heavy tests using supplied hashes.
- [ ] Add prefetching experiment in the probe loop.
- [ ] Implement real Robin Hood displacement or update the design to keep linear probing.
- [ ] Add SwissTable-style control bytes only after benchmark baselines are stable.
- [ ] Compare `HashTable` against `std::unordered_map` for aggregation workloads.

## P5: Generalize the Execution Model

- [ ] Introduce runtime `Schema` on chunks and operators.
- [ ] Replace `TypedChunk`-only APIs with a safe `VectorBase` column interface.
- [ ] Add `MemorySource` for arbitrary typed columns.
- [ ] Add string key support.
- [ ] Add multi-column key support.
- [ ] Add aggregate function descriptors for `SUM`, `COUNT`, `MIN`, `MAX`.
- [ ] Add a tiny logical plan layer only after operator semantics are stable.

## P6: Documentation and Tooling

- [x] Add project-level design document: `DESIGN.md`
- [ ] Add `docs/architecture/vectorized-execution.md`
- [ ] Add `docs/architecture/hash-table.md`
- [ ] Add `docs/architecture/operators.md`
- [ ] Add `docs/api/vector.md`
- [ ] Add `docs/api/hash-table.md`
- [ ] Add `docs/api/operators.md`
- [ ] Add clang-format check target.
- [ ] Add a local CI script that builds, tests, and runs the fast benchmarks.
- [ ] Add GitHub Actions only after local script is reliable.

## Suggested Next Sprint

1. Fix documentation drift and mark the real current state.
2. Add deterministic `GeneratedDataSource` and source validation.
3. Add `FilterOp` with selection-vector implementation.
4. Add `LimitOp` to make chunk-boundary behavior easy to test.
5. Add duplicate-key hash join tests before changing join internals.
