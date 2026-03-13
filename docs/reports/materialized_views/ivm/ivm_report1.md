# 增量计算 (IVM) 技术调研报告

你好！作为在数据库内核和 StarRocks 社区摸爬滚打多年的老兵，我非常高兴能和你一起探讨增量计算（Incremental View Maintenance, IVM）这个迷人又充满挑战的领域。从底层的 C++ 执行引擎、向量化优化，到上层的查询优化器（Query Optimizer）和物化视图（Materialized View），IVM 一直是打破“性能-成本”不可能三角的核心武器。

以下是我为你整理的 IVM 技术调研报告，涵盖了代数理论、工业界实现、学术界最新进展以及我们在 StarRocks 中的落地思考。

---

## 1. Executive Summary

在当前云原生与存储计算分离（Storage-Compute Separation）的架构趋势下，传统的全量 Batch 刷新已无法满足业务对实时性（Freshness）和计算成本（Cost-efficiency）的双重苛求。IVM 的本质是通过计算查询结果的微分（$\Delta Q$），将 $O(|DB|)$ 的全量计算降维到接近 $O(|\Delta DB|)$ 的增量开销。

当前工业界（Snowflake, Databricks, BigQuery, StarRocks）均已将 Materialized View (MV) 升级为核心竞争力，普遍采用“透明查询重写（Smart Tuning / Query Rewrite）”+“DAG 增量刷新”的范式。然而，针对非单调算子（Non-monotonic operators，如 Window Function, `COUNT DISTINCT`）以及复杂多表 Join 的状态膨胀问题，纯工程手段已触及天花板。学术界（如 DBSP, F-IVM）正通过更高维度的代数抽象（如 Ring of Databases、Factorized 状态）来突破理论下界。对于 StarRocks 而言，融合流式 Changelog 语义与按需状态计算，将是下一代 IVM 的关键突围方向。

---

## 2. IVM 理论基础与瓶颈分析

### 2.1 代数框架：Ring of Databases 与微分查询

IVM 的底层理论基础是将数据库操作映射为交换环（Commutative Ring） $(K, \oplus, \otimes, 0, 1)$ 上的多项式运算。当底层数据发生变化 $\Delta DB$ 时，视图 $V = Q(DB)$ 的增量可以通过计算查询 $Q$ 的偏导数来获得：


$$\Delta V = Q(DB \oplus \Delta DB) \ominus Q(DB)$$


对于线性算子（如 Projection, Union），$\Delta Q$ 可以下推；但对于 Join 算子，展开后会产生交叉项（Cross terms）：


$$\Delta(R \bowtie S) = (\Delta R \bowtie S) \cup (R \bowtie \Delta S) \cup (\Delta R \bowtie \Delta S)$$


这种交叉项在多表 Join 时会导致高阶增量（Higher-order deltas），正是传统 IVM 状态爆炸的根源。

### 2.2 算子分类：Monotonic vs. Non-monotonic

* **单调算子（Monotonic Operators）**：如 `SELECT`, `JOIN`, `SUM`, `COUNT`。数据插入只会导致结果集增加或数值单向累加，极易实现 IVM。
* **非单调算子（Non-monotonic Operators）**：如 `MIN`, `MAX`, `COUNT DISTINCT`, `Window Functions`, `OUTER JOIN`。
* **瓶颈本质**：当一个极值（如 MAX）被 Delete 时（即 Retraction 操作），引擎必须回溯次大值。这要求系统缓存海量的底层明细状态（Intermediate State），打破了 $O(|\Delta DB|)$ 的空间复杂度下界。



---

## 3. 工业界现状 (Industrial Implementations)

### 3.1 Snowflake Dynamic Table

* **架构与机制**：基于内部的 Change Tracking 和 Stream 机制构建 DAG。用户声明目标延迟（`TARGET_LAG`）和计算资源（`WAREHOUSE`），调度器自动编排微批（Micro-batch）刷新。
* **状态**：GA (General Availability)。
* **增量策略**：支持 `AUTO`, `FULL` (类似于 Oracle 的 COMPLETE), `INCREMENTAL` (类似于 FAST)。`AUTO` 模式下，优化器根据算子兼容性自动选择。
* **Limitations**：
* 不支持非确定性函数（Non-deterministic functions）的增量。
* 外部表（External Tables）的增量支持受限。
* *数据来源：Snowflake 官方文档 (Dynamic Table Resource / SnowConvert AI 转换规则).*



### 3.2 Databricks Materialized View

* **架构与机制**：构建于 Delta Live Tables (DLT) 之上。强依赖 Delta Lake 的事务日志（Transaction Log）。引擎通过读取 `_change_data` (CDC) 流来驱动增量聚合。
* **状态**：GA。
* **增量策略**：增量刷新（Incremental Refresh）。主要针对常见的聚合和追加写（Append-only）场景优化。
* **Limitations**：
* 对于包含复杂 Window Function 或非等值 Join 的 MV，往往会退化为 Full Compute。
* *数据来源：Databricks 官方文档 (Incremental Refresh).*



### 3.3 BigQuery Materialized View

* **架构与机制**：强调“零维护成本”的无服务器体验。核心亮点是 **Smart Tuning**（智能重写）和 **Materialized View Recommender**（基于历史过去 30 天 Query 负载自动推荐构建 MV）。
* **状态**：GA。
* **增量策略**：后台自动进行 Incremental Refresh。如果检测到增量代价过大，会退化并限流。
* **Limitations**：
* 不支持复杂的 CTE 内部嵌套非单调聚合的增量。
* 不支持 Outer Joins 的严格增量维护。
* *数据来源：Google Cloud BigQuery 官方文档 (Materialized views intro).*



### 3.4 StarRocks Materialized View

* **架构与机制**：分为 Sync MV (单表 Rollup 索引，实时强一致) 和 Async MV (多表复杂查询，后台 Task 异步刷新)。基于 SPJG (Select-Project-Join-Group-by) 模型实现透明查询重写，支持 View Delta Join 和 Derivable Joins。
* **状态**：GA (Async MV 从 v2.4 起持续迭代，v3.x 引入更多湖仓融合特性)。
* **增量策略**：支持 `ASYNC` (数据驱动), `ASYNC EVERY` (定时), `MANUAL`。支持基于时间分区的精准刷新 (Partition-level refresh) 和中间结果落盘 (Intermediate Result Spilling) 防止 OOM。
* **Limitations**：
* 不支持包含 Window Functions 或 Join+Aggregation 混合复杂场景的直接增量重写。
* Outer Join 中包含复杂 ON 谓词时可能匹配失败（建议下推到 WHERE）。
* *数据来源：StarRocks 官方文档 (Async MV Query Rewrite, Troubleshooting).*



---

## 4. 横向对比矩阵

| 引擎 | 算子覆盖与增量支持 | 延迟下限 | 一致性保证 | 成本模型 / 刷新触发 | 流批融合能力 |
| --- | --- | --- | --- | --- | --- |
| **Snowflake (Dynamic Tables)** | SPJG 良好；部分 Outer Join 受限 | 1 分钟 (`TARGET_LAG`) | 最终一致 / 快照级 | 需独占 Warehouse 计算资源；DAG 驱动 | 高（底层基于 Stream & Task） |
| **Databricks (MV via DLT)** | 擅长 Append-only 和简单聚合 | 几分钟量级 | 强一致（基于 Delta Log 事务） | Serverless/按量计费；数据变更驱动 | 极高（Spark Structured Streaming 统一） |
| **BigQuery (MV)** | 单表聚合/简单 Join 极佳 | 无显式 SLA (系统自动调度) | 强一致 (Smart Tuning 保证透明) | 自动维护，不直接向用户暴露维护计算费 | 弱（偏向纯 Batch 的微批化） |
| **StarRocks (Async MV)** | SPJG, View Delta Join, 多表 Join | 秒级~分钟级 (`INTERVAL`) | 最终一致 (基于 Task Run) | 共享集群资源，分区级细粒度刷新 (TTL) | 中（正向 Flink Changelog 语义演进） |

---

## 5. 学术界最新研究成果与技术瓶颈深度分析

近年来，学术界（VLDB/SIGMOD）对 IVM 的研究主要集中在“打破状态膨胀”和“丰富语言表达能力”上：

1. **DBSP (Directed-Bicycle Stream Processing)**
* *论文：Budiu et al., "DBSP: Automatic Incremental View Maintenance for Rich Query Languages", VLDB 2023.*
* **核心贡献**：为丰富的数据库语言（包含 Window queries, Monotonic/Non-monotonic recursion）提供了一套完整的流处理代数。证明了所有的基本算子都有 $O(|DB| / |\Delta DB|)$ 的加速潜力，通过将查询转化为 Stateful streaming operator 解决复杂 SQL 的增量化。


2. **消除 Join 带来的超线性膨胀 (Super-linear Blowup)**
* *论文：Hu et al., "Change Propagation Without Joins", VLDB 2023.*
* **核心贡献**：传统 Change Propagation 遇到 Join 会导致最坏情况下的多项式级复杂度。该研究指出，只要查询计划中剥离传统物理 Join（利用 Factorized / GHD 分解），空间和更新时间均可控制在线性范围 $O(|\Delta DB|)$ 内。


3. **Split Maintenance（连续视图的拆分维护）**
* *论文：Winter et al., "Meet Me Halfway: Split Maintenance of Continuous Views", VLDB 2020.*
* **核心贡献**：在 Umbra 系统中，针对高吞吐插入场景，不强求在写入时完成 100% 的 IVM 计算（如 DBToaster 那样），而是将维护代价一分为二：写入时只做轻量级 Partial Delta，查询时再做最终的 Merge。这为工程中平衡 Freshness 和 Throughput 提供了绝佳思路。


4. **云原生数据仓库的 Streaming View**
* *论文：Zhou et al., "Streaming View: An Efficient Data Processing Engine for Modern Real-time Data Warehouse of Alibaba Cloud", VLDB 2025.*
* **核心贡献**：直击 Zero-ETL 背景下的 IVM 落地痛点。通过在基础表上建立基于 Join Key 的增量索引（Join Views），以及使用基于磁盘的状态机代替内存 Hash Table，解决了传统流引擎中海量 Window State 导致的 OOM 问题。



---

## 6. 对 StarRocks 的启示与可落地方案建议

结合学术界的理论进展和我在 StarRocks 社区的研发经验，对于下一代 IVM 引擎的演进，我提出以下几点落地方案和建议：

### 6.1 引入 Retraction Stream（撤回流）语义应对非单调算子

目前 StarRocks Async MV 主要通过分区的整体 Overwrite 来规避非单调算子（如 `COUNT DISTINCT`）的更新难题。

* **Actionable Step**：借鉴 Flink SQL 的 Retraction 模型与 DBSP 理论，在存储引擎（Storage Engine）底层原生地引入 `[-1]` (Delete/Retract) 行标记。在计算引擎中，为 `MAX`/`MIN` 引入有限深度的候选队列（Top-K 树），当最大值收到 Retract 信号时，以 $O(\log K)$ 的代价选出次大值，避免 Fallback 到分区全量刷新。

### 6.2 引入 Meet Me Halfway (Split Maintenance) 机制

* **Actionable Step**：在当前的 Task 刷新框架外，引入“Query-time Merge”特性。即 MV 物理表中只维护到 T-1 时刻的 Base Data，T时刻到 T+1 的增量 $\Delta DB$ 缓存在轻量级的内存 Delta Store 中。当用户的 Query 命中 MV 时，优化器动态生成 `SELECT * FROM MV UNION ALL SELECT * FROM DeltaStore` 的执行计划。这可以在不增加后台刷新频率（降低写放大）的前提下，实现业务视角的强一致实时性。

### 6.3 针对高优算子利用 Factorization (F-IVM) 降维

* **Actionable Step**：针对多表 Star Schema/Snowflake Schema 的 Join MV，当前通过展开为宽表会带来严重的冗余状态。可以探索在存储层保留外键引用的字典编码（Global Dictionary / Factorized Representation），在增量计算时只传递 Keys 的 Delta，直到最终 Project 节点再进行 Materialization，以此压榨 CPU Cache 和内存带宽。

---

希望这份详实的调研报告对你的架构设计和内核优化有所帮助。如果你想更深入探讨某一个具体方向（比如 **如何具体在 StarRocks 的 Optimizer 中实现非单调算子的查询重写逻辑**，或者 **如何设计 Retraction Stream 的底层存储结构**），随时告诉我，我们可以马上展开推演！