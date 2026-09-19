# xlab Repository Refactoring Plan

## Document Role

This file is the active backlog for repository cleanup, restructuring, and
quality work. Keep task lists, migration notes, and refactoring plans here.
Stable project navigation belongs in `README.md`; coding-agent rules belong in
`AGENTS.md`; knowledge capture workflows belong in `SKILL.md`.

## Overview

重构多语言实验室仓库xlab，将各语言项目拆分为独立项目，每个项目使用独立Context，并创建现代LLM项目必备文件，丰富测试覆盖率，标记无用文件。

## Repository Structure Analysis

> **Snapshot date**: 2026-09-19. Verified against the working tree on branch
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
│       ├── py-cli/       # CLI toolkit
│       ├── py-cycle-lab/ # Long-cycle investment compass
│       ├── py-ego/       # StarRocks MV monitor + LLM companion
│       ├── py-email/     # Gmail newsletter digest
│       ├── py-lab/       # Streamlit/LangChain AI platform
│       ├── py-learn/     # Telegram daily-learning agent
│       ├── py-optimizer1/# Optimizer analysis system
│       ├── py-optimizer2/# Multi-engine optimizer analyzer
│       ├── py-pia/       # Product intelligence agent
│       ├── py-report/    # LLM API deep-research pipeline
│       ├── py-stock/     # Stock price database
│       ├── py-tools/     # Misc tools
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
| `projects/llm-wiki` | Moved to `liminalis/llm-wiki`. |
| `go/hello` | Never materialized; the first `go/` project is `go/k8s-lab/`. |
| `skills/`, `_templates/` | Do not exist at repo root; skills live in `docs/skills/` and `.claude/skills/`. |

Do not create tasks against the paths above. Work belongs in the successor
location.

### ⚠️ Branch divergence caveat

`main` contains only **3 commits** (`4176047`, `4a022f3`, `357df48`), while
`dev1` holds **169 commits that are not on `main`**. The two lines have
different project inventories.

This backlog describes the **working tree as checked out from `main`**. Before
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
   - [ ] 创建 `cc/cclab/AGENTS.md`
     - 项目概述：C++实验室核心代码
     - 构建命令：`./build.sh [DEBUG|RELEASE|ASAN|LSAN]`
     - 测试命令：`cd build_ASAN && ctest`
     - 代码风格：.clang-format, .clang-tidy
   - [ ] 创建 `cc/cclab/RULES.md`
     - C++20/23标准
     - Google Test测试框架
     - Sanitizer使用（ASAN, LSAN, UBSAN）
   - [ ] 创建 `cc/cclab/CHANGELOG.md`
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
   - [ ] 创建 `cc/algo/AGENTS.md`
     - LeetCode解决方案集合
     - 构建系统：Makefile
     - 运行命令：`make leetcode_<number>`
   - [ ] 创建 `cc/algo/RULES.md`
     - 每个算法文件头部注释：问题描述、复杂度分析
   - [ ] 创建 `cc/algo/README.md`
     - 按类别组织的算法列表
   - [ ] 创建 `cc/algo/CHANGELOG.md`

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
   - [ ] 创建 `cc/srlab/README.md`
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
   - [ ] 创建 `cc/projects/cpython/README.md`
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
   - [ ] 创建 `cc/projects/interpreter/README.md`
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
   - [ ] 创建 `cc/projects/io-uring/README.md`
   - [ ] 创建 `cc/projects/io-uring/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 添加io_uring操作测试
   - [ ] 添加性能基准测试

---

#### Project: cc/projects/kv-store

**现状**: Key-value store implementation

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `cc/projects/kv-store/AGENTS.md`
   - [ ] 创建 `cc/projects/kv-store/RULES.md`
   - [ ] 创建 `cc/projects/kv-store/README.md`
   - [ ] 创建 `cc/projects/kv-store/CHANGELOG.md`
   - [ ] 创建 `cc/projects/kv-store/docs/architecture/`

2. **丰富单元测试**
   - [ ] 为存储引擎添加测试
   - [ ] 为网络层添加测试
   - [ ] 为并发操作添加测试
   - [ ] 为持久化添加测试

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
   - [ ] 创建 `cc/projects/mini-seastar/AGENTS.md`
   - [ ] 创建 `cc/projects/mini-seastar/RULES.md`
   - [ ] 创建 `cc/projects/mini-seastar/README.md`
   - [ ] 创建 `cc/projects/mini-seastar/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 为future/promise添加测试
   - [ ] 为scheduler添加测试
   - [ ] 为网络层添加测试

---

#### Project: cc/projects/query-engine

**现状**: Query engine implementation

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `cc/projects/query-engine/AGENTS.md`
   - [ ] 创建 `cc/projects/query-engine/RULES.md`
   - [ ] 创建 `cc/projects/query-engine/README.md`
   - [ ] 创建 `cc/projects/query-engine/CHANGELOG.md`
   - [ ] 创建 `cc/projects/query-engine/docs/architecture/`

2. **丰富单元测试**
   - [ ] 为parser添加测试
   - [ ] 为planner添加测试
   - [ ] 为executor添加测试
   - [ ] 为storage层添加测试

---

#### Project: cc/projects/thread-pool

**现状**: Thread pool implementation

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `cc/projects/thread-pool/AGENTS.md`
   - [ ] 创建 `cc/projects/thread-pool/RULES.md`
   - [ ] 创建 `cc/projects/thread-pool/README.md`
   - [ ] 创建 `cc/projects/thread-pool/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 为线程池添加并发测试
   - [ ] 添加性能基准测试

---

#### Project: cc/projects/web-server

**现状**: Web server implementation

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `cc/projects/web-server/AGENTS.md`
   - [ ] 创建 `cc/projects/web-server/RULES.md`
   - [ ] 创建 `cc/projects/web-server/README.md`
   - [ ] 创建 `cc/projects/web-server/CHANGELOG.md`

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
   - [ ] 创建 `rust/rlab/AGENTS.md`
     - Cargo workspace结构
     - 子crate: bloom_filter, leetcode, lockfree-queue, rlab-tools, thread-pool
   - [ ] 创建 `rust/rlab/RULES.md`
     - Rust 2021 edition
     - cargo fmt, cargo clippy
     - Error handling with Result
   - [ ] 创建 `rust/rlab/README.md`
   - [ ] 创建 `rust/rlab/CHANGELOG.md`

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
   - [ ] 创建 `rust/rdb/AGENTS.md`
   - [ ] 创建 `rust/rdb/RULES.md`
   - [ ] 创建 `rust/rdb/README.md`
   - [ ] 创建 `rust/rdb/CHANGELOG.md`
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
   - [ ] 创建 `rust/projects/umbra/README.md`
   - [ ] 创建 `rust/projects/umbra/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 分析并补充测试

---

### 【Python 项目】

#### Project: python/pylab

**现状**: Core Python lab with pytest

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `python/pylab/AGENTS.md`
     - Python 3.13+
     - pytest测试框架
     - 依赖管理：requirements.txt
   - [ ] 创建 `python/pylab/RULES.md`
     - PEP 8规范
     - Type hints要求
     - black, isort, ruff配置
   - [ ] 创建 `python/pylab/README.md`
   - [ ] 创建 `python/pylab/CHANGELOG.md`

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

#### Project: liminalis/backend/radar

**现状**: Liminalis 的情报雷达业务域（45 个跟踪文件 / 39 个 `.py`），已有测试
`liminalis/tests/test_radar.py`、`test_radar_extractor.py`、
`liminalis/backend/tests/radar/`。

**Tasks**:

1. **补齐测试**
   - [ ] 为 `backend/radar/ranker.py`、`summarizer.py`、`seen_tracker.py` 添加测试
   - [ ] 为 `backend/radar/sync/` 添加测试
2. **遵循架构约束**
   - [ ] 确认改动通过 `tests/test_architecture.py`（`_shared` 边界与事务规则守护）

---

#### Project: liminalis/backend/invest

**现状**: Liminalis 的投资分析业务域（含 `agents/`、`core/`、`modules/`、
`scheduler/`、`notifier/`、`web/`、`diff/`），已有测试
`liminalis/tests/test_invest.py`、`liminalis/backend/invest/tests/`。

**Tasks**:

1. **补齐测试**
   - [ ] 为 `backend/invest/agents/` 添加测试
   - [ ] 为 `backend/invest/core/` 添加测试
   - [ ] 为 `backend/invest/modules/data_collector`、`report_generator` 添加测试
2. **遵循架构约束**
   - [ ] 确认改动通过 `tests/test_architecture.py`

---

#### Project: python/projects/py-email

**现状**: Email processing tool

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `python/projects/py-email/AGENTS.md`
   - [ ] 创建 `python/projects/py-email/RULES.md`
   - [ ] 创建 `python/projects/py-email/README.md`
   - [ ] 创建 `python/projects/py-email/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 为src/my_email添加测试

---

#### Project: python/projects/py-toydb

**现状**: Toy database implementation

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `python/projects/py-toydb/AGENTS.md`
   - [ ] 创建 `python/projects/py-toydb/RULES.md`
   - [ ] 创建 `python/projects/py-toydb/README.md`
   - [ ] 创建 `python/projects/py-toydb/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 为toydb模块添加测试

---

#### Project: python/projects/py-ego

**现状**: AI assistant project

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `python/projects/py-ego/AGENTS.md`
   - [ ] 创建 `python/projects/py-ego/RULES.md`
   - [ ] 创建 `python/projects/py-ego/README.md`
   - [ ] 创建 `python/projects/py-ego/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 为核心模块添加测试

---

#### Project: python/projects/py-academic

**现状**: Academic paper tools

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `python/projects/py-academic/AGENTS.md`
   - [ ] 创建 `python/projects/py-academic/RULES.md`
   - [ ] 创建 `python/projects/py-academic/README.md`
   - [ ] 创建 `python/projects/py-academic/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 为crazy_functions模块添加测试

---

#### Project: python/projects/py-pia

**现状**: Product information analysis

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `python/projects/py-pia/AGENTS.md`
   - [ ] 创建 `python/projects/py-pia/RULES.md`
   - [ ] 创建 `python/projects/py-pia/README.md`
   - [ ] 创建 `python/projects/py-pia/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 为src/pia添加测试

---

#### Project: python/projects/py-report

**现状**: Report generation tool

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `python/projects/py-report/AGENTS.md`
   - [ ] 创建 `python/projects/py-report/RULES.md`
   - [ ] 创建 `python/projects/py-report/README.md`
   - [ ] 创建 `python/projects/py-report/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 为src/agent添加测试

---

#### Project: python/projects/py-lab

**现状**: Python lab tools

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `python/projects/py-lab/AGENTS.md`
   - [ ] 创建 `python/projects/py-lab/RULES.md`
   - [ ] 创建 `python/projects/py-lab/README.md`
   - [ ] 创建 `python/projects/py-lab/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 为核心模块添加测试

---

#### Project: python/projects/py-stock

**现状**: Stock analysis tool

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `python/projects/py-stock/AGENTS.md`
   - [ ] 创建 `python/projects/py-stock/RULES.md`
   - [ ] 创建 `python/projects/py-stock/README.md`
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
   - [ ] 创建 `java/xlab-iceberg/README.md`
   - [ ] 创建 `java/xlab-iceberg/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 为核心功能添加JUnit测试

---

#### Project: java/xlab-itest

**现状**: Integration test projects (multi-module)

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `java/xlab-itest/AGENTS.md`
     - 多模块项目结构
     - 子项目: benchmark, framework, groovy, interview, itest, jlib, scala, spark, spring
   - [ ] 创建 `java/xlab-itest/RULES.md`
   - [ ] 创建 `java/xlab-itest/README.md`
   - [ ] 创建 `java/xlab-itest/CHANGELOG.md`

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
   - [ ] 创建 `haskell/projects/sql-parser/README.md`
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
   - [ ] 创建 `haskell/projects/stm-engine/README.md`
   - [ ] 创建 `haskell/projects/stm-engine/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 为STM实现添加测试

---

### 【Go 项目】

#### Project: `go/k8s-lab` 与 `liminalis/llm-wiki`

**现状**: `go/k8s-lab` 已建成——纯标准库实现的迷你 Kubernetes 控制面
（MVCC store / apiserver / informer / workqueue / ReplicaSet controller /
kubelet 模拟器 / `cmd/demo`），全包测试覆盖率 82%~100%，`-race` 全绿。
迭代路线见 `go/k8s-lab/TODOS.md`。另一个 Go 模块是 `liminalis/llm-wiki`
（`go 1.25.0`，约 7,154 行，已有 8 个 `_test.go`）。
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
3. **`liminalis/llm-wiki` 质量**
   - [ ] 在 CI 中执行 `go vet ./...` 与 `go test ./...`
   - [ ] 补齐 `internal/service`、`internal/repository` 的测试覆盖

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
   - [ ] 创建 `shell/bin/README.md`
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
> 等已补入并重新排序。

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
- [ ] 清理空壳目录：顶层 `projects/`（0 文件）、`python/projects/py-numpy-pandas`（无 `.py`）
- [ ] 评估 `cc/srlab/data/v1.jstack`（1MB，代码中无引用）是否仍需入库
- [ ] 评估 `python/projects/py-pia/data/{raw,normalized}`（2.5MB 抓取缓存）是否应入库
- [ ] 为 `liminalis` 与 `optimizer-learning` 补写本文件中的 `#### Project:` 任务段（当前缺失）

### P0 - 核心项目（优先重构）

1. **liminalis** - 统一平台（FastAPI + React + Go）。已有架构守护测试，优先在域内深化
2. **optimizer-learning** - Volcano vs Cascades 对比工具。**缺 `tests/`（仅空 `__init__.py`）与 `pyproject.toml`，且依赖 `sqlglot` 未声明**
3. **cc/cclab** - C++ 核心实验室
4. **cc/projects/kv-store** - KV 存储实现（最接近可独立开源）
5. **cc/projects/query-engine** - 向量化查询引擎（**无 tests 目录**）
6. **rust/rlab** - Rust 核心实验室
7. **rust/rdb** - Rust 数据库实现
8. **python/pylab** - Python 核心实验室
9. **python/llm_benchmark** - LLM 评测框架（已有 pyproject + 7 个测试）
10. **liminalis/backend/radar** - 情报雷达域

### P1 - 重要项目（次要重构）

11. **cc/algo** - 算法实现（288 文件）
12. **cc/projects/mini-seastar** - 协程异步框架
13. **cc/projects/thread-pool** - work-stealing 线程池
14. **cc/projects/web-server** - io_uring/kqueue 双后端 Web 服务器
15. **rust/projects/umbra** - JIT 编译流水线（可与 query-engine、optimizer-learning 串成 OLAP 主线）
16. **liminalis/backend/invest** - 投资分析域
17. **python/projects/py-email** - Gmail 摘要工具
18. **python/projects/py-cli** - 工程化最规范的 Python 子项目
19. **python/projects/py-toydb** - 玩具数据库
20. **java/xlab-itest** - Java 集成测试（4 个 Gradle 模块，10k 行）

### P2 - 其他项目（按需重构）

21. **python/projects/{py-pia, py-lab, py-optimizer1, py-optimizer2, py-torch, py-report, py-cycle-lab, py-learn, py-stock, py-ego, py-tools}**
22. **python/ivm** - 仅 2 个文件，但与增量视图维护研究方向直接相关，值得升级为正式项目
23. 其余 C++ 项目（`cc/projects/{cpython, interpreter, io-uring, llvm-jit, learn-balel}`）
24. **haskell/projects/{sql-parser, stm-engine, dsl-transform}**、`haskell/hslab`
25. **rust/projects/{fragment-tutor, subway-game}**（subway-game 仅 26 行）
26. **liminalis/llm-wiki** - Go 模块
27. **shell/{bin, docker, mysql, fio}**、**llm/cuda**、**tools**
28. **docs/books** - 12 本书约 9.5 万行 Markdown，独立知识线

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
