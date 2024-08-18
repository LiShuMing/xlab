# TinyKV Project Refactoring Tasks

**Goal:** Transform TinyKV into a modern LLM-friendly project with standardized documentation, improved structure, and 80%+ test coverage.

**Priority:** P0

---

## Task 1: Create AGENTS.md (AI Agent Guide)

**Files:**
- Create: `cc/projects/kv-store/AGENTS.md`

**Description:**
Create AGENTS.md with build commands, test commands, directory structure, dependencies, and common tasks.

**Checklist:**
- [ ] Document build commands (cmake, make)
- [ ] Document test commands (ctest, individual tests)
- [ ] Document directory structure
- [ ] Document dependencies (googletest, benchmark)
- [ ] Document benchmark commands
- [ ] Document code style (format target)

---

## Task 2: Create RULES.md (Coding Standards)

**Files:**
- Create: `cc/projects/kv-store/RULES.md`

**Description:**
Create RULES.md with C++ coding standards following Harness Engineering standards.

**Checklist:**
- [ ] Naming conventions (PascalCase classes, camelCase functions, snake_case variables)
- [ ] Include order rules
- [ ] 100 column limit
- [ ] Modern C++ guidelines (C++20 features)
- [ ] Error handling patterns
- [ ] Testing requirements

---

## Task 3: Create CHANGELOG.md

**Files:**
- Create: `cc/projects/kv-store/CHANGELOG.md`

**Description:**
Create CHANGELOG.md following Keep a Changelog format.

**Checklist:**
- [ ] Document v0.1.0 initial release
- [ ] List all existing components (MemTable, SkipList, Arena, etc.)
- [ ] Document build system
- [ ] Document test framework

---

## Task 4: Update README.md (English Version)

**Files:**
- Modify: `cc/projects/kv-store/README.md`

**Description:**
The current README is in Chinese. Create an English version with modern LLM-friendly structure.

**Checklist:**
- [ ] Project badges (build status, C++20, license)
- [ ] Quick description and features
- [ ] Quick start with code examples
- [ ] Build instructions
- [ ] Testing instructions
- [ ] Architecture overview (MemTable, WAL, SSTable phases)
- [ ] Roadmap
- [ ] Keep reference to old Chinese content if needed

---

## Task 5: Create docs/ Directory Structure

**Files:**
- Create: `cc/projects/kv-store/docs/api/README.md`
- Create: `cc/projects/kv-store/docs/architecture/README.md`

**Description:**
Create documentation structure for API and architecture docs.

**Checklist:**
- [ ] Create docs/api/ directory with component placeholders
- [ ] Create docs/architecture/ directory with design docs placeholders
- [ ] Document MemTable design
- [ ] Document SkipList design
- [ ] Document Arena allocator design

---

## Task 6: Create TODOS.md

**Files:**
- Create: `cc/projects/kv-store/TODOS.md`

**Description:**
Create TODOS.md tracking missing tests and future improvements.

**Checklist:**
- [ ] List missing tests (WAL, SSTable, compaction, etc.)
- [ ] List incomplete features
- [ ] List code quality improvements needed
- [ ] List documentation gaps

---

## Task 7: Clean Up Root Directory

**Files:**
- Delete: `cc/projects/kv-store/test_arena` (binary)
- Delete: `cc/projects/kv-store/test_node` (binary)
- Delete: `cc/projects/kv-store/test_skiplist` (binary)
- Delete: `cc/projects/kv-store/test_arena.cpp` (old test file)
- Delete: `cc/projects/kv-store/test_node.cpp` (old test file)
- Delete: `cc/projects/kv-store/test_skiplist.cpp` (old test file)
- Delete: `cc/projects/kv-store/test_skiplist.dSYM/` (debug symbols)
- Delete: `cc/projects/kv-store/claude.md` (replaced by AGENTS.md)
- Delete: `cc/projects/kv-store/SUMMARY.md` (consider if still needed)

**Description:**
Remove binaries and old test files that should be in tests/ directory.

**Checklist:**
- [ ] Remove all compiled binaries from git
- [ ] Remove old standalone test files
- [ ] Remove debug symbol directories
- [ ] Remove redundant documentation files

---

## Task 8: Create .gitignore

**Files:**
- Create: `cc/projects/kv-store/.gitignore`

**Description:**
Create .gitignore to prevent committing build artifacts.

**Checklist:**
- [ ] Ignore build/ directories
- [ ] Ignore compiled binaries
- [ ] Ignore IDE files (.vscode, .idea)
- [ ] Ignore OS files (.DS_Store)
- [ ] Ignore debug symbols

---

## Task 9: Verify CMakeLists.txt Paths

**Files:**
- Modify: `cc/projects/kv-store/CMakeLists.txt`

**Description:**
Check and fix the thirdparty directory path which is currently hardcoded to a macOS path.

**Checklist:**
- [ ] Check THIRDPARTY_DIR path is correct for xlab structure
- [ ] Consider making path relative or configurable
- [ ] Ensure all tests are properly registered

---

## Task 10: Review and Update Existing Tests

**Files:**
- Review: `cc/projects/kv-store/tests/memtable/skiplist_test.cpp`
- Review: `cc/projects/kv-store/tests/memtable/memtable_test.cpp`

**Description:**
Review existing tests for coverage and quality.

**Checklist:**
- [ ] Check test coverage
- [ ] Verify tests compile and pass
- [ ] Add missing edge case tests
- [ ] Ensure tests follow naming conventions

---

## Summary

After completing all tasks:
1. Project will have modern LLM-friendly documentation
2. Clean directory structure without binaries
3. Proper .gitignore in place
4. English documentation ready for international contributors
5. Clear roadmap for future development (WAL, SSTable, Compaction phases)

**Estimated Completion:** 10 tasks
