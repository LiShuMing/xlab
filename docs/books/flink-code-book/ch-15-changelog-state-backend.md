# 第 15 章 · Changelog State Backend 与 Restore 加速

## 导读

- **一句话**：本章回答"当 Job 故障恢复时，为什么要等几十 GB 的 State 从 S3 下载完？Changelog 怎么把恢复时间从 10 分钟缩到 10 秒"。
- **前置知识**：第 12 章 Checkpoint、第 13 章 State Backend。
- **读完本章你能回答**：
  - 传统 State Restore 为什么慢
  - Changelog 记了什么、存在哪、怎么序列化
  - ChangelogKeyedStateBackend 如何拦截每条 state 变更并写入双路
  - Materialization 触发与截断的完整生命周期
  - 恢复时 base state + changelog 重放的协作流程
  - Changelog 与 WAL、Kafka Streams changelog topic 的设计取舍

---

## 15.1 — 设计动机：恢复 100GB State 的痛苦

```
传统 Restore：
  1. 从 S3/HDFS 下载所有 SST/Heap 文件 → 30~150s (网络)
  2. 从 Checkpoint Metadata 重建所有 State Backend → 10~60s (CPU/IO)
  3. 从 Source 重新读取从 Checkpoint 到 Failure 间的数据 → 延迟
  Total：数分钟
```

核心矛盾：**Checkpoint 间隔越长，恢复越快（Source 回放少）；但 State 快照越大，下载越慢。**

为什么这样设计？传统方案要么缩短 Checkpoint 间隔（更多 IO 开销和 Barrier 对齐延迟），要么接受长恢复时间。Changelog 放弃了"每次 Checkpoint 都全量快照"的做法，转而用"全量快照 + 增量 log"的双路模型，将恢复时间从 O(state_size) 降到 O(changelog_since_last_checkpoint)。解决的是恢复速度问题，放弃的是每条 state 变更多一次 append 的额外开销。

---

## 15.2 — 核心数据结构

### 15.2.1 StateChange — 单条变更记录

`StateChange` 是 Changelog 的最小记录单元（`org.apache.flink.runtime.state.changelog.StateChange:L27`）：

```java
public class StateChange implements Serializable {
    private final int keyGroup;   // -1 = 元数据变更, >=0 = 数据变更
    private final byte[] change;  // 序列化后的变更内容
}
```

两条构造路径：`StateChange.ofMetadataChange(byte[])` 用于 keyGroup=-1 的元数据，`StateChange.ofDataChange(int keyGroup, byte[])` 用于 keyGroup>=0 的数据变更。

为什么只存 keyGroup 和 byte[] 而不是 key/namespace/value？因为序列化由 `KvStateChangeLoggerImpl` 完成——操作码（StateChangeOperation）、stateShortId、key、namespace、value 全部序列化成 byte[] 再封装。StateChange 本身格式无关，下游存储不需要理解变更语义，也使得不同 StateChangelogStorage 实现可以共用同一套序列化逻辑。

### 15.2.2 StateChangeOperation — 变更操作类型

`org.apache.flink.state.changelog.StateChangeOperation:L31` 定义了 9 种操作：

| 操作 | 作用域 | 触发场景 |
|------|--------|---------|
| CLEAR | key + namespace | ValueState.clear() |
| SET | key + namespace | ValueState.update() |
| SET_INTERNAL | key + namespace | TTL compaction 内部更新 |
| ADD | key + namespace | AggregatingState.add() / ReducingState.reduce() |
| MERGE_NS | key + 多 namespace | Window 触发合并 namespace |
| ADD_ELEMENT | key + namespace + element | ListState.add() |
| ADD_OR_UPDATE_ELEMENT | key + namespace + element | MapState.put() |
| REMOVE_ELEMENT | key + namespace + element | ListState/MapState remove |
| METADATA | 全局 | state 首次注册时写入一次 |

METADATA 是特殊操作，在 `AbstractStateChangeLogger.logMetaIfNeeded()` 中首次写入（含 state 名、序列化器、shortId），后续该 state 的变更不再重复写元数据。`metaDataWritten` 标志位在 `resetWritingMetaFlag()` 时重置，每次 Materialization 触发后重置，保证新周期内元数据重新写入。

### 15.2.3 ChangelogKeyedStateBackend — 变更拦截层

`ChangelogKeyedStateBackend`（`org.apache.flink.state.changelog.ChangelogKeyedStateBackend:L114`）包装原始 `AbstractKeyedStateBackend`，对每个 state 操作双写。它不直接操作 state 数据——所有操作由 `ChangelogValueState`/`ChangelogListState` 等包装类完成，在委托给原始 state 的同时调用 `KvStateChangeLogger` 将变更追加到 changelog writer。

核心字段：`keyedStateBackend`（被委托的原始 backend）、`stateChangelogWriter`（changelog 写入器）、`changelogSnapshotState`（快照状态追踪）、`lastUploadedFrom/lastUploadedTo`（上次上传的 sequence 范围）、`changelogTruncateHelper`（截断辅助）。

一个容易忽略的细节：`lastCreatedStateId` 是一个 short 类型的自增 ID，为每个 state 分配唯一标识。变更序列化时只写 shortId 而非 state 全名，减少每条变更记录的开销。state 全名和 shortId 的映射关系通过 METADATA 操作写入 changelog，恢复时由 `ChangelogBackendLogApplier` 重建到 `Map<Short, StateID> stateIds` 中。

### 15.2.4 ChangelogStateBackendHandle — 双路状态句柄

`ChangelogStateBackendHandle`（`org.apache.flink.runtime.state.changelog.ChangelogStateBackendHandle:L57`）同时持有 materialized 和 non-materialized 两部分：

```java
public interface ChangelogStateBackendHandle extends KeyedStateHandle {
    List<KeyedStateHandle> getMaterializedStateHandles();        // 已物化的完整快照
    List<ChangelogStateHandle> getNonMaterializedStateHandles(); // 未物化的增量 log
    long getMaterializationID();
}
```

实现类 `ChangelogStateBackendHandleImpl` 核心字段：`materialized`（DFS 上的完整 SST/Heap 文件）、`nonMaterialized`（DFS 上的 log 文件）、`materializationID`（物化版本号）、`checkpointId`（对应的 checkpoint ID）、`persistedSizeOfThisCheckpoint`（本次 checkpoint 持久化字节数）。

为什么这样设计？恢复时需要同时定位"全量快照在哪里"和"增量 log 在哪里"，分开持有使得截断 non-materialized 不影响 materialized。这也是 rescaling 时 `getIntersection()` 能正确切割两路数据的基石——该方法的实现（L250）分别对 materialized 和 nonMaterialized 列表做 keyGroupRange 交集过滤，生成新的 handle。

`ChangelogStateBackendLocalHandle` 是 local recovery 变体，同时持有 `localMaterialized` + `localNonMaterialized`（本地路径）和 `remoteHandle`（远程路径），在 Task 本地恢复时优先使用本地句柄。

### 15.2.5 StateChangelogWriter — 变更写入接口

`StateChangelogWriter`（`org.apache.flink.runtime.state.changelog.StateChangelogWriter:L28`）定义了 5 个核心操作：

- `append(int keyGroup, byte[] value)` — 追加数据变更到内存缓冲
- `appendMeta(byte[] value)` — 追加元数据变更
- `persist(SequenceNumber from, long checkpointId)` — 将指定范围变更持久化到外部存储
- `truncate(SequenceNumber to)` — 截断已物化的变更，释放资源
- `confirm / reset` — 通知 JM 确认或回滚变更

为什么 `append` 不直接持久化？因为 state 变更频率极高，同步刷盘吞吐无法接受。`append` 只写内存缓冲，由 `persist` 在 Checkpoint Barrier 到达时批量上传。

`FsStateChangelogWriter` 的实现中有一个关键优化——pre-emptive flush：当 `activeChangeSetSize` 超过 `dstl.dfs.preemptive-persist.threshold`（默认 1MB）时，不等 checkpoint 就提前上传。这避免了 checkpoint 间隔内内存无限膨胀。另一个优化是 `rollover()` 机制——`append` 不递增 SequenceNumber，只在 `nextSequenceNumber()` 时 rollover，将当前 activeChangeSet 打包成 `StateChangeSet` 移入 `notUploaded` 队列。这意味着多个 append 共享同一个 SQN，减少了 DFS 文件中的分段数量。

### 15.2.6 StateChangelogStorage — SPI 存储接口

`StateChangelogStorage`（`org.apache.flink.runtime.state.changelog.StateChangelogStorage:L32`）通过 `StateChangelogStorageLoader` 加载实现类。内置两种实现：

| 实现 | 类路径 | 用途 |
|------|--------|------|
| `InMemoryStateChangelogStorage` | `flink-runtime/.../changelog/inmemory/` | 测试，数据不持久 |
| `FsStateChangelogStorage` | `flink-dstl/flink-dstl-dfs/.../changelog/fs/` | 生产，写入 DFS |

`StateChangelogStorageLoader` 遵循 Java SPI 规范，通过 `ServiceLoader.load(StateChangelogStorageFactory.class)` 扫描 classpath 上的工厂类。`FsStateChangelogStorageFactory` 的 identifier 为 `"filesystem"`，`InMemoryStateChangelogStorageFactory` 的 identifier 为 `"memory"`。外部可通过在 META-INF/services 中注册自定义 `StateChangelogStorageFactory` 注入实现（如基于 BookKeeper 或 Kafka 的 distlog）。

`StateChangelogStorageView` 是恢复时的只读视图接口——恢复端不需要创建 Writer，只需要通过 `createReader()` 读取已有的 changelog 数据。

### 15.2.7 StateChangeFormat — 序列化格式

`StateChangeFormat`（`org.apache.flink.changelog.fs.StateChangeFormat:L46`）定义了变更写入 DFS 时的二进制格式：

```
[ChangeSet 1]
  int: keyGroup 数量
  [KeyGroup 1]（metadata keyGroup=-1 优先）
    int: 变更条数
    int: keyGroup ID
    [Change 1] int:length + byte[length]
    [Change 2] ...
  [KeyGroup 2] ...
[ChangeSet 2] ...
```

为什么按 keyGroup 分组写？因为 rescaling 恢复需要按 keyGroup 切割 state，分组写入使 `ChangelogStateHandle.getIntersection()` 能精确切割属于目标 keyGroupRange 的变更，避免恢复时读取无关数据。Metadata keyGroup(-1) 优先写入——恢复时必须先处理元数据才能正确解析后续数据操作。

`StateChangeSet`（`org.apache.flink.changelog.fs.StateChangeSet:L38`）是上传的基本单位，包含 logId（区分不同 operator）、sequenceNumber、变更列表。`FsStateChangelogWriter` 按 SQN 将 StateChangeSet 组织在 `NavigableMap<SequenceNumber, StateChangeSet>` 中，`persist` 时将指定范围的 ChangeSet 打包成 UploadTask 提交。

---

## 15.3 — 关键流程走读

### 15.3.1 Changelog 写入路径

以 `ValueState.update()` 为例，完整路径：

```
1. ChangelogValueState.update(value)（L61）：
   - delegatedState.update(value)              → 写入原始 backend
   - changeLogger.valueUpdated(value, ns)      → 追加到 changelog

2. AbstractStateChangeLogger.log(SET, dataWriter, ns)：
   - logMetaIfNeeded() → 首次写入 METADATA（state 名、序列化器、shortId）
   - serialize(SET, ns, dataWriter) → byte[opcode + shortId + key + ns + value]
   - stateChangelogWriter.append(keyGroup, bytes) → 写入内存缓冲

3. FsStateChangelogWriter.append()：
   - 添加 StateChange 到 activeChangeSet
   - activeChangeSetSize >= threshold → 触发 pre-emptive flush
```

### 15.3.2 Checkpoint 快照与 Materialization 触发

**Checkpoint 快照**：Barrier 到达时 `ChangelogKeyedStateBackend.snapshot()`（L399）记录 `lastUploadedFrom = changelogSnapshotState.lastMaterializedTo()` 和 `lastUploadedTo = stateChangelogWriter.nextSequenceNumber()`，调用 `stateChangelogWriter.persist(lastUploadedFrom, checkpointId)` 异步上传 DFS，返回 `CompletableFuture`。上传完成后 `buildSnapshotResult()`（L503）组装 `ChangelogStateBackendHandleImpl`（materialized = 已物化句柄，nonMaterialized = 之前未物化 log + 本次 persist 的 log）。persist 是异步的——上传到 DFS 需要网络 IO，同步等待会阻塞算子。

注意一个细节：`ChangelogKeyedStateBackend` 只支持 `CheckpointType.CHECKPOINT`，Savepoint 走独立的 `nativeSavepoint()` 路径。

**Materialization 触发**：`PeriodicMaterializationManager`（`org.apache.flink.state.common.PeriodicMaterializationManager:L53`）周期触发（默认 10 分钟，初始延迟随机化避免雷群效应），通过 MailboxExecutor 投递到 Task 线程调用 `initMaterialization()`（L853）。核心流程：检查上次物化是否已确认/失败（`lastConfirmedMaterializationId < materializedId - 1` 时跳过，避免 SharedStateRegistry 连续性断裂） → 获取 `upTo = stateChangelogWriter.nextSequenceNumber()` → 触发 `keyedStateBackend.snapshot()` 生成完整快照 → 异步上传 → 成功后回到 Task 线程更新 `changelogSnapshotState` + 调用 `changelogTruncateHelper.materialized(upTo)`。

为什么 Materialization 需要经过 MailboxExecutor？因为 `ChangelogKeyedStateBackend` 不是线程安全的，状态更新必须在 Task 主线程完成。异步线程只负责上传 IO。

### 15.3.3 截断流程

截断由 `ChangelogTruncateHelper`（`org.apache.flink.state.changelog.ChangelogTruncateHelper:L86`）管理，需同时满足两个条件：
1. **Checkpoint 已被 subsume**：JM 确认该 checkpoint 不再用于恢复
2. **Changelog 已被 materialize**：该序列号之前的变更已物化到完整快照

```java
private void truncate() {
    if (subsumedUpTo != null && materializedUpTo != null) {
        SequenceNumber to = min(subsumedUpTo, materializedUpTo);
        stateChangelogWriter.truncate(to);
    }
}
```

即使 state 已物化，JM 仍可能用旧 checkpoint 恢复，此时需要 changelog 增量补齐——所以必须双条件满足。

### 15.3.4 恢复路径

恢复由 `ChangelogBackendRestoreOperation.restore()`（`org.apache.flink.state.changelog.restore.ChangelogBackendRestoreOperation:L66`）驱动：

```
1. extractBaseState(stateHandles) → 提取所有 materialized 的 KeyedStateHandle
2. baseBackendBuilder.apply(baseState) → 用原始 StateBackend 恢复 base backend
3. changelogRestoreTargetBuilder.apply(baseBackend, stateHandles) → 创建 ChangelogRestoreTarget
4. 遍历每个 handle 的 nonMaterialized 部分：
   a. getStateChangelogStorageView() → 创建 StateChangelogHandleReader
   b. CloseableIterator<StateChange> → 逐条读取变更
   c. ChangelogBackendLogApplier.apply() → 分发：
      - METADATA → 恢复序列化器 → createKeyedState() 注册 state
      - 数据操作 → shortId 查找 StateID → 获取 ChangelogState →
        state.getChangeApplier(factory).apply(op, in)
        (如 ValueStateChangeApplier: SET → state.update(deserialize))
5. 返回完整的 ChangelogKeyedStateBackend
```

**Non-Materialized 恢复**：当 `materialized` 为空时（Job 首次启动或 disable periodic materialization），base backend 从零初始化，恢复完全依赖重放 changelog 中所有 StateChange。先 apply METADATA 注册 schema（`ChangelogBackendLogApplier.restoreKvMetaData()` 通过 `StateDescriptor` 在空 backend 中创建 state），再逐条重放数据操作。此模式只适合小作业——changelog 包含所有历史变更（含被覆盖的旧值），大 state 重放耗时甚至超过下载快照。

**SequenceNumber 的角色**：`SequenceNumber`（`org.apache.flink.runtime.state.changelog.SequenceNumber:L34`）是 changelog 中的逻辑时间戳，用于划定 materialized 和 non-materialized 的边界。`ChangelogSnapshotState.materializedTo` 记录当前物化到哪个 sequence，`persist(from)` 从该 sequence 开始上传。恢复时不需要 SequenceNumber——因为 `ChangelogStateHandle` 已经包含了需要重放的完整变更范围。

**兼容性**：`getChangelogStateBackendHandle()`（L133）将旧版 checkpoint 的普通 `KeyedStateHandle` 包装为 `ChangelogStateBackendHandleImpl(materialized=handle, nonMaterialized=emptyList())`，保证恢复逻辑兼容。`ChangelogStateBackendLocalHandle` 则用于 local recovery，同时持有本地和远程两套句柄。

---

## 15.4 — 横向对比

### vs PostgreSQL Checkpoint + WAL

| 维度 | PostgreSQL | Flink Changelog |
|------|-----------|-----------------|
| 写入时机 | 事务 commit 前 fsync WAL | state 变更 append 内存，checkpoint 时 persist |
| Checkpoint | BGWriter 周期刷脏页 + LSN | PeriodicMaterialization 周期物化 + 截断 changelog |
| 恢复 | 从最近 checkpoint LSN 重放 WAL | 下载 materialized state + 重放 non-materialized changelog |
| 持久性保证 | crash 后绝不丢已 commit 数据 | changelog 丢失仍可从完整 checkpoint 恢复 |

关键差异：PostgreSQL WAL 是事务一致性保证，Flink Changelog 是恢复加速手段——持久性要求低于数据库 WAL。

### vs RocksDB 自身的 WAL

RocksDB WAL 用于单 TM 进程崩溃后恢复 MemTable 中的未刷盘数据，存储在本地磁盘，MemTable flush 到 SST 后即删除。Flink Changelog 用于跨 TM 的分布式恢复，存储在 DFS 上，需 materialization + checkpoint subsume 后才截断。为什么不能复用 RocksDB WAL？TM 机器宕机后本地文件不可访问，Flink 的恢复粒度是"在新的 TM 上重建 state"。即使 TM 没有宕机只是进程重启，RocksDB WAL 也只恢复到最近 MemTable 级别，无法恢复到最近 Checkpoint 之后的状态——这之间的 gap 需要 Flink Changelog 填补。

### vs Spark Structured Streaming

Spark SS 依赖 HDFS-backed Checkpoint，没有 WAL 增量思想，恢复需全量下载 state 目录。Spark 3.x 的 RocksDB state store 引入了 incremental checkpoint（SST 文件级增量），但不如 Flink Changelog 的行级增量精细。典型对比：100GB state，Spark SS 恢复 5-15 分钟，Flink+Changelog（10GB changelog）约 10-30 秒。

### vs Kafka Streams State Store 恢复

| 维度 | Kafka Streams | Flink Changelog |
|------|--------------|-----------------|
| Changelog 存储 | Kafka compacted topic | DFS 文件 |
| 截断机制 | Kafka log compaction（保留最新 key） | Materialization 后 truncate |
| 全量快照 | 无（纯 log 驱动） | 有（PeriodicMaterialization） |

Kafka Streams 是"纯 log 驱动"，Flink Changelog 是"快照 + log"双路模型。双路模型恢复更快（下载快照 + 少量 log 重放 vs 全量 log 重放），但需要管理快照与 log 的一致性。

### vs StarRocks / MaxCompute

StarRocks Primary Key 表的 changelog 是存储引擎内部事务日志，面向单机/副本同步。MaxCompute StreamCompute 基于 Blink（Flink 分支），额外集成 Pangu 作为 ChangelogStorage 后端，利用 append-only 文件和分层存储降低存储成本。

---

## 15.5 — 调优与实战陷阱

### Changelog 引起过多网络 IO

高频 state 变更（高频 counter、大 MapState 频繁 put）导致 `preEmptiveFlushIfNeeded` 频繁触发上传，背压升高。现象：TaskManager 的背压突然升高，Changelog Writer 的 `append` 调用耗时变长。

调优策略：
- `dstl.dfs.preemptive-persist.threshold` 调大（默认 1MB），减少 pre-emptive flush 频率
- 高频更新的 state 用 `AggregatingState` 替代 `ValueState`——前者在内存中聚合，checkpoint 时只写一条合并后的值
- 缩短 materialization 间隔（如从 10 分钟降到 3 分钟），减少每次 checkpoint 需要上传的 changelog 量

### 内存中 Changelog 大小管理

`FsStateChangelogWriter` 的 `notUploaded` + `activeChangeSet` 会持续膨胀。现象：TaskManager 堆内存占用持续增长，GC 压力增大，极端情况下 OOM。

调优策略：
- 监控 `changelog.buffer.size` 指标
- `preemptive-persist.threshold` 适当调小，让大缓冲提前上传释放内存
- 确保 DFS 写入带宽充足——如果 DFS 成为瓶颈，changelog 上传排队会撑大内存
- Materialization 间隔不宜超过 30 分钟——长时间不物化意味着 changelog 不被截断，旧段持续占用内存

### Materialization 间隔的配置策略

`state.changelog.periodic-materialize.interval` 默认 10 分钟。间隔过短 → DFS IO 压力大、与 Checkpoint 冲突；间隔过长 → changelog 积压、恢复重放多。推荐：小 state（<10GB）3-5 分钟，中等 state（10-100GB）10 分钟，大 state（>100GB）10-20 分钟。`state.changelog.max-failures-allowed` 默认 3，DFS 抖动频繁可调大。

### Changelog 与 Unaligned Checkpoint 的配合

二者解决不同层面问题：Changelog 加速 state restore，Unaligned Checkpoint 加速 barrier 对齐。可同时启用——Changelog 只关注 keyed state，不覆盖 operator state 和 in-flight 数据。恢复时间 = max(state restore via changelog, in-flight buffer restore)。

### Savepoint 与 Rescaling 陷阱

Savepoint 走 `nativeSavepoint()` 路径，强制触发原始 backend 全量快照、non-materialized 为空——不提供 changelog 加速效果。这是设计取舍：Savepoint 语义是"可移植的自包含快照"。Rescaling 后首次 Materialization 完成前不生成本地快照（`isRescaling = true`），导致 rescaling 后首次恢复可能比正常恢复慢。

---

## 本章要点回顾

1. 传统恢复瓶颈在从 DFS 下载全量 State——Changelog 用持续写 WAL 的方式让恢复只需重放最近变更，恢复时间从分钟级降到秒级。
2. `ChangelogKeyedStateBackend` 是拦截层，包装原始 StateBackend，每条 state 变更双写。
3. `ChangelogStateBackendHandle` 持有 materialized + non-materialized 双路句柄，恢复先恢复 base state 再重放 changelog。
4. Materialization 是截断 Changelog 的关键——周期物化后截断旧 log，防止无限增长。截断需 checkpoint subsume + materialize 双条件。
5. Changelog 对持久性要求低于数据库 WAL——丢失仍可从完整 checkpoint 恢复。
6. Non-Materialized 模式（纯 log 驱动）适合小 state 作业，大 state 必须开启 PeriodicMaterialization。
7. 调优核心：平衡 Materialization 间隔、pre-emptive persist 阈值、DFS 带宽。

## 源码导航

| 类 | 路径 | 职责 |
|----|------|------|
| `ChangelogStateBackend` | `flink-state-backends/flink-statebackend-changelog/.../ChangelogStateBackend.java` | StateBackend 包装入口 |
| `ChangelogKeyedStateBackend` | `flink-state-backends/flink-statebackend-changelog/.../ChangelogKeyedStateBackend.java` | 变更拦截层，双写 + 快照 + 物化 |
| `ChangelogStateBackendHandle` | `flink-runtime/.../changelog/ChangelogStateBackendHandle.java` | 双路状态句柄接口 |
| `StateChange` | `flink-runtime/.../changelog/StateChange.java` | 单条变更记录 |
| `StateChangeOperation` | `flink-state-backends/flink-statebackend-changelog/.../StateChangeOperation.java` | 变更操作枚举 |
| `StateChangelogWriter` | `flink-runtime/.../changelog/StateChangelogWriter.java` | 写入接口（append/persist/truncate） |
| `StateChangelogStorage` | `flink-runtime/.../changelog/StateChangelogStorage.java` | SPI 存储接口 |
| `FsStateChangelogStorage` | `flink-dstl/flink-dstl-dfs/.../FsStateChangelogStorage.java` | DFS 生产实现 |
| `FsStateChangelogWriter` | `flink-dstl/flink-dstl-dfs/.../FsStateChangelogWriter.java` | DFS 写入器（含 pre-emptive flush） |
| `StateChangeFormat` | `flink-dstl/flink-dstl-dfs/.../StateChangeFormat.java` | 序列化格式 |
| `ChangelogBackendRestoreOperation` | `flink-state-backends/flink-statebackend-changelog/.../restore/ChangelogBackendRestoreOperation.java` | 恢复入口 |
| `ChangelogBackendLogApplier` | `flink-state-backends/flink-statebackend-changelog/.../restore/ChangelogBackendLogApplier.java` | 变更重放引擎 |
| `PeriodicMaterializationManager` | `flink-state-backends/flink-statebackend-common/.../PeriodicMaterializationManager.java` | 周期物化管理器 |
| `ChangelogTruncateHelper` | `flink-state-backends/flink-statebackend-changelog/.../ChangelogTruncateHelper.java` | 截断辅助 |
| `StateChangelogOptions` | `flink-core/.../configuration/StateChangelogOptions.java` | 配置项定义 |
