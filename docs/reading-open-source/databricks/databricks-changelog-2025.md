我是一名拥有 10 年以上经验的资深研发工程师，目前是顶尖开源 OLAP 数据库（StarRocks）的核心开发者与 Committer。我的日常技术栈围绕 C++、高并发、分布式系统、向量化执行以及底层性能压榨。同时，我也在积极拥抱 AI 时代，探索 LLM、RAG 和前沿编程语言（如 Rust、Haskell）。
参考 Databricks的如下release notes，总结其在2025年重大feature/optimzation及新的场景支持，分析该产品的产品商业定位及市场卖点;结合历史资料（历史release node)、博客介绍相关评论， 从技术、产品、商业话的视角，分析并洞察其产品在该年的定位及迭代方向的重点变化。
参考其release notes:
- https://docs.databricks.com/gcp/en/release-notes/product
- https://docs.databricks.com/gcp/en/release-notes/product
按照博客的方式输出一篇介绍、思考的报告类文章：
输出时注意：
- 内容尽量详实，通过引用原release note中的commit/link来说明相关的功能feature；
- 语言流畅、减少空话，尽量言之有物，结合相关feature的blog或者PR文章进行补充相关的概念或者名词；
- 在专业名词或者属于该产品的技术名词，请使用英文备注，并附上英文链接。

---
我是一名拥有 10 年以上经验的资深研发工程师，目前是顶尖开源 OLAP 数据库（[StarRocks](https://github.com/StarRocks/starrocks)）的核心开发者与 Committer。我的日常技术栈围绕 C++、高并发、分布式系统、向量化执行以及底层性能压榨。同时，我也在积极拥抱 AI 时代，探索 LLM、RAG 和前沿编程语言（如 Rust、Haskell）。

请参考 Databricks(spark的商业化公司) 的官方 Release Notes，同时结合历史版本记录、官方博客、技术文章及社区讨论：

**分析维度要求如下：**

1. **重大 Feature 与场景支持**：总结近年来（重点聚焦最近 2–3 个大版本）最重要的功能特性与新场景支持，优先关注对 HTAP、分布式事务、存储引擎、SQL 兼容性等方向有实质影响的变化；

2. **执行引擎 / 存储引擎 / 性能优化动向**：重点梳理执行引擎、Optimizer（优化器）在向量化执行、下推优化、统计信息、自适应查询执行（AQE）等方面的演进；结合 Databricks的 HTAP 架构特点，分析其在 TP 与 AP 融合上的技术取舍；

3. **自动化与运维智能化**：关注 Databricks在自动化运维（如 Auto Analyze、Auto Scaling可观测性（如 Clinic、Performance Overview）、以及资源管控（Resource Control）方面的进展；

4. **技术、产品与商业化视角的综合洞察**：
  - **技术视角**：与同类系统（如 Doris/StarRocks、ClickHouse）做横向对比，指出 Databricks在技术路线上的独特选择与权衡；
  - **产品视角**：分析各版本迭代的重心转移（如从"功能完整性"到"性能与稳定性"、再到"HTAP 场景化落地"）；
  - **商业化视角**：结合 Databricks Cloud 产品动向，分析其 Serverless、多云策略与开源社区的协同关系。

**参考资料：**
- https://docs.databricks.com/gcp/en/release-notes/product

**输出格式要求：**
- 以**博客深度分析文章**的形式输出，面向有分布式系统与数据库内核背景的工程师读者，语言要有技术深度、不讲废话；
- 内容尽量详实，**通过直接引用原 Release Notes 中具体的条目或 GitHub PR/Issue 链接**来支撑论点，避免泛泛而谈；
- 结合相关官方博客或社区文章，对重要特性补充背景概念和技术原理；
- **专业名词及产品专属技术术语使用英文标注**，并尽可能附上英文参考链接（文档、博客或 PR）；


---


# 研究性调研文档生成 Prompt

---

## 🧑‍💻 角色背景（Role & Context）

你是一名拥有 10 年以上经验的资深研发工程师，具备深厚的数据库内核与分布式系统背景。你目前是顶尖开源 OLAP 数据库 [StarRocks](https://github.com/StarRocks/starrocks) 的核心开发者与 Committer，日常技术栈涵盖 C++、高并发系统设计、分布式一致性协议、向量化执行引擎以及底层性能调优。与此同时，你也在积极拥抱 AI 时代，探索 LLM 应用、RAG 架构，以及 Rust、Haskell 等前沿编程语言。

你对数据库与数据湖仓（Lakehouse）领域有强烈的技术品味与批判性视角，能够穿透产品宣传辞令，直击技术实现的取舍与本质。

---

## 📋 任务目标（Task）

请基于以下资料来源，撰写一篇**面向数据库内核与分布式系统工程师的深度研究性分析文章**，系统梳理 **Databricks**（Apache Spark 的商业化公司，Lakehouse 架构的主要推动者）近年来的技术演进脉络、产品战略重心与商业化路径。

**核心参考资料：**
- Databricks 官方 Release Notes（GCP 版）：https://docs.databricks.com/gcp/en/release-notes/product
- Databricks 官方博客（Engineering）：https://www.databricks.com/blog/category/engineering
- Delta Lake GitHub 仓库：https://github.com/delta-io/delta
- Apache Spark GitHub 仓库：https://github.com/apache/spark
- Databricks Runtime（DBR）Release Notes：https://docs.databricks.com/en/release-notes/runtime/index.html
- 社区讨论（Databricks Community、Delta Lake Slack、Spark Summit 演讲等）

**聚焦范围：** 重点覆盖最近 2–3 个大版本周期（如 Databricks Runtime 13.x、14.x、15.x），兼顾历史版本的演进背景。

---

## 🔬 分析维度（Analysis Dimensions）

### 1. 重大 Feature 与场景支持

总结近年来最重要的功能特性与新场景支持，**优先关注对以下方向有实质影响的变化**：

- **Lakehouse 架构演进**：Delta Lake 的能力扩展（如 Liquid Clustering、Deletion Vectors、Row Tracking）对 HTAP 场景的支持进展；
- **分布式事务与数据一致性**：Delta Lake ACID 事务的演进、UniForm（Hudi/Iceberg 兼容层）对多格式互操作的影响；
- **存储引擎（Delta Lake / Photon）**：Photon 向量化执行引擎的覆盖范围扩展、Delta Lake 存储格式迭代（如 V3 Checkpoint、DV 与 Column Mapping 的交互）；
- **SQL 兼容性与语言扩展**：ANSI SQL 兼容性进展、新增窗口函数、CTE、Python UDTF、Parameterized Queries 等；
- **AI/ML 与 LLM 集成**：AI Functions（`ai_query()`）、Unity Catalog 中的 Model Registry 演进、Feature Store 与在线推理链路；
- **数据治理**：Unity Catalog 的权限模型、Column-level Lineage、Fine-grained Access Control 的演进；

对每项重大 Feature，请尽量**直接引用对应版本的 Release Notes 原文条目**，并附上相关 GitHub PR / Issue 链接或官方文档链接。

---

### 2. 执行引擎 / 存储引擎 / 性能优化动向

重点梳理以下方向的技术演进，要求有具体实现细节，避免仅停留在功能描述层面：

- **Photon 执行引擎**：向量化执行的算子覆盖进展（哪些算子已原生支持、哪些仍回退到 JVM Spark）、与原生 Spark 执行引擎的性能对比数据；
- **查询优化器（Spark Catalyst / Databricks Optimizer）**：统计信息（Statistics）收集机制、代价模型（Cost-Based Optimizer, CBO）的迭代、Join Reorder、动态分区裁剪（Dynamic Partition Pruning）；
- **自适应查询执行（AQE, Adaptive Query Execution）**：AQE 在 Databricks 上的增强实现（如 Shuffle Merge 策略、Skew Join 自动处理），与开源 Spark AQE 的差异；
- **下推优化（Pushdown）**：谓词下推、聚合下推到 Delta Lake 存储层（借助 Data Skipping、Z-Ordering / Liquid Clustering）的能力边界与实际效果；
- **HTAP 路由机制**：Databricks 如何在同一 Lakehouse 架构中处理 TP 写入与 AP 查询的隔离与协同——Deletion Vectors 对 MVCC 的模拟、Row Tracking 对 CDC 场景的支持；
- **Streaming 与批处理统一**：Structured Streaming 的 State Store 演进（RocksDB State Store）、Trigger.AvailableNow 等生产优化；

请结合 Databricks 的 Lakehouse 架构特点，分析其在 **TP 与 AP 融合**上的技术取舍——哪些是架构先天优势，哪些是历史包袱（如基于 JVM 的 Spark 调度开销、写放大问题）或已知短板。

---

### 3. 自动化与运维智能化

关注 Databricks 在**降低运维复杂度**方向上的系统性努力，具体包括：

- **Auto Optimize / Auto Compaction**：Delta Lake 的自动小文件合并与 Optimize 触发机制（`OPTIMIZE` + `ZORDER`、Liquid Clustering 的自动 Cluster 维护），与手动运维方式的对比；
- **Predictive Optimization**：DBR 13.x 引入的 Predictive Optimization 功能，其统计驱动的后台 Compaction 逻辑与 Auto Analyze 的类比；
- **Auto Scaling（Cluster Auto Scaling / Serverless Compute）**：Classic Cluster 的 Auto Scaling 与 Serverless SQL Warehouse 的弹性伸缩差异，冷启动延迟与资源隔离策略；
- **可观测性（Observability）**：
  - **Query Profile / Query History**：执行计划可视化、算子级别的 Metrics 展示，与 StarRocks Profile 机制的横向对比；
  - **Spark UI 增强 / Databricks Assistant**：AI 驱动的查询诊断能力；
  - **Lakehouse Monitoring**：数据质量监控（Data Quality Metrics）、Schema Drift 检测；
- **资源管控（Resource Management）**：
  - Query Watchdog、Fair Scheduler、Resource Pools 的机制与局限；
  - Serverless 模式下的 DBU（Databricks Unit）计费粒度与资源隔离模型；

---

### 4. 技术、产品与商业化视角的综合洞察

#### 4.1 技术视角：横向对比

与同类系统进行有深度的横向技术对比，重点聚焦**架构选型的本质差异**，而非功能清单的罗列：

| 对比维度 | Databricks (Delta Lake + Photon) | StarRocks / Doris | ClickHouse | Snowflake |
|---|---|---|---|---|
| 定位 | Lakehouse（批流一体） | OLAP / HTAP | 纯 AP | Cloud Data Warehouse |
| 存储格式 | Delta Lake（Parquet-based） | 自研列存 | MergeTree | 自研列存 |
| 执行引擎 | Photon（C++向量化）+ JVM Spark | 全链路向量化（C++） | 全链路向量化（C++） | 自研向量化 |
| 事务支持 | Delta Lake ACID（OCC） | 有限事务支持 | 无 | ACID（云原生） |
| HTAP 路径 | Deletion Vectors + Row Tracking | 主键表行列混存 | 无原生 TP | 无原生 TP |
| 扩展方式 | 存算分离（S3/GCS/ADLS） | Share-Nothing | Share-Nothing | 存算分离 |
| 开源策略 | Spark 开源 / Delta 部分开源 | 完全开源 | 完全开源 | 闭源 |

请在对比中指出 Databricks 在技术路线上的**独特选择与已知权衡**（trade-offs），例如：
- Photon 作为 JVM Spark 的加速层而非替代品，导致的算子覆盖不完整问题；
- Delta Lake 基于 Parquet 的兼容性优势与写放大、小文件问题的长期博弈；
- Liquid Clustering 相较 Z-Ordering 的根本改进在哪里，局限性又是什么；

#### 4.2 产品视角：版本迭代重心分析

请梳理 Databricks Runtime 各主要大版本的**产品战略重心演变**，例如：

- **早期 DBR（< 10.x）**：Spark 能力整合，Delta Lake ACID 基础建设；
- **DBR 10.x – 12.x**：Photon 引擎逐步落地，Unity Catalog 初步推出，ML 链路整合；
- **DBR 13.x – 14.x**：Lakehouse 场景化深化，AI/LLM 集成爆发，Serverless Compute GA，Liquid Clustering 发布；
- **DBR 15.x 及以后**：性能与稳定性收敛，HTAP 能力（Deletion Vectors、Row Tracking）成熟，与外部格式（Hudi、Iceberg）的互操作；

分析**每个阶段的版本迭代节奏与侧重点**是否与 Databricks 的市场竞争态势相呼应（如对 Snowflake 的追击、对开源生态的主导权争夺）。

#### 4.3 商业化视角：云产品策略与开源社区协同

结合 Databricks 的云产品动向，分析：

- **Serverless 架构**：Databricks Serverless SQL Warehouse 与 Serverless Jobs 的技术实现（计算存储分离、Per-Query 资源分配），与 Snowflake Serverless、AWS Athena 的差异化定位；
- **多云策略**：Databricks 在 AWS、GCP、Azure 上的落地差异（如功能 GA 时间不对齐问题）与统一数据平面的设计目标；
- **开源与商业化的协同关系**：
  - Delta Lake 开源至 Linux Foundation 后，Databricks 如何通过闭源的 Predictive Optimization、Liquid Clustering 早期版本等保持商业护城河；
  - Delta Lake vs. Apache Iceberg 的开源社区竞争格局；
- **与竞品的商业竞争态势**：面对 Snowflake、Google BigQuery、AWS Redshift/Athena，Databricks 的差异化壁垒（统一批流、AI 集成、开放格式）的实际竞争力如何？

---

## 📝 输出格式要求（Output Format）

- **体裁**：博客深度分析文章（Long-form Technical Blog），而非枯燥的功能列表；
- **受众**：具备分布式系统与数据库内核背景的工程师，**语言要有技术深度，不讲废话，不堆砌形容词**；
- **引用规范**：
  - 通过**直接引用 Release Notes 中的具体条目**来支撑论点（格式：`> Databricks Runtime 14.3 Release Notes: ...`）；
  - 对重要特性，附上对应的 **GitHub PR / Issue 链接**或官方文档页面链接；
  - 引用官方博客或社区文章时，请注明出处并附链接；
- **术语规范**：专业名词及产品专属技术术语**优先使用英文**（如 Adaptive Query Execution、Deletion Vectors、Liquid Clustering、Optimistic Concurrency Control），中文语境中首次出现时附中文释义；
- **结构建议**（可灵活调整）：
  1. **TL;DR / Executive Summary**：3–5 句话的核心结论，给忙碌的工程师一个速览；
  2. **背景与版本谱系**：快速梳理 Databricks Runtime 的架构演进时间线；
  3. **逐维度深度分析**（对应上述 4 个分析维度）；
  4. **综合评价与展望**：基于技术现状，对 Databricks 未来 1–2 年的技术路线做出有依据的预判（如 Delta Lake 与 Iceberg 的融合走向、Photon 的完整替代计划等）；
- **篇幅**：不设硬性上限，**以说清楚为准，宁深勿浅**；

---

## ⚠️ 特别注意事项

- 请**主动区分"官方宣称"与"社区实测 / 已知问题"**，对存在落地差距的特性如实指出（例如 Photon 算子覆盖率的实际限制、Liquid Clustering 在超大表上的维护成本等）；
- 对于仅在 Databricks 商业版中可用、开源 Delta Lake / Spark 中未提供的功能，请明确标注 **[Databricks-only]**；
- 如遇资料缺失或信息不确定，请明确说明"待验证"，不要凭空推断；
- 注意区分 **Databricks Runtime（DBR）版本**与 **Delta Lake 版本**的对应关系，避免混淆；

----

# Databricks 技术演进深度分析：从 Lakehouse 到 Lakebase

## 一位 OLAP 内核工程师视角下的 DBR 13.x → 18.x 全景解读

---

## TL;DR / Executive Summary

1. **存储层的核心赌注已落定**：Deletion Vectors + Liquid Clustering + UniForm 三件套，是 Databricks 在 DBR 13.x–17.x 周期内对"Delta Lake 该怎么做高效 mutable 存储"这一问题给出的完整答案。与 Z-Ordering 的静态布局不同，这套组合使得 Delta 在 write amplification 与 read skipping 之间的 trade-off 空间终于变得可调控。

2. **Photon 依然是加速层，不是替代品**：四年过去，Photon 的定位没有根本变化——它通过 JNI 嵌入 JVM Spark，在算子级别做向量化加速。这个架构选择的历史包袱决定了其算子覆盖率上限，混合执行路径中的行列转换开销是社区持续反映的痛点。

3. **运维智能化是差异化壁垒**：Predictive Optimization（含 Auto Statistics、Auto Liquid Clustering）背后是 Unity Catalog 的全局 query pattern 感知，这是闭源平台才能做到的系统级优化，开源 Delta Lake + Spark 用户无法复现。

4. **Lakebase 是 2025 年最大的战略转折**：收购 Neon、引入 serverless PostgreSQL，Databricks 正在将自己从"下游分析平台"变成"应用数据库 + 分析平台"的统一入口。这是直接对标 Aurora Serverless 的一步棋，但技术栈成熟度仍是待验证变量。

5. **格式战争接近终局**：UniForm + Iceberg v3 的落地，意味着 Delta 和 Iceberg 在物理文件层面的 binary compatibility 已基本实现。Databricks 选择了"兼容而非迁移"的策略，这对 StarRocks/Doris 等 Iceberg native 系统是个值得关注的信号。

---

## 一、版本谱系与架构演进时间线

在深入各维度分析之前，先建立一个清晰的版本坐标系。

| DBR 版本 | Spark 版本 | 发布时间 | 战略重心 |
|---|---|---|---|
| 13.3 LTS | 3.4.1 | 2023-08 | Photon 覆盖扩展，Unity Catalog 基础建设 |
| 14.3 LTS | 3.5.0 | 2024-02 | Deletion Vectors GA，Liquid Clustering Preview |
| 15.4 LTS | 3.5.0 | 2024-08 | Liquid Clustering GA，Auto Clustering，Serverless 深化 |
| 16.4 LTS | 3.5.2 | 2025-05 | Iceberg 原生支持，Scala 2.13 过渡，Auto Compaction |
| 17.3 LTS | 4.0.0 | 2025-10 | Spark 4.0 落地，Python UDTF TABLE 参数，EXECUTE IMMEDIATE |
| 18.x (Beta) | 4.1.0 | 2026-01 | Spark Connect 稳定化，新一代 Photon 优化 |

几个值得关注的时间节点：

- **DBR 16.4 是 Scala 2.12 的最后一个 LTS**，提供双镜像（2.12 + 2.13），给用户一个过渡窗口。DBR 17.x 起完全切换到 Scala 2.13，这对依赖 2.12 生态的企业用户是一次不小的迁移压力。
- **DBR 17.3 是第一个基于 Spark 4.0.0 的 LTS 版本**，包含 Spark 4.0 全部修复与改进，但同时也做了部分 revert（如 `SPARK-44856` 回退了 Python UDTF Arrow 序列化优化），说明 GA 前的质量把控压力依然很大。
- **Lakebase GA 于 2025 年底**，标志 Databricks 正式进入 OLTP 赛道。

---

## 二、重大 Feature 与场景支持

### 2.1 Delta Lake 存储层：三件套的技术本质

#### Deletion Vectors（删除向量）

Deletion Vectors 是 Delta Lake 近年来最重要的存储层改进，其核心思想是**将行级删除从"立即物化"推迟到"读时合并"**。

传统的 Delta Lake DELETE/UPDATE/MERGE 操作需要重写整个受影响的 Parquet 文件——在宽表或大文件场景下，这意味着写放大（Write Amplification）可达数十倍。Deletion Vectors 通过引入独立的 `.dvbin` 文件（本质上是 RoaringBitmap 的序列化形式）来标记被逻辑删除的行位置，物理文件保持不变，直到 `OPTIMIZE` 触发真正的合并重写。

从 Delta 协议层面看，这是对 `delta.enableDeletionVectors = true` 表属性的支持，同时引入了新的协议版本要求（`minReaderVersion=3, minWriterVersion=7`），不支持 DV 的旧客户端无法读取（[官方文档](https://docs.databricks.com/aws/en/delta/deletion-vectors)）。

**与 Iceberg 的关系**是一个微妙的技术博弈点：Iceberg v2 的 `position delete files` 在概念上类似，但二进制格式不同；Iceberg v3 的 Deletion Vectors 则与 Delta 的实现使用了**相同的二进制编码**（来自 Apache Parquet 规范），这是 Databricks 主导推动的格式统一（[Databricks Blog: Apache Iceberg v3](https://www.databricks.com/blog/apache-icebergtm-v3-moving-ecosystem-towards-unification)）。

> 从 StarRocks 的角度看这个设计：DV 的读时合并开销在列存扫描路径中会引入额外的 bitmap AND 操作，对高 DML 率的表读性能有负面影响。Photon 在读 DV 时能否做到与 Spark 路径等效的优化，目前社区反馈不够充分——这是待验证的点。

实际效果：DBR 官方数据称 MERGE 性能相比传统 copy-on-write 有 **10x 提升**（针对少量行更新场景）。结合 Data + AI Summit 2024 的 [MERGE + Liquid Clustering 专题演讲](https://www.databricks.com/dataaisummit/session/optimizing-merge-performance-using-liquid-clustering)，这组合在 CDC 场景下的确定性要比以往强得多。

#### Liquid Clustering（液态聚类）

Z-Ordering 是 Databricks 长期以来的数据布局优化手段，但有几个工程层面的硬伤：
- 聚类 key 变更需要全量重写（`OPTIMIZE ZORDER BY`）；
- 在并发写入场景下，Z-Ordering 的文件重写与正常写入存在冲突；
- 对高基数列效果差；
- 无法适应随时间变化的查询 pattern。

Liquid Clustering 的核心改进是将布局决策从**静态声明**变为**增量维护**：
- 使用 `CLUSTER BY (col1, col2)` 声明 intent，不绑定写入路径；
- 后台 `OPTIMIZE` 以增量方式只重写"尚未聚类"的文件，已聚类文件不动；
- 支持在线变更聚类 key，变更后运行 `OPTIMIZE FULL` 才触发全量重聚（[官方文档](https://docs.databricks.com/aws/en/delta/clustering)）；
- `CLUSTER BY AUTO`（DBR 15.4+）配合 Predictive Optimization，由平台分析历史查询 workload 自动选择聚类列。

**[Databricks-only]** `CLUSTER BY AUTO` 依赖 Predictive Optimization，后者需要 Unity Catalog managed table，开源 Delta Lake 用户无法使用。

从 DBR 16.4 起，Liquid Clustering 还扩展到了 **managed Apache Iceberg tables**（Public Preview），并通过 Auto Compaction 在 OPTIMIZE 间隔期间自动合并小文件（`DBR 16.4 Release Notes: Unity Catalog-managed liquid clustering tables now trigger auto-compaction`）。

**已知局限**：对于超大表（TB 级别），首次启用 Clustering 或变更 key 后的 `OPTIMIZE FULL` 可能需要数小时，运维窗口规划是实际落地的主要障碍。此外，Liquid Clustering 对 streaming write 的支持从 DBR 16.0 起才加入，此前流写场景无法使用。

#### UniForm 与 Iceberg v3：格式战争终局

UniForm（Universal Format，前称 Delta Lake Universal Format）的设计思路简洁：**在同一份 Parquet 数据文件之上，异步生成 Iceberg 元数据层**，使 Iceberg 客户端无需数据迁移即可读取 Delta 表（[官方文档](https://docs.databricks.com/aws/en/delta/uniform)）。

但 UniForm IcebergCompatV1/V2 有一个根本性限制：**不支持 Deletion Vectors**。这导致启用 DV（必要的高性能 DML 前提）的表无法同时启用 UniForm，两者互斥。

这个矛盾到 **Iceberg v3** 才得以化解。Iceberg v3 在规范层面引入了 DV 支持，且与 Delta 的实现使用相同的二进制格式——这意味着一份 DV 文件可以同时被 Delta 和 Iceberg v3 客户端理解，无需翻译层（[Databricks Blog: Advancing the Lakehouse with Apache Iceberg v3](https://www.databricks.com/blog/advancing-lakehouse-apache-iceberg-v3-databricks)）。

在 DBR 16.4 + Unity Catalog 环境下，已可以同时启用三者：

```sql
CREATE TABLE catalog.schema.table (c1 INT)
TBLPROPERTIES(
  'delta.enableDeletionVectors' = 'true',
  'delta.enableIcebergCompatV3' = 'true',
  'delta.universalFormat.enabledFormats' = 'iceberg'
);
```

Iceberg v3 还引入了两个对 Databricks 平台有额外价值的 feature：
- **VARIANT 类型**：半结构化数据（JSON/XML）原生列式存储，支持 shredding（列展开）查询优化；
- **Row Lineage**：行级别血缘追踪，与 Delta 的 Row Tracking 在语义上对齐，对 CDC 场景至关重要。

> **注意**：Iceberg v3 managed tables 升级后**不可降级**（`Managed Iceberg tables that are upgraded to v3 can't be downgraded`），而 Delta UniForm 表可以降级。这个不对称性在生产环境中需要格外注意。

---

### 2.2 Spark 4.0 落地（DBR 17.3 LTS）

DBR 17.3 是第一个搭载 Spark 4.0.0 的 LTS 版本，几个值得关注的变化：

**Python UDTF TABLE 参数支持**：Unity Catalog Python UDTFs 现在可以接受整张表作为输入参数（`TABLE arguments`），这对复杂数据转换和表级聚合计算有明显价值，相比此前只能逐行处理的 UDTF 大幅扩展了表达能力（[DBR 17.3 GCP Release Notes](https://docs.databricks.com/gcp/en/release-notes/runtime/17.3lts)）。

**`input_file_name()` 正式废弃**：这个函数因为在分布式执行下语义不稳定（文件切分顺序不确定）而早在 13.3 LTS 就已 deprecated，17.3 起不再支持，统一用 `_metadata.file_name` 替代。这个变化对大量依赖该函数做文件级元数据追踪的 ETL pipeline 有迁移成本。

**递归 CTE（`LIMIT ALL`）**：支持 `LIMIT ALL` 移除对递归 CTE 总大小的限制，解决了部分图计算场景的限制。

**`EXECUTE IMMEDIATE` 增强**：支持 constant expression 作为 SQL 字符串和参数标记的参数，动态 SQL 能力进一步完善。

**`remote_query` 表值函数**：支持直接在 SQL 中查询远程数据库引擎（通过 Unity Catalog Connections），返回表格结果，这是 Lakehouse Federation 能力的 SQL 层体现。

---

### 2.3 Lakebase：OLTP 的 Lakehouse 化

2025 年 Data + AI Summit 上，Databricks 宣布 Lakebase——基于 Neon（约 $1B 收购）的 serverless PostgreSQL 引擎，与 Lakehouse 架构深度集成。这是 Databricks 史上最重要的战略转向之一。

技术架构上，Lakebase 延续了 Neon 的核心设计：
- **存算分离**：PostgreSQL compute layer 与 object storage-based storage layer 解耦，可以独立弹性伸缩；
- **Scale to Zero**：idle 状态下完全释放 compute，消除空载成本；
- **Compute Autoscaling**：动态调整 compute 资源以匹配流量波峰；
- **即时分支（Instant Branching）**：zero-copy clone 支持风险可控的测试和开发工作流。

GA 阶段（2025 年底）已实现 Compute Autoscaling，数据展示了接近 **19,000 QPS、中位延迟 4.56ms** 的性能指标（Data + AI Summit Demo）。

**与 Lakehouse 的集成**是 Lakebase 相比独立 Neon 的核心增值点：
- 通过 Unity Catalog 统一治理，OLTP 表与 Delta 表共享相同的权限、血缘、审计体系；
- Lakebase Sync 支持将 OLTP 数据实时同步到 Delta 表，使分析查询无需额外 ETL；
- Online Feature Store（[DBR Sept 2025 Release Notes](https://docs.databricks.com/aws/en/release-notes/product/2025/september)）基于 Lakebase 实现低延迟特征服务，与 offline feature tables 保持一致性。

> **工程师视角的清醒判断**：Neon 的存算分离 PostgreSQL 架构在 scalability 上有先天优势，但其 write path 引入了额外的网络 RTT（计算节点 → 存储节点），对低延迟写密集场景存在 trade-off。Lakebase 是否能在 P99 延迟上与传统 Aurora 竞争，尚待社区大规模实测。此外，OLTP 与 OLAP 的存储层仍是两套（PostgreSQL storage vs Delta Lake），"统一"更多是治理层面的统一，不是存储层的真正融合。

---

## 三、执行引擎 / 存储引擎 / 性能优化

### 3.1 Photon：架构定位的永久局限

Photon 的核心论文（[SIGMOD '22](https://people.eecs.berkeley.edu/~matei/papers/2022/sigmod_photon.pdf)）已经清晰定义了其设计约束：**Photon 不是 Spark 的替代品，是嵌入 JVM Spark 的 native 加速层**。

具体机制：
- Photon library 以 JNI 方式加载进 JVM，Spark 与 Photon 通过 off-heap 内存指针传递数据；
- 执行路径是**自底向上**：从 scan operator 开始进入 Photon 执行，遇到不支持的算子时退出回 JVM Spark；
- 两者使用共享的 off-heap memory，通过 Spark memory manager 协调 spill；
- 当 plan 中存在 Photon/non-Photon 混合段时，存在**行列格式转换开销**（columnar ↔ row），这是性能损耗的主要来源之一。

官方宣称的性能数字：TPC-DS 1TB benchmark 上相比 DBR non-Photon 提升 **2x**，实际用户场景报告 **3x–8x**（[Databricks 官网](https://www.databricks.com/product/photon)）。但这些数字的前提是**高 Photon 算子覆盖率**，混合执行场景下数字会大幅缩水。

**算子覆盖的现实**：目前 Photon 原生支持的核心算子包括：scan（Parquet/Delta）、filter、project、aggregation、hash join（替换 sort-merge join）、sort、exchange（shuffle）、Delta/Parquet 写入（UPDATE/DELETE/MERGE INTO）。不支持的场景会 fall back 到 JVM Spark，典型的 fallback 触发点包括：
- Python/Scala UDF（UDF 在 JVM 执行，Photon 无法加速 UDF 本身）；
- 复杂嵌套类型操作；
- 某些窗口函数的边缘 case；
- 使用了 DV 的表的某些读取路径（社区反馈，待官方确认）。

**与 StarRocks/ClickHouse 的本质区别**：StarRocks 和 ClickHouse 的向量化引擎是**全链路 native**，不存在 JVM 边界，也不存在行列转换开销。Photon 的"混合执行"架构在任何有 UDF 的查询上都会产生性能 cliff，这是其架构先天决定的上限。

从 DBR 16.4 到 17.3，Photon 持续扩展算子覆盖，但官方没有公开具体的覆盖率指标。Query History 中的 "Task Time in Photon" 百分比是判断实际 Photon 利用率的最直接手段。

### 3.2 Spark Catalyst / Databricks Optimizer

Databricks 的优化器基于 Apache Spark Catalyst，但包含大量闭源扩展（DBR 是 Spark 的 fork，不完全开源）。近版本值得关注的方向：

**Adaptive Query Execution（AQE）**：AQE 在 Spark 3.x 中已是标配，Databricks 在其基础上做了多项增强：
- **Skew Join 自动处理**：检测到数据倾斜时自动将大分区拆分，与开源 AQE 基本一致但调优参数有差异；
- **Shuffle partition 自适应合并**：根据 shuffle 后的实际数据量动态合并小 partition，减少 task overhead；
- DBR 14.x 起对 AQE 与 Photon 的协同有改进，减少 AQE re-planning 时触发 Photon fallback 的情况。

**Cost-Based Optimizer（CBO）** 的准确性依赖统计信息质量。这正是 Predictive Optimization 中的 **Automatic Statistics Management**（DBR 2025 GA）要解决的问题：通过 Unity Catalog 感知所有 read/write 操作，自动触发 `ANALYZE TABLE`，确保 CBO 始终有最新统计信息（[Databricks SQL 2025 Roundup](https://www.databricks.com/blog/sql-databricks-lakehouse-2025)）。

**Dynamic Partition Pruning（DPP）**：在事实表 + 维度表的 join 场景下，DPP 通过将维度表的过滤结果广播到事实表扫描阶段，大幅减少 I/O。Databricks 的 DPP 实现比开源 Spark 更激进，会在更多场景下启用，但也会在某些情况下引入额外的 broadcast 内存压力。

**replaceWhere 并行化**（DBR 15.4）：Selective overwrite 操作现在将 delete + insert 并行执行，同时对启用了 Change Data Feed 的表，不再写独立的 change data 文件，而是使用 `_change_type` hidden column 记录变更，消除了额外的写放大（`DBR 15.4 Release Notes: Selective overwrites using replaceWhere now run jobs that delete data and insert new data in parallel`）。

### 3.3 Structured Streaming 的生产化改进

**RocksDB State Store 的异步加载**（DBR 15.4）：`COPY INTO` 命令的延迟改进，通过将 RocksDB state store 的加载改为异步，显著改善了大状态查询（如大量已摄取文件的 COPY INTO）的启动延迟（`DBR 15.4 Release Notes: improvement in start times for queries with large states`）。

**Type Widening**（DBR 16.4 Preview）：Delta 表支持 schema evolution 中的类型拓宽（如 INT → BIGINT），同时对开启了 type widening 的表支持 streaming 读取和 Delta Sharing。

**Lakeflow Spark Declarative Pipelines**（前 DLT，2025 年 6 月改名）：多 catalog/schema 发布模式 GA，streaming metrics 监控增强，Python custom sources/sinks 支持。

---

## 四、自动化与运维智能化

### 4.1 Predictive Optimization：Unity Catalog 的系统级红利

Predictive Optimization 是 Databricks 在运维智能化方向上最具差异化的能力，其核心逻辑是：**Unity Catalog 作为全局数据平面，天然掌握所有表的 read/write 模式，可以据此做出比用户更准确的优化决策**。

具体覆盖的自动化操作：
- **Auto OPTIMIZE / Compaction**：基于写入频率和文件大小分布，后台自动触发 OPTIMIZE；
- **Auto Liquid Clustering**（配合 `CLUSTER BY AUTO`）：分析历史查询 filter pattern，自动选择和更新聚类列；
- **Auto VACUUM**：自动清理过期版本文件；
- **Automatic Statistics Management**（2025 GA）：自动触发 `ANALYZE TABLE`，消除手动维护统计信息的运维负担（[Databricks SQL 2025 Roundup](https://www.databricks.com/blog/sql-databricks-lakehouse-2025)）。

**[Databricks-only]** 这些能力全部要求 Unity Catalog managed table，且需要在平台设置中启用 Predictive Optimization。外部 table 或开源 Delta Lake 用户无法使用。

> **与 TiDB Auto Analyze 的类比**：两者的设计哲学相似——通过平台感知触发统计信息维护。但 Predictive Optimization 的范围更广，涵盖了文件布局优化（Compaction、Clustering），不只是统计信息层面。TiDB Auto Analyze 在高写入率表上的触发频率控制是已知的工程难题；Databricks 通过 Unity Catalog 的全局视图理论上可以做得更精准，但具体实现质量有待社区大规模验证。

### 4.2 Serverless Compute 的演进

Databricks Serverless 在架构上已形成三个独立层次：
- **Serverless SQL Warehouse**：面向分析查询，以 SQL 语句为粒度计费（DBU per second），暖池机制基本消除冷启动；
- **Serverless Jobs / Pipelines**：面向数据工程，"Performance Optimized"模式 2025 年 GA，优化启动延迟和执行效率；
- **Serverless GPU Compute**：面向 ML/AI，支持按需 H100（2025 年 9 月新增）。

**与 Classic Cluster 的本质区别**：Classic Cluster 的 Auto Scaling 是 instance-level 的，VM 启动需要 1-5 分钟；Serverless 的弹性是 container/task-level，资源调度在 Databricks 托管的暖池中完成，响应速度快一到两个数量级。

计费模型：Serverless 按实际消耗 DBU（秒级粒度）计费，但 DBU 单价高于同配置 Classic Cluster。对于间歇性负载（BI Dashboard 按需查询、低频批处理），Serverless 的 TCO 优于预留 Cluster；对于 24/7 高负载，Classic Cluster + Spot Instance 仍有成本优势。

### 4.3 可观测性

**Query Profile**：Databricks SQL 的查询执行计划可视化是当前市场上完成度较高的实现之一，提供算子级别的 rows in/out、time、spill 指标，以及 Photon vs non-Photon 的执行分布。与 StarRocks 的 Profile 相比，Databricks 的 UI 更友好，但缺少 StarRocks Pipeline Execution 那种细粒度的 fragment/pipeline 级别分析。

**[Databricks-only]** **Databricks Assistant** 的 AI 驱动查询诊断能力正在逐步落地，可以对慢查询给出自然语言解释和优化建议，但这类 AI 辅助诊断的准确性取决于训练数据质量，目前社区评价褒贬不一。

**Cost Observability**（2025 年）：新增仓库级、Dashboard 级、用户级的消耗分析工具，以及 Materialized Views 的成本监控（Private Preview），帮助团队定位消费热点。

---

## 五、技术、产品与商业化综合洞察

### 5.1 与同类系统的横向对比

| 对比维度 | Databricks | StarRocks / Doris | ClickHouse | Snowflake |
|---|---|---|---|---|
| 核心定位 | Lakehouse + AI Platform | HTAP OLAP | 极致 AP | Cloud DW |
| 执行引擎 | Photon (C++, partial) + JVM Spark | 全链路向量化 (C++) | 全链路向量化 (C++) | 自研向量化 |
| 存储格式 | Delta Lake (Parquet-based) | 自研列存 (Segment) | MergeTree | 自研列存 |
| 事务支持 | Delta ACID (OCC, Percolator-inspired) | 有限事务 (Primary Key Table) | 无 | ACID |
| HTAP 路径 | DV + Row Tracking (write-optimized DML) | Primary Key 行列混存 | 无 | 无 |
| 存算架构 | 存算分离 (S3/GCS/ADLS) | Share-Nothing | Share-Nothing | 存算分离 |
| 开源策略 | Spark 完全开源 / Delta 开源但关键特性 Databricks-only | 完全开源 | 完全开源 | 完全闭源 |
| AI 集成 | 深度集成 (Mosaic AI, ai_query()) | 初步探索 | 无 | 有限 |

**Databricks 的独特取舍**：

1. **Photon 的渐进式替换策略 vs 全链路重写**：StarRocks 和 ClickHouse 选择从头构建全链路 C++ 向量化引擎，接受 API 层的 breaking change 风险；Databricks 选择在 Spark API 兼容性的约束下做 partial native 加速，保住了大量现有用户的迁移成本，但付出了混合执行架构的工程复杂度和性能上限的代价。这是两种完全不同的工程哲学，没有对错之分，只有取舍。

2. **Open Format vs 自研列存**：Delta Lake 基于 Parquet 的决策带来了极好的生态兼容性（任何能读 Parquet 的工具都可以直接读），但 Parquet 的行组（Row Group）组织方式天然不如专为 AP 设计的自研列存高效，特别是在列裁剪和 late materialization 方面。StarRocks 的自研列存在 SSB/TPC-H 等 benchmark 上的绝对性能通常优于 Photon + Delta Lake，但无法直接被 Pandas/Spark 等工具原生访问。

3. **Lakehouse HTAP vs 专用 HTAP**：Databricks 的 HTAP 路径本质上是用 Deletion Vectors + Row Tracking 在 AP 优化的列式存储上模拟 MVCC，这对 TP 侧的写延迟（行级 DV 写入 + 元数据事务）和读延迟（DV 合并）都有额外开销。StarRocks Primary Key 表的行列混存方案在 TP 写入路径上更直接，但也带来了存储格式的不开放性。

### 5.2 产品战略重心演变

**DBR < 13.x（早期基础建设期）**：核心任务是让 Spark + Delta Lake 能用、可靠。Photon 在 2021 年 Public Preview，功能覆盖有限，定位是 Databricks SQL 的差异化性能亮点。Unity Catalog 在 2022 年推出，初期功能粗糙。

**DBR 13.x–14.x（功能完整性 + 性能深化期）**：Photon 覆盖率大幅提升，Deletion Vectors GA，Liquid Clustering 进入 Preview。Unity Catalog 成为核心治理层，Column-level Lineage 等企业特性落地。这个阶段的主旋律是"Databricks SQL 要能打 Snowflake"。

**DBR 15.x–16.x（Lakehouse 场景化落地期）**：Liquid Clustering GA，Auto Clustering 上线，Predictive Optimization 系列能力逐步开放。Iceberg 原生支持（managed Iceberg table Public Preview），UniForm 从 V1 演进到 V2/V3。这个阶段的信号是：Databricks 在解决"如何让 Lakehouse 真正好用"，而不只是"如何让它功能完整"。

**DBR 17.x–18.x + Lakebase（AI-native + HTAP 整合期）**：Spark 4.0 落地，Lakebase GA，Mosaic AI 全面深化，MLflow 3.0 发布。这个阶段的战略意图非常清晰：**从数据分析平台向"应用开发 + 数据分析 + AI"一体化平台演进**，Snowflake 不再是唯一对标，AWS Aurora / Google AlloyDB 也进入了竞争射程。

### 5.3 商业化策略：开源与闭源的边界

Databricks 的开源/闭源边界经过精心设计：

**完全开源**：Apache Spark（核心引擎）、Delta Lake（存储格式协议 + 基础 SDK）、MLflow（实验追踪）。

**开源但 Databricks 深度优化**：Delta Lake 的开源版本可在任何 Spark 环境运行，但 Photon、Predictive Optimization、Auto Liquid Clustering、Deletion Vectors 的最优执行路径均需 Databricks Runtime 或 Unity Catalog。这形成了一种微妙的开源护城河——开源版本可用，但商业版的性能和运维体验形成事实上的锁定。

**格式中立战略**：UniForm + Iceberg v3 的推进，表面上是降低格式锁定，实际上是 Databricks 主动出击——通过主导 Iceberg v3 的关键特性（DV、Row Lineage 的二进制兼容），使自己成为开放格式生态的实际规则制定者，而不是被动的兼容方。这与 Google 推动 Kubernetes 的策略有相似之处。

**Lakebase 的商业逻辑**：Neon 本身是开源项目（PostgreSQL fork），但 Databricks 将其包装为 managed service，附加 Unity Catalog 集成、自动扩缩容、平台治理等商业价值。这将 Databricks 的 TAM（Total Addressable Market）从纯 AP/ML 市场扩展到了 OLTP 市场，且对已有 Databricks 数据平台投入的大客户而言，采用成本极低。

**多云策略的现实**：Databricks 在 AWS、GCP、Azure 上的功能 GA 时间并不完全一致，GCP 相对滞后。例如 Lakebase 在 GCP 的 Public Preview 比 AWS 晚了数月。这个现象是架构复杂性的真实反映，也是多云策略下"平台一致性"承诺与工程实现之间的固有张力。

---

## 六、综合评价与展望

### 已经确定的技术方向

1. **Delta Lake + Iceberg v3 格式统一**将在 2026 年进一步深化，Deletion Vectors 的跨格式 binary compatibility 是关键里程碑；
2. **Lakebase（Serverless PostgreSQL）**的生产稳定性和性能边界将在未来 12 个月得到充分验证（或证伪）；
3. **Automatic Statistics Management GA** 标志 Predictive Optimization 系列完成闭环，Databricks SQL 的"zero-tuning" 定位进一步强化；
4. **Spark 4.0 / Scala 2.13** 的迁移将在 2026 年成为主要运维成本，大量依赖 2.12 的企业需要认真规划。

### 尚待观察的变量

1. **Photon 的长期路线**：官方从未承诺 Photon 会成为"全量替代 JVM Spark"的引擎。在 LLM/AI 负载日益重要的背景下，是否会有 Photon v2（更宽的算子覆盖）或全新的 native runtime 计划，是社区关注但官方尚未明确的方向。
2. **Lakebase 的 OLTP 竞争力**：19,000 QPS @ 4.56ms 的 Demo 数字需要在真实混合负载（高并发短事务 + 长事务 + 分析查询竞争资源）下验证；
3. **Delta vs Iceberg 的社区博弈**：Apache Iceberg 在 Snowflake、AWS、Google 的持续投入下仍在快速演进，Databricks 的"兼容而非竞争"策略能否在格式标准战中保持主导地位，取决于开源社区的实际采用速度；
4. **多语句事务（Multi-statement Transactions）**：Databricks SQL 2025 Roadmap 中明确提到这个特性，对于将 Databricks SQL 用于 OLTP-like 场景的用户来说是关键能力，目前仍在开发中。

---

## 参考资料

- [Databricks Runtime Release Notes Index](https://docs.databricks.com/aws/en/release-notes/runtime/)
- [DBR 17.3 LTS GCP Release Notes](https://docs.databricks.com/gcp/en/release-notes/runtime/17.3lts)
- [DBR 16.4 LTS Release Notes](https://docs.databricks.com/aws/en/release-notes/runtime/16.4lts)
- [DBR 15.4 LTS Release Notes](https://docs.databricks.com/aws/en/release-notes/runtime/15.4lts)
- [Databricks Platform Release Notes (GCP)](https://docs.databricks.com/gcp/en/release-notes/product)
- [Deletion Vectors Documentation](https://docs.databricks.com/aws/en/delta/deletion-vectors)
- [Liquid Clustering Documentation](https://docs.databricks.com/aws/en/delta/clustering)
- [UniForm / Iceberg Reads Documentation](https://docs.databricks.com/aws/en/delta/uniform)
- [Apache Iceberg v3 Features on Databricks](https://docs.databricks.com/aws/en/iceberg/iceberg-v3)
- [Databricks Blog: Apache Iceberg v3 – Moving the Ecosystem Towards Unification](https://www.databricks.com/blog/apache-icebergtm-v3-moving-ecosystem-towards-unification)
- [Databricks Blog: Advancing the Lakehouse with Apache Iceberg v3](https://www.databricks.com/blog/advancing-lakehouse-apache-iceberg-v3-databricks)
- [Photon Public Preview Announcement](https://www.databricks.com/blog/2021/06/17/announcing-photon-public-preview-the-next-generation-query-engine-on-the-databricks-lakehouse-platform.html)
- [Photon: A Fast Query Engine for Lakehouse Systems (SIGMOD '22)](https://people.eecs.berkeley.edu/~matei/papers/2022/sigmod_photon.pdf)
- [Databricks Blog: SQL on the Databricks Lakehouse in 2025](https://www.databricks.com/blog/sql-databricks-lakehouse-2025)
- [Databricks Blog: Lakebase Generally Available](https://www.databricks.com/blog/databricks-lakebase-generally-available)
- [Databricks Blog: Lakebase Holiday Update](https://www.databricks.com/blog/lakebase-holiday-update)
- [Data + AI Summit 2024: MERGE + Liquid Clustering](https://www.databricks.com/dataaisummit/session/optimizing-merge-performance-using-liquid-clustering)
- [Databricks Platform Release Notes June 2025](https://docs.databricks.com/aws/en/release-notes/product/2025/june)
- [Databricks Platform Release Notes September 2025](https://docs.databricks.com/aws/en/release-notes/product/2025/september)
