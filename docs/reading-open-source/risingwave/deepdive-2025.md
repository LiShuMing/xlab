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


# RisingWave 深度技术分析：IVM、Hummock 与云原生流处理架构

> 作为 StarRocks 核心开发者的视角，结合公开技术资料综合分析

---

## Executive Summary

RisingWave 是一个以 **Incremental View Maintenance（IVM）** 为核心设计哲学、用 Rust 全栈实现的云原生流处理数据库。它将"流处理"问题重新定义为"持续增量维护物化视图"的问题，以 PostgreSQL 协议为接入标准，以自研的 **Hummock**（基于对象存储的 LSM-tree 引擎）为状态存储底座，以 **Barrier-based Checkpoint** 为一致性保障机制，构建了一套与 Flink 截然不同的技术体系。

对 StarRocks 开发者而言，最值得关注的核心差异有三点：
1. **状态存储完全 Disaggregated**：Hummock 把所有流处理状态持久化到 S3，Compute Node 本身无状态，这使得弹性伸缩（Rescaling）在架构层面成为可能；
2. **SQL-first 而非算子-first**：整个系统从 SQL 声明式语义出发构建执行计划，而不是让用户拼接算子 DAG；
3. **批流统一的代价**：Batch Query 直接读 Hummock 的 SSTable，这带来了额外的一致性语义（Read-after-write on Materialized Views），但也引入了对象存储的读延迟。

---

## 一、IVM 设计哲学：流处理即物化视图增量维护

### 1.1 核心抽象

传统流处理系统（Flink DataStream API）的抽象是**算子图（Dataflow Graph）**——数据从 Source 流入，经过 Map/Filter/Aggregate 等算子变换，最终流出到 Sink。用户需要显式管理状态（`ValueState`、`MapState`），手写 `ProcessFunction`，系统只保证"数据按顺序流过算子"。

RisingWave 的抽象是**物化视图（Materialized View）**——用户用 SQL 声明"我希望持续维护的查询结果"，系统负责在每一条输入数据到达时，**增量更新**该结果集。这本质上是数据库领域的经典问题：IVM（Incremental View Maintenance）。

```
-- RisingWave 用户视角：只需声明
CREATE MATERIALIZED VIEW order_stats AS
SELECT user_id, COUNT(*), SUM(amount)
FROM orders
GROUP BY user_id;

-- 系统在内部自动维护增量更新逻辑：
-- Δoutput = F(Δinput, current_state)
```

### 1.2 Delta 语义：算子的增量计算模型

在 RisingWave 的 Streaming DAG 中，每个算子的输入输出均为**变更流（Change Stream）**，而非原始数据流。变更的类型分为三种：

| 消息类型 | 语义 |
|---------|------|
| `Insert(row)` | 新增一行 |
| `Delete(row)` | 删除一行 |
| `UpdateDelete(old) + UpdateInsert(new)` | 更新一行（拆分为删旧+插新） |

这套模型被称为 **Changelog/Delta 流**。每个算子（Hash Agg、Hash Join、Top-N）都必须实现"给定 Δinput，计算 Δoutput"的增量逻辑。

以 Hash Aggregation 为例：
```
输入: Insert(user_id=1, amount=100)
当前状态: {user_id=1: count=5, sum=400}
增量逻辑: count += 1, sum += 100
输出: UpdateDelete(user_id=1, count=5, sum=400)
      UpdateInsert(user_id=1, count=6, sum=500)
```

这与 Flink Table API 的 Retract Stream / Upsert Stream 概念相似，但 RisingWave 将其作为**唯一**的执行语义，而 Flink 在 DataStream 层面还支持无状态的纯 Append 流，两套 API 的语义时常令用户困惑。

### 1.3 与 Flink 设计哲学的本质差异

| 维度 | RisingWave | Apache Flink |
|------|-----------|--------------|
| **核心抽象** | Materialized View (IVM) | Dataflow Graph (Operator) |
| **用户接口** | SQL-first，无 DataStream API | DataStream API + Table API（两套语义） |
| **状态所有权** | 系统托管（Hummock） | 用户显式管理（State Backend） |
| **查询结果** | 持久化 MV，可 Ad-hoc 查询 | 流出到 Sink，不可回查 |
| **设计起点** | 数据库 + 流处理融合 | 批处理框架演化而来 |

---

## 二、Hummock：云原生 LSM-tree 存储引擎深度解析

这是 RisingWave 最核心的差异化技术，也是与 Flink+RocksDB 体系最根本的架构分叉点。

### 2.1 设计动机：为什么不用 RocksDB？

Flink 使用 RocksDB 作为 State Backend（即将迁移到自研的 ForSt）。RocksDB 是一个**本地磁盘上的 LSM-tree**，其核心假设是：数据就在本机 SSD 上，随机读写延迟在微秒级别。

这个假设在云环境下被打破：
- **弹性伸缩困难**：RocksDB 状态绑定在本地节点，Scale-in 时必须迁移状态数据，代价极高；
- **存储成本**：云环境中，计算节点挂载的 NVMe SSD 远比 S3 贵；
- **备份/恢复**：RocksDB Checkpoint 需要将本地数据上传到远端，是个额外的 I/O 放大操作。

Hummock 的核心思路：**直接以 S3 为 Primary Storage，LSM-tree 就构建在 S3 上**。

### 2.2 Hummock 架构：SSTable on S3

```
写路径：
  Compute Node
  └── Write Buffer (Memtable, in-memory)
       └── [Checkpoint 触发] Flush → SSTable (.sst)
            └── 上传到 S3 (Staging / L0)
                 └── Compactor Node 执行 Compaction
                      └── L1 → L2 → ... → Ln (all on S3)
```

**SSTable 结构**遵循标准 LSM-tree 格式：
- Block（默认 64KB）+ Block Index
- Bloom Filter（per SSTable，减少 False Positive 读 S3）
- 每个 KV 对携带 **Epoch** 信息（用于 MVCC，见 §三）

**层级组织**：

| 层级 | 特点 |
|------|------|
| Memtable | 内存中，Write Buffer，按 Epoch 组织 |
| L0 (Staging) | Flush 后直接上传，SSTable 之间 Key Range 可重叠 |
| L1~Ln | Compaction 后，同层 Key Range 不重叠（Leveled），或分 Tier（Tiered） |

**Compaction 策略**是 Hummock 的核心工程挑战之一：

- **Tiered Compaction**（类 Size-Tiered）：写放大小，但读放大大；适合写密集的流处理状态更新场景。
- **Leveled Compaction**：读放大小，但写放大大；适合读密集的 Ad-hoc 查询场景。

RisingWave 实际使用的是混合策略：L0 内部使用 Tiered，L0→L1 及以下使用 Leveled。这是一个针对**流处理状态访问模式**（高频点查 + 周期性范围扫描）的务实权衡。

### 2.3 Bloom Filter 布局策略

Hummock 在每个 SSTable 的粒度上维护 Bloom Filter，而非按 Level 维护全局 Bloom Filter。这意味着：
- L0 有多个 SSTable，每个都有独立 Bloom Filter，查询 L0 时需要检查所有 L0 SSTable 的 BF；
- L1 及以下每层的 SSTable 之间 Key Range 不重叠，因此只需查找对应 Key Range 的 SSTable 的 BF。

在流处理场景下，绝大多数状态访问是**点查**（如 Hash Agg 按 group key 查找当前聚合值），BF 命中率至关重要。

### 2.4 与 RocksDB 的延迟权衡

这是 Hummock 设计中最重要的 Trade-off：

| 操作 | RocksDB（本地 NVMe） | Hummock（S3） |
|------|---------------------|---------------|
| 点查（BF 命中） | ~10μs | ~1-10ms（S3 GET） |
| 点查（BF 未命中，读 SSTable） | ~100μs | ~10ms+ |
| 写入（Memtable） | ~1μs | 相同（仍在内存） |
| Checkpoint Flush | 本地落盘，ms级 | S3 PUT，100ms级 |

**结论**：Hummock 的读延迟比 RocksDB 高 1-2 个数量级。RisingWave 通过以下手段缓解：
1. **Block Cache**：在 Compute Node 本地内存中缓存热点 SSTable Block；
2. **Meta Cache**：缓存 SSTable 的 Index Block 和 Bloom Filter，避免每次读 S3；
3. **流处理的访问局部性**：大多数状态访问有较强的时间局部性（最近更新的 Key 最常被访问），Cache 命中率较高。

对于对状态读延迟极度敏感的场景（如毫秒级响应的 Streaming Join），这仍然是 Hummock 相比 RocksDB 的劣势。

---

## 三、Barrier Checkpoint：一致性机制与 Exactly-Once 保证

### 3.1 Barrier 注入机制

RisingWave 的 Checkpoint 机制借鉴了 Flink 的 Aligned Checkpoint 设计，但结合了自身的存储架构做了深度定制。

**Barrier 是一种特殊的控制消息**，由 Meta Node 周期性注入到所有 Source 节点的输入流中。Barrier 携带一个 **Epoch 号**（单调递增），在流图中随数据流向传播：

```
[Kafka Source] ──→ [Filter] ──→ [Hash Agg] ──→ [Sink]
     │                               │
  Barrier(e=100)              Barrier(e=100)
  注入                         传播到此
```

当一个算子收到所有上游的 Barrier(e=100) 之后：
1. 对齐（Aligned）：等待所有上游的 Barrier 都到达（与 Flink Aligned Checkpoint 相同）；
2. 将自身状态 Flush 到 Hummock（即将 Memtable 中 Epoch=100 的数据写入 L0 SSTable 并上传 S3）；
3. 向下游传递 Barrier(e=100)。

当所有算子都完成 Barrier 处理，Meta Node 收到所有 Sink 算子的确认后，**Checkpoint 完成**，此时 Epoch=100 对应的全局一致性快照已持久化到 S3。

### 3.2 Epoch-based MVCC in Hummock

Hummock 的每个 KV 对都携带写入时的 Epoch：

```
Key: (user_key, epoch)  → Value
Key: (user_id=1, e=98)  → {count=4, sum=300}
Key: (user_id=1, e=99)  → {count=5, sum=400}
Key: (user_id=1, e=100) → {count=6, sum=500}
```

这使得 Hummock 天然支持 **MVCC**（Multi-Version Concurrency Control）：
- 流处理读取时，使用**当前 Epoch** 的版本；
- Batch Query 读取时，使用**最近已完成 Checkpoint 的 Epoch**，保证读取到的是一致性快照；
- 过期的 Epoch 版本在 Compaction 时被清理（类似数据库的 Vacuum）。

### 3.3 与 Flink Aligned Checkpoint 的异同

| 维度 | RisingWave Barrier Checkpoint | Flink Aligned Checkpoint |
|------|-------------------------------|--------------------------|
| **Barrier 来源** | Meta Node 集中注入 | JobManager 注入 |
| **状态存储** | Hummock（S3） | RocksDB → S3（二次上传） |
| **一致性快照** | 天然是 S3 上的 SSTable 集合 | 需要将 RocksDB 状态序列化后上传 |
| **Barrier 对齐** | 需要对齐（可能引入延迟） | 同样需要对齐 |
| **Unaligned Checkpoint** | 暂不支持 | Flink 1.11+ 支持 |
| **恢复速度** | 直接从 S3 读 SSTable，无本地恢复阶段 | 需要将 S3 数据下载到本地重建 RocksDB |

**恢复速度**是 Hummock 架构的重要优势：由于 Compute Node 本身无状态，故障恢复时，新的 Compute Node 启动后直接从 S3 读取最近 Checkpoint 的 SSTable 即可，**不需要将状态数据搬移到本地**。Flink 恢复时需要从 S3 下载全量 RocksDB State，数据量大时可能需要分钟级甚至小时级。

### 3.4 Exactly-Once 保证边界

| 组件 | 保证级别 |
|------|---------|
| Source（Kafka） | At-Least-Once 摄入 + Barrier 对齐去重 → Exactly-Once |
| 内部算子状态 | Exactly-Once（Barrier + Hummock Checkpoint） |
| Sink（Kafka） | At-Least-Once（除非 Sink 支持幂等写入或事务） |
| Sink（Iceberg/JDBC） | Exactly-Once（通过 2PC / Upsert 机制） |

**重要边界**：与 Flink 相同，Exactly-Once 的端到端保证需要 Source 和 Sink 的协作。Kafka Sink 默认是 At-Least-Once；Iceberg Sink 通过 Iceberg 事务机制可实现 Exactly-Once。

---

## 四、流式算子实现：状态管理深度解析

### 4.1 Streaming Hash Aggregation

**状态结构**：每个 Aggregation 算子在 Hummock 中为每个 Group Key 维护一个 KV 对：

```
Key: (operator_id, vnode, group_key)
Value: {agg_col1: val1, agg_col2: val2, ...}
```

其中 `vnode`（Virtual Node）是 RisingWave 的一致性哈希分片标识，用于支持 Scale-out 时的状态重分布（见 §六）。

**增量更新路径**：
1. 收到 Insert(row)：按 group_key 查 Hummock（或 Block Cache）取当前聚合值；
2. 应用增量函数（count+1，sum+delta）；
3. 将新值写入 Hummock（写入 Memtable，Checkpoint 时 Flush）；
4. 向下游发送 UpdateDelete（旧聚合值）+ UpdateInsert（新聚合值）。

**优化**：对于高频更新的 Group Key，Compute Node 会在内存中维护一个 **Agg Cache**（类似 Write Buffer Aggregation），将多个增量合并后批量写入 Hummock，减少对 S3 的读写次数。

### 4.2 Streaming Hash Join（Stream-Stream Join）

这是流处理系统中状态最重的算子，也是 RisingWave 与 Flink 实现差异最大的地方。

**两侧状态存储**：

```
Left State:  Key=(operator_id, left_join_key, pk)  → left_row
Right State: Key=(operator_id, right_join_key, pk) → right_row
```

两侧状态均存储在 Hummock 中。当左侧到来一条新数据时：
1. 用 left_join_key 查 Right State，找到所有匹配的右侧行；
2. 将 left_row 写入 Left State（供未来右侧数据到来时使用）；
3. 对每个匹配的右侧行，输出 Join 结果（Insert）。

**无界 Join 的状态膨胀问题**：无时间窗口约束的 Stream-Stream Join，两侧状态都是无界增长的。RisingWave 和 Flink 都面临这个根本性问题。缓解手段：
- **Interval Join**：通过 `WHERE A.ts BETWEEN B.ts - INTERVAL '1 hour' AND B.ts + INTERVAL '1 hour'` 限制 Join 窗口；
- **Session Window Join**：基于事件时间的窗口。

基于 Hummock 的优势是：状态可以无限制地溢出到 S3，不受 Compute Node 本地内存约束；劣势是每次状态查找可能需要读 S3，延迟高于 RocksDB。

### 4.3 Watermark 与 Event Time 窗口

RisingWave 的 Watermark 机制与 Flink 类似，但实现路径不同：

- **Flink**：Watermark 是数据流中的特殊消息，由 Source 生成，随数据流传播，每个算子维护独立的 Watermark 状态。
- **RisingWave**：Watermark 与 Barrier 系统集成，Watermark 信息随 Barrier 在流图中传播，算子可以据此触发窗口计算并**清理过期状态**（通过 Hummock 的范围删除）。

窗口清理（State Eviction）是 Event Time 窗口最重要的机制，可以控制状态大小。RisingWave 通过 Watermark 推进来确定哪些窗口已经关闭，进而删除对应的 Hummock KV。

### 4.4 Top-N 算子的状态存储优化

```sql
-- 经典 Top-N 查询
SELECT * FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY category ORDER BY sales DESC) AS rn
  FROM products
) WHERE rn <= 10;
```

**Managed Top-N**（有 PARTITION BY，即分组 Top-N）：
- 状态：每个 Partition 维护一个有序集合（底层是 Hummock 的范围扫描）；
- Key: `(operator_id, partition_key, sort_key, pk)`
- 当新数据进来时，检查是否能进入 Top-N；若能，挤出末位，输出 Delete+Insert；
- 优化：在内存中维护每个 Partition 的 Top-N 结果集（热数据），仅在边界情况才访问 Hummock。

**AppendOnly Top-N**（输入为仅追加流，无 UPDATE/DELETE）：
- 可以使用更简单的数据结构，避免 Retract 消息的处理；
- 内存占用更小，吞吐更高。

---

## 五、Rescaling：弹性伸缩的工程挑战

这是流处理系统中**工程难度最高**的功能之一，也是 RisingWave 在架构设计上的核心竞争力。

### 5.1 问题本质

流处理作业的状态（Aggregation State、Join State 等）按照 Key 分布在多个 Compute Node 上。当需要扩容（从 3 个 Node 变为 5 个 Node）时，必须将部分状态从旧 Node 迁移到新 Node，同时保证作业不中断（或仅短暂暂停）。

**Flink 的做法**（至今仍是重量级操作）：
1. 触发 Savepoint（全量 Checkpoint）；
2. 停止作业；
3. 修改并行度后重新提交；
4. 从 Savepoint 恢复（从 S3/HDFS 下载状态到新节点的本地 RocksDB）；
5. 恢复时间与状态大小正相关，可能需要分钟到小时级。

### 5.2 RisingWave 的 Vnode-based Rescaling

RisingWave 使用 **Virtual Node（Vnode）** 机制解决这个问题，核心思路类似 Cassandra 的虚拟分区：

```
状态 Key 空间
     │
     ▼
Consistent Hash → Vnode (0~255, 共 256 个虚拟分区)
     │
     ▼
Vnode → Actor (实际处理单元)
     │
     ▼
Actor → Compute Node (物理节点)
```

所有状态在 Hummock 中的存储都携带 `vnode` 前缀。这意味着：
- **状态天然按 Vnode 分片**，可以任意重新分配 Vnode 到不同的 Actor/Node；
- 由于状态在 S3 上（Hummock），**状态本身不需要物理迁移**，只需要更新 Vnode→Actor 的映射关系；
- 新 Actor 启动后，直接从 S3 读取对应 Vnode 范围的 SSTable 即可。

**Rescaling 流程**：
1. Meta Node 触发 Barrier，所有当前 Epoch 的状态 Flush 到 S3；
2. 停止旧 Actor（或新建 Actor，取决于扩缩容方向）；
3. 更新 Vnode 映射表（仅是元数据操作，极快）；
4. 新 Actor 从 S3 加载对应 Vnode 的状态（可以流式预热 Block Cache）；
5. 恢复处理。

**关键优势**：步骤 3（元数据更新）是毫秒级的，步骤 4 的延迟取决于 Block Cache 预热速度，而非状态大小——因为状态已经在 S3 上，无需物理搬移。

这比 Flink 的 Savepoint 恢复快了 1-2 个数量级（尤其在大状态场景下）。

---

## 六、批流统一：Batch Query on Streaming State

### 6.1 执行路径

RisingWave 支持对物化视图执行 Ad-hoc 查询：

```sql
-- 物化视图（持续维护）
CREATE MATERIALIZED VIEW order_stats AS
SELECT user_id, SUM(amount) FROM orders GROUP BY user_id;

-- Ad-hoc 批查询（直接读取 MV 的当前状态）
SELECT * FROM order_stats WHERE user_id = 123;
```

执行路径：
```
SQL → Frontend (Parser + Planner + Optimizer)
   → 生成 Batch Physical Plan（非 Streaming Plan）
   → Batch Executor（向量化执行，Arrow 格式）
   → 读取 Hummock SSTable（使用最近完成的 Checkpoint Epoch）
   → 返回结果
```

Batch Query **不走 Streaming DAG**，而是走独立的 **Batch Executor**，后者基于 Apache Arrow 格式实现向量化执行。

### 6.2 Streaming 与 Batch 共享表达式框架

值得关注的设计点：RisingWave 的 Streaming 路径和 Batch 路径共享同一套**表达式求值框架**（Expression Evaluation）。这避免了同一 SQL 函数需要实现两遍的问题（这在 Flink 的 DataStream vs Table API 双路径中是个长期痛点）。

### 6.3 一致性语义

Batch Query 读取的是**最近完成 Checkpoint 的 Epoch** 对应的快照，而非"当前最新"的流处理状态（因为流处理状态可能有未 Flush 的 Memtable 数据）。

这意味着：**Batch Query 的结果可能落后于实时流处理状态数秒**（取决于 Checkpoint 间隔，默认 1s）。

对于需要读取"绝对最新"状态的场景，RisingWave 提供了 `SET STREAMING_PARALLELISM` 等参数来控制，但代价是更高的延迟。

### 6.4 与 StarRocks 的对比（关键差异）

作为 StarRocks 开发者，这里是最值得关注的边界：

| 维度 | StarRocks | RisingWave |
|------|-----------|-----------|
| **物化视图刷新** | 异步批量刷新（分钟级~小时级） | 增量实时维护（毫秒~秒级） |
| **MV 与基表一致性** | 最终一致（刷新间隔内有 Lag） | 每个 Checkpoint 后一致（秒级 Lag） |
| **Ad-hoc 查询引擎** | 强大的 MPP OLAP 引擎（CBO + 向量化 + Colocate Join） | 相对简单的 Batch Executor，OLAP 分析能力弱 |
| **适合场景** | 大规模 OLAP 分析（PB 级数据，复杂多维分析） | 实时流处理 + 低延迟持续查询 |
| **数据摄入方式** | 批量导入（Stream Load / Broker Load） | 从 Kafka/CDC 持续摄入 |
| **状态存储** | 列式存储（Segment Files）+ 本地磁盘 | Hummock（S3 LSM-tree）|

**定位边界**：在"实时数仓"场景下，StarRocks + Flink 的经典组合（Flink 处理实时流 → 写入 StarRocks → StarRocks 承接 OLAP 查询）中，RisingWave 可以替代 Flink 的角色，并且还能承接部分 StarRocks 上"轻量级"的实时查询（通过 MV 直接查询）。但对于大规模 OLAP 分析，StarRocks 的 MPP 引擎远强于 RisingWave 的 Batch Executor。

---

## 七、竞品深度对比

### 7.1 vs Apache Flink

| 维度 | RisingWave | Apache Flink |
|------|-----------|--------------|
| **核心模型** | IVM（SQL声明式） | Dataflow（算子命令式）|
| **状态存储** | Hummock（S3 LSM-tree，无状态Compute） | RocksDB/ForSt（本地磁盘，有状态Compute）|
| **Rescaling** | Vnode元数据重映射，秒级 | Savepoint重启，分钟~小时级 |
| **故障恢复** | 无状态恢复，秒级 | 状态下载重建，分钟级 |
| **SQL完备性** | PostgreSQL方言，SQL-first | Calcite，但Table/DataStream语义割裂 |
| **生产成熟度** | 2023年以来快速发展，用户规模远小于Flink | 超过10年历史，Apache顶级项目，生产部署极为广泛 |
| **实现语言** | Rust（内存安全，无GC停顿） | Java/Scala（JVM GC可能引入 Stop-the-World）|
| **生态** | 新兴，Connector覆盖度追赶中 | 极其丰富（数百个Connector），企业支持成熟 |
| **适用场景** | 云原生、弹性伸缩需求强、SQL优先 | 企业级复杂流处理，大状态作业，成熟生产环境 |

**Rust vs JVM 的性能差异**：在极限吞吐场景下，Rust 的无 GC 特性理论上优于 JVM（Flink 在高吞吐下可能出现 GC Pause 导致的延迟抖动）。但 Flink 经过多年优化，JVM 的 JIT 编译也相当高效，实际性能差距需要 workload-specific benchmark 才能说明。

### 7.2 vs Materialize

Materialize 和 RisingWave 是目前最接近的两个竞品：都以"SQL on Streams"为核心，都以 IVM 为设计哲学，都以 PostgreSQL 协议为接入标准。

| 维度 | RisingWave | Materialize |
|------|-----------|-------------|
| **IVM 实现基础** | 自研 Streaming DAG（Delta 流模型） | Differential Dataflow（RUST，来自TimelyDataflow生态）|
| **状态存储** | Hummock（自研，S3 LSM-tree） | PERSIST（基于S3，但架构不同） |
| **实现语言** | Rust | Rust |
| **PostgreSQL兼容** | 高度兼容 | 高度兼容 |
| **商业化** | RisingWave Cloud + 开源社区 | Materialize Cloud（主要商业产品） |
| **开源授权** | Apache 2.0 | BSL（商业限制，2年后转Apache）|
| **融资/背景** | RisingWave Labs（VC支持） | 有充分融资，美国市场为主 |

Materialize 基于 **Differential Dataflow** 的理论更为成熟（Frank McSherry 的工作），但 RisingWave 在工程实现和商业推进上更为激进，在中国市场（和亚太地区）拥有更强的生态。

---

## 八、商业化与生态

### 8.1 RisingWave Cloud

托管服务，提供：
- 全托管的 RisingWave 集群（类似 Confluent Cloud 对 Kafka 的关系）；
- 存算分离架构（Hummock on S3）使得云服务的资源调度更灵活；
- 与 AWS/GCP/Azure 的对象存储直接集成。

竞争定位：
- **vs Confluent Cloud**：Confluent 提供 Kafka + Flink（ksqlDB/Flink SQL），是流处理的重量级玩家；RisingWave 更轻量，SQL 体验更接近数据库；
- **vs Ververica Cloud**（阿里云上的 Flink 托管服务）：面向有 Flink 历史包袱的企业；RisingWave 面向新项目/云原生新用户。

### 8.2 Connector 生态现状

| 类型 | 已支持 |
|------|--------|
| **Source** | Kafka、Kinesis、Pulsar、CDC（MySQL/PG/MongoDB via Debezium）、S3（CSV/JSON/Parquet）、Iceberg |
| **Sink** | Kafka、Iceberg、Delta Lake、MySQL、PostgreSQL、Elasticsearch、ClickHouse、TiDB |
| **BI兼容** | Grafana、Metabase、Tableau（通过 PG 协议） |
| **dbt集成** | dbt-risingwave adapter（支持将 dbt model 编译为 MV）|

dbt 集成是一个重要的生态信号：dbt 用户可以用熟悉的 SQL 工作流定义实时物化视图，降低了从批处理迁移到实时处理的门槛。

---

## 总结：对 StarRocks 开发者的启示

从一个高性能 OLAP 数据库开发者的视角看 RisingWave，最有价值的技术洞察是：

1. **存算分离不只是架构时髦**：Hummock 把"状态完全放在 S3"做到了极致，使得 Rescaling 从"需要搬移数据"变成了"只需更新元数据映射"，这是一个真正的架构级突破。StarRocks 的 Shared-Nothing 架构在弹性方面的代价更高，这值得借鉴。

2. **IVM 与批量刷新 MV 的边界**：StarRocks 的异步物化视图适合"分析查询加速"场景，RisingWave 的流式 MV 适合"实时数据消费"场景。两者在 Lag 容忍度上的根本差异决定了各自的适用场景边界。

3. **Rust 的工程价值**：无 GC 停顿在高并发、低延迟的流处理场景下有实际价值。C++ 有相似的无 GC 优势，但 Rust 的所有权模型在多线程状态管理上提供了额外的安全保障，这与流处理系统大量有状态算子的特点非常契合。

4. **Barrier Checkpoint 的精妙**：用 Barrier 注入流图实现全局一致性快照，是一个优雅的分布式系统设计。它避免了"停止世界"式的全局锁，同时能保证所有算子状态的全局一致性。这个思想可以应用于任何需要在不停机情况下获取分布式系统一致性快照的场景。