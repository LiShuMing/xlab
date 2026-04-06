# Optimizer Expert Analyzer Agent — 方案设计文档

> 版本：v2.0  
> 定位：基于 Harness 功能循环构建的查询引擎 Optimizer 深度分析与多引擎对比系统  
> 观测引擎：ClickHouse · StarRocks · Doris · GPDB(Orca) · Apache Calcite · CockroachDB · PostgreSQL · Columbia

---

## 目录

1. [背景与目标](#1-背景与目标)
2. [观测引擎全景](#2-观测引擎全景)
3. [整体架构](#3-整体架构)
4. [核心设计原则](#4-核心设计原则)
5. [第一层：引擎配置（Engine Config）](#5-第一层引擎配置)
6. [第二层：Task 1 — 枚举与 Prompt 生成](#6-第二层task-1--枚举与-prompt-生成)
7. [第三层：Task 2 — 逐规则深度分析](#7-第三层task-2--逐规则深度分析)
8. [第四层：Schema-locked 结构化存储](#8-第四层schema-locked-结构化存储)
9. [第五层：Task 3 — 多引擎对比报告](#9-第五层task-3--多引擎对比报告)
10. [输出目录结构](#10-输出目录结构)
11. [Prompt 模板设计](#11-prompt-模板设计)
12. [可靠性保障机制](#12-可靠性保障机制)
13. [执行流程与断点续跑](#13-执行流程与断点续跑)
14. [实现优先级建议](#14-实现优先级建议)
15. [附录 A：关系代数符号约定](#15-附录a关系代数符号约定)
16. [附录 B：各引擎 File Scanner 适配说明](#16-附录b各引擎-file-scanner-适配说明)

---

## 1. 背景与目标

### 1.1 问题背景

查询优化器（Query Optimizer）是 OLAP/OLTP 数据库的核心组件，其质量直接决定查询性能的上限。当前工程实践中存在以下痛点：

- **优化器功能难以系统化梳理**：Rules 数量庞大（通常 100-300+），缺乏统一的分析框架；
- **跨引擎对比没有标准化方法**：不同引擎对同一优化逻辑有不同的实现和命名，无法直接比较；
- **优化器功能对齐评估缺乏工具支撑**：判断"某引擎是否缺少某类优化"依赖人工经验，耗时且不系统；
- **引擎技术谱系复杂**：8 个观测引擎横跨 C++/Java/Go/C 四种语言，Volcano/Cascades/Optgen/Path-based/自研 五类框架，File Scanner 无法一刀切；
- **源码阅读成本极高**：即使是领域专家，系统性分析一个引擎的全部优化规则也需要数周时间。

### 1.2 目标

构建一个基于 Harness 循环的 Agent 系统，实现：

| 目标 | 具体指标 |
|------|---------|
| **Task 1** | 自动枚举指定引擎的全部 RBO/CBO/Scalar/Post-Opt Rules 及 Properties，生成带优先级的分析任务队列 |
| **Task 2** | 对每条 Rule 生成结构化深度分析，包括关系代数形式表达、触发条件、正确性条件、性能意义 |
| **Task 3** | 基于统一 schema 对 8 个引擎进行多维度对比，输出功能对齐矩阵与差异报告 |
| **可靠性** | 支持断点续跑、低置信度自动标记、结果可人工审核 |
| **可扩展性** | 新增一个引擎只需增加配置文件，无需修改框架代码 |

### 1.3 分析维度覆盖

```
Optimizer 分析维度
├── 优化器框架与生命周期
│   ├── 整体架构（Cascades / Volcano / Optgen / Path-based / 自研）
│   ├── Plan 表示（LogicalPlan → PhysicalPlan 转换路径）
│   └── 阶段划分（Rewrite → Explore → Implement → Enforce → PostOpt）
├── 规则体系
│   ├── RBO Rules（逻辑变换规则）
│   ├── CBO Rules（物理实现规则 + 代价模型）
│   ├── Scalar Rules（表达式层重写规则）
│   └── Post-Opt Rules（物理计划后处理规则）
├── Properties & Traits（Enforcer 机制）
├── 统计信息体系
│   ├── 采集机制与存储
│   ├── 调度策略
│   └── 代价估算使用方式
└── 其他功能
    ├── 可观测性（EXPLAIN、Trace、Profile）
    ├── 可解释性（Plan hint、Rule 开关）
    └── 可扩展性（Rule 注册机制、插件接口）
```

---

## 2. 观测引擎全景

8 个引擎在语言、框架、优化器风格上差异显著，这直接决定了 File Scanner 的策略和 Prompt 的关注侧重。

### 2.1 引擎技术全景表

| 引擎 | 语言 | 优化器框架 | Rule 表达方式 | 优化器根目录 | 规模预估 |
|------|------|---------|------------|------------|--------|
| **StarRocks** | C++ | Cascades | C++ 类继承（TransformationRule / ImplementationRule） | `be/src/sql/optimizer/` | ~150 条 |
| **Apache Doris** | Java（FE） | Cascades（Nereids） | Java 类继承（Rule 抽象基类） | `fe/src/main/java/org/apache/doris/nereids/` | ~200 条 |
| **ClickHouse** | C++ | 自研多 Pass QueryPlan | C++ 函数（tryXxx 命名约定） | `src/Processors/QueryPlan/Optimizations/` | ~46 个优化函数 |
| **GPDB (Orca)** | C++ | Cascades（独立 Orca 库） | C++ 类（CXformXxx 命名） | `src/backend/gporca/libgpopt/` | ~178 个 Xform |
| **Apache Calcite** | Java | Volcano + HepPlanner 双引擎 | Java 类（继承 RelRule / RelOptRule） | `core/src/main/java/org/apache/calcite/rel/rules/` | ~191 条 |
| **CockroachDB** | Go + Optgen DSL | Cascades（自研 Memo） | Optgen DSL（.opt 文件）→ 生成 Go | `pkg/sql/opt/norm/` + `pkg/sql/opt/xform/` | ~260 条 |
| **PostgreSQL** | C | 自研 Path-based | C 函数（路径枚举 + 代价比较，无类） | `src/backend/optimizer/` | ~80 个函数单元 |
| **Columbia** | C++ | Columbia（学术 Cascades 变体） | C++ 类（Rule 抽象基类） | `src/` | ~58 条 |

### 2.2 各引擎优化器架构速览

#### StarRocks — Cascades 实现

完整的 Cascades 实现，分为逻辑重写（RBO Rules）和物理实现（CBO Rules）两阶段。逻辑计划表示为 `OptExpression` 树，Property 体系完整（`DistributionProperty`、`OrderProperty`、`CTEProperty`），Post-Opt 阶段做物理计划调整。统计信息存储于 FE 内存，支持直方图和 NDV。

#### Apache Doris — Nereids（Cascades 变体）

Nereids 是对老优化器的完整重写，采用 Cascades 框架，用 Java 实现（FE 部分）。规则分为 Rewrite Rules（逻辑等价）和 Exploration Rules（物理实现）。**注意**：Nereids 的源码在 FE（Java）而非 BE（C++），与 StarRocks 语言层有显著差异；同时 Doris 支持 HBO（Histogram-Based Optimization），是区别于其他引擎的特有能力。

#### ClickHouse — 自研多 Pass QueryPlan 优化器

不是 Cascades 框架，优化分三个 Pass：

- **Pass 1**（`optimizeTreeFirstPass`）：局部幂等操作，约 25 个 `tryXxx` 函数（谓词下推、聚合合并、冗余列裁剪等）；
- **Pass 2**（`optimizeTreeSecondPass`）：Read-in-order、谓词挂载到 PK 扫描；
- **Pass 3**（`addStepsToBuildSets`）：Subquery 物化 Sets。

ClickHouse 没有传统意义上的 CBO 规则注册机制，代价感知逻辑内嵌于各 Pass 函数中。分析粒度以"优化函数"而非"优化类"为单位，规则注册通过 `Optimizations.cpp` 中的静态数组维护。

#### GPDB (Orca) — 独立 Cascades 库

Orca 是独立的 C++ 优化器库，通过 DXL（Data eXchange Language，XML 格式）与 GPDB 主体交互。Rules 命名为 `CXformXxx`，分布在 `libgpopt/xforms/` 下，约 150 个。其 Property 系统极为完整（`CDistributionSpec`、`COrderSpec`、`CRewindabilitySpec`、`CPartitionPropagationSpec` 等），是分析分布式 CBO 的最佳样本。

#### Apache Calcite — 双引擎（HepPlanner + VolcanoPlanner）

独立的 SQL 优化器框架，被 Flink、Presto、Drill 等大量系统使用。其独特性在于双引擎并行：

- **HepPlanner**（启发式）：执行 CoreRules，固定顺序 top-down 遍历；
- **VolcanoPlanner**（CBO）：执行 EnumerableRules，动态规划探索等价类。

规则用 `RelRule`（新式）或 `RelOptRule`（旧式）Java 类定义，通过 `operand()` 模式匹配，`onMatch()` 执行变换。由于 Calcite 是框架而非完整数据库，统计信息和代价模型可由集成方自定义，分析侧重规则本身和 Trait 体系。

#### CockroachDB — Optgen DSL + Cascades Memo

自研了 Optgen 领域特定语言（`.opt` 文件），用 DSL 描述规则的匹配和替换模式，由 `optgen` 工具生成 Go 代码。规则分布在：

- `pkg/sql/opt/norm/*.opt`：Normalization 规则（~120 条，等价于 RBO）；
- `pkg/sql/opt/xform/*.opt`：Exploration 规则（~80 条，等价于 CBO）。

File Scanner 需要读取 `.opt` DSL 文件而非生成的 Go 代码，DSL 语法简洁，可读性高，可直接作为 prompt 输入。

#### PostgreSQL — Path-based 自研优化器

独特的 Path-based 系统：对每个 `RelOptInfo`（关系等价类）枚举多条 Path，通过 `cost_xxx()` 函数计算路径代价，保留代价最小的路径。没有"规则"的明确注册机制，优化逻辑分散在多个 `.c` 文件中，分析粒度以"优化函数/模块"为单位，而非"Rule 类"。

#### Columbia — 学术参考实现

Columbia University 提出的 Cascades 变体，是很多现代优化器（包括 SQL Server Cascades 实现）的理论基础。Rules 约 40 条，代码精简，适合作为 Cascades 语义的标准参照。

### 2.3 对比维度覆盖矩阵（预期）

| 对比维度 | SR | Doris | CH | GPDB | Calcite | CRDB | PG | Columbia |
|---------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| 谓词下推 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Join 重排序 | ✓ | ✓ | △ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 子查询解嵌套 | ✓ | ✓ | △ | ✓ | ✓ | ✓ | ✓ | - |
| 聚合下推 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | - |
| CTE 优化 | ✓ | ✓ | △ | △ | ✓ | ✓ | ✓ | - |
| 物化视图改写 | ✓ | ✓ | ✓ | - | ✓ | - | ✓ | - |
| 分区裁剪 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | - |
| 分布式 Property | ✓ | ✓ | - | ✓ | - | ✓ | - | - |
| Scalar 表达式重写 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | △ |
| 统计信息自动采集 | ✓ | ✓ | - | ✓ | - | ✓ | ✓ | - |
| 直方图支持 | ✓ | ✓ | - | ✓ | - | ✓ | ✓ | - |
| EXPLAIN 支持 | ✓ | ✓ | ✓ | ✓ | △ | ✓ | ✓ | - |
| Rule 开关/Hint | ✓ | ✓ | △ | ✓ | ✓ | ✓ | ✓ | - |

> ✓ 完整支持 · △ 部分支持 · - 不支持或不适用

---

## 3. 整体架构

### 3.1 架构概览

```
┌───────────────────────────────────────────────────────────────────┐
│                          INPUT LAYER                               │
│   engines/*.yaml  │  各引擎源码目录  │  target_engines 列表        │
└──────────────────────────────┬────────────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────────┐
│               TASK 1 — ENUMERATION（纯静态分析，无 LLM）           │
│   Language-aware File Scanner                                      │
│     ├── C++ Scanner    StarRocks / Doris BE / ClickHouse / GPDB / Columbia
│     ├── Java Scanner   Doris FE（Nereids） / Apache Calcite         │
│     ├── Go Scanner     CockroachDB（优先读 .opt DSL）               │
│     └── C Scanner      PostgreSQL                                   │
│   → Rule Enumerator → Prompt Factory → task_queue.json             │
└──────────────────────────────┬────────────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────────┐
│               TASK 2 — ANALYSIS（Harness Loop，逐 Rule LLM 分析）  │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│   │   RBO    │ │   CBO    │ │  Scalar  │ │ Post-Opt │ │ Props  │ │
│   │ Analyzer │ │ Analyzer │ │ Analyzer │ │ Analyzer │ │Analyzer│ │
│   └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────┘ │
│   ┌──────────────────────────────────────────────────────────────┐ │
│   │                Statistics Analyzer（整体分析，每引擎 1 次）    │ │
│   └──────────────────────────────────────────────────────────────┘ │
│   每条 Rule 独立执行，结果落盘 JSONL，confidence 自评，支持断点续跑  │
└──────────────────────────────┬────────────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────────┐
│               SCHEMA-LOCKED JSON STORE                             │
│   engine_id · category · rule_name · ra_form                       │
│   canonical_name · logical_category · optimizer_framework          │
└──────────────────────────────┬────────────────────────────────────┘
                               │
                     ┌─────────┴──────────┐
                     ▼                    │
       Task 2.5: Canonical Name Normalizer│
       （跨引擎对齐，LLM 归一化，~20 次调用）
                     │                    │
                     └─────────┬──────────┘
                               ▼
┌───────────────────────────────────────────────────────────────────┐
│               TASK 3 — COMPARISON                                  │
│   Diff Engine → Scoring Engine → LLM 深度对比 → Markdown Writer    │
└───────────────────────────────────────────────────────────────────┘
```

### 3.2 数据流

```
各引擎源码
  │
  ├─[Language-aware File Scanner]──→ {engine}_file_index.json
  ├─[Rule Enumerator]──────────────→ 规则清单 + 工作量估算
  ├─[Prompt Factory]───────────────→ task_queue.json
  ├─[Analysis Harness]─────────────→ data/{engine}/xxx_rules.jsonl
  ├─[Canonical Normalizer]─────────→ canonical_name_map.json
  ├─[Diff Engine]──────────────────→ diff_matrix.json
  └─[MD Writer]────────────────────→ output/ 报告目录
```

---

## 4. 核心设计原则

### 4.1 分析粒度：以单条 Rule 为单位

8 个引擎合计约 1200+ Rules，Harness 循环将每条 Rule 作为独立分析单元，每次调用只处理一条规则，专注、精准、可独立验证，中断后可从任意位置恢复。

### 4.2 语言感知的 File Scanner

| 语言/范式 | 典型引擎 | 提取策略 |
|---------|--------|--------|
| C++ 类继承 | StarRocks、Doris BE、GPDB、Columbia | 正则匹配类声明 + 大括号深度计数提取方法体 |
| C++ 函数式 | ClickHouse | 匹配 `tryXxx` 函数，读取 Optimizations.cpp 注册数组 |
| Java 类继承 | Calcite、Doris FE | JavaParser AST 精确提取 `onMatch()` / `apply()` |
| Optgen DSL | CockroachDB | 专用轻量解析器，提取 `[RuleName]` 规则块 |
| C 函数 | PostgreSQL | 按 key_files 清单逐文件提取函数体 |

### 4.3 Schema 先行：统一输出格式是对比的前提

- **关系代数符号约定**：所有 prompt 注入统一符号表（见附录 A），防止不同调用使用不同记法；
- **`canonical_name` 字段**：将引擎特定命名归一化为跨引擎可对比的标准名称；
- **`logical_category` 字段**：将规则分配到 22 个标准优化类别；
- **`optimizer_framework` 字段**：记录规则所属框架类型，对比报告中自动注明差异背景。

### 4.4 任务状态持久化，支持断点续跑

每条 task 的状态维护在 `task_queue.json`：`pending → in_progress → done | failed`。支持 `--resume`，中断后自动跳过 `done` 任务。

### 4.5 可信度机制：不信任单次 LLM 输出

- 要求 Claude 输出 `confidence: 0.0-1.0` 自评分；
- `confidence < 0.7` 自动进入 `needs_review` 队列；
- RA 表达式通过符号解析器做格式校验；
- 支持 `--force-rerun {task_id}` 对指定规则强制重分析。

---

## 5. 第一层：引擎配置

### 5.1 通用配置文件结构

```yaml
# engines/{engine_id}.yaml

engine_id: starrocks
display_name: "StarRocks"
version: "3.x"
language: cpp                 # cpp | java | go | c
optimizer_framework: cascades # cascades | volcano | path_based | optgen | custom
optimizer_root: "./be/src/sql/optimizer"

patterns:
  rbo_rules:
    glob: "..."
    class_pattern: "..."        # C++/Java 类继承引擎
    func_pattern: "..."         # ClickHouse / PostgreSQL 函数式
    key_methods: [...]
    dsl_file_pattern: "..."     # CockroachDB Optgen DSL

  cbo_rules: { ... }
  scalar_rules: { ... }
  post_opt: { ... }
  properties: { ... }
  statistics:
    glob: "..."
    entry_points: [...]

lifecycle_entry:
  optimizer_class: "..."
  entry_method: "..."
  plan_root_class: "..."

rule_registry:
  file: "..."
  enum_name: "..."
  list_func: "..."

scanner_hints:
  skip_generated_files: false
  prefer_dsl_over_generated: false
  max_tokens_per_snippet: 2000
```

### 5.2 全部 8 个引擎配置

#### StarRocks

```yaml
engine_id: starrocks
display_name: "StarRocks"
version: "3.x"
language: cpp
optimizer_framework: cascades
optimizer_root: "./be/src/sql/optimizer"

patterns:
  rbo_rules:
    glob: "**/transform/rule_*.cpp"
    class_pattern: "class Rule\\w+\\s*:\\s*public TransformationRule"
    key_methods: ["transform", "check", "pattern"]
  cbo_rules:
    glob: "**/implement/rule_*.cpp"
    class_pattern: "class Rule\\w+\\s*:\\s*public ImplementationRule"
    key_methods: ["implement", "check"]
  scalar_rules:
    glob: "**/rewrite/*.cpp"
    class_pattern: "class \\w+Rewriter"
    key_methods: ["visitCall", "rewrite", "apply"]
  post_opt:
    glob: "**/physical_rewrite/*.cpp"
    class_pattern: "class \\w+Rule\\s*:\\s*public PhysicalRule"
    key_methods: ["rewrite", "apply"]
  properties:
    glob: "**/property/*.h"
    class_pattern: "class \\w+Property"
    key_methods: ["enforce", "satisfy", "output"]
  statistics:
    glob: "**/statistics/**/*.{cpp,h}"
    entry_points: ["StatisticsCollector", "ColumnStatistics", "CostEstimator"]

lifecycle_entry:
  optimizer_class: "OptimizerTask"
  entry_method: "optimize"
  plan_root_class: "OptExpression"

rule_registry:
  file: "optimizer/rule/RuleType.h"
  enum_name: "RuleType"
```

#### Apache Doris（Nereids）

```yaml
engine_id: doris
display_name: "Apache Doris (Nereids)"
version: "2.x"
language: java
optimizer_framework: cascades
optimizer_root: "./fe/src/main/java/org/apache/doris/nereids"

patterns:
  rbo_rules:
    glob: "**/rules/rewrite/**/*.java"
    class_pattern: "class \\w+Rule\\s+extends\\s+RewriteRuleFactory"
    key_methods: ["buildRules", "build"]
  cbo_rules:
    glob: "**/rules/implementation/**/*.java"
    class_pattern: "class \\w+Rule\\s+extends\\s+ImplementationRuleFactory"
    key_methods: ["buildRules", "build"]
  scalar_rules:
    glob: "**/rules/expression/**/*.java"
    class_pattern: "class \\w+\\s+extends\\s+ExpressionPatternRule"
    key_methods: ["matchThen"]
  post_opt:
    glob: "**/rules/mv/**/*.java"
    class_pattern: "class \\w+"
    key_methods: ["apply", "check"]
  properties:
    glob: "**/properties/**/*.java"
    class_pattern: "class \\w+Property"
    key_methods: ["satisfy", "output", "computeFromChildren"]
  statistics:
    glob: "**/stats/**/*.java"
    entry_points: ["StatsDeriveResult", "StatsCalculator", "HboStatsProvider"]

rule_registry:
  file: "nereids/rules/RuleType.java"
  enum_name: "RuleType"
  list_func: "buildRules"
```

#### ClickHouse

```yaml
engine_id: clickhouse
display_name: "ClickHouse"
version: "24.x"
language: cpp
optimizer_framework: custom
optimizer_root: "./src/Processors/QueryPlan/Optimizations"

patterns:
  rbo_rules:
    glob: "**/Optimizations/*.cpp"
    # ClickHouse 无 Rule 类，以优化函数为粒度
    func_pattern: "^(size_t|bool)\\s+try[A-Z]\\w+\\(QueryPlan::Node"
    key_methods: []
  cbo_rules:
    glob: "**/Optimizations/optimizeTreeSecondPass.cpp"
    func_pattern: "void\\s+optimizeTree\\w+"
    key_methods: []
  scalar_rules:
    glob: "**/Interpreters/ActionsDAG.cpp"
    func_pattern: "void\\s+ActionsDAG::\\w+"
    key_methods: []
  post_opt:
    glob: "**/QueryPlan/QueryPlan.cpp"
    func_pattern: "void\\s+QueryPlan::optimize"
    key_methods: []
  properties:
    glob: "**/Processors/QueryPlan/IQueryPlanStep.h"
    class_pattern: "struct DataStream"
    key_methods: []
  statistics:
    glob: "**/Interpreters/DatabaseCatalog.cpp"
    entry_points: ["TableStatistics", "ColumnStats"]

scanner_hints:
  rule_registry_file: "src/Processors/QueryPlan/Optimizations/Optimizations.cpp"
  registry_array_pattern: "static const Optimization optimizations\\[\\]"
```

#### GPDB (Orca)

```yaml
engine_id: gpdb_orca
display_name: "GPDB (Orca)"
version: "7.x"
language: cpp
optimizer_framework: cascades
optimizer_root: "./src/backend/gporca/libgpopt"

patterns:
  rbo_rules:
    glob: "**/xforms/CXform*.cpp"
    class_pattern: "class CXform\\w+\\s*:\\s*public CXformExploration"
    key_methods: ["Transform", "Matches", "Arity"]
  cbo_rules:
    glob: "**/xforms/CXform*.cpp"
    class_pattern: "class CXform\\w+\\s*:\\s*public CXformImplementation"
    key_methods: ["Transform", "Matches"]
  scalar_rules:
    glob: "**/xforms/CXformScalar*.cpp"
    class_pattern: "class CXformScalar\\w+"
    key_methods: ["Transform"]
  post_opt:
    glob: "**/engine/COptimizer.cpp"
    func_pattern: "COptimizer::\\w+"
    key_methods: []
  properties:
    glob: "**/base/CDistributionSpec*.{h,cpp}"
    class_pattern: "class CDistributionSpec\\w+"
    key_methods: ["FSatisfies", "PdsCopyWithRemappedColumns"]
  statistics:
    glob: "**/base/CStatistics.cpp"
    entry_points: ["CStatistics", "CHistogram", "CMDAccessorUtils"]

lifecycle_entry:
  optimizer_class: "COptimizer"
  entry_method: "PdxlnOptimize"
  plan_root_class: "CGroupExpression"

rule_registry:
  file: "libgpopt/include/gpopt/xforms/CXformFactory.h"
  list_func: "Pxff"
```

#### Apache Calcite

```yaml
engine_id: calcite
display_name: "Apache Calcite"
version: "1.37.x"
language: java
optimizer_framework: volcano
optimizer_root: "./core/src/main/java/org/apache/calcite"

patterns:
  rbo_rules:
    # CoreRules — 由 HepPlanner 执行
    glob: "**/rel/rules/*.java"
    class_pattern: "class \\w+Rule\\s+extends\\s+(RelRule|AbstractConverter)"
    key_methods: ["onMatch", "matches", "perform"]
    annotation_filter: "@Value.Immutable"
  cbo_rules:
    # EnumerableRules — 由 VolcanoPlanner 执行，Logical → Enumerable 转换
    glob: "**/adapter/enumerable/Enumerable*Rule.java"
    class_pattern: "class Enumerable\\w+Rule"
    key_methods: ["onMatch"]
  scalar_rules:
    glob: "**/rex/RexSimplify.java"
    class_pattern: "class RexSimplify"
    key_methods: ["simplify", "simplifyAnd", "simplifyOr"]
  post_opt:
    glob: "**/rel/RelDecorrelator.java"
    class_pattern: "class RelDecorrelator"
    key_methods: ["decorrelateQuery", "decorrelateRel"]
  properties:
    glob: "**/plan/RelTrait*.java"
    class_pattern: "class \\w+TraitDef"
    key_methods: ["convert", "canConvert", "getTraitClass"]
  statistics:
    glob: "**/rel/metadata/**/*.java"
    entry_points: ["RelMdRowCount", "RelMdSelectivity", "RelMdDistinctRowCount"]

rule_registry:
  file: "rel/rules/CoreRules.java"
  list_func: "class CoreRules"

scanner_hints:
  java_ast_parser: true
```

#### CockroachDB

```yaml
engine_id: cockroachdb
display_name: "CockroachDB"
version: "24.x"
language: go
optimizer_framework: optgen
optimizer_root: "./pkg/sql/opt"

patterns:
  rbo_rules:
    glob: "**/norm/*.opt"
    dsl_rule_pattern: "^\\[\\w+,\\s*Normalize\\]"
  cbo_rules:
    glob: "**/xform/*.opt"
    dsl_rule_pattern: "^\\[\\w+,\\s*(Explore|Generate\\w+)\\]"
  scalar_rules:
    glob: "**/norm/scalar*.opt"
    dsl_rule_pattern: "^\\[\\w+\\]"
  post_opt:
    glob: "**/xform/optimizer.go"
    func_pattern: "func \\(o \\*Optimizer\\) \\w+"
    key_methods: []
  properties:
    glob: "**/physical/required.go"
    class_pattern: "type \\w+Required struct"
    key_methods: []
  statistics:
    glob: "**/stats/**/*.go"
    entry_points: ["TableStatistic", "HistogramData", "SampledColumn"]

scanner_hints:
  skip_generated_files: true       # 跳过 *_gen.go 和 *.og.go
  prefer_dsl_over_generated: true  # 优先读 .opt 文件
  optgen_dsl_parser: true
```

#### PostgreSQL

```yaml
engine_id: postgres
display_name: "PostgreSQL"
version: "16.x"
language: c
optimizer_framework: path_based
optimizer_root: "./src/backend/optimizer"

patterns:
  # PostgreSQL 无 Rule 类，按功能模块 + 函数为分析单元
  rbo_rules:
    glob: "**/prep/*.c"
    func_pattern: "^(void|List\\s*\\*|Query\\s*\\*)\\s+\\w+(PlannerInfo|Query)\\s*\\*"
    key_files:
      - "prep/prepjointree.c"
      - "prep/prepqual.c"
      - "prep/tlist.c"
      - "plan/subselect.c"
  cbo_rules:
    glob: "**/path/*.c"
    func_pattern: "^\\w+\\s+\\w+\\(PlannerInfo"
    key_files:
      - "path/joinpath.c"
      - "path/indxpath.c"
      - "util/costsize.c"
      - "path/allpaths.c"
  scalar_rules:
    glob: "**/optimizer/clauses.c"
    func_pattern: "Node\\s*\\*\\s+eval_const_expressions"
    key_files:
      - "optimizer/clauses.c"
  post_opt:
    glob: "**/plan/createplan.c"
    func_pattern: "Plan\\s*\\*\\s+create_\\w+_plan"
    key_files:
      - "plan/createplan.c"
  properties:
    glob: "**/optimizer/pathkeys.c"
    key_files:
      - "optimizer/pathkeys.c"
  statistics:
    glob: "**/statistics/**/*.c"
    entry_points: ["examine_attribute_values", "statext_ndistinct", "get_attavgwidth"]
    key_files:
      - "utils/selfuncs.c"
      - "statistics/statistics.c"

scanner_hints:
  no_class_concept: true
  key_function_signature: "PlannerInfo *"
```

#### Columbia

```yaml
engine_id: columbia
display_name: "Columbia"
version: "academic"
language: cpp
optimizer_framework: columbia
optimizer_root: "./src"

patterns:
  rbo_rules:
    glob: "**/rules/*.{cpp,h}"
    class_pattern: "class \\w+Rule\\s*:\\s*public Rule"
    key_methods: ["fire", "top_match", "next_substitute"]
  cbo_rules:
    glob: "**/rules/impl_*.{cpp,h}"
    class_pattern: "class Impl_\\w+Rule"
    key_methods: ["fire"]
  scalar_rules:
    glob: "*.{cpp,h}"
    func_pattern: ""
  post_opt:
    glob: "**/opt/*.cpp"
    func_pattern: ""
  properties:
    glob: "**/physprop/*.{cpp,h}"
    class_pattern: "class PhysProp"
    key_methods: ["Dominated", "operator=="]
  statistics:
    glob: "**/cat/*.cpp"
    entry_points: ["SCHEMA", "FDSET", "PHYS_PROP"]
```

### 5.3 配置验证规则

启动前静态校验，校验失败立即终止：

1. `optimizer_root` 目录存在；
2. 各 `glob` 模式能匹配至少 1 个文件；
3. `key_methods` 中的方法名在匹配文件中至少出现一次；
4. `rule_registry` 中配置的 `enum_name` 或 `list_func` 必须在对应文件中存在；
5. CockroachDB：`.opt` 文件中必须能解析出至少 1 条 `[RuleName]` 块；
6. PostgreSQL：`key_files` 列表中的文件必须全部存在。

---

## 6. 第二层：Task 1 — 枚举与 Prompt 生成

### 6.1 Language-aware File Scanner

**C++ 类继承引擎（StarRocks / Doris BE / GPDB / Columbia）**：

```
1. 用 class_pattern 正则定位所有类声明
2. 从类声明 '{' 起，大括号深度计数，找到类体结束位置
3. 在类体内对 key_methods 逐一定位并提取方法体
4. 提取类级 Doxygen 注释（/** ... */，位于类声明前）
5. 查找 rule_registry 中对应枚举项及注释
```

**ClickHouse（函数式 + 注册数组）**：

```
1. 读取 Optimizations.cpp 中的静态数组：
   {tryXxx, "friendlyName", &settings::xxx} 即为一条规则
2. 根据函数名定位对应 .cpp 文件，提取函数体
```

**Apache Calcite（Java AST）**：

```
1. JavaParser 解析 .java 文件为 AST
2. 找到继承 RelRule / RelOptRule 的类
3. 精确提取 onMatch() 方法体
4. 提取 @Value.Immutable Config 内部类（定义 operand 匹配模式）
5. 在 CoreRules.java 中找到对应静态字段及 Javadoc
```

**CockroachDB（Optgen DSL）**：

```
1. 扫描 norm/*.opt 和 xform/*.opt 文件
2. 按 [RuleName, Tags] 分隔符切分规则块
3. 提取规则块前的 # 注释行
4. 提取匹配模式（=> 前）和替换模式（=> 后）
5. 跳过 *_gen.go 和 *.og.go 生成文件
```

**PostgreSQL（C 函数）**：

```
1. 按 key_files 列表依次扫描核心文件
2. 用 func_pattern 正则定位函数签名
3. 大括号深度计数提取函数体
4. 提取函数前的块注释（/* ... */）
   （PostgreSQL 注释质量极高，务必包含）
```

### 6.2 Rule Enumerator 工作量估算（8 引擎）

```
Optimizer Rule Inventory — All Engines
══════════════════════════════════════════════════════════
Engine          │ RBO  │ CBO  │ Scalar│ Post │ Props│ Total
────────────────┼──────┼──────┼───────┼──────┼──────┼──────
StarRocks       │  47  │  38  │   29  │  18  │  12  │  144
Doris (Nereids) │  62  │  45  │   35  │  20  │  15  │  177
ClickHouse      │  18  │   8  │   12  │   4  │   4  │   46
GPDB (Orca)     │  65  │  58  │   18  │  15  │  22  │  178
Calcite         │  85  │  55  │   25  │   8  │  18  │  191
CockroachDB     │ 120  │  82  │   30  │  12  │  16  │  260
PostgreSQL      │  22  │  28  │   12  │  10  │   8  │   80
Columbia        │  22  │  18  │    8  │   4  │   6  │   58
══════════════════════════════════════════════════════════
Total           │ 441  │ 332  │  169  │  91  │ 101  │ 1134
──────────────────────────────────────────────────────────
Est. LLM calls  : ~1142（含 8 次 Statistics 整体分析）
Est. total tokens: ~1.7M input + ~570K output
Est. API cost   : ~$17–25（Claude Sonnet，含重试余量）
Est. wall time  : ~4.8 hr (sequential) / ~50 min (parallel ×6)
══════════════════════════════════════════════════════════
```

### 6.3 Task Queue 结构

```json
{
  "task_id": "cockroachdb::rbo::EliminateProject",
  "engine_id": "cockroachdb",
  "category": "rbo",
  "rule_name": "EliminateProject",
  "source_file": "pkg/sql/opt/norm/project_funcs.go",
  "dsl_file": "pkg/sql/opt/norm/project.opt",
  "source_snippet": "...",
  "dsl_snippet": "[EliminateProject]\n(Project $input:* [])\n=> $input",
  "optimizer_framework": "optgen",
  "language": "go",
  "estimated_tokens": 420,
  "status": "pending",
  "priority": 1,
  "created_at": "...",
  "analyzed_at": null,
  "retries": 0
}
```

**优先级规则**：RBO + CBO（P1）→ Properties + Statistics（P2）→ Scalar + Post-Opt（P3）。

---

## 7. 第三层：Task 2 — 逐规则深度分析

### 7.1 Analysis Harness 主循环

```
WHILE task_queue 中存在 status=pending 的任务：
  1. 取出下一个 pending 任务（按 priority 排序）
  2. 状态更新为 in_progress
  3. Prompt Factory 根据 category + optimizer_framework + language 选择模板，
     注入 source_snippet + RA 符号约定 + 框架特定问题 + JSON schema
  4. 调用 Claude API（max_tokens=2000，temperature=0）
  5. 输出校验：JSON 可解析 + 必填字段完整 + RA 符号合规 + confidence 范围
  6a. 校验通过 → 写入 data/{engine}/xxx_rules.jsonl，状态 done
  6b. 校验失败 → 重试最多 2 次，仍失败则状态 failed，写入 error_log.jsonl
  7. confidence < 0.7 → 追加写入 data/needs_review.jsonl
```

### 7.2 框架差异对 Prompt 的影响

| 框架类型 | 额外关注点 | 在 Prompt 中增加的问题 |
|---------|---------|---------------------|
| Cascades（SR/Doris/GPDB/Columbia） | Memo 搜索控制、Property 推导 | 该规则是否会触发 Enforcer 插入？如何控制 explore 深度？ |
| Optgen DSL（CockroachDB） | DSL 语义解读 | 请解读 Optgen 匹配模式和替换模式的代数含义 |
| 多 Pass（ClickHouse） | Pass 执行顺序、幂等性 | 该优化函数在哪个 Pass 中执行？与其他 Pass 的依赖关系？ |
| Path-based（PostgreSQL） | 路径代价比较语义 | 该函数生成何种类型的 Path？与哪些代价函数交互？ |
| Volcano（Calcite） | HepPlanner vs VolcanoPlanner 分工 | 该规则属于 CoreRules（HEP）还是 EnumerableRules（Volcano）？为什么？ |

### 7.3 各分析器说明

#### RBO Analyzer — 逻辑等价变换

核心关注：变换前后关系代数表达式（语义等价）；触发条件；与其他 RBO Rules 的依赖/冲突；规则顺序约束。

#### CBO Analyzer — 物理实现与代价模型

核心关注：逻辑算子 → 物理算子映射；代价公式（CPU/Memory/Network cost）；统计信息依赖；物理属性约束。

**特殊处理**：
- ClickHouse：代价感知逻辑内嵌在 Pass 函数中，分析"Pass 函数的代价感知逻辑"；
- PostgreSQL：以路径代价函数为单位（`cost_hashjoin`、`cost_mergejoin` 等）。

#### Scalar Analyzer — 表达式层重写

核心关注：表达式模式匹配（哪类 ScalarOperator / RexNode）；等价变换代数依据；函数属性（确定性、幂等性）；NullHandling 交互。

#### Post-Opt Analyzer — 物理计划后处理

核心关注：触发时机；对已选定物理计划的修改范围；与执行引擎接口对接（Pipeline 划分、Exchange 插入）。

#### Properties Analyzer — Enforcer 机制

核心关注：Property 语义（Ordering/Distribution/Partition/Rewindability）；Enforcer 算子插入条件；Required vs. Preferred vs. Any；Property 推导规则；Property 间冲突处理。

**重点引擎**：GPDB Orca 的 Property 体系在 8 个引擎中最完整，是分析分布式 Enforcer 机制的最佳样本。

#### Stats Analyzer — 统计信息体系（整体分析）

以整个统计信息模块为单元，覆盖采集、存储、调度、代价使用四个维度。

**各引擎差异提示**：

| 引擎 | 统计信息特点 |
|------|-----------|
| StarRocks | FE 内存 + 直方图，Full/Sample ANALYZE |
| Doris | Nereids Stats + HBO（Histogram-Based Optimization） |
| ClickHouse | 无传统统计信息，依赖 primary key 基数 |
| GPDB Orca | DXL 格式传递，通过 MDAccessor 获取 PG 统计信息 |
| Calcite | 可插拔 RelMetadataProvider，无内置采集 |
| CockroachDB | 分布式统计采集，完整直方图 |
| PostgreSQL | pg_statistic 系统表，MCV + Histogram + ndistinct |
| Columbia | 学术实现，仅基础基数信息 |

---

## 8. 第四层：Schema-locked 结构化存储

### 8.1 Rule Analysis Schema

```typescript
interface RuleAnalysis {
  // 标识信息
  task_id: string;
  engine_id: string;
  category: "rbo" | "cbo" | "scalar" | "post_opt" | "property";
  rule_name: string;
  source_file: string;
  dsl_snippet?: string;          // CockroachDB Optgen 专用
  optimizer_framework: string;

  // 核心分析
  summary: string;
  ra_input_pattern: string;
  ra_output_pattern: string;
  ra_condition: string;

  // 正确性与适用性
  correctness_conditions: string[];
  performance_impact: string;
  edge_cases: string[];

  // 框架特定字段
  framework_notes?: string;
  enforcer_triggered?: boolean;  // CBO 规则：是否触发 Enforcer 插入
  stats_dependencies?: string[]; // CBO 规则：依赖的统计信息字段

  // 跨引擎对比关键字段
  logical_category: LogicalCategory;
  canonical_name: string;
  related_rules: string[];

  // 质量元信息
  confidence: number;
  needs_review: boolean;
  analyzed_at: string;
  model_version: string;
}

type LogicalCategory =
  | "predicate_pushdown"
  | "join_reorder"
  | "join_elimination"
  | "subquery_unnesting"
  | "aggregation_pushdown"
  | "aggregation_elimination"
  | "projection_pruning"
  | "view_merging"
  | "cte_reuse"
  | "sort_elimination"
  | "limit_pushdown"
  | "partition_pruning"
  | "constant_folding"
  | "expression_simplification"
  | "distribution_optimization"
  | "physical_join_impl"
  | "physical_agg_impl"
  | "physical_scan_impl"
  | "mv_rewrite"
  | "set_operation"
  | "window_function"
  | "other";
```

### 8.2 存储格式

```
data/
├── {engine_id}/
│   ├── rbo_rules.jsonl
│   ├── cbo_rules.jsonl
│   ├── scalar_rules.jsonl
│   ├── post_opt_rules.jsonl
│   ├── properties.jsonl
│   └── statistics.json
├── canonical_name_map.json
├── diff_matrix.json
├── scoring.json
└── task_queue.json
```

---

## 9. 第五层：Task 3 — 多引擎对比报告

### 9.1 Canonical Name 归一化（Task 2.5）

在 Task 2 完成后、Task 3 开始前执行一次全局归一化：

```
1. 收集所有引擎的全量 canonical_name，按 logical_category 分组
2. 对每个 category，将名称列表提交 LLM 聚类（约 20 次 API 调用）：
   "以下是 8 个引擎中 predicate_pushdown 类别下的规则名称，
    请将语义相同的规则合并为同一 canonical_name（格式：category.action），
    输出归一化映射表 JSON"
3. 将映射表应用到所有 JSONL 文件
4. 保存 canonical_name_map.json
```

**目标命名示例**：

```
predicate_pushdown.filter_through_join
predicate_pushdown.filter_through_aggregate
join_reorder.bushy_tree_enumeration
subquery_unnesting.in_to_semijoin
aggregation_pushdown.partial_agg_below_join
distribution_optimization.broadcast_vs_shuffle_decision
```

### 9.2 Diff Matrix 生成

对每个 `canonical_name`，遍历 8 个引擎，记录 `present/absent` 及 RA 语义对比，输出 `diff_matrix.json`：

```json
{
  "canonical_name": "predicate_pushdown.filter_through_join",
  "logical_category": "predicate_pushdown",
  "engines": {
    "starrocks":   { "present": true,  "rule_name": "PushDownPredicatesRule",   "confidence": 0.92 },
    "doris":       { "present": true,  "rule_name": "PushFilterInsideJoinRule", "confidence": 0.88 },
    "clickhouse":  { "present": true,  "rule_name": "tryPushFilterToStorage",   "confidence": 0.75 },
    "gpdb_orca":   { "present": true,  "rule_name": "CXformPushGbBelowJoin",    "confidence": 0.85 },
    "calcite":     { "present": true,  "rule_name": "FilterJoinRule",           "confidence": 0.93 },
    "cockroachdb": { "present": true,  "rule_name": "PushFilterIntoJoinLeft",   "confidence": 0.90 },
    "postgres":    { "present": true,  "rule_name": "push_down_qual (prepjointree.c)", "confidence": 0.82 },
    "columbia":    { "present": true,  "rule_name": "PUSH_EQJOIN",             "confidence": 0.78 }
  },
  "all_present": true,
  "semantic_equivalent": false,
  "diff_summary": "各引擎均实现此规则，但 ClickHouse 仅将谓词下推至 Storage 层（与 MergeTree 耦合），其他引擎下推至逻辑 Join 算子下方；PostgreSQL 通过 qual 列表处理，无显式 Rule 类抽象。",
  "alignment_score": 0.78
}
```

### 9.3 Scoring Engine

**评分维度与权重**：

| 维度 | 权重 | 计算方式 |
|------|------|--------|
| 规则覆盖率 | 40% | 该 logical_category 中 present 规则数 / 总规则数 |
| 语义等价度 | 30% | 所有引擎都 present 的规则中，RA 语义等价比例 |
| 触发条件完整性 | 15% | 基于 confidence 加权的 edge_cases 覆盖 |
| 框架成熟度 | 15% | 主观评分：Rule 注册机制类型安全性、是否支持 Rule 开关等 |

**8 引擎综合评分卡（格式预览，数值在 Task 3 执行后填充）**：

| 优化维度 | SR | Doris | CH | GPDB | Calcite | CRDB | PG | Columbia |
|---------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| 谓词下推 | - | - | - | - | - | - | - | - |
| Join 优化 | - | - | - | - | - | - | - | - |
| 子查询处理 | - | - | - | - | - | - | - | - |
| 聚合优化 | - | - | - | - | - | - | - | - |
| 分布式 Property | - | - | - | - | - | - | - | - |
| 统计信息体系 | - | - | - | - | - | - | - | - |
| **综合评分** | - | - | - | - | - | - | - | - |

### 9.4 对比报告生成策略

**两阶段策略**：

- **阶段一（机器生成ï：基于 diff_matrix.json 自动生成对比矩阵表格（✓/✗/△），100% 确定性；
- **阶段二（LLM 深度分析）**：对有语义差异的规则对（预计约 200-300 个），调用 Claude 生成 3-5 段深度对比分析，有明确数据支撑。

---

## 10. 输出目录结构

```
output/
│
├── {engine_id}/                    # 单引擎分析报告（8 个引擎各一目录）
│   ├── 00_framework_lifecycle.md   # 优化器框架与生命周期
│   ├── 01_rbo_rules.md             # RBO 规则（每条 Rule 一个 H2 section）
│   ├── 02_cbo_rules.md
│   ├── 03_scalar_rules.md
│   ├── 04_post_optimizer.md
│   ├── 05_properties.md
│   ├── 06_statistics.md
│   └── 07_other_features.md        # 可观测性、可解释性、可扩展性
│
├── comparison/                     # 多引擎对比报告
│   ├── 00_executive_summary.md     # 执行摘要 + 综合评分卡
│   ├── 01_framework_comparison.md  # 框架架构对比（技术谱系）
│   ├── 02_rbo_comparison.md        # RBO 对比矩阵 + 深度分析
│   ├── 03_cbo_comparison.md        # CBO 对比（含代价模型差异）
│   ├── 04_scalar_comparison.md
│   ├── 05_post_opt_comparison.md
│   ├── 06_properties_comparison.md # Properties 对比（重点：分布式 Property）
│   ├── 07_statistics_comparison.md
│   ├── 08_missing_rules.md         # 缺失规则汇总与影响分析
│   └── 09_observability_comparison.md
│
└── data/                           # 结构化原始数据
    ├── {engine_id}/                # 每引擎的 JSONL 数据
    ├── canonical_name_map.json
    ├── diff_matrix.json
    ├── scoring.json
    └── task_queue.json
```

---

## 11. Prompt 模板设计

### 11.1 RBO Rule 分析 Prompt

```
你是一位数据库查询优化器专家，正在分析 {engine}（{optimizer_framework} 框架）的源码。

## 待分析规则
规则名称：{rule_name}
规则类型：RBO — 逻辑等价变换
源码语言：{language}
{dsl_section}   // CockroachDB: 注入 DSL 原文

{source_snippet}

## 分析任务

### 1. 规则概述（2-3 句话）
### 2. 关系代数形式表达
使用附录符号约定，给出：输入模式 / 输出模式 / 触发条件
### 3. 正确性条件
### 4. 性能影响
### 5. 边界情况与限制
### 6. Canonical Name（格式：logical_category.specific_action）
### 7. 框架特定说明
{framework_specific_questions}

请严格按以下 JSON schema 返回，不要输出 JSON 以外的任何内容：
{output_schema}
```

**framework_specific_questions 示例**：

- Cascades：该规则是否影响 Memo 搜索空间？是否会触发 Enforcer 插入？
- Optgen DSL：匹配模式和替换模式的代数语义是什么？
- ClickHouse Pass：该函数在哪个 Pass 中执行？是否幂等？
- PostgreSQL：该函数生成何种类型的 Path？与哪些代价函数交互？
- Calcite/Volcano：该规则属于 HepPlanner 还是 VolcanoPlanner？为什么？

### 11.2 CBO Rule 分析 Prompt

在 RBO 基础上额外询问：

```
### 8. 物理算子映射
### 9. 代价模型
- 引用哪些统计信息（NDV/RowCount/AvgSize/Histogram）？
- 代价公式（CPU cost / Memory cost / Network cost）？
- 统计信息缺失时的 fallback？
### 10. 物理属性约束
- 该算子 output 哪些 Physical Properties？
- 对 children 有哪些 required properties？
- 是否触发 Enforcer（Sort / Exchange）插入？
```

### 11.3 Optgen DSL 专用 Prompt（CockroachDB）

```
你是一位 CockroachDB Optgen 查询优化器专家。

## 待分析规则（Optgen DSL 格式）
{dsl_snippet}

生成的 Go 代码参考（供理解，非主要分析对象）：
{generated_go_snippet}

分析重点：
1. DSL 语义解读：Match pattern 匹配什么 Memo 表达式？Replace pattern 生成什么？
2. 关系代数形式表达（参考附录符号约定）
[后续问题与通用 RBO Prompt 一致]
```

### 11.4 多引擎对比 Prompt（Task 3）

```
你是一位数据库优化器专家，分析 {n} 个引擎对同一优化规则的实现差异。

规则：{canonical_name}（{logical_category}）

## {engine_A}（{framework_A}）
规则名：{rule_name}  RA 输入：{ra_input}  RA 输出：{ra_output}

## {engine_B}（{framework_B}）
[...]

缺失引擎：{absent_engines}（未实现此规则）

请分析：
1. 各实现的 RA 语义是否完全等价？差异在哪？
2. 触发条件覆盖范围的差异（更保守 vs 更激进）？
3. 缺失该规则的引擎对哪类查询有性能影响？
4. 框架差异（Cascades vs Path-based vs 多 Pass）对实现方式的影响？
5. 哪个实现最完整？原因？

输出 3-5 段自然语言分析，不需要 JSON 格式。
```

---

## 12. 可靠性保障机制

### 12.1 Source Snippet 质量控制

| 优先级 | 内容 | 估算 Token | 是否必须 |
|-------|------|-----------|---------|
| P0 | 核心变换方法体（transform/onMatch/fire/tryXxx） | 400-800 | 必须 |
| P0 | 触发条件方法体（check/match/pattern） | 100-300 | 必须 |
| P1 | 类/函数级注释（Doxygen/Javadoc/Go doc） | 50-200 | 尽量 |
| P1 | 类声明与成员变量 | 100-200 | 尽量 |
| P2 | 规则注册枚举注释 | 30-100 | 可选 |
| P2 | 辅助 private 方法 | 200-600 | 按 budget |

超出 2000 tokens 时，按 P2→P1→P0 逆序裁剪。

**语言特定说明**：
- Optgen DSL（CockroachDB）：DSL 原文通常仅 50-200 tokens，附带生成的 Go 核心函数 ~300 tokens；
- PostgreSQL：注释质量极高，务必包含函数前块注释。

### 12.2 关系代数符号合规校验

合规符号集：`σ π ⋈ ⟕ ⟖ ⟗ γ τ ∪ ∩ − × ρ δ ⋉ ▷ λ ω` 及其 ASCII 替代写法。

校验规则：括号匹配；下标格式（`_p` 或 `_{predicate}`）；关系变量为大写字母；禁止 SQL 语法关键字。校验失败 → 追加 `needs_review.jsonl`。

### 12.3 Confidence 机制

| 情况 | 建议置信度 |
|------|-----------|
| Optgen DSL 输入（语义最明确） | 0.85-0.95 |
| 有详细 Doxygen/Javadoc 注释 | 0.85-0.95 |
| 代码清晰但无注释 | 0.70-0.85 |
| PostgreSQL C 函数（需结合上下文） | 0.65-0.80 |
| 依赖大量外部上下文 | 0.50-0.70 |
| 代码有明显歧义 | < 0.50 |

低置信度处理：自动拉取更多上下文重试一次；仍低则标记 `needs_review: true`；报告中加注 ⚠️ 标记。

### 12.4 重试与错误处理

```
JSON 解析失败：立即重试，最多 2 次
必填字段缺失：立即重试，最多 2 次
API 限流(429)：指数退避，最多 5 次（1/2/4/8/16 秒）
API 错误(5xx)：等待 10s 后重试，最多 3 次
RA 符号校验失败：增加符号约定提示重试，最多 1 次
超过重试次数：状态 failed，写入 error_log.jsonl
```

---

## 13. 执行流程与断点续跑

### 13.1 完整执行流程

```
STEP 0: 初始化
  - 读取目标引擎列表（--engines 或默认全部 8 个）
  - 校验所有 engines/*.yaml 配置
  - 创建输出目录结构

STEP 1: Task 1 — 枚举（每引擎 3-10 分钟，无 LLM）
  FOR EACH engine:
    Language-aware File Scanner → Rule Enumerator
    → 写入 {engine}_file_index.json
  → 生成 task_queue.json（汇总）
  → 输出工作量估算（规则数 / token 数 / 预计费用）
  → [人工确认] 是否继续

STEP 2: Task 2 — 分析（全量 ~4.8 hr，并发 ×6 ~50 min）
  Analysis Harness 主循环
  - 实时进度：已完成 xxx/1142，当前引擎 xxx，预计剩余 xx 分钟
  - 每 20 条写一次æ¥点
  - 循环结束输出执行摘要

STEP 2.5: Canonical Name 归一化（~15 分钟，~20 次 API 调用）
  - 按 logical_category 分组聚类归一化
  - 更新所有 JSONL 文件
  - 保存 canonical_name_map.json

STEP 3: Task 3 — 对比报告（~30-60 分钟）
  - 生成 diff_matrix.json（机器逻辑）
  - Scoring Engine（机器逻辑）
  - LLM 深度对比分析（~200-300 次 API 调用）
  - 生成所有 Markdown 报告
```

### 13.2 断点续跑机制

| Task | 续跑逻辑 | 强制重跑命令 |
|------|---------|-----------|
| Task 1 | 若 `{engine}_file_index.json` 存在则跳过 | `--force-rescan {engine_id}` |
| Task 2 | 跳过 `status=done` 的任务 | `--force-rerun {task_id}` / `--rerun-failed` |
| Task 2 | 只处理指定引擎 | `--engines starrocks,doris` |
| Task 2.5 | 若 `canonical_name_map.json` 存在则跳过 | `--force-renormalize` |
| Task 3 | 若 `diff_matrix.json` 存在则跳过计算 | `--regen-report` |

### 13.3 增量新增第 9 个引擎

```
1. 添加 engines/{new_engine}.yaml
2. python run.py --engines {new_engine} --task 1,2
3. python run.py --task 2.5 --incremental-normalize
4. python run.py --task 3 --regen-report
```

---

## 14. 实现优先级建议

### Phase 1：单引擎 MVP，验证分析质量（1-2 周）

| 模块 | 工作量 | 验收标准 |
|------|--------|---------|
| StarRocks 配置 YAML + 校验 | 0.5 天 | 正确定位所有 Rule 文件 |
| C++ File Scanner（StarRocks） | 2 天 | 提取 100+ Rule 方法体，token 估算误差 <20% |
| Task Queue 状态机 | 0.5 天 | 4 状态正确流转 |
| RBO + CBO Prompt 模板 | 2 天 | 20 条 Rule 人工验证准确率 >80% |
| RA 符号校验器 | 1 天 | 正确拒绝 SQL 语法和未知符号 |
| 单引擎 Markdown 报告 | 1 天 | 格式清晰，RA 表达式正确 |

### Phase 2：全分类 + 多语言扩展（1.5 周）

| 模块 | 工作量 |
|------|--------|
| Scalar / Post-Opt / Properties / Statistics Prompt 模板 | 2.5 天 |
| Java File Scanner（Calcite） | 2 天 |
| Optgen DSL 专用解析器（CockroachDB） | 1.5 天 |
| PostgreSQL C Scanner | 1 天 |
| 可靠性机制（confidence + 重试 + needs_review） | 1 天 |

### Phase 3：多引擎全覆盖 + 对比报告（2 周）

| 模块 | 工作量 |
|------|--------|
| Doris（Java FE Nereids）Scanner 适配 | 1.5 天 |
| GPDB Orca（C++ Xform）Scanner 适配 | 1 天 |
| ClickHouse + Columbia Scanner 适配 | 1 天 |
| Task 2.5 Canonical Name 归一化 | 1 天 |
| Diff Matrix + Scoring Engine | 1.5 天 |
| 对比报告 Markdown 生成 | 2.5 天 |
| 端到端测试 + 文档 | 1 天 |

### 关键决策点

**StarRocks 是最佳 MVP 对象**：已有深度理解，可直接验证 Claude 输出准确性，快速迭代 prompt 模板。

**Calcite 是最佳对比基准**：纯优化器框架，规则语义最明确（Java + 好注释 + 学术命名）。当某条 `canonical_name` 的语义不确定时，以 Calcite 对应命名为准。

**CockroachDB Optgen 是意外收获**：`.opt` DSL 文件本身接近"关系代数规则的机器可读表示"，分析结果置信度预期最高，可作为 RA 表达式质量的参照标杆。

**PostgreSQL 的分析方式最特殊**：无 Rule 类，以函数为单位，建议在 Phase 2 为其设计独立的 `path_based_function` 分析类别，避免强行套用 Cascades 的 RBO/CBO 框架。

**`canonical_name` 字典是最有价值的副产品**：8 个引擎分析完成后将形成"OLAP/OLTP 优化器规则本体（Optimizer Rule Ontology）"，具有独立的参考和学术价值，建议作ä独立资产。

---

## 15. 附录 A：关系代数符号约定

所有 Prompt 模板注入此约定，保证跨引擎、跨调用的符号一致性。

### 基本算子

| 算子 | 符号 | 示例 | 含义 |
|------|------|------|------|
| 选择 | σ | σ_{a>5}(R) | 过滤满足谓词的行 |
| 投影 | π | π_{a,b}(R) | 保留指定列 |
| 重命名 | ρ | ρ_{S(a,b)}(R) | 重命名关系或列 |
| 笛卡尔积 | × | R × S | 无条件叉乘 |
| θ-连接 | ⋈_p | R ⋈_{a=b} S | 条件连接 |
| 自然连接 | ⋈ | R ⋈ S | 同名列等值连接 |
| 左外连接 | ⟕ | R ⟕_p S | 左侧行全保留 |
| 右外连接 | ⟖ | R ⟖_p S | 右侧行全保留 |
| 全外连接 | ⟗ | R ⟗_p S | 两侧行全保留 |
| 半连接 | ⋉ | R ⋉_p S | 仅返回 R 中匹配行 |
| 反半连接 | ▷ | R ▷_p S | 仅返回 R 中不匹配行 |

### 扩展算子

| 算子 | 符号 | 示例 | 含义 |
|------|------|------|------|
| 聚合 | γ | γ_{G; SUM(a)→s}(R) | 分组聚合，G 为分组列 |
| 排序 | τ | τ_{a↑, b↓}(R) | 升/降序 |
| 去重 | δ | δ(R) | 去除重复行 |
| LIMIT | λ | λ_n(R) | 取前 n 行 |
| 窗口函数 | ω | ω_{f; P; O}(R) | P=PARTITION，O=ORDER |
| 集合并 | ∪ | R ∪ S | 去重合并 |
| 多集合并 | ∪ₐ | R ∪ₐ S | UNION ALL |
| 集合交 | ∩ | R ∩ S | 取公共行 |
| 集合差 | − | R − S | R 中不在 S 中的行 |
| 分布式交换 | ε | ε_{dist}(R) | Exchange 算子（Shuffle/Broadcast） |

### 谓词约定

- 简单谓词：`a > 5`、`a = b`；
- 复合谓词：`p₁ ∧ p₂`（AND）、`p₁ ∨ p₂`（OR）、`¬p`（NOT）；
- 子查询：`∃(subquery)` 或 `IN(subquery)`。

### 变换规则记法

```
前提条件
─────────────────────────────
输入表达式
⟹
输出表达式
```

**示例**（谓词下推穿越 Inner Join）：

```
p 仅引用 R 的列，Join 类型为 INNER JOIN
─────────────────────────────────────────
σ_p(R ⋈_q S)
⟹
σ_p(R) ⋈_q S
```

---

## 16. 附录 B：各引擎 File Scanner 适配说明

### B.1 C++ 类继承引擎（StarRocks / Doris BE / GPDB / Columbia）

**类体提取**：从类声明 `{` 起，大括号深度计数，`depth` 回到 0 时即类体结束。注意跳过字符串字面量和注释内的括号。

**方法体提取**：在已提取的类体内，对每个 `key_method`，同样用大括号深度计数定位方法体边界。

### B.2 ClickHouse（函数式 + 注册数组）

读取 `Optimizations.cpp` 中的静态注册数组：

```cpp
{tryRemoveRedundantDistinct, "removeRedundantDistinct", &settings::xxx},
```

每一项即为一条"Rule"，根据函数名在其他文件中定位并提取函数体。

### B.3 Apache Calcite（Java AST）

推荐使用 `javalang`（Python）或 JavaParser（Java CLI）做精确 AST 解析：

- 找到 `extends RelRule` 或 `extends RelOptRule` 的类；
- 精确提取 `onMatch(RelOptRuleCall call)` 方法体；
- 提取 `@Value.Immutable Config` 内部类（`operand()` 定义匹配模式）；
- 在 `CoreRules.java` 中找到对应静态字段的 Javadoc。

### B.4 CockroachDB（Optgen DSL）

`.opt` 文件规则格式：

```
# Comment line
[RuleName, Normalize]
(MatchPattern
    $child:*
    $filter:(Filters [...])
)
=>
(ReplacePattern $child $filter)
```

解析策略：以 `[` 开头的行为规则开始标记；收集前面的 `#` 注释；提取 `=>` 前后的模式；跳过 `*_gen.go` 和 `*.og.g 函数）

关键文件清单（以函数为分析单元）：

```
src/backend/optimizer/
├── prep/prepjointree.c   # 谓词下推、子查询展开（RBO 等价）
├── prep/prepqual.c       # 谓词规范化
├── path/joinpath.c       # Join 路径枚举（CBO 核心）
├── path/indxpath.c       # 索引路径枚举
├── util/costsize.c       # 代价计算函数（cost_hashjoin 等）
├── path/allpaths.c       # 全路径枚举入口
├── optimizer/clauses.c   # 常量折叠（Scalar 等价）
├── plan/createplan.c     # Plan 节点创建（Path → Plan）
└── optimizer/pathkeys.c  # 排序键处理（Properties 等价）
```

分析单元命名约定：`postgres::{category}::{file_name}::{function_name}`

---

*文档版本：v2.0*  
*覆盖引擎：ClickHouse · StarRocks · Doris(Nereids) · GPDB(Orca) · Apache Calcite · CockroachDB · PostgreSQL · Columbia*  
*本文档描述系统设计，不包含具体代码实现。*

