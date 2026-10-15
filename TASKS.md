# xlab Repository Refactoring Plan

## Document Role

This file is the active backlog for repository cleanup, restructuring, and
quality work. Keep task lists, migration notes, and refactoring plans here.
Stable project navigation belongs in `README.md`; coding-agent rules belong in
`AGENTS.md`; knowledge capture workflows belong in `SKILL.md`.

## Migrated Work: Destination Routing

The earlier source roots below have been accepted into their destination repositories.
Their old task lists are retained only as historical planning context, not active
xlab backlog or verified statements of current destination gaps. Reconcile any
remaining work with the destination’s current tests, documentation, and backlog;
do not recreate the old xlab directories.

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

## Windows Portability

- [x] Add a native PowerShell build/test entry point with Visual Studio tool discovery.
- [x] Share CMake test dependencies and separate MSVC/Unix compiler options.
- [x] Historically built a portable cclab subset, TinyKV, query-engine, and thread-pool together. TinyKV and query-engine now build in Vela.
- [x] Repair queue ownership, shutdown, Arena alignment, and initialization defects found by Windows tests.
- [x] Package and test ToyDB, and isolate RDB tests from hard-coded Unix directories.
- [x] Add Windows/Ubuntu CI definitions and a module support matrix in `WINDOWS.md`.
- [ ] Complete Windows ports of the remaining cclab components and serialization/SIMD labs.
- [ ] Audit native extensions, LLVM/ANTLR, Tauri, and service-dependent applications separately.
- [ ] Validate Java, Go, and Haskell with their Windows toolchains.
- [ ] Keep Linux kernel/POSIX API experiments runnable in WSL.

## Current cleanup decisions (2026-10-15)

- Keep one consolidated xlab cleanup proposal. Publication and merge need authorization.
- Preserve unmigrated projects and held books; classify them using the [current inventory](docs/meta/retained-projects.md).
- Review every orphan dependency declaration against its actual consumers before changing it; preserve the two pinned gitlinks.
- Legacy cron is removed without a stub; no installed schedule was inspected or changed. Replacing installed schedules and migrating live state are separate actions.
- Calcite/RisingWave import review is pending. Their source retirement can join this same proposal only after accepted target-main mappings exist. Claude Code/Feynman remain held for provenance/quotation review.
- Review the obsolete draft [PR #20](https://github.com/LiShuMing/xlab/pull/20) for reconciliation or closure; it is not automatically merged or closed here.
- Remaining experiments keep their current ownership. A matching name in another repository is not migration evidence.

The long-form backlog below is historical planning, not a current audit of missing
files or feature gaps. Before implementation, verify the module's current state.
Existing-file checklist entries are marked for review rather than creation.

## Overview

重构多语言实验室仓库xlab，将各语言项目拆分为独立项目，每个项目使用独立Context，并创建现代LLM项目必备文件，丰富测试覆盖率，标记无用文件。

## Historical Repository Structure Analysis

> **Historical snapshot, not the current checkout**: 2026-09-19. Verified against the working tree on branch
> `chore/repo-hygiene` (from `origin/main`). Directories listed under "Projects
> removed" no longer exist here; their tasks have been redirected.

```
xlab/
├── liminalis/            # Unified personal platform (NOT yet in older plans)
│   ├── backend/          # FastAPI: radar, invest, ego, wechat, _shared
│   ├── src/              # React 19 + Vite + Tailwind frontend
│   ├── llm-wiki/         # Go CLI (personal context maintenance)
│   ├── tests/            # pytest suite incl. architecture guard tests
│   └── docs/             # PRDs, RFCs, API contracts
├── optimizer-learning/   # Volcano vs Cascades optimizer comparison tool
├── cc/                   # C++ Projects
│   ├── cclab/            # Core C++ lab (CMake, Google Test)
│   ├── algo/             # Algorithm implementations
│   ├── ccbench/          # Benchmarks
│   ├── srlab/            # Serialization experiments
│   ├── simd/             # SIMD optimizations
│   ├── nasm/             # Assembly experiments
│   ├── extentions/       # GDB / editor extensions
│   ├── golab/            # Go-C++ interop (single file)
│   ├── tools/            # duckdb and misc tooling
│   └── projects/         # Personal C++ projects
│       ├── cpython/      # Python extension
│       ├── interpreter/  # Language interpreter
│       ├── io-uring/     # io_uring experiments
│       ├── kv-store/     # Key-value store
│       ├── llvm-jit/     # LLVM JIT compiler
│       ├── mini-seastar/ # Async framework
│       ├── query-engine/ # Query engine
│       ├── thread-pool/  # Thread pool
│       └── web-server/   # Web server
├── rust/                 # Rust Projects
│   ├── rlab/             # Core Rust lab
│   ├── rdb/              # Database implementation
│   └── projects/         # Projects
│       ├── fragment-tutor/
│       ├── subway-game/
│       └── umbra/
├── python/               # Python Projects
│   ├── pylab/            # Core Python lab
│   ├── llm_benchmark/    # LLM evaluation framework
│   ├── ivm/              # Incremental view maintenance prototypes
│   ├── tools/            # Python tooling
│   └── projects/         # Projects
│       ├── py-academic/  # VENDORED fork of binary-husky/gpt_academic
│       ├── py-cycle-lab/ # Long-cycle investment compass
│       ├── py-ego/       # StarRocks MV monitor + LLM companion
│       ├── py-lab/       # Streamlit/LangChain AI platform
│       ├── py-stock/     # Stock price database
│       ├── py-torch/     # micrograd + PyTorch learning
│       └── py-toydb/     # Toy database
├── java/                 # Java Projects
│   ├── xlab-iceberg/     # Apache Iceberg
│   └── xlab-itest/       # Integration test projects (4 Gradle modules;
│                         #   xlab-interview/jlib/scala/spark/spring are plain
│                         #   dirs, NOT included in settings.gradle.kts)
├── haskell/              # Haskell Projects
│   ├── hslab/            # Core Haskell lab (single file)
│   └── projects/         # Projects
│       ├── dsl-transform/    # DSL transformation
│       ├── sql-parser/       # SQL parser
│       └── stm-engine/       # STM engine
├── go/                   # Go Projects
│   ├── SKILL.md          # conventions
│   └── k8s-lab/          # mini Kubernetes control plane from scratch (zero deps)
├── llm/                  # GPU / ROCm environment notes and scripts
│   └── cuda/
├── tools/                # Repository maintenance scripts
├── shell/                # Shell Projects
│   ├── bin/              # Utilities
│   ├── docker/           # Docker scripts
│   ├── fio/              # FIO tests
│   └── mysql/            # MySQL utilities
└── docs/                 # Obsidian vault (Markdown, NOT an MkDocs site)
```

### Projects removed since the last plan revision

| Old path | Disposition |
| --- | --- |
| `projects/llm-wiki` | Previously moved to `liminalis/llm-wiki`; now [Lyra llm-wiki](https://github.com/LiShuMing/lyra/tree/main/llm-wiki/). |
| `go/hello` | Never materialized; the first `go/` project is `go/k8s-lab/`. |
| `skills/`, `_templates/` | Do not exist at repo root; skills live in `docs/skills/` and `.claude/skills/`. |

Do not create tasks against the paths above. Work belongs in the successor
location.

### Historical branch divergence observation (2026-09-19; not current status)

At that earlier audit, `main` was recorded as containing only **3 commits** (`4176047`, `4a022f3`, `357df48`), while
`dev1` holds **169 commits that are not on `main`**. The two lines have
different project inventories.

These counts are retained as historical context and must not be used for current routing. Before
executing any task here, confirm which branch you are on; tasks written against
`main`'s layout may not apply to `dev1`.

## Common Tasks (All Projects)

每个项目需要完成以下任务：

### 1. 创建现代LLM项目文件

- **AGENTS.md** - AI助手工作指南
  - 项目概述和目标
  - 技术栈和依赖
  - 构建和测试命令
  - 代码风格规范
  - 重要文件和目录结构

- **RULES.md** - 项目规则和规范
  - 代码命名规范
  - 提交信息规范
  - 测试要求
  - 文档要求

- **README.md** - 项目文档
  - 项目介绍
  - 快速开始
  - 构建说明
  - 测试说明
  - 目录结构

- **CHANGELOG.md** - 变更日志
  - 版本历史
  - 功能变更
  - Bug修复

- **docs/** 目录
  - architecture/ - 架构文档
  - api/ - API文档
  - guides/ - 使用指南

### 2. 丰富单元测试覆盖率

- 目标：核心代码覆盖率达到80%+
- 测试策略：
  - 单元测试（所有函数/方法）
  - 集成测试（关键流程）
  - 边界情况测试
  - 错误处理测试

### 3. 标记无用文件

- 扫描并标记：
  - 未使用的代码文件
  - 临时文件
  - 重复代码
  - 废弃的配置
- 记录到 `TODOS.md`

### 4. 符合语言规范

- C++: C++20/23, clang-format, clang-tidy
- Rust: 2021 edition, cargo fmt, clippy
- Python: 3.13+, black, ruff, mypy
- Java: Gradle/Maven, standard conventions
- Go: gofmt, golint
- Haskell: cabal/stack, hlint
- Shell: shellcheck

### 5. 符合LLM Vibe Coding规范

- 清晰的文件结构
- 自解释的命名
- 类型提示（Python/TypeScript）
- 完整的文档字符串
- 示例代码

### 6. 符合Harness Engineer规范

- 标准化的构建脚本
- CI/CD配置（GitHub Actions）
- 代码覆盖率报告
- 自动化测试

---

## 按项目详细任务

---

### 【C++ 项目】

#### Project: cc/cclab

**现状**: Core C++ lab with CMake build, Google Test, data structures and algorithms

**Tasks**:

1. **创建项目文件**
   - [ ] 复核 `cc/cclab/AGENTS.md`（文件已存在；内容与质量需按当前实现核对）
     - 项目概述：C++实验室核心代码
     - 构建命令：`./build.sh [DEBUG|RELEASE|ASAN|LSAN]`
     - 测试命令：`cd build_ASAN && ctest`
     - 代码风格：.clang-format, .clang-tidy
   - [ ] 复核 `cc/cclab/RULES.md`（文件已存在；内容与质量需按当前实现核对）
     - C++20/23标准
     - Google Test测试框架
     - Sanitizer使用（ASAN, LSAN, UBSAN）
   - [ ] 复核 `cc/cclab/CHANGELOG.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 创建 `cc/cclab/docs/`
     - architecture/ - 架构图
     - api/ - API参考

2. **丰富单元测试**
   - [ ] 分析现有测试覆盖（test/目录）
   - [ ] 为核心数据结构添加测试：
     - SkipList
     - B+Tree
     - Robin Hood Hash Map
     - MPMC Queue
   - [ ] 为工具类添加测试：
     - Thread pools
     - Coroutines
     - Consistent hash
     - LRU cache
   - [ ] 目标：核心代码覆盖率达到80%+

3. **标记无用文件**
   - [ ] 扫描src/和test/目录
   - [ ] 标记未使用的实验性代码
   - [ ] 记录到 `cc/cclab/TODOS.md`

4. **代码规范检查**
   - [ ] 运行 `clang-format -i` 格式化所有代码
   - [ ] 运行 `clang-tidy` 检查并修复问题
   - [ ] 确保所有头文件有 `#pragma once`
   - [ ] 确保所有公有函数有文档注释

5. **CI/CD配置**
   - [ ] 创建 `.github/workflows/ci.yml`
     - Build矩阵（DEBUG, RELEASE, ASAN）
     - 测试执行
     - Clang-tidy检查

---

#### Project: cc/algo

**现状**: Algorithm implementations with LeetCode solutions

**Tasks**:

1. **创建项目文件**
   - [ ] 复核 `cc/algo/AGENTS.md`（文件已存在；内容与质量需按当前实现核对）
     - LeetCode解决方案集合
     - 构建系统：Makefile
     - 运行命令：`make leetcode_<number>`
   - [ ] 复核 `cc/algo/RULES.md`（文件已存在；内容与质量需按当前实现核对）
     - 每个算法文件头部注释：问题描述、复杂度分析
   - [ ] 复核 `cc/algo/README.md`（文件已存在；内容与质量需按当前实现核对）
     - 按类别组织的算法列表
   - [ ] 复核 `cc/algo/CHANGELOG.md`（文件已存在；内容与质量需按当前实现核对）

2. **丰富单元测试**
   - [ ] 为LeetCode解决方案添加测试框架
   - [ ] 每个算法至少3个测试用例（正常、边界、错误）

3. **标记无用文件**
   - [ ] 检查重复或废弃的算法实现
   - [ ] 记录到 `cc/algo/TODOS.md`

---

#### Project: cc/ccbench

**现状**: Benchmark framework

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `cc/ccbench/AGENTS.md`
   - [ ] 创建 `cc/ccbench/RULES.md`
   - [ ] 创建 `cc/ccbench/README.md`
   - [ ] 创建 `cc/ccbench/CHANGELOG.md`

2. **丰富测试**
   - [ ] 为benchmark工具本身添加测试
   - [ ] 确保所有benchmark可运行

---

#### Project: cc/srlab

**现状**: Serialization experiments

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `cc/srlab/AGENTS.md`
   - [ ] 创建 `cc/srlab/RULES.md`
   - [ ] 复核 `cc/srlab/README.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 创建 `cc/srlab/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 分析tests/目录现有测试
   - [ ] 为序列化/反序列化添加边界测试

---

#### Project: cc/simd

**现状**: SIMD optimization experiments

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `cc/simd/AGENTS.md`
   - [ ] 创建 `cc/simd/RULES.md`
   - [ ] 创建 `cc/simd/README.md`
   - [ ] 创建 `cc/simd/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 为SIMD实现添加正确性测试
   - [ ] 添加性能对比测试

---

#### Project: cc/projects/cpython

**现状**: Python C extension experiments

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `cc/projects/cpython/AGENTS.md`
   - [ ] 创建 `cc/projects/cpython/RULES.md`
   - [ ] 复核 `cc/projects/cpython/README.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 创建 `cc/projects/cpython/CHANGELOG.md`

2. **丰富测试**
   - [ ] 添加Python端测试
   - [ ] 确保C扩展可正确编译和导入

---

#### Project: cc/projects/interpreter

**现状**: Language interpreter implementation

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `cc/projects/interpreter/AGENTS.md`
   - [ ] 创建 `cc/projects/interpreter/RULES.md`
   - [ ] 复核 `cc/projects/interpreter/README.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 创建 `cc/projects/interpreter/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 为lexer/parser添加测试
   - [ ] 为AST求值添加测试
   - [ ] 为运行时添加测试

---

#### Project: cc/projects/io-uring

**现状**: io_uring experiments

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `cc/projects/io-uring/AGENTS.md`
   - [ ] 创建 `cc/projects/io-uring/RULES.md`
   - [ ] 复核 `cc/projects/io-uring/README.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 创建 `cc/projects/io-uring/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 添加io_uring操作测试
   - [ ] 添加性能基准测试

---

#### Historical Project: cc/projects/kv-store → [vela/storage](https://github.com/LiShuMing/vela/tree/main/storage)

> Historical pre-migration notes only. Continue work in the linked destination;
> check its current implementation before adopting any item below.

**迁移前现状**: Key-value store implementation

**Historical task ideas (not active xlab tasks)**:

1. **创建项目文件**
   - 创建 `cc/projects/kv-store/AGENTS.md`
   - 创建 `cc/projects/kv-store/RULES.md`
   - 创建 `cc/projects/kv-store/README.md`
   - 创建 `cc/projects/kv-store/CHANGELOG.md`
   - 创建 `cc/projects/kv-store/docs/architecture/`

2. **丰富单元测试**
   - 为存储引擎添加测试
   - 为网络层添加测试
   - 为并发操作添加测试
   - 为持久化添加测试

---

#### Project: cc/projects/llvm-jit

**现状**: LLVM JIT compiler experiments

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `cc/projects/llvm-jit/AGENTS.md`
   - [ ] 创建 `cc/projects/llvm-jit/RULES.md`
   - [ ] 创建 `cc/projects/llvm-jit/README.md`
   - [ ] 创建 `cc/projects/llvm-jit/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 为JIT编译添加测试
   - [ ] 为优化pass添加测试

---

#### Project: cc/projects/mini-seastar

**现状**: Async framework inspired by Seastar

**Tasks**:

1. **创建项目文件**
   - [ ] 复核 `cc/projects/mini-seastar/AGENTS.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 复核 `cc/projects/mini-seastar/RULES.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 复核 `cc/projects/mini-seastar/README.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 复核 `cc/projects/mini-seastar/CHANGELOG.md`（文件已存在；内容与质量需按当前实现核对）

2. **丰富单元测试**
   - [ ] 为future/promise添加测试
   - [ ] 为scheduler添加测试
   - [ ] 为网络层添加测试

---

#### Historical Project: cc/projects/query-engine → [vela/execution](https://github.com/LiShuMing/vela/tree/main/execution)

> Historical pre-migration notes only. Continue work in the linked destination;
> check its current implementation before adopting any item below.

**迁移前现状**: Query engine implementation

**Historical task ideas (not active xlab tasks)**:

1. **创建项目文件**
   - 创建 `cc/projects/query-engine/AGENTS.md`
   - 创建 `cc/projects/query-engine/RULES.md`
   - 创建 `cc/projects/query-engine/README.md`
   - 创建 `cc/projects/query-engine/CHANGELOG.md`
   - 创建 `cc/projects/query-engine/docs/architecture/`

2. **丰富单元测试**
   - 为parser添加测试
   - 为planner添加测试
   - 为executor添加测试
   - 为storage层添加测试

---

#### Project: cc/projects/thread-pool

**现状**: Thread pool implementation

**Tasks**:

1. **创建项目文件**
   - [ ] 复核 `cc/projects/thread-pool/AGENTS.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 复核 `cc/projects/thread-pool/RULES.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 复核 `cc/projects/thread-pool/README.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 复核 `cc/projects/thread-pool/CHANGELOG.md`（文件已存在；内容与质量需按当前实现核对）

2. **丰富单元测试**
   - [ ] 为线程池添加并发测试
   - [ ] 添加性能基准测试

---

#### Project: cc/projects/web-server

**现状**: Web server implementation

**Tasks**:

1. **创建项目文件**
   - [ ] 复核 `cc/projects/web-server/AGENTS.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 复核 `cc/projects/web-server/RULES.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 复核 `cc/projects/web-server/README.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 复核 `cc/projects/web-server/CHANGELOG.md`（文件已存在；内容与质量需按当前实现核对）

2. **丰富单元测试**
   - [ ] 为HTTP解析添加测试
   - [ ] 为路由添加测试
   - [ ] 为并发连接添加测试

---

### 【Rust 项目】

#### Project: rust/rlab

**现状**: Core Rust lab with Cargo workspace

**Tasks**:

1. **创建项目文件**
   - [ ] 复核 `rust/rlab/AGENTS.md`（文件已存在；内容与质量需按当前实现核对）
     - Cargo workspace结构
     - 子crate: bloom_filter, leetcode, lockfree-queue, rlab-tools, thread-pool
   - [ ] 复核 `rust/rlab/RULES.md`（文件已存在；内容与质量需按当前实现核对）
     - Rust 2021 edition
     - cargo fmt, cargo clippy
     - Error handling with Result
   - [ ] 复核 `rust/rlab/README.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 复核 `rust/rlab/CHANGELOG.md`（文件已存在；内容与质量需按当前实现核对）

2. **丰富单元测试**
   - [ ] 为bloom_filter添加测试
   - [ ] 为lockfree-queue添加并发测试
   - [ ] 为thread-pool添加测试

3. **标记无用文件**
   - [ ] 检查并标记无用代码
   - [ ] 记录到 `rust/rlab/TODOS.md`

4. **代码规范检查**
   - [ ] 运行 `cargo fmt --all`
   - [ ] 运行 `cargo clippy --all-targets --all-features`
   - [ ] 确保所有pub函数有文档注释

5. **CI/CD配置**
   - [ ] 创建 `.github/workflows/ci.yml`

---

#### Project: rust/rdb

**现状**: Database implementation in Rust

**Tasks**:

1. **创建项目文件**
   - [ ] 复核 `rust/rdb/AGENTS.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 复核 `rust/rdb/RULES.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 复核 `rust/rdb/README.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 复核 `rust/rdb/CHANGELOG.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 创建 `rust/rdb/docs/architecture/`

2. **丰富单元测试**
   - [ ] 为analyzer添加测试
   - [ ] 为executor添加测试
   - [ ] 为parser添加测试
   - [ ] 为planner添加测试
   - [ ] 为storage添加测试

---

#### Project: rust/projects/umbra

**现状**: Umbra database experiments

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `rust/projects/umbra/AGENTS.md`
   - [ ] 创建 `rust/projects/umbra/RULES.md`
   - [ ] 复核 `rust/projects/umbra/README.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 创建 `rust/projects/umbra/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 分析并补充测试

---

### 【Python 项目】

#### Project: python/pylab

**现状**: Core Python lab with pytest

**Tasks**:

1. **创建项目文件**
   - [ ] 复核 `python/pylab/AGENTS.md`（文件已存在；内容与质量需按当前实现核对）
     - Python 3.13+
     - pytest测试框架
     - 依赖管理：requirements.txt
   - [ ] 复核 `python/pylab/RULES.md`（文件已存在；内容与质量需按当前实现核对）
     - PEP 8规范
     - Type hints要求
     - black, isort, ruff配置
   - [ ] 复核 `python/pylab/README.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 复核 `python/pylab/CHANGELOG.md`（文件已存在；内容与质量需按当前实现核对）

2. **丰富单元测试**
   - [ ] 分析test/目录现有测试
   - [ ] 为核心模块添加测试
   - [ ] 目标：80%+覆盖率

3. **标记无用文件**
   - [ ] 扫描并标记无用代码
   - [ ] 记录到 `python/pylab/TODOS.md`

4. **代码规范检查**
   - [ ] 添加pyproject.toml配置（black, ruff, mypy）
   - [ ] 运行black格式化
   - [ ] 运行ruff检查
   - [ ] 运行mypy类型检查

5. **CI/CD配置**
   - [ ] 创建 `.github/workflows/ci.yml`

---

#### Historical Project: liminalis/backend/radar → [lyra/backend/radar](https://github.com/LiShuMing/lyra/tree/main/backend/radar)

> Historical pre-migration notes only. Continue work in the linked destination;
> check its current implementation before adopting any item below.

**迁移前现状**: Liminalis 的情报雷达业务域（45 个跟踪文件 / 39 个 `.py`），已有测试
`liminalis/tests/test_radar.py`、`test_radar_extractor.py`、
`liminalis/backend/tests/radar/`。

**Historical task ideas (not active xlab tasks)**:

1. **补齐测试**
   - 为 `backend/radar/ranker.py`、`summarizer.py`、`seen_tracker.py` 添加测试
   - 为 `backend/radar/sync/` 添加测试
2. **遵循架构约束**
   - 确认改动通过 `tests/test_architecture.py`（`_shared` 边界与事务规则守护）

---

#### Historical Project: liminalis/backend/invest → [lyra/backend/invest](https://github.com/LiShuMing/lyra/tree/main/backend/invest)

> Historical pre-migration notes only. Continue work in the linked destination;
> check its current implementation before adopting any item below.

**迁移前现状**: Liminalis 的投资分析业务域（含 `agents/`、`core/`、`modules/`、
`scheduler/`、`notifier/`、`web/`、`diff/`），已有测试
`liminalis/tests/test_invest.py`、`liminalis/backend/invest/tests/`。

**Historical task ideas (not active xlab tasks)**:

1. **补齐测试**
   - 为 `backend/invest/agents/` 添加测试
   - 为 `backend/invest/core/` 添加测试
   - 为 `backend/invest/modules/data_collector`、`report_generator` 添加测试
2. **遵循架构约束**
   - 确认改动通过 `tests/test_architecture.py`

---

#### Migrated: Lyra email-digest and daily-learning

Current code, safety boundaries and tests live in [email-digest](https://github.com/LiShuMing/lyra/tree/main/modules/email-digest) and [daily-learning](https://github.com/LiShuMing/lyra/tree/main/modules/daily-learning). Historical xlab backlog is superseded; do not recreate retired roots.

---

#### Project: python/projects/py-toydb

**现状**: Toy database implementation

**Tasks**:

1. **创建项目文件**
   - [ ] 复核 `python/projects/py-toydb/AGENTS.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 复核 `python/projects/py-toydb/RULES.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 复核 `python/projects/py-toydb/README.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 复核 `python/projects/py-toydb/CHANGELOG.md`（文件已存在；内容与质量需按当前实现核对）

2. **丰富单元测试**
   - [ ] 为toydb模块添加测试

---

#### Project: python/projects/py-ego

**现状**: AI assistant project

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `python/projects/py-ego/AGENTS.md`
   - [ ] 创建 `python/projects/py-ego/RULES.md`
   - [ ] 复核 `python/projects/py-ego/README.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 创建 `python/projects/py-ego/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 为核心模块添加测试

---

#### Project: python/projects/py-academic

**现状**: Academic paper tools

**Tasks**:

1. **创建项目文件**
   - [ ] 复核 `python/projects/py-academic/AGENTS.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 创建 `python/projects/py-academic/RULES.md`
   - [ ] 复核 `python/projects/py-academic/README.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 创建 `python/projects/py-academic/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 为crazy_functions模块添加测试

---

#### Project: python/projects/py-lab

**现状**: Python lab tools

**Tasks**:

1. **创建项目文件**
   - [ ] 复核 `python/projects/py-lab/AGENTS.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 创建 `python/projects/py-lab/RULES.md`
   - [ ] 复核 `python/projects/py-lab/README.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 创建 `python/projects/py-lab/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 为核心模块添加测试

---

#### Project: python/projects/py-stock

**现状**: Stock analysis tool

**Tasks**:

1. **创建项目文件**
   - [ ] 复核 `python/projects/py-stock/AGENTS.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 创建 `python/projects/py-stock/RULES.md`
   - [ ] 复核 `python/projects/py-stock/README.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 创建 `python/projects/py-stock/CHANGELOG.md`

---

### 【Java 项目】

#### Project: java/xlab-iceberg

**现状**: Apache Iceberg related experiments

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `java/xlab-iceberg/AGENTS.md`
     - Gradle构建
     - Java版本
   - [ ] 创建 `java/xlab-iceberg/RULES.md`
   - [ ] 复核 `java/xlab-iceberg/README.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 创建 `java/xlab-iceberg/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 为核心功能添加JUnit测试

---

#### Project: java/xlab-itest

**现状**: Integration test projects (multi-module)

**Tasks**:

1. **创建项目文件**
   - [ ] 复核 `java/xlab-itest/AGENTS.md`（文件已存在；内容与质量需按当前实现核对）
     - 多模块项目结构
     - 子项目: benchmark, framework, groovy, interview, itest, jlib, scala, spark, spring
   - [ ] 复核 `java/xlab-itest/RULES.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 复核 `java/xlab-itest/README.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 复核 `java/xlab-itest/CHANGELOG.md`（文件已存在；内容与质量需按当前实现核对）

2. **丰富单元测试**
   - [ ] 为各子项目添加测试

---

### 【Haskell 项目】

#### Project: haskell/hslab

**现状**: Core Haskell lab

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `haskell/hslab/AGENTS.md`
     - Cabal/Stack构建
   - [ ] 创建 `haskell/hslab/RULES.md`
   - [ ] 创建 `haskell/hslab/README.md`
   - [ ] 创建 `haskell/hslab/CHANGELOG.md`

---

#### Project: haskell/projects/sql-parser

**现状**: SQL parser in Haskell

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `haskell/projects/sql-parser/AGENTS.md`
   - [ ] 创建 `haskell/projects/sql-parser/RULES.md`
   - [ ] 复核 `haskell/projects/sql-parser/README.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 创建 `haskell/projects/sql-parser/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 为parser添加测试

---

#### Project: haskell/projects/dsl-transform

**现状**: DSL transformation

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `haskell/projects/dsl-transform/AGENTS.md`
   - [ ] 创建 `haskell/projects/dsl-transform/RULES.md`
   - [ ] 创建 `haskell/projects/dsl-transform/README.md`
   - [ ] 创建 `haskell/projects/dsl-transform/CHANGELOG.md`

---

#### Project: haskell/projects/stm-engine

**现状**: STM (Software Transactional Memory) engine

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `haskell/projects/stm-engine/AGENTS.md`
   - [ ] 创建 `haskell/projects/stm-engine/RULES.md`
   - [ ] 复核 `haskell/projects/stm-engine/README.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 复核 `haskell/projects/stm-engine/CHANGELOG.md`（文件已存在；内容与质量需按当前实现核对）

2. **丰富单元测试**
   - [ ] 为STM实现添加测试

---

### 【Go 项目】

#### Project: `go/k8s-lab`

**现状**: `go/k8s-lab` 已建成——纯标准库实现的迷你 Kubernetes 控制面
（MVCC store / apiserver / informer / workqueue / ReplicaSet controller /
kubelet 模拟器 / `cmd/demo`），全包测试覆盖率 82%~100%，`-race` 全绿。
迭代路线见 `go/k8s-lab/TODOS.md`。原 `liminalis/llm-wiki` 已迁往
[Lyra llm-wiki](https://github.com/LiShuMing/lyra/tree/main/llm-wiki/)，其质量工作应在目标仓库跟进。
另有 `cc/golab/src/leetcode/leetcode_433.go` 单文件。

**Tasks**:

1. **修正文档**
   - [x] `go/SKILL.md` 的 Project Structure 不再声称存在 `hello/`、`golab/`
   - [x] 根 `AGENTS.md` / `README.md` 的 Go 段落与实际一致
   - [x] `go/SKILL.md` / 根 `AGENTS.md` / `TASKS.md` 收录 `k8s-lab`
2. **`go/k8s-lab` 迭代**（详见其 TODOS.md，按教学价值排序）
   - [ ] Deployment 控制器（滚动更新 / revision / rollback）
   - [ ] rate-limited workqueue（指数退避）
   - [ ] GC：ownerReferences + 级联删除
   - [ ] scheduler 与多节点 kubelet（节点心跳 / 驱逐）
3. **历史迁移事项：Lyra llm-wiki 质量**（非 xlab 待办，先核对目标现状）
   - 原计划：在 CI 中执行 `go vet ./...` 与 `go test ./...`
   - 原计划：补齐 `internal/service`、`internal/repository` 的测试覆盖

---

### 【Shell 项目】

#### Project: shell/bin

**现状**: Shell utilities

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `shell/bin/AGENTS.md`
     - Bash/Zsh
     - shellcheck
   - [ ] 创建 `shell/bin/RULES.md`
     - `set -euo pipefail`
     - 引用变量
   - [ ] 复核 `shell/bin/README.md`（文件已存在；内容与质量需按当前实现核对）
   - [ ] 创建 `shell/bin/CHANGELOG.md`

2. **代码规范检查**
   - [ ] 对所有脚本运行shellcheck

---

#### Project: shell/docker

**现状**: Docker scripts

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `shell/docker/AGENTS.md`
   - [ ] 创建 `shell/docker/RULES.md`
   - [ ] 创建 `shell/docker/README.md`
   - [ ] 创建 `shell/docker/CHANGELOG.md`

---

#### Project: shell/mysql

**现状**: MySQL utilities

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `shell/mysql/AGENTS.md`
   - [ ] 创建 `shell/mysql/RULES.md`
   - [ ] 创建 `shell/mysql/README.md`
   - [ ] 创建 `shell/mysql/CHANGELOG.md`

---

## 执行优先级

> **修订于 2026-09-19。** 此前被完全遗漏的 `liminalis`（及其 `radar`、`invest`
> 业务域）、`optimizer-learning`、`python/llm_benchmark`、`rust/projects/umbra`
> 等已补入并重新排序。已迁移条目仅保留历史排序，后续工作以目标仓库为准。

### P0 - 仓库卫生（先做，影响所有后续工作）

**已完成的基线修复**（2026-09-19）：

- [x] 从 git 索引移除运行时 SQLite 数据库与已编译二进制（9 个文件，工作区文件保留）
- [x] `.gitignore` 增加对应规则，防止再次被提交（已用 `git check-ignore` 逐个验证）
- [x] 根 `README.md` / `AGENTS.md` 补全 `liminalis`、`optimizer-learning`、`llm`、`tools`
- [x] 删除 `README.md` 中不存在的 `skills/`、`_templates/` 条目
- [x] 修正 `AGENTS.md`：`mkdocs.yml` 不存在、`.secrect_key` 不存在、Go 版本（1.25.0 而非 1.21.0）与构建路径
- [x] 修正 `go/SKILL.md` 的目录结构声明
- [x] 修正本文件中指向已删除目录的任务

**待办**：

- [x] 提交上述改动（分支 `chore/repo-hygiene`，基于 `origin/main`）
- [ ] 决定 `python/projects/py-academic`（283 文件 / 63k 行 vendored fork）是否改为 submodule
- [x] 核对目录：顶层 `projects/` 不在 Git 树中；`python/projects/py-numpy-pandas` 有 8 个跟踪文件（含 notebook、数据和启动脚本），不能因无 `.py` 判为空壳。
- [ ] 评估 `cc/srlab/data/v1.jstack`（1MB，代码中无引用）是否仍需入库
- [x] 已迁移 Python 项目的旧抓取缓存与生成产物随源码目录退出当前树；不改写历史或用户运行目录。
- 历史待办已转出：平台与优化器任务分别在 [Lyra](https://github.com/LiShuMing/lyra/tree/main) 和 [Vela optimizer](https://github.com/LiShuMing/vela/tree/main/optimizer) 中核对维护，不再补建 xlab 项目任务段。

### P0 - 核心项目（优先重构）

1. **已迁出：[lyra](https://github.com/LiShuMing/lyra/tree/main)** - 原 `liminalis`；历史排序保留，当前任务见目标仓库。
2. **已迁出：[vela/optimizer](https://github.com/LiShuMing/vela/tree/main/optimizer)** - 原 `optimizer-learning`；历史排序保留，当前任务见目标仓库。
3. **cc/cclab** - C++ 核心实验室
4. **已迁出：[vela/storage](https://github.com/LiShuMing/vela/tree/main/storage)** - 原 `cc/projects/kv-store`；历史排序保留，当前任务见目标仓库。
5. **已迁出：[vela/execution](https://github.com/LiShuMing/vela/tree/main/execution)** - 原 `cc/projects/query-engine`；历史排序保留，当前任务见目标仓库。
6. **rust/rlab** - Rust 核心实验室
7. **rust/rdb** - Rust 数据库实现
8. **python/pylab** - Python 核心实验室
9. **python/llm_benchmark** - LLM 评测框架（已有 pyproject + 7 个测试）
10. **已迁出：[lyra/backend/radar](https://github.com/LiShuMing/lyra/tree/main/backend/radar)** - 原 `liminalis/backend/radar`；历史排序保留，当前任务见目标仓库。

### P1 - 重要项目（次要重构）

11. **cc/algo** - 算法实现（288 文件）
12. **cc/projects/mini-seastar** - 协程异步框架
13. **cc/projects/thread-pool** - work-stealing 线程池
14. **cc/projects/web-server** - io_uring/kqueue 双后端 Web 服务器
15. **rust/projects/umbra** - AI 记忆数据库，Arrow/Lance/DataFusion、向量索引与 gRPC；当前不是 JIT 编译流水线
16. **已迁出：[lyra/backend/invest](https://github.com/LiShuMing/lyra/tree/main/backend/invest)** - 原 `liminalis/backend/invest`；历史排序保留，当前任务见目标仓库。
17. **已迁出：[Lyra email-digest](https://github.com/LiShuMing/lyra/tree/main/modules/email-digest)** - 当前任务在目标仓库维护。
18. **已迁出：[Lyra developer-tools](https://github.com/LiShuMing/lyra/tree/main/modules/developer-tools)** - 当前任务在目标仓库维护。
19. **python/projects/py-toydb** - 玩具数据库
20. **java/xlab-itest** - Java 集成测试（4 个 Gradle 模块，10k 行）

### P2 - 其他项目（按需重构）

21. **python/projects/{py-lab, py-torch, py-cycle-lab, py-stock, py-ego}**
22. **python/ivm** - 仅 2 个文件，但与增量视图维护研究方向直接相关，值得升级为正式项目
23. 其余 C++ 项目（`cc/projects/{cpython, interpreter, io-uring, llvm-jit, learn-balel}`）
24. **haskell/projects/{sql-parser, stm-engine, dsl-transform}**、`haskell/hslab`
25. **rust/projects/{fragment-tutor, subway-game}**（保留项目；规模与实现状态须按当前源码核对）
26. **已迁出：[lyra/llm-wiki](https://github.com/LiShuMing/lyra/tree/main/llm-wiki)** - 原 `liminalis/llm-wiki`；历史排序保留，当前任务见目标仓库。
27. **shell/{bin, docker, mysql, fio}**、**llm/cuda**、**tools**
28. **docs/books** - 当前保留 4 组待审稿件、76 个文件；已迁稿件在 Cygnus 维护，不能沿用旧总量。

---

## 验收标准

每个项目重构完成后应满足：

1. ✅ AGENTS.md, RULES.md, README.md, CHANGELOG.md 已创建
2. ✅ docs/ 目录结构已创建（如适用）
3. ✅ 单元测试覆盖率达到80%+（核心代码）
4. ✅ 代码通过语言特定的格式化工具
5. ✅ 代码通过语言特定的linter检查
6. ✅ TODOS.md 已记录无用文件
7. ✅ CI/CD配置已创建（GitHub Actions）

---

## 备注

- 每个项目应在一个独立的Context中完成
- 重构时不改变现有代码功能
- 优先完成P0项目，再处理P1和P2
- 每个项目完成后创建独立的commit
