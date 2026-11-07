# xlab

`xlab` is a personal research and engineering laboratory for systems programming,
database internals, algorithms, and AI-assisted development workflows.

The repository is intentionally multi-language. C++ is the main systems lab, while
Rust, Python, Java, Go, OCaml, Lean 4, Shell, and documentation projects capture focused
experiments, prototypes, reading notes, and tools.

## Documentation Entry Points

Use the root documents by audience:

| File | Audience | Purpose |
| --- | --- | --- |
| `README.md` | Humans | Project overview, navigation, and quick start. |
| `PROJECTS.md` | Humans/agents | Complete project index, language map, and task routing. |
| `AGENTS.md` | Coding agents | Repository rules, build/test commands, style conventions, and safety notes. |
| `CLAUDE.md` | Claude Code compatibility | Thin pointer to `AGENTS.md` to avoid duplicated agent instructions. |
| [docs/README.md](docs/README.md) | Readers/writers | Knowledge ownership, retained sources, and Cygnus routes. |

Module-level files such as `cc/SKILL.md`, `python/SKILL.md`, or
`rust/rlab/AGENTS.md` override or refine the root guidance for that subtree.

## Repository Map

For every project path, nested workspace member, and third-party reference, see
[PROJECTS.md](PROJECTS.md). It also maps common tasks to the relevant modules
and identifies legacy directories without current source code.

```text
xlab/
|-- cc/                 C++ lab, algorithms, benchmarks, systems/database experiments
|-- rust/               Rust lab, database experiments, async/concurrency projects
|-- python/             Python lab, AI/data tooling, research prototypes
|-- java/               Java projects, Iceberg and interview/test labs
|-- go/                 Go lab: k8s-lab (mini Kubernetes control plane from scratch)
|-- ocaml/              Functional programming, expression interpreter and constant folding
|-- lean4/              Functional programming and machine-checked correctness proofs
|-- llm/                GPU/ROCm environment setup notes and scripts
|-- shell/              Shell utilities, Docker/MySQL/FIO helpers
|-- tools/              Repository-level maintenance scripts
`-- docs/               Six sections: design/ systems/ playbooks/ notes/ contracts/ archive/
```

### Migrated Projects

These thirteen source roots have moved to their own repositories. Continue development,
builds, and issue tracking in the current homes; the old paths are historical.

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

DayLog native UI acceptance was not run; the owner waived it as a source-retirement
prerequisite.

Five named projects were retired by owner decision.

### Standalone Projects in xlab

Selected projects and design scaffolds are listed below. Runnable projects own
their build systems; a scaffold is explicitly marked and has no build command.

| Project | Path | Stack | Notes |
| --- | --- | --- | --- |
| MiniSeastar | `labs/runtime/reactor/` | C++20, CMake | Coroutine scheduler, per-thread reactor. |
| OCaml Lab | [ocaml/](ocaml/) | OCaml, Dune | Language basics, expression interpreter and constant folding; [中文教程](ocaml/TUTORIAL.md). |
| Lean 4 Lab | [lean4/](lean4/) | Lean 4, Lake | Structural induction and constant-folding correctness; [中文教程](lean4/TUTORIAL.md). |
| K8s Lab | `go/k8s-lab/` | Go (stdlib only) | Mini Kubernetes control plane: MVCC store, apiserver, informers, workqueue, ReplicaSet controller, kubelet sim. |
| Linux Lab | [labs/linux/](labs/linux/) | C, C++ | Page faults, page-table walk, TLB and RCU grace-period demos. |
| LLM Lab | [labs/llm/](labs/llm/) | Python | Three stages: GPU environment, tiny-transformer training, quantified evaluation. |
| Daft Lab | `labs/daft/` | Python | Daft columnar execution experiments. |

## Quick Start

Clone normally. Initialize only the two pinned test dependencies when building C++;
historical third-party references live in the dependency catalog.

```bash
git clone https://github.com/LiShuMing/xlab.git
cd xlab

# Diagnose the checkout before selecting a module:
bash tools/healthcheck.sh
```

Dependency status: `.gitmodules` contains exactly two pinned gitlinks
(GoogleTest 1.15.2 and Google Benchmark 1.9.1). Initialize them with
`git submodule update --init -- cc/thirdparty/googletest cc/thirdparty/benchmark`.
The former orphan references are catalog entries; legacy CMake accepts installed
packages or explicit local sources.

Common project commands (run each example separately from the xlab checkout root):

```bash
# Portable C++ subset; opt in to pinned GoogleTest download
cmake -S . -B build -DXLAB_FETCH_DEPENDENCIES=ON
cmake --build build --parallel
ctest --test-dir build --output-on-failure

# Rust lab
cd rust/rlab
cargo test

# Python lab
cd python/pylab
pytest

# k8s-lab: mini Kubernetes control plane (pure Go, zero deps)
cd go/k8s-lab
go run ./cmd/demo               # end-to-end: apply, self-heal, scale
go test -race ./...             # -race is mandatory here
```

For migrated application and database commands, follow the current
[Lyra README](https://github.com/LiShuMing/lyra/blob/main/README.md),
[Carina README](https://github.com/LiShuMing/carina/blob/main/README.md), and
[Vela README](https://github.com/LiShuMing/vela/blob/main/README.md).

`docs/` is an Obsidian vault of plain Markdown — there is no site generator at
the repository root, so there is nothing to build or serve.

## Build and CI Scope

There is no whole-repository build. Root CMake builds only portable `cc/cclab`
and `labs/runtime/pool`; its default dependency download setting is OFF.
Without an installed/cached GoogleTest, default configure fails. Opt-in
`XLAB_FETCH_DEPENDENCIES=ON` fetches pinned test dependencies (and Benchmark
when requested), not the historical research reference catalog. Standalone
`cc/cclab/build.sh` also defaults to the portable subset and runs its tests;
`CCLAB_PORTABLE_ONLY=OFF` explicitly selects the legacy full laboratory.

[Native CI](.github/workflows/native-build.yml) covers portable C++ on
Linux/Windows, Rust rlab/rdb tests and Clippy on Linux/Windows, and ToyDB on Windows.
[Core quality](.github/workflows/core-quality.yml) adds Go vet/race/demo,
IVM, LLM Benchmark, Linux ToyDB, DuckDB smoke, and portable C++ ASAN/UBSAN.
[Repository checks](.github/workflows/repository-checks.yml) validate dependency
metadata, offline fixtures and maintained navigation without an orphan-failure exception.
CI configuration is not evidence that a run has completed. Run the commands
locally and record any module that stays unverified in its own README.

OCaml and Lean 4 use independent Dune/Lake builds. From the checkout root, run
`bash tools/setup-learning.sh all`, then `source tools/learning-env.sh`.
Continue with [OCaml](ocaml/README.md) or [Lean 4](lean4/README.md).
Haskell sources were removed by owner decision.

JVM, GPU and other independent projects still require their local guides
and toolchains. DayLog build/test ownership is in Carina.

## Windows Builds

Native Windows build instructions and the module support matrix are in
[WINDOWS.md](WINDOWS.md). From PowerShell, build/test the portable C++ projects
or the selected multi-language group:

```powershell
./tools/build-windows.ps1
./tools/build-windows.ps1 -Project all -Configuration Release
```

The script discovers Visual Studio's CMake/MSVC/Ninja tools and supports the
current WSL share checkout, with outputs on the Windows disk. Linux-specific
experiments continue to use WSL.

## Working Principles

- Keep generated files, virtual environments, build outputs, and dependency
  installs out of git.
- Keep third-party dependency restoration explicit; declarations alone are not usable gitlinks.
- Prefer focused module documentation over one giant root document.
- When reorganizing code, preserve migration intent in the module README or
  changelog so future readers can understand what moved and why.

Codex/Linux 研究稿、邮件摘要及每日学习模块已迁出，归属见上表。

其余四组书稿共 76 个源文件已退役。

Path, placeholder and formatting conventions: [FORMATTING.md](FORMATTING.md).
