# vagg Task Board

This file is the active task board for `cc/projects/query-engine`. The earlier
repository-refactoring checklist has been completed: AGENTS/RULES/README/
CHANGELOG/docs/TODOS/gitignore all exist. Future work should now follow the
engine design rather than the old scaffolding checklist.

## References

- [Design](./DESIGN.md)
- [TODOs](./TODOS.md)
- [Architecture Docs](./docs/architecture/)
- [API Docs](./docs/api/)
- [Build Project Note](../../../docs/build/query-engine.md)

## Sprint 0: Documentation Alignment

- [x] Add project-level `DESIGN.md`
- [x] Rewrite `TODOS.md` as a staged execution roadmap
- [x] Update README to use current APIs
- [x] Update architecture/API docs to reflect prototype join/sort status
- [x] Update `docs/build/query-engine.md` with current phases
- [ ] Re-run build/tests after CMake is available locally

## Sprint 1: Honest MVP Fixes

- [ ] Add deterministic seed support to `GeneratedDataSource`
- [ ] Validate `MemoryDataSource` key/value length equality
- [ ] Preserve validity bits when `FlatVector::Resize` grows the vector
- [ ] Add vector resize/null regression tests
- [ ] Add empty-input aggregation tests
- [ ] Update hash table comments to say linear probing where appropriate

## Sprint 2: Minimal Pipeline Operators

- [ ] Implement `FilterOp`
- [ ] Add `FilterOp` tests
- [ ] Implement `ProjectOp`
- [ ] Add `ProjectOp` tests
- [ ] Implement `LimitOp`
- [ ] Add chunk-boundary limit tests
- [ ] Add a README pipeline example after operators are implemented

## Sprint 3: Join Semantics

- [ ] Add failing tests for duplicate build/probe join keys
- [ ] Replace aggregated build hash table with build-row storage
- [ ] Implement correct N:M inner join output
- [ ] Track matched build rows
- [ ] Implement LEFT join
- [ ] Add chunk-boundary tests for large join output

## Sprint 4: Sort and Top-N Semantics

- [ ] Make `SortOp` honor `SortKey::column_index`
- [ ] Add multi-key sort for `(key, value)`
- [ ] Fix/verify `TopNOp` with duplicate keys
- [ ] Add tests for `n == 0` and `n > row_count`
- [ ] Defer external sort until in-memory semantics are complete

## Sprint 5: Benchmark Track

- [ ] Make benchmark inputs reproducible
- [ ] Add low-cardinality, high-cardinality, Zipf, and sequential distributions
- [ ] Report unique keys, load factor, average probes, and resize count
- [ ] Add `std::unordered_map` comparison benchmark
- [ ] Add prefetch experiment behind a small, measurable change
