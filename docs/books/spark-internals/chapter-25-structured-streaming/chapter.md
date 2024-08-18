# 第 25 章：Structured Streaming — 无限数据的有限处理

## 设计动机

批处理的世界观是"数据是有限的"。一个批处理 Job 读入完整的数据集、执行计算、写出结果——然后结束。流处理的世界观是"数据是无限的"——Kafka Topic 持续接收新数据、传感器每秒射出读数、用户不断点击——计算永远不"完成"。

Spark 对流处理的第一代方案是 **DStream**（Discretized Stream），基于 RDD 的微批处理模型。它的设计很清晰（每个 batch 是一个 RDD），但有一个致命缺陷：**DStream 不理解 SQL**。用户不能对 DStream 执行 `df.groupBy().agg()`——必须用 `reduceByKeyAndWindow` 这类低级 API。这造成了"批和流"的代码分裂：同一份业务逻辑需要写两个完全不同的版本。

Structured Streaming（Spark 2.0+）的解决方案是一个过于简洁到令人生疑的声明：**把流数据当作一个不断追加的表来处理**。用户不需要知道数据是批还是流——他们写的 SQL/DataFrame 代码在批和流两种模式下都能执行。这被称为"批流一体"（Batch-Stream Unified）。

```
同一份代码:
  df.groupBy("dept").agg(sum("salary"), avg("age"))
  
批处理模式:  读取所有 HDFS 文件 → 聚合 → 写入结果
流处理模式:  持续读取 Kafka → 每个 micro-batch 做增量聚合 → 持续写入
```

这个统一不是魔法——它是从 Catalyst 到执行引擎的一个完整的流式扩展层。

## 核心原理

### 25.1 StreamingQuery 生命周期与 MicroBatch 执行循环

Structured Streaming 的核心执行循环在 `MicroBatchExecution` 中实现。它继承自 `StreamExecution`（抽象基类），遵循以下生命周期：

```
StreamExecution 状态机:
  INITIALIZING → ACTIVE → TERMINATED
                    ↓
              RECONFIGURING (查询参数变更，如分区数)

MicroBatchExecution.runActivatedStream():
  ┌── 循环开始 ──────────────────────────────────────┐
  │                                                    │
  │ 1. 获取当前 batch 的开始 offsets                     │
  │    (从 checkpoint 恢复 或 从 source 初始化)           │
  │                                                    │
  │ 2. 查询各 Source 是否有新数据                         │
  │    → Source.getOffset / latestOffset()              │
  │                                                    │
  │ 3. if 有数据 (或需要执行无数据 batch):                  │
  │      a. constructNextBatch()                        │
  │         → 确定开始/结束 offset                       │
  │         → 替换 StreamingExecutionRelation            │
  │            (逻辑计划中的流式数据"占位符"               │
  │             → 实际的数据 scan 节点)                   │
  │      b. runBatch()                                  │
  │         → 执行逻辑计划 → 物理计划 → 分布式执行         │
  │         → 提交到 Sink                               │
  │         → 记录 commit log                           │
  │      c. finishTrigger()                             │
  │         → 更新 checkpoint (offset log + commit log)  │
  │         → 生成 StreamingQueryProgress               │
  │         → 通知 StreamingQueryListener                │
  │    else:                                            │
  │      等待 pollingDelayMs (默认 10ms)                 │
  │                                                    │
  │ 4. 检查是否 TERMINATED / RECONFIGURING              │
  │                                                    │
  └── 循环回到 1 ──────────────────────────────────────┘
```

```scala
// MicroBatchExecution: executeOneBatch 的核心逻辑
// 1. constructNextBatch: 确定 offset 范围并更新逻辑计划
if (!execCtx.isCurrentBatchConstructed) {
  execCtx.isCurrentBatchConstructed =
    constructNextBatch(execCtx, noDataBatchesEnabled)
}

// 2. runBatch: 执行 plan + sink
if (execCtx.isCurrentBatchConstructed) {
  if (currentBatchHasNewData)
    execCtx.updateStatusMessage("Processing new data")
  else
    execCtx.updateStatusMessage("No new data but cleaning up state")
  runBatch(execCtx, sparkSessionForStream)
} else {
  execCtx.updateStatusMessage("Waiting for data to arrive")
}
```

每个 batch 都生成一个新的 `LogicalPlan`，通过 `StreamingExecutionRelation` 将被替换为对应 offset 范围的实际数据扫描计划。这意味着流处理的每个 batch 都是完整的 Catalyst 优化过程——流式 batch 获得了与批处理相同的 SQL 优化能力。

### 25.2 基于 Checkpoint 的 Exactly-Once 语义

Structured Streaming 的容错性依赖一个关键的外部分量：**Checkpoint 目录**。这个目录是 HDFS（或 S3）上的一个持久化位置，包含所有"在处理第 N 个 batch 时 Spark 崩溃了，重启后怎么知道从哪里恢复"的信息：

```
Checkpoint 目录结构:
  <checkpointLocation>/
    ├── offsets/          ← OffsetSeqLog
    │     └── <batchId>   ← 每 batch 一条: 各 source 的 offset
    ├── commits/          ← CommitLog
    │     └── <batchId>   ← 每 batch 一条: 标记"该 batch 已完整提交"
    ├── state/            ← StateStore 数据 (HDFS 文件 或 RocksDB)
    │     └── <operatorId>/
    │           └── <partitionId>/
    │                 └── version-<batchId>.zip 或 RocksDB 文件
    ├── sources/          ← FileStreamSourceLog (文件系统的 purged 状态)
    └── metadata          ← StreamingQueryCheckpointMetadata (查询 UUID/Schema)
```

恢复流程很直接：

```
1. 读取 metadata → 重建 SparkSession → 验证 Schema 兼容性
2. 读取 OffsetSeqLog → 找到最后一个已写入 offset 的 batch
3. 读取 CommitLog → 找到最后一个已提交的 batch
4. 如果 lastCommittedBatch < lastOffsetBatch:
     → 重新执行 lastCommittedBatch+1 到 lastOffsetBatch 的 batch
     → 这些 batch 的 StateStore 版本可能仍然存在 → 直接使用
5. 继续执行后续 batch
```

**Exactly-once 的保证**来自两个文件系统操作之间的原子性边界：
- `CommitLog` 的写入是幂等的：每个 batch 的提交只写一次，写入完成后表示该 batch 的所有数据已持久化到 Sink
- 如果在写入 CommitLog 之前崩溃 → 重启后重放该 batch → Sink 必须支持幂等写入（如 FileStreamSink 使用 `FileCommitProtocol`）

### 25.3 Source — 流式数据入口的统一接口

`Source` trait 定义了流式数据的最基本合约：

```scala
trait Source extends SparkDataStream {
  def schema: StructType                    // 数据模式
  def getOffset: Option[Offset]            // 当前最大可用 offset
  def getBatch(start: Option[Offset], end: Offset): DataFrame  // 获取数据
  def commit(end: Offset): Unit            // 确认处理完成
}
```

关键约束：**offset 必须是单调递增的**。Spark 在每个 batch 之间记录各 Source 的 offset 到 `OffsetSeqLog`，并在重启时用这些 offset 从 Source 请求"从 start 到 end"的数据。Source 必须保证每次请求相同 offset 范围返回的数据一致——这是 exactly-once 的前提。

DSv2 的 `MicroBatchStream` 接口更丰富：

```scala
trait MicroBatchStream extends SparkDataStream {
  def latestOffset(): OffsetV2              // 最新的 offset
  def planInputPartitions(start: OffsetV2, end: OffsetV2): Array[InputPartition]
  def createReaderFactory(): PartitionReaderFactory
  def commit(end: OffsetV2): Unit
  def deserializeOffset(json: String): OffsetV2
}
```

这与 DSv2 的 `Batch.planInputPartitions()` 完全对齐——流式 Source 本质上是一个 "每个 batch 产生不同 Batch 的 DSv2 Table"。这种统一性非常优雅：**流式 Source 就是可以增量读取的 DSv2 Table**。

### 25.4 Sink — 流式输出与 Commit 协议

`Sink` 的接口同样简洁：

```scala
trait Sink {
  def addBatch(batchId: Long, data: DataFrame): Unit
}
```

`addBatch` 接收一个 batch 的 DataFrame 并将其写入外部系统。关键点：如果 `addBatch(batchId, data)` 在 batch 重放时被再次调用（因为前一次在写入 CommitLog 前崩溃），Sink 必须做出幂等的响应——输出相同的数据不产生额外的影响。

`FileStreamSink` 通过 `FileStreamSinkLog`（继承自 `CompactibleFileStreamLog`）管理已提交的文件：

```
FileStreamSink 的幂等写入:
  1. batchId=5 的 addBatch 被调用
  2. 使用 FileCommmitProtocol 写数据文件到临时目录
  3. Driver 记录 "batch-5 写了哪些文件" → 写入 FileStreamSinkLog
  4. 写入 SinkLog 后 CommitLog 被写入
  5. 如果重启后 batchId=5 需要重放:
     → 检查 FileStreamSinkLog: batch-5 已经有文件记录 → 跳过重复写入
```

`ForeachBatchSink` 提供了一个编程模型——用户在回调中接收 DataFrame 和 batchId，可以自行写入任何外部系统（JDBC、HBase、REST API 等）。

### 25.5 StateStore — 流式状态的基础设施

流处理中的关键操作（Aggregation、Deduplication、Stream-Stream Join）都需要跨 batch **记住状态**。StateStore 提供了一致的接口来管理这些状态：

```scala
// 状态管道的三个关键算子:
// 1. StateStoreRestoreExec — 从 StateStore 中读取上一 batch 的状态
// 2. (用户定义的操作) — 将当前 batch 数据与状态合并
// 3. StateStoreSaveExec  — 将更新后的状态写回 StateStore

// StateStore 的版本语义:
//   每个 batch 产生一个新版本的 StateStore
//   版本 = batchId，表示"处理完 batch N 之后的状态"
```

StateStore 存储一个 `(UnsafeRow key, UnsafeRow value)` 的键值对集合。支持三种基本操作：
- `get(key)`: 读取当前值
- `put(key, value)`: 写入新值
- `remove(key)`: 删除键值对
- `prefixScan(prefixKey)`: 范围扫描（用于 session window 合并）
- `iterator()`: 全量遍历

Spark 提供了两个 StateStore Provider：

| Provider | 存储位置 | 特性 |
|----------|---------|------|
| HDFSBackedStateStore | 内存 HashMap + HDFS 增量快照 | 快速，但受 Executor 内存限制 |
| RocksDBStateStore | 本地磁盘 (RocksDB LSM-tree) | 内存消耗低，支持列族，支持范围扫描 |

RocksDB 是生产环境的默认选择——`spark.sql.streaming.stateStore.providerClass = org.apache.spark.sql.execution.streaming.state.RocksDBStateStoreProvider`。它支持列族（column families），使得 `TransformWithState` 可以将不同类型的 state 变量（ValueState、ListState、MapState、TimerState）分别存储在独立的列族中，避免一个大的 LSM-tree 的所有操作相互竞争。

```scala
// RocksDB 的状态生命周期管理:
// UPDATING → (commit) → COMMITTED → (new batch, create new version) → ...
// UPDATING → (abort)  → ABORTED   → discard changes
// 状态机的关键是: RocksDB 使用 MVCC snapshot (stamp) 确保读的一致性
// commit 后旧的 snapshot 可以被后台 compaction/MaintenanceTask 清理
```

`RocksDBStateStoreProvider` 还实现了 `SupportsFineGrainedReplay`——允许在不同版本之间只 replay 增量的 changelog，而不是全量加载。这对检查点间隔（`spark.sql.streaming.stateStore.minDeltasForSnapshot`）的优化至关重要。

### 25.6 Watermark — 基于事件时间的延迟容忍

流处理的一个经典困境：如何保证不丢失"迟到"的数据，同时又不在内存中无限期地保留所有历史状态？

Structured Streaming 的答案是 **Watermark**：

```
事件时间 (event time):
  - 数据在源头产生的时间，由一行中的某个 timestamp 列表示
  - 注意区分 event time 与 processing time (数据进入 Spark 的时间)

Watermark 计算:
  watermark = max(event_time_seen_in_all_partitions) - watermarkDelayMs
  
  例如: watermarkDelayMs = "5 minutes"
  batch-1: 看到的 event time 范围 [10:00, 10:02]
    → max = 10:02 → watermark = 10:02 - 5min = 9:57
  batch-2: 看到的 event time 范围 [9:55, 10:04]
    → max = 10:04 → watermark = 10:04 - 5min = 9:59
  batch-3: watermark = 9:59 → state store 可以丢弃 event time < 9:59 的状态
    → 那些 9:58 的数据如果现在才到 → "too late" → 被丢弃
```

Watermark 的计算依赖于 `EventTimeWatermarkExec` 物理算子。它在每 batch 的处理任务中:
1. 使用 `EventTimeStatsAccum`（AccumulatorV2）收集当前 batch 中所有 partition 的 event time 的最大值
2. 将这些 accumulator 的值收集到 Driver → 计算全局的 event time max
3. 更新 `WatermarkTracker`：`watermark = max_event_time - delayMs`
4. Stateful 算子（如 streaming aggregation）检查 watermark 值来决定是否可以驱逐旧状态

```scala
// EventTimeWatermarkExec 中的核心:
val watermarkExpression = WatermarkSupport.watermarkExpression(
  eventTime, watermarkDelayMs, ...

// watermarkExpression 是一组条件的组合:
//   eventTime <= watermarkThreshold (state cleanup condition)
//   eventTime > watermarkThreshold  (keep processing)

// WatermarkSupport.getMaxEventTime 从 accumulator 中提取全局最大值
// watermarkMs = maxEventTime - delayThreshold (both in milliseconds)
```

**Watermark 的实际效应**：
- Aggregation：只有 event time <= watermark 的 group 可以被驱逐（下一 batch 不再维护该 group 的状态）
- Deduplication：只有 event time <= watermark 的 rows 可以被从状态中移除
- Stream-Stream Join：两侧的 watermark 分别决定各自 state 的保留范围

### 25.7 Output Mode — 三种输出语义

Output mode 控制每个 batch 向 Sink 以什么粒度输出结果：

```
Append:   只输出本 batch "新增"的行
  - 要求: 输出行永不更新（不可变）
  - 适用: 无 aggregation 的 filter/map/join (对 append-only 的流)

Complete: 输出完整结果表的全部内容
  - 每个 batch 都在 Sink 中覆盖整个结果
  - 适用: 单表 aggregation 且无 watermark

Update:   只输出自上个 batch 以来"变化"的行
  - 新增行 + 更新行 → 输出
  - 适用: 有 watermark 的 aggregation
    → 旧 group 被驱逐 → "移除旧的聚合结果"= null 变化
    → 新数据到达 → "更新聚合结果"= new_agg_value 变化
```

触发模式（Trigger）与 Output mode 正交：

```
ProcessingTime:  "每 N 秒运行一个 batch"（最常用）
AvailableNow:    "把当前可用的数据全处理完 → 然后停止"
OneTime:         "只运行一个 batch → 停止"
Continuous:      "连续执行, <1ms 延迟"（实验性, Spark 3.0+）
RealTime:        "微秒级延迟"（Spark 4.0+, 实验性）
```

`RealTimeTrigger` 是 Spark 4.0 中新增的模式，使用 `RealTimeStreamScanExec` 和低延迟的分区管理——Source 不等待所有 partition 的数据，而是"先用已有数据执行，缺的 partition 下次再做"。代价是放弃对 end offset 的先验知识——progress report 中 end offsets 是占位符。

### 25.8 流式聚合 — 增量维护聚合状态

流式聚合与非流式聚合的核心区别在于：**每个 group 的聚合状态必须在 batch 之间保持**。

```
带 Watermark 的流式聚合的物理计划:
  EventTimeWatermarkExec                    ← 计算 watermark
    └── StateStoreRestoreExec               ← 读取上一个 batch 的聚合状态
          └── StreamingAggregationExec       ← 增量聚合 (partial + final)
                ├── 当前 batch 的行
                └── 恢复的旧聚合值
              └── StateStoreSaveExec         ← 保存更新后的聚合状态到 StateStore

StateStore 中的每个 key 对应一个 group 的:
  - 当前聚合值 (e.g. sum=100, count=5)
  - 该 group 的 max_event_time

StateStoreSaveExec 在 checkpoint 中更新:
  version-5.zip:  { group_dept=Engineering → (sum=500, count=25),
                     group_dept=Sales      → (sum=300, count=15), ... }
```

**Session Window Aggregation** 是一个特别有趣的情况——窗口的边界取决于数据本身的到达时间。传统方法（Flink）需要在 window 未关闭时保持所有行、等窗口关闭后再聚合。Spark 的 `StreamingSessionWindowStateManager` 使用 `MergingSortWithSessionWindowStateIterator` 在内存中做增量合并：

```
Session Window 合并:
  1. 从 StateStore 恢复本 partition 的活跃 session windows
  2. 将当前 batch 的行按 session key + event time 排序
  3. 多路合并：旧 window + 新行 → 
     if (new_row.eventTime - existing_window.end <= gap_duration)
       → merge (扩展 window)
     else
       → 输出旧窗口, 开始新窗口
  4. 只保持活跃 session windows (> watermark) 在 StateStore 中
```

### 25.9 Stream-Stream Join — 两条流的状态交集

`StreamingSymmetricHashJoinExec` 实现了两条流之间的 join。不同于批处理的 hash join（一侧全量 build、一侧 probe），流式 join 需要两侧**都保持状态**：

```
Stream-Stream Join 的状态管理:
  对 LEFT stream:  维护 LeftStateStore (右 stream watermark 之前的状态可以丢弃)
  对 RIGHT stream: 维护 RightStateStore (左 stream watermark 之前的状态可以丢弃)

Join 流程:
  1. 当前 batch 中 LEFT stream 的每一行:
     → probe RightStateStore 看是否有匹配
     → 将左行写入 LeftStateStore
  2. 当前 batch 中 RIGHT stream 的每一行:
     → probe LeftStateStore 看是否有匹配  
     → 将右行写入 RightStateStore
  3. 根据 watermark 清理：如果 left watermark 推进 → RightStateStore + left watermark
     → 删除右 state store 中 event_time <= left_watermark 的行
```

Join 的类型限制：
- Inner join + watermark：支持且数据丢弃最小
- Left/Right outer join + watermark：支持，需要保留未匹配行直到 watermark 阈值
- Full outer join + watermark：支持但状态双倍膨胀
- 不带 watermark 的 join：不支持（因为 state 永远无法回收）

```scala
// SymmetricHashJoinStateManager 维护:
//  - keyToNumValues: key → 状态行数（每条 stream key 可能有多个匹配）
//  - keyWithIndexToValue: (key, index) → 状态行
//  - 需要支持 "eventTime <= watermark → 删除" 的范围删除
```

### 25.10 TransformWithState — Spark 4.0 的有状态算子框架

Spark 4.0 引入的 `TransformWithState` 是迄今为止 Structured Streaming 最有影响力的新 API。它将"状态管理"从一个隐藏在 Catalyst 内部的实现细节提升到用户可编程的层面：

```scala
// 用户定义状态变量:
// ValueState[T]:  单个值（类似 Map<T>）
// ListState[T]:   有序列表（类似 List<T>）
// MapState[K, V]: 键值映射（类似 Map<K, V>）
// TimerState:     定时器，支持 processing time 和 event time

// StatefulProcessor 接口:
trait StatefulProcessor[K, I, O] {
  def init(outputMode: OutputMode, timeMode: TimeMode): Unit
  def handleInputRows(
      key: K,
      inputRows: Iterator[I],
      timerValues: TimerValues,
      expiredTimerInfo: ExpiredTimerInfo): Iterator[O]
  def close(): Unit
}
```

与前几代的有状态 API（`mapGroupsWithState`、`flatMapGroupsWithState`）相比，`TransformWithState` 的关键改进：
1. **多状态变量**：一个 Processor 可以有多个 ValueState/ListState/MapState，而不是所有状态混在一个 group state 对象中
2. **TTL（Time-to-Live）**：每个 State 变量可以配置 TTL，自动执行过期清理，不需要用户手动实现
3. **Timer 独立管理**：`TimerState` 支持 event time 和 processing time 定时器，且与 ValueState/ListState 分开管理
4. **列族隔离**：在 RocksDB 中不同类型的 State 变量使用不同的列族，避免跨操作类型的 LSM-tree 竞争

```python
# PySpark 中的 TransformWithState:
from pyspark.sql.streaming.stateful_processor import StatefulProcessor

processor = StatefulProcessor(
    initialState=initial_df,
    key_encoder=str,  # key 类型
)
```

## 关键代码片段

### 示例：Watermark 追踪的完整流程

```scala
// EventTimeWatermarkExec 在每个 Task 中:
// 1. 用 Accumulator 收集 event time 的最大值
val eventTimeStatsAccum = EventTimeStatsAccum(...)
child.execute().mapPartitions { iter =>
  iter.foreach { row =>
    val eventTime = row.getLong(eventTimeColumnIndex)
    eventTimeStatsAccum.add(eventTime)  // update max/min/avg/count
  }
  ...
}

// 2. Driver 从 Accumulator 获取合并后的 stats
val stats = eventTimeStatsAccum.value
val maxEventTime = stats.max  // 本 batch 各 Task 的 event time 的全局最大值

// 3. 计算 watermark:
// watermarkMs = maxEventTime - delayThreshold
// 只有 watermarkMs > lastWatermarkMs 时才推进 watermark
```

### 示例：聚合状态的增量更新

```scala
// 流式聚合的每个 group 在 StateStore 中存储:
//   Key: group_by_columns (e.g. dept="Engineering")
//   Value: (sum, count, max_event_time_of_group)  ← 通过 UnsafeRow 编码
//
// 当新 batch 数据到达:
//   1. StateStoreRestoreExec 恢复旧值: (old_sum, old_count, old_max_eventTime)
//   2. 合并: new_sum = old_sum + batch_sum
//            new_count = old_count + batch_count
//            new_max_eventTime = max(old_max_eventTime, batch_max_eventTime)
//   3. 检查: if new_max_eventTime <= watermarkMs → 驱逐这个 group 的状态
//   4. StateStoreSaveExec 保存: (new_sum, new_count, new_max_eventTime)
```

## 硬件视角

**RocksDB 的 LSM-tree 写入放大与 Compaction I/O**：

Structured Streaming 中每个 batch 的 state commit 触发的 RocksDB compaction 是 I/O 密度最高的过程之一：

```
RocksDB MemTable flush (L0) → L1 → L2 → ... → Lmax:
  每次 commit 后 RocksDB 可能触发 flush + compaction

写入放大因子 = total_bytes_written_to_disk / new_state_bytes
典型的 streaming aggregation:
  new_state_bytes = 每 batch ~100MB (100M groups × 8 bytes each)
  compaction_io = ~1-2GB per level transition
  → 写入放大 ≈ 10-20×

在高吞吐场景下，这需要:
  - SSD 随机写 IOPS ≥ 20000
  - 如果所有 partition 同时 flush → IOPS 飙升 → 磁盘队列深度上升
  → 建议: 使用 `spark.sql.streaming.stateStore.rocksdb.compactionStyle` 调优
```

通过 NVMe SSD + 增大 RocksDB block size（如 64KB-256KB 适用于 streaming 的 scan-heavy workload），写入放大可以从 ~20× 降至 ~5×。

**StateStore 加载的磁盘网络效应**：

当 Executor 重启并被重新调度到新节点时，StateStore 的恢复需要从 HDFS checkpoint 下载 RocksDB 数据——可能每个 partition 大小在 100MB-10GB 范围。选择每次都将 snapshot 写到分布式文件系统——这带来两个维度的 I/O：
- 读放大：checkpoint snapshot 的全量加载（而非增量恢复）
- 网络竞争：多个 Executor 同时从 HDFS 拉取 state store、同时从 Kafka/Brokers 拉数据

StateStore 的 `minDeltasForSnapshot`（默认 10）控制 snapshot 创建的频率——太大意味着重放太多的增量 log（时间成本），太小意味着 snapshot 占用太多磁盘空间（空间成本）。

## AI 时代反思

Structured Streaming 与 LLM Agent 的契合度出奇地高——不是因为 LLM 能写流式处理代码（它们在这方面和其他 Spark SQL 差不多），而是因为 **Streaming 的状态监控和诊断**是一个非常适合 Agent 的领域：

```
场景: Agent 作为"Streaming Doctor"在监控一个有状态的 streaming query

Agent 的检查清单:
  1. 读取 checkpoint metadata → 确认 schema 未漂移
  2. 分析 OffsetSeqLog → 看是否某个 source offset 落后（Kafka lag 增加）
  3. 分析 CommitLog → 看 batch 处理时间递增趋势（state store 膨胀信号）
  4. 检查 rocksdb metrics:
     → numBytesCompacted / batch > 阈值 → compaction 是瓶颈
     → numSstFiles > 阈值 → 需要触发 compaction
  5. 检查 watermark 滞后:
     → maxEventTime - watermarkMs < delayMs → 暗示有 late data 还没到
     → 建议: "watermark delay 可能设置得太小了——最近 3 个 batch 中有 12% 的数据被标记为 late"
```

这个 Agent 不需要是一个完整的 "auto-tuning" 系统——它只需要做"pattern match + explain"就很有价值。很多 streaming 生产问题是配置错误导致的——watermark delay 设置不当、state TTL 太长或太短、RocksDB 参数在 streaming 场景下使用默认值——而传统监控工具（Grafana/Prometheus）告诉你"批处理时间变长了"但不告诉你"因为 state store 的 L2 compaction 在 batch 53 和 batch 54 之间触发了 ~20GB 额外 I/O"。

从 LLM 角度看，**Structured Streaming 的设计文档比代码本身更有价值**。因为 Structured Streaming 的核心——状态机、watermark propagation、checkpoint 恢复——在代码中分布在数百个文件里，但设计文档（如 Databricks 发表的 Streaming Aggregation 论文）将整个架构浓缩在几张图和几个 invariant 中。LLM 的训练数据如果包含这些设计文档，在帮助用户理解 streaming query behavior 时会准确得多。

## 源码导航

| 文件 | 关键内容 | 行号参考 |
|------|---------|---------|
| `sql/core/src/main/scala/.../runtime/StreamExecution.scala` | StreamExecution 抽象类，生命周期状态机，awaitProgressLock，deleteCheckpointOnStop | ~74 (abstract class StreamExecution), ~57 (State trait) |
| `sql/core/src/main/scala/.../runtime/MicroBatchExecution.scala` | MicroBatchExecution，runActivatedStream 主循环，executeOneBatch，constructNextBatch，runBatch，populateStartOffsets | ~59 (class), ~545 (runActivatedStream), ~557 (executeOneBatch), ~848 (constructNextBatch) |
| `sql/core/src/main/scala/.../operators/stateful/EventTimeWatermarkExec.scala` | EventTimeWatermarkExec，EventTimeStatsAccum，WatermarkSupport，watermark calculation | ~35 (EventTimeStats), ~66 (EventTimeStatsAccum) |
| `sql/core/src/main/scala/.../operators/stateful/statefulOperators.scala` | StateStoreRestoreExec (~732), StateStoreSaveExec (~800), StreamingDeduplicateExec (~1412), StreamingDeduplicateWithinWatermarkExec (~1469) | |
| `sql/core/src/main/scala/.../state/StateStore.scala` | StateStore trait，ReadStateStore，版本管理，maintenance 基础设施 | |
| `sql/core/src/main/scala/.../state/RocksDBStateStoreProvider.scala` | RocksDBStateStore，状态转换机 (UPDATING→COMMITTED/ABORTED/RELEASED)，列族管理，MVCC stamp | ~41 (class), ~46 (RocksDBStateStore) |
| `sql/core/src/main/scala/.../state/HDFSBackedStateStoreProvider.scala` | HDFSBackedStateStore，内存 HashMap 实现，增量快照 | |
| `sql/core/src/main/scala/.../checkpointing/OffsetSeqLog.scala` | OffsetSeqLog，offset 持久化，batch 级别的 offset 记录 | |
| `sql/core/src/main/scala/.../checkpointing/CommitLog.scala` | CommitLog，commit 标记，Exactly-once 的最后一道防线 | |
| `sql/core/src/main/scala/.../Source.scala` | Source trait，getOffset/getBatch/commit 合约 | ~32 (trait Source) |
| `sql/core/src/main/scala/.../Sink.scala` | Sink trait，addBatch 幂等合约 | |
| `sql/core/src/main/scala/.../sources/FileStreamSource.scala` | FileStreamSource，file listing + tracking | |
| `sql/core/src/main/scala/.../runtime/FileStreamSinkLog.scala` | FileStreamSinkLog，幂等的文件级写入确认 | |
| `sql/core/src/main/scala/.../stateful/join/StreamingSymmetricHashJoinExec.scala` | Stream-Stream Join，双状态存储，watermark 协调 | |
| `sql/core/src/main/scala/.../stateful/join/SymmetricHashJoinStateManager.scala` | SymmetricHashJoinStateManager，keyToNumValues，keyWithIndexToValue | |
| `sql/core/src/main/scala/.../stateful/transformwithstate/TransformWithStateExec.scala` | TransformWithStateExec (Spark 4.0)，多状态变量，TTL，TimerState | |
