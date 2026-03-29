# Vectorized Query Engine (vagg) Refactoring Tasks

**Goal:** Transform vagg into a modern LLM-friendly project with standardized documentation, improved structure, and comprehensive test coverage.

**Priority:** P0

---

## Task 1: Create AGENTS.md (AI Agent Guide)

**Files:**
- Create: `cc/projects/query-engine/AGENTS.md`

**Description:**
Create AGENTS.md with build commands, test commands, directory structure, dependencies, and common tasks.

**Checklist:**
- [ ] Document build commands (cmake, make)
- [ ] Document test commands (ctest, individual tests)
- [ ] Document directory structure
- [ ] Document dependencies (googletest, benchmark)
- [ ] Document benchmark commands
- [ ] Document the vectorized query execution model

---

## Task 2: Create RULES.md (Coding Standards)

**Files:**
- Create: `cc/projects/query-engine/RULES.md`

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
- Create: `cc/projects/query-engine/CHANGELOG.md`

**Description:**
Create CHANGELOG.md following Keep a Changelog format.

**Checklist:**
- [ ] Document v0.1.0 initial release
- [ ] List all existing components (Vector, HashTable, Operators, etc.)
- [ ] Document build system
- [ ] Document test framework

---

## Task 4: Update README.md (English Version)

**Files:**
- Modify: `cc/projects/query-engine/README.md`

**Description:**
The current README is in Chinese. Create an English version with modern LLM-friendly structure.

**Checklist:**
- [ ] Project badges (build status, C++20, license)
- [ ] Quick description and features (vectorized execution, hash aggregation)
- [ ] Quick start with code examples
- [ ] Build instructions
- [ ] Testing instructions
- [ ] Architecture overview (Vector, HashTable, Operators)
- [ ] Performance considerations
- [ ] Keep reference to original Chinese documentation

---

## Task 5: Create docs/ Directory Structure

**Files:**
- Create: `cc/projects/query-engine/docs/api/README.md`
- Create: `cc/projects/query-engine/docs/architecture/README.md`

**Description:**
Create documentation structure for API and architecture docs.

**Checklist:**
- [ ] Create docs/api/ directory with component placeholders
- [ ] Create docs/architecture/ directory with design docs placeholders
- [ ] Document Vector design
- [ ] Document HashTable design
- [ ] Document Operator framework

---

## Task 6: Create TODOS.md

**Files:**
- Create: `cc/projects/query-engine/TODOS.md`

**Description:**
Create TODOS.md tracking missing tests and future improvements.

**Checklist:**
- [ ] List missing tests
- [ ] List incomplete features
- [ ] List code quality improvements needed
- [ ] List documentation gaps

---

## Task 7: Create .gitignore

**Files:**
- Create: `cc/projects/query-engine/.gitignore`

**Description:**
Create .gitignore to prevent committing build artifacts.

**Checklist:**
- [ ] Ignore build/ directories
- [ ] Ignore compiled binaries
- [ ] Ignore IDE files (.vscode, .idea)
- [ ] Ignore OS files (.DS_Store)
- [ ] Ignore debug symbols

---

## Task 8: Rename claude.md to archive

**Files:**
- Delete: `cc/projects/query-engine/claude.md`

**Description:**
The claude.md file is replaced by AGENTS.md. Remove it.

---

## Task 9: Verify Source Files Exist

**Files:**
- Check: `cc/projects/query-engine/src/common/status.cc`
- Check: `cc/projects/query-engine/src/vector/vector.cc`
- Check: `cc/projects/query-engine/src/ht/hash_table.cc`

**Description:**
Verify all source files referenced in CMakeLists.txt exist.

---

## Task 10: Review Test Files

**Files:**
- Review: `cc/projects/query-engine/tests/test_hash_table.cc`
- Review: `cc/projects/query-engine/tests/test_aggregation.cc`
- Review: `cc/projects/query-engine/tests/test_vector.cc`
- Review: `cc/projects/query-engine/tests/test_hash_join.cc`
- Review: `cc/projects/query-engine/tests/test_sort.cc`

**Description:**
Review existing tests for coverage and quality.

**Checklist:**
- [ ] Check test coverage
- [ ] Verify tests compile and pass
- [ ] Document any missing test scenarios

---

## Summary

After completing all tasks:
1. Project will have modern LLM-friendly documentation
2. Clean directory structure
3. Proper .gitignore in place
4. English documentation ready for international contributors
5. Clear understanding of current implementation state

**Estimated Completion:** 10 tasks
