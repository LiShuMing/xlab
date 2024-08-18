# 第 12 章 · Checkpoint 核心机制：Chandy-Lamport 的工业实现

## 导读

- **一句话**：本章剖析 Flink Checkpoint 的完整机制——从 Barrier 的注入、对齐到 State 的快照保存，完整追踪一次分布式快照的生命周期。
- **前置知识**：分布式系统基础概念、Chandy-Lamport 快照算法。
- **读完本章你能回答**：
  - Barrier 是什么、从哪来、怎么传播
  - Aligned Checkpoint vs Non-aligned Checkpoint 的实现差异
  - CheckpointCoordinator 如何协调完全局快照
  - 一次 Checkpoint 的时间花费在哪里

---

## 12.1 — 设计动机：流系统中的全局一致性快照

批作业的容错很简单：重跑失败的 Stage。流作业的容错很困难，因为：
- 数据源是无限的，不能重跑所有历史
- 算子内部有状态（窗口累积、中间计算结果）
- 需要保证 Exactly-once 语义——不多、不少、不重复

Flink 的答案基于 **Chandy-Lamport 分布式快照算法（1985）** 的异步屏障快照变种：

> 在 Data Stream 中注入 "Checkpoint Barrier"（屏障），这些 barrier 在 DAG 中流动，当所有算子都收到 Barrier 并各自保存了自己的状态时——一个全局一致的快照就行成了。

---

## 12.2 — CheckpointCoordinator：快照协调器源码

### 核心字段

`CheckpointCoordinator` 是 JobMaster 端的核心组件（`flink-runtime/.../checkpoint/CheckpointCoordinator.java:101`）：

```java
public class CheckpointCoordinator {
    private final Object lock = new Object();                    // 全局锁
    private final JobID job;                                     // Job ID
    private final CheckpointProperties checkpointProperties;     // checkpoint 属性
    private final Executor executor;                             // 异步执行器
    private final CheckpointsCleaner checkpointsCleaner;         // 已完成 checkpoint 清理器
    private final Collection<OperatorCoordinatorCheckpointContext> coordinatorsToCheckpoint;
    @GuardedBy("lock")
    private final Map<Long, PendingCheckpoint> pendingCheckpoints; // 待完成的 checkpoint
    private final CompletedCheckpointStore completedCheckpointStore; // 已完成 checkpoint 存储
    private final CheckpointStorageCoordinatorView checkpointStorage; // 存储视图
    private final CheckpointIDCounter checkpointIdCounter;       // ID 计数器
}
```

### 触发 Checkpoint：triggerCheckpoint()

```java
// CheckpointCoordinator.java
public CompletableFuture<CompletedCheckpoint> triggerCheckpoint(
        long timestamp, Map<String, Object> checkpointOptions) {
    synchronized (lock) {
        // 1. 生成 checkpoint ID（递增）
        long checkpointId = checkpointIdCounter.getAndIncrement();

        // 2. 创建 PendingCheckpoint（跟踪所有应答）
        PendingCheckpoint pendingCheckpoint = new PendingCheckpoint(
                job, checkpointId, timestamp, ...);

        // 3. 向所有 Source Execution 发送 triggerCheckpoint RPC
        for (Execution execution: sourceExecutions) {
            execution.triggerCheckpoint(checkpointId, timestamp, ...);
        }

        // 4. 注册超时回调
        pendingCheckpoint.setCompletionFuture(...);
    }
}
```

### 接收 Ack：receiveAcknowledgeMessage()

```java
// CheckpointCoordinator.java
public void receiveAcknowledgeMessage(AcknowledgeCheckpoint message, String taskManagerLocation) {
    synchronized (lock) {
        PendingCheckpoint pendingCheckpoint = pendingCheckpoints.get(checkpointId);
        // 记录该 Task 的状态快照
        pendingCheckpoint.acknowledgeTask(
                taskExecutionId, subtaskState, metrics);

        // 检查是否所有 Task 都 ack 了
        if (pendingCheckpoint.isFullyAcknowledged()) {
            completePendingCheckpoint(pendingCheckpoint);
        }
    }
}
```

**一次 Checkpoint 的完整生命周期**：
```
1. triggerCheckpoint() → 创建 PendingCheckpoint → 向所有 Source 发 RPC
2. Source 注入 Barrier → Barrier 沿 DAG 传播
3. 每个 Task 在 Barrier 处保存 State → 向 JM 发 Ack
4. PendingCheckpoint 收到所有 Ack → isFullyAcknowledged() = true
5. completePendingCheckpoint() → 将 checkpoint 持久化到 CompletedCheckpointStore
6. 通知所有 Task checkpoint 完成 → notifyCheckpointComplete()
```

---

## 12.3 — Checkpoint Barrier 的注入与传播

### Barrier 是什么

`CheckpointBarrier` 是 Stream 中的一个控制事件——它跟普通 Record 和 Watermark 一样在 DAG 边上传输，但它自己的补货不进行任何数据计算。

```java
// flink-runtime/.../checkpoint/CheckpointBarrier.java
public class CheckpointBarrier {
    long id;         // checkpoint 编号（全局唯一，如 checkpoint-42）
    long timestamp;  // 注入时间
    // ...
}
```

### 注入

`CheckpointCoordinator` 向所有 Source 算发送出一个 "trigger checkpoint" 信号。每个 Source 算子收到后：
1. 记录当前的 **Source 偏移量** （Kafka offset/File position）
2. 向所有**输出通道** 注入一个 `CheckpointBarrier`
3. 通知 Coordinator "我的 source state 已保存"

---

## 12.3 — Aligned Checkpoint（对齐检查点）

### 在算子处的工作

当一个算子收到 Barrier：

```
                       ┌─ 输入通道 0 ── [Barrier-42] ← 先到
  operator             │
                       └─ 输入通道 1 ── [Record] [Record] ...  ← 还没到 Barrier
```

**对齐过程**：

```
1. 通道 0 的 Barrier 先到 → 停止处理通道 0 的数据
2. 通道 1 的数据仍然照常处理，直到 Barrier 到达通道 1
3. 在此期间，通道 1 到达的剩余数据 = "barrier 前在途数据"
4. 通道 0 的 Barrier 后到达的数据 → 暂存在 InputChannel 中(被 block)
5. 两个通道的 Barrier 都到了 → 封锁所有输入 → 触发状态快照
6. 保存完状态后 → 重新放行所有 InputChannel
```

### 为什么要对齐

如果 Barrier 到达后立即保存状态——那此时通道 1 的剩余数据的计算结果就不再算了（它们属于 barrier 前的数据处理）。对齐消除了这种不一致：**所有 Barrier 前的数据都在算子状态中体现了**。

### 性能开销

对齐期间阻塞一半通道——少量数据被迫请求延迟等待。对延迟敏感的作业可能有问题（毫秒级的 accumulated idle time）。

---

## 12.4 — Non-aligned Checkpoint（未对齐检查点）

### 解决对齐的延迟问题

Non-aligned Checkpoint 的设计是：**Barrier 到达后不等待其他通道**。相反：

```
1. 通道 0 的 Barrier 先到
2. 记录 "barrier" 时通道 1 的输出缓冲中的数据→ 作为 Checkpoint 的一部分附加
3. 立即保存这个瞬时时机的完整状态（内含一些 "不可恢复的乱序数据"）
4. 恢复时间时：重新播放这些附加数据 + 重新放数据流
```

**好处**：极低延迟——不需要等对齐
**代价**：更多数据写入检查点存储（额外的"在途数据"），导致较大的 Checkpoint 规模

---

## 12.5 — CheckpointCoordinator：全局协调者视角

### 快照周期

```
CheckpointCoordinator (在 JobMaster 内)
  ├── Timer 触发：每 N ms 开启一个新的 Checkpoint
  ├── 检查上次是否还有 pending（等待完成的 Checkpoint）
  ├── 通知所有 Source 算子 "触发 checkpoint"
  ├── 各 Source 注入 Barrier
  └── 等待所有算子报告 "checkpoint completed" 
    ├── 收到全部 → Commit 至 State Storage
    ├── 部分超时 → Abort Checkpoint
    └── Commit 完后 → 清理旧的 Checkpoint 数据
```

### 全局一致性判定

Coordinator 需要确保所有 Source 和 Sink 各自保存了状态——以及所有中间算子的状态。只有当每个 Operator 组都报告完成时，这个 Checkpoint 才全局完成。

源码入口：
- `flink-runtime/.../checkpoint/CheckpointCoordinator.java`
- `flink-runtime/.../checkpoint/CheckpointBarrierHandler.java`

---

## 12.6 — Checkpoint 时间足迹

一次 Checkpoint 的 4 个阶段：

```
Timestamp 0 ms: Coordinator 触发
   → Async Barrier 注入
   → +5ms  (Barrier 传播延迟差)
   ↓
OperatorX 做好 snapshot:
   → save state to StateStorage = 50ms~500ms (取决于 state size)
   → Async snapshot to DFS
   ↓
All operators done:
   → Coordinator 提交 check
   → write CheckpointMetadataOutputStream = 10ms~50ms
Done: ~600ms total
```

主要的瓶颈在 **State 大小** 和 **存储延迟**（到 S3/HDFS 的长尾延迟）。

---

## 12.7 — 横向对比

### vs Spark Structured Streaming Checkpoint

Spark SS 的 Checkpoint 是：将 offset 写 WAL + 执行状态的倍量存储到 Luci文件。它本质上是一个 Batch 的间隔一次性完成——没有 Barrier 的概念、没有分布对齐。

Flink 更精细：**持续在线快照、异步增量保存**。

### vs MaxCompute 容错

MaxCompute 无 Checkpoint 概念——如果工作台失败，重跑 SQL 即可（数据通常在存储中）。对比 Flink 场景，MaxCompute 没有"状态"——它基于"存储是完整且一致的"假设（这份假设对数据源是 ET 化的，不必在引擎做 Checkpoint）。

---

## 12.8 — 调优与实战陷阱

### Checkpoint 超时

如果 checkpoint 时间 > checkpoint timeout → Aborted → 重试 → 永远不完成 → OOM 的恶性循环。

**THE FIX**：
- 检查 state 大小（显著减少了？）
- 检查 RocksDB 是否在 Checkpoint 时将所有 L0 文件回放（compaction 不及时导致 checkpoint 时间斩 cut）
- 增加 checkpoint timeout 或减小 checkpoint 间隔（流足够快？）

### 两种模式的选择

```java
// 普通流：对齐模式即可（毫秒级空闲）
// 延迟极低要求的流（Cep/HFT）：用未对齐
StreamExecutionEnvironment.enableCheckpointing(5000, CheckpointingMode.EXACTLY_ONCE);
// vs
StreamExecutionEnvironment.enableCheckpointing(5000, CheckpointingMode.AT_LEAST_ONCE);
```

### 增量 Checkpoint

RocksDB State Backend 支持增量 Checkpoint——只上传从上次 Checkpoint 以来变化的文件。对于大 State 来说（百万到十亿 Key），这个功能是不可或缺的。

```yaml
state.backend.incremental: true
state.backend.rocksdb.checkpoint.transfer.thread.num: 4
```

---

## 本章要点回顾

1. Barrier 是在 Data DAG 上传输的"快照时间标记"——从 Source 注入、在两侧交点处触发算子状态保存。
2. Aligned Checkpoint 通过"等所有输入的 Barrier 到齐"保证全局一致性——代价是短暂的延迟；Non-aligned 不等待，但 Checkpoint 更大。
3. CheckpointCoordinator 是全局协调者——通过周期 Timer 触发、收集完成状态、提交/放弃。
4. Checkpoint 的瓶颈在 State 大小和远程存储延迟。

## 源码导航

- CheckpointBarrier：`flink-runtime/.../checkpoint/CheckpointBarrier.java`
- CheckpointCoordinator：`flink-runtime/.../checkpoint/CheckpointCoordinator.java`
- BarrierHandler（对齐/未对齐）：`flink-runtime/.../checkpoint/CheckpointBarrierHandler.java`
- 算子侧快照：`flink-runtime/.../checkpoint/ChannelStateCheckpointWriter.java`
