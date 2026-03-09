我是一名拥有 10 年以上经验的资深研发工程师，目前是顶尖开源 OLAP 数据库
（[StarRocks](https://github.com/StarRocks/starrocks)）的核心开发者与 Committer。
我的日常技术栈围绕 C++、高并发、分布式系统、向量化执行以及底层性能压榨。
同时，我也在积极拥抱 AI 时代，探索 LLM、RAG 和前沿编程语言（如 Rust、Haskell）。

请参考 Apache Doris 的官方文档、官方博客、GitHub 提交历史
（apache/doris）、GitHub Issues、社区讨论（Slack、微信群技术文章），
以及 SelectDB（Doris 商业化公司）的技术博客进行综合分析：

**注意**：Doris 与 StarRocks 同源于百度 Palo，两者在架构上有大量相似之处，
分析时应重点聚焦**两者在技术路线上的分歧点**，而非重复描述共同的基础设计。

**分析维度要求如下：**

1. **重大 Feature 与场景支持**：总结近年来（重点聚焦 v2.0 → v2.1 → v3.0，
   2023–2025 年）最重要的功能特性：

  - **存储引擎演进**：Doris 的 Segment V2 存储格式——
     ColumnBlock 与 Page 的层次结构；
     各索引类型的存储布局（Ordinal Index / Short Key Index /
     Bitmap Index / Bloom Filter Index / ZoneMap Index）；
     Inverted Index（v2.0 引入，基于 CLucene）的实现架构
     与适用场景（全文检索 + 等值/范围加速）；
     NGram Bloom Filter 的设计；
     与 StarRocks 存储格式的具体差异（Page 大小、
     索引组织方式、Compression Codec 支持）；
  - **Compute-Storage Separation（存算分离，v2.1+）**：
     Doris 存算分离模式的架构——
     FE（Frontend）/ BE（Backend）/ MS（Meta Service）
     三层新架构；数据缓存（File Cache）的设计与一致性保证；
     与 StarRocks 存算分离（shared-data 模式）的架构对比
     （元数据管理方式、缓存粒度、冷热分离策略）；
  - **Auto Partition（自动分区，v2.1+）**：
     基于 RANGE/LIST 的自动分区创建机制；
     动态分区（Dynamic Partition）的演进；
     与 StarRocks 分区裁剪能力的对比；
  - **半结构化数据：Variant 类型（v2.1+）**：
     Doris Variant 列的存储实现——
     是否采用 Column Store 动态拆解（Sub-Column）
     还是 JSON 原始存储；
     与 StarRocks JSON 类型 / Databend VARIANT 的对比；
     Inverted Index 在 Variant 列上的下推能力；
  - **Doris 3.0 存算分离 GA**：v3.0 中存算分离从实验性到 GA
     的关键工程里程碑；Multi-Cluster（多计算集群共享存储）
     的隔离机制；冷热分层自动化策略；

2. **执行引擎深度**：

  - **向量化执行引擎（Apache Arrow 格式，v1.2+ 全面切换）**：
     Doris 向量化执行引擎基于 Block（列批）的实现；
     Pipeline Execution Engine（v2.0+，类似 StarRocks
     Pipeline 引擎）的设计——Task 调度、
     Driver 级并行、Back-pressure 机制；
     与 StarRocks Pipeline Engine 的具体实现差异
     （线程模型、Task 粒度、调度策略）；
  - **查询优化器：Nereids（v2.0 全面切换）**：
     Nereids 是 Doris 从头重写的 CBO 优化器——
     Cascades 框架实现；Memo 结构与 Rule 体系；
     统计信息收集（`ANALYZE TABLE`）的自动化；
     Join Reorder（动态规划 + 启发式）；
     与 StarRocks Optimizer 的能力对比
     （尤其是 TPC-DS 复杂查询场景）；
  - **Runtime Filter**：Doris Runtime Filter 的实现——
     跨 Fragment 的 Bloom Filter / Min-Max Filter 传递；
     与 StarRocks Runtime Filter 的下推深度对比；
     IN-list Filter 的使用边界；
  - **物化视图体系（v2.1 异步物化视图）**：
     同步物化视图（Rollup）与异步物化视图的设计差异；
     异步物化视图的自动刷新策略（Partition 级别增量刷新）；
     透明改写（Transparent Rewrite）的实现深度——
     是否支持多表 Join 物化视图的自动匹配；
     与 StarRocks 物化视图透明改写的对比；
  - **Join 优化**：Bucket Shuffle Join / Colocate Join /
     Broadcast Join / Shuffle Join 的选择策略；
     Runtime Adaptive Join 策略；

3. **湖仓一体（Lakehouse）能力**：

  - **Multi-Catalog（外部数据源，v1.2+）**：
     Hive / Iceberg / Hudi / Delta Lake / JDBC Catalog
     的接入深度；Iceberg 的 Position Delete 合并实现；
     Catalog 层的权限与 Credential 管理；
     与 StarRocks External Catalog 的实现对比
     （元数据缓存策略、统计信息同步、谓词下推深度）；
  - **数据导入体系**：Stream Load / Broker Load /
     Routine Load（Kafka）/ INSERT INTO SELECT 的
     性能边界与适用场景；
     Group Commit（聚合小批量写入，v2.1+）
     的实现机制与延迟收益；
     与 StarRocks 各导入方式的对比；

4. **Doris vs StarRocks 深度对比**（本 Prompt 的核心关注点）：

  - **分叉后的技术路线差异**：2021 年分叉后，两个项目在
     以下维度的分歧选择——
     向量化引擎的实现路径（Doris 更保守的 Arrow 格式 vs
     StarRocks 更激进的自研内存格式）；
     优化器重写策略（Doris Nereids 从头重写 vs
     StarRocks 渐进式演进）；
     存算分离的时间节点与实现路径；
     社区治理（Apache 基金会 vs 独立开源）；
  - **生产案例对比**：两者在国内互联网大厂的实际落地场景；
     典型性能对比测试（ClickBench / TPC-H / TPC-DS）的
     客观分析（区分 benchmark 条件的公平性问题）；
  - **生态差异**：SelectDB 商业化 vs StarRocks Inc 商业化；
     社区活跃度（GitHub Star / Contributor 数量趋势）；
     国际化程度（英文文档质量、海外用户占比）；

5. **商业化与社区治理**：

  - **SelectDB**：Doris 商业化公司的产品线
     （SelectDB Cloud / SelectDB Enterprise）；
     与 Apache Doris 基金会的关系；
     商业功能边界（哪些功能在 Enterprise 版才有）；
  - **Apache 治理的双刃剑**：Apache Way 对 Doris
     发版节奏的影响；IP 清理的历史遗留问题；
     核心贡献者集中度（百度系 + SelectDB 系）；

**参考资料：**
- https://doris.apache.org/docs/
- https://github.com/apache/doris/releases
- https://doris.apache.org/blog/
- https://www.selectdb.com/blog
- *Doris: A Modern Analytical Database System*（相关技术博客）

**输出格式要求：**
- 鉴于你是 StarRocks 核心开发者，分析时应提供
  **具体到代码层面的技术对比**（如两者 HashJoin 实现差异、
  物化视图透明改写的 Rule 覆盖度对比），
  避免停留在功能列表层面；
- 文章结构建议：
  **Executive Summary（重点：与 StarRocks 的技术路线分叉）
  → Segment V2 存储格式深度解析
  → Nereids CBO 优化器：从头重写的代价与收益
  → Pipeline 执行引擎：与 StarRocks 实现对比
  → 物化视图体系：透明改写能力边界
  → 存算分离架构：v3.0 GA 技术解析
  → Lakehouse 能力：Multi-Catalog 实现深度
  → Doris vs StarRocks：技术路线深度对比
  → 社区治理与 SelectDB 商业化
  → 总结与展望**；
