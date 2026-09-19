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
| `AGENTS.md` | Coding agents | Repository rules, build/test commands, style conventions, and safety notes. |
| `CLAUDE.md` | Claude Code compatibility | Thin pointer to `AGENTS.md` to avoid duplicated agent instructions. |
| `SKILL.md` | Knowledge workflows | Personal knowledge-base and technical writing/capture workflow. |
| `TASKS.md` | Maintainers/agents | Current backlog and repository refactoring plan. |

Module-level files such as `cc/SKILL.md`, `python/SKILL.md`, or
`rust/rlab/AGENTS.md` override or refine the root guidance for that subtree.

## Repository Map

```text
xlab/
|-- liminalis/          Unified personal platform: FastAPI + React + Go llm-wiki
|-- optimizer-learning/ Volcano vs Cascades query optimizer comparison tool
|-- cc/                 C++ lab, algorithms, benchmarks, systems/database experiments
|-- rust/               Rust lab, database experiments, async/concurrency projects
|-- python/             Python lab, AI/data tooling, research prototypes
|-- java/               Java projects, Iceberg and interview/test labs
|-- go/                 Go conventions (SKILL.md); real Go code is in liminalis/llm-wiki
|-- haskell/            Functional programming experiments
|-- llm/                GPU/ROCm environment setup notes and scripts
|-- shell/              Shell utilities, Docker/MySQL/FIO helpers
|-- tools/              Repository-level maintenance scripts
`-- docs/               Obsidian vault: notes, reports, and book-length studies
```

### Standalone Projects

These directories are self-contained projects with their own build systems,
suitable for independent iteration or extraction:

| Project | Path | Stack | Notes |
| --- | --- | --- | --- |
| Liminalis | `liminalis/` | FastAPI, React 19, Go | Four domains: radar, invest, ego, wechat. Architecture guarded by tests. |
| Optimizer Learning | `optimizer-learning/` | Python | Volcano and Cascades planners over a shared relational model. |
| TinyKV | `cc/projects/kv-store/` | C++20, CMake | LSM-tree key-value store. |
| Query Engine | `cc/projects/query-engine/` | C++20, CMake | Vectorized execution: hash agg, hash join, sort. |
| MiniSeastar | `cc/projects/mini-seastar/` | C++20, CMake | Coroutine scheduler, per-thread reactor. |
| Umbra JIT | `rust/projects/umbra/` | Rust, Cargo | Data-centric JIT pipeline for OLAP. |
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

Common project commands:

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

# Liminalis platform (needs pip install -e '.[dev]' for backend deps)
cd liminalis
npm install                     # frontend deps
npm run dev                     # Vite dev server
npm run api                     # FastAPI backend on :8010
python -m pytest                # backend tests (testpaths = tests/)
npm run check                   # combined project check

# Optimizer comparison tool (needs: pip install sqlglot)
cd optimizer-learning
python cli.py list
python cli.py compare --all
```

`docs/` is an Obsidian vault of plain Markdown — there is no site generator at
the repository root, so there is nothing to build or serve.

## Working Principles

- Keep generated files, virtual environments, build outputs, and dependency
  installs out of git.
- Keep large third-party dependencies optional and submodule-based.
- Prefer focused module documentation over one giant root document.
- When reorganizing code, preserve migration intent in `TASKS.md` or module
  changelogs so future readers can understand what moved and why.
