# xlab Repository Refactoring Plan

## Overview

重构多语言实验室仓库xlab，将各语言项目拆分为独立项目，每个项目使用独立Context，并创建现代LLM项目必备文件，丰富测试覆盖率，标记无用文件。

## Repository Structure Analysis

```
xlab/
├── cc/                    # C++ Projects
│   ├── cclab/            # Core C++ lab (CMake, Google Test)
│   ├── algo/             # Algorithm implementations
│   ├── ccbench/          # Benchmarks
│   ├── srlab/            # Serialization experiments
│   ├── simd/             # SIMD optimizations
│   ├── projects/         # Personal C++ projects
│   │   ├── cpython/      # Python extension
│   │   ├── interpreter/  # Language interpreter
│   │   ├── io-uring/     # io_uring experiments
│   │   ├── kv-store/     # Key-value store
│   │   ├── llvm-jit/     # LLVM JIT compiler
│   │   ├── mini-seastar/ # Async framework
│   │   ├── query-engine/ # Query engine
│   │   ├── thread-pool/  # Thread pool
│   │   └── web-server/   # Web server
│   └── tools/            # Tools
├── rust/                 # Rust Projects
│   ├── rlab/             # Core Rust lab
│   ├── rdb/              # Database implementation
│   └── projects/         # Projects
│       ├── fragment-tutor/
│       ├── subway-game/
│       └── umbra/
├── python/               # Python Projects
│   ├── pylab/            # Core Python lab
│   └── projects/         # Projects
│       ├── py-academic/  # Academic paper tools
│       ├── py-ego/       # AI assistant
│       ├── py-email/     # Email processing
│       ├── py-invest/    # Investment analysis
│       ├── py-lab/       # Lab tools
│       ├── py-paper/     # Paper management
│       ├── py-pia/       # Product info analysis
│       ├── py-radar/     # Database monitoring
│       ├── py-report/    # Report generation
│       ├── py-stock/     # Stock analysis
│       ├── py-tools/     # Tools
│       ├── py-toydb/     # Toy database
│       └── py-zotero/    # Zotero plugin
├── java/                 # Java Projects
│   ├── xlab-iceberg/     # Apache Iceberg
│   └── xlab-itest/       # Integration test projects
├── haskell/              # Haskell Projects
│   ├── hslab/            # Core Haskell lab
│   └── projects/         # Projects
│       ├── dsl-transform/    # DSL transformation
│       ├── sql-parser/       # SQL parser
│       └── stm-engine/       # STM engine
├── go/                   # Go Projects
│   └── hello/            # Hello world
└── shell/                # Shell Projects
    ├── bin/              # Utilities
    ├── docker/           # Docker scripts
    ├── fio/              # FIO tests
    └── mysql/            # MySQL utilities
```

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

#### Project: python/projects/py-radar

**现状**: Database monitoring tool with DuckDB

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `python/projects/py-radar/AGENTS.md`
   - [ ] 创建 `python/projects/py-radar/RULES.md`
   - [ ] 创建 `python/projects/py-radar/README.md`
   - [ ] 创建 `python/projects/py-radar/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 为storage/模块添加测试
   - [ ] 为sync/模块添加测试
   - [ ] 为summarizer添加测试

3. **代码规范检查**
   - [ ] 完善pyproject.toml
   - [ ] 格式化并检查代码

---

#### Project: python/projects/py-invest

**现状**: Investment analysis tool

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `python/projects/py-invest/AGENTS.md`
   - [ ] 创建 `python/projects/py-invest/RULES.md`
   - [ ] 创建 `python/projects/py-invest/README.md`
   - [ ] 创建 `python/projects/py-invest/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 为agents模块添加测试
   - [ ] 为core模块添加测试
   - [ ] 为modules添加测试

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

#### Project: python/projects/py-paper

**现状**: Paper management tool

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `python/projects/py-paper/AGENTS.md`
   - [ ] 创建 `python/projects/py-paper/RULES.md`
   - [ ] 创建 `python/projects/py-paper/README.md`
   - [ ] 创建 `python/projects/py-paper/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 为paper-agent添加测试

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

#### Project: python/projects/py-zotero

**现状**: Zotero plugin

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `python/projects/py-zotero/AGENTS.md`
   - [ ] 创建 `python/projects/py-zotero/RULES.md`
   - [ ] 创建 `python/projects/py-zotero/README.md`
   - [ ] 创建 `python/projects/py-zotero/CHANGELOG.md`

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

#### Project: go/hello

**现状**: Go hello world experiments

**Tasks**:

1. **创建项目文件**
   - [ ] 创建 `go/hello/AGENTS.md`
     - Go 1.21+
     - go modules
   - [ ] 创建 `go/hello/RULES.md`
     - gofmt
     - golangci-lint
   - [ ] 创建 `go/hello/README.md`
   - [ ] 创建 `go/hello/CHANGELOG.md`

2. **丰富单元测试**
   - [ ] 为核心功能添加测试

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

### P0 - 核心项目（优先重构）

1. **cc/cclab** - C++核心实验室
2. **cc/projects/kv-store** - KV存储实现
3. **cc/projects/query-engine** - 查询引擎
4. **rust/rlab** - Rust核心实验室
5. **rust/rdb** - Rust数据库实现
6. **python/pylab** - Python核心实验室
7. **python/projects/py-radar** - 数据库监控工具
8. **python/projects/py-toydb** - 玩具数据库

### P1 - 重要项目（次要重构）

9. **cc/algo** - 算法实现
10. **cc/projects/mini-seastar** - 异步框架
11. **cc/projects/thread-pool** - 线程池
12. **cc/projects/web-server** - Web服务器
13. **python/projects/py-invest** - 投资分析
14. **python/projects/py-email** - 邮件处理
15. **java/xlab-itest** - Java集成测试

### P2 - 其他项目（按需重构）

16. 所有其他C++项目
17. 所有其他Python项目
18. 所有Rust项目
19. 所有Haskell项目
20. Go和Shell项目

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
