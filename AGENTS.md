# AGENTS.md — AI Coding Agent Guide

This document provides essential information for AI coding agents working with the `xlab` repository.

## Project Overview

**xlab** is a multi-language laboratory codebase primarily written in Chinese context but with English code/documentation. It serves as a personal research and experimentation platform covering systems programming, data structures, algorithms, and database internals. The repository owner is a senior database kernel engineer with focus on OLAP systems, query optimizers, and distributed systems.

### Repository Information
- **Origin**: https://github.com/LiShuMing/xlab
- **Type**: Personal R&D laboratory / Code experiments collection
- **Language Distribution**: C++ (primary), Python, Rust, Go, Java, Haskell, Shell
- **Documentation**: Chinese (MkDocs Material), Code comments: Mixed

## Project Structure

```
xlab/
├── cc/                    # C++ laboratory (main focus)
│   ├── cclab/            # Core C++ lab with CMake build
│   ├── algo/             # Algorithm implementations (LeetCode, etc.)
│   ├── ccbench/          # Benchmarks
│   ├── srlab/            # Serialization experiments
│   ├── simd/             # SIMD optimizations
│   ├── golab/            # Go-C++ interop experiments
│   ├── projects/         # Personal C++ projects
│   └── thirdparty/       # 40+ Git submodules (major deps)
├── rust/                 # Rust laboratory
│   ├── rlab/             # Workspace-based Rust lab
│   ├── rdb/              # Database implementation experiments
│   └── thirdparty/       # Rust submodules (RisingWave, DataFusion, etc.)
├── python/               # Python laboratory
│   ├── pylab/            # Core Python lab with pytest
│   ├── projects/         # Personal Python projects
│   └── thirdparty/       # Python submodules
├── go/                   # Go laboratory
│   └── hello/            # Go module experiments
├── java/                 # Java laboratory
│   ├── xlab-iceberg/     # Apache Iceberg related
│   └── xlab-itest/       # Interview/test projects
├── haskell/              # Haskell functional programming lab
├── shell/                # Shell scripting utilities
│   ├── bin/              # Executable scripts
│   ├── docker/           # Docker scripts
│   └── mysql/            # MySQL utilities
└── docs/                 # MkDocs documentation (Chinese)
```

## Technology Stack by Module

### C++ (cc/)
- **Standard**: C++20/23 (configurable, default C++20)
- **Build System**: CMake 3.22+
- **Build Types**: DEBUG, RELEASE, ASAN, LSAN, UBSAN
- **Compilers**: GCC or Clang (prefers clang-19)
- **Testing**: Google Test
- **Key Libraries**:
  - Google: glog, googletest, benchmark, abseil-cpp
  - Facebook: folly, velox, rocksdb
  - Databases: DuckDB, Doris, ClickHouse, leveldb
  - Systems: seastar, brpc, muduo, Arrow
  - Other: fmt, concurrentqueue, boost

### Rust (rust/)
- **Edition**: 2021
- **Build System**: Cargo workspace
- **Key Projects**:
  - `rlab`: Core experiments (lockfree, thread-pool, bloom filter)
  - `rdb`: Database implementation with tokio
- **Key Dependencies**: tokio, parking_lot, serde, zstd, roaring
- **Third-party Submodules**: RisingWave, Materialize, DataFusion, Timely/Differential Dataflow

### Python (python/)
- **Version**: 3.13.5 (managed via pyenv)
- **Environment**: Virtual environments (.venv)
- **Testing**: pytest
- **Key Packages**: numpy, pandas, duckdb, matplotlib, faiss-cpu
- **Projects**: py-radar, py-invest, py-email, py-academic, py-toydb

### Go (go/)
- **Version**: 1.21.0
- **Module**: Go modules
- **Projects**: hello (basic experiments)

### Java (java/)
- **Build Tools**: Gradle (primary), Maven
- **Projects**: xlab-iceberg, xlab-itest (interview prep)

### Haskell (haskell/)
- **Build Tools**: cabal or stack
- **Project**: hslab (functional programming experiments)

### Shell (shell/)
- **Shell**: Bash/Zsh
- **Tools**: bin/ utilities, Docker scripts, MySQL utilities

## Build Commands

### C++ (cc/cclab)
```bash
cd cc/cclab
./build.sh                    # Default ASAN build
BUILD_TYPE=RELEASE ./build.sh # Release build
# Build outputs to build_ASAN/ or build_RELEASE/

# Run tests
cd build_ASAN && ctest
```

### C++ Algorithms (cc/algo)
```bash
cd cc/algo
make leetcode_<number>        # Build specific LeetCode solution
make run_leetcode_<number>    # Build and run
make test                     # Verify toolchain
```

### Rust
```bash
cd rust/rlab
cargo build
cargo test
cargo clippy                  # Linting
cargo fmt                     # Formatting
```

### Python
```bash
cd python/pylab
pip install -r requirements.txt
pytest -s test_file.py        # Individual test
cd test && make test          # All tests
```

### Go
```bash
cd go/hello
go build
go test
```

### Java
```bash
# Gradle projects
./gradlew build

# Maven projects
mvn build
```

### Documentation (MkDocs)
```bash
mkdocs serve                  # Local development server
mkdocs build                  # Build static site
```

## Code Style Guidelines

### C++
- **Formatter**: clang-format (Google style based)
- **Linter**: clang-tidy with custom checks
- **Key Settings**:
  - Column limit: 100
  - Indent: 4 spaces
  - Pointer alignment: Left
  - Allow short functions inline
- **Standards**: Use C++20 features, RAII, `[[nodiscard]]`, move semantics
- **Modern C++**: Prefer `std::make_unique`, `std::make_shared`, smart pointers

### Rust
- Run `cargo fmt` and `cargo clippy` before committing
- Use `snake_case` for functions/variables
- Use `PascalCase` for types/traits
- Error handling with `Result<T, E>` and `?` operator

### Python
- **Style**: PEP 8
- **Tools**: black, isort (recommended)
- Use type hints for function signatures
- Virtual environments for all projects

### Go
- **Formatter**: `gofmt` (standard)
- Use `golangci-lint` for comprehensive linting
- Error handling: explicit errors, no panic in production

### Java
- Standard Java naming conventions
- Use `var` for local variables (Java 10+)
- Prefer `Optional` over null

### Shell
- Shebang: `#!/usr/bin/env bash`
- Use `set -euo pipefail`
- Quote all variable expansions
- Use `[[ ]]` over `[ ]`

## Testing Strategy

### C++
- **Framework**: Google Test (googletest submodule)
- **Location**: `cc/cclab/test/`
- **Types**: Unit tests, benchmark tests
- **Sanitizers**: ASAN (Address), LSAN (Leak), UBSAN (Undefined Behavior)

### Rust
- `cargo test` for unit tests
- `cargo bench` for benchmarks

### Python
- **Framework**: pytest
- **Location**: `python/pylab/test/`
- Coverage with pytest-cov

### Java
- **Framework**: JUnit 5, TestNG

## Git Submodules

This repository uses extensive Git submodules for third-party code:

### Initialize Submodules
```bash
git submodule update --init --recursive
```

### Key Submodule Categories
- **C++ thirdparty**: 40+ submodules including DuckDB, RocksDB, Folly, Arrow
- **Rust thirdparty**: RisingWave, Materialize, DataFusion, Timely Dataflow
- **Python thirdparty**: TinyDB, PyDBSP

⚠️ **Important**: Submodules are NOT automatically initialized. Most require manual initialization when needed.

## Development Conventions

### Documentation Standards
The `docs/` directory follows a specific technical writing style defined in `docs/SKILL.md`:

- **Persona**: Senior database kernel engineer
- **Report Types**:
  1. Technical Deep-Dive (Architecture analysis)
  2. RCA Report (Root Cause Analysis)
  3. Technology Survey (Research reports)
- **Language**: English for external reports, Chinese for internal docs
- **Requirements**:
  - Source-code anchored claims (class names, file paths)
  - Honest about gaps and limitations
  - Comparison with industry implementations
  - Concrete improvement directions

### AI-Assisted Coding Guidelines

When generating code for this repository:

1. **C++**: Generate compilable code first, then optimize
   - Include proper headers
   - Use `std::make_unique` / `std::make_shared`
   - Handle edge cases explicitly
   - Consider move semantics for large objects

2. **Rust**: Start with type signatures
   - Use `cargo check` frequently
   - Follow borrow checker rules
   - Error handling with `anyhow` or `thiserror`

3. **Python**: Use type hints
   - Prefer `pathlib.Path` over `os.path`
   - Use `dataclasses` for structured data
   - Generator expressions for memory efficiency

4. **All Languages**: 
   - No incomplete code snippets
   - Add comments for non-obvious logic
   - Include error handling

## Security Considerations

- `.secrect_key` file exists in shell/ (intentionally misspelled) — DO NOT commit secrets
- Environment variables loaded via `env.sh` scripts
- Database connection strings and credentials stored separately

## IDE Configuration

- **C++**: CLion `.idea/` directories present
- **Java**: IntelliJ IDEA `.idea/` directories present
- **VSCode**: `.vscode/` in .gitignore
- **Clangd**: `compile_commands.json` generated by CMake

## Important Files

- `.clang-format` — C++ code formatting rules
- `.clang-tidy` — C++ linting configuration  
- `mkdocs.yml` — Documentation site configuration
- `CLAUDE.md` — Existing Claude Code guidance
- `**/SKILL.md` — Language/module specific guidelines

## Contact & Context

- **Author**: Li ShuMing (ming.moriarty@gmail.com)
- **Focus Areas**: Database kernels, OLAP systems, query optimization, materialized views
- **Open Source**: Committer on StarRocks
- **Research Interests**: Incremental view maintenance (IVM), streaming systems, query optimizers
