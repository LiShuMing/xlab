我是一名拥有 10 年以上经验的资深研发工程师，目前是顶尖开源 OLAP 数据库（StarRocks）的核心开发者与 Committer。我的日常技术栈围绕 C++、高并发、分布式系统、向量化执行以及底层性能压榨。同时，我也在积极拥抱 AI 时代，探索 LLM、RAG 和前沿编程语言（如 Rust、Haskell）。

参考 Iceberg的如下release notes, 同时结合历史资料（历史release node）、博客：
- 总结其最近这些年其的重大feature/optimzation及新的场景支持;
- 总结其最近这些年在执行/存储/自动化/性能优化等方面的主要动向；
- 从技术、产品、商业话的视角，分析并洞察其产品在该年的定位及迭代方向的重点变化。

参考其release notes:
- https://docs.pingcap.com/releases/tidb-self-managed/

按照博客的方式输出一篇介绍、思考的报告类文章：
输出时注意：
- 内容尽量详实，通过引用原release note中的commit/link来说明相关的功能feature；
- 语言流畅、减少空话，尽量言之有物，结合相关feature的blog或者PR文章进行补充相关的概念或者名词；
- 在专业名词或者属于该产品的技术名词，请使用英文备注，并附上英文链接。


这个 prompt 存在几个问题需要修正和丰富：主题不一致（说 Iceberg 但链接是 TiDB），以及可以增加更多上下文让输出质量更高。帮你优化如下：

---

**优化后的 Prompt（TiDB 版本）：**

我是一名拥有 10 年以上经验的资深研发工程师，目前是顶尖开源 OLAP 数据库（[StarRocks](https://github.com/StarRocks/starrocks)）的核心开发者与 Committer。我的日常技术栈围绕 C++、高并发、分布式系统、向量化执行以及底层性能压榨。同时，我也在积极拥抱 AI 时代，探索 LLM、RAG 和前沿编程语言（如 Rust、Haskell）。

请参考 TiDB 的官方 Release Notes，同时结合历史版本记录、官方博客、技术文章及社区讨论：

**分析维度要求如下：**

1. **重大 Feature 与场景支持**：总结近年来（重点聚焦最近 2–3 个大版本）最重要的功能特性与新场景支持，优先关注对 HTAP、分布式事务、存储引擎、SQL 兼容性等方向有实质影响的变化；

2. **执行引擎 / 存储引擎 / 性能优化动向**：重点梳理 TiKV、TiFlash、MPP 执行引擎、Optimizer（优化器）在向量化执行、下推优化、统计信息、自适应查询执行（AQE）等方面的演进；结合 TiDB 的 HTAP 架构特点，分析其在 TP 与 AP 融合上的技术取舍；

3. **自动化与运维智能化**：关注 TiDB 在自动化运维（如 Auto Analyze、Auto Scaling、TiDB Operator）、可观测性（如 Clinic、Performance Overview）、以及资源管控（Resource Control）方面的进展；

4. **技术、产品与商业化视角的综合洞察**：
  - **技术视角**：与同类系统（如 CockroachDB、YugabyteDB、StarRocks、ClickHouse）做横向对比，指出 TiDB 在技术路线上的独特选择与权衡；
  - **产品视角**：分析各版本迭代的重心转移（如从"功能完整性"到"性能与稳定性"、再到"HTAP 场景化落地"）；
  - **商业化视角**：结合 PingCAP 的 TiDB Cloud 产品动向，分析其 Serverless、多云策略与开源社区的协同关系。

**参考资料：**
- Release Notes 主页：https://docs.pingcap.com/releases/tidb-self-managed/
- TiDB 博客：https://www.pingcap.com/blog/
- GitHub 主仓库：https://github.com/pingcap/tidb

**输出格式要求：**
- 以**博客深度分析文章**的形式输出，面向有分布式系统与数据库内核背景的工程师读者，语言要有技术深度、不讲废话；
- 内容尽量详实，**通过直接引用原 Release Notes 中具体的条目或 GitHub PR/Issue 链接**来支撑论点，避免泛泛而谈；
- 结合相关官方博客或社区文章，对重要特性补充背景概念和技术原理；
- **专业名词及产品专属技术术语使用英文标注**，并尽可能附上英文参考链接（文档、博客或 PR）；
- 全文结构建议：引言 → 执行/存储引擎演进 → 自动化与运维 → HTAP 场景深化 → 商业化与生态 → 总结与洞察，各章节言之有物，避免罗列式堆砌。


# TiDB 7.x → 8.x：一个 HTAP 系统走向成熟的完整路径

> 以 StarRocks 内核工程师的视角，深度解析 TiDB 三年来在执行引擎、存储架构、资源管控与商业化上的技术演进

---

## 引言：从"可用"到"生产可靠"，再到"AI 就绪"

如果以 LTS（Long-Term Support）版本为里程碑来划分 TiDB 的演进阶段，近三年大致可以分为三个相互衔接的主题：

- **TiDB 7.1 LTS（2023.05）**：HTAP 架构的"能力拼图"基本完成——TiFlash MPP、Resource Control、Disaggregated Architecture 初具规模，但很多特性仍是 experimental；
- **TiDB 7.5 LTS（2023.12）**：稳定性、可观测性、MySQL 兼容性补齐，从"功能完整"走向"生产可靠"；
- **TiDB 8.1 LTS（2024.05）**与 **8.5 LTS（2024.12）**：执行引擎和存储引擎的底层架构被系统性重写或增强，同时 Vector Search 的引入标志着 TiDB 开始向"AI-ready 数据库"方向发力。

这三年间 PingCAP 的工程投入重心有一条清晰的主线：**从"搭积木"到"夯地基"，再到"开新疆"**。本文试图从执行引擎/存储引擎演进、自动化与运维、HTAP 场景深化、以及商业化生态四个维度，系统还原这条主线。

---

## 一、执行引擎演进：TiFlash 的向量化深化与 MPP 架构成熟

### 1.1 Pipeline 执行引擎：TiFlash 的核心重构

TiFlash 在 v7.2.0 引入了 Pipeline 执行引擎（[#6569](https://github.com/pingcap/tiflash/issues/6569)），并在 v8.x 系列持续演进，这是近三年 TiFlash 最重要的底层重构。

传统的 Volcano-style pull 模型在多核并发下存在固有的 thread-per-query 开销和调度抖动问题——每个算子（Scan、Join、Agg）阻塞式等待上游数据，导致线程频繁空转。Pipeline 执行引擎的核心思想是将查询执行分解为 Pipeline Breaks（通常是需要物化中间结果的算子边界，如 Build 端的 HashJoin），每个 pipeline segment 内部采用 push-based 的事件驱动模型，线程不再因等待数据而阻塞，而是向任务队列提交工作单元（Task），由固定大小的线程池调度执行。

这与 Velox、DuckDB 的 Morsel-driven parallelism 思路高度类似，区别在于 TiFlash 的 pipeline 是在分布式 MPP 框架内执行的，需要额外处理 Exchange 算子（Shuffle 和 Broadcast）与 pipeline 的交互边界。

在 v8.4.0 中，Pipeline 执行模型的 task 等待机制得到增强（[#8869](https://github.com/pingcap/tiflash/issues/8869) @SeaRise），同时 JOIN 算子的取消机制被改进，能够及时响应 cancel 请求（[#9430](https://github.com/pingcap/tiflash/issues/9430) @windtalker）。这两处修改的背后是同一个工程问题：在 pipeline 模型下，中止执行需要协调所有 stage 的 task 状态，比 pull 模型下简单的异常抛出要复杂得多。

### 1.2 HashAgg 高 NDV 优化：TiFlash 的聚合瓶颈被正视

v8.3.0 中 TiFlash 引入了多种 HashAgg 聚合计算模式（[#9196](https://github.com/pingcap/tiflash/issues/9196) @guo-shaoge），通过系统变量 `tiflash_hashagg_preaggregation_mode` 控制，专门针对高 NDV（Number of Distinct Values）数据的聚合性能问题。

这个问题在 OLAP 场景中很常见：当 GROUP BY 列的基数很高时（如 user_id、order_id），第一阶段预聚合（pre-aggregation）的过滤效果极差，大量的中间数据需要在节点间 shuffle，导致网络和内存压力双双飙升。TiFlash 之前的策略是固定的两阶段 HashAgg，无法根据数据特征动态选择聚合策略。

新引入的多模式设计允许在预聚合效果差时提前终止，直接进入 Final Agg 阶段，避免无效的预聚合开销。这与 StarRocks 的 Adaptive Pre-Aggregation 思路相近，但 StarRocks 是在优化器层面基于统计信息做自适应选择，而 TiFlash 的实现目前仍需要通过系统变量手动配置——这是一个工程上尚待完善的地方。

### 1.3 Runtime Filter：HashJoin 的过滤前移

[Runtime Filter](https://docs.pingcap.com/tidb/stable/runtime-filter/) 在 v7.3.0 引入（实验性），v7.5.0 正式 GA，是 TiFlash MPP 执行框架中一个重要的 Join 优化技术。

基本思路是：在 HashJoin 的 Build 阶段构建完 Hash Table 后，提取 join key 的值域集合（当前只支持 IN 类型谓词），以 Bloom Filter 或精确值集合的形式发送给 Probe 端，Probe 端在扫描时提前过滤不可能匹配的行，减少参与 Join 的数据量。这在星型模型（Star Schema）的维表 Join 场景中尤其有效——维表上的过滤条件（如 `date_dim.d_date = '2002-2-01'`）可以通过 Runtime Filter 传递到事实表（`catalog_sales`）的扫描阶段，大幅减少从存储层读取的数据量。

从实现上看，TiFlash 当前的 Runtime Filter 只支持 LOCAL 模式（同节点内过滤），`tidb_runtime_filter_mode = LOCAL`，不支持跨节点的 GLOBAL 模式（即把 Build 端的过滤信息广播到所有 Scan 节点）。GLOBAL 模式的实现需要在 MPP 的 Exchange 层引入额外的 barrier 同步，工程复杂度更高。StarRocks 在这方面支持 GLOBAL Bloom Filter 已经相当成熟，是 TiFlash 当前的一个明显差距。

### 1.4 Disaggregated TiFlash + S3：存储计算分离的正式成熟

[TiFlash Disaggregated Storage and Compute Architecture](https://docs.pingcap.com/tidb/stable/tiflash-disaggregated-and-s3/)（分离式架构）于 v7.0.0 作为实验特性引入，**v7.4.0 正式 GA**（[#6882](https://github.com/pingcap/tiflash/issues/6882) @JaySon-Huang et al.）。

架构上将 TiFlash 节点分为两类：
- **Write Node**：接收来自 TiKV 的 Raft Log，将行存数据转换为列存格式，定期打包上传到 S3；维护一个 local buffer（约 200 GB SSD）作为上传前的临时缓存；
- **Compute Node**：无状态，秒级扩缩容；从 Write Node 获取最新数据快照，从 S3 读取历史数据，使用本地 NVMe SSD 作为 Data Cache 加速重复读取。

这套架构的核心价值在于：Compute Node 完全无状态，scale-out 不需要数据重分布，也不需要等待副本同步——这是它与传统 TiFlash coupled 架构最根本的差异。对于 TiDB Cloud Serverless 场景，这种架构能做到在查询量为零时停掉所有 Compute Node（zero-cost 空闲），这是 cloud native 分析数据库的标配。

从工程上看，Disaggregated TiFlash 的一个关键挑战是 Write Node 和 Compute Node 之间的一致性读——Compute Node 需要知道哪些数据已经上传到 S3（稳定数据），哪些数据还在 Write Node 的本地 buffer 里（Delta 数据）。TiFlash 通过 Write Node 维护 snapshot 元数据，Compute Node 在查询时向 Write Node 发送 RPC 获取 snapshot 信息，再分别从 S3 和 Write Node 读取对应的数据块并在内存中合并——这本质上是一个分布式快照读的协议，设计上类似 Delta Lake / Iceberg 的 table snapshot，但粒度细化到了 Region 级别。

### 1.5 TiKV MVCC In-Memory Engine (IME)：慢查询的新解法

**v8.5.0** 引入的 [TiKV MVCC In-Memory Engine](https://docs.pingcap.com/tidb/stable/tikv-in-memory-engine/)（[#16141](https://github.com/tikv/tikv/issues/16141) @SpadeA-Tang @glorv @overvenus）是 TiKV 存储层少见的面向读放大问题的专项优化。

**背景**：TiKV 基于 RocksDB 实现 MVCC，每次更新不覆盖旧值，而是追加新版本（带 commit_ts 作为 key 后缀）。当一行数据被频繁更新（如订单状态、游戏积分排行榜）或 `tidb_gc_life_time` 设置较长（如保留 24 小时历史版本用于 PITR），RocksDB 中同一 key 会堆积大量历史版本。Coprocessor 在扫描时必须遍历所有版本才能找到最新值，导致 `total_keys` 远大于 `processed_keys`（即 MVCC Amplification），CPU 和延迟双双恶化。

IME 的解法：在 TiKV 内存中维护一个独立的 in-memory 缓存层，缓存最新版本的 MVCC 数据，并实现独立的 MVCC GC 机制——比 TiDB 层的 GC 更激进地在内存中清理历史版本。这样，Coprocessor 在扫描热数据时可以绕过 RocksDB，直接从内存缓存中读取最新版本，MVCC Amplification 从根源上消除。

IME 采用的自适应策略值得关注：通过统计 RocksDB Iterator `next` 和 `prev` 的调用次数来识别 MVCC Amplification 严重的 Region，自动选择 Top-N 个 Region 加载到内存，并在内存压力超过 90% 时按读访问频率 LRU 淘汰。这避免了把所有热数据都加载到内存的内存压力，同时又能精准命中 MVCC Amplification 最严重的 hotspot。

从 StarRocks 的视角看，StarRocks 基于列存（没有行存 MVCC 的问题），这个问题不存在。但类似的"版本堆积 → scan 放大"问题在 Primary Key 表的 Compaction 场景中有对应——StarRocks 依赖 Compaction 来合并旧版本，这是写时合并（write-time merge）策略，而 TiKV IME 是读时绕过（read-time bypass）策略，两者是针对同一问题的不同工程取舍。

---

## 二、优化器演进：统计信息、全局索引与 TSO 并行化

### 2.1 Global Index on Partitioned Tables：分区表的长期痛点被修复

[Global Index](https://docs.pingcap.com/tidb/stable/global-indexes/)（全局索引）是 TiDB 分区表长期以来的历史债务。在 v8.3.0 之前，分区表上的唯一键必须包含分区列——这与 Oracle、MySQL 的行为不兼容，在从这些数据库迁移数据时需要修改表 Schema，成本极高。

演进路径：
- **v7.6.0**：引入 `tidb_enable_global_index` 系统变量，实验特性；
- **v8.3.0**：`GLOBAL` 关键字支持显式创建全局索引，实验特性（[Release Notes](https://docs.pingcap.com/tidb/stable/release-8.3.0/)）；
- **v8.4.0**：Global Index 正式 **GA**，`tidb_enable_global_index` 废弃，全局索引默认开启（[Release Notes](https://docs.pingcap.com/tidb/stable/release-8.4.0/)）；
- **v8.5.4**：支持在非唯一列上创建 Global Index（[#58650](https://github.com/pingcap/tidb/issues/58650) @Defined2014 @mjonss）。

从技术实现看，Global Index 的 key 编码不带 `PartitionID` 前缀（本地索引的 key 格式是 `PartitionID_indexID_ColumnValues`），而是直接 `indexID_ColumnValues`，存储在独立的 Region 中。这使得不带分区键的 point query 和 range query 只需访问单个全局索引 Region，而不是扫描所有分区的本地索引——RPC 请求数从 N（分区数）降至 1，性能收益显著。

代价是：`TRUNCATE PARTITION`、`DROP PARTITION`、`REORGANIZE PARTITION` 等 DDL 操作需要同时更新全局索引，引入了额外的写放大。这是局部与全局索引之间永恒的工程权衡。

### 2.2 Active PD Follower：PD 的扩展性瓶颈被系统性解决

[Active PD Follower](https://docs.pingcap.com/tidb/stable/tune-region-performance/)（[#7431](https://github.com/tikv/pd/issues/7431) @okJiang）在 v7.6.0 作为实验特性引入，**v8.5.0 正式 GA**。

**背景**：PD Leader 是 TiDB 集群中的单点协调者，负责 TSO 分发、Region 心跳处理、调度决策。在大集群（数万 Region、大量 TiDB 节点）下，TiDB 节点频繁向 PD Leader 请求 Region 元数据（路由信息），导致 PD Leader CPU 过载，进而影响 TSO 分发延迟，拖累整个集群的事务吞吐。

Active PD Follower 的解法：让 PD Follower 也能处理 Region 信息查询请求（`pd_enable_follower_handle_region = ON`），将读请求均匀分散到所有 PD 节点，PD Leader 只负责 TSO 分发和调度写入。这类似于 etcd 中的 Learner + ReadIndex 机制，但 PD 是基于 etcd 构建的，所以这里实际上是在 etcd 的 Follower 上实现了一套独立的 Region 缓存层，通过 Follower 的本地状态机响应读请求，避免了所有请求打到 Leader 的瓶颈。

### 2.3 TSO Parallel Fetch：事务延迟优化

**v8.5.0** 引入了 `tidb_tso_client_rpc_mode` 系统变量，支持 `PARALLEL` 和 `PARALLEL-FAST` 两种 TSO 并行获取模式（[Release Notes](https://docs.pingcap.com/tidb/stable/release-8.5.0/)）。

传统模式下，TiDB Server 向 PD 获取 TSO 时是串行批处理——多个事务的 TSO 请求被合并成一个 batch 发送，等待 PD 返回后再分配。`PARALLEL` 模式允许 TiDB Server 同时向 PD 发送多个 TSO 请求，减少等待时间，但代价是 PD 的 TSO 处理压力增加——这是 TiDB 端延迟与 PD 端 CPU 的直接权衡，需要根据集群负载特征选择。

### 2.4 统计信息体系的改进

v8.x 系列对统计信息（Statistics）体系做了多处改进，这是优化器估算准确性的基础：

- **Embedded Analyze for DDL**（[v8.5.4](https://docs.pingcap.com/tidb/dev/release-8.5.4/)）：通过 `tidb_stats_update_during_ddl` 系统变量，在 DDL 操作（如创建/重建索引）完成后自动触发 ANALYZE，避免新索引在统计信息空白期内被优化器低估使用率，防止出现计划退化；
- **Schema Cache with LRU**（[v8.4.0 默认开启](https://docs.pingcap.com/tidb/stable/release-8.5.0/)）：通过 `tidb_schema_cache_size`（默认 512 MiB）控制 schema 元数据缓存，使用 LRU 替换策略，在大量表（数万张）的场景下显著降低内存占用；
- **NDV Estimation 优化**（[v8.5.4 #61792](https://docs.pingcap.com/tidb/dev/release-8.5.4/)）：改进对小 NDV 列的查询基数估算逻辑，减少估算偏差导致的执行计划选择错误。

---

## 三、自动化与运维智能化：Resource Control 的体系成熟

### 3.1 Resource Control：从实验到生产的完整历程

[Resource Control](https://docs.pingcap.com/tidb/stable/tidb-resource-control/)（资源管控）是 TiDB 7.x 到 8.x 期间最系统性的运维能力建设之一，解决的是多租户/多业务共享集群时的资源隔离问题。

**v6.6.0**：首次引入 Resource Control 作为实验特性，支持通过 `CREATE RESOURCE GROUP` 定义资源组，指定 `RU_PER_SEC`（Request Units per second，一种统一的资源度量单位，综合了 CPU、I/O 消耗）进行速率限制；

**v7.1.0 / v7.2.0**：Resource Control 正式 GA，新增 Runaway Query（[文档](https://docs.pingcap.com/tidb/stable/tidb-resource-control/#manage-queries-that-consume-more-resources-than-expected)）管理——可以设置当查询消耗的资源超过阈值时自动降级（切换到低优先级资源组）或终止，避免单个失控查询拖垮整个集群；

**v7.4.0**：Resource Control 在 TiFlash 侧实现（[TiFlash Resource Control 设计文档](https://github.com/pingcap/tiflash/blob/release-8.1/docs/design/2023-09-21-tiflash-resource-control.md)），基于 Token Bucket 算法实现速率限制，在 Pipeline 执行模型下通过优先级调度（priority scheduling）处理资源竞争；

**v8.x**：Resource Control 扩展到 Background Task 管理，包括自动统计信息收集（Auto Analyze）、DDL 操作、TiKV 的 Compaction 等后台任务，避免后台任务在业务高峰时占用过多资源。

从技术实现看，TiDB 的 RU（Request Unit）是一个跨层的统一资源度量抽象，包含：1 RU ≈ 1 CPU millisecond + 64 bytes 读 I/O + 1 KB 写 I/O（具体折算因子可配置）。这种统一度量单位避免了分别限制 CPU、内存、I/O 时的复杂策略配置，但代价是无法精确区分不同维度的资源瓶颈。对于 CPU-bound 的分析查询和 I/O-bound 的批量扫描，相同的 RU 消耗可能对集群的实际冲击完全不同。这是 RU 抽象的固有局限，也是未来细化资源管控的工程方向。

### 3.2 Accelerated Table Creation：DDL 的数量级跃升

**v8.5.0** 将 [Accelerated Table Creation](https://docs.pingcap.com/tidb/stable/ddl-introduction/#accelerate-ddl-execution)（[#50052](https://github.com/pingcap/tidb/issues/50052) @D3Hunter @gmhdbjd）正式 GA，并默认开启。

该特性的核心是：在批量建表时（如数据迁移初始化阶段），并行化 DDL 的元数据写入流程，利用 TiDB 的 [Distributed eXecution Framework（DXF）](https://docs.pingcap.com/tidb/stable/tidb-distributed-execution-framework/)协调多个 TiDB 节点协同处理建表任务，在数百万张表的场景下可以将时间从小时级压缩到分钟级。这对于从 MySQL 或 Oracle 迁移大型业务系统的场景（动辄数十万张表）有极大的实际意义。

### 3.3 Online DDL 进化：ADMIN ALTER DDL JOBS

**v8.5.0** 支持在线调整运行中 DDL 任务的执行参数（[Release Notes](https://docs.pingcap.com/tidb/stable/release-8.5.0/)）：

```sql
-- 在线调整指定 DDL 任务的 batch size
ADMIN ALTER DDL JOBS job_id BATCH_SIZE = 256;
-- 在线调整写入 TiKV 的流量上限
ADMIN ALTER DDL JOBS job_id MAX_WRITE_SPEED = '200MiB';
```

这对于生产环境中执行大表 `ADD INDEX` 时非常实用：可以在不中断任务的情况下，根据业务流量的峰谷变化动态降低或提升 DDL 资源消耗。

### 3.4 BR 备份恢复：客户端加密 GA

**v8.5.0** 中 BR（Backup & Restore）的客户端加密（[Client-Side Encryption](https://docs.pingcap.com/tidb/stable/backup-and-restore-use-cases/#encrypt-backup-data)）正式 GA，全量备份和日志备份均支持在客户端使用自定义密钥加密后再上传到 S3，满足数据主权（Data Residency）场景下备份数据不在云存储侧明文存放的合规需求。

---

## 四、HTAP 场景深化：Vector Search 与 AI 转型

### 4.1 Vector Search：TiDB 的 AI-Ready 转型信号

TiDB 对 Vector Search 的支持是 8.x 系列最具战略意义的新方向。v8.4.0 引入 `VECTOR` 数据类型和 HNSW（Hierarchical Navigable Small World）向量索引（[文档](https://docs.pingcap.com/tidb/stable/vector-search-index/)），v8.5.0 随 LTS 一并发布，成为官方支持特性。

**架构设计要点**：

1. Vector Index 存储在 TiFlash 而非 TiKV——这是必然选择：HNSW 索引本质上是一个图结构（多层 skip-graph），需要随机访问，TiKV 的 RocksDB 点查没问题，但 HNSW 的图遍历在列存层更容易利用 SIMD 加速距离计算；
2. 支持 `VEC_COSINE_DISTANCE()` 和 `VEC_L2_DISTANCE()` 两种距离函数，维度固定（如 `VECTOR(1536)` 对应 OpenAI text-embedding-3-small）；
3. **关键约束**：向量索引只能在已有 TiFlash Replica 的表上创建；索引构建是异步的（对已持久化数据构建 HNSW，delta 数据待持久化后再构建），查询结果始终完整（暴力扫描补充未索引的 delta 数据）；
4. **混合查询**：可以在单条 SQL 中将向量搜索结果与传统关系查询组合，如先用向量搜索找出相似商品（Top-K），再用 TiKV 数据过滤库存状态——这是 TiDB HTAP 架构的天然优势，其他专用向量数据库（Pinecone、Qdrant）无法做到这一点。

从工程视角看，TiDB 当前 Vector Search 的实现相对早期——HNSW 只支持单一距离函数索引，不支持 IVF（倒排文件索引，更适合超大规模向量数据集），也不支持量化（Product Quantization, PQ）。Oracle 23ai 已经实现了 IVF + AI Smart Scan 的组合，Databricks 则重写了整个 Vector Search 基础设施支持十亿级向量。TiDB 在这方面的工程深度还有较大差距，但胜在生态集成（HTAP 混合查询）这条差异化路线上。

### 4.2 TiKV 的 Partitioned Raft KV：写密集场景的存储引擎升级

[Partitioned Raft KV](https://docs.pingcap.com/tidb/stable/partitioned-raft-kv/)（pRaft KV）从 v7.4.0 开始在与生态工具的兼容性上得到大幅提升（DM、Dumpling、TiDB Lightning、TiCDC、BR、PITR 全面验证），在混合读写场景下性能更稳定，特别适合写密集型负载，单节点支持 8 核 CPU + 8 TB 存储 + 64 GB 内存的配置规模。

与传统 TiKV 的区别在于：pRaft KV 对每个物理节点上管理的 Region 做了分区存储（Partitioned）——不同 Region 的 RocksDB 实例不共享 WAL，减少了 WAL 的竞争，提升了写吞吐。代价是每个 TiKV 节点需要维护更多个 RocksDB 实例，内存占用和 Compaction 并发度管理更复杂。

### 4.3 TiDB 与 ClickHouse/StarRocks 的 HTAP 路线对比

作为 StarRocks 的内核工程师，这里值得做一个直白的横向对比：

| 维度 | TiDB | StarRocks | ClickHouse |
|------|------|-----------|------------|
| 核心优势 | HTAP 统一引擎，TP 侧强一致性，零 ETL 实时分析 | 极致 OLAP 性能，物化视图，向量化执行成熟 | 极致写入吞吐，单机 OLAP 性能无对手 |
| AP 引擎成熟度 | TiFlash MPP 可用，但 TPC-H 性能与 SR/CH 差距明显 | 最强 | 强，但分布式支持较弱 |
| 数据新鲜度 | 秒级（Raft Learner 异步复制） | 取决于导入频率（通常分钟级） | 分钟级 |
| 事务能力 | 完整 ACID，Snapshot Isolation | 无 | 无 |
| 向量搜索 | HNSW（早期），与 HTAP 混合查询 | 无 | 无 |
| 云原生架构 | TiFlash Disaggregated 支持 S3 | Shared-Data 模式（S3 原生） | 无存储分离 |
| 运维复杂度 | 高（TiDB + TiKV + TiFlash + PD + TiCDC...） | 中等 | 低 |

TiDB 的根本定位不是要在 AP 性能上超越 StarRocks 或 ClickHouse——它的差异化是：**在不引入额外数据仓库的前提下，让 TP 的实时数据直接可用于 AP 分析**。这对于需要"新鲜数据 + 复杂分析 + 事务一致性"的场景（如金融风控、实时库存分析、SaaS 多租户数据服务）是有真实价值的。

---

## 五、商业化与生态：TiDB Cloud 的 Serverless 深化

### 5.1 TiDB Cloud Serverless 的架构基础

TiDB Cloud Serverless 在 2023-2025 年间持续深化，其背后的核心技术就是 **TiFlash Disaggregated Architecture**：Compute Node 完全无状态，可以在查询量为零时缩减为 0，在流量突发时秒级扩容。这与 Snowflake Serverless / Databricks Serverless 的思路完全一致，但 TiDB 的优势是同时支持 TP 工作负载（TiKV 侧）的弹性。

TiDB Cloud 在 2025 年推出了新的存储类型分层：Standard storage type 自动应用于 2025 年 4 月 1 日之后在 AWS 上创建的新 TiDB Cloud Dedicated 集群（需要 v7.5.5、v8.1.2 或 v8.5.0 及以上版本），这是 TiDB Cloud 在存储成本优化上的一次重要里程碑。

TiDB Cloud Serverless 在大数据写入场景的成本降低了 80%：当在 autocommit 模式下执行超过 16 MiB 的写操作，或在乐观事务模式下执行超过 16 MiB 的写操作时均可获益，这对于大批量 ETL 导入场景有显著降本效果。

### 5.2 TiDB Cloud Branching：面向 GitOps 的数据库分支

TiDB Cloud 的 Branching 功能支持灵活的分支创建：可以选择特定集群或分支作为父节点，并指定精确的时间点使用父节点数据，这类似于 Neon（已被 Databricks 收购）的数据库分支功能，为 CI/CD 流水线提供了隔离的测试数据库环境，无需复制实际数据。

这个功能的技术基础同样是 Disaggregated TiFlash 的快照语义，加上 TiDB 的 MVCC 机制，实现 copy-on-write 式的数据分支——不同分支共享同一份基础数据在 S3 的物理存储，只写入差异部分。

### 5.3 开源与商业化的协同

TiDB 坚持 Apache 2.0 开源策略，核心数据库引擎（TiDB、TiKV、TiFlash、PD）全部开源，这是 PingCAP 差异化于 CockroachDB（Business Source License，3 年后才能自由使用）和 MongoDB（SSPL）的重要竞争策略。

在 TiDB 8.5 的开源贡献中，来自 Airbnb、ByteDance、Flipkart、LinkedIn 和 Plaid 等大型公司的工程师不仅在使用 TiDB，也在积极为其贡献代码——这个社区贡献格局是 TiDB 技术护城河的重要组成部分，也是其开源商业模式可持续性的直接证明。

从商业竞争格局来看，PingCAP 的多云策略明确：TiDB Cloud 同时支持 AWS（主要）、GCP 和 Azure，这避免了单云依赖，但也意味着需要维护更复杂的多云基础设施。与 CockroachDB 的竞争更多在金融、政府等强一致性场景；与 PlanetScale（基于 Vitess 的 MySQL 分片）的竞争在中小型互联网业务场景；真正与 Databricks / Snowflake 竞争则是 TiDB 8.x 发力 HTAP 分析场景的新战场。

---

## 六、总结与洞察：三条主线，一个未完成的转型

回看 TiDB 从 7.1 到 8.5 的整个演进路径，可以提炼出三条清晰的主线：

**第一条主线：存储计算分离的彻底化**。TiFlash Disaggregated Architecture 的 GA（v7.4.0）是这条主线的标志，它不仅是一个部署选项，更是 TiDB Cloud Serverless 的架构基础。这条路径在技术上已经基本走通，但工程成熟度（稳定性、性能调优、迁移复杂度）仍在持续打磨中。

**第二条主线：系统性地补齐 MySQL 兼容性和 Oracle 迁移能力**。Global Index GA（v8.4.0）、`SKIP LOCKED`、外键约束强化、JSON 函数扩展……这些变化表面上碎片化，实质上是 PingCAP 在逐步消化来自传统数据库迁移客户的核心诉求。这条主线驱动了大量的商业落地。

**第三条主线：向 AI-Ready 数据库转型**。Vector Search（v8.4.0 引入，v8.5.0 随 LTS 发布）是这条主线的起点，但目前仍处于早期——HNSW 索引功能基础，与 LLM 生态的深度集成（如 LangChain、LlamaIndex）正在建设中。TiDB 在这条路上的真正竞争力来自 HTAP 的天然优势：一个 RAG 应用既需要向量搜索（查知识库），又需要联合结构化数据（查用户状态、权限、业务规则），TiDB 是能在一个数据库里同时完成两件事的极少数选手之一。

**一个未完成的问题**：TiFlash 的 AP 性能与 StarRocks、ClickHouse 之间的差距，在过去三年并没有被显著缩小。Pipeline 执行引擎、Runtime Filter、HashAgg 多模式优化都是在补齐基础能力，而非实现超越。对于重度 OLAP 场景，TiDB 的 HTAP 架构仍然难以替代独立的 OLAP 数仓。TiDB 的正确商业叙事应该是：**不是"替代 StarRocks/ClickHouse"，而是"减少对独立 OLAP 系统的依赖频率，让 80% 的分析需求在 HTAP 框架内得到满足"**。

这是一个足够大的市场，也是一条需要继续走很久的路。

---

*参考资料：[TiDB Release Notes Index](https://docs.pingcap.com/releases/tidb-self-managed/) | [TiDB v8.5.0 Release Notes](https://docs.pingcap.com/tidb/stable/release-8.5.0/) | [TiDB v8.4.0 Release Notes](https://docs.pingcap.com/tidb/dev/release-8.4.0/) | [TiDB v8.3.0 Release Notes](https://docs.pingcap.com/tidb/stable/release-8.3.0/) | [TiDB v7.4.0 Release Notes](https://docs.pingcap.com/tidb/stable/release-7.4.0/) | [TiFlash Disaggregated Architecture](https://docs.pingcap.com/tidb/stable/tiflash-disaggregated-and-s3/) | [TiKV MVCC In-Memory Engine](https://docs.pingcap.com/tidb/stable/tikv-in-memory-engine/) | [Global Indexes](https://docs.pingcap.com/tidb/stable/global-indexes/) | [Runtime Filter](https://docs.pingcap.com/tidb/stable/runtime-filter/) | [TiFlash Resource Control Design](https://github.com/pingcap/tiflash/blob/release-8.1/docs/design/2023-09-21-tiflash-resource-control.md) | [IME Blog: Query Performance Unleashed](https://www.pingcap.com/blog/accelerating-query-performance-tidb-in-memory-engine/)*
