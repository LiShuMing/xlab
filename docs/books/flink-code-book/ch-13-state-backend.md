# 第 13 章 · State Backend：可插拔的状态存储

## 导读

- **一句话**：本章展示 Flink 的 State Backend 插拔体系——Heap、RocksDB、ForSt 三种后端各自的设计哲学和关键实现细节。
- **前置知识**：第 12 章 Checkpoint 概念、LSM-Tree 基本原理。
- **读完本章你能回答**：
  - 三个 State Backend 的内部数据结构差异在哪
  - `KeyedStateBackend` 的 Key-Group 分割是一个怎样的 hash 机制；怎么支持 Rescale
  - RocksDB 在 Flink 中被怎样专门定制——有哪些跟标准 RocksDB 不同的地方
  - State TTL（Time-to-Live）的实现用了什么数据结构

---

## 13.1 — 设计动机：状态存储的决定涉及四个矛盾

| 矛盾 | Heap | RocksDB |
|------|------|---------|
| **大小** | 局限于堆内存（GB 级） | 单机 TB+（LSM-Tree 外存） |
| **速度（读/写）** | 最快 ─ 纯内存 hash map | 内存 + 磁盘，受限于 LSM-Tree R/W |
| **恢复延迟** | 需要从 DFS 下载文件，完整重载 | 增量恢复，Local Dir 留存后直接复用 |
| **GC 影响** | 状态大小决定 GC 压力 | 大多不碰 Java heap |

---

## 13.2 — State Backend 接口

```
StateBackend
├── createKeyedStateBackend()   ← Keyed State 后端
├── createOperatorStateBackend() ← Operator State 后端
└── Checkpoint/Savepoint 支持
```

`Keyed State` — 每 Key 有独立的状态（ValueState、ListState、MapState）
`Operator State` — 算子级别的状态（如 Source offset、Broadcast state）

源码入口：`flink-runtime/.../state/StateBackend.java`

---

## 13.3 — KeyGroup：Hash-Sliced Key Space

### 为什么需要 KeyGroup

Keyed State 需要按 key 分区到各 Slot。如果直接用 `key.hashCode() % parallelism` —— 并行度变了就得重新分区所有 Key。

Flink 提出了 KeyGroup 这个中间层：

```
key → (murmurHash(key) → KeyGroupIndex) → SlotIndex

KeyGroup 总数 = maxParallelism（创建时固定，通常 128~32768）

Rescale 时：
  old: KeyGroup 0..127 分配给 4 个 Slot
  new: KeyGroup 0..127 分配给 8 个 Slot
  → State 不需要重新分区！只需改变 KeyGroup→Slot 的映射
```

`KeyGroupsStateHandle` 存储的也是一个 `KeyGroupRange` 标记它包含哪部分 Key 的状态数据。Rescale 只是重新映射 KeyGroup→Slot，不需要 touch 任何 state 文件。

源码入口：`flink-runtime/.../state/KeyGroupRange.java`

---

## 13.4 — HeapKeyedStateBackend：纯内存哈希表

### 数据结构

```
HeapKeyedStateBackend
  ├── keyGroupRange: 本 Task 负责的 KeyGroup 范围
  ├── StateTable (每个 State): 
  │   ├── StateMap<KeyGroup, Key, State> 
  │   └── 可选：同步 Checkpoint 时做 Copy-On-Write
  └── 无 TTL 机制 → 用 TtlStateContext 包装
```

Keys 被打散在内存中的一个接近"HashMap<KeyGroup, HashMap<Key, Value>>"的结构中。对于轻度状态（百万 Key 以内，每 Key 几 KB），Heap memory 足够快。

源吗入口：`flink-runtime/.../state/heap/HeapKeyedStateBackend.java`

### Copy-on-Write 优化

老版本 Heap backend 的 Checkpoint 是一条**暂停所有写锁，等完整上传完**的阻塞路径。后来引入 CoW：
- Checkpoint 时异步复制一份快照 hash table
- 写入过程可以继续——写的修改在另一张表中（活跃表），等待异步上传的旧表完成再释放

---

## 13.5 — RocksDBStateBackend：LSM-Tree 下的 State

### 适配上的关键定制

```
每个 KeyedStateBackend 包含一个 RocksDB 实例
  ├── ColumnFamily per State Descriptor（每个 ValueState/ListState 对应一个 CF）
  ├── Write Buffer = Managed Memory 中分配
  ├── Block Cache = Managed Memory 中分配
  └── 本地 State 目录 = Local FileSystem（SSD 优先）
```

**定制 1**：写路径不经过 WAL——Checkpoint 就是 Full Backup + Incremental。否则就是双写。

**定制 2**：Value 的序列化是两层——RocksDB Key = <KeyGroup, Key, Namespace> (Composite)，Value = Flink 自己的 binary state value。

**定制 3**：Checkpoint 转成增量——Distributed FileSystem 上传 SST File，且仅上传变化了的新文件（`IncrementalLocalKeyedStateHandle`）。

源码入口：
- `flink-statebackend-rocksdb/.../state/rocksdb/RocksDBKeyedStateBackend.java`
- `flink-statebackend-rocksdb/.../state/rocksdb/RocksDBStateBackend.java`

### 针对 HDD vs SSD 的配置差异

HDD 环境：更小 write buffer、更小 block cache
SSD 环境：最大化 block cache 以减少读盘延迟

---

## 13.6 — ForSt State Backend：新一代 LSM

ForSt 是 Flink 社区正在投入的新 LSM-backend（替代 RocksDB）：

- 更轻量的 LSM-Tree（面向嵌入式场景而非数据库场景）
- Java/Scala 友好集成
- 针对小 Key/Value 的优化（Flink State 的典型特点）

源码入口：`flink-state-backends/flink-statebackend-forst/`

---

## 13.7 — State TTL（Time-to-Live）机制

### 设计

Flink State TTL 不是"懒删除"也不是"全量扫描"。结合了两个思路：

```java
// 用户视角：每条 Key 的 Value 存活 TTL 时间
StateTtlConfig ttlConfig = StateTtlConfig
    .newBuilder(Time.hours(24))
    .setUpdateType(StateTtlConfig.UpdateType.OnCreateAndWrite)
    .setStateVisibility(StateTtlConfig.StateVisibility.NeverReturnExpired)
    .build();
```

### 内部实现

```
每个 State 由一个 TtlValue<SV> 包装
  └── TtlValue { SV userValue; long lastAccessTimestamp; }

StateTable<TtlValue<SV>>
  ├── 全量 Compact（Checkpoint 时触发）┐
  ├── Incremental Cleanup（每次访问 Key时）┘
  └── RocksDB CompactionFilter 出击
```

**Incremental Cleanup**：每次访问 Key 时，检查 `lastAccessTimestamp` 是否过期——过期就立即清除。

**RocksDB CompactionFilter**：RocksDB 底层 Compaction 时，调用 Flink 自己的 `TtlCompactionFilter` 判定该 Key 是否过期——用 SST 文件合并的方式批量清理。

源码入口：`flink-runtime/.../state/ttl/TtlStateContext.java`

---

## 13.8 — 横向对比

### vs Spark State Store

Spark 没有内置的 State Backend——State 直接使用自容错的 GroupState (mapGroupsWithState)。State 集成在 RocksDB/内存中以 `HDFSBackedStateStore` 形式，但不是一个完整可换的 Backend API。Flink 的 API 和插拔体系更干净、更肆意。

### vs Flink State V2（FLIP-477：ForSt/New State API）

最新版 Flink 中有一个 `state.v2` 包——这是未来 State API 的演进方向。它在 `flink-runtime/.../state/v2` 下面，计划解决：
- 免锁的 Forget/异步快照分离
- 更好的 Rescale 支持
- 对 KV 优化的二进制协议

---

## 调优与实战陷阱

### OOM：RocksDB 占太多 Managed Memory

RocksDB 的 block cache 对缓存命中率至关重要——但如果全分配成 block cache，写缓冲不够 → MemTable 频繁刷 → Compaction 爆炸。

公式：WriteBuffer = Managed Memory * 0.5, BlockCache = Managed Memory * 0.3, 其余给 OS 页缓存。

### 批量读效率

如果需要扫全部 Key（如 Iterate over MapState），**避免**在 Task 中直接 for-loops 从头 iterate → 会阻塞整个 Task 的 mailbox（因为它同步在算子线程里做）。换成分批增量读取。

### Rescale 时的 State 放大

如果 `maxParallelism` 设很小（例如 128），但要 Rescale 到 256 并行度——单个 Slot 的 KeyGroup 数量成倍增加到跨倍数。这会导致 Restore 时每个 Slot 收到更多 State Handle → 恢复时间变成 N 倍。一开始就把 `maxParallelism` 设够大（至少 2048 或 4096）。

---

## 本章要点回顾

1. State Backend 的插拔核心是 `KeyedStateBackend` 和 `OperatorStateBackend` 的创建接口。
2. KeyGroup 是 parallel 变更时 State 不被重新分片的关键。
3. Heap Backend = 内存 HashMap + CoW 快照；RocksDB Backend = LSM-Tree + 增量 Checkpoint。
4. State TTL 结合 incremental cleanup + CompactionFilter 实现高效清理。

## 源码导航

- StateBackend 接口：`flink-runtime/.../state/StateBackend.java`
- HeapKeyedStateBackend：`flink-runtime/.../state/heap/HeapKeyedStateBackend.java`
- RocksDBKeyedStateBackend：`flink-statebackend-rocksdb/.../state/rocksdb/RocksDBKeyedStateBackend.java`
- State V2：`flink-runtime/.../state/v2/`
- TTL：`flink-runtime/.../state/ttl/`
- KeyGroupRange：`flink-runtime/.../state/KeyGroupRange.java`
