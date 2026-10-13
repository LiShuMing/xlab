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

These six source roots have moved to their own repositories. Continue development,
builds, and issue tracking in the current homes; the old paths are historical.

| Former xlab path | Current home |
| --- | --- |
| `liminalis/` | [lyra](https://github.com/LiShuMing/lyra/tree/main) |
| `panming/` | [carina](https://github.com/LiShuMing/carina/tree/main) |
| `python/projects/tech-radar/` | [carina/modules/tech-radar](https://github.com/LiShuMing/carina/tree/main/modules/tech-radar) |
| `cc/projects/kv-store/` | [vela/storage](https://github.com/LiShuMing/vela/tree/main/storage) |
| `cc/projects/query-engine/` | [vela/execution](https://github.com/LiShuMing/vela/tree/main/execution) |
| `optimizer-learning/` | [vela/optimizer](https://github.com/LiShuMing/vela/tree/main/optimizer) |

### Standalone Projects in xlab

These remaining directories are self-contained projects with their own build systems:

| Project | Path | Stack | Notes |
| --- | --- | --- | --- |
| MiniSeastar | `cc/projects/mini-seastar/` | C++20, CMake | Coroutine scheduler, per-thread reactor. |
| Umbra JIT | `rust/projects/umbra/` | Rust, Cargo | Data-centric JIT pipeline for OLAP. |
| K8s Lab | `go/k8s-lab/` | Go (stdlib only) | Mini Kubernetes control plane: MVCC store, apiserver, informers, workqueue, ReplicaSet controller, kubelet sim. |
| LLM Benchmark | `python/llm_benchmark/` | Python | Quantified LLM evaluation framework. |

## Quick Start

Clone the repository normally. Do not initialize every submodule by default; many
third-party trees are large research references.

```bash
git clone https://github.com/LiShuMing/xlab.git
cd xlab

# Initialize only what you need, for example:
git submodule update --init cc/thirdparty/googletest cc/thirdparty/abseil-cpp
```

Common project commands (run each example from the xlab checkout root):

```bash
# C++ core lab
cd cc/cclab
./build.sh

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
- Keep large third-party dependencies optional and submodule-based.
- Prefer focused module documentation over one giant root document.
- When reorganizing code, preserve migration intent in `TASKS.md` or module
  changelogs so future readers can understand what moved and why.
