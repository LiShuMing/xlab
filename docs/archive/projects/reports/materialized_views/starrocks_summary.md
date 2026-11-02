# StarRocks Materialized View 

---

## 一、MV 整体理解

MV 工作的核心价值在于**"复用"**：最大化利用内核引擎的优势，解决上层业务的"重复性"问题。这决定了 MV 工作的两个特性：

- **距离业务近**：使用场景、使用方式多，参数暴露多，使用技巧较多，用好需要一定心智负担；
- **与内核引擎耦合深**：稍有使用不当，容易暴露性能问题。

---

## 二、MV 分类与整体框架

StarRocks 的 MV 分为两类：**同步 MV（Sync MV / Rollup）** 和 **异步 MV（Async MV）**。

> 官方文档入口：
> - [Synchronous Materialized View (Rollup)](https://docs.starrocks.io/docs/using_starrocks/Materialized_view-single_table/)
> - [Asynchronous Materialized View](https://docs.starrocks.io/docs/using_starrocks/async_mv/Materialized_view/)
> - [MV SQL Reference](https://docs.starrocks.io/docs/category/materialized-view/)

---

### 2.1 同步 MV（Sync MV）

**核心逻辑：**
类似 Table 的 Index 构建（原名 RollupIndex），复用了 SchemaChanging（刷新存量历史数据）+ TabletSink 实时导入（新增数据）的能力，保障 MV 与基表在同一事务中提交，实时可见。

**现状：** 基本处于维护状态，仍有少量用户在用（如 kaspi），不时发现 bug。

**功能：**
- 仅支持单表（projection 或聚合）；
- 支持通用聚合函数、Where 表达式、Limit 表达式；
- 支持存算一体、存算分离（v3.4.0+）。

**局限：**
- 数据分布（分区、分桶）和生命周期与基表绑定；
- 无法支持多表复杂 Query 场景。

---

### 2.2 异步 MV（Async MV）

> 从 v2.4 开始支持，支持多表 Join、更多聚合函数，刷新可手动/周期/事件触发。

#### 2.2.1 核心刷新机制

| 机制 | 说明 | 状态 |
|---|---|---|
| **PCT**（Partition Change Tracking） | 基于分区变化的分区级增量刷新，目前主流刷新方式 | 生产可用 |
| **IVM**（Incremental View Maintenance） | 基于 Delta（行级）的增量刷新，目前处于 MVP 实验阶段，支持 Iceberg/Paimon | 实验阶段 |

> IVM 相关 Issue：[#61789](https://github.com/StarRocks/starrocks/issues/61789)

IVM 的核心思路：以 Time-Varying Relation（TVR）对基表变化进行版本化建模，做行级 Delta 传播，而非 PCT 的分区级全量覆写。IVM 成熟后，可重新思考当前 MV 创建约束（如是否强制要求基表到 MV 的分区映射关系），拓展 MV 的场景边界。

---

#### 2.2.2 MV 创建

> 文档：[Create a Partitioned Materialized View](https://docs.starrocks.io/docs/using_starrocks/async_mv/use_cases/create_partitioned_materialized_view/)

当前创建约束（基于 PCT）：
- MV 与基表之间必须存在可推导的**分区映射关系**（1:1、上卷、下钻），FE 侧可推导，否则无法支持分区级刷新；
- 支持 Range 和 List 分区类型的基表；
- **不支持**同时含 Range + List 混合分区类型的基表；
- 支持多事实表分区级增量刷新（多表 Join/Union，按天增量调度刷新）；
- 目前创建 MV 仍要求基表的分区列出现在 MV 的最终输出列中，否则无法创建。

---

#### 2.2.3 MV 改写（Query Rewrite）

> 文档：[Asynchronous MV - Query Rewrite](https://docs.starrocks.io/docs/using_starrocks/async_mv/Materialized_view/)

支持的改写能力：
- **基于 SPJG 的改写**（核心路径）
- **时效性补偿改写**（staleness-based compensation）
- **基于 UK/FK Constraint 的冗余 Table 裁剪**
- **View Based MV Rewrite**（视图作为改写基础）
- **基于文本的改写**（Text-based rewrite）
- **聚合下推的改写**
- **时序场景改写**

---

#### 2.2.4 MV 刷新

> 文档：[REFRESH MATERIALIZED VIEW](https://docs.starrocks.io/docs/sql-reference/sql-statements/materialized_view/REFRESH_MATERIALIZED_VIEW/)

- **PCT 刷新**：支持各种数据源（Native Table、Hive、Iceberg、Paimon 等）；
- **IVM 增量刷新**：目前支持 Iceberg、Paimon（实验阶段）；
- 默认开启 Spill；
- 支持 Resource Group / Warehouse 资源隔离；
- 刷新粒度由 `partition_refresh_number` 控制（v3.3 后默认为 1，即逐分区刷新）。

---

#### 2.2.5 MV 调度

复用 Task/TaskRun 调度管理体系：
- **Task**：对应一个 MV；
- **TaskRun**：MV 一次刷新的最小单元，单次刷新可能拆分为多个 TaskRun（由 `partition_refresh_number` 决定）；
- 底层基于 `ScheduledExecutorService.scheduleAtFixedRate` 按定义周期触发；
- 全局维护一个 `TaskRunFIFOQueue`，策略为 FIFO，保障全局刷新公平调度。

调度方式：`MANUAL` / `ASYNC`（事件式，目前仅能感知 NativeTable 基表变化）/ `PERIODIC`（周期调度）。

---

#### 2.2.6 可观测性

> 文档：[SHOW MATERIALIZED VIEWS](https://docs.starrocks.io/docs/sql-reference/sql-statements/materialized_view/SHOW_MATERIALIZED_VIEW/)

**刷新侧：**
- `information_schema.task_runs`
- `information_schema.materialized_views`
- `SHOW MATERIALIZED VIEWS`
- MV Metrics / Profile 中的 MV 指标

**改写侧：**
- `TRACE MV LOGS <query>`
- Profile 中的 MV 改写指标
- MV Metrics

---

#### 2.2.7 外围功能

- **MV 与 SchemaChange 的兼容处理**
- **MVActiveChecker**：后台任务，默认开启，自动检测非手动 inactive 的 MV 并尝试 re-active（处理基表 recreate 或 schema change 导致的 inactive 场景）；
- **测试体系**：SQL-Tester、StarRocksTest、MVTestFramework。

---

## 三、已有问题、需求与思考

### 3.1 MV 支持边界

- **创建约束过强**：目前创建 MV 需要在 Query 中将基表分区列作为最终输出列，能否在确保基表→MV 为单射映射的前提下简化此约束？
- **分区类型统一**：OlapTable 希望统一 Range/List 分区，MV 理论上也可以跟进支持更通用的分区映射；
- **IVM 成熟后的重构方向**：当 IVM 成熟后，可重新思考创建约束——例如允许非分区基表创建分区 MV。此时需重新设计：
  - 如何进行 Query Rewrite？
  - 如何在 PCT 和 IVM 之间动态切换（参考 BigQuery MV 和 Snowflake Dynamic Table 的设计）？
- **MV 与基表生命周期解耦**：目前这块遗漏问题较多，暂未形成统一的产品设计，需重点关注。

---

### 3.2 MV 改写增强

**改写完备性问题：**
- 当前 SPJG 补偿能力有限，以下场景还不支持：Grouping Set、Set Operator、Window、Limit、TopN、Union 等；
- Text-based 改写能力相较于 Oracle 较局限，还可以支持更多 Pattern（如部分 Output 不对齐的场景）；
- View Rewrite 不支持 Union 补偿，涉及基表分区变化时，仍退化到 SPJG 改写补偿；
- MV 改写规则与现有 RBO 存在冲突，目前通过多 Stage 改写规避了部分冲突，但也带来了额外耗时；
- 改写依赖 CBO 阶段，也可能带来耗时问题。

**改写性能问题：**
- **MVCache 分散**：目前 MV Cache 散落在 Query 改写、MV 刷新多处，建议收敛到 MV 级别统一 Cache，减少重复计算；
- **OptExpression Load 耗时**：当用户 Query 依赖大量外部表时，用于改写的 OptExpression load 操作可能很耗时；目前该 Load 不阻塞 Query，放置在 `CachingMvPlanContextBuilder` Cache 中，更新时机为：FE 重启、首次访问、MV Inactive/Active、调整 `enable_query_rewrite`；
- **时效性检测性能**：每次 Query 都需遍历 MV 和基表所有分区做 PartitionDiff 计算，分区多或有外表时可能有明显性能问题；`force_mv` 做过部分尝试，但还未彻底解决；
- **Plan Cache 结合**：能否保存相同 Pattern 的 Query 改写后 Plan，减少 parser/analyzer/MV rewrite 代价？时效性保障是关键问题。

---

### 3.3 MV 刷新能力增强

- **刷新性能**：类似改写侧，抽象统一的 MVCache（当前 `CachingMvPlanContextBuilder` 已有部分），减少不必要的重复计算；
- **Rolling Refresh 明确化**：明确用户只刷新最近 N 天数据的场景（Rolling Refresh）的产品语义和实现；
- **外部数据源增强**：JDBC、Hudi 的分区级刷新支持尚不完善。

---

### 3.4 MV 调度增强

- **Crontab 通用调度**：支持更灵活的调度表达式；
- **高频调度**：当前基于 JDK 的 `ScheduledExecutorService`，不适合高频场景，需改造；
- **更丰富的调度策略：**
  - 更丰富的 DAG 调度（级联刷新），思考如何替代外部调度平台（Airflow / Dolphin Scheduler）；
  - 支持重试、优先级；
  - 更好的血缘调度，在事件调度语义下支持更多基表数据源。

---

### 3.5 MV 运维能力增强

- **改写诊断增强**：输出更多可读、可解释的结构化信息，方便运维 DBA 或用户直接获取改写失败原因（当前 `TRACE MV LOGS` 已有基础能力，但可进一步结构化）；
- **可观测性（结合 BYOC）**：输出针对每个 MV 的刷新进度（时效性）、命中次数、收益等指标。

---

### 3.6 代码维护（Tech Debt）

MV 代码经过多人迭代，命名和抽象不统一。4.x 已做过部分清理，但仍有历史遗留：
- `MV` vs `Mv`
- `AMV` vs `MTMV`
- `PCT`
- `IVM` vs `TVR`

建议有机会做更彻底的抽象和命名统一。

---

### 3.7 测试覆盖

**当前状态：**
- StarRocksTest 中已有大数据量（1W+ 个 MV）的基础测试（FE 重启影响）；
- 有 MVTestFramework，包含 MV Lifecycle 的基础 Case，但覆盖场景偏少。

**建议补充：**
- 在 StarRocksBenchmark 中添加 MV 相关 Cover Case：
  - 基表（外表/内表）有大量分区时的刷新、改写 Performance（与不改写对比）；
  - MV 有大量基表（10/50/100）时的刷新、改写 Performance；
  - 添加 SSB / TPCH / TPCDS 100GB Scale 的例行化 Benchmark，观察各 Release 版本变化趋势。

---

## 四、关键 Docs 链接汇总

| 主题 | 链接 |
|---|---|
| 同步 MV（Rollup） | https://docs.starrocks.io/docs/using_starrocks/Materialized_view-single_table/ |
| 异步 MV 概述 | https://docs.starrocks.io/docs/using_starrocks/async_mv/Materialized_view/ |
| 分区 MV 创建 | https://docs.starrocks.io/docs/using_starrocks/async_mv/use_cases/create_partitioned_materialized_view/ |
| 数据建模与 MV | https://docs.starrocks.io/docs/using_starrocks/async_mv/use_cases/data_modeling_with_materialized_views/ |
| 数据湖查询加速 | https://docs.starrocks.io/docs/3.3/using_starrocks/async_mv/use_cases/data_lake_query_acceleration_with_materialized_views/ |
| CREATE MATERIALIZED VIEW | https://docs.starrocks.io/docs/sql-reference/sql-statements/materialized_view/CREATE_MATERIALIZED_VIEW/ |
| REFRESH MATERIALIZED VIEW | https://docs.starrocks.io/docs/sql-reference/sql-statements/materialized_view/REFRESH_MATERIALIZED_VIEW/ |
| SHOW MATERIALIZED VIEWS | https://docs.starrocks.io/docs/sql-reference/sql-statements/materialized_view/SHOW_MATERIALIZED_VIEW/ |
| information_schema.materialized_views | https://docs.starrocks.io/docs/sql-reference/information_schema/materialized_views/ |
| IVM Feature Issue | https://github.com/StarRocks/starrocks/issues/61789 |
