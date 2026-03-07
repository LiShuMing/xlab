我是一名拥有 10 年以上经验的资深研发工程师，目前是顶尖开源 OLAP 数据库
（[StarRocks](https://github.com/StarRocks/starrocks)）的核心开发者与 Committer。
我的日常技术栈围绕 C++、高并发、分布式系统、向量化执行以及底层性能压榨。
同时，我也在积极拥抱 AI 时代，探索 LLM、RAG 和前沿编程语言（如 Rust、Haskell）。

请参考 StarRocks 的官方文档、官方博客、GitHub 提交历史
（StarRocks/starrocks）、GitHub Issues/Discussions、
社区 Slack，以及 StarRocks Inc 技术博客进行综合分析。

**特别说明**：本报告的受众是 StarRocks 核心开发者本人，因此：
- **不需要介绍基础架构**（FE/BE 分层、MPP 执行、向量化引擎基础
  等你已熟知的内容可一笔带过）；
- **重点聚焦以下三类内容**：
  ① 你可能没有深度参与的模块的内部设计细节；
  ② 社区与外部用户视角的真实痛点与评价
    （GitHub Issues 中高频出现的问题类型）；
  ③ 竞品（Doris / ClickHouse / Databricks / Snowflake）
    对 StarRocks 的技术挑战点；

**分析维度要求如下：**

1. **近期重大 Feature 深度解析**：总结近年来（重点聚焦 v3.0 → v3.1
   → v3.2 → v3.3，2023–2025 年）你可能没有完整跟踪的模块演进：

   - **存算分离（Shared-Data，v3.0 GA）**：
     StarRocks 存算分离架构的完整技术细节——
     StarCache（本地 SSD 缓存层）的缓存粒度（Tablet 级别 vs
     Block 级别）与一致性保证；
     Persistent Index 在对象存储场景下的存储布局变化；
     CN（Compute Node）的无状态化设计与 BE 的兼容路径；
     多 Warehouse（计算集群）共享同一 Storage 的
     隔离机制与元数据并发控制；
     与 Snowflake Virtual Warehouse / Databricks
     存算分离的架构对比；
   - **物化视图透明改写（v2.5+ 持续增强）**：
     透明改写的 Rule 覆盖范围——当前支持哪些 Join 类型
     的改写、哪些聚合函数的改写、嵌套物化视图的改写；
     改写匹配算法（Query-to-MV Subsumption 检测）的实现；
     多物化视图候选时的 Cost-based 选择；
     物化视图的增量刷新（Partition-level Refresh）
     在分区裁剪的实现细节；
     与 Doris 异步物化视图 / Databricks Materialized View
     的能力对比；
   - **Primary Key 表（v2.0+ 持续优化）**：
     Persistent Index 的设计——
     L0（内存 + WAL）/ L1（本地磁盘 B-tree）/ L2
     三层结构的合并策略；
     Update-Delete 路径的写入放大分析；
     Compaction 策略（Size-tiered vs Leveled）
     对 Primary Key 表查询性能的影响；
     与 Doris Unique Key 表 / ClickHouse
     ReplacingMergeTree 的实现对比；
   - **数据湖分析能力（External Catalog，v2.3+）**：
     Hive / Iceberg / Delta / Hudi / Paimon Catalog
     的元数据缓存策略（本地 Cache + 异步刷新）；
     Native Parquet / ORC Reader 的 Late Materialization
     与 Row-level Filter 实现；
     Iceberg Equality Delete 的 MOR 实现现状；
     与 Trino / Spark 在湖上查询性能的对比；
   - **Query Cache（v2.5+）**：
     Tablet 级别 Query Result Cache 的设计——
     缓存 Key 的构造（涉及 Partition Version）；
     Cache Invalidation 策略（数据更新时的精确失效）；
     Colocate 场景下的缓存命中率分析；

2. **执行引擎内核：你可能没有深度参与的模块**：

   - **CBO 优化器深度**：
     统计信息的采样算法（`ANALYZE TABLE` 的采样策略）；
     Histogram 的桶数选择与 MCV（Most Common Values）
     的存储格式；
     Join Reorder 的动态规划实现——
     当 Join 表数超过阈值时的启发式降级策略；
     Subquery Unnesting 的规则覆盖范围；
     与 Doris Nereids / Calcite-based Optimizer 的
     规则体系对比；
   - **Pipeline 执行引擎（v2.3+ 默认启用）**：
     Driver 与 OperatorChain 的关系；
     IO Task 与 CPU Task 的分离调度；
     LocalExchange 算子的实现
     （PassThrough / Partition / Broadcast 模式）；
     Back-pressure 在 Pipeline 中的传递机制；
     与 Doris Pipeline Engine 的实现差异；
   - **Spill to Disk**：
     Hash Join / Hash Aggregate / Sort 算子的
     Spill 触发阈值与分区策略；
     Spill 文件格式（是否基于 Arrow / 自定义格式）；
     Spill 与 Pipeline 背压的协同机制；
   - **Runtime Filter**：
     RF 的类型（Bloom Filter / In-list / Min-Max）
     在不同场景的选择策略；
     跨 Fragment 的 RF 传递协议（GRF 全局 RF）；
     RF 构建完成前的 Probe 端等待策略（Early RF vs Late RF）；

3. **社区真实痛点分析**（从用户视角）：

   - **GitHub Issues 高频问题分类**：
     OOM 类问题的根因分布（哪些算子最容易触发）；
     Schema Change 阻塞写入的用户投诉频率与根因；
     Compaction 积压导致查询变慢的报告模式；
     External Catalog 元数据不一致的投诉类型；
   - **文档与易用性**：
     用户反馈最难理解的配置项
     （`pipeline_dop` / `query_cache_size` /
     `enable_materialized_view_rewrite` 等）；
     与 ClickHouse 文档质量的用户比较评价；
   - **运维复杂度**：
     FE 的 BDBJE（BerkeleyDB Java Edition）元数据存储
     的运维痛点（脑裂、恢复复杂）；
     BE Tablet 数量膨胀的管理挑战；
     存算分离模式下的调试复杂度；

4. **竞品对 StarRocks 的技术挑战**：

   - **Doris 的追赶**：Nereids 优化器成熟后
     在复杂查询场景的性能差距收窄；
     Doris 物化视图能力的追赶速度；
     Apache 品牌对企业采购的影响；
   - **ClickHouse 的防御优势**：
     ClickHouse 在高并发点查（低延迟 OLAP）场景的
     性能优势是否被 StarRocks 追平；
     ClickHouse 生态（Grafana / Superset 集成成熟度）
     对 StarRocks 的压力；
   - **Databricks / Snowflake 的下压**：
     在 Lakehouse 场景，用户是否会选择
     "Databricks 一站式"而跳过 StarRocks；
     StarRocks on Iceberg / Delta 的竞争力
     vs 原生 Spark / Databricks SQL；
   - **DuckDB / MotherDuck 的侧翼**：
     单机 OLAP 场景（< 1TB）DuckDB 对 StarRocks
     的替代威胁；MotherDuck 在小团队市场的切入；

5. **技术路线与商业化综合洞察**：

   - **开源策略**：Apache 2.0 全开源 vs
     部分企业功能闭源的边界（CelerData 商业版
     独有功能清单）；与 Doris / ClickHouse 开源策略对比；
   - **CelerData 商业化路径**：
     CelerData Cloud（托管 StarRocks）的技术架构；
     与 MotherDuck / Databricks 的市场定位差异；
   - **社区国际化**：英文文档质量的演进；
     海外贡献者占比趋势；
     与 ClickHouse（更强国际化）的社区对比；
   - **技术路线前瞻**：
     存算分离 Shared-Data 的下一步（Multi-Warehouse GA）；
     向量化引擎的 SIMD 优化空间（AVX-512 覆盖率）；
     AI/ML 集成方向（向量检索 / Feature Store 集成）；

**参考资料：**
- https://docs.starrocks.io/
- https://github.com/StarRocks/starrocks/releases
- https://www.starrocks.io/blog
- https://www.celerdata.com/blog
- StarRocks 相关论文与技术分享（VLDB / SIGMOD Workshop）

**输出格式要求：**
- **假设读者是 StarRocks 核心开发者**，跳过基础概念介绍，
  直接切入工程细节与设计权衡；
- 对用户痛点部分，**直接引用 GitHub Issue 编号
  或社区讨论链接**，不要泛泛而谈；
- 对竞品挑战部分，要有**具体的 benchmark 数据或
  用户案例**支撑，避免主观判断；
- 文章结构建议：
  **Executive Summary（面向 StarRocks 核心开发者的特别说明）
  → 存算分离 Shared-Data：StarCache + CN 无状态化深度解析
  → 物化视图透明改写：规则覆盖度与 Cost-based 选择
  → Primary Key 表：Persistent Index 三层结构与写入放大
  → CBO 优化器：统计信息精度与 Join Reorder 降级策略
  → Pipeline 执行引擎：Driver 调度 + Spill + Back-pressure
  → 湖仓分析：External Catalog 元数据缓存与 Iceberg MOR
  → 社区真实痛点：GitHub Issues 高频问题根因分析
  → 竞品技术挑战：Doris / ClickHouse / Databricks / DuckDB
  → 商业化与开源策略
  → 总结与展望**；