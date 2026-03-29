# TinyKV TODOs

This file tracks missing tests, incomplete features, and other technical debt for TinyKV.

## Missing Tests

The following components need comprehensive unit tests:

### High Priority

- [ ] `Slice` - String reference tests
  - Test construction from various sources
  - Test comparison operators
  - Test edge cases (empty, null)
  - Test ToString() method

- [ ] `Status` - Error handling tests
  - Test OK status
  - Test error codes and messages
  - Test ToString() formatting
  - Test move semantics

- [ ] `Arena` - Memory allocator tests
  - Test basic allocation
  - Test large allocations (> block size)
  - Test alignment
  - Test memory usage tracking
  - Test destruction behavior

### Medium Priority

- [ ] `SkipList` - Additional edge case tests
  - Test concurrent read scenarios
  - Test iterator invalidation
  - Test with custom comparator

- [ ] `MemTable` - Additional tests
  - Test overwrite behavior
  - Test iterator range
  - Test memory accounting

### Low Priority

- [ ] Benchmark improvements
  - Add comparison with std::map
  - Add memory usage benchmarks
  - Add scalability benchmarks

## Incomplete Features

### Phase 2: WAL (Write-Ahead Log)

- [ ] `WALWriter` - Log writer implementation
  - Record formatting (length + type + crc)
  - Fsync handling
  - File rotation

- [ ] `WALReader` - Log reader implementation
  - Record parsing
  - CRC verification
  - Corruption handling

- [ ] Recovery logic
  - Replay WAL on startup
  - Skip corrupted records
  - Build MemTable from WAL

### Phase 3: SSTable

- [ ] `BlockBuilder` - Data block construction
  - Key-value pair encoding
  - Prefix compression (optional)
  - Restart points

- [ ] `TableBuilder` - SSTable writer
  - Data blocks
  - Index blocks
  - Footer with metadata

- [ ] `TableReader` - SSTable reader
  - Block loading
  - Index lookup
  - Iterator interface

### Phase 4: Version Management

- [ ] `VersionSet` - Multi-version tracking
  - Level tracking
  - File metadata

- [ ] `Manifest` - Persistent metadata
  - Atomic updates
  - CURRENT file switching

### Phase 5: Compaction

- [ ] `CompactionPicker` - Compaction scheduling
  - Level triggering
  - Size ratio checks

- [ ] `MergingIterator` - Multi-source iteration
  - Heap-based merge
  - Duplicate handling

## Code Quality Improvements

- [ ] Apply clang-format to all source files
- [ ] Run clang-tidy and fix warnings
- [ ] Add [[nodiscard]] to appropriate functions
- [ ] Add more constexpr where applicable
- [ ] Review exception safety of all components
- [ ] Add noexcept to move operations

## Documentation Improvements

- [ ] Add detailed API docs for each component in `docs/api/`
  - [ ] arena.md
  - [ ] skiplist.md
  - [ ] memtable.md
  - [ ] slice.md
  - [ ] status.md

- [ ] Add architecture docs in `docs/architecture/`
  - [ ] overview.md
  - [ ] memtable.md
  - [ ] lsm-tree.md
  - [ ] phases.md

## CI/CD Setup

- [ ] Create `.github/workflows/kv-store-ci.yml`
  - Build matrix: DEBUG, RELEASE
  - Run all tests
  - Run clang-tidy check
  - Run clang-format check
  - Build and run benchmarks

## Build System Improvements

- [ ] Fix hardcoded thirdparty path in CMakeLists.txt
- [ ] Add option to use system googletest/benchmark
- [ ] Add install target verification
- [ ] Add pkg-config file generation

## Notes

- Project has good foundation with Phase 1 complete
- Main gaps are in Phases 2-5 (WAL, SSTable, Version, Compaction)
- Code quality is generally high
- Documentation needs improvement for API details
