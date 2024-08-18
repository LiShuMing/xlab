# 第 23 章 · Source / Sink 的设计演化

## 导读

- **一句话**：本章追溯 Flink Source 和 Sink API 从 v1 到 v2 的演进——理解为什么 FLIP-27 重新设计了 Source，FLIP-143/191 重新设计了 Sink。
- **前置知识**：第 1 章提交流程、第 10 章 StreamTask。
- **读完本章你能回答**：
  - `SourceFunction` (v1) 的 4 个设计缺陷
  - `SplitEnumerator` + `SourceReader` 的分工与协作
  - `SinkWriter` + `Committer` 的两阶段提交如何保证 Exactly-once
  - 流和批的 Source 怎么共用同一套 SPI
  - SourceReader 内部线程模型如何避免阻塞 Mailbox

---

## 23.1 — 设计动机

### SourceFunction(v1)：同步时代的限制

`org.apache.flink.streaming.api.functions.source.legacy.SourceFunction<T>` 是 Flink 最早的 Source 抽象：

```java
// SourceFunction.java:L103
public interface SourceFunction<T> extends Function, Serializable {
    void run(SourceContext<T> ctx) throws Exception;
    void cancel();
}
```

`SourceContext` 内部持有 checkpoint 锁（`getCheckpointLock()`），所有状态更新和 `collect()` 必须包裹在 `synchronized(ctx.getCheckpointLock())` 块中。四个根本问题：

1. **单线程模型**：一个 Source 对应一个线程，checkpoint 锁跟读取锁共享 → 相互阻塞。
2. **不支持批量读**：每次只读单条 record，无法构建 scan batch（向量化）。
3. **Split 管理耦合**：Split 分配逻辑塞在 SourceFunction 实现里，无法动态重新分配。
4. **水印生成分离**：Timestamp 和 Watermark 在 SourceFunction 外部独立生成，容易不一致。

为什么这样设计——SourceFunction 诞生于 Flink 早期，那时只需对接简单消息队列，单线程 + checkpoint 锁是最直接的方案。放弃的替代方案是异步 IO 模型（后来被 v2 采纳），因为在 1.0 时代异步框架的复杂度高于收益。

---

## 23.2 — 核心数据结构

### 23.2.1 Source 接口（v2 顶层入口）

```java
// Source.java:L37
@Public
public interface Source<T, SplitT extends SourceSplit, EnumChkT>
        extends SourceReaderFactory<T, SplitT> {
    Boundedness getBoundedness();
    SplitEnumerator<SplitT, EnumChkT> createEnumerator(SplitEnumeratorContext<SplitT> enumContext);
    SplitEnumerator<SplitT, EnumChkT> restoreEnumerator(
            SplitEnumeratorContext<SplitT> enumContext, EnumChkT checkpoint);
    SimpleVersionedSerializer<SplitT> getSplitSerializer();
    SimpleVersionedSerializer<EnumChkT> getEnumeratorCheckpointSerializer();
    default Set<? extends WatermarkDeclaration> declareWatermarks() {
        return Collections.emptySet();
    }
}
```

三个泛型参数：`T` 是产出记录类型，`SplitT` 是 Split 类型，`EnumChkT` 是 Enumerator 的 checkpoint 状态类型。`Boundedness` 取 `BOUNDED` 或 `CONTINUOUS_UNBOUNDED`，同一 Source 实现服务流和批。

### 23.2.2 SplitEnumerator

运行在 JobMaster 端，全局管理所有 Split 并分配到 SourceReader：

```java
// SplitEnumerator.java:L34
public interface SplitEnumerator<SplitT extends SourceSplit, CheckpointT>
        extends AutoCloseable, CheckpointListener {
    void start();
    void handleSplitRequest(int subtaskId, @Nullable String requesterHostname);
    void addSplitsBack(List<SplitT> splits, int subtaskId);
    void addReader(int subtaskId);
    CheckpointT snapshotState(long checkpointId);
    void close();
    default void notifyCheckpointComplete(long checkpointId) {}
    default void handleSourceEvent(int subtaskId, SourceEvent sourceEvent) {}
}
```

核心方法：`handleSplitRequest` 处理 Reader 的 Pull 请求（`requesterHostname` 用于本地化调度）；`addSplitsBack` 在 Reader 失败后回收未消费 Split；`handleSourceEvent` 是自定义事件扩展管道。SplitEnumeratorContext 提供 `assignSplits()`、`signalNoMoreSplits()`、`sendEventToSourceReader()` 以及 `callAsync()`（异步执行 Split 发现后回调 coordinator 线程）。

### 23.2.3 SourceReader

每个 Subtask 一个，负责真正从源读取数据：

```java
// SourceReader.java:L56
public interface SourceReader<T, SplitT extends SourceSplit>
        extends AutoCloseable, CheckpointListener {
    void start();
    InputStatus pollNext(ReaderOutput<T> output);
    List<SplitT> snapshotState(long checkpointId);
    CompletableFuture<Void> isAvailable();
    void addSplits(List<SplitT> splits);
    void notifyNoMoreSplits();
    default void handleSourceEvents(SourceEvent sourceEvent) {}
    default void pauseOrResumeSplits(
            Collection<String> splitsToPause, Collection<String> splitsToResume) {...}
}
```

SourceReader 的状态机由 `InputStatus`（`org.apache.flink.core.io.InputStatus`）驱动：

- `MORE_AVAILABLE` → Mailbox 循环调用 `pollNext()`
- `NOTHING_AVAILABLE` → 等待 `isAvailable()` future 完成后 Mailbox 唤醒
- `END_OF_INPUT` → 流结束

`pollNext()` 必须非阻塞。这就是 v2 不需要 checkpoint 锁的根本原因——读取和状态快照由不同线程完成，通过 `FutureCompletingBlockingQueue` 和 `CompletableFuture` 协调。`pauseOrResumeSplits` 用于 Watermark Alignment，默认抛出 `UnsupportedOperationException`。

### 23.2.4 SourceSplit 与 SourceEvent

```java
// SourceSplit.java:L25
public interface SourceSplit { String splitId(); }
// SourceEvent.java:L27
public interface SourceEvent extends Serializable {}
```

`SourceSplit` 极简——只要求唯一标识。`FileSourceSplit` 包含 `filePath`/`offset`/`length`/`hostnames[]`/`readerPosition`；Kafka 的 `KafkaPartitionSplit` 包含 `topicPartition`/`startingOffset`/`stoppingOffset`。`SourceEvent` 是 Enumerator 与 Reader 之间的扩展通信管道。

### 23.2.5 Sink 接口层次

Sink v2 因为两阶段提交天然需要拆分角色，层次比 Source 更深：

```
Sink<InputT>                              ← 顶层工厂
  ├─ createWriter() → SinkWriter<InputT>
  ├─ SupportsCommitter<CommittableT>      ← mixin: 两阶段提交
  │    └─ createCommitter() → Committer<CommittableT>
  └─ SupportsWriterState<InputT, StateT>  ← mixin: Writer 有状态
       └─ restoreWriter(context, recoveredState) → StatefulSinkWriter
```

```java
// SinkWriter.java:L32
public interface SinkWriter<InputT> extends AutoCloseable {
    void write(InputT element, Context context);
    void flush(boolean endOfInput);
}
// CommittingSinkWriter.java:L28
public interface CommittingSinkWriter<InputT, CommittableT> extends SinkWriter<InputT> {
    Collection<CommittableT> prepareCommit();
}
// Committer.java:L39
public interface Committer<CommT> extends AutoCloseable {
    void commit(Collection<CommitRequest<CommT>> committables);
}
```

`CommitRequest` 提供精细的提交控制：`signalAlreadyCommitted()`（幂等跳过）、`signalFailedWithKnownReason()`（不重试）、`signalFailedWithUnknownReason()`（作业失败）、`retryLater()`（可重试）、`updateAndRetryLater()`（部分成功后更新重试）。

### 23.2.6 Committable 的结构

以 FileSink 为例，`FileSinkCommittable`（`org.apache.flink.connector.file.sink.FileSinkCommittable`）包含三种载荷：`pendingFile`（待提交的临时文件）、`inProgressFileToCleanup`（需清理的 in-progress 文件）、`compactedFileToCleanup`（需清理的合并后文件）。Kafka Sink 的 Committable 则是事务 ID，Committer 用它调用 `commitTransaction()`。

---

## 23.3 — 关键流程走读

### 23.3.1 SourceFunction(v1) 的运行与 checkpoint 锁竞争

SourceFunction 的 `run()` 在独立线程中执行，`collect()` 和状态更新必须持锁：

```java
synchronized (ctx.getCheckpointLock()) {
    ctx.collect(record);
    offset++;
}
```

checkpoint 触发时也需要同一把锁读取状态。如果 `collect()` 之间有慢 IO（Kafka poll 超时），checkpoint 线程被阻塞 → 耗时抖动。这是 v1 最被诟病的问题。

### 23.3.2 FLIP-27 Source 的 Enumerator-Reader 协作流程

```
  JobMaster                          TaskManager
 ┌──────────────────┐              ┌─────────────────────┐
 │ SplitEnumerator  │  addReader() │ SourceReader[sub 0]  │
 │   start()        │◄─────────────│  启动后自动注册       │
 │ 发现新 Split     │              │                     │
 │   assignSplits() │─────────────►│  addSplits()        │
 │                  │  handleSplit │                     │
 │   assignSplit()  │◄──Request()─│  sendSplitRequest() │
 │ signalNoMore     │─────────────►│  notifyNoMoreSplits │
 └──────────────────┘              └─────────────────────┘
```

两种 Split 分配模式：**Pull 模式**（Reader 主动请求，FileSource 使用）和 **Push 模式**（Enumerator 主动推送，Kafka Partition 发现使用）。两者可混合——Kafka 启动时 Push 所有已知 Partition，FileSource 的 Reader 在每个 Split 消费完后 Pull 请求下一个。

### 23.3.3 SourceReader 的内部线程模型

`SourceReaderBase`（`org.apache.flink.connector.base.source.reader.SourceReaderBase`）将数据读取和记录发射解耦为两个线程：

```
 Mailbox 线程 (主线程)                  I/O 线程 (SplitFetcher)
 ┌─────────────────────────┐          ┌────────────────────────┐
 │ pollNext()              │          │ SplitReader.fetch()    │
 │   ↓ 从 elementsQueue   │◄─────────│   ↓ 从外部系统拉取数据  │
 │     取出 RecordsWith   │  Future  │   ↓ 封装放入 queue     │
 │     SplitIds            │ Comple- │                        │
 │   ↓ emitRecord()       │  ting    │                        │
 │     → ReaderOutput     │  Block-  │                        │
 └─────────────────────────┘  Queue  └────────────────────────┘
```

`elementsQueue`（`FutureCompletingBlockingQueue`）默认容量 2（`SourceReaderOptions.ELEMENT_QUEUE_CAPACITY`）。两种 SplitFetcherManager 策略：

1. **SingleThreadFetcherManager**：一个 I/O 线程多路复用所有 Split。Kafka Source 和 File Source 使用此模式。
2. **多线程模式**：自定义 SplitFetcherManager，每个 Split 分配独立 I/O 线程。适用于 IO 延迟高且 Split 间无共享资源的场景（如 HBase Source）。

为什么这样设计——单线程多路复用适合大多数 Connector（Kafka Consumer 本身是单线程 poll），避免多线程同步开销。放弃的替代方案是 Netty 式全异步 IO，但对现有 Client 库不友好。

### 23.3.4 File Source 实现走读

File Source 是 FLIP-27 的参考实现。**FileSource** 根据 `Boundedness` 选择创建 `StaticFileSplitEnumerator`（批模式，纯 Pull）或 `ContinuousFileSplitEnumerator`（流模式，周期性 Push）。

```java
// StaticFileSplitEnumerator.java:L88
public void handleSplitRequest(int subtask, @Nullable String hostname) {
    final Optional<FileSourceSplit> nextSplit = splitAssigner.getNext(hostname);
    if (nextSplit.isPresent()) {
        context.assignSplit(nextSplit.get(), subtask);
    } else {
        context.signalNoMoreSplits(subtask);
    }
}
```

**FileSourceReader** 继承 `SingleThreadMultiplexSourceReaderBase`，在 `onSplitFinished()` 中请求下一个 Split。**FileSourceSplit** 包含 `filePath`/`offset`/`length`/`hostnames[]`/`readerPosition`。

### 23.3.5 Sink v2 的两阶段提交流程

```
Checkpoint N 触发
    │
    ▼
SinkWriterOperator.prepareSnapshotPreBarrier(N)
    ├─ sinkWriter.flush(false)                      ← 第一阶段：刷写缓冲
    ├─ ((CommittingSinkWriter) sinkWriter)
    │    .prepareCommit() → Collection<CommT>       ← 生成 Committable
    └─ emit CommittableWithLineage → CommitterOperator

...... Checkpoint N 完成 ......

CommitterOperator.notifyCheckpointComplete(N)
    └─ committer.commit(committablesOfN)            ← 第二阶段：原子提交
         Kafka: commitTransaction / File: rename
```

Exactly-once 保证：第一阶段 flush 数据到临时存储（对外不可见）；第二阶段 `notifyCheckpointComplete` 后原子提交。commit 失败则从上一个 checkpoint 恢复并重试，`signalAlreadyCommitted()` 允许幂等跳过。

**File Sink**：Writer 写 `.in-progress.{uuid}` → prepareCommit 封装为 `PendingFileRecoverable` → Committer rename 为最终文件名。rename 在大多数文件系统上幂等。

**Kafka Sink**：Writer 在每个 checkpoint 周期开启 Kafka 事务 → prepareCommit 返回事务 ID → Committer 调用 `commitTransaction()`。事务超时自动回滚，保证不会部分可见。

---

## 23.4 — 横向对比（Spark / Kafka Streams / StarRocks）

### vs Spark DataSource V2

| 维度 | Flink FLIP-27 Source | Spark DataSource V2 |
|------|---------------------|---------------------|
| Split 管理 | SplitEnumerator 在 JobMaster | ScanBuilder 在 Driver |
| 数据读取 | pollNext() 非阻塞 | MicroBatchReader / ContinuousReader 两套 API |
| 流批统一 | 同一 Source，Boundedness 区分 | MicroBatchReader（微批）和 ContinuousReader（连续）分离 |
| Checkpoint | 天然嵌入 Source 生命周期 | 依赖 Structured Streaming 的 offset log |

Spark 的 MicroBatchReader 每个微批重新创建 Reader，Flink 的 SourceReader 是长生命周期对象，跨 checkpoint 持续运行，可维护连接池等丰富内部状态。

### vs Kafka Streams 的 Source/Sink 设计

Kafka Streams 没有 Source API——只读 Kafka，Source 硬编码。Sink 通过 `ProductionExceptionHandler` 处理写入失败，无独立 Committer。事务保证通过 `exactly_once_beta` 实现（Kafka 事务 API 封装），与 Flink 方案殊途同归，但只适用于 Kafka-to-Kafka 场景。

### vs StarRocks 的导入导出机制

StarRocks 导入使用 Stream Load（HTTP PUT），Exactly-once 依赖 Label 幂等去重——每个导入请求携带唯一 Label，FE 端做去重。Flink Connector 写入 StarRocks 时，`StarRocksSink` 通过 Label（含 checkpointId）实现幂等，本质是利用 StarRocks 自身去重能力替代 Flink 的 Committer 机制。

---

## 23.5 — 调优与实战陷阱

### 23.5.1 SourceReader 的 pendingRecords 和 mailbox 积压

`elementsQueue` 默认容量 2，I/O 线程最多缓存 2 批数据。下游慢导致 Mailbox 积压时，`emitNext()` 循环调用 `pollNext()` 直到 `NOTHING_AVAILABLE`。调优：增大 `source.reader.element.queue.capacity`（吸收 IO 抖动，代价是内存）；通过 `SourceReaderMetricGroup.setPendingRecordsGauge()` 监控积压。

### 23.5.2 SplitEnumerator 的 Split 分配策略对数据倾斜的影响

- **FileSource LocalityAwareSplitAssigner**：优先本地 Split，但某些 Node 文件远大于其他 Node → 倾斜。对策：`BlockSplittingRecursiveEnumerator` 按 HDFS block 大小切分大文件。
- **Kafka Partition 分配**：默认 round-robin，热点 Partition 导致部分 Subtask 积压。FLIP-27 没有内置动态重平衡，需监控 `pendingRecords` 手动调整。

### 23.5.3 Sink 的 commit 失败处理

Committer `commit()` 可能因外部系统故障失败：`retryLater()` 可重试（下次 checkpoint 完成时重新提交）；`signalFailedWithKnownReason()` 丢弃 committable 继续；`signalFailedWithUnknownReason()` 作业失败。

实战陷阱：commit 必须幂等——如果向外部数据库 INSERT 无唯一约束，重试导致数据重复。必须依赖外部系统去重或 committable 携带去重信息。

### 23.5.4 Connector 的 Checkpoint 对齐问题

某个 Split 消费远慢于其他 Split 时，checkpoint barrier 延迟。Unaligned Checkpoint（FLIP-76）可缓解，但 Source 端仍依赖 `pollNext()` 及时返回。Watermark Alignment（FLIP-182）通过 `pauseOrResumeSplits()` 暂停过快 Split，但需 Connector 显式支持。设置 `pipeline.watermark-alignment.allow-unaligned-source-splits: true` 可绕过限制，但可能导致 watermark 不对齐。Kafka Source 应合理设置 `fetch.max.bytes` 和 `max.poll.records` 避免单次 poll 返回过多数据。

---

## 本章要点回顾

1. SourceFunction(v1) 是单线程、单记录、Lock-based——四个根本问题限制扩展性。
2. FLIP-27 Source(v2) = Enumerator(管理 Split) + Reader(并行读) + SourceEvent(扩展通信) → 解耦优雅，流批统一。
3. SourceReader 的 `pollNext()` 非阻塞 + `isAvailable()` future → 与 Mailbox 天然集成，无需 checkpoint 锁。
4. SourceReaderBase 的 SplitFetcherManager 提供单线程多路复用和多线程两种 IO 模型。
5. Sink v2 = Writer(prepareCommit) + Committer(commit) → 两阶段 Exactly-once，Committer 天然幂等。
6. CommitRequest 提供精细的提交控制（retryLater / signalAlreadyCommitted / signalFailedWithKnownReason）。
7. File Sink 通过 rename 实现幂等提交；Kafka Sink 通过事务 API 实现原子提交。
8. Split 分配策略和 Checkpoint 对齐是调优的关键点。

## 源码导航

- FLIP-27 Source 核心 API：`flink-core/.../api/connector/source/Source.java`
- SplitEnumerator 接口：`flink-core/.../api/connector/source/SplitEnumerator.java`
- SourceReader 接口：`flink-core/.../api/connector/source/SourceReader.java`
- SourceSplit / SourceEvent：`flink-core/.../api/connector/source/SourceSplit.java`、`SourceEvent.java`
- InputStatus 枚举：`flink-core/.../core/io/InputStatus.java`
- SourceReaderBase：`flink-connector-base/.../source/reader/SourceReaderBase.java`
- SingleThreadFetcherManager / SplitFetcherManager：`flink-connector-base/.../source/reader/fetcher/`
- SourceReaderOptions：`flink-connector-base/.../source/reader/SourceReaderOptions.java`
- Sink v2 核心：`flink-core/.../api/connector/sink2/Sink.java`、`SinkWriter.java`、`CommittingSinkWriter.java`、`Committer.java`、`SupportsCommitter.java`
- FileSource / StaticFileSplitEnumerator / ContinuousFileSplitEnumerator / FileSourceReader / FileSourceSplit：`flink-connector-files/.../file/src/`
- FileSinkCommittable：`flink-connector-files/.../file/sink/FileSinkCommittable.java`
- SourceOperator：`flink-runtime/.../streaming/api/operators/SourceOperator.java`
- SinkWriterOperator / CommitterOperator / GlobalCommitterOperator：`flink-runtime/.../streaming/runtime/operators/sink/`
- SourceFunction(v1，已弃用)：`flink-runtime/.../streaming/api/functions/source/legacy/SourceFunction.java`
