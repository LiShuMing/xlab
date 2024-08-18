# 增量计算（Incremental View Maintenance, IVM）技术调研报告

> **目标读者**：具备数据库内核背景的研发工程师  
> **版本**：v1.0 · 2025-03  
> **文档状态**：Draft for Review

---

## 1. Executive Summary

增量视图维护（IVM）是数据库领域持续了三十余年的核心难题。其本质是：当基表数据发生变更（delta）时，能否以远低于全量重算的代价，将变更传播到下游物化视图。

**工业界现状（2025 Q1）**：

- **Snowflake Dynamic Table**（GA, 2023）：基于 Stream/Change Tracking 的批式 IVM，算子覆盖中等，最小 lag 1 分钟，非单调算子（含排名类 Window Function）仅支持部分场景，对 non-monotonic 查询严格限制 append-only changes，详见 SIGMOD 2023 论文 [Akidau et al.]；SIGMOD 2025 进一步发布 Delayed View Semantics (DVS) 形式化框架 [Sotolongo et al.]。
- **Databricks Materialized View**（Public Preview, 2025-10）：基于 Delta Lake 日志的增量刷新，依赖 Row Tracking + Deletion Vectors，支持 Window Function（需指定 PARTITION BY），FULL/RIGHT OUTER JOIN 均已支持；运行于 Serverless Pipeline，具备 cost-model 自动选择增量 vs 全量策略。
- **BigQuery Materialized View**（GA）：区分 Incremental MV 与 Non-incremental MV，前者支持 Smart Tuning（透明查询改写）但 SQL 语法受限；后者通过 `allow_non_incremental_definition=true` 解锁完整 SQL，但每次 full recompute；内部使用 sketch 存储 AVG/APPROX_COUNT_DISTINCT 等中间态。
- **StarRocks Async MV**（GA, v2.4+）：Partition-based 增量刷新（PCT, Partition Change Tracking），v4.1 引入 `refresh_mode=INCREMENTAL`，仅支持 append-only base table 操作；Issue #61789（2025-08）启动了基于 relational algebra 的真正行级 IVM 框架（IVMBasedMVRefreshProcessor），目标覆盖 Select/Project/Join/Aggregate/UnionAll。

**核心结论**：
1. 工业界 IVM 实现普遍以**分钟级 lag + 有限算子覆盖**为代价换取生产可用性；
2. 非单调算子（Window、`COUNT DISTINCT`、`EXCEPT`、自连接）的增量化在理论上存在**状态爆炸**瓶颈，多数引擎选择回退全量；
3. 学术界的 DBToaster / F-IVM / DBSP 给出了理论下界与代数框架，但工程落地仍有显著 gap；
4. 流批一体（Streaming + IVM）是最有潜力的演进方向，Snowflake DVS、Flink Changelog Stream 是目前最接近终态的两条路径。

---

## 2. IVM 理论基础

### 2.1 代数框架

IVM 的数学基础可以追溯到 1986 年 Blakeley、Larson、Tompa 的经典 SIGMOD 论文 *"Efficiently Updating Materialized Views"*，其核心思想是 **delta query**：

```
ΔV = Q(DB + ΔDB) - Q(DB)
```

对于关系代数中的 SELECT/PROJECT/FILTER，delta 是线性的，增量代价与 |ΔDB| 成正比。但对于 JOIN，delta 需要展开为：

```
Δ(R ⋈ S) = ΔR ⋈ S + R ⋈ ΔS + ΔR ⋈ ΔS
```

多表 JOIN 的 delta 展开会引入指数级数量的 auxiliary view，这是 DBToaster 采用**递归 delta（higher-order delta）**的动机。

#### 2.1.1 DBToaster（VLDB 2009 / VLDB Journal 2014）

Koch, Ahmad et al. 的 DBToaster 系统 [Koch et al., VLDB Journal 23(2):253–278, 2014] 通过对维护查询本身反复求 delta，将复杂查询编译为深度递归的增量函数（C++/Scala 代码）。

- 核心创新：对 delta query 再次 delta，即 **higher-order IVM**，消除扫描和 join，将每次更新开销降至接近 O(1)
- 适用场景：内存数据库 + 高频写入的 standing query（如算法交易）
- 工程局限：生成代码体积随 query 复杂度指数增长；不适合 OLAP 仓库中 TB 级 base table 的场景

#### 2.1.2 F-IVM（SIGMOD 2018 / VLDB Journal 2023）

Kara, Nikolic, Olteanu, Zhang 的 F-IVM [VLDB Journal, 2023, DOI:10.1007/s00778-023-00817-w] 结合了三个核心技术：
1. **Higher-order IVM**：将维护任务分解为 view tree 层级结构
2. **Factorized Computation**：在 key space 和 payload space 分别优化
3. **Ring Abstraction**：将聚合值抽象为 ring 元素，统一处理 SUM/COUNT/ML 目标函数

F-IVM 在实验中比 first-order IVM 和 DBToaster 快最多 **2 个数量级**，且内存占用显著更低。

#### 2.1.3 DBSP（PVLDB 2023 / VLDB Journal 2025）

Budiu, McSherry, Ryzhyk, Tannen 的 DBSP [PVLDB 16(7):1601–1614, 2023; VLDB Journal 2025 extended version] 提供了迄今最完整的 IVM 形式化框架：

1. 定义 **DBSP**（一种流式计算语言）来描述数据流上的计算
2. 将 IVM 问题转化为 DBSP 程序的增量化：对任意 DBSP 程序存在算法将其转为增量形式
3. 证明 SQL 和 Datalog 可以直接在 DBSP 之上实现，且所有基础原语都有高效增量实现

DBSP 的工程产物是 **Feldera**（原 DBSP 开源实现），已支持完整 SQL 的增量计算。

#### 2.1.4 动态 Yannakakis 算法（SIGMOD 2017 / VLDB Journal 2020）

Idris, Ugarte, Vansummeren et al. 的工作针对无环合取查询（acyclic conjunctive queries）给出了精确的复杂度下界：对于 q-hierarchical 查询，在 O(1) 更新时间和 O(1) 枚举延迟之间存在 fine-grained 复杂度 tradeoff，这在 SIGMOD 2024 Gems of PODS 演讲中被 Olteanu 重新总结。

### 2.2 单调 vs 非单调算子分类

| 算子类型 | 代表算子 | 增量化难度 | 原因 |
|----------|----------|------------|------|
| **单调算子** | SELECT, PROJECT, FILTER, UNION ALL, INNER JOIN, SUM/COUNT/MIN/MAX | 低-中 | 输入 INSERT → 输出 INSERT；delta 方向确定 |
| **伪单调算子** | LEFT/RIGHT/FULL OUTER JOIN | 中-高 | 右侧 INSERT 可能导致左侧 NULL 行变 non-NULL（retraction） |
| **非单调算子** | `COUNT DISTINCT`, `EXCEPT`/`MINUS`, `NOT EXISTS`, `PERCENT_RANK`, unbounded window frames | 高 | 输入 INSERT/DELETE 均可导致输出 INSERT 或 DELETE，需维护 auxiliary state |
| **非确定性算子** | `CURRENT_TIMESTAMP`, `RAND()`, `ANY_VALUE` | 不可增量 | 每次调用结果不同，无法 delta 传播 |

### 2.3 理论下界

Henzinger, Krinninger et al. 基于 Online Matrix-Vector Multiplication 猜想证明：对于一般性 join 查询，不存在同时满足 O(polylog n) 更新时间和 O(polylog n) 查询时间的 IVM 算法（除非该猜想为假）。

这意味着：**在通用 OLAP 工作负载中，完全避免全量重算在理论上不可行**。工程系统必须在算子覆盖范围、状态内存、更新延迟三者之间做 tradeoff。

---

## 3. 工业界现状

### 3.1 Snowflake Dynamic Table

**状态**：GA（2023）  
**文档**：[Supported queries](https://docs.snowflake.com/en/user-guide/dynamic-tables-supported-queries) · [Limitations](https://docs.snowflake.com/en/user-guide/dynamic-tables-limitations)  
**学术论文**：
- Akidau et al., *"What's the Difference? Incremental Processing with Change Queries in Snowflake"*, SIGMOD 2023, DOI:10.1145/3589776
- Sotolongo et al., *"Streaming Democratized: Ease Across the Latency Spectrum with Delayed View Semantics and Snowflake Dynamic Tables"*, SIGMOD 2025

#### 3.1.1 架构与增量机制

Dynamic Table 底层依赖两个原语：
- **Stream**：基于 micro-partition 的行级变更追踪对象，存储 `$ACTION`（INSERT/DELETE）+ `$ROW_ID` 元数据列，本质是 Snowflake Time Travel 的结构化视图
- **Change Tracking**：在 base table 上开启后，Snowflake 记录 micro-partition 层变更日志，Stream 的 offset 与表的 retention 策略绑定（默认 14 天，超期则 Stream 失效，强制全量重建）

增量刷新流程：
```
Base Table Change → Stream Delta → Incremental Merge → Dynamic Table
```

刷新策略：`TARGET_LAG = <interval>` 或 `DOWNSTREAM`（由下游 DT 反向驱动），最小精度 **1 分钟**。多个 Dynamic Table 构成 DAG，调度引擎保证拓扑序执行。

SIGMOD 2023 论文指出，Snowflake 的 IVM 对非单调查询**仅支持 append-only changes over monotonic queries**：

> "to provide consistent performance, we only support append-only changes over monotonic queries"
> — Akidau et al., SIGMOD 2023

#### 3.1.2 算子支持矩阵（来源：官方文档，2025-03）

| 算子/特性 | 增量刷新 | 全量刷新 | 备注 |
|-----------|----------|----------|------|
| SELECT/PROJECT/FILTER | ✅ | ✅ | |
| GROUP BY + SUM/COUNT/MIN/MAX/AVG | ✅ | ✅ | |
| INNER JOIN / CROSS JOIN | ✅ | ✅ | 多表均支持 |
| OUTER-EQUI JOIN | ✅ | ✅ | |
| LEFT/RIGHT/FULL OUTER JOIN | ✅（有限制） | ✅ | 不支持两侧为同表；不支持非等值谓词 |
| UNION ALL | ✅ | ✅ | |
| UNION（DISTINCT） | ✅ | ✅ | 行为等价于 UNION ALL + SELECT DISTINCT |
| Window Functions | ✅（有限制） | ✅ | **不支持** PERCENT_RANK/DENSE_RANK/RANK + sliding frame；不支持 ANY_VALUE |
| DISTINCT | ✅ | ✅ | |
| WITH (CTE) | ✅ | ✅ | 不支持 WITH RECURSIVE |
| Subquery (WHERE EXISTS 等) | ❌ | ✅ | |
| PIVOT / UNPIVOT | ❌ | ❌ | 两种模式均不支持 |
| SAMPLE / TABLESAMPLE | ❌ | ❌ | |
| Set Operators (MINUS/EXCEPT/INTERSECT) | ❌ | ✅ | |
| External Functions | ❌ | ❌ | |
| VOLATILE UDF | ❌ | ✅ | |
| ML/LLM Functions (Cortex) | ✅（仅 SELECT 子句） | ✅ | 注：AI 函数支持增量，但非确定性结果 |
| CURRENT_TIMESTAMP 等 | ✅（仅 WHERE/HAVING/QUALIFY） | ✅（仅 WHERE/HAVING/QUALIFY） | |
| Geospatial Types | ❌ | ✅ | |
| Structured Data Types | ❌ | ❌ | |

#### 3.1.3 核心 Limitations

1. **Stream 失效风险**：当 Stream 的 offset 超过 base table 的 `MAX_DATA_EXTENSION_TIME_IN_DAYS`（默认与 `DATA_RETENTION_TIME_IN_DAYS` 绑定），Dynamic Table 进入 stale 状态，必须完整重建（DROP + CREATE），存在数据新鲜度 SLA 断裂风险
2. **跨 Database DAG 不支持**：Dynamic Table 不能跨 database 建立依赖链
3. **不支持 External Table / Stream / Materialized View 作为 source**：`Dynamic tables don't support sources that include directory tables, external tables, streams, and materialized views`
4. **最小 lag 1 分钟**：无法满足秒级近实时场景
5. **计算成本不透明**：刷新消耗 Virtual Warehouse credits，无细粒度增量 vs 全量代价对比接口
6. **非等值 OUTER JOIN 不支持增量**：如 `LEFT JOIN ON a.date BETWEEN b.start AND b.end`
7. **DAG 级别一致性弱**：不同节点刷新存在时间窗口，无法保证 DAG 全局原子性

---

### 3.2 Databricks Materialized View

**状态**：Public Preview（截至 2025-10-10 文档注明）  
**文档**：[Incremental refresh for materialized views](https://docs.databricks.com/gcp/en/optimizations/incremental-refresh)

#### 3.2.1 架构与增量机制

Databricks MV 的增量能力建立在 **Delta Lake** 的三个底层特性上：

1. **Change Data Feed (CDF)**：Delta 表的行级变更日志，记录 `_change_type`（insert/update_preimage/update_postimage/delete）
2. **Row Tracking**：为每行分配稳定的 `_row_id`，是 JOIN 增量刷新的必要条件（文档中标注 `*` 的算子均要求 Row Tracking）
3. **Deletion Vectors**：软删除机制，避免 full file rewrite，降低增量刷新的 I/O 放大

所有刷新运行于 **Serverless Pipeline**（基于 Spark Structured Streaming 内核），引擎通过 **cost model** 自动选择以下增量策略：

| 刷新技术 | 含义 |
|----------|------|
| `ROW_BASED` | 基于 CDF 行级变更的增量更新 |
| `PARTITION_OVERWRITE` | 受影响分区的增量覆盖写 |
| `WINDOW_FUNCTION` | Window Function 的增量路径（需 PARTITION BY） |
| `APPEND_ONLY` | 仅追加场景的优化路径 |
| `GROUP_AGGREGATE` | 聚合查询增量 |
| `GENERIC_AGGREGATE` | 通用聚合路径 |
| `FULL_RECOMPUTE` | 回退全量（非增量） |
| `NO_OP` | 无变化，跳过 |

#### 3.2.2 算子支持矩阵

| 算子 | 增量支持 | 备注 |
|------|----------|------|
| SELECT/PROJECT（确定性函数 + immutable UDF） | ✅* | 需 Row Tracking |
| GROUP BY | ✅ | |
| WITH (CTE) | ✅ | |
| UNION ALL | ✅* | 需 Row Tracking |
| WHERE/HAVING Filter | ✅* | 需 Row Tracking |
| INNER JOIN | ✅* | 需 Row Tracking |
| LEFT OUTER JOIN | ✅* | 需 Row Tracking |
| FULL OUTER JOIN | ✅* | 需 Row Tracking |
| RIGHT OUTER JOIN | ✅* | 需 Row Tracking |
| Window Functions（OVER + PARTITION BY） | ✅ | **必须指定 PARTITION BY** |
| QUALIFY | ✅ | |
| Non-deterministic time functions（WHERE 子句） | ✅ | `current_date()` 等仅限 WHERE |
| Non-Delta sources（volumes, external locations） | ❌ | 不支持增量 |
| Row filters / Column masks | ❌ | 不支持增量 |

相比 Snowflake，Databricks MV 的重大优势：**支持 FULL/RIGHT OUTER JOIN 的增量**，以及 **Window Function（带 PARTITION BY）的增量路径**。

#### 3.2.3 核心 Limitations

1. **Preview 状态**：截至文档日期（2025-10-10）仍为 Public Preview，生产稳定性存疑
2. **仅限 Delta 数据源**：External Table（S3/GCS 原始文件）、Foreign Catalog 不支持增量
3. **Row Tracking 依赖**：大量算子的增量路径需要 base table 开启 Row Tracking（Delta 特性），老旧表迁移成本较高
4. **不支持嵌套 MV**：MV 不能以另一个 MV 为 source（BigQuery 同样限制）
5. **Kafka 等流式 source 不支持**：文档明确指出不应对"records should only be processed once"的 source 使用 MV，推荐 Streaming Table
6. **Full refresh 陷阱**：删除了 source 数据后 full refresh 无法恢复，可能导致 MV 数据永久丢失

---

### 3.3 BigQuery Materialized View

**状态**：GA  
**文档**：[Introduction to materialized views](https://cloud.google.com/bigquery/docs/materialized-views-intro)

#### 3.3.1 架构与增量机制

BigQuery MV 区分两种类型：

**Incremental MV**（默认）：
- 底层基于 BigQuery 的 **table storage changelog**（类似 Delta CDF），当 base table 发生 INSERT 时，自动将增量追加到 MV
- 若 base table 发生 DELETE/UPDATE（如 DML 语句或分区删除），则该 MV 的对应部分失效，查询时自动从 base table 读取最新数据（query-time merge）
- 支持 **Smart Tuning**：当查询可被 MV 部分覆盖时，自动 reroute，减少扫描字节数

**Non-incremental MV**（需 `allow_non_incremental_definition = true`）：
- 支持完整 SQL 语法（几乎无限制）
- 每次刷新全量重算，不支持 Smart Tuning

内部存储优化：`AVG`、`ARRAY_AGG`、`APPROX_COUNT_DISTINCT` 的聚合结果以 **sketch（中间态 BYTES）** 存储，而非最终值，支持增量 merge 而无需保留明细数据。

#### 3.3.2 核心 Limitations

1. **Incremental MV SQL 语法严格受限**：仅支持 `SELECT`, `FROM`（单表 + 聚合），不支持多表 JOIN、Window Function、EXCEPT/INTERSECT（具体以 [Create materialized views](https://cloud.google.com/bigquery/docs/materialized-views-create) 为准）
2. **不支持嵌套 MV**：`Materialized views cannot be nested on other materialized views`（Logical view reference 为 Preview 状态）
3. **不支持 External / Wildcard Table、Snapshots 作为 source**
4. **组织隔离限制**：`A materialized view must reside in the same organization as its base tables`
5. **MV 定义不可修改**：`The materialized view SQL cannot be updated after the materialized view is created`，需 DROP + CREATE
6. **跨云 JOIN 限制**：MV over Amazon S3 BigLake 表的数据不可直接与 BigQuery 原生表 JOIN
7. **Non-incremental MV 无 Smart Tuning**：牺牲了 query rewrite 的核心价值

---

### 3.4 StarRocks Async Materialized View

**状态**：GA（v2.4+），INCREMENTAL 模式（v4.1+，Roadmap）  
**文档**：[Asynchronous materialized views](https://docs.starrocks.io/docs/using_starrocks/async_mv/Materialized_view/) · [Feature Support](https://docs.starrocks.io/docs/using_starrocks/async_mv/feature-support-asynchronous-materialized-views/) · [GitHub Issue #61789](https://github.com/StarRocks/starrocks/issues/61789)

#### 3.4.1 架构与增量机制

StarRocks 的 MV 增量刷新分三个层次：

**Layer 1 — PCT（Partition Change Tracking，GA）**：
- 以 partition 为最小刷新粒度，当 base table 某分区数据变化时，只刷新 MV 的对应分区
- 刷新本质是 `INSERT OVERWRITE`（对受影响分区全量重算），非真正的行级增量
- 优点：大幅降低相比全量刷新的资源消耗；缺点：受限于 partition 对齐，MV 的 partition key 必须与 base table 的 partition 表达式一致

**Layer 2 — INCREMENTAL 模式（v4.1，append-only，GA）**：
- `refresh_mode = INCREMENTAL` 或 `AUTO`（自动判断）
- 仅支持 **append-only** 操作：base table 有 UPDATE/MERGE/OVERWRITE 时，INCREMENTAL 模式刷新失败（AUTO 回退到 PCT）
- 支持算子：`Select/Project/Filter/Join/Aggregate/UnionAll`（文档注明"generally support incremental refresh"）
- 限制：聚合后 Join 和 UNION 后聚合的组合支持，但部分 operator combination 有 limitations

**Layer 3 — IVMBasedMVRefreshProcessor（In Progress）**：
- Issue #61789（2025-08 提出）明确了当前 PCT 的不足：partition 强耦合、GROUP BY key 过多时 OOM、不支持非分区表上的分区 MV 等
- 目标：构建基于 relational algebra 的行级增量计算框架，支持 Iceberg append-only（Phase 1）和 retractable changes via Iceberg V3 CDC（Phase 2）

#### 3.4.2 Query Rewrite（透明改写，GA）

这是 StarRocks MV 相比竞品的核心差异化能力：
- 支持 SPJG-type（Scan-Filter-Project-Join-Aggregate）透明改写
- v2.5+ 默认开启（`enable_materialized_view_rewrite = true`）
- 支持单表、多表 JOIN、聚合、UNION、嵌套 MV 等多种改写场景
- 外部表 MV（Hive/Iceberg catalog）同样支持查询改写

---

## 4. 横向对比矩阵

| 维度 | Snowflake Dynamic Table | Databricks MV | BigQuery MV | StarRocks Async MV |
|------|------------------------|---------------|-------------|-------------------|
| **状态** | GA | Public Preview | GA | GA（IVM 框架 In Progress） |
| **IVM 底层机制** | Stream（micro-partition 变更日志） | Delta CDF + Row Tracking + Deletion Vectors | Table storage changelog + sketch | PCT（partition-level overwrite）+ append-only row delta |
| **最小刷新延迟** | 1 分钟 | 秒级（Serverless pipeline） | 5 分钟（自动刷新间隔，可更短） | 秒级（ASYNC 模式，data change 触发） |
| **INNER JOIN 增量** | ✅ | ✅* | ❌（incremental MV 受限） | ✅（append-only） |
| **OUTER JOIN 增量** | ✅（等值，有限制） | ✅*（FULL/RIGHT/LEFT 均支持） | ❌ | ✅（append-only，有限制） |
| **Window Function 增量** | ✅（部分，无 sliding frame RANK） | ✅（需 PARTITION BY） | ❌ | ✅（部分，append-only） |
| **COUNT DISTINCT 增量** | ❌（回退全量） | ❌ | ✅（APPROX_COUNT_DISTINCT via sketch，非精确） | ❌（回退全量） |
| **流式数据源** | ❌（Kafka 等不支持） | ❌（推荐 Streaming Table） | ❌ | ✅（Routine Load/Stream Load 触发 ASYNC refresh） |
| **透明查询改写** | ❌ | ❌ | ✅（仅 Incremental MV） | ✅（核心能力） |
| **外部表支持** | ❌（不能作 source） | ❌（增量）/✅（全量） | ✅（BigLake，增量受限） | ✅（Hive/Iceberg catalog，仅定期刷新） |
| **DAG/嵌套 MV** | ✅（跨 Database 不支持） | ✅（MV 可做 source） | ❌（不能嵌套） | ✅（嵌套 MV 支持） |
| **一致性保证** | 单表刷新原子；DAG 无全局原子 | Pipeline 级别事务 | 查询时 merge 保证新鲜度 | 单次刷新原子；跨 MV 无保证 |
| **成本模型** | Virtual Warehouse credit；无细粒度估算 | Serverless 按 DBU；cost model 自动选增量/全量 | On-demand bytes scanned；sketch 存储优化 | BE 资源；partition_refresh_number 控制批次 |
| **开源/闭源** | 闭源 | 闭源 | 闭源 | 开源（Apache 2.0） |

`*` = 需要 Row Tracking 开启

---

## 5. 技术瓶颈深度分析

### 5.1 非单调算子的本质困境

Snowflake SIGMOD 2023 论文直接点明了核心问题：

对于非单调算子，输入的 INSERT 可能导致输出 DELETE（retraction），输入的 DELETE 可能导致输出 INSERT。计算完整输出 delta 与重新计算 full query 的复杂度等价：

```
non-monotonic_op(base + Δinsert + Δdelete) ≠ 
  non-monotonic_op(base) + Δ_output_insert - Δ_output_delete
```

以 `COUNT DISTINCT` 为例：删除一个值时，只有当该值在 base 中 **唯一** 时，输出才减少 1；判断是否唯一需要扫描整个 group，时间复杂度 O(|base group|)。

解决方案只有两类：
1. **接受近似**：用 HyperLogLog/Theta Sketch 替代精确计数（BigQuery 的做法），牺牲精度换可增量性
2. **维护 auxiliary state**：为每个 group 维护 value → count 的 hashmap（Flink 的做法），以 O(|distinct values|) 内存换 O(1) 更新

### 5.2 Retraction（撤回）问题

真正的行级 IVM 必须支持 **Changelog Stream**，即数据流中包含：
- `+I`（Insert）
- `-D`（Delete）
- `-U` / `+U`（Update = Delete + Insert）

Flink SQL 的 Changelog Mode 是目前工业界最成熟的 retraction 实现。其核心思路是让每个算子同时处理正向和负向变更：

```
Aggregate(-U[key, old_val]) → 撤回旧聚合值
Aggregate(+U[key, new_val]) → 插入新聚合值
```

**工程代价**：
- 每个有状态算子（GroupBy、Window）需要维护完整的 state backend（通常为 RocksDB）
- State 大小与 distinct key 数量成正比，不受控的 key 爆炸会导致 OOM
- 在 OLAP 仓库的 shared-nothing 存储架构中内嵌 state backend，架构侵入性极强

### 5.3 State 爆炸与内存管理

StarRocks Issue #61789 明确记录了当前 PCT 刷新在 MV 含大量 GROUP BY key 时出现 OOM 的问题（`Refresh MV OOM when MV's base table contains too much data`）。

根本原因：PCT 的"增量"是分区级别的 INSERT OVERWRITE，刷新任务需要将整个受影响分区的数据全部 load 到内存计算。当 key 维度爆炸时，中间 aggregation 结果无法装入 BE 内存。

真正的行级 IVM 通过只处理 |Δ| 大小的 delta 可以缓解这个问题，但在含复杂 JOIN 的查询中，delta 可能因为 join amplification 而膨胀。

### 5.4 新鲜度 vs 成本的 Pareto 前沿

|  | 高新鲜度 | 低成本 |
|--|---------|--------|
| **全量刷新** | ❌（批次间有 lag） | ❌（每次全量扫描） |
| **分区级增量（PCT）** | ✅（受分区粒度影响） | ✅（只刷新变化分区） |
| **行级增量（IVM）** | ✅（最细粒度） | ✅（只处理 delta 行） |
| **流式处理（Flink）** | ✅✅（毫秒级） | ❌（持续运行，状态资源常驻） |

在没有流式 runtime 支撑的纯批架构下，高新鲜度与低成本之间存在结构性张力：刷新频率越高，资源消耗越大。

### 5.5 一致性与正确性保证

多级 MV DAG 的刷新一致性是一个未被充分解决的问题：
- Snowflake 承认 DAG 中不同节点的刷新存在时间窗口
- BigQuery 通过 query-time merge 保证单个 MV 的查询新鲜度，但嵌套不支持
- Databricks Pipeline 提供了 dataset 级别的刷新原子性

Snowflake SIGMOD 2025 论文（Sotolongo et al.）专门引入了 **Delayed View Semantics (DVS)** 框架来形式化这个问题，提出了 transaction isolation 的扩展以支持流式应用的 invariant 维护。

---

## 6. 可行方案探讨

### 6.1 方案一：扩展 Changelog Stream 模型（IVM + Retraction）

**思路**：在 OLAP 引擎内部引入 retraction-aware 的增量算子，仿照 Flink SQL 的 Changelog Mode。

**优点**：
- 理论上可支持所有 SQL 算子的增量化（含 Window、COUNT DISTINCT）
- 延迟可降至秒级甚至毫秒级

**工程难点**：
- 需要在列存 BE（StarRocks 的 segment/tablet 体系）内嵌入行级 state backend，架构侵入性极强
- Retraction 在复杂 JOIN 下可能产生比原始 delta 大得多的 auxiliary state，需要精心设计 state compaction 策略
- 与当前 Compaction/Vectorized Execution 路径的集成需要大量工程

**参考**：StarRocks Issue #61789 Phase 2（利用 Iceberg V3 CDC 支持 retractable changes）

**Gap 分析**：学术上 DBSP 已给出完整框架，Feldera 已有 prototype 实现；但 StarRocks 需要在 MPP OLAP 的分布式执行框架上重新实现一套 stateful operator，工作量约 12-18 个月。

### 6.2 方案二：分层 Delta 架构（Hot/Cold）

**思路**：将增量写入维护在独立的 **delta partition** 中，查询时做 union-merge（类似 LSM-Tree），定期 compaction 合并到 base MV。

```
base_mv_partition (cold, full) ∪ delta_mv_partition (hot, recent Δ)
→ query: merge-on-read
→ background: compaction (delta → base)
```

**优点**：
- 工程改动相对小，与 StarRocks 现有 Compaction 体系兼容
- 写路径简单：delta 只追加不修改，天然 append-only
- 对 retraction 友好：DELETE 可标记为 tombstone 行，compaction 时合并消除

**缺点**：
- 查询时 merge 开销（但 StarRocks 向量化执行擅长此类 merge sort）
- Compaction 调度的 cost 不可忽视，需要在 freshness 和资源消耗间调整 compaction 频率
- 对含 `DISTINCT` 的查询，delta 层与 base 层的去重在 merge-on-read 时仍需扫描两层

**参考**：ClickHouse `ReplacingMergeTree` / `AggregatingMergeTree` 采用类似思路

### 6.3 方案三：近似增量（Sketch-based IVM）

**思路**：对 `COUNT DISTINCT`、`PERCENTILE`、`TOP-K` 等非单调聚合算子，引入概率数据结构（**HyperLogLog**, **Theta Sketch**, **T-Digest**），将精确语义替换为近似语义，换取可增量性。

**近似数据结构对比**：

| 结构 | 目标算子 | 误差率 | 增量合并 |
|------|----------|--------|----------|
| HyperLogLog | COUNT DISTINCT | ~1-2% | ✅（register merge） |
| Theta Sketch（Apache DataSketches） | COUNT DISTINCT（更精确） | ~0.5% | ✅ |
| T-Digest | PERCENTILE/MEDIAN | 可控 | ✅ |
| Count-Min Sketch | Top-K/Frequency | ~1% | ✅ |

BigQuery 的 `APPROX_COUNT_DISTINCT` 和 StarRocks 的 `approx_count_distinct`（HLL）已是这个思路的落地，但尚未与 MV 增量刷新深度集成。

**StarRocks 落地路径**：将 HLL/Theta Sketch 列类型纳入 Incremental MV 的合法聚合函数，使含 DISTINCT 语义的 MV 可以走增量路径，代价是约 1% 的精度损失。

**Gap 分析**：工程改动中等，主要在 MV 刷新的 merge 算子中增加 sketch merge 路径，约 2-3 个月。

### 6.4 方案四：Optimizer 驱动的自适应增量（Partial IVM）

**思路**：在 Query Optimizer 阶段，通过 relational algebra 等价变换，将 SQL 查询分解为：
- **可增量子树**：走行级 delta 计算
- **不可增量子树**：仅对 |Δ| 大小的 delta 数据重算（而非全表重算）

这是比全量刷新更精细的"partial full refresh"：即使不能做真正的 IVM，也比对全表重算省很多。

**Cost Model 关键**：Optimizer 需要准确估算 `|Δ|/|base|` 比率。当 delta 较小时，partial refresh 接近 IVM；当 delta 较大（如批量导入）时，自动 fallback 到全量。

**参考**：DBToaster 的核心思想；Databricks MV 的 cost model 自动选择增量/全量策略；StarRocks Issue #61789 Phase 2。

**StarRocks 落地路径**：
1. 在 MV refresh optimizer 中实现 `partial_delta_scan`（只读取 base table 中变化的 delta 行）
2. 对可增量的算子（SPJ）走 delta 路径；对不可增量算子（DISTINCT、Window）仅对 delta 数据重算
3. 合并 delta 计算结果与现有 MV 数据（需要支持 retraction 或依赖 append-only 约束）

### 6.5 方案五：流批一体（Native Streaming IVM）

**思路**：将 StarRocks 的 MV 刷新与流式 source（Kafka/Pulsar）直接打通，基于 Routine Load 的 CDC 消费，实时触发行级 MV 维护，延迟降至秒级。

**现有基础**：
- StarRocks 的 Primary Key 表已支持 partial update，Merge-on-Read 语义可视为简化版 retraction
- Routine Load 已实现 Kafka → StarRocks 的 CDC 导入
- 同步 MV（Rollup）在单表 + 单次写入时实现了真正的同步行级更新

**目标**：将同步 MV 的实时更新语义扩展到异步 MV（多表 JOIN + 复杂聚合），打通 Kafka CDC → Async MV 的完整增量链路。

**Gap 分析**：这是最激进也最有价值的方向，需要将 Flink Changelog Mode 的增量算子内置到 StarRocks 的 Pipeline Executor 中，预计 18-24 个月。

---

## 7. 对 StarRocks 的启示与建议

### 7.1 近期（0-6 个月）：低成本高收益

1. **Sketch-based IVM（方案三）**：优先落地 HLL/Theta Sketch 与 Incremental MV 的集成，解锁含 DISTINCT 语义的 MV 增量路径；预期工程量 2-3 个月
2. **Cost Model 增强**：实现 MV 刷新的增量 vs PCT vs 全量的三路代价估算，类似 Databricks 的自动选择机制；预期工程量 1-2 个月
3. **Partial Delta Scan（方案四雏形）**：对不可增量算子，实现仅扫描 base table delta 部分的优化，而非全表重算

### 7.2 中期（6-12 个月）：扩展算子覆盖

4. **基于 Iceberg V2/V3 的行级 IVM（Issue #61789 Phase 1）**：利用 Iceberg IncrementalScan API 实现 append-only 场景下的真正行级增量；重点支持 Lakehouse 场景（Iceberg 外表的 MV 刷新）
5. **分层 Delta 架构（方案二）**：为 non-partition 表引入 delta segment + merge-on-read 路径，解除当前 MV 对 partition 对齐的强依赖

### 7.3 长期（12-24 个月）：流批一体

6. **Retraction-aware 增量算子（方案一）**：引入 Changelog Stream 语义，支持含 UPDATE/DELETE 的 base table 上的复杂 MV 增量维护；与 Primary Key 表的 Merge-on-Read 机制深度集成
7. **Native Streaming IVM（方案五）**：打通 Kafka CDC → Async MV 的完整增量链路，将 MV 刷新延迟从分钟级降至秒级

### 7.4 与学术界的对接建议

- **DBSP 框架**（Budiu et al., PVLDB 2023）给出了任意 SQL 查询的增量化算法，其核心算法可以直接指导 StarRocks IVM operator 的实现，建议 deep read 其 VLDB Journal 2025 extended version
- **F-IVM**（Kara et al., VLDB Journal 2023）的 factorized computation 思路对多表 JOIN MV 的增量优化有直接参考价值
- Snowflake 在 SIGMOD 2025 发表的 **Delayed View Semantics** 形式化框架是目前工业级 IVM 语义规范的最新进展，建议参考其 transaction isolation 扩展

---

## 8. 参考资料

### 学术论文

| 论文 | 会议/期刊 | 年份 | 核心贡献 |
|------|-----------|------|----------|
| Blakeley, Larson, Tompa. *Efficiently Updating Materialized Views* | SIGMOD | 1986 | Delta query 基础理论 |
| Ahmad, Koch. *DBToaster: A SQL Compiler for High-Performance Delta Processing* | PVLDB | 2009 | Higher-order IVM 编译器 |
| Koch et al. *DBToaster: Higher-order delta processing for dynamic, frequently fresh views* | VLDB Journal 23(2):253–278 | 2014 | DBToaster 完整论文 |
| Idris, Ugarte, Vansummeren. *The Dynamic Yannakakis Algorithm* | SIGMOD | 2017 | 无环查询 IVM 复杂度下界 |
| Kara et al. *Incremental View Maintenance with Triple Lock Factorization Benefits (F-IVM)* | SIGMOD | 2018 | F-IVM 基础论文 |
| Kara, Nikolic, Olteanu, Zhang. *F-IVM: Analytics over Relational Databases under Updates* | VLDB Journal | 2023 | F-IVM 完整论文 DOI:10.1007/s00778-023-00817-w |
| Budiu, McSherry, Ryzhyk, Tannen. *DBSP: Automatic Incremental View Maintenance for Rich Query Languages* | PVLDB 16(7):1601–1614 | 2023 | 通用 IVM 形式化框架 |
| Budiu et al. *DBSP: automatic incremental view maintenance for rich query languages* | VLDB Journal | 2025 | DBSP extended version DOI:10.1007/s00778-025-00922-y |
| Akidau et al. *What's the Difference? Incremental Processing with Change Queries in Snowflake* | SIGMOD (Proc. ACM Manag. Data 1(2):196) | 2023 | Snowflake Stream/CHANGES 实现，DOI:10.1145/3589776 |
| Sotolongo, Mills, Akidau et al. *Streaming Democratized: Ease Across the Latency Spectrum with Delayed View Semantics and Snowflake Dynamic Tables* | SIGMOD Industry | 2025 | DVS 形式化 + Dynamic Table 大规模运营经验，arXiv:2504.10438 |

### 官方文档

| 资源 | 链接 |
|------|------|
| Snowflake Dynamic Table Supported Queries | https://docs.snowflake.com/en/user-guide/dynamic-tables-supported-queries |
| Snowflake Dynamic Table Limitations | https://docs.snowflake.com/en/user-guide/dynamic-tables-limitations |
| Databricks MV Incremental Refresh | https://docs.databricks.com/gcp/en/optimizations/incremental-refresh |
| BigQuery MV Introduction | https://cloud.google.com/bigquery/docs/materialized-views-intro |
| StarRocks Async MV Docs | https://docs.starrocks.io/docs/using_starrocks/async_mv/Materialized_view/ |
| StarRocks Feature Support: Async MV | https://docs.starrocks.io/docs/using_starrocks/async_mv/feature-support-asynchronous-materialized-views/ |
| StarRocks CREATE MATERIALIZED VIEW | https://docs.starrocks.io/docs/sql-reference/sql-statements/materialized_view/CREATE_MATERIALIZED_VIEW/ |

### GitHub Issues / PRs

| 资源 | 链接 |
|------|------|
| StarRocks Issue #61789: Incremental MV Refresh (IVMBasedMVRefreshProcessor) | https://github.com/StarRocks/starrocks/issues/61789 |

---

*报告生成时间：2025-03 | 文档版本：v1.0 | 如有内容更新请以各引擎最新官方文档为准*
