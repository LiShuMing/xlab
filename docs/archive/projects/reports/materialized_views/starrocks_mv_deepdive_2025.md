# StarRocks MV

你是一位顶尖的数据库内核专家，精通 OLAP 数据库架构设计、查询优化器原理（CBO/RBO/Cascades/ORCA）、物化视图理论（等价改写、增量维护、一致性协议）及大规模工程实现。

我是 StarRocks 的核心开发者与 Committer，拥有 10 年以上数据库内核研发经验，技术栈涵盖 C++、高并发、分布式系统、向量化执行引擎与底层性能优化。

**请基于这一背景：**
- 跳过基础概念解释，直接输出源码级、架构级的深度分析
- 所有结论必须锚定具体源码，给出关键类名、文件路径、核心函数或 PR/Issue 编号
- 对尚不完善或存在已知缺陷的能力，直接指出，不做过度美化
- 分析缺陷时，给出工程上可行的改进方向，而非泛泛而谈

---

# 任务目标

以 **StarRocks 最新主干源码**为基础，对其 Materialized View（MV）子系统进行系统性的源码级架构剖析，覆盖：

1. 整体架构与模块边界
2. 产品能力与能力边界（支持什么、不支持什么、边界条件在哪里）
3. 已知缺陷与工程短板（源码层面的问题，非用户文档层面的描述）
4. 改进优化方向（结合业界实现对比，给出 StarRocks 可借鉴的方向）

---

# 具体分析维度

## 1. 整体架构与模块划分

- MV 子系统在 FE/BE 中的模块边界与职责划分（代码入口、关键包路径）
- 同步 MV（Rollup/Single-table MV）与异步 MV（Async MV）的架构差异与演进路径
- MV 元数据的存储与版本化机制（GlobalStateMgr 中的持久化、EditLog、镜像更新）
- `MaterializedView` 类的继承体系与核心字段语义（`OlapTable` 子类结构、`MvPlanContext` 缓存、`MvUpdateInfo` 状态机）
- MV 与优化器（CBO）的集成点：`MaterializationContext` 的生命周期与注入时机

## 2. 基表支持类型的能力边界

- 支持的基表类型全集（内表、Hive/Iceberg/Hudi/Paimon/JDBC Catalog 外表、视图、嵌套 MV）及各自的**能力降级路径**（哪些能力在哪种基表类型下不可用）
- 分区映射（Partition Mapping）机制的源码实现：
  - `PartitionBasedMvRefreshProcessor` 中的分区 diff 算法
  - 多基表场景下的分区对齐策略（`partition_refresh_strategy` 的实现逻辑）
  - 外表分区变更感知的实现链路（Hive HMS、Iceberg Snapshot、Paimon version）
- Hudi/JDBC 外表无法分区增量刷新的根因（代码层面的缺失，而非文档说明）

## 3. 查询改写（Query Rewrite）能力边界

- SPJG 改写框架的完整调用链：从 `OptimizerTask` → `MaterializedViewRewriteRule` → `MvUtils` 到最终 plan 替换的全路径
- 支持的改写类型与能力边界，重点分析：
  - **View Delta Join**：补偿 Join 的实现机制（FK/PK 约束的利用方式、`ViewDeltaJoinRule` 的触发条件与限制）
  - **Derivable Join**：可推导消除 Join 的条件（`JoinDeriveRule` 的等价推导逻辑）
  - **Text-based Rewrite**（v3.3+）：文本匹配改写的实现原理、与 SPJG 的优先级关系、已知局限
  - **Aggregate Rollup**：上卷维度消除的完整条件（functional dependency 利用）
  - **Predicate Compensation**：补偿谓词的生成与正确性验证
  - **Union Rewrite**（分区补偿）：TTL + stale 分区的 UNION 改写链路
- 改写有效性验证机制（数据一致性校验、`mv_rewrite_staleness_second` 的生效链路）
- **改写失败的常见 case**（源码中的 early-return 路径）及 EXPLAIN 中的失败原因输出机制

## 4. 刷新（Refresh）机制能力边界

- 刷新框架整体架构：`MvTaskRunProcessor` / `PartitionBasedMvRefreshProcessor` 的职责与执行模型
- 支持的刷新模式：
  - **全量刷新（FULL）**
  - **分区级增量刷新（PCT，Partition Change Tracking）**：分区版本快照的记录与 diff 逻辑
  - **行级增量刷新（Incremental Refresh，Issue #61789）**：当前进展、实现方案（Iceberg IncrementalScan API 的利用）、已知限制（仅 append-only，retractable changes 的规划方向）
- 刷新触发机制：手动、定时（`MVActiveChecker`）、ON COMMIT（写入触发链路）的实现差异
- 多事实表对齐刷新（v3.3+）的实现：`multi_fact_table` 对齐策略的分区选取算法
- 刷新任务的调度、并发控制（`TaskRunScheduler`）、失败重试与幂等性保障
- **刷新的核心性能瓶颈**：大分区数场景下的元数据扫描开销、任务调度延迟来源

## 5. 已知缺陷与工程短板（源码层面）

请重点挖掘以下类型的问题：
- **改写覆盖率的系统性缺口**：哪些 SQL pattern 因架构限制无法被改写，根因在哪
- **刷新正确性风险**：外表元数据缓存一致性问题（`ConnectorMetadataCache`）、ON COMMIT 触发的竞态条件
- **性能问题**：planning 阶段 MV 候选筛选的复杂度（所有 MV 参与改写尝试时的 overhead）、大规模 MV 场景下的 FE 内存压力
- **多表分区对齐的设计局限**：M:N 分区映射不支持的根因与工程代价
- **其他已知 Issue**：结合 GitHub Issues/PR 中的实际缺陷记录

## 6. 与业界实现的横向对比及改进方向

以下对比维度，请结合 StarRocks 源码现状，给出**可落地的改进建议**：

| 对比维度 | StarRocks 现状 | 业界最佳实践 | 改进方向 |
|---------|---------------|------------|---------|
| 行级增量刷新 | PCT 分区级 | Flink/RisingWave 流式增量、Iceberg V3 CDC | |
| 改写算法完备性 | SPJG + Text/View-based | Google Spanner MV、Calcite LARA | |
| 一致性模型 | Staleness + 强一致可选 | Snowflake MVCC-based freshness | |
| 自动 MV 推荐 | Roadmap，未落地 | Oracle DBMS_ADVISOR、AutoMV 学术方向 | |
| MV-on-MV 级联维护 | 支持但无依赖感知调度优化 | Materialize.io 流式级联 | |
| 大规模 MV Planning 开销 | 全候选尝试 | Presto/Trino 的 MV 过滤与 cost-pruning | |

---

# 输出要求

- **源码锚定**：每个结论附关键类名/文件路径（如 `fe/fe-core/com/starrocks/mv/analyzer/`、`PartitionBasedMvRefreshProcessor.java`）或 GitHub Issue/PR 编号
- **缺陷量化**：对性能问题尽量给出复杂度分析（如"O(n×m) 的改写尝试，n=MV 数量，m=query plan nodes"）
- **改进可行性**：给出改进方向时，区分"短期可做（patch 级）"与"需要架构重构"
- **不美化**：对能力边界、已知缺陷直接陈述，不因 StarRocks 是调研对象而回避问题
- **语言**：简洁，面向内核工程师，无需解释通用数据库概念


# StarRocks Vs Doris
# 角色与背景

你是一位顶尖的数据库内核专家，精通 OLAP 数据库架构设计、查询优化器原理、物化视图理论及工程实现。

我是 StarRocks 的核心开发者与 Committer，拥有 10 年以上数据库内核研发经验，技术栈涵盖 C++、高并发、分布式系统、向量化执行引擎与底层性能优化。请基于这一背景，**跳过基础概念解释，直接面向源码级、架构级的深度分析**。

---

# 任务目标

请以 **Apache Doris 最新主干源码**为基础，对其 Materialized View（物化视图，MV）子系统进行系统性的架构剖析，并与 StarRocks MV 实现进行深度对比。

---

# 具体分析维度

## 1. 整体框架概览
- MV 子系统在 Doris FE/BE 中的模块划分与代码入口（关键类/文件路径）
- 同步 MV（Rollup-based）与异步 MV（Async MV）的架构差异及演进路径
- MV 元数据管理机制（Catalog 层如何存储、版本化 MV 定义）

## 2. 基表支持类型的能力边界
- 支持哪些基表类型作为 MV 的数据源（内表、外表、Hive/Iceberg/Hudi 等 External Catalog、视图、其他 MV）
- 各基表类型在 MV 刷新和改写中的支持完整度与已知限制
- 分区键透传与 Partition Mapping 机制（对 External Table 的支持现状）

## 3. 查询改写（Query Rewrite）能力边界
- 改写框架采用的核心算法（SPJG 模式、基于规则 vs 基于代价）
- 支持的改写类型边界：
  - 聚合上卷（Aggregate Rollup）
  - Join 改写（Join 类型、顺序、补偿 Join）
  - 谓词补偿（Predicate Compensation）
  - UNION 改写
  - 嵌套 MV 改写
- 改写有效性校验机制（数据一致性、时效性检查）

## 4. 刷新（Refresh）机制能力边界
- 支持的刷新模式：全量、增量、分区级增量
- 刷新触发方式：手动、定时、基于 Binlog/CDC 的自动触发
- 增量刷新的实现原理（分区感知、数据版本追踪）
- 级联 MV 刷新与刷新依赖拓扑管理
- 刷新任务的调度、失败重试与幂等性保障

## 5. StarRocks vs Doris 横向对比

请以结构化表格 + 补充说明的形式，从以下维度对比两者差异：

| 对比维度 | StarRocks | Doris | 差异说明 |
|---|---|---|---|
| 同步/异步 MV 架构 | | | |
| 外表支持范围 | | | |
| 分区增量刷新 | | | |
| 查询改写算法 | | | |
| 嵌套 MV 支持 | | | |
| Rewrite 一致性策略 | | | |
| 刷新触发机制 | | | |
| 透明加速效果 | | | |

重点关注：
- Doris 在哪些方向的设计或实现上**优于或领先于** StarRocks
- Doris 相对于 StarRocks 当前存在的**明显短板**
- 两者在架构取舍上体现的**设计哲学差异**

---

# 输出要求

- 所有结论需**锚定源码**，给出关键类名、文件路径或核心函数（如 `MaterializedViewHandler`、`MaterializedViewRewriter` 等）
- 对于尚不完善或存在已知 Issue 的能力，请直接指出，勿做过度美化
- 语言简洁，面向内核工程师，无需解释通用数据库概念

# StarRocks Vs Oracle

## 角色与背景

你是一位顶尖的数据库内核专家，深度熟悉 Oracle Database 内核（Materialized View、Query Rewrite、Advanced Replication）与 StarRocks 的 MV 子系统实现，精通 OLAP 数据库架构设计、查询优化器原理与物化视图工程实现。

我是 StarRocks 的核心开发者与 Committer，拥有 10 年以上数据库内核研发经验，技术栈涵盖 C++、高并发、分布式系统、向量化执行引擎与底层性能优化。

**请基于这一背景：**
- 跳过基础概念，直接输出架构级、实现级的深度对比
- StarRocks 侧结论锚定源码（关键类名/文件路径/Issue 编号）；Oracle 侧结论锚定官方文档、内核白皮书或可信技术资料
- 对能力差距直接陈述，不因立场而回避
- 对比结论区分"设计哲学差异"与"工程完成度差距"

---

## 任务目标

以 **StarRocks 最新主干源码** 与 **Oracle Database 19c/21c MV 实现**为基础，从产品能力边界、架构设计取舍、工程实现质量三个层面进行系统性深度对比，重点识别 StarRocks 相对 Oracle 的**能力缺口**与**可借鉴的设计**。

---

## 具体对比维度

### 1. 改写算法完备性

- **Oracle**：
  - `DBMS_MVIEW.EXPLAIN_REWRITE` 的改写诊断机制（改写失败的分类枚举）
  - General Query Rewrite（GQR）vs Enhanced Query Rewrite（EQR）的算法差异
  - Subquery unnesting 与 MV 改写的协同：Oracle 如何处理 subquery 内的 MV 命中
  - Oracle 对 `UNION ALL` / `GROUPING SETS` / `ROLLUP` / `CUBE` 的 MV 改写支持范围
  - PCT（Partition Change Tracking）改写：Oracle 的 stale partition + fresh partition UNION 改写与 StarRocks Union Rewrite 的机制对比
- **StarRocks**：
  - SPJG 模式的能力上界（当前不支持的 SQL pattern 列举）
  - Text-based Rewrite（v3.3+）作为 SPJG fallback 的覆盖范围与局限
  - View Delta Join / Derivable Join 的触发条件与 Oracle 对应能力的差异
- **对比重点**：
  - Oracle 对 **非 SPJ 查询**（含 window function、analytic function、subquery）的改写支持 vs StarRocks 当前限制
  - 改写失败诊断的工程完整度（Oracle `EXPLAIN_REWRITE` vs StarRocks `EXPLAIN` 中的 MV 改写失败输出）

### 2. 增量维护（Incremental Refresh）机制

- **Oracle**：
  - Fast Refresh 的实现机制：MV Log（`MLOG$_xxx`）的 rowid/PK-based 变更捕获
  - 复杂 MV 的 Fast Refresh 限制（哪些 aggregate 函数、join 类型不支持 fast refresh，根因分析）
  - ON COMMIT Fast Refresh 的事务集成：与 redo log / undo log 的交互
  - Partition Change Tracking（PCT）Refresh：与 StarRocks PCT 的设计对比
  - `CONSIDER FRESH` hint 机制：强制使用 stale MV 的手段
- **StarRocks**：
  - 当前 PCT 分区级刷新的实现（`PartitionBasedMvRefreshProcessor`）
  - 行级增量刷新（Issue #61789）的进展与方案：Iceberg IncrementalScan vs Oracle MV Log 的方案差异
  - ON COMMIT 触发的实现局限（竞态条件、高频写场景的 overhead）
- **对比重点**：
  - Oracle Fast Refresh（行级增量）vs StarRocks PCT（分区级增量）的**维护代价与适用场景**差异
  - Oracle MV Log 机制的工程成熟度 vs StarRocks 行级增量刷新的早期局限
  - 两者对 **多表 Join MV 的增量维护**支持范围差异（Oracle 的 join MV fast refresh 严格限制 vs StarRocks 的全量刷新兜底策略）

### 3. 一致性模型与 Staleness 管理

- **Oracle**：
  - `STALE_TOLERATED` / `ENFORCED` / `TRUSTED` 的一致性级别语义及其在 rewrite 中的行为
  - `QUERY_REWRITE_INTEGRITY` 参数的全局/session 级控制
  - Constraint-based rewrite：Oracle 利用 PK/FK/Unique 约束扩展改写范围（`RELY` constraint）的机制
- **StarRocks**：
  - `mv_rewrite_staleness_second` + `query_rewrite_consistency` 的语义与实现
  - 强一致校验链路（`MvUpdateInfo` 状态检查）的开销
  - 基于约束的改写（Derivable Join 依赖 FK/PK）的当前完备性
- **对比重点**：
  - Oracle `RELY` constraint（无需实际数据验证的"信任约束"）是否有对应机制，对改写覆盖率的影响
  - 两者在 **OLAP 场景下 stale 容忍策略**的工程取舍

### 4. 分区 MV 能力

- **Oracle**：
  - Partition Key 与 MV 分区的映射规则（`PARTITION BY` 在 MV DDL 中的限制）
  - PCT（Partition Change Tracking）的依赖条件（哪些情况下 PCT 失效退化为全量）
  - Multi-column partition mapping 的支持情况
- **StarRocks**：
  - 分区映射的当前限制（不支持 M:N 分区映射的根因）
  - 多基表场景下分区对齐策略（`multi_fact_table` v3.3+）的算法实现
  - 分区 TTL（`partition_live_number`）机制
- **对比重点**：
  - 分区映射灵活性差异及其对 MV 适用场景的影响
  - Oracle PCT 失效条件 vs StarRocks 分区对齐的降级路径

### 5. 可管理性与运维诊断

- **Oracle**：
  - `DBMS_MVIEW` 工具集（`EXPLAIN_REWRITE`、`REFRESH`、`EXPLAIN_MVIEW`）
  - `DBA_MVIEWS` / `DBA_MVIEW_LOGS` / `DBA_MVIEW_REFRESH_TIMES` 系统视图
  - Automatic Tuning Advisor 对 MV 的推荐机制（`DBMS_ADVISOR`）
- **StarRocks**：
  - MV 相关系统表（`information_schema.materialized_views`）与 `SHOW MATERIALIZED VIEWS` 的信息完整度
  - 改写失败的诊断手段（`EXPLAIN` 输出的 MV 命中/失败信息）
  - 自动 MV 推荐能力（Roadmap 状态）
- **对比重点**：
  - 运维诊断工具链的完整度差异
  - Oracle 成熟工具链对 StarRocks 可观测性建设的借鉴价值

---

## 输出结构

### Part 1：能力矩阵对比表
覆盖上述所有维度，格式：

| 对比维度 | Oracle 19c/21c | StarRocks（主干） | 差距性质 | StarRocks 改进方向 |
|---------|---------------|-----------------|---------|-----------------|
| ... | ... | ... | 设计差异/完成度差距/场景不适配 | 短期patch/架构重构 |

### Part 2：Oracle 设计中值得 StarRocks 借鉴的 Top 5
每条给出：Oracle 的实现机制描述 → StarRocks 当前状态 → 具体借鉴建议（含可落地的实现路径）

### Part 3：StarRocks 相对 Oracle 的结构性优势
StarRocks 作为云原生 MPP OLAP 数据库，在哪些 MV 相关维度上具备 Oracle 难以企及的优势（外表 MV、湖仓加速、弹性刷新调度等）

### Part 4：关键缺口的工程优先级建议
结合对比结论，给出 StarRocks MV 子系统最值得优先攻克的 3 个能力缺口，每个给出工程可行性评估

---

## 输出要求

- StarRocks 侧结论锚定源码（类名/路径/Issue 编号）
- Oracle 侧结论注明来源（官方文档章节、内核白皮书、Metalink Note 编号等）
- 差距性质区分"设计哲学差异"与"工程完成度差距"（前者无优劣，后者有追赶空间）
- 改进方向区分"短期可做（patch 级，1-2 人月）"与"需要架构重构（半年以上）"


# StarRocks Vs Calcite


你是一位顶尖的数据库内核专家，深度熟悉 Apache Calcite 的物化视图改写框架（`SubstitutionVisitor`、`MaterializedViewRule`、LARA 算法）与 StarRocks 的 MV 子系统实现，精通查询优化器理论与工程实现。

我是 StarRocks 的核心开发者与 Committer，拥有 10 年以上数据库内核研发经验，技术栈涵盖 C++、高并发、分布式系统、向量化执行引擎与底层性能优化。

**请基于这一背景：**
- 跳过基础概念，直接输出架构级、算法级的深度对比
- StarRocks 侧结论锚定源码；Calcite 侧结论锚定源码（`org.apache.calcite.rel.rules.materialize` 包）或学术论文（LARA、SPJG 原始论文）
- 重点关注**算法完备性差异**，而非产品功能对比

---

## 任务目标

以 **StarRocks 最新主干源码** 与 **Apache Calcite 主干源码**（`calcite-core/src/main/java/org/apache/calcite/rel/rules/materialize/`）为基础，从改写算法设计、实现架构、能力边界三个层面进行深度对比，重点识别 Calcite MV 改写框架的**算法优势**与 StarRocks 可借鉴的具体实现。

---

## 具体对比维度

### 1. 改写算法核心对比

- **Calcite 的改写框架**：
  - `SubstitutionVisitor`（旧框架）与 `MaterializedViewRule` 系列（新框架，基于 LARA 算法）的演进路径
  - LARA（Lossless and non-Lossless Aggregate Rewriting Algorithm）的核心步骤：compensation predicate 生成、aggregate function 变换、列 lineage 推导的具体实现（`MaterializedViewAggregateRule.java`）
  - `UnifyRule` 体系：`ProjectToProjectUnifyRule`、`AggregateToAggregateUnifyRule`、`JoinOnJoinUnifyRule` 的匹配逻辑与覆盖范围
  - Calcite 对 **multi-level aggregation**（嵌套聚合）的改写支持
  - Calcite 改写框架与 Volcano/Cascades 优化器的集成方式（`AbstractMaterializedViewRule` 作为 RelOptRule 的注入机制）
- **StarRocks 的改写框架**：
  - SPJG 实现架构（`MaterializedViewRewriteRule` 系列）与 Calcite LARA 的算法对应关系
  - `StructInfo` 提取与 Calcite `MutableRel` 树的设计对比
  - 关系映射（`RelationMapping` / `SlotMapping`）与 Calcite `Mapping` 体系的对比
- **对比重点**：
  - 两者对 **compensation predicate 完备性**的处理差异（哪些谓词形式 Calcite 支持而 StarRocks 不支持，根因在哪）
  - Calcite LARA 的 aggregate function 变换规则集 vs StarRocks 的 aggregate rollup 支持范围
  - **算法正确性保证**：Calcite 有形式化证明（LARA 论文）的改写正确性，StarRocks 的正确性验证机制是什么

### 2. Join 改写能力对比

- **Calcite**：
  - `JoinUnifyRule` 对 Join 类型（inner/outer/semi/anti）的改写支持矩阵
  - Join 交换律/结合律在改写中的利用（`JoinCommuteRule` 与 MV 改写的协同）
  - Calcite 如何处理 **Join 顺序不一致**（MV 中 A JOIN B，query 中 B JOIN A）的场景
  - Outer Join 到 Inner Join 的等价变换在改写中的利用
- **StarRocks**：
  - View Delta Join（`ViewDeltaJoinRule`）的实现：FK/PK 约束的注册与校验机制
  - Derivable Join 的等价推导逻辑
  - Join 类型不匹配时的改写失败路径
- **对比重点**：
  - Calcite `JoinUnifyRule` 对 Join 变换的完备性 vs StarRocks 的 Join 改写覆盖范围
  - 两者对 **semi-join / anti-join** 的 MV 改写支持差异

### 3. 优化器集成架构对比

- **Calcite**：
  - `AbstractMaterializedViewRule` 作为 `RelOptRule` 的注入机制（rule-based 触发 vs cost-based 选择）
  - MV 改写在 Calcite planner（HepPlanner vs VolcanoPlanner）中的执行时机与优先级
  - Calcite 的 `RelOptMaterialization` 对象：MV 元数据的表示与注册机制
  - Lattice（格）结构：Calcite 对 Star Schema 的结构化建模与 MV 推荐的关系
- **StarRocks**：
  - MV 改写在 Cascades 优化器中的注入时机（`OptimizerTask` 的执行顺序）
  - `MvPlanContext` 缓存机制：MV 定义 SQL 的 plan 复用逻辑
  - MV 候选筛选机制（避免所有 MV 参与改写尝试的过滤策略）
- **对比重点**：
  - Calcite Lattice 结构对 StarRocks 的借鉴价值（是否适用于 OLAP 场景的 Star Schema MV 推荐）
  - 改写规则的执行模型差异：Calcite rule-firing vs StarRocks Cascades exploration phase 的 overhead 比较

### 4. 改写覆盖率的系统性对比

逐类分析两者的支持状态与差异根因：

| SQL Pattern | Calcite 支持状态 | StarRocks 支持状态 | 差异根因 |
|-------------|----------------|------------------|---------|
| SPJ（Select-Project-Join） | | | |
| SPJG（+ Group-by Aggregate） | | | |
| Aggregate with HAVING | | | |
| Window Function | | | |
| UNION ALL | | | |
| Subquery（相关/非相关） | | | |
| GROUPING SETS / ROLLUP / CUBE | | | |
| Multi-level Aggregation | | | |
| Outer Join MV | | | |
| MV on View | | | |
| Nested MV（MV on MV） | | | |
| COUNT DISTINCT / approx_count_distinct | | | |

### 5. 可观测性与调试支持

- **Calcite**：
  - `RelOptListener` 机制：改写过程的事件追踪
  - `ExplainLevel` 中的 MV 改写信息输出
- **StarRocks**：
  - `EXPLAIN` 中 MV 改写命中/失败的输出机制（`MaterializationContext.getStringInfo()`）
  - MV 改写 trace 的完整性与调试友好度
- **对比重点**：Calcite 的诊断机制对 StarRocks 改写调试工具链建设的参考价值

---

## 输出结构

### Part 1：算法架构对比图（文字描述）
用模块图（文字形式）描述两者改写框架的架构差异，突出核心算法组件的对应关系

### Part 2：能力矩阵对比表
覆盖上述所有维度，格式：

| 对比维度 | Calcite（主干） | StarRocks（主干） | 差距性质 | StarRocks 改进方向 |
|---------|--------------|-----------------|---------|-----------------|
| ... | ... | ... | 算法设计差异/实现完成度差距 | 短期patch/架构重构 |

### Part 3：Calcite LARA 算法中值得 StarRocks 直接借鉴的 Top 3 设计
每条给出：Calcite 的实现源码路径 → StarRocks 当前状态 → 具体移植/借鉴建议

### Part 4：StarRocks 在工程实现上相对 Calcite 的优势
Calcite 作为通用框架，在 OLAP 特化场景下（外表 MV、分区增量、湖仓加速）有哪些设计天花板，StarRocks 在这些方向上的优势

### Part 5：改写算法完备性提升的优先级建议
结合对比结论，给出 StarRocks 改写算法最值得优先补齐的 3 个 pattern，每个给出实现复杂度评估（参考 Calcite 对应实现的代码规模）

---

## 输出要求

- Calcite 侧结论锚定源码（`org.apache.calcite.rel.rules.materialize.*` 路径或具体类名）及相关学术论文（LARA、SPJG 原始论文标题+年份）
- StarRocks 侧结论锚定源码（类名/路径/Issue 编号）
- 差距性质区分"算法设计差异"与"实现完成度差距"
- 改进方向区分"短期可做（patch 级）"与"需要架构重构"
- 对算法正确性问题（改写可能产生错误结果的 case）给予特别标注
