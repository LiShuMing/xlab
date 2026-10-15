# xlab

`xlab` is a personal research and engineering laboratory for systems programming,
database internals, algorithms, and AI-assisted development workflows.

The repository is intentionally multi-language. C++ is the main systems lab, while
Rust, Python, Java, Go, Haskell, Shell, and documentation projects capture focused
experiments, prototypes, reading notes, and tools.

## Documentation Entry Points

Use the root documents by audience:

| File | Audience | Purpose |
| --- | --- | --- |
| `README.md` | Humans | Project overview, navigation, and quick start. |
| `PROJECTS.md` | Humans/agents | Complete project index, language map, and task routing. |
| `AGENTS.md` | Coding agents | Repository rules, build/test commands, style conventions, and safety notes. |
| `CLAUDE.md` | Claude Code compatibility | Thin pointer to `AGENTS.md` to avoid duplicated agent instructions. |
| `SKILL.md` | Knowledge workflows | Personal knowledge-base and technical writing/capture workflow. |
| [docs/README.md](docs/README.md) | Readers/writers | Knowledge ownership, retained sources, and Cygnus routes. |
| `TASKS.md` | Maintainers/agents | Current backlog and repository refactoring plan. |

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
|-- haskell/            Functional programming experiments
|-- llm/                GPU/ROCm environment setup notes and scripts
|-- shell/              Shell utilities, Docker/MySQL/FIO helpers
|-- tools/              Repository-level maintenance scripts
`-- docs/               Obsidian vault: notes, reports, and book-length studies
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

Python source retirement: [verified migration record](docs/migrations/2026-10-14-python-source-retirement.md).

DayLog source retirement and recovery: [verification record](docs/migrations/2026-10-14-daylog-source-retirement.md). Native UI acceptance was not run; the owner waived it as a source-retirement prerequisite.

Five named projects were retired by owner decision: [scope and recovery](docs/migrations/2026-10-15-five-project-retirement.md).

### Standalone Projects in xlab

Selected projects and design scaffolds are listed below. Runnable projects own
their build systems; a scaffold is explicitly marked and has no build command.

| Project | Path | Stack | Notes |
| --- | --- | --- | --- |
| MiniSeastar | `cc/projects/mini-seastar/` | C++20, CMake | Coroutine scheduler, per-thread reactor. |
| K8s Lab | `go/k8s-lab/` | Go (stdlib only) | Mini Kubernetes control plane: MVCC store, apiserver, informers, workqueue, ReplicaSet controller, kubelet sim. |
| LLM Lab | [python/projects/llm-lab/](python/projects/llm-lab/) | Python | Model training/reference experiments. |
| LLM Benchmark | `python/llm_benchmark/` | Python | Quantified LLM evaluation framework. |

## Quick Start

Clone the repository normally. Do not initialize every submodule by default; many
third-party trees are large research references.

```bash
git clone https://github.com/LiShuMing/xlab.git
cd xlab

# Diagnose the checkout before selecting a module:
bash tools/healthcheck.sh
```

Dependency status: `.gitmodules` now has 40 declarations: two pinned gitlinks
(GoogleTest 1.15.2 and Google Benchmark 1.9.1) plus 38 unresolved orphan declarations.
Initialize only the two real gitlinks with
`git submodule update --init -- cc/thirdparty/googletest cc/thirdparty/benchmark`.
29 reference/external-package declarations are preserved in the [dependency inventory](docs/meta/dependency-declarations.json)
instead of `.gitmodules`; no dependency source or package consumer was deleted.
The remaining 38 include five direct/manual legacy inputs and 33 unresolved cases.
The healthcheck deliberately continues to report those 38 failures.
See [consumer evidence](docs/meta/dependency-declarations.md), [pinned versions](docs/meta/cpp-test-dependencies.md)
and [build scope](#build-and-ci-scope).

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
and `cc/projects/thread-pool`; its default dependency download setting is OFF.
Without an installed/cached GoogleTest, default configure fails. Opt-in
`XLAB_FETCH_DEPENDENCIES=ON` fetches pinned test dependencies (and Benchmark
when requested), not the historical research reference catalog. The legacy standalone
`cc/cclab/build.sh` has broader third-party requirements and is not equivalent.

[Native CI](.github/workflows/native-build.yml) tests this C++ subset on
Linux/Windows, plus `rust/rlab`, `rust/rdb`, and Python ToyDB on Windows.
Its path filters do not cover every lab or documentation-only change.
[Repository checks](.github/workflows/repository-checks.yml) run offline
healthcheck fixtures and navigation checks. A passing fixture suite does not
mean the full checkout healthcheck passes or every project builds.
Go, Haskell, JVM and other independent projects require their own local guides
and toolchains. DayLog build/test ownership is now in Carina.

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
- When reorganizing code, preserve migration intent in `TASKS.md` or module
  changelogs so future readers can understand what moved and why.

Codex/Linux 研究稿、邮件摘要及每日学习模块的当前归属、排除项与恢复入口见
[本批迁移记录](docs/migrations/2026-10-14-books-email-learning-retirement.md)。

Current retained-project decisions and cleanup boundaries: [classification](docs/meta/retained-projects.md), [consolidated cleanup](docs/meta/repository-cleanup.md).

其余四组书稿共 76 个源文件的验收、维护归属与恢复见 [书稿退役记录](docs/migrations/2026-10-15-remaining-books-retirement.md)。

Path, placeholder and formatting conventions: [FORMATTING.md](FORMATTING.md).
