# cc/cclab Project Tasks

## Project Overview

**cc/cclab** is the core C++ laboratory with CMake build system, Google Test framework, and various data structures and utilities.

### Current State
- **Source Files**: 36 headers/implementations in `src/`
- **Test Files**: Multiple `.cc` files in `test/common/` and `test/utils/`
- **Build System**: CMake with `build.sh` script
- **Code Style**: `.clang-format`, `.clang-tidy` configured
- **Key Components**:
  - Data structures: SkipList, B+Tree, Robin Hood Hash Map, MPMC Queue
  - Utilities: Thread pools, Coroutines, Consistent hash, LRU cache

---

## Task 1: Create AGENTS.md

**Description**: Create AI coding agent guide for cc/cclab

**Files to Create**:
- `cc/cclab/AGENTS.md`

**Content Requirements**:
- Project overview
- Technology stack (C++20/23, CMake, Google Test)
- Build commands (`./build.sh [DEBUG|RELEASE|ASAN|LSAN]`)
- Test commands (`cd build_ASAN && ctest`)
- Code style (clang-format, clang-tidy rules)
- Directory structure

---

## Task 2: Create RULES.md

**Description**: Create project rules and conventions

**Files to Create**:
- `cc/cclab/RULES.md`

**Content Requirements**:
- C++20/23 standard requirements
- Naming conventions
- Google Test framework usage
- Sanitizer usage (ASAN, LSAN, UBSAN)
- Documentation requirements

---

## Task 3: Update README.md

**Description**: Enhance existing README with modern structure

**Files to Modify**:
- `cc/cclab/README.md`

**Content Requirements**:
- Project introduction
- Quick start guide
- Build instructions
- Test instructions
- Directory structure
- Dependencies

---

## Task 4: Create CHANGELOG.md

**Description**: Create changelog file

**Files to Create**:
- `cc/cclab/CHANGELOG.md`

**Content Requirements**:
- Version history (start with 0.1.0)
- Feature changes
- Bug fixes
- Format following Keep a Changelog

---

## Task 5: Create docs/ Directory Structure

**Description**: Create documentation directory structure

**Files/Directories to Create**:
- `cc/cclab/docs/`
- `cc/cclab/docs/architecture/`
- `cc/cclab/docs/api/`

---

## Task 6: Analyze Current Test Coverage

**Description**: Analyze existing tests and identify gaps

**Actions**:
- [ ] List all source files in `src/`
- [ ] List all test files in `test/`
- [ ] Map tests to source files
- [ ] Identify untested components:
  - SkipList variants
  - B+Tree
  - Robin Hood Hash Map
  - MPMC Queue
  - Thread pools
  - Coroutines
  - Consistent hash
  - LRU cache

**Files to Review**:
- All files in `src/common/`
- All files in `src/utils/`

---

## Task 7: Add Tests for SkipList

**Description**: Ensure comprehensive SkipList test coverage

**Files to Review/Create**:
- `test/common/skiplist_test.cc`
- `test/common/skiplist_v2_test.cc`

**Test Cases Needed**:
- [ ] Basic insertion
- [ ] Search operations
- [ ] Deletion
- [ ] Edge cases (empty list, single element)
- [ ] Concurrent access (if applicable)

---

## Task 8: Add Tests for B+Tree

**Description**: Add comprehensive B+Tree tests

**Files to Review**:
- `test/common/bplusplustree_test.cc`
- `src/common/btree/bplustree.h`

**Test Cases Needed**:
- [ ] Insertion
- [ ] Search
- [ ] Range queries
- [ ] Deletion
- [ ] Tree balancing
- [ ] Edge cases

---

## Task 9: Add Tests for Robin Hood Hash Map

**Description**: Add comprehensive Robin Hood Hash Map tests

**Files to Review**:
- `test/common/robin_hood_map_test.cc`
- `src/common/map/robin_hood_map.h`

**Test Cases Needed**:
- [ ] Insertion
- [ ] Lookup
- [ ] Deletion
- [ ] Collision handling
- [ ] Rehashing
- [ ] Edge cases

---

## Task 10: Add Tests for MPMC Queue

**Description**: Add comprehensive MPMC Queue tests

**Files to Review**:
- `test/common/mpmc_queue_test.cc`
- `src/common/queue/mpmc_queue.h`

**Test Cases Needed**:
- [ ] Single producer single consumer
- [ ] Multiple producers multiple consumers
- [ ] Queue full/empty conditions
- [ ] Concurrent operations
- [ ] Performance benchmarks

---

## Task 11: Add Tests for Thread Pool

**Description**: Add comprehensive Thread Pool tests

**Files to Review**:
- `src/utils/thread_pool.h`

**Test Cases to Create**:
- [ ] Basic task execution
- [ ] Multiple tasks
- [ ] Task with return values
- [ ] Concurrent task submission
- [ ] Thread pool destruction

---

## Task 12: Add Tests for Coroutines

**Description**: Add comprehensive Coroutine tests

**Files to Review**:
- `test/common/coroutine_test1.cc`
- `test/common/coroutine_test2.cc`
- `src/common/coroutine.h`

**Test Cases Needed**:
- [ ] Basic coroutine functionality
- [ ] Coroutine suspension/resumption
- [ ] Error handling in coroutines

---

## Task 13: Add Tests for Consistent Hash

**Description**: Add comprehensive Consistent Hash tests

**Files to Review**:
- `test/common/consistent_hash_test.cc`
- `src/common/consistent_hash/consistent_hash.h`

**Test Cases Needed**:
- [ ] Node addition
- [ ] Node removal
- [ ] Key distribution
- [ ] Virtual nodes
- [ ] Edge cases

---

## Task 14: Add Tests for LRU Cache

**Description**: Add comprehensive LRU Cache tests

**Files to Review**:
- `src/utils/lru.hpp`

**Test Cases to Create**:
- [ ] Basic put/get
- [ ] Eviction policy
- [ ] Size limits
- [ ] Update existing keys
- [ ] Concurrent access (if thread-safe)

---

## Task 15: Run Code Formatting

**Description**: Format all code with clang-format

**Commands**:
```bash
cd /home/lism/work/xlab/cc/cclab
find src test -name "*.h" -o -name "*.hpp" -o -name "*.cpp" -o -name "*.cc" | xargs clang-format -i
```

---

## Task 16: Run Clang-Tidy

**Description**: Fix all clang-tidy warnings

**Commands**:
```bash
cd /home/lism/work/xlab/cc/cclab
# Run clang-tidy on all source files
find src -name "*.cpp" -o -name "*.cc" | xargs clang-tidy --fix
```

---

## Task 17: Ensure Header Guards

**Description**: Ensure all headers have proper include guards or #pragma once

**Files to Check**:
- All `.h` and `.hpp` files in `src/`

**Requirements**:
- [ ] All headers use `#pragma once` OR proper include guards

---

## Task 18: Document Public APIs

**Description**: Ensure all public functions have documentation comments

**Files to Check**:
- All headers in `src/common/`
- All headers in `src/utils/`

**Requirements**:
- [ ] Public classes have class-level comments
- [ ] Public methods have doc comments
- [ ] Parameters and return values documented

---

## Task 19: Scan for Unused Files

**Description**: Identify unused or experimental code files

**Actions**:
- [ ] Review all files in `src/experiment/`
- [ ] Check for duplicate implementations
- [ ] Identify dead code

**Output**:
- Create `cc/cclab/TODOS.md` with list of files to review/remove

---

## Task 20: Create CI/CD Configuration

**Description**: Create GitHub Actions workflow

**Files to Create**:
- `.github/workflows/cc-cclab-ci.yml`

**Workflow Requirements**:
- [ ] Build matrix: DEBUG, RELEASE, ASAN
- [ ] Run all tests
- [ ] Run clang-tidy check
- [ ] Run clang-format check

---

## Task 21: Verify Build

**Description**: Verify project builds successfully

**Commands**:
```bash
cd /home/lism/work/xlab/cc/cclab
./build.sh ASAN
cd build_ASAN && ctest
```

---

## Task 22: Final Review

**Description**: Final review of all changes

**Checklist**:
- [ ] AGENTS.md created and complete
- [ ] RULES.md created and complete
- [ ] README.md updated
- [ ] CHANGELOG.md created
- [ ] docs/ directory created
- [ ] Test coverage improved
- [ ] Code formatted with clang-format
- [ ] clang-tidy warnings fixed
- [ ] All headers have proper guards
- [ ] Public APIs documented
- [ ] TODOS.md created with unused files
- [ ] CI/CD workflow created
- [ ] Build passes
- [ ] All tests pass

---

## Execution Order

1. Tasks 1-5: Create documentation files (can be done in parallel)
2. Task 6: Analyze test coverage
3. Tasks 7-14: Add missing tests
4. Tasks 15-18: Code quality improvements
5. Task 19: Mark unused files
6. Task 20: Create CI/CD
7. Tasks 21-22: Verify and review
