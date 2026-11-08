# AGENTS.md — AI Coding Agent Guide

This document provides essential information for AI coding agents working with the `xlab` repository.

## Mandatory Repository Rules

Before starting any task, read [RULES.md](RULES.md). Its Gmail-only commit identity
and public-content/credential safety requirements apply to every agent, delegated
agent, and subtree. Read it again before creating or rewriting commits or pushing.
Subdirectory instructions may strengthen these requirements but must not relax them.
Delegating agents must pass these requirements to their workers; an already-running
session must reload the rules before its next Git write operation.

## Document Role

This is the canonical root instruction entry point for coding agents. Keep commit
identity and public-content safety policy in `RULES.md`; keep other durable
repository rules, build/test commands, style conventions, and safety notes here.
For human-facing project navigation, use `README.md`. For personal
knowledge-management workflows and active backlog items, use `docs/`.

Use `PROJECTS.md` for project discovery and task routing. Before editing a
module, read its local instructions and build manifest. When adding, moving,
or removing a project, update its entry and routing in `PROJECTS.md`.

## Project Overview

**xlab** is a multi-language laboratory codebase primarily written in Chinese context but with English code/documentation. It serves as a personal research and experimentation platform covering systems programming, data structures, algorithms, and database internals. The repository owner is a senior database kernel engineer with focus on OLAP systems, query optimizers, and distributed systems.

### Repository Information
- **Origin**: https://github.com/LiShuMing/xlab
- **Type**: Personal R&D laboratory / Code experiments collection
- **Language Distribution**: C++ (primary), Python, Rust, Go, Java, OCaml, Lean 4, Shell
- **Documentation**: Chinese (Markdown, Obsidian vault in `docs/`), Code comments: Mixed

## Project Structure

```
xlab/
├── cc/                   # C++ laboratory (main focus)
│   ├── cclab/            # Core C++ lab with CMake build
│   ├── algo/             # Algorithm implementations (LeetCode, etc.)
│   ├── ccbench/          # Benchmarks
│   ├── srlab/            # Serialization experiments
│   ├── extentions/       # GDB / editor extensions
│   ├── projects/         # Remaining personal C++ projects
│   └── thirdparty/       # Declared references; see dependency status below
├── labs/                 # Topic-oriented labs; the language is an implementation detail
│   ├── linux/            # Kernel mechanisms: page faults, page tables, TLB, RCU
│   ├── llm/              # LLM stages and foundations: env, train, bench, torch, numpy
│   ├── interpreter/      # Source to result: tree-walk, self-hosting, LLVM JIT
│   ├── async-io/         # Linux async I/O: io_uring wrapper and a dual-backend server
│   ├── runtime/          # Scheduling models: single-thread reactor vs work-stealing pool
│   ├── lowlevel/         # SIMD vectorization, hand-written NASM assembly, LLVM IR and pass plugins
│   ├── k8s-lab/          # Mini Kubernetes control plane from scratch (pure stdlib)
│   ├── ivm/              # Incremental view maintenance and DBSP prototypes
│   └── daft/             # Daft columnar execution experiments
├── rust/                 # Rust laboratory
│   ├── rlab/             # Workspace-based Rust lab
│   ├── rdb/              # Database implementation experiments
│   └── thirdparty/       # Declared Rust research references
├── python/               # Python laboratory
│   ├── pylab/            # Core Python lab with pytest
│   ├── projects/         # Personal Python projects
│   └── thirdparty/       # Declared Python references
├── go/                   # Go laboratory: LeetCode exercises (`golab`)
├── java/                 # Java laboratory
│   ├── xlab-iceberg/     # Apache Iceberg related
│   └── xlab-itest/       # Interview/test projects
├── ocaml/                # OCaml language, interpreter and constant-folding lab
├── lean4/                # Lean 4 programming and proof lab
├── shell/                # Shell scripting utilities
│   ├── bin/              # Executable scripts
│   ├── docker/           # Docker scripts
│   ├── fio/              # FIO benchmark scripts
│   └── mysql/            # MySQL utilities
├── tools/                # Repository maintenance scripts (healthcheck.sh)
└── docs/                 # Six sections: design/ systems/ playbooks/ notes/ contracts/ archive/
```

## Project Placement

One directory answers one organizing dimension. Decide the home before creating a path:

| The work is about … | Home | Test |
| --- | --- | --- |
| a language: syntax, standard library, toolchain | `cc/`, `python/`, `rust/`, `go/`, `java/`, `ocaml/`, `lean4/`, `shell/` | the exercise loses meaning in another language |
| a mechanism, system or product | `labs/<topic>/` | the topic survives a rewrite in another language |
| knowledge without runnable code | `docs/` | the content survives deleting all code |
| the repository itself | `tools/` | it serves the repo, not a topic |

Rules for `labs/` (details in [labs/README.md](labs/README.md)):

- The language layer never appears at topic level. `labs/linux/` holds experiments directly;
  a `c/`, `rust/` or `python/` subdirectory appears only when one experiment has a second
  implementation.
- An experiment is a unit, not a library: it carries its own sources and run notes, and
  `labs/<topic>/Makefile` only dispatches.
- Shared code moves up, never sideways: same-topic sharing goes to `labs/<topic>/common/`,
  cross-topic sharing to `labs/libs/`. Cross-topic relative paths such as `../python/...`
  fail `tools/test_lab_isolation.py`.
- A single-language application stays in its language tree (`python/projects/py-toydb`,
  `py-ego`, …). `labs/` is not a second `python/projects/`. The deciding question is purpose:
  reproducing a system's mechanism belongs in `labs/` even when one language suffices
  (`labs/k8s-lab/`).

Moving, adding or removing a lab also updates `labs/README.md`, the `PROJECTS.md` routing
table, and every CI path filter that names the old location.

## Migrated Project Routing

The following source roots have left xlab. Do not recreate them here or run
commands against their former paths. Read the destination repository’s local
instructions and build manifests before working there.

| Former xlab path | Current home |
| --- | --- |
| `liminalis/` | [lyra](https://github.com/LiShuMing/lyra/tree/main) |
| `panming/` | [carina](https://github.com/LiShuMing/carina/tree/main) |
| `python/projects/tech-radar/` | [carina/modules/tech-radar](https://github.com/LiShuMing/carina/tree/main/modules/tech-radar) |
| `cc/projects/kv-store/` | [vela/storage](https://github.com/LiShuMing/vela/tree/main/storage) |
| `cc/projects/query-engine/` | [vela/execution](https://github.com/LiShuMing/vela/tree/main/execution) |
| `optimizer-learning/` | [vela/optimizer](https://github.com/LiShuMing/vela/tree/main/optimizer) |
| `swift/projects/daylog/` | [carina/apps/daylog](https://github.com/LiShuMing/carina/tree/main/apps/daylog) |
| `python/projects/py-cli/` | [lyra/modules/developer-tools](https://github.com/LiShuMing/lyra/tree/main/modules/developer-tools) |
| `python/projects/py-tools/` | [lyra/modules/developer-tools](https://github.com/LiShuMing/lyra/tree/main/modules/developer-tools) |
| `python/projects/py-optimizer1/` | [vela/research/optimizer-evidence](https://github.com/LiShuMing/vela/tree/main/research/optimizer-evidence) |
| `python/projects/py-optimizer2/` | [vela/research/optimizer-scanner](https://github.com/LiShuMing/vela/tree/main/research/optimizer-scanner) |
| `python/projects/py-pia/` | [carina/modules/product-intelligence](https://github.com/LiShuMing/carina/tree/main/modules/product-intelligence) |
| `python/projects/py-report/` | [carina/modules/research-report](https://github.com/LiShuMing/carina/tree/main/modules/research-report) |
| `python/projects/py-email/` | [lyra/modules/email-digest](https://github.com/LiShuMing/lyra/tree/main/modules/email-digest) |
| `python/projects/py-learn/` | [lyra/modules/daily-learning](https://github.com/LiShuMing/lyra/tree/main/modules/daily-learning) |

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
- **Workspace root**: none — there is no `rust/Cargo.toml`; run Cargo inside the selected project or pass `--manifest-path`. `rlab` owns its workspace.
- **Key Projects**:
  - `rlab`: Core experiments (lockfree, thread-pool, bloom filter)
  - `rdb`: Database implementation with tokio
- **Key Dependencies**: tokio, parking_lot, serde, zstd, roaring
- **Third-party declarations (currently no gitlinks)**: RisingWave, Materialize, DataFusion, Timely/Differential Dataflow

### Python (python/)
- **Version**: 3.13.5 (managed via pyenv)
- **Environment**: Virtual environments (.venv)
- **Testing**: pytest
- **Manifests**: none at the `python/` root; each project owns its own `requirements.txt` or `pyproject.toml`.
- **Key Packages**: numpy, pandas, duckdb, matplotlib, faiss-cpu
- **Projects**: py-cycle-lab, py-ego, py-lab,
  py-stock, py-toydb
- **Incremental computation**: `labs/ivm/` — incremental view maintenance (IVM) join
  formulas and DBSP (differential dataflow) algebra prototypes, stdlib only

### Go (go/)
- **Version**: 1.26.2 (per `labs/k8s-lab/go.mod`)
- **Module**: Go modules
- **Projects**: `go/golab/` — standalone LeetCode solutions built and run by its
  own `Makefile` (`make leetcode_433`), no `go.mod` and no cgo import. The
  from-scratch mini Kubernetes control plane lives in `labs/k8s-lab/` (pure
  stdlib, zero dependencies): MVCC store, apiserver facade, informers,
  workqueue, ReplicaSet controller, kubelet simulator, `cmd/demo`.
- **Migrated Go module**: [Lyra llm-wiki](https://github.com/LiShuMing/lyra/tree/main/llm-wiki/)
  (formerly `liminalis/llm-wiki/`) owns the context CLI and web service.
  Use its current `go.mod` and README for toolchain and test instructions.

### Java (java/)
- **Build Tools**: Gradle (primary), Maven
- **Projects**: xlab-iceberg, xlab-itest (interview prep)
- **Independent manifests**: modules under `java/xlab-itest/` carry their own Maven/SBT files; the root Gradle build does not cover them.

### OCaml (ocaml/)
- **Version**: 5.5.2, pinned in `.ocaml-version`
- **Build Tool**: Dune 3.24.2; standard library only
- **Commands**: `dune build`, `dune runtest`, `dune exec ocaml-lab`
- **Guide**: `ocaml/README.md` and `ocaml/TUTORIAL.md`

### Lean 4 (lean4/)
- **Version**: 4.35.0, pinned in `lean-toolchain`
- **Build Tool**: Lake; toolchain-provided Std, no Mathlib
- **Commands**: `lake build xlab-lean xlab-tests`, `lake exe xlab-tests`
- **Proof policy**: no `sorry`, `admit`, or custom axioms; warnings fail builds
- **Guide**: `lean4/README.md` and `lean4/TUTORIAL.md`

Activate these isolated user tools with `source tools/learning-env.sh`.
Their build outputs (`ocaml/_build`, `lean4/.lake`) are not source files.
Haskell was owner-retired; do not restore its roots to satisfy historical links.

### Shell (shell/)
- **Shell**: Bash/Zsh
- **Tools**: bin/ utilities, Docker scripts, MySQL utilities
- **Before running**: read each script — several act on the personal host (docker, mysql, fio).

## Build Commands

Root CMake covers only portable cclab and the work-stealing pool in
labs/runtime, not all C++ labs.
Native CI additionally tests rlab/rdb/ToyDB; other projects have independent
requirements. See [README build/CI scope](README.md#build-and-ci-scope).
Standalone cclab defaults to the portable subset. Set CCLAB_PORTABLE_ONLY=OFF
only for the separately provisioned legacy laboratory.


### Native Windows

```powershell
./tools/build-windows.ps1                                # Portable C++ build and tests
./tools/build-windows.ps1 -Project all -Configuration Release
./tools/build-windows.ps1 -Project rlab -Configuration Release
```

See `WINDOWS.md` for the supported module matrix. The script discovers Visual
Studio's MSVC/CMake/Ninja tools and writes outputs to `%LOCALAPPDATA%/xlab-build`.
Use Ninja with `\\wsl.localhost` source paths for WSL-hosted checkouts. The native
`cclab` path builds a portable subset; Linux kernel/POSIX experiments use WSL.

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

### Low-level SIMD, assembly and LLVM IR (labs/lowlevel)
```bash
make -C labs/lowlevel                     # SIMD benchmarks, NASM tutorials, LLVM IR lab
make -C labs/lowlevel/nasm run-t1         # Run one tutorial
make -C labs/lowlevel/llvm check          # Assert the four IR layers
make -C labs/lowlevel/llvm passes         # Per-pass instruction counts and diff
```
The SIMD half needs a C++17 compiler and AVX2; the assembly half needs NASM 2.x;
the LLVM half needs the `llvm18` conda environment (`opt`, `lli`, `clang`,
`llvmdev` headers) plus `gxx_linux-64` for plugin builds — the system g++ is
pinned to the old C++ ABI and produces plugins `opt` cannot load. Each half
writes into its own `bin/`, and the topic Makefile only dispatches.

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
cd labs/k8s-lab
go run ./cmd/demo               # end-to-end mini control plane demo
go test -race ./...             # -race is mandatory (heavy concurrency)
```

### Java
```bash
# Gradle projects
./gradlew build

# Maven projects
mvn test
```

### Documentation
`docs/` is an Obsidian vault of Markdown notes — there is **no site generator
config at the repository root**, so there is nothing to build or serve. Read and
edit the Markdown directly.

Research-report documentation and commands now live in
[Carina modules/research-report](https://github.com/LiShuMing/carina/tree/main/modules/research-report).

## Code Style Guidelines

### Style authority (mandatory)

Every code change — design, naming, error handling, comments and file layout —
must follow the authoritative style guide of its language. This applies to new
files, refactors and review fixes alike; "it works" is not a style argument.

| Language | Authoritative guide | Local enforcement |
| --- | --- | --- |
| C/C++ | [Google C++ Style Guide](https://google.github.io/styleguide/cppguide.html) | nearest `.clang-format` (Google base), `.clang-tidy` |
| Python | [PEP 8](https://peps.python.org/pep-0008/) + [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html) | module pyproject (Ruff) |
| Go | [Effective Go](https://go.dev/doc/effective_go) | `gofmt`, `golangci-lint` |
| Rust | [Rust API Guidelines](https://rust-lang.github.io/api-guidelines/) | `cargo fmt --check`, `cargo clippy` |
| Java | [Google Java Style Guide](https://google.github.io/styleguide/javaguide.html) | module build plugins |
| JS/TS | [Google JS/TS Style Guide](https://google.github.io/styleguide/) | module Prettier/ESLint |
| Shell | [Google Shell Style Guide](https://google.github.io/styleguide/shellguide.html) | `bash -n`, `shellcheck` where available |
| OCaml / Lean 4 | language and library conventions (Dune / Lake layout) | `dune build`, `lake build` |

Precedence when sources disagree: [RULES.md](RULES.md) > module `AGENTS.md` >
nearest formatter configuration > the guide above. A module may tighten naming or
layout; it must not relax correctness, safety or the column limit. Report style work honestly — if a tool is unavailable (for example
`clang-format` is not installed), check the rule by hand and say so instead of
claiming the tool ran.

### Naming and structure (C++, Google C++ Style)
- Types `CamelCase`; functions and methods `CamelCase` verbs (`AddPath`, `Lca`).
- Local variables and parameters `snake_case`; member variables keep a trailing
  underscore (`parent_`); constants and enumerators `kCamelCase`
  (`kTernaryIterations`); macros `PROJECT_UPPER_SNAKE`, and avoid macros anyway.
- `using namespace std;` is a legacy property of `cc/algo/src/include/fwd.h`.
  New code neither adds it nor introduces new unscoped `using` declarations.
- Helpers needed by a single translation unit go into an unnamed namespace so
  linkage stays internal; do not publish them from the global namespace.
- Include only what the file uses, in the order: own header, C library, C++
  standard library, third party, project headers.
- Prefer `std::vector`/`std::array` and `std::` algorithms over hand-rolled
  containers; no owning raw pointers, no manual `new`/`delete`.

### Prefer direct code over speculative abstraction
- Write the concrete algorithm first. Introduce a template, callback, functor or
  wrapper type only when at least two real call sites need the variation; one
  call site means the abstraction is cost without benefit.
- Prefer a plain loop or `std::` algorithm over a new layer; prefer a named local
  struct over a five-field tuple; prefer explicit parameters over captured state.
- No speculative generality: no "future extension" hooks, empty virtual methods,
  or configuration flags that only ever hold one value.
- Name things after what they hold (`pressures`, `parent_`), not after the pattern
  that produced them (`helper`, `manager`, `impl`).
- Comments explain why, invariants and pitfalls; they do not restate the line.

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
- **Compliance**: naming and visibility follow "Naming and structure" above;
algorithm exercises keep a `main()` with a brute-force cross-check,
but the cross-check must stay a direct implementation, not a second framework.

### Rust
- Run `cargo fmt` and `cargo clippy` before committing
- Use `snake_case` for functions/variables
- Use `PascalCase` for types/traits
- Error handling with `Result<T, E>` and `?` operator

### Python
- **Style**: PEP 8
- **Tools**: follow module pyproject settings first (including Ruff); Black/isort are legacy guidance only when no conflicting module policy exists.
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

`.gitmodules` contains exactly two pinned gitlinks, GoogleTest and Google
Benchmark. Preserve their hashes and URLs.
Current dispositions separate installed-package/explicit-source dependencies
from unversioned catalog references; historical unknown intent remains unknown.
Do not invent source revisions or restore orphan declarations. Legacy consumers
must use explicit package/source inputs and fail clearly when prerequisites are absent.
Validate with `bash tools/healthcheck.sh`.
A metadata pass is not whole-repository build certification. Record actual
verification status and core commands in the module that owns them.

### Historical Reference Categories
- **C++ reference catalog**: DuckDB, RocksDB, Folly, Arrow and other historical references
- **Rust reference catalog**: RisingWave, Materialize, DataFusion, Timely Dataflow
- **Python reference catalog**: TinyDB, PyDBSP

⚠️ A successful empty `git submodule status` is not evidence of healthy dependencies.
Compare declarations and tracked gitlinks before discussing initialization.

## Development Conventions

### Documentation Standards
Use [docs/README.md](docs/README.md) for the six-section routing and Cygnus routes.
Writing guidance:

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

- Follow [RULES.md](RULES.md) for Gmail-only Author/Committer identity and mandatory
  checks against non-public corporate content and credentials. Inspect actual
  staged Git objects before committing and every outgoing commit before pushing;
  a clean final working tree or keyword-only scan is not sufficient evidence.
- Environment variables loaded via `env.sh` scripts
- Database connection strings and credentials stored separately
- `.secrect_key` (intentionally misspelled) and `.env` / `.env.*` are gitignored.
  Do not commit secrets under any name.
- **Runtime data must never be committed.** SQLite databases, fetched HTML/JSON
  caches, and local artifacts are generated by the applications on first run and
  may contain chat logs, OAuth tokens, or personal data. `.gitignore` already
  excludes the known paths; when a project starts writing local state, add its
  data directory to `.gitignore` in the same change.
- **Compiled binaries must never be committed.** Build outputs belong in
  `build*/` or `target/`. If a CMake target produces an extensionless binary
  inside a source directory, add an explicit path rule to `.gitignore`.
- Packaged installers (`.deb`, `.rpm`, `.pkg`) are fetched from upstream, not
  vendored.

## IDE Configuration

- **C++**: CLion metadata is not tracked
- **Java**: IntelliJ IDEA metadata is not tracked
- **VSCode**: `.vscode/` in .gitignore
- **Clangd**: `compile_commands.json` generated by CMake

## Important Files

- `RULES.md` — Mandatory Gmail commit identity and public-content/credential safety policy
- `.clang-format` — C++ code formatting rules
- `.clang-tidy` — C++ linting configuration  
- `CLAUDE.md` — Claude Code compatibility pointer to this file
- `QWEN.md` — Qwen Code compatibility pointer (mirrors `CLAUDE.md`)
- `**/AGENTS.md` — Subtree-specific guidance; it may refine local workflows but must not relax root `RULES.md` identity and safety requirements. Each module keeps exactly one such file — module rules, engineering standards and open backlog live in it, not in a second `RULES.md` or `TODOS.md`.

## Contact & Context

- **Author**: Li ShuMing (ming.moriarty@gmail.com)
- **Focus Areas**: Database kernels, OLAP systems, query optimization, materialized views
- **Open Source**: Committer on StarRocks
- **Research Interests**: Incremental view maintenance (IVM), streaming systems, query optimizers

All former `docs/books/` source roots are retired without stubs; do not recreate
them in xlab.

Path, placeholder and formatting conventions: [FORMATTING.md](FORMATTING.md).
