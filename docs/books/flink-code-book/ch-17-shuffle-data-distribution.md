# 第 17 章 · Shuffle 与数据分发策略

## 导读

- **一句话**：本章剖析 Flink 的各种数据分发模式——keyBy、broadcast、rescale、global 等，以及 Hybrid Shuffle 和 Tiered Storage 的现代分发设计，覆盖从 Partitioner 选路到磁盘落盘的完整链路。
- **前置知识**：第 13 章 KeyGroup 与状态分片、第 16 章 ResultPartition。
- **读完本章你能回答**：
  - 8 种分区策略分别怎么选 Channel、哪个场景用哪个
  - KeyBy 的两阶段 hash 映射如何保证 Rescale 安全
  - Hybrid Shuffle 为什么能把内存和磁盘统一为收发层
  - Tiered Storage 在 Memory / Disk / Remote 三层之间如何降级
  - Sort-Merge Blocking Shuffle 如何减少小文件风暴

---

## 17.1 — 设计动机

### 为什么 Flink 需要多种分区策略

流式计算中，数据从上游算子到下游算子的传递路径就是"Shuffle"——它决定了每条记录走向哪个下游 subtask。Flink 没有采用 Spark 那种"一种 Shuffle 实现走天下"的方式，而是设计了 8 种内置分区策略，原因在于**流批一体**场景下对延迟、吞吐和语义的差异化需求：

1. **Forward**：Operator Chain 内部，零网络开销——流作业的默认选择。
2. **KeyBy**：保证相同 key 落到同一 subtask——状态一致性的前提。
3. **Rebalance / Rescale**：负载均衡——前者全量轮询，后者局部轮询，网络开销差异巨大。
4. **Broadcast**：维度表关联——每条数据复制到所有下游。
5. **Global**：集中式处理——所有数据汇聚到 subtask 0。
6. **Shuffle**：随机分发——不保证 key 语义的均匀散布。
7. **Custom**：用户自定义分区函数——满足业务特殊路由。

### 为什么这样设计：流批一体下 Partition 和 Shuffle 的设计差异

流批一体的核心矛盾是：**流式要求低延迟（PIPELINED），批式要求大吞吐（BLOCKING）**。

- 流模式下，数据边产边消费，上下游必须同时调度（`MUST_BE_PIPELINED`），任何中间落盘都是多余延迟。
- 批模式下，数据全量产出后才消费（`BLOCKING`），必须落盘以解耦上下游生命周期。

Flink 放弃了"要么全内存、要么全磁盘"的二选一，引入 `HYBRID_FULL` 和 `HYBRID_SELECTIVE`——能内存先内存，不够再写盘，下游可以随时消费已产出的数据。这解决了批作业内存不够、流作业延迟过高的两难，放弃的是实现复杂度——Hybrid Shuffle 的状态机比纯 PIPELINED 复杂得多。

在分区策略层面，`isPointwise()` 标志区分了"一对一/多对少"与"全对全"的边连接模式：`ForwardPartitioner` 和 `RescalePartitioner` 是 `POINTWISE`，`KeyBy`、`Rebalance` 等是 `ALL_TO_ALL`。这个标志在 `StreamingJobGraphGenerator` 中直接决定了 `DistributionPattern`——进而影响调度器如何分配 TaskSlot。

---

## 17.2 — 核心数据结构

### ChannelSelector 接口与 StreamPartitioner 抽象类

一切分区策略的起点是 `ChannelSelector`——它回答唯一的问题：**这条记录该发到哪个 logical channel？**

```java
// org.apache.flink.runtime.io.network.api.writer.ChannelSelector:L28
public interface ChannelSelector<T extends IOReadableWritable> {
    void setup(int numberOfChannels);
    int selectChannel(T record);
    boolean isBroadcast();
}
```

`StreamPartitioner` 在此基础上增加了流式场景需要的语义：`SubtaskStateMapper getDownstreamSubtaskStateMapper()` 解决 Rescale 时 in-flight 数据的映射问题，`boolean isPointwise()` 决定 POINTWISE vs ALL_TO_ALL 连接模式。

`SubtaskStateMapper` 的五种策略——`ARBITRARY`（任意分配）、`ROUND_ROBIN`（轮询）、`RANGE`（范围映射）、`FIRST`（只映射到 subtask 0）、`FULL`（全量广播+下游过滤）——对应不同分区策略在并行度变化时的状态恢复行为。

### 8 种分区策略一览

| 策略 | selectChannel 逻辑 | isPointwise | SubtaskStateMapper | 典型场景 |
|------|-------------------|-------------|-------------------|---------|
| **Forward** | return 0 | true | UNSUPPORTED | Operator Chain |
| **KeyBy** | assignKeyToParallelOperator(key, maxP, n) | false | RANGE | Aggregation/Join |
| **Rebalance** | (next+1) % n，随机起步 | false | ROUND_ROBIN | 负载均衡 |
| **Rescale** | ++next % n | true | UNSUPPORTED | 同 TM 重均衡 |
| **Broadcast** | 抛异常（RecordWriter 直接写全部 channel） | false | UNSUPPORTED | 维度表 |
| **Global** | return 0 | false | FIRST | 集中处理 |
| **Shuffle** | random.nextInt(n) | false | ROUND_ROBIN | 随机散布 |
| **Custom** | partitioner.partition(key, n) | false | FULL | 业务路由 |

关键代码引用：

```java
// KeyBy 的核心路由：<KeyGroupStreamPartitioner:L55>
return KeyGroupRangeAssignment.assignKeyToParallelOperator(key, maxParallelism, numberOfChannels);

// Rebalance 的随机起步：<RebalancePartitioner:L40>
nextChannelToSendTo = ThreadLocalRandom.current().nextInt(numberOfChannels);

// Rescale 的 POINTWISE 标志：<RescalePartitioner:L80>
public boolean isPointwise() { return true; }

// Custom 的 FULL 映射（Rescale 时全量广播+过滤）：<CustomPartitionerWrapper:L63>
public SubtaskStateMapper getDownstreamSubtaskStateMapper() { return SubtaskStateMapper.FULL; }
```

**为什么 CustomPartitioner 禁用 Unaligned Checkpoint？** 因为 Unaligned Checkpoint 依赖框架知道 in-flight 数据属于哪个 subtask，而自定义分区函数的路由逻辑框架不可推断——无法保证恢复后数据路由一致。

### ResultPartition 类型枚举

分区策略决定数据"怎么走"，ResultPartition 类型决定数据"怎么存"。二者正交组合：

| 类型 | 消费约束 | 可重消费 | 释放方 | 典型场景 |
|------|---------|---------|-------|---------|
| `PIPELINED` | MUST_BE_PIPELINED | 否 | UPSTREAM | 流式无限流 |
| `PIPELINED_BOUNDED` | MUST_BE_PIPELINED | 否 | UPSTREAM | 流式有限流 |
| `PIPELINED_APPROXIMATE` | CAN_BE_PIPELINED | 否 | UPSTREAM | 近似本地恢复 |
| `BLOCKING` | BLOCKING | 是 | SCHEDULER | 批作业默认 |
| `BLOCKING_PERSISTENT` | BLOCKING | 是 | SCHEDULER | 持久化中间结果 |
| `HYBRID_FULL` | CAN_BE_PIPELINED | 是 | SCHEDULER | 批作业混合模式 |
| `HYBRID_SELECTIVE` | CAN_BE_PIPELINED | 否 | SCHEDULER | 流作业混合模式 |

`ConsumingConstraint` 是最核心的区分维度——`BLOCKING` 表示下游必须等上游全部完成，`MUST_BE_PIPELINED` 表示上下游必须同时调度，`CAN_BE_PIPELINED` 表示下游可以随时消费已产出数据。`HYBRID_FULL` 的 `isReconsumable=true` 使其在 failover 时无需重新计算上游。

### StreamingJobGraphGenerator 中分区策略如何决定 Edge 模式

```java
// <StreamingJobGraphGenerator:L1609>
if (partitioner.isPointwise()) {
    jobEdge = downStreamVertex.connectNewDataSetAsInput(
            headVertex, DistributionPattern.POINTWISE, resultPartitionType, ...);
} else {
    jobEdge = downStreamVertex.connectNewDataSetAsInput(
            headVertex, DistributionPattern.ALL_TO_ALL, resultPartitionType, ...);
}
```

ResultPartitionType 由 `getResultPartitionType()` 决定——当 edge 的 exchange mode 为 `UNDEFINED` 时，由全局 `StreamExchangeMode` 回退：`ALL_EDGES_PIPELINED` → PIPELINED_BOUNDED，`ALL_EDGES_BLOCKING` → BLOCKING，`ALL_EDGES_HYBRID_FULL` → HYBRID_FULL。

---

## 17.3 — 关键流程走读

### KeyBy 的两阶段分区完整走读

KeyBy 不是简单的 `hash(key) % parallelism`。它通过 KeyGroup 中间层实现 Rescale 安全——改并行度不需要重分布状态。

**阶段一：Key → KeyGroup**

```java
// <KeyGroupRangeAssignment:L63><L76>
public static int assignToKeyGroup(Object key, int maxParallelism) {
    return MathUtils.murmurHash(key.hashCode()) % maxParallelism;
}
```

`murmurHash` 对 Java `hashCode()` 做二次散列，消除 JDK 原生 hash 的分布不均（如 String 的 31x 多项式在低比特位聚集）。

**阶段二：KeyGroup → Subtask**

```java
// <KeyGroupRangeAssignment:L124>
public static int computeOperatorIndexForKeyGroup(
        int maxParallelism, int parallelism, int keyGroupId) {
    return keyGroupId * parallelism / maxParallelism;
}
```

整数除法保证了：连续 KeyGroup 落到同一 subtask（Range 分区，非 hash 取模）；并行度变化时 KeyGroup 只做边界迁移；只要 maxParallelism 不变，同一 key 永远映射到同一 KeyGroup。

**完整数据流**：

```
Record → KeySelector.getKey() → key.hashCode() → murmurHash(keyHash)
       → keyGroupId = murmurHash % maxParallelism
       → operatorIndex = keyGroupId * parallelism / maxParallelism
       → subpartitionIndex = operatorIndex
       → RecordWriter 写入对应的 ResultSubpartition
```

### Rescale 与 Rebalance 的区别和使用场景

| 维度 | Rebalance | Rescale |
|------|-----------|---------|
| 连接模式 | ALL_TO_ALL | POINTWISE |
| 网络连接数 | upstream x downstream | max(upstream, downstream) |
| 负载均衡效果 | 全局最优 | 局部最优 |
| Rescale 安全 | ROUND_ROBIN | UNSUPPORTED |
| 典型场景 | 数据源倾斜时重分布 | 同 TM 内 map → filter |

**为什么 Rescale 不支持 Rescale 安全映射？** POINTWISE 连接下上游只认识部分下游，并行度变化时对应关系完全重建，无法做增量映射。

### Hybrid Shuffle 的完整数据流走读

Hybrid Shuffle 有两种变体：`HYBRID_FULL`（可重消费）和 `HYBRID_SELECTIVE`（不可重消费）。核心思想：**数据先写 Memory Tier，不够再溢写 Disk Tier，下游随时可消费已产出数据。**

**写入流程**：

```
RecordWriter.emit()
  → TieredResultPartition.emitRecord()
    → TieredStorageProducerClient.write()
      → BufferAccumulator.receive() → 累积到 Buffer 后回调
        → TierProducerAgent[0] (Memory).tryStartNewSegment() + write()
          → 如果 Memory Tier 拒绝（内存不足）
            → TierProducerAgent[1] (Disk).tryStartNewSegment() + write()
```

`TieredStorageProducerClient` 维护每个 subpartition 当前写入的 tier agent（`currentSubpartitionTierAgent`），优先写高优先级 Tier。当高优先级 Tier 返回 `write() = false`，自动降级。

**读取流程**：下游 InputChannel 通过 `TieredStorageConsumerClient` 按优先级查找——Memory Tier 直接读内存 buffer；Disk Tier 通过 `PartitionFileReader` 按需读本地文件；Remote Tier 通过 Netty 从远端拉取。消费端无需知道数据在哪个 Tier。

### Tiered Storage 的写入和读取流程

Tiered Storage 通过 `TierFactoryInitializer` 组装 Tier 链：

```java
// <TierFactoryInitializer:L69>
List<TierFactory> tierFactories = new ArrayList<>();
tierFactories.add(createMemoryTierFactory(configuration));   // Tier 0: 内存
tierFactories.add(createDiskTierFactory(configuration));     // Tier 1: 本地磁盘
if (remoteStoragePath != null) {
    tierFactories.add(createRemoteTierFactory(configuration)); // Tier 2: 远端 DFS
}
```

三层语义：Memory Tier（BufferPool 直接持有，延迟最低）、Disk Tier（本地 SSD/HDD，`ProducerMergedPartitionFileWriter` 合并写入）、Remote Tier（远端 DFS，需配置 `NETWORK_HYBRID_SHUFFLE_REMOTE_STORAGE_BASE_PATH`）。

写入时的 Buffer 累积器分两种：`HashBufferAccumulator`（按 subpartition 累积，适合 KeyBy）和 `SortBufferAccumulator`（先排序再归并写，适合批作业减少随机 IO）。

### Sort-Merge Blocking Shuffle（FLIP-148）的流程

`SortMergeResultPartition` 是 BLOCKING 类型的高性能实现。数据先写入 `DataBuffer`（默认 8MB），满后按 subpartition index 排序并顺序写磁盘（`PartitionedFile`），同时生成索引文件。

读取时 `SortMergeResultPartitionReadScheduler` 根据索引文件定位数据区域，使用 `BatchShuffleReadBufferPool` 异步预读，合并多个 IO 请求为大的顺序读。

**为什么这样设计**：传统 `BoundedBlockingResultPartition` 为每个 subpartition 创建独立文件——subpartition 数量大时产生小文件风暴。SortMerge 方案将所有 subpartition 合并到少量大文件，通过索引做路由，大幅减少文件数和随机 IO。放弃的是写入时的一次排序开销——对批作业，排序代价远小于 IO 优化收益。

---

## 17.4 — 横向对比（Spark / StarRocks / MaxCompute）

### vs Spark Shuffle

| 维度 | Flink | Spark |
|------|-------|-------|
| **Shuffle 种类** | PIPELINED / BLOCKING / HYBRID | Sort-based / Tungsten-sort / Push-based |
| **信息追踪** | JobMaster 持有 Partition 状态 | MapOutputTracker（独立 RPC） |
| **反压机制** | 信用模型（Credit-based），per-subpartition 精细控制 | TCP buffer + fetch failed 重试，粗放 |
| **Tiered Storage** | Hybrid + Tiered 框架（Memory/Disk/Remote） | Spark 3.2+ Push-based Shuffle（Magnet） |
| **内存管理** | 固定 BufferPool + 溢写 | Tungsten 内存页 + Unsafe 排序 |

**关键差异**：Spark Shuffle 是 Stage 刚性切分——上游全部完成，下游才开始。Flink 的 `HYBRID` 允许上下游部分重叠。Push-based Shuffle（Magnet）是 Spark 对 Hybrid 思路的回应，但 Merge 服务是独立集群组件，而 Flink 复用 TaskManager 的 Netty 服务。

### vs StarRocks Exchange

| 维度 | Flink | StarRocks |
|------|-------|-----------|
| **数据传输** | Netty TCP 直连 | Exchange Service (BRPC) |
| **分区策略** | 8 种 StreamPartitioner | Hash / Broadcast / Bucket / Round-Robin |
| **压缩** | 可选（BLOCKING/HYBRID 支持） | 默认 LZ4/ZSTD |
| **多表物化** | 不支持 | Exchange 复用（同一 Scan 输出到多个 Join） |

StarRocks Exchange 更注重 MPP 场景下的数据本地性——Build 侧广播后 Probe 侧直接读本地副本。Flink 没有这种"多消费者共享同一 ResultPartition"的机制。

### vs MaxCompute Shuffle

| 维度 | Flink | MaxCompute |
|------|-------|------------|
| **Shuffle 粒度** | Operator 间（Edge 级别） | Stage 间（DAG 间级别） |
| **数据持久化** | 本地磁盘 / Hybrid Tiered | 分布式文件系统 |
| **调度耦合** | 上下游可同时调度 | 上游 Stage 完成后才调度 |
| **容错** | Checkpoint + ResultPartition 重放 | Stage 级别重跑 |

MaxCompute Shuffle 本质是 DAG 间的持久化中间表——天然支持 TB 级 Shuffle 和 Stage 级容错，但每个 Stage 边界都是完整的 DFS 写+读，延迟高。Flink 通过 Tiered Storage 的 Remote Tier 模拟类似能力，但 Memory/Disk Tier 使小 Shuffle 避免 DFS 开销。

---

## 17.5 — 调优与实战陷阱

### keyBy 数据倾斜的定位和解决

**症状**：某个 subtask 处理速度远慢于其他，反压集中，Checkpoint 耗时增长。

**定位**：Flink Web UI 查看 BackPressure 和 `numRecordsIn` 分布；用 `KeyGroupRangeAssignment.computeKeyGroupRangeForOperatorIndex()` 计算各 subtask 承载的 KeyGroup 范围确认倾斜。

**解决方案**：
- **提高 maxParallelism**：KeyGroup 数增加后热点 key 更细粒度分散（如 128 → 4096）。
- **Local-Global Aggregation**：先本地预聚合再 keyBy 全局聚合——类似 Spark Combine。
- **加盐拆分**：对热点 key 加随机前缀拆成 N 个 sub-key，聚合后二次聚合。
- **Rebalance 替代 KeyBy**：若业务不要求 key 局部性，直接均匀分发。

### Hybrid Shuffle 内存配置

| 配置项 | 作用 | 默认值 |
|-------|------|-------|
| `taskmanager.network.memory.fraction` | Network BufferPool 占 TM 堆外比例 | 0.1 |
| `taskmanager.network.memory.max` | BufferPool 最大值 | 1GB |
| `taskmanager.network.memory.buffers-per-subpartition` | 每 subpartition 缓冲区数 | 2 |

**陷阱**：subpartition 数 = upstream x downstream 很大时（如 100 x 200 = 20000），仅 2 buffer/subpartition 就需 1.25GB。不够则频繁溢写 Disk Tier，吞吐下降。**解法**：调大 `network.memory.max` 或减小并行度。

### 网络缓冲区不足导致反压

**症状**：日志出现 `Insufficient number of network buffers`，全部 subtask 高反压。

**根因**：BufferPool 耗尽。所需 buffer 数 ≈ subpartition 数 x (buffers-per-subpartition + 1) + input channel 数 x (floating-buffers-per-gate + 1)。当需求超过总量，死锁。

**解法**：增大 `network.memory.max`，或调低 `buffers-per-subpartition`（牺牲吞吐换内存）。

### 批作业中 Blocking Shuffle 的磁盘 IO 瓶颈

**症状**：批作业运行远超预期，磁盘 IO 100%，CPU 利用率低。

**根因**：`BoundedBlockingResultPartition` 每个subpartition 一个文件——大量小文件导致 IO 散布和磁头寻道。

**解法**：
- **启用 SortMergeResultPartition**：`taskmanager.network.sort-shuffle.min-parallelism=4`，合并 subpartition 到少量大文件。
- **启用压缩**：`taskmanager.network.compression.enabled=true`（仅 BLOCKING/HYBRID 支持）。
- **切换到 Hybrid Shuffle**：`execution.batch-shuffle-mode=ALL_EXCHANGES_HYBRID_FULL`，Memory Tier 吸收热数据。

---

## 本章要点回顾

1. 8 种分区策略通过 `ChannelSelector.selectChannel()` 决定每条记录的下游 channel——`isPointwise()` 标志决定 POINTWISE vs ALL_TO_ALL 连接模式。
2. KeyBy 不是简单取模，而是 `murmurHash(key) → KeyGroup → operatorIndex` 两阶段映射——KeyGroup 中间层保证 Rescale 安全。
3. Rescale vs Rebalance 的本质差异在网络拓扑：Rescale 是局部轮询（POINTWISE），Rebalance 是全量轮询（ALL_TO_ALL）。
4. ResultPartitionType 覆盖 PIPELINED / BLOCKING / HYBRID 三大类——`ConsumingConstraint` 决定调度耦合度。
5. Hybrid Shuffle 通过 Tiered Storage 将 Memory / Disk / Remote 三层统一在 `TieredResultPartition` 中——优先写内存，不足自动降级。
6. SortMerge Blocking Shuffle 通过排序合并写入减少小文件——以排序开销换取读取时的顺序 IO。
7. 横向对比：Spark Shuffle 是 Stage 刚性切分，StarRocks Exchange 追求数据本地性，MaxCompute Shuffle 基于 DFS 中间表——Flink Hybrid Shuffle 在延迟和吞吐间取中间点。

## 源码导航

| 模块 | 关键类 | 路径 |
|------|--------|------|
| 分区接口 | `ChannelSelector` | `flink-runtime/.../io/network/api/writer/ChannelSelector.java` |
| 分区抽象 | `StreamPartitioner` | `flink-runtime/.../streaming/runtime/partitioner/StreamPartitioner.java` |
| Forward | `ForwardPartitioner` | `flink-runtime/.../streaming/runtime/partitioner/ForwardPartitioner.java` |
| KeyBy | `KeyGroupStreamPartitioner` | `flink-runtime/.../streaming/runtime/partitioner/KeyGroupStreamPartitioner.java` |
| Rebalance | `RebalancePartitioner` | `flink-runtime/.../streaming/runtime/partitioner/RebalancePartitioner.java` |
| Rescale | `RescalePartitioner` | `flink-runtime/.../streaming/runtime/partitioner/RescalePartitioner.java` |
| Broadcast | `BroadcastPartitioner` | `flink-runtime/.../streaming/runtime/partitioner/BroadcastPartitioner.java` |
| Global | `GlobalPartitioner` | `flink-runtime/.../streaming/runtime/partitioner/GlobalPartitioner.java` |
| Shuffle | `ShufflePartitioner` | `flink-runtime/.../streaming/runtime/partitioner/ShufflePartitioner.java` |
| Custom | `CustomPartitionerWrapper` | `flink-runtime/.../streaming/runtime/partitioner/CustomPartitionerWrapper.java` |
| KeyGroup 映射 | `KeyGroupRangeAssignment` | `flink-runtime/.../state/KeyGroupRangeAssignment.java` |
| MurmurHash | `MathUtils` | `flink-core/.../util/MathUtils.java` |
| 分区类型 | `ResultPartitionType` | `flink-runtime/.../io/network/partition/ResultPartitionType.java` |
| Rescale 映射 | `SubtaskStateMapper` | `flink-runtime/.../io/network/api/writer/SubtaskStateMapper.java` |
| JobGraph 生成 | `StreamingJobGraphGenerator` | `flink-runtime/.../streaming/api/graph/StreamingJobGraphGenerator.java` |
| Hybrid Tiered | `TieredResultPartition` | `flink-runtime/.../io/network/partition/hybrid/tiered/shuffle/TieredResultPartition.java` |
| Tier 初始化 | `TierFactoryInitializer` | `flink-runtime/.../io/network/partition/hybrid/tiered/shuffle/TierFactoryInitializer.java` |
| Producer Client | `TieredStorageProducerClient` | `flink-runtime/.../io/network/partition/hybrid/tiered/storage/TieredStorageProducerClient.java` |
| SortMerge | `SortMergeResultPartition` | `flink-runtime/.../io/network/partition/SortMergeResultPartition.java` |
| Pipelined | `PipelinedResultPartition` | `flink-runtime/.../io/network/partition/PipelinedResultPartition.java` |
| Blocking | `BoundedBlockingResultPartition` | `flink-runtime/.../io/network/partition/BoundedBlockingResultPartition.java` |
