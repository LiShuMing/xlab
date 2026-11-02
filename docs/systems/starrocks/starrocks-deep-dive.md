# StarRocks 深度技术报告
## 面向核心开发者：你可能没有完整跟踪的模块演进、社区痛点与竞品挑战

> **阅读对象**：StarRocks 核心 Committer。FE/BE 分层、MPP 执行、向量化基础略去不表，直接切入设计决策与工程权衡。

---

## Executive Summary

v3.0→v3.3 这一轮演进的战略主轴清晰：**存算分离从 Preview 走向 GA，物化视图从单功能走向透明改写平台，Primary Key 从"能用"走向"高性能写入"**。v3.4/v3.5 继续在 Multi-Warehouse、湖仓写入、向量索引三条线推进。

对核心开发者而言，最值得关注的几个工程风险点：

1. **缓存体系三代并存**：File Cache → Block Cache（Page Cache + Block Cache）→ v4.0 统一 Data Cache，存量用户升级路径复杂，参数语义漂移是高频 issue 来源。
2. **Persistent Index 的 L0/L1 合并时机**：当前实现在 L1 文件很大（~4GB）时，即使只更新一行也会 flush 一个约 256MB 的 snapshot，磁盘 IO 放大问题被多个 PR 反复修补（#12862、#34352）。
3. **Iceberg Equality Delete 的 MOR 路径**：v3.2.5 才对 Parquet 格式完整支持，实现为 left anti-join，delete file 数量大时内存和 jemalloc 压力显著——这是当前湖仓场景最容易踩的坑。
4. **CBO Join Reorder 的 5 表阈值**：≤5 表走穷举，>5 表直接降级 Greedy，缺乏平滑过渡，复杂多维分析场景下容易生成次优计划。

---

## 一、存算分离 Shared-Data：StarCache + CN 无状态化深度解析

### 1.1 缓存演进：从 File Cache 到 Block Cache

早期（v3.0/v3.1 初版）的 File Cache 以 **Segment 文件** 为缓存单元，即便只访问一列也要加载整个 segment file。v3.1.7/v3.2.3 开始切换为 **Block Cache**，改为按 MB 级 block 按需加载——这是一个关键的性能跃升，特别是对宽表的列裁剪场景。

v3.3.0 起 Data Cache 默认启用，架构变为双层：
- **Page Cache（内存）**：存储解压后的 data page，粒度不固定，LRU 淘汰，用于 native 表和外表。
- **Block Cache（磁盘）**：存储原始 remote 数据块，持久化（CN 重启后可复用），通过 `starlet_star_cache_disk_size_percent` 控制容量上限。

v3.3.2 引入了更激进的**防缓存污染**策略：全表扫、全分区扫、非 SELECT 语句（如 ANALYZE TABLE）不填充 Block Cache，避免大查询将热数据驱逐出去。v3.3.0 还加入了 **CACHE SELECT** 主动预热，让 cache warmup 可编程化。v3.4 则引入了 **Segmented LRU（SLRU）** 替代普通 LRU，对大扫描查询的 cache 污染防御更系统。

**v4.0 统一**：内存与磁盘缓存参数被合并入统一 Data Cache 系统，存量 v3.x 升级需要迁移配置——这是近期 ops 用户的一个隐患。

### 1.2 CN 无状态化的边界

CN 的"无状态"是相对的：
- **真正无状态**：数据文件不在本地，无副本管理、无 tablet 所有权。
- **有本地状态**：Block Cache（可容忍丢失，重启后重建），Persistent Index（Primary Key 表在 v3.1.4 之后支持 index 持久化到 CN 本地磁盘）。Spill 临时文件也在本地。

扩缩容时，只需重新分配 tablet scan 范围，不需要数据迁移——这是与 BE 的根本差异。FE 通过 StarOS（内部 shard 管理层）维护 CN 到 shard 的映射，多 CN 共享同一 shard 时通过版本号保证读一致性。

### 1.3 Multi-Warehouse 现状（2025→2026 路线）

多 Warehouse 共享同一 Storage 的**元数据并发控制**是当前最复杂的工程问题。当前架构：多 Warehouse 下各自有独立的 CN pool，FE Leader 统一管理 tablet version 和 transaction，通过乐观并发控制（版本号 check）处理写冲突。

Roadmap 2026（#67632）明确将 Multi-Warehouse、Range-based data distribution（#64986）、Auto tablet split 列为 Native Storage 的核心投入点，说明当前 multi-warehouse 下的 tablet 调度在大规模场景（>10M shards）仍有明显瓶颈（Roadmap 2024 #39686 已提及"Shard schedule optimization for large scale"）。

**与 Snowflake Virtual Warehouse 的关键差异**：Snowflake 的 Virtual Warehouse 之间通过 Global Services Layer 协调，元数据在 FoundationDB 中统一存储，写冲突在 cloud service layer 序列化。StarRocks 的 FE BDBJE 元数据存储在高并发写入下本身就是瓶颈——这是架构上的历史包袱。

---

## 二、物化视图透明改写：规则覆盖度与 Cost-based 选择

### 2.1 SPJG 改写框架及其边界

StarRocks 透明改写基于 **SPJG（Select-Project-Join-Group-by）** pattern，这个框架本质上覆盖了大多数 BI 和 reporting 查询，但对以下场景存在明确限制：

- **ORDER BY 在 MV 定义中会禁用 SPJG 改写**（保证全局排序与透明改写语义冲突，官方文档明确说明）。
- **JDBC Catalog 和（早期）Hudi Catalog 上的 MV 不支持改写**。
- **非 SPJG pattern 的子查询**：v3.3.0 前，view-based MV 会把 query 展开成 base table 查询再做 SPJG 匹配，对深层嵌套 view 会失败；v3.3.0 引入 view-based rewrite 和 text-based rewrite 两种补丁路径，一定程度绕过了 SPJG 限制。

**Join 类型支持**：INNER JOIN、LEFT/RIGHT OUTER JOIN、SEMI JOIN、ANTI JOIN 均在 SPJG 框架内支持改写。特别值得注意的是 **View Delta Join**：MV join 的表比 query 多，当多余的 join 是 1:1 cardinality preservation join 时可以自动消除——这是 SSB 等 star schema benchmark 场景的关键优化。

### 2.2 改写匹配算法细节

Query-to-MV 的 subsumption 检测流程：
1. 对 query 和 MV 分别做 SPJG 分解，提取 predicates、grouping expressions、output expressions；
2. 判断 query 的 output 是否能从 MV 的 output 中 derive（列等价类检查 + 谓词包含关系检查）；
3. 对聚合函数做 rollup 推理：MV 中的 `SUM` 可以被 query 中的 `SUM` 复用，`COUNT(DISTINCT)` 复用需要 bitmap/hll 转换；
4. 多 MV 候选时，走 CBO 估算每个 MV 的扫描代价（行数 × 宽度），选最低代价方案。

**Partition-level Refresh 的谓词裁剪**：对分区 MV，query 中包含分区裁剪谓词时，改写会只扫描 MV 中已刷新的分区，过期分区回退到 base table——这个行为由 `mv_rewrite_staleness_second` 控制，设计上允许用户在 freshness 与性能之间权衡。

### 2.3 与 Doris 异步 MV 的对比

Doris 异步 MV 的透明改写（基于 Nereids）在功能上已大幅追赶，两者 SPJG 框架类似。差异主要在：Doris MV 对 Hive/Iceberg external table 的 partition-level refresh（v2.1 才开始做），StarRocks 在这里领先约一个版本周期。此外 StarRocks 的 text-based rewrite（v3.3）和 view-based rewrite 是 Doris 目前尚未完整复制的能力。

---

## 三、Primary Key 表：Persistent Index 三层结构与写入放大

### 3.1 L0/L1/L2 结构详解

**L0（内存 + WAL 文件）**：所有新的 upsert/delete 先写入内存 hash map，并 append-only 追加到磁盘 WAL 日志（`index.l0` 文件）。`l0_max_mem_usage` 默认 100MB/tablet 控制内存上限。

L0 flush 到 L1 的触发条件（来自 PR #12862 的注释）：
- L0 内存用量 > L1 用量的 10%，且 > 最大 snapshot size（默认 16MB）；
- **或** L0 WAL 文件大小 > 200MB（防止 WAL 无限增长）。

**L1（本地磁盘 B-tree 文件）**：将 L0 snapshot 合并后写入，key 有序存储，支持二分查找。文件可以有多个（批量写入时会先 flush 多个 temp L1），最终 merge 为一个。注意：**PR #34352 修复了一个 bug：当只有一个 temp L1 文件时，delete 操作会被重复写入 new L1 文件，导致 L1 文件比预期大**，影响磁盘 IO 效率——这个 bug 直到 v3.2/v3.1 才修复，说明早期 L1 merge 路径存在较长时间的隐患。

**L2（对象存储，v3.3 引入）**：shared-data 场景下，Primary Key index 支持 remote storage 落盘，增强了弹性，代价是 lookup 延迟增加（需从对象存储拉取 index block）。

v3.3 同时优化了 persistent index 的**读 IO 粒度**：支持以更小的 page 粒度读取，减少不必要的 IO 放大；并改进了 Bloom Filter 以减少 false positive。

### 3.2 写入放大分析

一条 Update = Delete（标记原行到 DelVector）+ Insert（新行写入新 rowset）。

主要写入放大来源：
1. **L0 → L1 flush**：每次 snapshot flush 重写整个 L0 内容，L1 大时（比如 4GB）而 L0 更新量只有 256MB 时，IO 放大比约 16:1。
2. **Compaction**：Primary Key 表的 compaction 需要同时合并 rowset 和更新 Persistent Index，内存压力较大（Issue #61388：stream load 时 compaction 内存用量达 60GB）。
3. **Size-tiered Compaction**（v3.3 引入）：替代之前默认的 leveled-style，减少写 IO 和内存开销，适合高频写入场景。启用 `enable_pk_size_tiered_compaction_strategy=true` 后，`max_pk_rowsets_num_in_compaction` 默认从 5 提升到 1000（v3.2.4+），允许更多 rowset 参与一次 compaction，减少积压。

### 3.3 与 ClickHouse ReplacingMergeTree 的对比

ReplacingMergeTree 是后台异步去重，查询时可能读到未合并的旧版本（需要 `FINAL` 关键字强制合并，代价高昂）。StarRocks PK 表通过 DelVector 在**读路径**过滤已删除行，保证查询总能看到最新状态，无需 `FINAL` 等价物。代价是写入时额外的 index lookup 开销。

Doris Unique Key MOW（Merge-On-Write，v2.0 引入）与 StarRocks PK 表的设计方向一致，也是写时去重，但 Doris 的实现不使用独立的 Persistent Index 文件，而是在 rowset 内部维护 delete bitmap。两种方案各有利弊：StarRocks 的独立 index 文件查找效率更高（O(1) hash lookup），但文件管理复杂度更高。

---

## 四、CBO 优化器：统计信息精度与 Join Reorder 降级策略

### 4.1 统计信息体系

**基础统计**（自动周期采集）：每列的 NDV、NULL count、min/max、avg row size。采样策略：按 row 比例采样（`statistic_sample_collect_rows`），默认采样不超过 20 万行。v3.2 开始支持从 Hive/Iceberg/Hudi 直接采集统计信息。

**Histogram（v2.4 引入，仍需手动触发）**：等高直方图（equi-height），每个桶包含等量数据，对高频值（MCV）单独分配桶。关键参数：`WITH N BUCKETS`（桶数），`histogram_mcv_size`（MCV 数量，默认 32），`histogram_sample_ratio`（采样比例）。**重要限制：Histogram 不在自动采集任务中，必须手动 `ANALYZE TABLE ... UPDATE HISTOGRAM`**——这是用户最容易忽略的盲点，对数据倾斜列影响极大。

**Query Feedback（v3.x 引入）**：执行时记录 PlanNode 的实际 InputRows/OutputRows，与 CBO 估计值对比，生成 tuning guide，下次执行时自动修正 Join 顺序。由 `enable_plan_advisor`（默认 true）和 `slow_query_analyze_threshold`（默认 5s）控制。这是对 histogram 不足的运行时补偿机制。

### 4.2 Join Reorder 降级策略

官方文档和源码分析（Medium 技术文章）揭示：
- **≤5 张表**：基于交换律和结合律的穷举搜索（Exhaustive），搜索空间约 5! / 2 = 60。
- **>5 张表**：降级为 **Greedy** 算法，每次选当前代价最低的 join，不保证全局最优。
- 另有 **DPsub**（子集 DP）和 **Left-Deep Tree** 约束模式作为备选。

**阈值 5 是一个明显的工程 shortcut**。对于 TPC-DS 中 8-10 表 join 的查询，Greedy 可能比穷举差 10%-30% 的计划质量（取决于统计信息精度）。Doris Nereids 同样面临类似问题，但 Nereids 将阈值设计为可配置参数，灵活性略好。

**Cascades 框架 vs Calcite**：StarRocks CBO 基于 Cascades-like 框架，深度定制（非 Calcite），规则集与向量化执行引擎高度耦合。好处是没有 Calcite 的 rule explosion 问题；代价是社区共享规则的成本高——这也解释了为何 StarRocks 的 optimizer 规则贡献主要来自内部团队。

---

## 五、Pipeline 执行引擎：Driver 调度、Spill 与 Back-pressure

### 5.1 Driver/OperatorChain 架构

一个 Fragment Instance 被拆分为若干 Pipeline，每个 Pipeline 是 Source → Operators → Sink 的链式结构。**Driver** 是 Pipeline 的执行单元，包含一个 OperatorChain 和一个调度状态机。

数据流：`SourceOperator::pull_chunk()` → 逐级 `push_chunk()` → `SinkOperator`，以 **Chunk**（固定行数 batch，默认 4096 行，可通过 `vector_chunk_size` 调整）为单元流转。

**IO Task 与 CPU Task 分离**（关键设计）：当 ScanOperator 需要读取 remote 数据（object storage）时，它会提交一个异步 IO Task，Driver 进入 `PENDING_CHUNK` 状态，释放 CPU 线程。IO 完成回调后，Driver 重新入队 CPU 调度池。这是避免 IO 阻塞 CPU 线程的关键机制，在 shared-data 场景尤其重要——详见 StarRocks Engineering Medium 文章《Deep Dive To StarRocks I/O Model》系列（2025.12）。

**LocalExchange** 算子实现三种模式：PassThrough（同 Pipeline 内传递）、Partition（按 hash 分发到不同 Pipeline）、Broadcast（广播）。是 Pipeline 内并行数据分发的核心原语。

### 5.2 Spill to Disk

从 v3.0.1 开始支持，覆盖算子：Hash Join（build side）、Hash Aggregate、Sort。

触发机制（两层）：
1. **Query 级别**：query 内存用量超过 `query_mem_limit * 80%`；
2. **Resource Group 级别**（v3.1.7+）：RG 内所有 query 总内存超过 `BE内存 * mem_limit * spill_mem_limit_threshold`。

Spill 文件格式：**自定义格式**（非 Arrow，基于 Chunk 序列化），写入 `spill_local_storage_dir` 指定的本地目录。v3.x 支持配置多个 spill 目录以利用多块磁盘，并支持 direct IO（commit `0d5626f`：`support yield and direct io for spill`）。

v3.4 发现的 Spill + Pipeline 协同 bug（#65027）：Hash Join spill 时，build side 的 `set_finishing` task 失败后状态只记录在 spiller 内部，probe side 继续执行，导致 crash 或无限循环——说明 Spill 与 Pipeline 状态机的交互边界还有未覆盖的错误路径。

Back-pressure 传递：当下游算子的 output buffer 满时（`has_output() == false`），Driver 状态切换为 `PENDING_FINISH` 或 `INPUT_EMPTY`，调度器不再分配 CPU，天然实现反压。

### 5.3 Global Runtime Filter（GRF）

RF 类型选择策略：小 NDV 用 In-list，大 NDV 用 Bloom Filter，数值列用 Min-Max（代价最低）。

GRF（跨 Fragment）传递：build side 完成后，GRF 通过 FE 协调分发到所有 probe side Fragment Instance。**Early RF**（等待 RF 就绪后再 probe）vs **Late RF**（probe 端先扫描，RF 就绪后过滤）——当前实现在 RF 构建慢时默认走 Late RF 降级，避免阻塞。

---

## 六、湖仓分析：External Catalog 元数据缓存与 Iceberg MOR

### 6.1 元数据缓存策略

**默认行为**：首次查询时缓存 table metadata，24 小时内保活，后台每 10 分钟刷新一次（`background_refresh_metadata_interval_millis`）。60 秒内再次查询直接命中缓存且认为 fresh（`iceberg_table_cache_refresh_interval_sec=60`）；60-10分钟窗口内，使用 stale 缓存同时触发异步刷新。

**Iceberg Delete File 缓存**（关键参数）：`iceberg_delete_file_cache_memory_usage_ratio`，默认 10% 内存。在大量 equality delete 场景下，delete file 本身的元数据就可能撑满这个限制，导致反复从 HMS/S3 拉取——这是高频写入 + 实时查询场景的性能杀手。

**Partition-level 检测能力**：Hive Catalog、Iceberg Catalog（v3.1.4+）、JDBC/MySQL（v3.1.4+）、Paimon（v3.2.1+）支持分区级变更检测，可做增量 MV 刷新。Hudi Catalog 只支持全量刷新（无分区级变更检测）。

### 6.2 Iceberg Equality Delete MOR 实现

这是近两年湖仓场景最重要的改进之一，实现细节值得关注：

- **Position Delete**：在 scan 时直接应用，构建 bitmap，删除行不物化到 Chunk，代价极低。
- **Equality Delete**：实现为 **Left Anti-Join**，data file 是 left child，delete file 是 right child。相比 position delete，equality delete 需要额外的 hash join 算子，内存开销与 delete file 规模成正比。

关键限制（来自 PR #37419）：**不支持 equality column 的 schema evolution**（add/drop eq column）。这在 Flink CDC 写 Iceberg 的场景下是一个实际约束——Flink upsert 模式会产生大量 equality delete，schema 变化时可能需要 Spark compaction 将 delete file 合并掉才能查询。

一个 user 的实际 issue（#41866）显示：在大量 equality delete 文件的场景下，jemalloc 内存分配压力大，用户建议降低 `delete-file-threshold`（Iceberg 写入侧）或手动触发 Spark compaction。这说明 StarRocks 侧的 equality delete 处理在 delete file 数量极多时效率退化，**应当在 v3.4/v3.5 中优化为减少重复读取 delete file 的机制**——这已在 v3.4 release note 中明确提及（"Optimizes Iceberg V2 query performance by reducing repeated reads of delete-files"）。

支持矩阵：ORC 格式 equality delete 从 v3.1.8/v3.2.3 开始，Parquet 从 v3.2.5 开始。v3.3 官方宣布"Added support for V2 table equality deletes"。

### 6.3 Native Parquet/ORC Reader 的 Late Materialization

StarRocks native reader 支持 Late Materialization：先用过滤列（predicate 列）确定命中行的 rowid bitmap，再按 rowid 拉取其他列——这对宽表 + 高选择率谓词场景有显著收益。v3.3 进一步支持 Parquet Page Index（Column/Offset Index），可以跳过整个 page，减少扫描的物理 IO。

---

## 七、社区真实痛点：GitHub Issues 高频问题根因分析

### 7.1 OOM 类问题根因分布

| 根因 | 典型 Issue | 算子/模块 |
|---|---|---|
| Primary Key compaction 内存失控 | #61388（compaction 内存 60GB） | Compaction + PK Index |
| Nestloop Join 大 ARRAY | v3.3 release note #55603 | NestloopJoin |
| CASE-WHEN 深层嵌套，FE expression tree 节点爆炸 | v3.4 release note #66379 | FE Parser/Analyzer |
| Java UDAF heap OOM | v3.4 release note #67025 | UDAF |
| Hash Join 内存估计不准（Spill 未及时触发） | 通用 | HashJoinOperator |

PK 表的 compaction OOM 是 **生产环境最高频投诉之一**，根因是 `l0_max_mem_usage * tablet_count` 上限控制不够精细，高并发写入时多个 tablet 同时 flush 叠加超出 BE 内存。

### 7.2 Schema Change 阻塞写入

StarRocks Schema Change（linked/sorted schema change）会对涉及的 tablet 加写锁，阻塞 load。v3.x 的 Light Schema Change（仅修改列元数据，不重写数据）大幅缓解了 ADD/DROP COLUMN 的阻塞，但 Type Change（如 INT→BIGINT）仍需完整的数据重写，期间写入受限。

v3.4 release note 中有 `ALTER TABLE` 导致 metadata lock 缺失的 bug fix（#55605），说明这一块的锁管理历史欠债较多。

### 7.3 Compaction 积压

高频写入场景（如 Stream Load 每批 300MB，4 线程并发）容易导致 tablet 的 rowset 积压，Compaction Score（CS）持续走高。v3.3 引入了**降载策略**：当 Compaction 任务无法及时完成时，自动降低 load 速率（#52269）——这是一个合理的 backpressure，但用户感知为"写入变慢"，是常见投诉来源。

v3.4 fix #59998（"Under high-frequency loading scenarios, Compaction could be delayed"）证实了这是持续工程投入的方向。

### 7.4 External Catalog 元数据不一致

最高频的投诉模式：Hive/Iceberg 数据已更新（Spark/Flink 写入），StarRocks 查询仍返回旧数据。根因是 10 分钟异步刷新窗口 + 60s fresh 窗口的设计——对于分钟级刷新需求的用户，默认参数不满足。

建议生产配置：将 `iceberg_table_cache_refresh_interval_sec` 降低，或使用 `REFRESH EXTERNAL TABLE` 手动强制刷新。

### 7.5 FE BDBJE 运维痛点

BDBJE（BerkeleyDB Java Edition）是 FE 元数据存储的核心，主要痛点：
- **脑裂风险**：BDBJE 使用 Paxos-like 协议，但网络分区时的恢复流程复杂，社区曾有多起"FE 主节点切换后元数据不一致"的报告。
- **元数据膨胀**：大规模集群（百万 tablet）下 BDBJE 数据库文件增长，影响 FE 启动时间（v3.4 Roadmap 将 "Accelerate FE startup" 列为 2026 重点）。
- **BDBJE 替换**：Roadmap 2024 提及"Decoupled storage for FE（Finished design）"，说明已有替换 BDBJE 的设计，但尚未上线。

---

## 八、竞品技术挑战

### 8.1 Apache Doris 的追赶

**Nereids 优化器**（Doris v2.0 GA）已在 TPC-DS 全量 SQL 支持上追平。Doris 官方 blog（以某安全厂商用户案例为例）显示：用 3 台 Doris 节点（30% CPU）替换了 13 台 StarRocks 节点处理同等写入负载，主要优势在 **inverted index** 对文本字段的检索效率（StarRocks 当时缺 inverted index，v3.x 才补充）。

**物化视图追赶**：Doris 异步 MV 的 transparent rewrite 在 v2.1+ 已基本追平 StarRocks v2.5 水准，但 partition-level refresh 和 view-based rewrite 落后约一个版本周期。

**Apache 品牌**：在国内大型企业采购中，Apache 品牌确实有优势（合规、社区中立性），但在海外市场影响相对有限。值得关注的是 StarRocks 2024 年宣布加入 Linux Foundation，试图建立类似的中立性。

### 8.2 ClickHouse 的防御优势

**点查低延迟场景**：ClickHouse 在 ClickBench 上的成绩仍略优于 StarRocks（来自 toddstoffel/analytics_benchmark：ClickHouse 6.41s vs StarRocks 6.76s，均 100% 查询成功率）。两者差距已非常接近，但 ClickHouse 在 MergeTree 的 index granularity 机制上对高并发点查有天然优势。

StarRocks 的 **Row Store**（Roadmap 2024 提及"Optimize row store for high concurrent point lookup"）是对抗 ClickHouse 点查优势的核心战略。

**生态压力**：ClickHouse 的 Grafana 数据源插件、Superset 集成成熟度确实优于 StarRocks，但差距在 2023-2024 年已大幅收窄。

### 8.3 Databricks/Snowflake 的下压

在 Lakehouse 场景，用户选择 "Databricks 一站式"的决策驱动力不是 StarRocks 的性能，而是**减少系统数量**（Databricks = ETL + Delta Live Tables + Databricks SQL + ML）。对于已有 Databricks 合同的用户，采购 StarRocks 需要额外论证 ROI。

StarRocks 的反制是：在 Shopee 等用户案例中，StarRocks 的 ad-hoc 查询性能是 Presto/Spark SQL 的 **2-3x**（使用相同算力，Shopee 案例，2024.09），这使得"用 StarRocks 替换 Databricks SQL"在纯查询性能上有充分论据。关键问题是写入侧（ETL）StarRocks 原生支持有限，需要依赖 Flink/Spark 做上游，这给 Databricks 留下了护城河。

### 8.4 DuckDB/MotherDuck 的侧翼威胁

DuckDB 在 < 1TB 的单机/小团队场景下，部署运维成本几乎为零，这对 StarRocks 构成侧翼压力。但两者的竞争层面几乎不重叠：DuckDB 主要面向数据分析师/工程师个人使用，StarRocks 面向企业级多并发查询服务。MotherDuck（DuckDB 云托管）在小团队市场有切入，但其并发能力上限使得它无法替代 StarRocks 的核心场景。

真正的风险是 **DuckDB Wasm + BI 工具集成**（Metabase、Observable 等）在边缘分析场景的蚕食。

---

## 九、商业化与开源策略

### 9.1 开源边界

StarRocks 是 **Apache 2.0 全开源**（2024 年捐赠 Linux Foundation），核心功能无闭源版。CelerData 商业版（CelerData Cloud / BYOC）的独有能力主要是：
- 托管云服务的运维自动化（auto-scaling、备份恢复）；
- 企业级安全审计、SSO 集成；
- 优先级 SLA 支持。

对比 ClickHouse Inc.（ClickHouse Cloud 有部分企业功能不开源，如 RBAC 的细粒度功能较早在云端）和 Doris（完全 Apache 开源，无商业公司主导的闭源功能），StarRocks 的开源策略是三者中**开放程度最高的**。

### 9.2 社区国际化

海外贡献者占比呈上升趋势，但核心 Committer 仍以 CelerData 员工为主。与 ClickHouse（俄罗斯发起，国际化非常充分，Issues 以英文为主，贡献者遍布全球）相比，StarRocks 的社区国际化程度仍有差距。英文文档质量在 v3.3 后有明显提升（官方声明"added more comprehensive definitions for product capabilities"）。

---

## 十、技术路线前瞻（2025→2026）

### Roadmap 2026 关键信号（#67632）

**Native Storage（Shared-Data）**：
- Multi-Warehouse 正式 GA（Range-based distribution #64986，Auto tablet split）
- 支持更大 Tablet 的 scalability（#66457，当前 shared-data 下单 tablet 大小有瓶颈）
- FE 启动加速、FE graceful step-down（#63357，BDBJE 替换前的临时方案）

**Iceberg 深度集成**：
- Iceberg Delete/Update（#66944）——从只读到读写，这是 2026 最重要的单点突破
- Iceberg V3 spec compliance（deletion vectors、variant type）

**AI/向量方向**：
- Vector Index（ANNS）在 v3.4 已实验性支持，2026 走向稳定
- Hybrid search（vector + full-text + scalar）——与 Elasticsearch 竞争的重要武器

**执行引擎**：
- Sub-second data freshness（Roadmap 2025）——降低 load → 可查 延迟至秒级以内
- 并发事务提交优化（Enhanced concurrent transaction commits）——高并发写入场景的关键

### SIMD/AVX-512 覆盖率

当前向量化引擎以 AVX2 为基线，部分热路径（如 hash join 中的 hash 计算、字符串 compare）已有 AVX-512 优化，但覆盖率不系统。ARM Graviton 的优化在 v3.3 有明确投入（测试显示性能大幅提升），说明 ARM first-class 支持已成战略方向，与 Roadmap 的云原生定位一致。

---

## 总结

StarRocks v3.x 的技术债主要集中在三处：**FE BDBJE 元数据存储的可扩展性**、**Persistent Index 的写入放大**、**Iceberg Equality Delete 在高 delete file 数量下的性能退化**。这三个问题在 GitHub Issues 和 Release Notes 中均有持续工程投入的证据，但截至 v3.4 均未完全解决。

从竞品格局看，StarRocks 在复杂多表 join + 物化视图透明改写的组合场景下仍有技术领先优势，这也是其核心护城河。Doris 的追赶速度值得重视，特别是在 inverted index 和 Nereids 成熟后的日志分析场景。湖仓读写能力（Iceberg 写入）是 2026 的决战场。
