# 第 14 章 · Savepoint 与 State 兼容性

## 导读

- **一句话**：本章回答"Savepoint 和 Checkpoint 的区别，以及当你改了算子逻辑后怎样让旧的 State 在新代码上继续工作"。
- **前置知识**：第 12 章 Checkpoint、第 13 章 State Backend。
- **读完本章你能回答**：
  - Checkpoint 和 Savepoint 的关键区别
  - `TypeSerializerSnapshot` 的演化协议怎样实现 Schema Evolution
  - Operator ID 和 UID 的作用——为什么改了代码位置还需要找到旧 State
  - Savepoint 触发与恢复的完整链路
  - State Processor API 是怎样对 Savepoint 做离线操作
  - 升级时 OperatorID 匹配失败和 Schema 不兼容的后果与应对

---

## 14.1 — 设计动机：Checkpoint 为故障恢复，Savepoint 为升级迁移

| 维度 | Checkpoint | Savepoint |
|------|-----------|-----------|
| **触发** | 自动，由 CheckpointCoordinator 定时触发 | 手动，由用户通过 CLI/REST 触发 |
| **生命周期** | Job 结束后自动清除 | 永久保留，直到用户删除 |
| **目的** | 故障恢复 | 升级、A/B 测试、迁移 |
| **增量** | 默认支持增量 | 通常全量（自包含） |
| **格式稳定性** | 可能变 | 必须稳定（跨版本） |
| **文件共享** | `FORWARD_BACKWARD`，允许增量引用 | `NO_SHARING`，所有数据自包含 |

**一句话**：Checkpoint 是 Flink 为自己做的快照；Savepoint 是 Flink 为用户做的快照。

为什么这样设计？解决的问题是：故障恢复只需要"最近一次完整快照"，而升级迁移需要"格式稳定、可跨版本读取"的快照。如果用同一个机制，要么牺牲故障恢复的性能（每次都做全量），要么牺牲升级的可靠性（增量格式随版本变化）。Flink 选择分离两者——Checkpoint 走性能路线，Savepoint 走稳定性路线。放弃了"统一快照"的简洁性，换来了两种场景各自的最优解。

`CheckpointProperties` 用布尔标志控制两类快照的生命周期差异。Savepoint 的所有 `discard*` 标志均为 `false`，Checkpoint 的 `discardSubsumed = true`：

```java
// <org.apache.flink.runtime.checkpoint.CheckpointProperties:L#294>
public static CheckpointProperties forSavepoint(
        boolean forced, SavepointFormatType formatType) {
    return new CheckpointProperties(
            forced, SavepointType.savepoint(formatType),
            false, false, false, false, false, false); // 所有 discard = false
}
```

`SavepointType` 的 `SharingFilesStrategy.NO_SHARING` 确保 Savepoint 不引用其他文件，所有 State 数据自包含于 Savepoint 目录（`<org.apache.flink.runtime.checkpoint.SavepointType:L#85>`）。

---

## 14.2 — 核心数据结构

### 14.2.1 Savepoint 存储格式

一个 Savepoint 在 DFS 上的目录结构：

```
hdfs:///savepoints/savepoint-abc123/
  _metadata                  ← 元数据文件，包含所有 OperatorState 的索引
  aligned-xxx                ← 算子 State 的实际数据文件
```

`_metadata` 是入口文件（常量定义于 `<org.apache.flink.runtime.state.filesystem.AbstractFsCheckpointStorageAccess:L#86>`），由 `MetadataV*Serializer` 系列类序列化/反序列化，当前支持 V1~V6 共 6 种格式版本，通过 `<org.apache.flink.runtime.checkpoint.metadata.MetadataSerializers:L#32>` 按版本号分发。

`_metadata` 内部保存 `CheckpointMetadata` 对象（`<org.apache.flink.runtime.checkpoint.metadata.CheckpointMetadata:L#33>`），核心字段为 `checkpointId`、`Collection<OperatorState>` 和 `Collection<MasterState>`。

### 14.2.2 OperatorState 与 OperatorSubtaskState

`OperatorState` 是一个逻辑算子的全部 State 容器，按 `OperatorID` 索引（`<org.apache.flink.runtime.checkpoint.OperatorState:L#47>`）：

```java
public class OperatorState implements CompositeStateHandle {
    private final OperatorID operatorID;
    private final Map<Integer, OperatorSubtaskState> operatorSubtaskStates; // subtaskIndex → state
    private final int parallelism;
    private final int maxParallelism;
}
```

每个并行实例的 State 由 `OperatorSubtaskState` 表示（`<org.apache.flink.runtime.checkpoint.OperatorSubtaskState:L#74>`），包含 6 类 State Handle：managedOperatorState、rawOperatorState、managedKeyedState、rawKeyedState、inputChannelState、upstreamOutputBufferState。

为什么这样设计？将 State 分成 managed/raw x operator/keyed 四象限，让 Flink 和用户各管各的：managed State 由 Flink 控制序列化与 Schema 演化，raw State 由用户自行处理字节。这种分离使 `TypeSerializerSnapshot` 只需关心 managed State 的兼容性。

### 14.2.3 OperatorID 的生成规则

`OperatorID` 继承自 `AbstractID`，本质是 128-bit 标识。两种生成方式：

**方式一：用户指定 UID（推荐）**。通过 `.uid("my-map")` 指定，Flink 用 MurmurHash3 计算：

```java
// <org.apache.flink.streaming.api.graph.StreamGraphHasherV2:L#145>
private static byte[] generateUserSpecifiedHash(String operatorUid, Hasher hasher) {
    hasher.putString(operatorUid, Charset.forName("UTF-8"));
    return hasher.hash().asBytes();
}
```

**方式二：自动生成 hash（不推荐用于生产）**。未指定 UID 时，根据节点拓扑位置确定性计算哈希，输入节点的哈希参与下游计算（`<org.apache.flink.streaming.api.graph.StreamGraphHasherV2:L#276>`：`hash[j] = (byte)(hash[j] * 37 ^ otherHash[j])`），因此插入新算子会导致下游所有 ID 变化。

`OperatorIDPair`（`<org.apache.flink.runtime.OperatorIDPair:L#29>`）同时持有 `generatedOperatorID` 和可选的 `userDefinedOperatorID`。恢复时 Flink 会用两个 ID 分别匹配 Savepoint 中的 State。

### 14.2.4 TypeSerializerSnapshot 的接口设计

`TypeSerializerSnapshot` 是 Schema Evolution 的协议核心（`<org.apache.flink.api.common.typeutils.TypeSerializerSnapshot:L#72>`），定义 5 个方法：

```java
public interface TypeSerializerSnapshot<T> {
    int getCurrentVersion();
    void writeSnapshot(DataOutputView out);
    void readSnapshot(int readVersion, DataInputView in, ClassLoader cl);
    TypeSerializer<T> restoreSerializer();
    TypeSerializerSchemaCompatibility<T> resolveSchemaCompatibility(
        TypeSerializerSnapshot<T> oldSerializerSnapshot);
}
```

兼容性返回值 `TypeSerializerSchemaCompatibility` 有 4 种（`<org.apache.flink.api.common.typeutils.TypeSerializerSchemaCompatibility:L#44>`）：

| 结果 | 含义 | 处理方式 |
|------|------|----------|
| `COMPATIBLE_AS_IS` | 新 Serializer 直接可读旧数据 | 无需迁移 |
| `COMPATIBLE_AFTER_MIGRATION` | 旧 Serializer 读出 → 新 Serializer 写回 | Flink 自动全量迁移 |
| `COMPATIBLE_WITH_RECONFIGURED_SERIALIZER` | 新 Serializer 需重配置 | 用 reconfigured 替换 |
| `INCOMPATIBLE` | 无论如何无法读取 | 抛 `StateMigrationException`，Job 失败 |

为什么这样设计？`restoreSerializer()` 解决"旧数据怎么读"，`resolveSchemaCompatibility()` 解决"读出来后能不能写回去"。两者分离，使"加字段"场景通过 `COMPATIBLE_AFTER_MIGRATION` 自动完成，而"类型完全改变"直接阻断——宁可启动失败，也不要数据错乱。放弃了"自动推断兼容性"的便利性，换来了对数据一致性的绝对保障。

---

## 14.3 — 关键流程走读

### 14.3.1 Savepoint 触发的完整流程

```
REST API (POST /jobs/:jobid/savepoints)
  → SavepointHandlers.SavepointTriggerHandler.handleRequest()
    → RestfulGateway.triggerSavepoint()
      → Dispatcher → JobMaster.triggerSavepoint()
        → CheckpointCoordinator.triggerSavepoint(targetLocation, formatType)
          → CheckpointProperties.forSavepoint(...)
          → triggerCheckpointFromCheckpointThread(...)
            → triggerCheckpoint(...) [与 Checkpoint 共享触发链路]
              → 所有 Task 完成 barrier 对齐
              → CompletedCheckpoint 写入 DFS（_metadata + State 文件）
```

REST 层入口：`<org.apache.flink.runtime.rest.handler.job.savepoints.SavepointHandlers$L#257>`。最终调用 `CheckpointCoordinator.triggerSavepoint()`，构造 `CheckpointProperties.forSavepoint()` 后复用 `triggerCheckpoint()` 链路。关键差异：Savepoint 的 `forced = true`，不受并发 Checkpoint 数量限制和最小间隔约束。

### 14.3.2 Savepoint 恢复的完整流程

```
CLI: flink run -s hdfs:///savepoints/xxx new-job.jar
  → ClusterClient.submitJob(savepointRestoreSettings)
    → Dispatcher.submitJob()
      → JobMaster.<init>(... savepointRestoreSettings ...)
        → CheckpointCoordinator.restoreLatestCheckpointedStateToAll()
          → 定位 _metadata，反序列化 CheckpointMetadata
          → 提取 Map<OperatorID, OperatorState>
          → StateAssignmentOperation.assignStates()
            → checkStateMappingCompleteness(): 逐 OperatorID 匹配
            → buildStateAssignments(): 建立 JobVertex → OperatorState 映射
            → repartitionState(): 并行度变更时 State 重分配
            → applyStateAssignments(): 设置到 Execution.setInitialState()
```

OperatorID 匹配的关键检查在 `<org.apache.flink.runtime.checkpoint.StateAssignmentOperation:L#787>`，遍历 Savepoint 中每个 OperatorState，在当前 Job 的所有 OperatorIDPair 中查找匹配（同时检查 generatedOperatorID 和 userDefinedOperatorID）。

`SavepointRestoreSettings`（`<org.apache.flink.runtime.jobgraph.SavepointRestoreSettings:L#34>`）携带 `restorePath`、`allowNonRestoredState` 和 `RecoveryClaimMode`。`RecoveryClaimMode`（`<org.apache.flink.core.execution.RecoveryClaimMode:L#32>`）决定恢复后对 Savepoint 文件的所有权：
- **CLAIM**：Flink 取得所有权，后续 Checkpoint 可清理 Savepoint 文件
- **NO_CLAIM**（默认）：不拥有文件，首次 Checkpoint 做全量快照
- **LEGACY**（已废弃）：不拥有文件，但后续 Checkpoint 可直接引用 Savepoint 文件

### 14.3.3 TypeSerializerSnapshot 兼容性判断流程

恢复 State 时，`StreamTask` 在初始化 StateBackend 时执行兼容性检查：

```
1. 从 _metadata 反序列化出旧 TypeSerializerSnapshot
2. 创建新代码的 TypeSerializer，取其 TypeSerializerSnapshot
3. 调用 新snapshot.resolveSchemaCompatibility(旧snapshot)
4. 根据返回值：
   COMPATIBLE_AS_IS            → 直接使用新 Serializer
   COMPATIBLE_AFTER_MIGRATION  → 旧snapshot.restoreSerializer() 读旧数据
                                  → 新 Serializer 写回 → 迁移完成
   COMPATIBLE_WITH_RECONFIGURED_SERIALIZER → 使用 reconfigured Serializer
   INCOMPATIBLE               → 抛 StateMigrationException，Job 失败
```

`COMPATIBLE_AFTER_MIGRATION` 是最常见的增量迁移场景（如 POJO 增加字段），Flink 自动执行"读旧→写新"全量迁移，对用户透明。代价是恢复耗时增加。

### 14.3.4 OperatorID 匹配失败的后果

- `allowNonRestoredState = false`（默认）：`checkStateMappingCompleteness()` 抛 `IllegalStateException`，Job 启动失败
- `allowNonRestoredState = true`：该 OperatorState 被跳过，日志打印 `"Skipped checkpoint state for operator ..."`，State 永远不会恢复

反过来，新 Job 的算子在 Savepoint 中找不到匹配 State 时，该算子从空 State 启动——这是"改了 uid 导致状态丢失"的根因。

### 14.3.5 State Processor API 的详细用法

State Processor API 位于 `flink-state-processing-api` 模块，提供 `SavepointReader` 和 `SavepointWriter` 两个入口。

**读取**：`SavepointReader.read(env, path)` 加载 Savepoint，支持 `readListState()`、`readUnionState()`、`readBroadcastState()`、`readKeyedState()` 四种读取方式，通过 `OperatorIdentifier.forUid()` 或 `OperatorIdentifier.forUidHash()` 定位算子。

**写入/修改**：`SavepointWriter.fromExistingSavepoint(env, path)` 加载已有 Savepoint，支持 `removeOperator()`（删除算子 State）、`withOperator()`（添加新算子 State）、`changeOperatorIdentifier()`（修改算子标识符——元数据级操作，不涉及 State 数据读写）、`write(path)`（写出新 Savepoint）。

`changeOperatorIdentifier()` 的典型用例：给从未设过 UID 的算子补上 UID，避免因拓扑变化导致 ID 偏移。

---

## 14.4 — 横向对比（Spark / StarRocks / MaxCompute）

### vs Spark Structured Streaming

Spark SS 没有独立的 Savepoint——Checkpoint 同时用作恢复和升级。这看似简单，实际将"格式稳定性"和"性能"的矛盾合二为一：每次 Spark 版本升级都可能遇到 Checkpoint 格式不兼容。Flink 通过分离避免了这个矛盾，但代价是多维护一套 Savepoint 格式。

### vs Kafka Streams 的 State Store 迁移

Kafka Streams 的 State 存于本地 RocksDB + Changelog Topic，滚动升级不需停机（新实例加入 Consumer Group 自动接管 Partition 和 State）。但代价是没有全局一致快照，无法做 A/B 测试。Flink 的 Savepoint 是全局一致快照，支持 A/B 测试，但升级需要停机。

### vs MaxCompute

MaxCompute 无状态——升级只是换 UDF/UDAF 版本，不需要"恢复状态"。简单性来自"无状态"前提：每次执行从存储重新读数据。流式计算的状态跨越时间，Kafka 数据会过期，无法"重建"——这正是 Savepoint 存在的根本理由。

### vs StarRocks

StarRocks 遇到 Schema 变更时通常重建物化视图——OLAP 场景下可行，因为数据源持久。Flink 的 State 是瞬时的，无法重建，只能通过 `TypeSerializerSnapshot` 做增量兼容或 State Processor API 做离线迁移。

---

## 14.5 — 调优与实战陷阱

### 改了 uid 导致状态丢失

改了 `.uid()` 后 Flink 认为是新算子，旧 State 无法恢复。更危险的是：不设 UID 时，插入/删除算子会导致下游所有 ID 变化。

**运维层面的 UID 法规**：
1. 每个算子从第一天就设 uid 且永不改变
2. 开启 `pipeline.auto-generated-uids.allowed: false`，强制设 UID（`<org.apache.flink.streaming.api.graph.StreamGraphGenerator:L#557>` 中的检查）
3. 代码 Review 检查 `.uid()` 变更

### 不兼容的 Schema 变更处理

`TypeSerializerSnapshot` 可处理"加字段"（COMPATIBLE_AFTER_MIGRATION），但无法处理：字段类型改变、字段删除、类名变更。应对策略：
1. **加字段**：直接升级，Flink 自动迁移
2. **改类型/删字段**：用 State Processor API 离线读取 → 转换 → 写入新 Savepoint
3. **终极方案**：新建 State（新名称/新 UID），旧 State 保留但不再使用

### Savepoint 文件损坏的恢复

`_metadata` 是单一入口——损坏则整个 Savepoint 不可用。预防：使用 HDFS 副本、定期用 `SavepointReader.read()` 验证完整性、重要升级前保留多份 Savepoint。

### 大 State 的 Savepoint 耗时优化

1. 使用 Canonical Format（`SavepointFormatType.CANONICAL`），输出更紧凑
2. RocksDB 增量 Checkpoint 减少日常数据量，降低紧急 Savepoint 时的同步开销
3. 更多并行度 → 每个 SubTask State 更小 → barrier 对齐更快
4. 使用 `stop-with-savepoint --drain` 优雅停止

### 升级时并行度变更对 State 的影响

- **Keyed State**：基于 KeyGroup 分配，天然支持 rescale。`maxParallelism` 不变即可在任意并行度间迁移
- **Operator State**：`ListState` 按 round-robin 分配，`UnionState` 全量广播到所有 SubTask
- **maxParallelism 不能降低**：降低会抛异常。建议首次部署设足够大的 maxParallelism（如 4096），为扩容预留空间

---

## 本章要点回顾

1. Checkpoint = 内部故障恢复，自动清理；Savepoint = 用户触发的持久快照，格式稳定，数据自包含。
2. `OperatorID`（UID）是 State 的锚点——升级中不变才能恢复正确的 State。生产环境必须为每个算子显式设 UID。
3. `TypeSerializerSnapshot` 是 Schema Evolution 的协议——四级兼容性判断实现序列化格式的增量兼容。
4. Savepoint 触发复用 Checkpoint 链路，通过 `CheckpointProperties.forSavepoint()` 关闭所有自动清理标志。
5. State Processor API 允许离线操作 Savepoint——不经 Job 的 State 修改、分析与 UID 变更。
6. Flink 的 Savepoint 机制在"格式稳定性"和"升级灵活性"上优于 Spark SS 和 Kafka Streams，这是流式引擎有状态计算的必然要求。

## 源码导航

- `CheckpointCoordinator.triggerSavepoint()`：`org.apache.flink.runtime.checkpoint.CheckpointCoordinator`
- `CheckpointProperties.forSavepoint()`：`org.apache.flink.runtime.checkpoint.CheckpointProperties`
- `SavepointType`：`org.apache.flink.runtime.checkpoint.SavepointType`
- `OperatorID`：`org.apache.flink.runtime.jobgraph.OperatorID`
- `OperatorIDPair`：`org.apache.flink.runtime.OperatorIDPair`
- `StreamGraphHasherV2`：`org.apache.flink.streaming.api.graph.StreamGraphHasherV2`
- `TypeSerializerSnapshot`：`org.apache.flink.api.common.typeutils.TypeSerializerSnapshot`
- `TypeSerializerSchemaCompatibility`：`org.apache.flink.api.common.typeutils.TypeSerializerSchemaCompatibility`
- `OperatorState`：`org.apache.flink.runtime.checkpoint.OperatorState`
- `OperatorSubtaskState`：`org.apache.flink.runtime.checkpoint.OperatorSubtaskState`
- `CheckpointMetadata`：`org.apache.flink.runtime.checkpoint.metadata.CheckpointMetadata`
- `MetadataSerializers`：`org.apache.flink.runtime.checkpoint.metadata.MetadataSerializers`
- `StateAssignmentOperation`：`org.apache.flink.runtime.checkpoint.StateAssignmentOperation`
- `SavepointRestoreSettings`：`org.apache.flink.runtime.jobgraph.SavepointRestoreSettings`
- `RecoveryClaimMode`：`org.apache.flink.core.execution.RecoveryClaimMode`
- `SavepointHandlers`：`org.apache.flink.runtime.rest.handler.job.savepoints.SavepointHandlers`
- `SavepointReader`：`org.apache.flink.state.api.SavepointReader`
- `SavepointWriter`：`org.apache.flink.state.api.SavepointWriter`
- `OperatorIdentifier`：`org.apache.flink.state.api.OperatorIdentifier`
