# 研究性调研文档生成 Prompt

---

## 🧑‍💻 角色背景（Role & Context）

你是一名拥有 10 年以上经验的资深研发工程师，具备深厚的数据库内核与分布式系统背景。你目前是顶尖开源 OLAP 数据库 [StarRocks](https://github.com/StarRocks/starrocks) 的核心开发者与 Committer，日常技术栈涵盖 C++、高并发系统设计、向量化执行引擎、存储引擎以及底层性能调优。

你对列式数据库和分析型系统有强烈的技术品味与批判性视角，能够区分"工程上真实有效的优化"与"benchmark 调参游戏"，能够直击设计取舍的本质。你与 ClickHouse 是直接竞争关系，因此你的分析要既客观公正，又要有竞争对手视角的犀利洞察。

---

## 📋 任务目标（Task）

请基于以下资料来源，撰写一篇**面向数据库内核与分布式系统工程师的深度研究性分析文章**，系统梳理 **ClickHouse**（Yandex 孵化、目前由 ClickHouse Inc. 主导）近年来的技术演进脉络、架构取舍与商业化路径。

**核心参考资料：**
- ClickHouse 官方 Changelog：https://clickhouse.com/docs/en/whats-new/changelog
- ClickHouse 官方博客：https://clickhouse.com/blog
- ClickHouse GitHub 仓库（PR / Issue）：https://github.com/ClickHouse/ClickHouse
- ClickHouse Release Notes（按版本）：https://github.com/ClickHouse/ClickHouse/releases
- 社区讨论（ClickHouse GitHub Discussions、HN 讨论、ClickHouse meetup 演讲等）

**聚焦范围：** 重点覆盖近 2–3 年的版本演进（约 v23.x、v24.x、v25.x），兼顾历史版本的架构演进背景。

---

## 🔬 分析维度（Analysis Dimensions）

### 1. 重大 Feature 与场景支持

总结近年来最重要的功能特性，**优先关注对以下方向有实质影响的变化**：

- **存储引擎演进（MergeTree 家族）**：
  - SharedMergeTree（ClickHouse Cloud 的新存储引擎）与经典 ReplicatedMergeTree 的架构差异；
  - MergeTree 的 Part 合并策略演进（如 Vertical Merge、Parallel Merge）；
  - 轻量级 DELETE（Light-weight DELETE）与 UPDATE 的实现机制，与传统 `ALTER TABLE DELETE` Mutation 的对比；
  - 新的 Part 格式（Wide Part vs Compact Part）对小数据量写入的优化；

- **查询能力扩展**：
  - Analyzer（新查询分析器，基于 QueryTree AST 重构）的落地进展：从 experimental 到 production，以及它带来的 JOIN 语义修正、子查询去关联化改进；
  - Window Functions 的完善程度与已知限制；
  - 并行 Scalar Subquery 执行；
  - ASOF JOIN、PASTE JOIN 等 ClickHouse 特色 JOIN 类型的演进；

- **半结构化数据支持**：
  - `JSON` 数据类型（新版，与旧版 `Object('json')` 的对比）的底层存储机制（动态列、subcolumn 按需读取）；
  - `Dynamic` 类型与 `Variant` 类型的引入，及其对 schema-on-read 场景的影响；

- **物化视图与投影（Projection）**：
  - 增量物化视图的一致性保证机制与已知 edge case（如跨分区插入时的一致性问题）；
  - Projection 的自动选择机制与优化器集成现状；

- **事务支持（Experimental）**：
  - ClickHouse 对 ACID 事务的探索现状，`allow_experimental_transactions` 的实现路径与局限；
  - 为何 ClickHouse 在事务方向上进展缓慢——架构层面的根本原因分析；

对每项重大 Feature，请尽量**直接引用对应版本的 Changelog 或 GitHub PR 链接**，避免泛泛而谈。

---

### 2. 执行引擎 / 存储引擎 / 性能优化动向

这是本文的核心章节，要求有具体的实现细节，面向能读懂 C++ 代码和执行引擎论文的工程师：

- **向量化执行引擎**：
  - ClickHouse Pipeline Execution Model（基于 Processor/Port 的流水线模型）的演进，与 Morsel-Driven Parallelism 的关系；
  - SIMD 利用现状：AVX-512 的实际启用情况，与 StarRocks/DuckDB 在 SIMD 利用率上的横向对比；
  - Vectorized Aggregation 的 Hash Table 实现细节（Swiss Table / Two-Level Hash Table）；

- **查询优化器（Analyzer + Planner）**：
  - 新 Analyzer 的 QueryTree 重构带来了哪些优化空间（如 common subexpression elimination、predicate pushdown 的正确性修复）；
  - Cost-Based Optimizer（CBO）的现状：ClickHouse 长期依赖 rule-based 优化，CBO 的引入进度与挑战；
  - Join Order 优化：当前实现的局限性，与 DuckDB 的 dynamic programming join reorder 的对比；

- **存储层性能**：
  - MergeTree 的 Data Skipping Index（MinMax、Bloom Filter、Set、NGram）在实际场景中的有效性边界；
  - 主键索引（Sparse Index）的稀疏粒度（`index_granularity`）对读性能的影响，及近版本的自适应粒度（Adaptive Granularity）改进；
  - 列压缩的演进：ZSTD、LZ4、Gorilla、DoubleDelta 编解码器的适用场景，以及近版本新增编解码器；

- **并发控制与资源隔离**：
  - Workload Groups（Workload Management）与 Resource Policy 的实现机制；
  - 查询并发度控制（`max_threads`、`max_concurrent_queries`）的细粒度管理；
  - 内存超限处理机制（Overcommit Tracker、Query Memory Limit）的演进；

- **IO 优化**：
  - Prefetch 与 Read-ahead 机制；
  - 对象存储（S3/GCS）的 Read/Write 优化（如 S3 Express One Zone、分片上传策略）；
  - Page Cache（Userspace Cache / Uncompressed Cache / Mark Cache）的分层设计；

---

### 3. 云原生与存算分离架构

ClickHouse Cloud 是 ClickHouse Inc. 的核心商业产品，其架构演进值得单独深入分析：

- **SharedMergeTree**：
  - 与经典 ReplicatedMergeTree 的根本架构差异：数据存储在共享对象存储（S3），多个计算节点共享同一份数据；
  - ClickHouse Keeper（ZooKeeper 替代品）在 SharedMergeTree 中的角色；
  - 写入路径：数据如何从 INSERT 落到 S3，Part 的元数据如何同步到多个计算节点；
  - 读取路径：如何处理 Part 在对象存储上的分布与缓存一致性；
  - 与 Databricks Delta Lake（存算分离）、Snowflake（虚拟仓库）的架构对比；

- **ClickHouse Cloud Serverless / Auto Scaling**：
  - 冷启动延迟的工程优化手段（如 SSD Cache 预热、Part 元数据预加载）；
  - 多租户隔离策略；

- **Tiered Storage（分层存储）**：
  - Hot/Warm/Cold 数据的自动分层迁移策略（`TTL MOVE TO DISK`）；
  - 对象存储 + 本地 NVMe SSD 的混合存储架构在延迟敏感场景下的 trade-off；

---

### 4. 运维智能化与可观测性

- **内置可观测性**：
  - `system.query_log`、`system.part_log`、`system.merge_log` 等系统表体系的完整性；
  - `EXPLAIN` 语句的功能演进（`EXPLAIN PLAN`、`EXPLAIN PIPELINE`、`EXPLAIN ESTIMATE`）；
  - Query Sampling 与 Flame Graph 集成；

- **自动化运维**：
  - 自动 Merge 策略的调优（Background Thread Pool、`merge_max_block_size`）；
  - 自动物化视图刷新（REFRESH MATERIALIZED VIEW）的引入与局限；
  - ClickHouse Keeper 对 ZooKeeper 的替换进度与生产可用性；

- **ClickHouse Cloud 专有运维能力 [ClickHouse-Cloud-only]**：
  - SQL Console、Query Insights、Slow Query 分析；
  - 自动扩缩容的触发策略与用户可控粒度；

---

### 5. 技术、产品与商业化视角的综合洞察

#### 5.1 技术视角：横向对比

请以**架构选型的本质差异**为核心进行对比，不是功能列表的罗列：

| 对比维度 | ClickHouse | StarRocks | DuckDB | Databricks |
|---|---|---|---|---|
| 核心定位 | 极致 AP（实时分析） | HTAP OLAP | 嵌入式 OLAP | Lakehouse + AI |
| 存储引擎 | MergeTree（自研） | Segment-based（自研） | 自研列存 | Delta Lake（Parquet） |
| 执行模型 | Pipeline（Processor/Port） | Pipeline（自研） | Vectorized（Push-based） | Photon + JVM Spark |
| 并发架构 | 单查询多线程（水平扩展有限） | MPP（多节点并行） | 单节点 | MPP（Spark） |
| 分布式事务 | Experimental，极不成熟 | 有限支持 | 无 | Delta ACID |
| 扩展方式 | Share-Nothing（经典）/ SharedMergeTree（云） | Share-Nothing | 单机 / 嵌入式 | 存算分离 |
| JOIN 能力 | 较弱（历史上有名的 short-coming） | 强 | 强（DuckDB 以 JOIN 见长） | 强 |
| 开源策略 | Apache 2.0 完全开源 | Apache 2.0 完全开源 | MIT 完全开源 | Spark/Delta 开源，云特性闭源 |

重点指出 ClickHouse 在技术路线上的**独特选择与已知权衡**，例如：
- ClickHouse "单查询尽可能用满所有 CPU 核"的并发哲学与 MPP 架构的根本差异，以及在高并发小查询场景下的劣势；
- MergeTree Sparse Index 与 StarRocks 全局字典编码 + ZoneMap 的设计哲学对比；
- ClickHouse 在 JOIN 上长期的弱点（历史上不支持 Hash Join Spill，大 JOIN 需要手动 broadcast），以及近版本的改进进展；
- ClickHouse 的 approximate query（`approx_count_distinct`、HyperLogLog、分位数估计）是其实时分析场景的核心武器，与其他系统的对比；

#### 5.2 产品视角：版本迭代重心分析

请梳理 ClickHouse 近年各大版本的**产品战略重心演变**：

- **v22.x 及之前**：功能快速堆叠期，社区贡献驱动，稳定性参差；
- **v23.x**：工程质量提升，Analyzer 开始 experimental 落地，ClickHouse Cloud 商业化加速；
- **v24.x**：新 JSON 类型、Variant/Dynamic 类型落地，SharedMergeTree 成熟，JOIN 能力补强；
- **v25.x**：Analyzer 生产化，CBO 探索，AI/向量检索集成（如 vector similarity search）；

分析**版本迭代重心**是否与 ClickHouse Inc. 的商业竞争压力相呼应（如应对 DuckDB 的崛起、Databricks SQL 的追击）。

#### 5.3 商业化视角

- **ClickHouse Cloud 的定位**：与 Snowflake、BigQuery、Databricks SQL 的差异化在哪里？极致 AP 性能 + 开源基因是核心 narrative，但在企业治理（权限、血缘、数据目录）上的短板是否已补齐？
- **开源 vs 商业的护城河**：ClickHouse 完全开源（Apache 2.0），商业版的增值点主要集中在 SharedMergeTree、SQL Console、托管运维等云服务层面，而非功能层面的割裂。这与 Databricks 的"闭源关键特性"策略有显著不同——其对社区生态的影响是什么？
- **ClickHouse 的 AI 布局**：Vector Similarity Search（近似向量检索）的实现进展（基于 Annoy / usearch 的索引），与专业向量数据库（Milvus、Weaviate）的定位对比；
- **竞争态势**：DuckDB 的崛起对 ClickHouse 单机 OLAP 市场的侵蚀有多严重？两者的用户群体重叠度分析；

---

## 📝 输出格式要求（Output Format）

- **体裁**：博客深度分析文章（Long-form Technical Blog），面向能读懂执行引擎论文和 C++ 代码的工程师；**语言有技术深度，不讲废话，不堆砌形容词**；
- **引用规范**：
  - 通过**直接引用 Changelog 中的具体条目或 GitHub PR 链接**支撑论点（格式：`> ClickHouse v24.3 Changelog: ...`）；
  - 引用官方博客或社区文章时注明出处并附链接；
  - 对存在工程争议的特性，主动引用 GitHub Issue 或社区讨论佐证；
- **术语规范**：专业名词优先使用**英文**（如 Merge Tree、Sparse Index、Adaptive Granularity、Pipeline Execution Model），中文语境中首次出现附中文释义；
- **结构建议**：
  1. **TL;DR / Executive Summary**：3–5 句核心结论；
  2. **背景与版本谱系**：ClickHouse 的架构演进时间线（从 Yandex 内部工具到 ClickHouse Inc.）；
  3. **逐维度深度分析**（对应上述 5 个分析维度）；
  4. **综合评价与展望**：基于技术现状，对 ClickHouse 未来 1–2 年的技术路线做出有依据的预判（如 Analyzer/CBO 成熟化、SharedMergeTree 开源化可能性、与 AI 工作负载的融合方向）；
- **篇幅**：不设硬性上限，**以说清楚为准，宁深勿浅**；

---

## ⚠️ 特别注意事项

- ClickHouse 的版本迭代极快（每月一个小版本），要注意**区分 experimental feature 和 production-ready feature**，对尚在 `allow_experimental_*` flag 下的功能明确标注 **[Experimental]**；
- ClickHouse Cloud 的部分特性不对应开源版本，需明确标注 **[ClickHouse-Cloud-only]**；
- ClickHouse 社区中存在大量"某 benchmark 第一"的宣传，分析时需**主动审视 benchmark 的前提条件**（数据集大小、并发度、是否启用近似计算、硬件配置），不要将 benchmark 宣传作为技术结论；
- 如遇资料缺失或信息不确定，明确说明"待验证"，不要凭空推断；
- 注意区分**开源 ClickHouse 版本**与 **ClickHouse Cloud（SharedMergeTree 架构）**的能力边界，这是两套不同的系统；


# ClickHouse 技术演进深度分析：从 AP 极致到 Lakehouse 竞争者

## 一位 StarRocks 内核工程师视角下的 v23.x → v25.x 全景解读

---

## TL;DR / Executive Summary

1. **Analyzer（新查询分析器）是近三年最重要的基础设施重构**：从 v23.x experimental 到 v24.3 默认启用，QueryTree AST 的引入使得 predicate pushdown、JOIN 语义修正、CTE 嵌套等历史顽疾得以根治，并为 CBO 方向（DPsize Join Reorder，v25.12 首发）铺平了道路。这是一次迟到但必要的优化器现代化。

2. **SharedMergeTree 是云架构的质变，但对开源用户是黑盒**：SharedMergeTree 通过将 metadata 从各节点本地移至 ClickHouse Keeper + 共享对象存储，实现了真正的 stateless compute，彻底解决了 ReplicatedMergeTree 在弹性伸缩上的瓶颈。但它是 **[ClickHouse-Cloud-only]**，开源社区一个对应的 RFC（[#54644](https://github.com/ClickHouse/ClickHouse/issues/54644)）悬而未决。

3. **JSON / Variant / Dynamic 三件套是半结构化数据的完整解法**：v24.8 的新 JSON 类型基于 Variant + Dynamic 构建，实现了真正的 columnar subcolumn 存储——高基数 JSON path 的查询性能与普通列无异。v25.8 的 shared data 序列化优化将超高路径数场景（10k+ paths）的内存使用降低了 3300x，这不是调参，是序列化格式的根本重设计。

4. **Lightweight Updates（v25.7）终结了 Mutation 的历史包袱**：基于 patch part 机制的 UPDATE 语句，将改写范围从全列压缩到仅含变更数据的微型 Part，与 ClickHouse 持续运行的 background merge 协作完成物化。相比 StarRocks Primary Key 表的 Delete+Insert 路径，这是完全不同的实现哲学。

5. **Data Lake 从 v24 末期到 v25 发生质变**：从 24.12 的 Iceberg REST Catalog，到 25.3 的 Unity/Glue Catalog，到 25.8 覆盖 Partition Pruning、Schema Evolution、Time Travel、Positional Deletes——ClickHouse 在 18 个月内把数据湖查询能力从玩具级补齐到生产级。这直接威胁到 StarRocks/Trino 在 Lakehouse query 层的地位。

---

## 一、版本谱系与架构演进背景

ClickHouse 的发展轨迹分三段：**Yandex 内部工具期（2009–2016）→ 开源社区快速扩张期（2016–2021）→ ClickHouse Inc. 商业化主导期（2021–今）**。

ClickHouse Inc. 于 2021 年 9 月成立，融资超过 $2.5B。公司成立后版本节奏显著加快，维持**月度发布**的频率，每年两个 LTS 版本。

| 版本 | 发布时间 | 战略重心 |
|---|---|---|
| v23.3 LTS | 2023-03 | Analyzer experimental，ClickHouse Keeper 生产化 |
| v23.8 LTS | 2023-08 | Parallel Replicas，SharedMergeTree 成熟（Cloud） |
| v24.3 LTS | 2024-03 | Analyzer 默认启用（Beta），S3 Express One Zone |
| v24.8 LTS | 2024-08 | 新 JSON 类型 Experimental，JOIN 能力补强 |
| v25.3 LTS | 2025-03 | Data Lake Catalog（Unity/Glue），Refreshable MV 稳定 |
| v25.8 LTS | 2025-08 | Data Lake 全面 GA，JSON 序列化重构，Text Index experimental |
| v25.12 | 2025-12 | DPsize Join Reorder，Lazy Reading 75x 提速，Lightweight Updates |
| v26.1 | 2026-01 | Iceberg/Delta 写入，Deduplication 默认开启 |

**开源 vs Cloud 的能力分叉**正在加深：SharedMergeTree、SharedCatalog、Compute-Compute Separation（Warehouses）均为 **[ClickHouse-Cloud-only]**，而社区 RFC 推进缓慢。这与 Databricks 的策略异曲同工，只是包装更隐蔽——ClickHouse 宣称 Apache 2.0 完全开源，但云上最关键的架构创新事实上不开放。

---

## 二、重大 Feature 与场景支持

### 2.1 Analyzer：优化器现代化的迟到账单

ClickHouse 的历史 query analysis 基础设施（旧的 InterpreterSelectQuery）是在 Yandex 时期积累的技术债，核心问题包括：

- 嵌套 CTE + JOIN 的列解析错误（直接抛 `UNKNOWN_IDENTIFIER`）；
- 多路 ARRAY JOIN 语义错误；
- predicate pushdown 在含 JOIN 的查询中不可靠；
- subquery 去关联化能力几乎为零。

新 Analyzer 基于 **QueryTree AST**（[#42648](https://github.com/ClickHouse/ClickHouse/issues/42648)），将 analysis、planning、optimization 完全解耦，每个优化作为独立的 pass 施加在 QueryTree 上。

**关键里程碑**：
- v24.3：Analyzer 默认启用（Beta），旧实现仍可通过 `allow_experimental_analyzer = 0` 回退；
- v24.4：Analyzer 中 predicate pushdown 的 JOIN 传播改进——如果 `WHERE r.origin = 'KSFO'` 且 JOIN condition 为 `l.dest = r.origin`，Analyzer 能自动推导出 `l.dest = 'KSFO'` 并同时下推到左表，消除大量不必要的 JOIN 行（[v24.4 Release Blog](https://clickhouse.com/blog/clickhouse-release-24-04)）；
- v24.4：OUTER JOIN 到 INNER JOIN 的自动转换——当 WHERE 子句过滤掉 outer join 的 null 行时，自动降级为 INNER JOIN；
- v25.12：CBO 方向的第一步——DPsize Join Reorder 算法（见后文）。

> **与 StarRocks 的对比**：StarRocks 的 Optimizer 从立项之初就是 CBO-first 的设计（统计信息驱动的代价模型 + Cascades 框架），而 ClickHouse 直到 v24.x 还是以 rule-based 为主。这几年 ClickHouse Analyzer 的工作，本质上是在补 2015 年就应该做的事。但公平地说，ClickHouse 的执行模型（单查询全核并行）使得 join order 在中小数据集上不那么关键——在几亿行以内的场景，ClickHouse 暴力扫描往往比精细 plan 更实际。

**已知 Breaking Changes**（需要关注升级风险）：
- NULL 聚合行为变化（部分聚合函数对 NULL 的处理语义变更）；
- 某些依赖旧解析器 quirks 的 view 定义在 Analyzer 下会行为不同；
- 生产环境升级到 v24.3 前，强烈建议在 staging 用完整 query log 回放验证。

### 2.2 新 JSON 类型：从 hack 到真正的列式半结构化

ClickHouse 对 JSON 的处理历史可以概括为：`String` + `JSONExtract*` 函数 → `Object('json')`（旧版，本质是 Tuple 展开，v22.x experimental，已废弃）→ 新 JSON 类型（v24.8 experimental，v25.x 逐步生产化）。

新 JSON 类型的设计围绕三个构建块（[Blog: How we built JSON](https://clickhouse.com/blog/a-new-powerful-json-data-type-for-clickhouse)）：

**Variant 类型**：带判别器（discriminator）的 tagged union，类似 Rust 的 `enum`。存储上每个 variant type 有独立的列文件，discriminator 单独一个列文件，读取时按 subcolumn 语法（`c.Int64`）只加载目标类型的列文件，无需反序列化其他类型。

**Dynamic 类型**：Variant 的动态化版本——不需要预先声明所有可能的类型，由 `max_types` 参数控制最多多少种类型存为独立 subcolumn，超出部分落入 SharedVariant（`Map(String, String)` 结构）。

**JSON 类型**：以 Dynamic 为底层，对每个 JSON path 维护一个 Dynamic 列。path 数量由 `max_dynamic_paths`（默认 1024）控制，超出限制的 path 进入 shared data 结构。

v24.8 的初始实现中，shared data 用 `Map(String, String)` 存储，读取低频 path 需要扫描整个 Map 列——在 10k+ paths 的高基数 JSON 场景下，内存和性能都很糟糕。

v25.8 引入了 **Advanced Shared Data Serialization**：对 shared data 进行了专门的列式重组，读取单个低频 path 时不再需要扫描整个 shared data，测试数据显示在 10k paths 场景下：
- 单 path 读取时间快 **58x**（[Blog: JSON 58x faster](https://clickhouse.com/blog/json-data-type-gets-even-better)）；
- 内存使用降低 **3300x**。

> **工程师视角**：这个设计的核心挑战与 StarRocks 的 Variant 类型（用于 semi-structured data）高度相似——都要在"预先不知道 schema"和"保持列式读取优势"之间取得平衡。ClickHouse 的解法是双层结构（dynamic paths + shared data），StarRocks 的解法是 sparse column + column group。两者在读取高基数 path 时都有额外 indirection，只是实现细节不同。ClickHouse 的 v25.8 改进表明他们最初的 shared data 设计确实是个坑，v25.8 才真正填平。

**注意**：新 JSON 类型在 v26.x 之前仍处于 production preview 阶段，`allow_experimental_json_type = 1` 需要显式开启，生产环境需要谨慎评估。

### 2.3 Lightweight Updates（v25.7）：MergeTree 的 DML 革命

ClickHouse 历史上的 `ALTER TABLE ... UPDATE/DELETE` 是重量级的 Mutation 操作：触发对受影响列的全量重写，写放大极高，延迟极长（分钟到小时级），对并发读写有显著影响。轻量级 DELETE（Light-weight DELETE，通过 `_row_exists` 标记删除行，v22.x）是第一步改进，但仍不支持真正的 UPDATE 语法。

v25.7 引入的 **Lightweight Updates** 基于 **patch part** 机制（[v25.7 Release Blog](https://clickhouse.com/blog/clickhouse-release-25-07#lightweight-updates)，[详细技术系列](https://clickhouse.com/blog/updates-in-clickhouse-2-sql-style-updates)）：

1. `UPDATE` 语句触发写入一个极小的 **patch part**，只包含被修改的行和列，不触及其他数据；
2. patch part 在 background merge 中自动合并到 base part，更新被物化；
3. 在 patch part 尚未合并时，读取路径在每个 data range 内实时应用 patch，保证读取正确性，不影响并行度；

```sql
UPDATE orders SET discount = 0.2 WHERE quantity >= 40;
```

上述 UPDATE 在底层：创建一个仅包含 `WHERE quantity >= 40` 行的 patch part，写入 `discount = 0.2`，INSERT 立即返回。

官方 benchmark 数据（[v25.7 vs PostgreSQL](https://clickhouse.com/blog/update-performance-clickhouse-vs-postgresql)）：
- bulk UPDATE 场景最高快 **4000x**（相比 PostgreSQL）；
- 相比 ClickHouse 旧 Mutation 快 **1000x**。

> **与 Databricks Deletion Vectors 的对比**：两者的设计目标相似——都是避免 DML 触发全列重写。但实现路径不同：DV 是"soft delete bitmap + read-time merge"，适合 immutable append + 少量行级删除的场景；patch part 是"delta write + merge-time physical merge"，更接近 LSM-Tree 的 L0 write。ClickHouse 的 MergeTree 本身就是一种特殊的 LSM，patch part 可以认为是在列式存储上实现了"行级 delta"的变体。

### 2.4 Data Lake：从 query engine 到 Lakehouse 的跃升

这是 ClickHouse v24–v25 期间最重要的战略方向转变，也是对 StarRocks Lakehouse 能力的直接挑战。

| Feature | ClickHouse 24.11 | ClickHouse 25.8 |
|---|---|---|
| Catalog（Unity/REST/Glue/Polaris） | ❌ | ✅ |
| Partition Pruning | ❌ | ✅ |
| Statistics-based Pruning | ❌ | ✅ |
| Schema Evolution | ❌ | ✅ |
| Time Travel | ❌ | ✅ |
| Positional Deletes / Equality Deletes | ❌ | ✅ |
| Iceberg Write Support | ❌ | ✅（v26.1） |

v24.12 引入 Iceberg REST Catalog 和 Polaris Catalog 支持（[v24.12 Blog](https://clickhouse.com/blog/clickhouse-release-24-12#iceberg-rest-catalog-and-schema-evolution-support)）；v25.3 LTS 加入 Unity Catalog 和 AWS Glue Catalog（[v25.3 Blog](https://clickhouse.com/blog/clickhouse-release-25-03#aws-glue-and-unity-catalogs)）；v25.5 加入 Hive Metastore；v25.11 加入 Microsoft OneLake（[Alexey 2025 Blog](https://clickhouse.com/blog/alexey-favorite-features-2025)）。

v25.12 更进一步，Iceberg 表的 `ORDER BY` 子句支持 Part-level sorting，使 SELECT 查询能利用物理排序顺序做 skip——这是 ClickHouse 将 MergeTree 思想迁移到 Iceberg 的直接体现：

> `ClickHouse release call 25.12: ClickHouse and Spark are the only engines that utilize part-level sorting in Iceberg.`

---

## 三、执行引擎 / 存储引擎 / 性能优化

### 3.1 向量化执行模型：Pipeline Processor/Port

ClickHouse 的执行模型基于 **Push-based Pipeline**（Processor/Port 模型）：查询被分解为 Processor DAG，每个 Processor 有输入 Port 和输出 Port，数据以 Block（列式批次）在 Port 间流动。这与 Volcano/Iterator 模型（Pull-based，one-tuple-at-a-time）的根本区别在于：Push-based 天然适合流水线并行，减少了函数调用开销。

**SIMD 利用**：ClickHouse 的 SIMD 利用主要在以下层面：
- 列压缩/解压（LZ4 SIMD 加速、Gorilla/DoubleDelta codec）；
- Aggregation 的 Hash Table 探测（Swiss Table / Two-Level Hash Table）；
- 字符串函数（Volnitsky 字符串搜索算法）；
- AVX-512 在 v24.3 起通过 `RUSTFLAGS` 和编译选项逐步扩展覆盖。

> **与 StarRocks 的 SIMD 对比**：StarRocks 在 SIMD 利用上采用了更系统化的列向量 BitmaskColumn 设计，nullable 的判断通过 AVX2 popcount 批量处理；ClickHouse 的 SIMD 更分散，集中在特定算子（sort、hash join probe）。整体上 ClickHouse 的向量化执行更"有机生长"，StarRocks 的设计更工整，但两者的实际性能在宽表扫描 + 聚合场景下差异不大。DuckDB 的 Vectorized Interpretation（基于 Vector Register Machine）是另一套设计哲学，在小数据集上更有优势。

**Aggregation**：ClickHouse 的两级 Hash Table（Two-Level Aggregation）是高基数 GROUP BY 的核心优化——第一级 hash 做 pre-aggregation，第二级合并，避免单一超大 hash table 导致的 cache miss 雪崩。这在 v24.x 有持续的 memory compaction 优化（v24.8：Join table engine OPTIMIZE 后内存降低 30%）。

### 3.2 查询优化器：Analyzer + 迈向 CBO

**v25.12 DPsize Join Reorder**（[v25.12 Release Blog](https://clickhouse.com/blog/clickhouse-release-25-12)）是 ClickHouse CBO 方向的第一个实质性步骤。

DPsize 算法是经典动态规划 Join 枚举的 size-based 变体，与 PostgreSQL 的实现同源。相较于原来的 greedy 算法（每次选代价最小的下一个 join），DPsize 构建完整的 bottom-up 最优 join plan，能找到更优的 join 树形状。

使用方式：
```sql
SET allow_experimental_analyzer = 1;
SET query_plan_optimize_join_order_algorithm = 'dpsize,greedy';
SET allow_statistic_optimize = 1;
```

官方 TPC-H Q5（8 表 join，scale factor 100）测试数据：DPsize 相比 greedy 快约 **4.7%**。

这个数字看起来不惊艳，但背后的意义是：ClickHouse 的 CBO 基础设施（statistics + cost model + DP-based plan enumeration）已经打通，未来随着统计信息质量的提升，收益会进一步放大。

**当前 CBO 的局限**：
- Statistics（列统计信息）仍需手动 `ANALYZE TABLE` 触发，没有 auto-analyze 机制；
- DPsize 目前只支持 INNER JOIN，OUTER JOIN 的 join reorder 仍是 roadmap 项；
- cost model 对于 ClickHouse 的 MergeTree 存储特性（sparse index、data skipping）的集成仍不完整。

> **待验证**：ClickHouse 2025 Roadmap（[#74046](https://github.com/ClickHouse/ClickHouse/issues/74046)）列出了"Correlated subqueries with decorrelation"，但截至 v25.12 尚未合入 production。去关联化对于复杂分析查询至关重要，StarRocks 在这方面已经非常成熟，ClickHouse 的差距在这里仍然显著。

### 3.3 存储层：MergeTree 的持续进化

**Sparse Index（稀疏索引）与 Adaptive Granularity**：MergeTree 的主键索引是稀疏的（Sparse Index），每 `index_granularity`（默认 8192）行存一个索引条目。Adaptive Granularity（`adaptive_index_granularity_bytes`，默认 10MB）根据列数据大小自动调整粒度，对宽行数据有显著的 I/O 节省。

这个设计与 StarRocks 的 Short-key Index 类似，但 ClickHouse 的稀疏粒度更粗，在高选择性点查场景下需要依赖 Data Skipping Index（Bloom Filter、Set、NGram 等）补充。

**Data Skipping Index 的有效性边界**：
- MinMax Index：对范围查询有效，对随机点查无效；
- Bloom Filter：对等值查询有效，存在误报率（false positive），在高基数列上误报率低；
- Set Index：对小 IN 集合有效，集合过大时退化；
- NGram/Token Bloom Filter（v24.x 引入改进）：对 LIKE 查询有用，但需要谨慎控制 false positive。

**已知陷阱**：Data Skipping Index 的有效性严重依赖数据的物理排列——如果主键与过滤列的相关性不强，索引几乎没有收益。这是 ClickHouse 被诟病的典型场景：多维过滤（过滤列不在主键前缀）时，要么依赖 Data Skipping Index（效果有限），要么依赖 Projection（维护成本高），没有 StarRocks 全局字典编码 + 多列 Bitmap Index 那样灵活。

**v25.12 Lazy Reading 75x 提速**：这是一个重要的执行优化——在 ORDER BY ... LIMIT N 查询（Top-N）中，当 ORDER BY 列已经有 Data Skipping Index 可以跳过不需要的 granule 时，对其他列的读取推迟到确认该 granule 有效后才进行。这将 Top-N 查询的不必要 I/O 大幅削减，官方数据 75x 提速主要针对 IO-bound 的 Top-N 场景。

---

## 四、云原生架构：SharedMergeTree 与 SharedCatalog

### 4.1 SharedMergeTree：stateless compute 的核心

经典 ReplicatedMergeTree 的扩展瓶颈在于：即使数据存在 S3（zero-copy replication），**Part 元数据仍存在每个节点本地**。每次 INSERT、MERGE、MUTATION，元数据必须在所有 replica 之间同步，节点数量越多，Keeper 的协调开销越大，扩容速度越慢。

SharedMergeTree 的根本改变（[官方文档](https://clickhouse.com/docs/cloud/reference/shared-merge-tree)，[Jack Vanlightly 深度分析](https://jack-vanlightly.com/analyses/2024/1/23/serverless-clickhouse-cloud-asds-chapter-5-part-2)）：
- **数据**：全部在共享 S3/GCS/ADLS；
- **元数据**：集中存储在 ClickHouse Keeper，所有计算节点共享；
- **计算节点**：完全 stateless，只有 ephemeral 的本地 SSD Cache；
- **副本间通信**：彻底消除，replica 之间不直接通信，全部通过 Keeper 协调。

```json
[ReplicatedMergeTree]: 数据 → S3，元数据 → 每节点本地（需要 replica 间同步）
[SharedMergeTree]:     数据 → S3，元数据 → Keeper（单点真相，replica 异步 fetch）
```

扩缩容性质变：从"分钟级 VM 启动 + 数据同步"变为"秒级 container 启动 + 元数据 fetch"。官方描述支持同一张表数百个 replica，动态无 shard 扩展。

**2025 年的进一步演进**：SharedCatalog（[Blog: stateless compute](https://clickhouse.com/blog/clickhouse-cloud-stateless-compute)，2025-07）将 database 元数据（`CREATE TABLE` DDL）也从节点本地的 `.sql` 文件迁移到 Keeper，实现了真正意义上的全状态下沉，compute 节点变为纯内存状态的 stateless 服务。这是 ClickHouse Cloud 2025 年最重要的架构改进。

**[ClickHouse-Cloud-only] 说明**：SharedMergeTree 在 ClickHouse Inc. 内部是闭源的。开源社区的 RFC [#54644](https://github.com/ClickHouse/ClickHouse/issues/54644) 提出了基于 `S3_plain` disk + Keeper metadata 的开源替代方案，但截至 v26.1 仍在讨论中，没有官方承诺的时间线。

### 4.2 与其他存算分离系统的对比

| 维度 | ClickHouse SharedMergeTree | Databricks Delta Lake | Snowflake |
|---|---|---|---|
| 存储格式 | 自研 MergeTree（Parquet-incompatible） | Parquet（开放） | 自研（闭源） |
| 元数据存储 | ClickHouse Keeper（ZooKeeper-compatible） | Delta Log（JSON/Parquet） | 云原生托管 |
| Compute 间共享 | 是，通过 Keeper 异步同步 | 是，通过 Delta Log | 是，通过 Virtual Warehouse |
| 格式互操作 | 无（MergeTree 不开放读取协议） | UniForm / Iceberg REST | Iceberg Horizon |
| 开源可用性 | 否 | Delta Lake 开源（特性部分闭源） | 否 |

ClickHouse Cloud 的最大劣势是**格式锁定**：SharedMergeTree 的数据在 S3 上不可被 Spark/Trino/StarRocks 直接读取（没有开放的读取协议），而 Delta Lake 的 Parquet 文件可以被任何支持 Parquet 的工具读取。这对需要多引擎混用的企业用户是一个实质性壁垒。

---

## 五、运维智能化与可观测性

### 5.1 内置可观测性体系

ClickHouse 的可观测性是其重要竞争优势之一——`system.*` 表体系几乎覆盖了所有运维需要的诊断信息：

- `system.query_log`：所有查询的完整执行统计（read_rows、memory_usage、query_duration_ms 等），是慢查询分析的核心；
- `system.part_log`：Part 生命周期事件（INSERT、MERGE、REMOVE），分析 Merge 行为的必备工具；
- `system.merge_log`（v24.x+）：更细粒度的 Merge 过程日志；
- `system.processors_profile_log`（v23.x+）：Pipeline 中每个 Processor 的执行统计，用于算子级性能分析。

**EXPLAIN 体系**（近年持续增强）：
```sql
EXPLAIN PLAN SELECT ...;       -- 逻辑查询计划
EXPLAIN PIPELINE SELECT ...;   -- 执行 Pipeline DAG
EXPLAIN ESTIMATE SELECT ...;   -- 预估读取的 rows/bytes
EXPLAIN indexes = 1 SELECT ...; -- 展示 index 利用情况
```

v25.x 中，`EXPLAIN PIPELINE` 引入了更详细的 Processor 级别信息，便于识别 pipeline 中的 bottleneck。

> **与 StarRocks Query Profile 的对比**：StarRocks 的 Profile 系统提供 fragment/pipeline/operator 三层级的执行统计，对分布式执行的 skew 和 bottleneck 定位更直观；ClickHouse 的 `system.processors_profile_log` 在功能上类似但维度更粗，且对 SharedMergeTree 的分布式执行路径分析支持有限。**[ClickHouse-Cloud-only]** Query Insights（2024 年 7 月上线）提供 UI 级别的慢查询分析和 UDF 调用追踪，但开源版用户需要自己搭 Grafana + system table 查询方案。

### 5.2 自动化运维的现实

ClickHouse 的**自动 Merge** 是后台的 background thread pool 调度，参数（`background_pool_size`、`merge_max_block_size`）均可调，但没有类似 Databricks Predictive Optimization 那样的全局查询感知优化。

**Refreshable Materialized View**（v23.x 引入，v24.x 稳定化）：支持周期性全量刷新的物化视图，弥补了 ClickHouse 增量物化视图（Insert Trigger MV）在一致性上的已知问题（跨分区 INSERT 时的一致性 edge case）。但 Refreshable MV 本质上是定时重算，对实时性要求高的场景仍需依赖 Insert Trigger MV。

**ClickHouse Keeper 替代 ZooKeeper**：Keeper 是 ClickHouse 基于 Raft 协议实现的 ZooKeeper 兼容替代品，从 v22.x 开始逐步生产化，v24.x 起在新部署中推荐优先使用。在 SharedMergeTree 架构中，Keeper 承担了所有元数据协调职责，其稳定性和性能直接决定系统可用性。已知问题：Keeper 在超大集群（数百个 replica）下的 throughput 上限是工程挑战，正在通过 ClickHouse 2025 Roadmap 的 [Keeper Sharding RFC](https://github.com/ClickHouse/ClickHouse/issues/74046) 解决。

---

## 六、技术、产品与商业化综合洞察

### 6.1 横向对比：ClickHouse 的独特取舍

**"单查询吃满所有核"的并发哲学**：ClickHouse 默认 `max_threads = number_of_cpu_cores`，一个查询会并发使用所有 CPU 核。这在低并发（10–100 QPS）大查询场景下是正确的选择，能压榨硬件极限；但在高并发（1000+ QPS）中小查询场景，单查询多线程导致线程调度开销和 CPU cache 竞争，吞吐量反而不如 MPP 系统（StarRocks）或单线程并发（DuckDB embedded）。

ClickHouse Parallel Replicas（v23.x+）是对这一局限的部分补偿：允许一个查询跨多个 replica 并行扫描，但仍然是 single-coordinator 架构，和 MPP 的 distributed planning 有本质区别。

**MergeTree Sparse Index vs. StarRocks ZoneMap + 全局字典**：

| 维度 | ClickHouse Sparse Index | StarRocks ZoneMap |
|---|---|---|
| 粒度 | 8192 行（可配置） | Segment（数据块） |
| 多列过滤 | 需要 Data Skipping Index | ZoneMap 天然多列 |
| 高基数 | 需要 Bloom Filter Index | Bitmap Index + 全局字典 |
| 维护成本 | 自动（写入时） | 自动（写入时） |

ClickHouse 的 Sparse Index 设计在主键顺序扫描场景（时序、日志）下极高效，但在多维随机过滤场景下劣势明显——Data Skipping Index 需要手动建立，且 false positive 率管理是运维负担。

**JOIN 的历史包袱与近期改善**：ClickHouse 在 JOIN 上的弱点是历史公认的——Hash Join 无 spill（超内存直接 OOM），大表 JOIN 需要用 Global JOIN + broadcast；OUTER JOIN 语义历史上有 bug（Analyzer 之前）。

v24.5 开始支持不等条件 JOIN（`allow_experimental_join_condition`）；v24.8 扩展了 SEMI/ANTI JOIN 的不等条件支持；Hash Join spill to disk 在 2024–2025 Roadmap 中出现（[#74046](https://github.com/ClickHouse/ClickHouse/issues/74046)），但截至 v25.12 未见 GA。这仍然是 ClickHouse 与 StarRocks/DuckDB 相比的显著短板。

### 6.2 产品战略重心演变

**v22.x 及之前（功能快速堆叠期）**：Yandex 主导时期留下的技术债 + ClickHouse Inc. 初期"先做 feature 展示商业价值"的策略，导致这个时期的很多 feature 处于半成品状态（旧 JSON type、初期 Projection、早期 MV 一致性问题）。

**v23.x（质量与云化期）**：Analyzer 开始 experimental 落地，ClickHouse Cloud 商业化加速，SharedMergeTree 在 Cloud 内成熟。这个版本的重心是"把已有的东西做对"——Keeper 替代 ZooKeeper、Light-weight DELETE 稳定化、Parallel Replicas 上线。

**v24.x（Analyzer GA + 半结构化爆发期）**：Analyzer 默认启用是这个版本周期最重要的节点；新 JSON / Variant / Dynamic 类型的实验性落地是半结构化数据能力的质变；JOIN 能力持续补强（不等条件 JOIN、SEMI/ANTI 扩展）。这个阶段的竞争目标是"让 ClickHouse 能处理更复杂的查询"，直接对标 Databricks SQL 和 BigQuery。

**v25.x（Data Lake 全面布局 + 写入能力革命）**：Data Lake 从 v24 末期的"能用"到 v25.8 的"生产就绪"；Lightweight Updates（v25.7）是 DML 能力的质变；DPsize Join Reorder（v25.12）是 CBO 方向的第一步。这个阶段的战略意图是**从 AP-only 系统向"通用实时数据平台"演进**，直接竞争的不再只是 ClickHouse benchmark 领域的同类，而是整个 Lakehouse 赛道。

### 6.3 商业化：Apache 2.0 开源下的护城河

ClickHouse 宣称完全 Apache 2.0 开源，这与 Databricks（核心特性闭源）或 Snowflake（完全闭源）的策略截然不同，形成了"开源信仰"的品牌优势。

但实际的商业护城河在于：
1. **SharedMergeTree + SharedCatalog**：最关键的云原生架构创新不开源；
2. **托管运维的规模效应**：ClickHouse Cloud 在 ARM Graviton、S3 Express One Zone 等基础设施优化上的积累，自建集群难以复制；
3. **ClickPipes 数据集成生态**：MySQL/MongoDB/Postgres CDC、Kinesis、ABS 等托管 connector，降低了数据入湖门槛；
4. **企业合规（HIPAA/PCI）**：Enterprise tier 提供的合规认证，自建无法快速复制。

**DuckDB 的崛起与竞争重叠**：DuckDB 的定位是嵌入式 OLAP（embedded，in-process），与 ClickHouse 的部署模式（独立服务器）本质上不同，用户群体有重叠但不完全相同。DuckDB 更适合"数据科学家笔记本里跑 100GB 以内的分析"，ClickHouse 更适合"生产环境 TB 级实时分析"。但在 ClickHouse Local（CLI 模式）场景下，两者确实存在直接竞争，DuckDB 更简单的部署方式和更完整的 SQL 兼容性（特别是 CTE 和复杂 JOIN）是其优势。

**AI 布局**：
- **Vector Similarity Search**（基于 usearch/HNSW）：**[Experimental]**，v24.x 进入 early access waitlist（[Cloud Changelog](https://clickhouse.com/docs/whats-new/changelog/cloud)）。定位是"已有 ClickHouse 用户的向量检索补充"，不是专业向量数据库的竞争者；
- **MCP Server**（[GitHub](https://github.com/ClickHouse/mcp-clickhouse)）：2025 年增长最快的集成方式，与 Databricks Assistant 类似的 AI-native 数据交互方向；
- **ClickStack**：基于 ClickHouse 的开源可观测性栈（logs + metrics + traces），是 ClickHouse 进入 DevOps/SRE 市场的产品载体，OpenAI、Netflix 等公司的大规模部署案例是重要 social proof。

---

## 七、综合评价与展望

### 已确定的技术方向

1. **CBO 全面化**：DPsize 是开端，2026 年应会看到更完整的统计信息自动收集（类似 Auto Analyze）+ OUTER JOIN reorder + 更精准的 cost model。ClickHouse 的 Analyzer 基础设施已经就绪，CBO 的差距会在 2026–2027 年快速缩小；

2. **Data Lake 写入**：Iceberg/Delta Lake 写入支持（v26.x）将使 ClickHouse 从 Lakehouse query engine 变为完整的 Lakehouse citizen，对 StarRocks 的 Lakehouse 竞争格局有直接影响；

3. **Lightweight Updates 的生态扩散**：patch part 机制如果被 SharedMergeTree 充分利用，可以进一步降低 CDC-driven UPSERT 场景的写放大，这对实时数仓场景是重要的 use case 扩展；

4. **Text Index（Full-text Search）**：v25.9 的实验性 text index 是新的竞争维度，与 Elasticsearch/OpenSearch 争夺日志和文本搜索市场。

### 需要关注的风险

1. **SharedMergeTree 不开源**：开源社区用户无法享受最核心的云原生架构优化，长期可能导致开源版和云版的能力差距越来越大，影响社区信任；

2. **Hash Join Spill 仍未 GA**：在需要复杂多表 JOIN 的场景下，ClickHouse 对内存的要求仍然苛刻，这是生产稳定性的隐患；

3. **Analyzer 的 Breaking Changes 债务**：v24.3 默认启用 Analyzer 后，仍有部分历史 query 行为变化需要用户适配。大型生产系统的升级迁移成本不可小觑；

4. **JSON 类型的稳定性**：v26.1 之前，新 JSON 类型仍处于 experimental/preview 状态，`max_dynamic_paths` 的调参对用户提出了较高要求，不了解底层机制的用户容易踩坑（达到上限后落入 shared data 的性能退化）。

---

## 参考资料

- [ClickHouse Changelog 2024](https://clickhouse.com/docs/en/whats-new/changelog)
- [ClickHouse Changelog 2025](https://clickhouse.com/docs/whats-new/changelog)
- [Alexey's Favorite Features of 2025](https://clickhouse.com/blog/alexey-favorite-features-2025)
- [ClickHouse 2025 Roundup](https://clickhouse.com/blog/clickhouse-2025-roundup)
- [ClickHouse Release 24.3 – Analyzer Beta Default](https://clickhouse.com/blog/clickhouse-release-24-03)
- [ClickHouse Release 24.4 – Analyzer JOIN Improvements](https://clickhouse.com/blog/clickhouse-release-24-04)
- [ClickHouse Release 24.8 LTS – New JSON Type](https://clickhouse.com/blog/clickhouse-release-24-08)
- [ClickHouse Release 25.7 – Lightweight Updates](https://clickhouse.com/blog/clickhouse-release-25-07)
- [ClickHouse Release 25.12 – DPsize Join Reorder, Lazy Reading](https://clickhouse.com/blog/clickhouse-release-25-12)
- [Blog: How we built a new powerful JSON data type](https://clickhouse.com/blog/a-new-powerful-json-data-type-for-clickhouse)
- [Blog: Making complex JSON 58x faster (v25.8)](https://clickhouse.com/blog/json-data-type-gets-even-better)
- [Blog: Lightweight Updates – Part 2 (Patch Parts)](https://clickhouse.com/blog/updates-in-clickhouse-2-sql-style-updates)
- [Blog: ClickHouse Cloud Stateless Compute / SharedCatalog](https://clickhouse.com/blog/clickhouse-cloud-stateless-compute)
- [Blog: SharedMergeTree + Lightweight Updates](https://clickhouse.com/blog/clickhouse-cloud-boosts-performance-with-sharedmergetree-and-lightweight-updates)
- [Docs: SharedMergeTree](https://clickhouse.com/docs/cloud/reference/shared-merge-tree)
- [Docs: New JSON Type](https://clickhouse.com/docs/sql-reference/data-types/newjson)
- [Jack Vanlightly: Serverless ClickHouse Cloud Architecture](https://jack-vanlightly.com/analyses/2024/1/23/serverless-clickhouse-cloud-asds-chapter-5-part-2)
- [GitHub: Analyzer Migration Umbrella Issue #42648](https://github.com/ClickHouse/ClickHouse/issues/42648)
- [GitHub: RFC – MergeTree over S3 improvements #54644](https://github.com/ClickHouse/ClickHouse/issues/54644)
- [GitHub: Roadmap 2025 #74046](https://github.com/ClickHouse/ClickHouse/issues/74046)
- [GitHub: JSON Type Improvements Umbrella #68428](https://github.com/ClickHouse/ClickHouse/issues/68428)
- [v25.12 Release Slides](https://presentations.clickhouse.com/2025-release-25.12/)
