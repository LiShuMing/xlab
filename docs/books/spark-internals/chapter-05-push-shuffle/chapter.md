# 第 5 章：Push-based Shuffle — 服务端合并的写路径

## 设计动机

传统的 Shuffle 模型是 **Pull-based**：M 个 Mapper 各自将 partition N 的数据写到本地磁盘，Reducer 通过网络从 M 个节点拉取。这个模型在 Google MapReduce 论文中定义，在 Hadoop 和 Spark 中沿用了近 20 年，但它有一个根本的扩展性问题：

**Shuffle Read 的连接数 = Mappers × Reducers**

对于 5000 个 Mapper × 2000 个 Reducer 的 Shuffle，如果无优化，就是 1000 万次连接。即使有 `maxReqsInFlight` 流控和 batch fetch 合并，Reducer 仍然需要处理小块的随机 I/O——因为每个 Mapper 的 partition 可能只有几 KB 到几 MB。小块随机 I/O 对 HDD 是灾难性的（~1MB/s），对 NVMe SSD 也不同程度地产生 IOPS 压力。

Push-based Shuffle 翻转了这个模型：**Mapper 不等待 Reducer 来拉，而是主动把数据"推"到远程 Shuffle Service**。Shuffle Service 负责把同一个 partition 的多份数据在服务端合并成一个大文件。Reducer 只需要从 Shuffle Service 顺序读一个大文件——**每个 partition 的数据是连续的**。

```
Pull 模型:                       Push 模型:
Mapper-1 → write to disk         Mapper-1 → push → Shuffle Service ─┐
Mapper-2 → write to disk         Mapper-2 → push → Shuffle Service ─┤ merge partition N
Mapper-3 → write to disk         Mapper-3 → push → Shuffle Service ─┘
  ↓                                   ↓
Reducer-1 ← fetch from 3 nodes    Reducer-1 ← sequential read 1 big file (from any Shuffle Service)
```

这个模型将 Shuffle Read 的复杂度从 **M × R 次随机小 I/O** 降低到 **R 次顺序大 I/O**。

Spark 从 3.2 开始引入 Push-based Shuffle，它与其他 push-based 方案（Celeborn、Uniffle）的核心差异是：**不引入额外集群，直接复用 External Shuffle Service**。

## 核心原理

### 5.1 Push-based Shuffle 的完整数据流

```
阶段 1: Mapper 执行 Shuffle Write
  - 使用 UnsafeShuffleWriter 或 SortShuffleWriter 正常写出 (同传统 Shuffle)
  - SHUFFLE_SHUFFLE_MERGE_ALLOWED = true → 标记可以向 Shuffle Service push

阶段 2: Mapper push 数据到 Shuffle Service
  - ShuffleBlockPusher: 每个 Mapper 完成后, 异步将各 partition 数据 push 到 Shuffle Service
  - push 对象: partition 的序列化数据 (或 spill file 的 partition 段)
  - 使用 OneForOneBlockPusher: 每个 partition block 发送一个 PushBlockStream 消息

阶段 3: Shuffle Service 服务端合并
  - RemoteBlockPushResolver: 接收 push blocks, 按 (shuffleId, partition) 分组
  - 将同 partition 的多个 block 追加到同一个 merged shuffle file
  - 记录 meta: 每个 block 的 chunk offset + length

阶段 4: Finalize
  - Mapper 全部完成后, driver 向 Shuffle Services 发送 FinalizeShuffleMerge
  - Shuffle Service: 将 merged file 的 meta 写入磁盘
  - 返回 MergeStatuses: (shuffleId, partition, merged file path, chunk offsets)

阶段 5: Reducer 读取
  - MapOutputTracker 返回 push-based 的 blocksByAddress (已合并的)
  - Reducer 向 Shuffle Service 请求: GET merged shuffle file, partition range
  - 顺序读取大文件, 无需处理小块随机 I/O
```

### 5.2 RemoteBlockPushResolver — 服务端合并引擎

`RemoteBlockPushResolver` 运行在 Shuffle Service（External Shuffle Service 或内置的 BlockManager）中，负责接收和处理 push 过来的 shuffle blocks：

```java
// RemoteBlockPushResolver.java
// 核心方法:
// 1. receiveBlockPush: 接收 Mapper push 来的 blocks
// 2. finalizeShuffleMerge: 完成合并, 写出 meta 文件

// 内部维护状态:
Map<AppShufflePartitionId, MergedPartitionInfo> partitionInfoMap;
// AppShufflePartitionId = (appId, shuffleId, partitionId)
// MergedPartitionInfo: 记录该 partition 的合并文件 + 所有 chunk offsets
```

**Push 块的接收过程**：

```
1. Mapper 发送 PushBlockStream(appId, shuffleId, mapId, partitionId, data)
2. RemoteBlockPushResolver 收到:
   - 查找或创建对应的 MergedPartitionInfo
   - 将 data 追加写入 merged shuffle file 的尾部
   - 记录此 chunk 的 offset 和 length
   - 周期性 flush buffer
3. 返回 BlockPushReturnCode.SUCCESS 给 Mapper
4. Mapper 完成后: driver 发送 FinalizeShuffleMerge
5. RemoteBlockPushResolver.finalizeShuffleMerge:
   - 将所有 MergedPartitionInfo 的 meta 序列化为 MergedBlocksMeta
   - 写出 meta 文件 (与 merged file 同目录)
```

**Merged Shuffle File 的格式**：

```
merged shuffle file (per Shuffle Service, per shuffleId):
  [MergedBlocksMeta header: partition offsets]
  [partition 0 data: chunk0 | chunk1 | chunk2 ...]
  [partition 1 data: chunk0 | chunk1 ...]
  ...

meta 文件 (同目录):
  for each partition: [numChunks][for each chunk: chunkOffset, chunkLength]
```

Reducer 读取时：MapOutputTracker → 查询 `getPushBasedShuffleMapSizesByExecutorId` → 返回 (ShuffleServiceId, MergedBlock chunk 列表) → Reducer 直接按 (file path, offset, length) 读取。

### 5.3 ShuffleBlockPusher — Mapper 端的推送引擎

`ShuffleBlockPusher` 运行在 Mapper 端，负责将 Shuffle Write 完成的 partition 数据推送到选定的 Shuffle Service：

```scala
// ShuffleBlockPusher.scala
class ShuffleBlockPusher(conf: SparkConf) {
  // 1. 初始化: 从 driver 获取 Shuffle Services 列表
  // 2. 挑选策略: 按 partition 的 hash 分散到不同的 Shuffle Service
  //    例如: partition 0, 3, 6 → Service-A; partition 1, 4, 7 → Service-B
  // 3. 推送: 异步并发推送
  //    使用 OneForOneBlockPusher → 通过 TransportClient 发送 PushBlockStream
}
```

**与 UnsafeShuffleWriter 的集成**：

Mapper 使用 UnsafeShuffleWriter 完成 Shuffle Write 后，不直接把数据交给 Reducer（pull 模式），而是检查 `isShuffleMergeAllowed` 标志：

- 如果 `shuffleMergeAllowed = true` → 调用 `ShuffleBlockPusher.pushBlocks()`
- push 完成后 → Mapper 向 driver 报告 push success（`MapStatus` 包含 `mergeStatus`）
- Driver 的 `DAGScheduler` 收集所有 Mapper 的 merge status，当全部完成时发送 `FinalizeShuffleMerge`

### 5.4 数据分配 — 哪份数据推到哪个 Shuffle Service

Push-based Shuffle 的一个关键决策是**数据分散策略**。同一个 partition 的多个 Mapper 的数据可能分别推向不同的 Shuffle Service，也可能集中在同一个：

```
策略 A: 分散推 (Reduce data skew)
  partition 5:
    Mapper-1 → Service-A (merged file A/partition5: [chunk from mapper-1])
    Mapper-2 → Service-B (merged file B/partition5: [chunk from mapper-2])
    Mapper-3 → Service-C (merged file C/partition5: [chunk from mapper-3])
  Reducer-5: 需要从 Service-A, B, C 各读一个 chunk

策略 B: 集中推 (Minimize reads)
  partition 5:
    Mapper-1 → Service-A (merged file A/partition5: [chunks from all mappers])
    Mapper-2 → Service-A
    Mapper-3 → Service-A
  Reducer-5: 只需从 Service-A 读一个连续段
```

Spark 默认为 **每个 Mapper 的同一个 partition 数据随机选择一个 Shuffle Service**（通过 `pushBasedShuffleReplicate` 控制）。这平衡了 Server 侧的负载和 Reducer 的读取效率。

**分配算法**：对 partition `p` 的每个 Mapper `m`，选择 Shuffle Service `hash(p, m) % numServices`。这确保了"同一 partition 的不同 Mapper 不会全推向同一 Service"（防止单个 Service 的合并文件过大）。

### 5.5 Finalize — 从 Push 阶段到 Read 阶段的转换

Finalize 是 Push-based Shuffle 最关键的控制点——它将"正在写入"的合并文件变为"可读取"的完成文件。

```
Driver (DAGScheduler):
  - 监听 Stage 中所有 Mapper 的完成事件
  - 当所有 Mapper 完成后:
    - 收集所有 Mapper 的 MergeStatus (哪些 partition 被推到了哪些 Service)
    - 向每个参与的 Shuffle Service 发送 FinalizeShuffleMerge 消息
    - 等待所有 Shuffle Services 返回 MergeStatuses
  - 聚合 MergeStatuses → 发给 Reducer (通过 MapOutputTracker)
  - Reducer 的 MapOutputTracker 返回 push-based block 位置
```

```java
// RemoteBlockPushResolver.finalizeShuffleMerge:
public MergeStatuses finalizeShuffleMerge(FinalizeShuffleMerge msg) {
  // msg 包含: appId, shuffleId, 每个 mapper 的 merge info
  // 1. 根据 msg 确认哪些 partitions 无更多 blocks 将被推送
  // 2. 将所有 MergedPartitionInfo 序列化为 MergedBlocksMeta
  // 3. 写出 meta 文件到磁盘
  // 4. 返回 MergeStatuses (列出所有已完成的 partitions)
}
```

Finalize 之后，Shuffle Service 将 clearing 的任务标记为"当前 shuffle 的 merged files 可安全删除"——在后续的 `ContextCleaner` 或定期清理中执行。

### 5.6 Push-based Shuffle 的错误处理

Push-based Shuffle 特有的错误模式是 **部分 push 失败**——某个 Mapper 成功 push 了 3 个 partition 但第 4 个 push 因为网络错误失败了：

```
处理策略:
  - 失败的 push 不重试 (由 push retry 机制处理, 默认最多 1 次重试)
  - 当 mapper 最终仍然有 push 失败的 partition:
    - 这个 partition 的数据按传统 pull 方式处理 (Mapper 将其作为普通 shuffle data 保留)
    - MapOutputTracker 中标记该 partition 部分来自 push-based, 部分来自 pull
  - Reducer: 对混合来源的 partition 做合并
```

这是渐进增强（graceful degradation）——Push 优化可选的，失败也不影响正确性。

### 5.7 对标：Celeborn / Uniffle

Push-based Shuffle 不是 Spark 独有的概念。Celeborn（阿里开源）和 Uniffle（腾讯开源）是独立的 Shuffle Service 集群，与 Spark 的 push-based shuffle 共享相同的"push + merge"范式：

| 维度 | Spark Push-based Shuffle | Celeborn / Uniffle |
|------|-------------------------|---------------------|
| 部署 | 复用 External Shuffle Service | 独立集群 (CelebornWorker / ShuffleServer) |
| Shuffle 存储 | 本地磁盘 | 独立存储节点（可多副本） |
| 容错 | Graceful fallback to pull | 多副本保证不丢数据 |
| 数据倾斜控制 | Mapper 随机分配 | Partition 重新分配 (repartition) |
| I/O 模式 | 服务端合并 → 顺序读 | 服务端合并 → 顺序读 (可预取) |

Celeborn/Uniffle 的独立存储架构意味着"Shuffle 数据与计算节点分离"——当 Executor 被 decommissioned 或崩溃时，Shuffle 数据仍然在 Shuffle Service 上可用。这解决了"Shuffle 数据丢失导致 Stage 重算"的经典痛点。

## 关键代码片段

### 示例：Push vs Pull 的配置

```scala
// 启用 Push-based Shuffle:
spark.shuffle.push.enabled = true

// 合并条件: Merger 的数量
spark.shuffle.push.mergers.minThreshold = 100  // 至少 100 个 mapper 才启用 push
// 因为 mappers < 100 时, pull 的直接拉取通常更高效

// Push 重试:
spark.shuffle.push.maxRetainSize = Int.MaxValue  // 失败后保留的 shuffle 数据大小
// 如果 push 失败, Mapper 保留数据在本地, 且大小不超过此值时保留
```

## 硬件视角

**Push-based Shuffle 对 I/O 模式的根本改变**：

传统 pull 模型中，Reducer 的磁盘 I/O 是随机小块读：
```
Reducer 读取 partition 5:
  → HTTP GET Mapper-1:  fetch 3KB from offset 2048
  → HTTP GET Mapper-2:  fetch 5KB from offset 4096
  → HTTP GET Mapper-3:  fetch 2KB from offset 1024
  → ... (5000 次随机 fetch)
```

Push-based 模型中，Reducer 的磁盘 I/O 是顺序大块读：
```
Reducer 读取 partition 5:
  → HTTP GET ShuffleService-A: fetch merged file, from offset 10MB, length 25MB
  → DONE (只需要 1 次 fetch)
```

这意味着：
- HDD：Pull 模型几乎不可用（随机 1MB/s → 5000 次 × 5KB ≈ 25 秒，但实际随机 I/O 的 head seek 使总时间 > 100 秒），Push 模型顺序 150MB/s × 25MB ≈ 0.16 秒
- NVMe SSD：Pull 模型仍然有效（随机 1000MB/s），但 IOPS 压力大（5000 次队列深度 → 增加延迟）。Push 模型减少 IOPS → 顺序 3000MB/s

**Push 端网络开销**：

Push 模型增加了 Mapper → Shuffle Service 的网络传输（本来 Mapper 只写本地磁盘，现在还要发到远程）。这部分网络开销与 Shuffle Write 数据大小成正比。

但在 Mapper 运行期间，Mapper 的 CPU/磁盘已经在工作——写入 push 数据是"在已有 I/O 上 piggyback 的额外网络传输"。如果 Mapper 的磁盘写入是瓶颈，push 不会增加执行时间（因为网络和磁盘可以并行）。

**内存压力**：

Shuffle Service 需要内存来缓存接收到的 push blocks（在 flush 到合并文件之前）。合并文件本身也需要 buffer（write buffer）。但 Shuffle Service 的内存压力远远低于 Mapper/Reducer 的聚合 hash table 压力——因为 Shuffle Service 不需要做 `combineByKey`——它只是追加字节。

## AI 时代反思

Push-based Shuffle 是 LLM 训练数据中的一个"低覆盖区"——它是相对较新的特性（2021 年引入），公开技术文章的覆盖远少于传统的 Sort-based Shuffle。大多数 LLM 只能描述"push 模型减少小文件读取"的高层次含义，但无法解释 `RemoteBlockPushResolver` 的 chunk 管理或 Finalize 的两阶段提交语义。

这为 LLM Agent 的"增量学习"提供了一个好场景：Agent 在用户的集群环境中工作，通过读取 shuffle service 的 metrics（push block rate, merge latency, finalize time），逐步积累"这些指标在健康和不健康状态下的值"。经过 50-100 个生产查询后，Agent 可以建立内部的 baseline，然后检测异常。

这种"现场学习"（in-situ learning）模式与 LLM 的预训练是互补的——LLM 提供"概念框架"（知道 push-based shuffle 做什么），而现场学习提供"当前集群的实际情况"（这个集群的 push block latency baseline 是 5ms，现在变成 50ms → 某台 Shuffle Service 的磁盘有故障）。

另一个值得探索的方向：**LLM 是否可以自动调度 Celebrborn vs Spark Push-based Shuffle 的选择？** 两者各有优势：
- Spark Push-based：无需额外集群，适用 Shuffle 数据 < 1TB 的场景
- Celebrborn/Uniffle：独立的 Shuffle 集群，适用 Shuffle 数据 > 1TB 或需要高可用的场景

LLM 可以分析查询模式（Shuffle 数据量、frequency、重要性），提供"你的下一个查询应该用 Celebrborn 作为 Shuffle Service 因为 Shuffle 数据预计会超过 2TB"的建议——这是一种"基于历史查询模式的服务推荐"，类似于云负载的 service tier 推荐。

## 源码导航

| 文件 | 关键内容 | 行号参考 |
|------|---------|---------|
| `common/network-shuffle/src/main/java/org/apache/spark/network/shuffle/RemoteBlockPushResolver.java` | RemoteBlockPushResolver，push block 接收，合并文件管理，finalizeShuffleMerge 两阶段提交 | |
| `core/src/main/scala/org/apache/spark/shuffle/ShuffleBlockPusher.scala` | ShuffleBlockPusher，Mapper 端 push 引擎，Shuffle Service 选择策略，push retry | |
| `common/network-shuffle/src/main/java/org/apache/spark/network/shuffle/OneForOneBlockPusher.java` | OneForOneBlockPusher，单个 block push 的传输客户端 | |
| `common/network-shuffle/src/main/java/org/apache/spark/network/shuffle/MergedBlockMeta.java` | MergedBlockMeta，合并后块的元数据格式 | |
| `core/src/main/scala/org/apache/spark/storage/PushBasedFetchHelper.scala` | PushBasedFetchHelper，Reducer 端的 push-based block 读取辅助 | |
| `core/src/main/scala/org/apache/spark/MapOutputTracker.scala` | getPushBasedShuffleMapSizesByExecutorId，push-based 数据位置 | |
