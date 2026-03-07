我是一名拥有 10 年以上经验的资深研发工程师，目前是顶尖开源 OLAP 数据库（StarRocks）的核心开发者与 Committer。我的日常技术栈围绕 C++、高并发、分布式系统、向量化执行以及底层性能压榨。同时，我也在积极拥抱 AI 时代，探索 LLM、RAG 和前沿编程语言（如 Rust、Haskell）。 

参考 Oracle的如下release notes, 同时结合历史资料（历史release node）、博客：
- 总结其最近这些年其database的重大feature/optimzation及新的场景支持;
- 总结其最近这些年在自动化(automatic)/执行引擎/存储引擎/优化器等方面的主要动向；
- 分析该产品的产品商业定位及市场卖点;
- 从技术、产品、商业话的视角，分析并洞察其产品在该年的定位及迭代方向的重点变化。

参考其release notes:
- https://docs.oracle.com/en-us/iaas/releasenotes/services/database/index.htm
- https://docs.oracle.com/en-us/iaas/releasenotes/services/autonomous-database-serverless/index.htm

按照博客的方式输出一篇介绍、思考的报告类文章：
输出时注意：
- 内容尽量详实，通过引用原release note中的commit/link来说明相关的功能feature；
- 语言流畅、减少空话，尽量言之有物，结合相关feature的blog或者PR文章进行补充相关的概念或者名词； 
- 在专业名词或者属于该产品的技术名词，请使用英文备注，并附上英文链接。


# Oracle Database 2024–2025：从"企业数据库"到"AI for Data"的战略重铸

> 一名 OLAP 数据库内核工程师的视角：解读 Oracle 在 AI 时代的技术路线、产品演进与商业野心

---

## 前言：一次比看上去更深刻的蜕变

对于数据库圈子里的人来说，Oracle 的每一次大版本发布都值得认真拆解。2024 年 5 月正式 GA 的 [Oracle Database 23ai](https://blogs.oracle.com/database/oracle-announces-oracle-ai-database-26ai)，是 Oracle 19c（2019 年发布）之后的下一个长期支持版本（Long-Term Support Release，LTS），Premier Support 承诺到 2031 年。从 19c 算起，Oracle 足足蓄力了五年，这次交出的答卷横跨 AI 向量搜索、数据模型统一、自动化引擎全面升级、以及 Serverless 架构深化——超过 300 项主要新特性。

2025 年 10 月，Oracle 在 AI World 大会上更进一步，直接宣布用 **Oracle AI Database 26ai** 取代 23ai，标志性地将"AI"写进数据库的品牌名称，并开始系统性地进攻 Lakehouse 分析市场。

这不仅仅是一次版本迭代，而是 Oracle 对"数据库未来是什么"这个问题给出的完整答案：**数据库不应该仅仅是 AI 应用的后端存储，而应该是 AI 推理、Agent 执行、和数据治理的统一平台**。

本文将沿着技术演进、产品定位、商业策略三条线展开，系统梳理 Oracle 在这两年最重要的迭代。

---

## 一、核心 Feature 全景：23ai 的 300+ 特性中什么最值得关注

### 1.1 AI Vector Search：数据库级向量引擎

[Oracle AI Vector Search](https://www.oracle.com/database/ai-vector-search/) 是 23ai 的头号招牌特性。它在数据库内核中直接引入了 `VECTOR` 数据类型，配套全新的向量索引（[IVF_FLAT（Inverted File Flat）](https://blogs.oracle.com/database/oracle-database-23ai-on-exadata)，以及 HNSW 索引），以及 `vector_distance()` SQL 算子，让向量相似性搜索与传统关系查询能够在同一条 SQL 语句中混合执行。

从工程实现角度看，最有意思的设计决策是：Oracle 在 23ai 中引入了专为 AI Vector Search 优化的 IVF 索引，AI Smart Scan 利用该索引大幅缩小搜索空间，并将 Top-K 计算从数据库服务器卸载到 Exadata 存储服务器，避免了将大量向量数据传输到数据库层再丢弃的开销。

这背后是一套被称为 **AI Smart Scan** 的向量计算卸载机制，完全复用了 Exadata 在分析场景中"计算下推到存储层"的经典架构。具体的加速路径是：

- AI Smart Scan 在 Exadata 存储服务器上执行 `vector_distance()` 计算，每台存储服务器维护本地的 Top-K 候选集；
- 各存储节点各自的 Top-K 结果汇聚到数据库服务器做最终合并，避免了全量向量数据的网络传输；
- Exadata System Software 24ai 的 AI Smart Scan 在内存速度下处理向量数据，利用 Exadata RDMA Memory（XRMEM）和 Smart Flash Cache，在存储层完成高度可扩展的向量距离计算和 Top-K 过滤，AI 工作负载相比之前可加速 30 倍。

对于做过 OLAP 执行引擎的工程师来说，这套设计在逻辑上等价于把 SIMD 向量化计算和过滤下推（filter pushdown）组合到存储层，只是针对的是浮点向量距离运算而非传统的列式谓词过滤。区别在于：向量 Top-K 是一个全局排序问题，分布式 Top-K 归并需要额外的精度保证机制（类似 merge-sort），而 Oracle 的实现通过让每个存储节点维护局部 Top-K，再在数据库服务器归并，有效地把这个问题拆解成可并行化的子问题。

2025 年 10 月，26ai 进一步引入了 **Unified Hybrid Vector Search**：可以在单一查询中将向量搜索与关系型、文本、JSON、知识图谱、空间谓词混合，同时检索文档、图像、音频、视频和结构化数据行。这是向量数据库领域少见的"多模态统一查询"能力，从实现上看需要在查询优化器层面将异构的评分函数（向量距离 + 全文相关性 + 关系条件）组合进统一的执行计划，难度不低。

### 1.2 JSON Relational Duality Views：ORM 终结者

[JSON Relational Duality Views](https://blogs.oracle.com/database/oracle-announces-general-availability-of-json-relational-duality-in-oracle-database-23ai)（以下简称 Duality Views）是 23ai 中被工程界讨论最广泛的特性之一。

其核心思想是：数据以标准化关系表的形式存储，但可以通过 JSON 文档的方式访问。Duality View 是一个完全可更新、支持事务的 JSON 视图，当应用程序更新或删除文档时，底层对应的关系表数据会自动更新。

这解决了软件开发中长期存在的"对象-关系阻抗不匹配"（Object-Relational Impedance Mismatch）问题：应用层习惯用层次化的 JSON 对象工作，而关系数据库以规范化表格存储——过去开发者要么用 ORM 框架（引入 N+1 查询、性能陷阱等问题），要么引入独立的 MongoDB 等文档数据库（带来数据一致性和同步问题）。

Duality View 用一种优雅的方式切断了这两难：数据库处理将 JSON 更新翻译成底层多表 DML 的复杂性，开发者无需编写处理多表更新的逻辑，所有操作在单个原子事务中完成。

从数据库内核视角看，Duality Views 本质上是一个可写视图（updatable view）的扩展版本，但需要解决 JSON 文档到关系表之间的双向 mapping 问题，包括嵌套对象的展开、数组的拆分/聚合、以及更新时的冲突检测。Oracle 用了类似 GraphQL Schema 的语法来定义 Duality View，声明式地描述 JSON 文档的形状与底层表的对应关系，让内核来负责双向转换。

### 1.3 True Cache：Active Data Guard 驱动的中间层缓存

[Oracle True Cache](https://blogs.oracle.com/database/post/introducing-oracle-true-cache) 是一个部署在应用层和数据库之间的只读缓存层，底层基于 Active Data Guard 技术保持与主库的强一致性同步。

与传统 Redis/Memcached 方案的本质区别在于：True Cache 不需要应用代码管理缓存填充（cache population）和失效（invalidation）——这是 Memcached 层最常见的 bug 来源之一。Oracle 的 Active Data Guard 技术保证 True Cache 中的数据始终与主库同步，同时 True Cache 支持完整的 Oracle SQL、JSON 和 Graph 查询能力。

对比缓存系统的设计传统：Redis 是一个独立的 KV 引擎，应用需要自己维护"什么数据在 Redis 里"；True Cache 则是一个能理解 Oracle 数据语义的透明缓存，支持完整 SQL。代价是：它只能和 Oracle 主库配套使用，不具备独立性。这是 Oracle "一体化"生态战略的缩影。

### 1.4 Lock-Free Reservations 与 Priority Transactions

**Lock-Free Reservations**（[文档](https://docs.oracle.com/en/database/oracle/oracle-database/23/adfns/lock-free-reservation.html)）针对的是高并发 OLTP 场景中的热点行更新问题——最典型的例子是库存扣减、账户余额更新。传统行锁机制下，大量并发事务争抢同一行会产生严重的锁竞争等待。Lock-Free Reservations 允许在不持有传统行锁的情况下预留一个数值范围（如预留库存数量），只有在事务提交时才做最终的合法性校验，类似于乐观锁 + 值域预留的结合体。

**Priority Transactions** 允许为不同的事务设置优先级，在资源竞争时高优先级事务优先获得资源。这是针对混合工作负载场景（如 OLTP 和批量分析共存）下 QoS 控制的精细化工具。

### 1.5 SQL Firewall：内核级 SQL 注入防御

[Oracle SQL Firewall](https://docs.oracle.com/en/database/oracle/oracle-database/23/dbseg/using-oracle-sql-firewall.html) 是直接内嵌在数据库内核中的 SQL 白名单机制。它通过学习模式记录合法的 SQL 访问模式，一旦检测到偏离白名单的 SQL（包括 SQL 注入的特征模式），可以选择阻断、记录或告警。

从安全架构角度看，内核级防御相比应用层或网络层的 WAF 有本质优势：无法被绕过（因为所有 SQL 必须经过内核解析），且能感知会话上下文、用户身份、连接来源等完整信息。

### 1.6 Globally Distributed Database with RAFT

Oracle 在 23ai 中推出了基于 Raft 共识协议的 [Globally Distributed Database](https://www.oracle.com/database/distributed-database/)（前身是 Oracle Sharding），将分布式数据库的一致性协议从传统的两阶段提交（2PC）转向 Raft，解决跨地域多副本场景下的自动领导选举和故障恢复问题，同时对应用层暴露单一数据库视图，屏蔽分布式复杂性。

---

## 二、执行引擎与存储引擎：自动化能力的系统性升级

这是相对低调但对 OLAP/OLTP 引擎工程师最有参考价值的部分。

### 2.1 Database In-Memory 的自动化体系（AIM）

[Database In-Memory（DBIM）](https://blogs.oracle.com/in-memory/dbim-new-features-23ai) 在 23ai 中的最大变化是自动化能力的全面强化：

**Automatic In-Memory Sizing**：In-Memory 列存可以作为自动共享内存管理（ASMM）的一部分被动态管理，ASMM 可以根据整体数据库工作负载需求自动扩大或缩小 IM 列存的内存分配。这解决了一个长期困扰 DBA 的问题：IM 列存的大小需要手动设置，而在工作负载动态变化时很难精确配置。

**AIM（Automatic In-Memory）增强**：23ai 的 AIM 可以自动创建 Join Groups、启用 In-Memory Optimized Arithmetic、向量优化和 Bloom Filter 优化，基于增强的工作负载分析算法。新的分析还通过考虑 DML 开销来改进 AIM 在混合工作负载环境中的工作负载度量。

**Hybrid Exadata Scans**：对于部分填充（partially populated）的 In-Memory 表，Hybrid Exadata Scans 可以同时执行 IM 列存扫描和 Exadata Smart Scan，解决了之前只要表未完全填充就无法利用 IM 列存的问题。

**In-Memory JSON 优化**：Exadata Smart Scan 现在可以自动检测 JSON 列，并在 Exadata Smart Flash Cache 中为其构建 Path/Value 索引作为 CELLMEMORY 的一部分，对 JSON 查询的性能有显著提升。

从执行引擎视角看，这套体系的设计哲学是"让自动化决策取代人工调优"——类似于 StarRocks 中的 Cost-Based Optimizer 自动选择执行计划，Oracle 的 AIM 在内存管理层面做了类似的自适应决策框架。区别在于 Oracle 的决策粒度更细（下探到 Join Group 和 Bloom Filter 的自动创建），且与 Exadata 存储层深度耦合。

### 2.2 Exadata System Software 24ai：存储层的向量化革命

[Exadata System Software 24ai](https://blogs.oracle.com/exadata/post/exadata24ai) 是 2024 年 Exadata 有史以来最重要的软件版本之一，与 Database 23ai 配合推出。

**Transparent Cross-Tier Scan**：23ai 优化器现在可以在 Cross-Tier Scan 中透明地利用来自数据库层和存储层的列式数据，通过利用 IM 扫描的特性——数据裁剪、字典编码、压缩和 SIMD 处理——加速串行和并行查询，性能提升可达 3 倍。

**Pipelining Redo Writes**：在 Exadata X10M 部署中，将 redo 写入从传统的"批量写"（batched redo write）改为流水线式写入，提升 OLTP 事务吞吐量。这是存储引擎 WAL（Write-Ahead Log）机制层面的优化，等价于减少 redo 写入的端到端延迟。

**Enlarged Bloom Filter Offload**：从 Exadata System Software 24ai 开始，支持将更大的 Bloom Filter 卸载到存储服务器，使分析查询性能提升最高 2 倍。对于 Hash Join 重度场景，更大的 Bloom Filter 意味着更多的 probe 端数据可以在存储层被过滤掉，减少数据传输到数据库服务器的量。

**Columnar Cache on XRMEM**：将列式缓存（Columnar Cache）从 Flash Cache 层扩展到 XRMEM（Exadata RDMA Memory），利用 RDMA 的超低延迟特性进一步加速频繁访问的列式数据。

这些优化的组合效果从公开的 benchmark 数据来看相当可观——但需要注意，这些加速数字大多是在 Exadata 特定硬件配置下测得的，在通用云实例上的表现会有显著差异。这也是 Oracle 生态系统的"护城河"：深度软硬件协同优化，但与特定硬件强绑定。

### 2.3 Automatic Indexing 的演进

Oracle 的 [Automatic Indexing](https://docs.oracle.com/en/database/oracle/oracle-database/19/admin/managing-indexes.html#GUID-1A1D7A60-9FC0-4889-B1B5-47B649CB2A41) 特性（首次引入于 19c）在 23ai 中持续演进，结合 AI Vector Search 的索引管理需求，扩展了对向量索引的自动建议和管理能力。Auto Indexing 的核心逻辑是：通过分析 SGA 中的执行计划和执行统计（类似于 OLAP 系统的 query log 分析），在后台自动创建、验证（在 shadow 模式下对比前后查询性能）、并在确认有效后公开新索引。这与 StarRocks 中基于 Query Profile 的物化视图推荐类似，但作用于二级索引而非预聚合层。

### 2.4 查询优化器的 AI 辅助

Oracle 在 23ai 中引入了 [AI-Assisted SQL Optimization](https://docs.oracle.com/en/database/oracle/oracle-database/23/tgsql/)，基于历史执行统计和机器学习模型改进 Cardinality Estimation（基数估计）的准确性。长期以来，Cardinality Estimation 是 CBO（Cost-Based Optimizer）中最难准确的部分——多表 Join 后的基数估计误差是查询计划选择错误的主要根源之一。Oracle 尝试通过采样历史执行数据训练内部模型来校正这个估计偏差，思路上类似 Bao（Balsa 和 Bao 等学术工作中的学习型 join order 优化）。

---

## 三、Autonomous Database Serverless 的演进：从托管到 AI Native

OCI 上的 [Autonomous Database Serverless](https://docs.oracle.com/en-us/iaas/releasenotes/services/autonomous-database-serverless/index.htm) 是 Oracle 数据库云服务中迭代最快的产品线，也是 Oracle 验证新能力的"先锋阵地"。

### 3.1 Select AI 体系的系统性构建

**Select AI** 是 Oracle 在 Autonomous Database 中构建的自然语言数据接口体系，从 2024 到 2025 年经历了从单点功能到完整框架的演进：

- **Select AI for NL2SQL**：允许用自然语言提问，数据库内核自动生成 SQL 并执行，直接在 SQL 查询中嵌入 `DBMS_CLOUD_AI.GENERATE` 调用；
- **[Select AI for Python](https://docs.oracle.com/en-us/iaas/releasenotes/autonomous-database-serverless/2025-09-selectai-for-python.htm)**（2025 年 9 月）：将 `DBMS_CLOUD_AI` 的 NL2SQL 能力暴露给 Python 应用，无需通过 SQL 接口；
- **[Select AI Conversations](https://docs.oracle.com/en-us/iaas/releasenotes/autonomous-database-serverless/2025-09-selectai-conversations.htm)**（2025 年 9 月）：支持多轮对话上下文管理，不同 topic 的对话不再混淆上下文；
- **[Select AI Summarize & Translate](https://docs.oracle.com/en-us/iaas/releasenotes/autonomous-database-serverless/2025-09-selectai-summarize.htm)**（2025 年 9 月）：允许直接在 SQL/PL/SQL 中调用 LLM 完成文本摘要和翻译；
- **[Select AI Feedback](https://docs.oracle.com/en-us/iaas/releasenotes/autonomous-database-serverless/2025-09-selectai-feedback.htm)**（2025 年 9 月）：用户可以对生成的 NL2SQL 结果打分反馈，用于改进查询生成准确率；
- **[Select AI extends to more AI providers](https://docs.oracle.com/en-us/iaas/releasenotes/autonomous-database-serverless/2025-07-select-ai-extends-support-to-ai-providers.htm)**（2025 年 7 月）：增加对更多 LLM 提供商的支持，包括 Cohere、Mistral 等。

### 3.2 Select AI Agent：AI Agent 入库

2025 年 10 月，随 26ai 一同发布的 [Select AI Agent](https://docs.oracle.com/en-us/iaas/releasenotes/autonomous-database-serverless/2025-10-selectai-agent.htm) 是迄今为止最具野心的功能：Select AI Agent 支持在数据库内构建、部署和管理 AI Agent，支持自定义和预构建的数据库内工具、通过 REST 调用的外部工具以及 MCP Server，实现多步骤 Agentic 工作流的自动化。

配套的 **AI Private Agent Factory** 提供了无代码 Agent 构建平台，以容器形式在客户自己选择的环境中运行，使客户能在不向第三方 AI 框架共享数据的情况下享受 Oracle AI Database 的全部性能、安全和可扩展性。

2025 年 12 月，Autonomous AI Database 推出了内置的 [MCP Server](https://docs.oracle.com/en-us/iaas/releasenotes/autonomous-database-serverless/2025-12-mcp-server-for-autonomous-ai-database.htm)，为每个数据库实例提供一个托管的 MCP（Model Context Protocol）服务端，使外部 LLM 和 AI Agent 框架能够通过标准化接口安全访问数据库资源。

Oracle 的 Agent 战略与 Databricks 的 Mosaic AI Agent Framework 形成了有趣的对比：Databricks 把 Agent 框架放在数据平台层（Spark 上面），而 Oracle 把 Agent 执行逻辑直接嵌入数据库内核——用 PL/SQL 或 Python 存储过程定义 Agent 的工具和任务，在数据库事务的保护下执行多步推理。技术理由是合理的：通过把 Agent 逻辑与数据共置，可以消除网络延迟并获得数据库粒度的安全策略；让数百万现有 PL/SQL 开发者能够构建 AI Agent，是激活 Oracle 现有生态的聪明策略。

### 3.3 Autonomous AI Lakehouse：正面迎击 Databricks

2025 年 10 月，随 26ai 同步发布的 [Autonomous AI Lakehouse](https://www.oracle.com/database/autonomous-database/autonomous-data-warehouse/) 是 Oracle 进入 Lakehouse 赛道的最直接宣言：Autonomous AI Lakehouse 支持读写对象存储中的 Apache Iceberg 数据格式，同时在 OCI、AWS、Azure 和 Google Cloud 上均可使用，并与 Databricks、Snowflake 等其他 Iceberg 合规数据存储互操作，实现无需移动数据的无缝数据共享。

这是 Oracle 第一次以开放格式作为核心卖点，向传统 Lakehouse 玩家（Databricks、Snowflake、AWS Glue/Athena）正面竞争。其差异化优势是：Exadata 驱动的性能和按使用量付费的 Serverless 弹性伸缩，以及在同一 Iceberg 数据上叠加 Oracle Database 完整的 AI 和分析 SQL 能力。

配套的 [Iceberg REST Catalog Integration](https://docs.oracle.com/en-us/iaas/releasenotes/autonomous-database-serverless/2025-10-broader-and-enhanced-iceberg-rest-catalog-support.htm)（2025 年 10 月）支持 Databricks Unity Catalog 和 Snowflake Polaris 作为 Iceberg catalog，客户的 Oracle 数据库可以直接读写这些 catalog 中的 Iceberg 表，实现跨平台数据共享而无需 ETL。

同月，Autonomous AI Database 支持以 [DynamoDB API 兼容方式](https://docs.oracle.com/en-us/iaas/releasenotes/autonomous-database-serverless/2025-12-autonomous-ai-database-api-for-dynamodb.htm)访问，允许 DynamoDB 用户用现有工具和 SDK 直接接入 Oracle，降低迁移门槛。这是 Oracle 一贯的"协议兼容"迁移策略的延伸，之前已经有 MongoDB API 兼容。

### 3.4 Cloud Tables 与 External Table Cache：存储弹性的延伸

**[Cloud Tables](https://docs.oracle.com/en-us/iaas/releasenotes/autonomous-database-serverless/2025-09-use-cloud-tables-to-store-logging-and-diagnostic-info.htm)**（2025 年 9 月）允许创建数据存储在 Oracle 托管云存储上的表，数据不消耗数据库本地存储配额。对于日志、诊断信息等冷数据场景，Cloud Tables 提供了一种透明的冷热分离机制，类似于 Snowflake 的 External Table + 自动 staging 的结合体。

**[External Table Cache](https://docs.oracle.com/en-us/iaas/releasenotes/autonomous-database-serverless/2025-10-automatic-caching-for-external-tables.htm)**（2025 年 10 月）为频繁访问的外部表（如 Object Storage 上的 Parquet/ORC 文件）提供自动缓存，避免每次查询都重复从对象存储拉取数据。这与 StarRocks 的 data cache（external table 的本地 block cache）功能类似，但 Oracle 的版本集成在自动化框架中，无需手动配置缓存策略。

### 3.5 Live Workload Capture-Replay：生产级迁移验证

[Live Workload Capture-Replay](https://docs.oracle.com/en-us/iaas/releasenotes/autonomous-database-serverless/2025-10-live-workload-capture-replay-between-adb.htm)（2025 年 10 月）是一个生产迁移/升级场景的神器：在源数据库上捕获实时工作负载的同时，同步在目标数据库（如一个 refreshable clone）上回放，两者并行运行，允许比较性能差异和结果一致性。这对于从 19c 升级到 26ai 这种大版本跨越有极大的风险控制价值——可以在不影响生产的前提下提前验证新版本的兼容性和性能。

---

## 四、Oracle@Cloud 与多云战略：Database 作为跨云基础设施

### 4.1 Oracle Database@Azure / GCP / AWS

从 2023 年底开始，Oracle 加速推进多云数据库服务策略。[Oracle Database@Azure](https://www.oracle.com/cloud/azure/oracle-database-at-azure/) 于 2023 年 12 月 GA，使 Azure 用户可以在 Azure 数据中心内运行 Oracle Exadata 硬件，享受与 OCI 相同的 Oracle Database 服务，同时与 Azure 的网络、安全、身份服务深度集成，Azure 用户可以用 Azure 的云消费额度购买。

2025 年，Oracle AI Database 26ai 已经在全球四大超大规模云（OCI、Amazon Web Services、Microsoft Azure 和 Google Cloud）上全部可用。

这是一个意义深远的战略转变：Oracle 不再试图让客户"搬到 OCI"，而是把自己的数据库服务"搬进"客户已经在用的云环境。从商业模式上看，Oracle 把硬件（Exadata）变成了跨云的"database infrastructure"层，收取数据库服务费用，而底层算力费用由各大云厂商收取。

### 4.2 GoldenGate 26ai：实时数据流的 AI 化

[Oracle GoldenGate 26ai](https://blogs.oracle.com/dataintegration/oracle-goldengate-26ai-aipowered-realtime-data-replication-unveiled-at-oracle-ai-world-2025) 同样于 2025 年 10 月发布，将 AI 能力嵌入实时数据复制管道：新的 AI 微服务允许在数据移动过程中进行实时分析和转换，可以在流数据上执行实时分析，并自动检测和同步 schema 变更。

Auto-Schema 功能智能地检测跨异构数据库的 schema 变化并自动同步，减少了手工干预和停机时间——这在从 Oracle 迁移到 Autonomous AI Lakehouse 的场景中尤为有用。

---

## 五、自动化战略：Oracle 的"Autonomous"体系

Oracle 的"Autonomous"品牌涵盖了一个完整的自动化能力体系，跨越存储、内存、优化器、运维管理多个层面：

| 能力层 | 自动化特性 | 对应技术 |
|--------|-----------|---------|
| 内存管理 | Automatic In-Memory Sizing | ASMM + AIM 联动 |
| 索引管理 | Automatic Indexing | SQL Workload 分析 + Shadow 验证 |
| 统计信息 | Automatic Statistics Gathering | AWR + 采样分析 |
| 诊断优化 | Automatic Database Diagnostic Monitor（ADDM） | AWR 快照分析 |
| 备份恢复 | Autonomous Recovery Service（ARS） | 策略驱动自动备份 |
| 补丁更新 | AutoPatch / Auto-Upgrade | Zero-Downtime Patching |
| 资源管理 | Database Resource Manager（自动计划） | cs_resource_manager |

2025 年 12 月，Autonomous AI Database 开放了 [Database Resource Manager](https://docs.oracle.com/en-us/iaas/releasenotes/autonomous-database-serverless/2025-12-manage-workload-resources-using-db-resource-manager.htm) 的自定义配置能力（`cs_resource_manager` PL/SQL 包），允许用户为不同工作负载定义资源计划，在多租户/多工作负载场景下实现精细的 CPU、I/O 资源隔离。

---

## 六、商业定位与市场卖点

### 6.1 核心叙事：AI for Data，而非 Data for AI

Oracle 的产品叙事与 Databricks、Snowflake 形成了鲜明反差。后两者的思路是"建立一个数据平台，然后在上面加 AI"；Oracle 的答案是：把 AI 架构进整个数据和开发栈的核心，让 AI 在数据所在的地方运行——数据库——而不是把数据移到 AI 所在的地方。

这个叙事有其技术合理性：对于金融、电信、医疗等行业的关键任务系统，把生产数据库中的 TB 级业务数据搬到外部 AI 平台处理，在安全合规和延迟两个维度都是巨大负担。在数据库内做 AI 推理（in-database inference）是更现实的路径。

### 6.2 差异化竞争优势

**对传统企业客户（CTO/DBA）**：
- 26ai 升级无需数据库升级或应用重认证，只需应用 2025 年 10 月 Release Update（版本号 23.26.0）——这是 Oracle 数据库历史上最平滑的大版本切换，消除了传统"大版本升级"的风险；
- AI Vector Search 等 AI 特性不收取额外费用，降低了试用门槛；
- 99.995% 的 Autonomous Database SLA，加上自动故障恢复和 Zero Downtime Patching；

**对 AI/ML 工程师**：
- 向量、关系、JSON、图、空间数据在同一事务引擎下处理，Agent 开发无需跨系统整合；
- ONNX 模型可直接导入数据库执行推理，或集成 NVIDIA NIM 容器；
- MCP Server 内置于数据库实例，标准化 AI Agent 接入；

**对金融/医疗等强合规行业**：
- SQL Firewall 内核级 SQL 注入防御；
- TDE（Transparent Data Encryption）+ 客户管理密钥（CMK）+ 跨 tenancy 密钥管理；
- 数据主权（Data Residency）场景下的 Exadata Cloud@Customer（在客户自己的数据中心运行 Oracle 云服务）；

### 6.3 与竞争对手的横向对比

**vs. Databricks**：Databricks 通过 Spark 生态建立了大数据处理的护城河，正在向 OLTP（Lakebase）和 AI Agent（Agent Bricks）扩张；Oracle 反向切入——从 OLTP/OLAP 的核心地盘出发，向 Lakehouse（Autonomous AI Lakehouse + Iceberg）和 AI Agent 扩张。两者的交叠区域将越来越大，但客户群体目前仍有显著分化：Oracle 牢牢抓住的是银行、电信、政府等传统企业；Databricks 的优势在数据工程师密集的互联网和数据密集型企业。

**vs. Snowflake**：Snowflake 同样在拥抱 Iceberg、做 AI 功能（Cortex），但缺乏 Oracle 级别的事务处理能力和 Exadata 硬件加速。Oracle 的 "Exadata + Autonomous Serverless" 组合提供了 Snowflake 难以直接复制的性能优势，但 Snowflake 的易用性和多云原生体验仍然领先。

**vs. PostgreSQL 生态**：AWS Aurora PostgreSQL、Azure PostgreSQL Flexible Server、以及 Neon（已被 Databricks 收购）代表了 PostgreSQL 的云化路线。Oracle 通过提供 DynamoDB API 兼容、MongoDB API 兼容等方式主动降低门槛，但与 PostgreSQL 生态的生态开放性差距仍是其最大的软肋。

---

## 七、从内核工程师视角看 Oracle 技术路线的洞察

作为一个在 StarRocks 做 OLAP 执行引擎的工程师，以下几个技术设计决策值得深度思考：

**向量 Top-K 的分布式计算**：Oracle AI Smart Scan 在存储层做局部 Top-K，再在数据库服务器归并，本质上是 distributed Top-K 的经典分治方案。挑战在于：ANN 索引（如 IVF 或 HNSW）的 Top-K 结果在分区之间并不独立——每个分区的局部 Top-K 并不保证能覆盖全局 Top-K。Oracle 通过 IVF 的倒排索引结构（先聚类，再在最相近的几个聚类中心对应的分区里做精确搜索）来控制召回率，但这和 StarRocks 未来可能面临的分布式向量索引设计问题高度相关。

**In-Database Agent 的工程复杂度**：Select AI Agent 在数据库内执行多步推理意味着：每一步 LLM 调用都是一个同步的外部 HTTP 请求，而数据库事务引擎通常不擅长长时运行的网络 I/O。Oracle 大概率通过异步 job 框架（类似 DBMS_SCHEDULER）来包装 Agent 的执行，而非在事务上下文中同步等待 LLM 响应——否则锁持有时间会无限延长。这种设计在事务语义上的权衡值得深思。

**Lock-Free Reservations 的精确性保证**：这个特性在高频交易（HFT）场景下的正确性边界需要仔细审查。乐观值域预留 + 事务提交时校验的模式，在极端并发下可能出现"预留成功但最终回滚率极高"的问题（类似 CAS 失败率在高竞争下的指数级恶化）。Oracle 的实现细节值得深入研究。

---

## 八、结语：Oracle 的 AI 时代策略是一次"纵深防御"

Oracle 在 AI 时代的策略，本质上是把数十年积累的企业数据库护城河（ACID 事务、Exadata 硬件加速、数据安全合规体系），与 AI 时代的新需求（向量搜索、Agent 执行、自然语言查询、开放 Lakehouse 格式）强行缝合在一起。

这是一次"纵深防御"：不是和 Databricks/Snowflake 在它们的擅长领域正面竞争，而是把 AI 能力嵌入到客户已经无法轻易离开的存量系统中，让 AI 升级的"最小阻力路径"就是在 Oracle 数据库内部完成。

从 23ai 的"数据库内置 AI 工具"到 26ai 的"Agent first-class citizen in the database"，Oracle 的迭代节奏出奇地快——这在历史上以"稳重缓慢"著称的 Oracle 数据库产品线中并不常见。这种加速背后，既有 AI 时代窗口期的紧迫感，也有来自 Databricks、Snowflake 等新势力对传统分析市场的真实蚕食压力。

对于做开源 OLAP 数据库的工程师来说，Oracle 这次的技术布局有清晰的参考价值：**向量搜索与 OLAP 查询引擎的深度融合、存储层计算下推的新形态（针对向量距离的 SIMD 并行化）、以及 Agent 工作流对数据库引擎提出的新要求（长事务、外部 I/O 异步化、状态持久化）**，这些都是接下来两到三年值得认真对待的工程命题。

---

*参考链接：[Databricks Base Database Release Notes](https://docs.oracle.com/en-us/iaas/releasenotes/services/database/index.htm) | [Autonomous Database Serverless Release Notes](https://docs.oracle.com/en-us/iaas/releasenotes/services/autonomous-database-serverless/index.htm) | [Oracle AI Database 26ai 官方博客](https://blogs.oracle.com/database/oracle-announces-oracle-ai-database-26ai) | [Exadata AI Smart Scan Deep Dive](https://blogs.oracle.com/exadata/exadata-ai-smart-scan-deep-dive) | [Database In-Memory 23ai 新特性](https://blogs.oracle.com/in-memory/dbim-new-features-23ai) | [JSON Relational Duality GA 博客](https://blogs.oracle.com/database/oracle-announces-general-availability-of-json-relational-duality-in-oracle-database-23ai) | [Exadata System Software 24ai](https://blogs.oracle.com/exadata/post/exadata24ai) | [Oracle AI World 2025 Futurum 分析](https://futurumgroup.com/insights/oracle-ai-world-2025-is-the-database-the-center-of-the-ai-universe-again/)*
