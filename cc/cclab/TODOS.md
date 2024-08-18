# cc/cclab TODOs

This file tracks unused files, missing tests, and other technical debt for cc/cclab.

## Missing Tests

The following components need comprehensive unit tests:

### High Priority
- [ ] `src/utils/lru.hpp` - LRU Cache needs comprehensive tests
  - Test basic put/get operations
  - Test eviction policy
  - Test size limits
  - Test update of existing keys
- [ ] `src/utils/thread_pool.h` - Thread Pool needs dedicated test file
  - Test basic task execution
  - Test multiple tasks
  - Test task return values
  - Test concurrent task submission
  - Test graceful shutdown

### Medium Priority
- [ ] `src/common/queue/BlockingQueue.h` - Blocking queue tests
- [ ] `src/common/queue/spsc.h` - Single-producer single-consumer queue tests
- [ ] `src/common/queue/spmc_q.h` - Single-producer multi-consumer queue tests
- [ ] `src/common/cow.h` - Copy-on-write wrapper tests

### Low Priority (Existing tests may need enhancement)
- [ ] `src/common/skiplist/` - Add concurrent access tests
- [ ] `src/common/btree/bplustree.h` - Add more edge case tests
- [ ] `src/common/map/robin_hood_map.h` - Add stress tests

## Code Quality Improvements

- [ ] Apply clang-format to all source files (requires clang-format installation)
- [ ] Run clang-tidy and fix warnings (requires clang-tidy installation)
- [ ] Add [[nodiscard]] to appropriate functions
- [ ] Add more constexpr where applicable
- [ ] Review exception safety of all components

## Documentation Improvements

- [ ] Add API documentation for each major component in `docs/api/`
  - [ ] skiplist.md
  - [ ] bplustree.md
  - [ ] robin_hood_map.md
  - [ ] mpmc_queue.md
  - [ ] thread_pool.md
  - [ ] lru_cache.md
  - [ ] defer.md
- [ ] Add architecture overview in `docs/architecture/`
  - [ ] overview.md
  - [ ] data-structures.md
  - [ ] concurrency.md

## Potential Refactoring

- [ ] Consider unifying namespace (currently mix of `cclab` and `xlab`)
- [ ] Review and potentially remove unused experimental code in `src/experiment/`
- [ ] Consider making all queue implementations consistent in interface

## CI/CD Setup

- [ ] Create `.github/workflows/cc-cclab-ci.yml`
  - Build matrix: DEBUG, RELEASE, ASAN
  - Run all tests
  - Run clang-tidy check
  - Run clang-format check

## Notes

- Project has good test coverage for core data structures
- Code quality is generally high
- Main gaps are in utility components (thread_pool, lru_cache)
