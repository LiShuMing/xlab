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
|-- cc/          C++ lab, algorithms, benchmarks, systems/database experiments
|-- rust/        Rust lab, database experiments, async/concurrency projects
|-- python/      Python lab, AI/data tooling, research prototypes
|-- java/        Java projects, Iceberg and interview/test labs
|-- go/          Go experiments
|-- haskell/     Functional programming experiments
|-- shell/       Shell utilities, Docker/MySQL/FIO helpers
|-- docs/        MkDocs knowledge base and technical notes
|-- skills/      Local Codex/agent skills
`-- _templates/  Reusable note/project templates
```

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

# Documentation
mkdocs serve
```

## Working Principles

- Keep generated files, virtual environments, build outputs, and dependency
  installs out of git.
- Keep large third-party dependencies optional and submodule-based.
- Prefer focused module documentation over one giant root document.
- When reorganizing code, preserve migration intent in `TASKS.md` or module
  changelogs so future readers can understand what moved and why.
