# 第 27 章 · 计算引擎设计的本质追问

## 导读

- **一句话**：本章是全书的理论收官——结合 Flink/Spark/StarRocks/MaxCompute 四者经验，从第一性原理审视计算引擎的几大核心选择，回答"为什么没有最优解只有取舍"。
- **前置知识**：全书内容，尤其是 Ch05（图调度）、Ch08（Watermark/窗口）、Ch12（Checkpoint）、Ch13（State Backend）、Ch18（SQL 架构）。
- **读完本章你能回答**：
  - 为什么需要从第一性原理审视计算引擎——四代引擎各自踩过什么坑
  - 数据流模型和周期迭代模型的根本差异——深层含义不止于表面表格
  - 状态内置还是外存——CARF 法则背后的深层原因与混合方案
  - Exactly-once 的完整代价清单——何时该放弃、何时必须坚持
  - 调度模型、SQL 引擎、抽象分层的本质选择——映射到 OS 的体系结构理解
  - 引擎选型与迁移时的决策框架和常见陷阱

---

## 27.1 — 设计动机

为什么需要从第一性原理审视计算引擎？因为每一代引擎的创始人都在做同样的权衡，只是当时的硬件约束和应用需求把天平推向了不同方向。

**Flink** 诞生于流优先的信念：低延迟、状态在线、持续运行。它解决"流批共享同一引擎"，放弃的是批场景 Shuffle 效率——Record-by-Record 处理模型天然不适合全量数据重排。

**Spark** 诞生于"内存足够便宜"的时代假设：RDD 不可变 → 血缘重算 → 优雅容错。它解决"让分布式编程像本地编程一样简单"，放弃的是流场景的真正低延迟——Structured Streaming 的"微批"本质还是周期迭代。

**StarRocks** 诞生于"查询即服务"的 OLAP 需求：向量化执行 + CBO + MPP。它解决"ad-hoc 查询秒级返回"，放弃的是长时间运行的流式 ETL——算子没有"长期在线"概念，每次查询全新执行计划。

**MaxCompute** 诞生于超大规模离线处理需求：中心化调度 + 分层存储 + 多租户资源池。它解决"PB 级数据稳定可靠完成"，放弃的是交互式延迟——一个 MR Job 的调度开销可能就有数十秒。

为什么这样设计？**没有任何引擎能同时满足低延迟、高吞吐、大规模、交互式四个维度**。每个引擎在某两个维度做深，另外两个做浅。从第一性原理审视，就是要看清选择背后的不变量——计算引擎的五大本质问题：数据流模型、状态管理、一致性保证、调度策略、抽象层次。

---

## 27.2 — 数据流 vs 周期迭代：本质差异

### 27.2.1 核心差异一览

| 维度 | 数据流模型 (Flink) | 周期迭代模型 (Spark) |
|------|------------------|---------------------|
| **算子生命周期** | 长期在线 | Stage 临时存在 |
| **调度粒度** | 单 Vertex 可独立部署 | 全 Stage 完成才推进 |
| **数据交付** | Pipeline 在线推进 | Stage 边界 Shuffle |
| **反压** | 在线传播 | 阶段间不存在 |
| **容错** | Checkpoint (状态快照) | RDD 重算 (数据不可变) |

### 27.2.2 算子生命周期的深层含义

流式算子一旦启动，生命周期等同于 Job。这意味着三件事：

- **状态是驻留的**：`AbstractStreamOperator` 持有 `OperatorStateBackend` 和 `KeyedStateBackend` 两个长期引用（`<org.apache.flink.streaming.api.operators.AbstractStreamOperator:L#102>`）。代价是 GC 压力、内存溢出、State 迁移——全是长期驻留带来的工程复杂度。
- **算子可以积累"经验"**：在线模型的权重更新依赖长期驻留。Spark 算子每个 Stage 重新启动，上一次中间状态已随 RDD 消亡。
- **故障恢复语义不同**：流式算子需从 Checkpoint 恢复到精确中间状态；批式算子只需重算丢失分区。前者成本是"读快照 + 重放日志"，后者是"重算血缘链"。哪种更便宜取决于 State 大小与重算代价的比值。

### 27.2.3 调度粒度与数据交付

Flink 的 `DefaultScheduler`（`<org.apache.flink.runtime.scheduler.DefaultScheduler:L#85>`）在 Job 启动时一次性部署所有 Subtask。Spark 的 DAGScheduler 以 Stage 为粒度推进。差异的后果：

- **数据本地性**：Spark 可用延迟调度等待数据本地的 Slot；Flink 的 Eager 调度无法等待——所有算子同时运行，数据在哪算子就在哪。
- **资源利用率**：Spark 的 Stage 间隙可释放前阶段资源；Flink 所有算子同时占资源，利用率均匀但刚性。
- **反压传播**：Flink 通过 Credit 机制逐级在线传播；Spark Stage 间无反压——慢下游只是让 Shuffle 数据堆积在磁盘。

Pipeline 在线推进解决"实时性"，放弃"弹性调度"；Stage Shuffle 解决"资源弹性"，放弃"低延迟"。

### 27.2.4 容错：在哪为"不变"付出代价

Spark 让数据不变，状态可推导（重算），代价是 CPU 时间。Flink 让状态可变，数据需回放（Checkpoint + Source 重放），代价是 IO 时间。在 State 大而重算代价低的场景（图计算多轮迭代），Spark 更优；在 State 大且重算代价也高的场景（大规模窗口聚合），Flink 的 Checkpoint 更优——重算可能比读快照更慢。

### 27.2.5 没有最优解只有取舍

| 选择数据流模型时，你放弃了 | 选择周期迭代模型时，你放弃了 |
|--------------------------|----------------------------|
| 批场景 Shuffle 效率 | 流场景低延迟（Stage 边界不可逾越） |
| 资源弹性（Eager 调度占用刚性） | 长期驻留状态（每次 Stage 重新开始） |
| 简单容错（Checkpoint 远比 RDD 血缘复杂） | 在线反压（Stage 间无实时反压） |
| 声明式批优化（CBO 在流上几乎无用武之地） | 微秒级延迟（毫秒级是微批下限） |

---

## 27.3 — 状态管理的本质选择

### 27.3.1 内置 vs 外存的详细权衡

```
Engine-internal State:
  + 低延迟 (Heap <1μs, RocksDB ~10μs)
  + Exactly-once 由引擎内生保证
  + 状态与算子同生命周期，无需额外同步
  - 容量受限 (Heap 受 JVM, RocksDB 受本地磁盘, TB 级上限)
  - 跨 Job 共享困难 (State 被 Job 私有)
  - 扩缩容需 KeyGroup 重分布

External KV State (Redis / HBase / TiKV):
  + 无限容量 (分布式存储横向扩展)
  + 任意数据源共享访问
  - 跨网络延迟 (ms 级, 比本地慢 1000x)
  - Exactly-once 需外部存储协作 (2PC / 幂等写入)
  - 一致性窗口 (外部与引擎 State 可能不一致)
```

### 27.3.2 CARF 法则

- **C — Capacity**：State > ~10TB 时，本地磁盘 I/O 瓶颈和 Checkpoint 时间过长使外存成为唯一选择。
- **A — Access latency**：要求 <1ms 时网络 RTT（0.5~5ms）不可接受。Heap 亚微秒级，RocksDB 本地磁盘 ~10μs。
- **R — Repeat / share**：多 Job 共享同一份状态时，内置 State 是私有资源，外部 KV 天然支持多客户端。
- **F — Failure consistency**：Exactly-once 需求下，内置 State + Checkpoint 原子保证一致性。外存需 2PC 协调，复杂度骤增。

```java
// org.apache.flink.runtime.state.hashmap.HashMapStateBackend:L#63
public class HashMapStateBackend extends AbstractStateBackend
    implements ConfigurableStateBackend {

// org.apache.flink.state.rocksdb.EmbeddedRocksDBStateBackend:L#98
public class EmbeddedRocksDBStateBackend
    extends AbstractManagedMemoryStateBackend {
```

### 27.3.3 Flink 选择"状态内置"的深层原因

1. **延迟的物理极限**：流式算子每条记录都可能访问状态。1ms RTT = 每秒最多 1000 次状态访问，比本地内存慢三个数量级。
2. **一致性的原子性**：Checkpoint 原子性地绑定"数据处理进度"与"状态快照"。状态在外部则两个系统的事务协调成本远高于单系统。
3. **反压与流控的统一**：状态访问延迟可预测（本地）→ 反压传播延迟也可预测。外存延迟抖动直接传导为反压抖动。

### 27.3.4 外部 KV 的典型场景与混合方案

外部 KV 的典型场景：大规模共享 State（用户画像多 Job 共享）、State 即服务（推荐特征在线+离线同访）、超大规模 State（搜索索引 PB 级）。

实践最常见的混合模式：**热数据内置、冷数据外存**。Flink State 存近期窗口热数据保证低延迟，外部存储存冷数据通过 AsyncFunction 异步查询，定期通过 `TwoPhaseCommitSinkFunction` 增量同步。混合的本质是在"延迟"和"共享"之间划线——线内引擎保证，线外外部存储保证，2PC 是线上的桥梁。

---

## 27.4 — Exactly-once 的代价与选择

### 27.4.1 完整组成

```
Exactly-once =
  可重放 Source (Kafka offset / File position)
  + 幂等或事务性 Sink
  + Checkpoint (Barrier 对齐 + State 快照)
```

三个条件缺一不可。Exactly-once 的精确语义不是"每条记录恰好处理一次"——这在分布式系统中不可能保证。它是：**故障恢复后，最终结果等价于没有发生故障的情况**。

### 27.4.2 IO 开销的定量分析

开销来自两部分：
- **Barrier 传播**：每个 Checkpoint 周期，Barrier 从 Source 传播到 Sink。对齐期间算子需缓存数据（`<org.apache.flink.runtime.io.network.api.CheckpointBarrier:L#45>`），内存占用和数据滞留是真实开销。
- **State Snapshot**：HashMapStateBackend 全量序列化写入 DFS；RocksDB 增量上传 SST。State >10GB 时可能占 10~30% IO 带宽。

为什么是 10~30%？典型 1 分钟间隔、5GB State：全量 Snapshot ≈ 85MB/s；正常吞吐 300MB/s 时占约 28%。增量 CP 可降到 5~10%，但 Restore Compaction 开销增加。

### 27.4.3 端到端延迟与 At-least-once 场景

Barrier 对齐造成**反压-恢复振荡**：某分区 Barrier 延迟到达时其他分区数据被缓存。正常 <10ms，倾斜时可达数秒，State 特别大时 CP 完成可达分钟级。

| At-least-once 足够的场景 | 原因 |
|--------------------------|------|
| 近似聚合（HyperLogLog、T-Digest） | 重复计算不影响精度 |
| 幂等下游（Cassandra upsert、DynamoDB） | 写入天然去重 |
| 纯日志管道（Log → Elasticsearch） | 重复写入不影响检索 |
| 监控告警（Metrics → Alertmanager） | 去重系统过滤重复告警 |

### 27.4.4 与数据库 ACID 的类比

| 数据库 ACID | 计算引擎 Exactly-once |
|-------------|---------------------|
| Atomicity | Checkpoint 原子性 |
| Consistency | Source offset 与 State 联合一致 |
| Isolation | Barrier 对齐 = 逻辑隔离点 |
| Durability | Checkpoint 持久化到 DFS |

区别：ACID 是**单事务内**的保证，Exactly-once 是**跨故障恢复**的保证——前者解决"并发事务隔离"，后者解决"故障前后一致"。Exactly-once 是工程决策不是学术洁癖——"刚好一次"的本质是"最终结果不受 reprocess 影响"。

---

## 27.5 — 调度模型的本质

### 27.5.1 静态调度 vs 动态调度

- **静态调度**：Job 启动时确定所有 Task 部署位置，运行期间不变。Flink `DefaultScheduler`（`<org.apache.flink.runtime.scheduler.DefaultScheduler:L#85>`）。优势：部署简单、反压路径固定；劣势：无法根据运行时负载调整资源。
- **动态调度**：运行时动态调整 Task 数量和位置。Flink `AdaptiveScheduler`（`<org.apache.flink.runtime.scheduler.adaptive.AdaptiveScheduler:L#192>`）、Spark Dynamic Allocation。优势：资源利用率高；劣势：调度延迟、State 迁移开销。

流式作业选静态（长期运行需稳定资源保障），批式作业选动态（Stage 间资源需求差异大）。

### 27.5.2 资源粒度与数据本地性

| 维度 | Slot (Flink) | Container (Spark/MR on YARN) | Core 绑定 (StarRocks BE) |
|------|-------------|------------------------------|--------------------------|
| 隔离 | 内存隔离、CPU 共享 | 进程级强隔离 | CPU+内存硬绑定 |
| 启动 | 毫秒级 | 秒级 | 需预分配 |
| 适用 | 流式（内存是瓶颈） | 批式（需强隔离） | OLAP（需 CPU 亲和性） |

数据本地性上，Spark/MaxCompute 偏好"移动计算到数据"（大数据量、低计算密度）；Flink 不太在意（流式数据持续流入，"本地"是动态变化的）；StarRocks 混合策略（Scan 推送 + Compute 拉取）。

---

## 27.6 — SQL 引擎的本质

### 27.6.1 声明式 vs 命令式的边界

SQL 可嵌入命令式逻辑（UDF），但引入 UDF 后优化器推断能力下降。DataStream API 是命令式的——用户代码即最终执行计划。边界的本质是**优化器的自由度**：声明式越高优化器越强，命令式越高用户自由度越大。

### 27.6.2 优化器在什么层面做决策

1. **逻辑优化**（Rule-based）：谓词下推、列裁剪、常量折叠——总是正确的等价变换。
2. **物理优化**（Cost-based）：Join 顺序、Broadcast vs Shuffle Join——依赖数据统计，统计在流场景下可能过时。
3. **执行优化**（Runtime）：CodeGen 融合、向量化、异步 IO——不影响逻辑但极大影响性能。

为什么优化器不能总做最优决策？**成本模型是近似的**——流 SQL 的数据分布随时间变化，当前分钟最优的 Join 顺序下一分钟可能不再最优。

### 27.6.3 流 SQL vs 批 SQL 的本质差异

| 维度 | 批 SQL | 流 SQL |
|------|--------|--------|
| 时间语义 | 处理时间即查询时间 | Event Time / Processing Time 双时间 |
| 结果语义 | 一次计算完整结果 | 持续计算增量结果（Retract） |
| 窗口 | 不需要 | 必须（否则 State 无限增长） |
| Join | 全量 | Temporal / Interval Join（限制带时间谓词） |

流 SQL 引入"时间维度"让关系代数从静态快照变为动态流。Retract（撤回）是最容易出错的语义——`+[1], -[1], +[2]` 表示"之前 1 不算，现在结果是 2"。下游必须理解 Retract，否则重复计算。

---

## 27.7 — 分布式引擎 ≈ 超大虚拟多核 OS

### 27.7.1 完整映射表

| OS 概念 | 计算引擎映射 | 关键类 |
|---------|------------|--------|
| 进程 | Job (ExecutionGraph) | `<ExecutionGraph:L#81>` |
| 线程 | Task (Subtask) | `<ExecutionVertex:L#60>` |
| 虚拟内存 | MemorySegment + StateBackend | `<MemorySegment:L#70>` |
| IPC / Socket | Shuffle (RPC + Netty) | Network Stack (Ch16) |
| 调度器 | Scheduler | `<DefaultScheduler:L#85>` |
| 页故障 | BufferPool 耗尽 → 反压 | `<LocalBufferPool:L#71>` |
| 文件系统 | StateBackend (持久化) | `<HashMapStateBackend:L#63>` |
| 共享内存 | BroadcastState | BroadcastState 跨算子只读共享 |
| 互斥锁 | Barrier 对齐 | `<CheckpointBarrier:L#45>` |
| 系统调用 | RPC Gateway | `<TaskExecutor:L#203>` |
| 守护进程 | TaskExecutor | `<TaskExecutor:L#203>` |
| init 进程 | JobManager / ResourceManager | 全局协调 |
| CPU 亲和性 | Slot Sharing Group | 同 Group 部署同 Slot |
| OOM Killer | FailoverStrategy | 局部 Failover vs 全局 Restart |

### 27.7.2 映射的价值

不是学术隐喻——从体系结构理解分布式瓶颈：

- **"Context switch" = 反压传播延迟**：OS 微秒级，分布式毫秒到秒级（跨网络 + Credit 协商）。减少跳数（算子链融合）= 减少 switch。
- **"TLB miss" = KeyGroup hash miss**：OS 数十个时钟周期，RocksDB BlockCache miss 一次磁盘读（μs~ms）。优化方向相同：提高局部性。
- **"Cache coherency" = Barrier 对齐**：一致性越强，等待越长。

体系结构的优化思路可迁移：算法局部性 → State 访问局部性；缓存预热 → State 预加载；NUMA 感知 → 数据本地性调度。

---

## 27.8 — 什么是"好的抽象"

### 27.8.1 三种抽象对比

| 维度 | Spark: RDD | Flink: DataFlow + State | SQL Engine: Relation Algebra |
|------|-----------|------------------------|------------------------------|
| 核心抽象 | 不可变分区数据集 | DAG + 可变状态 | 声明式查询 + 优化器 |
| 容错 | 血缘重算 | Checkpoint 快照 | 依赖引擎 |
| 时间语义 | 无 | Event/Processing Time | 声明式窗口 |
| 用户可见控制 | 分区、缓存 | 并行度、State TTL、水位线 | 几乎没有 |

### 27.8.2 每层堵死了什么、释放了什么

**Spark RDD**：堵死低延迟流处理（不可变数据集无法在线更新 State）和细粒度状态控制；释放极简容错和高效批量操作。

**Flink DataFlow + State**：堵死声明式优化（用户拓扑无法被优化器重写）和简单执行模型；释放微秒级延迟和精细状态控制。

**SQL / Relation Algebra**：堵死命令式控制和非结构化数据处理；释放自动优化和批流统一。

好的抽象隐藏不必要细节但保证关键能力。每一层抽象都堵死了某个方向的灵活性，释放了另一个方向的生产力——设计引擎就是设计"在不同层给谁什么选择权"。

---

## 27.9 — 横向对比：四大引擎设计哲学

| 维度 | Flink | Spark | StarRocks | MaxCompute |
|------|-------|-------|-----------|------------|
| **核心信念** | 流优先，批是流的特例 | 内存优先，不可变是容错基础 | 查询优先，向量化是性能基石 | 规模优先，稳定性是第一要务 |
| **状态管理** | 内置 State Backend | RDD 血缘（无显式 State） | 无（查询无状态） | 无（Task 结束即释放） |
| **一致性** | Exactly-once (Checkpoint) | At-least-once (默认) | 快照隔离 (MPP) | 强一致 (中心化调度) |
| **调度** | Eager / Adaptive | DAG Stage 调度 | MPP 全并行 | 中心化 FIFO/Fair |
| **容错** | Checkpoint + Failover | RDD 重算 | 查询重试 | Task 重试 + 备用调度 |
| **延迟** | 毫秒~秒 | 秒~分钟 | 毫秒~秒 | 分钟~小时 |
| **资源模型** | Slot (内存隔离) | Executor (JVM 隔离) | BE (CPU+内存绑定) | Worker (Container 隔离) |

**Flink** 选择低延迟+有状态计算，放弃批 Shuffle 效率。**Spark** 选择简洁模型+优雅容错，放弃流场景真正低延迟。**StarRocks** 选择查询性能+OLAP 优化，放弃长时间有状态计算。**MaxCompute** 选择规模+稳定性，放弃交互式延迟——"数据足够大，等待是值得的"。

---

## 27.10 — 调优与实战陷阱

### 27.10.1 引擎选型决策框架

1. **延迟要求**：毫秒级 → Flink DataStream；秒级 → Flink SQL / StarRocks；分钟级+ → Spark / MaxCompute
2. **有状态？**：是（窗口/Join/CEP）→ Flink；否（ETL/映射）→ 均可
3. **数据规模**：<10TB → Flink + HashMapStateBackend；10TB~1PB → Spark/StarRocks；>1PB → MaxCompute

### 27.10.2 引擎迁移常见错误

| 迁移方向 | 最常见错误 | 根因 |
|---------|-----------|------|
| Spark → Flink | Flink 批模式替代 Spark 批处理，Shuffle 效率不如 | Flink Sort-Shuffle 不如 Tungsten Sort Shuffle |
| Spark → Flink | 忽视 State 管理，OOM 或 Checkpoint 超时 | 习惯无 State 编程，未设 TTL 和增量 CP |
| Flink → Spark | Structured Streaming 延迟从毫秒退化为秒级 | 微批 CP 间隔是延迟下限 |
| Flink → Spark | Exactly-once 不再自动保证 | Spark 依赖幂等 Sink |
| MaxCompute → Flink | PB 级离线数据常驻资源成本爆炸 | Flink 是常驻模型，不适合一次性超大规模 |
| 任意 → Flink | 低估反压，整个 DAG 被最慢算子拖垮 | 阶段性执行天然隔离慢算子 |

### 27.10.3 实战检查清单

**State 方案**：预估大小？（<1GB→HashMap, 1GB~10TB→RocksDB, >10TB→外存）；跨 Job 共享？（是→外存）；CP 间隔合理？
**Exactly-once**：下游支持幂等/事务？（不支持→At-least-once+去重）；IO 预算？（>30%→降频或增量 CP）；延迟预算？（Barrier 对齐可达秒级）
**引擎迁移**：重评延迟/吞吐/一致性三角？理解容错模型根本差异？灰度方案？

---

## 本章要点回顾

1. **数据流 + 状态 = 低延迟的代价是复杂容错；周期迭代 + 不可变数据 = 简单容错的代价是延迟。** 没有最优解只有取舍。
2. **状态内置适合 <1TB + <100ms；外部 KV 适合大 State + 放松延迟。** CARF 法则是决策四维度，混合方案是实践折中。
3. **Exactly-once IO 开销 10~30%——需判断业务能否承载。** At-least-once 在幂等下游、近似聚合、纯日志管道等场景足够。
4. **调度本质是静态 vs 动态、Slot vs Container、移动计算 vs 移动数据的三重选择。** 没有更好，只有更合适。
5. **SQL 引擎本质是声明式优化的自由度——但流 SQL 的时间维度让优化器能力大打折扣。** Retract 是最容易出错的语义。
6. **分布式引擎 ≈ 超大虚拟多核 OS。** 从 TLB miss 理解 KeyGroup 访问，从 Cache coherency 理解 Barrier 对齐。
7. **好的抽象隐藏不必要细节但保证关键能力——每层堵死一个方向，释放另一个方向。**

## 源码导航

| 主题 | 关键类 | 全限定路径 |
|------|--------|-----------|
| 流式算子基类 | `AbstractStreamOperator` | `org.apache.flink.streaming.api.operators.AbstractStreamOperator:L#102` |
| 流式任务执行 | `StreamTask` | `org.apache.flink.streaming.runtime.tasks.StreamTask:L#205` |
| 静态调度器 | `DefaultScheduler` | `org.apache.flink.runtime.scheduler.DefaultScheduler:L#85` |
| 动态调度器 | `AdaptiveScheduler` | `org.apache.flink.runtime.scheduler.adaptive.AdaptiveScheduler:L#192` |
| 执行图 | `ExecutionGraph` | `org.apache.flink.runtime.executiongraph.ExecutionGraph:L#81` |
| 执行顶点 | `ExecutionVertex` | `org.apache.flink.runtime.executiongraph.ExecutionVertex:L#60` |
| Checkpoint 协调 | `CheckpointCoordinator` | `org.apache.flink.runtime.checkpoint.CheckpointCoordinator:L#101` |
| Checkpoint Barrier | `CheckpointBarrier` | `org.apache.flink.runtime.io.network.api.CheckpointBarrier:L#45` |
| 堆内 State Backend | `HashMapStateBackend` | `org.apache.flink.runtime.state.hashmap.HashMapStateBackend:L#63` |
| RocksDB State Backend | `EmbeddedRocksDBStateBackend` | `org.apache.flink.state.rocksdb.EmbeddedRocksDBStateBackend:L#98` |
| 内存段 | `MemorySegment` | `org.apache.flink.core.memory.MemorySegment:L#70` |
| 本地 Buffer 池 | `LocalBufferPool` | `org.apache.flink.runtime.io.network.buffer.LocalBufferPool:L#71` |
| Task 执行器 | `TaskExecutor` | `org.apache.flink.runtime.taskexecutor.TaskExecutor:L#203` |

建议重新翻阅每章"源码导航"从全局视角理解各部分联结。
