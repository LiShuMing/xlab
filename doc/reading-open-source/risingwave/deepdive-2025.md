我是一名拥有 10 年以上经验的资深研发工程师，目前是顶尖开源 OLAP 数据库
（[StarRocks](https://github.com/StarRocks/starrocks)）的核心开发者与 Committer。
我的日常技术栈围绕 C++、高并发、分布式系统、向量化执行以及底层性能压榨。
同时，我也在积极拥抱 AI 时代，探索 LLM、RAG 和前沿编程语言（如 Rust、Haskell）。

请参考 RisingWave 的官方文档、官方博客、GitHub 提交历史
（risingwavelabs/risingwave）、GitHub Issues/Discussions、
社区 Slack，以及 RisingWave Labs 技术博客进行综合分析：

**分析维度要求如下：**

1. **重大 Feature 与场景支持**：总结近年来（重点聚焦 v1.0 至最新版本，
   2023–2025 年）最重要的功能特性：

   - **流处理核心：Streaming SQL 执行模型**：
     RisingWave 的核心设计哲学——
     将流处理问题转化为**增量维护物化视图**（Incremental View
     Maintenance，IVM）的问题；
     与 Flink（DataStream + Table API）设计哲学的本质差异
     （声明式 SQL-first vs 命令式算子-first）；
     Streaming DAG 中各算子的增量计算语义
     （Stateful Operator 的 Delta 输入 → Delta 输出）；
   - **存储引擎：Hummock（LSM-tree on Object Storage）**：
     RisingWave 自研的云原生状态存储引擎——
     完全基于对象存储（S3/OSS）的 LSM-tree 实现；
     SSTable 的上传策略（Staging → L0 → Ln）；
     Compaction 策略（Tiered / Leveled）与
     流处理状态访问模式的适配；
     Write Buffer（Memtable）到 S3 的持久化路径；
     Bloom Filter 在 Hummock 各层的布局；
     与 RocksDB（Flink State Backend）的设计对比
     （本地磁盘 vs 远端对象存储的延迟权衡）；
   - **一致性与 Checkpoint**：RisingWave 的 Barrier-based
     Checkpoint 机制——Barrier 注入流图的传播过程；
     与 Flink Aligned Checkpoint 的异同；
     Epoch-based MVCC（每个 Checkpoint 对应一个 Epoch）
     在 Hummock 中的实现；
     Exactly-Once 语义的端到端保证边界；
   - **PostgreSQL 兼容层**：RisingWave 以 PG 协议为接入标准——
     `pg_catalog` 覆盖度；
     Sink 写入下游（Kafka / Iceberg / MySQL / PG）的
     Delivery Guarantee；
     Source Connector（Kafka / CDC / S3）的实现架构；
   - **批流统一（Batch Query on Materialized Views）**：
     对物化视图执行 Ad-hoc 查询的执行路径——
     是直接读取 Hummock 的 SSTable 还是走独立的
     Batch Executor；与纯流处理系统（只有 Streaming Query）
     的差异；

2. **执行引擎深度**：

   - **流式算子实现**：
     Streaming Hash Aggregation 的状态结构
     （Hash Table in Hummock vs in-memory）；
     Streaming Hash Join（Stream-Stream Join）的
     两侧状态管理——Left State / Right State 的
     Hummock 存储布局；Join 窗口（时间窗口 vs 无界 Join）
     的内存状态上限问题；
     Watermark 机制与 Event Time 窗口的实现
     （与 Flink Watermark 语义的对比）；
     Top-N（`LIMIT` on Streaming）的状态存储优化
     （Managed Top-N vs AppendOnly Top-N）；
   - **向量化批处理引擎**：
     RisingWave 批处理路径基于 Arrow 格式的
     向量化执行器实现；
     Streaming 路径与 Batch 路径共享同一套
     表达式求值框架的设计；
   - **查询优化器**：
     流式查询计划的优化——如何将 SQL 查询
     转化为 Streaming DAG（LogicalPlan → StreamPlan）；
     物化视图 Rewrite（透明查询改写）的实现深度；
     批处理 CBO 的实现现状；
   - **分布式架构**：
     Meta Node / Compute Node / Frontend / Compactor
     四类节点的职责划分；
     Streaming Job 的 Fragment 调度
     （Actor 模型，每个 Fragment 对应多个 Actor）；
     Scale-out / Scale-in 时 State 重分布（Rescaling）
     的实现机制——这是流处理系统弹性伸缩最难解决的问题；

3. **与主流流处理系统的深度对比**：

   - **vs Apache Flink**：
     核心差异——RisingWave 的 IVM 模型 vs
     Flink 的 Dataflow 模型；
     状态存储——Hummock（S3 LSM） vs
     RocksDB（本地磁盘）/ ForSt（Flink 定制 RocksDB）；
     SQL 完备性——RisingWave 的 Streaming SQL
     vs Flink SQL（两者均基于 Calcite 解析，
     但执行语义差异显著）；
     Rescaling（弹性伸缩）的难度对比；
     生产成熟度与企业采纳现状；
   - **vs Materialize**（另一个 SQL-on-Streams 系统）：
     同样基于 Differential Dataflow / IVM 思想的
     两个系统的架构差异（Materialize 基于 Rust + PERSIST，
     RisingWave 的 Hummock 自研路径）；
   - **vs StarRocks（你的视角）**：
     StarRocks 的 Materialized View 与
     RisingWave 的 Streaming Materialized View 的
     根本差异（批量刷新 vs 增量实时维护）；
     在"实时数仓"场景下两者的定位边界；

4. **商业化与生态**：

   - **RisingWave Cloud**：托管服务的商业模式；
     与 Confluent Cloud / Ververica Cloud 的竞争定位；
   - **Rust 技术栈**：全栈 Rust 实现的工程收益
     （内存安全、async/await、编译器优化）；
     与 Flink（JVM）在极限吞吐场景的性能对比；
   - **生态整合**：Source/Sink Connector 覆盖度
     （Kafka / Kinesis / CDC / Iceberg / Delta /
     PostgreSQL / MySQL）；
     dbt 集成现状；BI 工具兼容性；

**参考资料：**
- https://docs.risingwave.com/
- https://github.com/risingwavelabs/risingwave/releases
- https://risingwave.com/blog/
- *RisingWave: A Scalable Stream Processing System*（相关论文）
- *Napa: Powering Scalable Data Warehousing with Robust Query
  Performance at Google*（VLDB 2021，IVM 背景参考）
- *Materialize: Incremental View Maintenance for PostgreSQL*
  （背景参考）

**输出格式要求：**
- 重点聚焦 RisingWave 的**核心差异化技术**
  （Hummock 存储引擎 + Barrier Checkpoint + IVM 模型），
  避免泛泛描述流处理基础概念；
- 文章结构建议：
  **Executive Summary
  → IVM 设计哲学：流处理即物化视图增量维护
  → Hummock：云原生 LSM-tree 存储引擎深度解析
  → Barrier Checkpoint：一致性机制与 Exactly-Once 保证
  → 流式算子实现：Hash Agg / Stream Join / Top-N 状态管理
  → Rescaling：弹性伸缩的工程挑战
  → 批流统一：Batch Query on Streaming State
  → 竞品深度对比（Flink / Materialize / StarRoc