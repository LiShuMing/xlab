# 第 19 章：BlockManager — 统一块存储的 Master-Slave 架构

## 设计动机

计算引擎中有一类常见的"基础设施型"组件——它们不直接参与 SQL 优化或算子执行，但对性能有根本性影响。BlockManager 就是这样的组件。它要解决的核心问题是：**同一个数据块（Block）可能存在于内存、磁盘、远程节点三个地方——谁来管理这些副本的一致性、可见性和生命周期？**

BlockManager 设计的精妙在于"Unified Block Abstraction"——不管是 RDD partition、Shuffle Block、Broadcast variable 还是 Task 结果，都抽象为 `BlockId`，由 BlockManager 统一定位、存储和传输。这种统一的抽象消除了"每种数据类型一个独立存储系统"的复杂性。

```
数据类型            BlockId                   存储位置
──────────────────────────────────────────────────────────
RDD partition       rdd_0_5                   Memory/Disk
Shuffle block       shuffle_0_3_5             Local disk
Broadcast var       broadcast_0               Memory/Disk (分布式)
Shuffle index       shuffle_0_3_0.index       Local disk
Task result         taskresult_123            Memory
Temp/Streaming      temp_*                    Memory/Disk
```

BlockManager 采用经典的 **Master-Slave 架构**：
- `BlockManagerMaster`（Driver 端）：持有全局元数据——哪个 Block 在哪个 Executor 的哪个 StorageLevel
- `BlockManager`（Executor/Driver 端）：实际的存储 + 传输操作——doPut/doGet/replicate/evict

## 核心原理

### 19.1 BlockId — 统一块标识

`BlockId` 是一个 sealed abstract class，针对不同的数据来源有不同的子类型：

```scala
sealed abstract class BlockId {
  def name: String  // 全局唯一标识，可序列化
  def isRDD: Boolean
  def isShuffle: Boolean
  def isBroadcast: Boolean
}

// 核心子类型:
case class RDDBlockId(rddId: Int, splitIndex: Int)           // "rdd_0_5"
case class ShuffleBlockId(shuffleId: Int, mapId: Long, reduceId: Int)  // "shuffle_0_3_5"
case class ShuffleBlockChunkId(shuffleId, shuffleMergeId, reduceId, chunkId) // push-based merge
case class BroadcastBlockId(broadcastId: Long, field: String) // "broadcast_0"
case class TaskResultBlockId(taskId: Long)                    // "taskresult_123"
case class TempLocalBlockId(id: UUID)                         // "temp_local_..."
```

`BlockId.name` 的命名规范直接决定了 `ExternalShuffleBlockResolver` 如何进行文件定位——文件名就是从 `name` 字段构建的（如 `shuffle_0_3_0.data`）。

### 19.2 BlockInfoManager — 块级读写的并发控制

`BlockInfoManager` 提供了 Block 级别的 **读写锁**。每个 Block 都有一个 `BlockInfo` 对象，记录其 StorageLevel、ClassTag 和锁状态：

```
Block 生命周期:
  1. lockNewBlockForWriting(blockId, newInfo) → WRITE 锁
     → 独占写入，不能同时有读者
  
  2. 写入完成后 → unlock(blockId) 或 downgradeLock(blockId)
     → unlock: 释放锁 → 后续 get 需要 lockForReading()
     → downgrade: WRITE → READ → 写入者转为读者，仍持有读锁
  
  3. lockForReading(blockId) → READ 锁
     → 共享读取，多个 reader 可以同时持有
```

这个锁的核心设计目的不是"多 Reader 并发"（Spark 很少出现同一 Executor 内多个 Task 同时读取同一个 Block 的场景），而是**确保一个 Block 在被写入期间不会被读取**——"不能看到写到一半的数据"。

### 19.3 写路径 — doPut 的三级存储

`BlockManager.doPut` 是写操作的统一入口。它是一个模板方法，通过 `putBody` 回调将实际的写入逻辑参数化：

```scala
private def doPut[T](
    blockId: BlockId,
    level: StorageLevel,
    classTag: ClassTag[_],
    tellMaster: Boolean,
    keepReadLock: Boolean)(putBody: BlockInfo => Option[T]): Option[T]
```

**StorageLevel** 决定数据放到哪：

| StorageLevel | 位置 | 说明 |
|-------------|------|------|
| MEMORY_ONLY | 内存（反序列化） | Java 对象 |
| MEMORY_ONLY_SER | 内存（序列化） | 字节数组 |
| MEMORY_AND_DISK | 先内存，满了溢写到磁盘 | 默认推荐 |
| DISK_ONLY | 仅磁盘 | 不消耗内存 |
| OFF_HEAP | 堆外内存 | 序列化 |

带有 `_2` 后缀的 level（如 `MEMORY_AND_DISK_2`）表示还要做一个远程副本——`replication = 2`。

**写入流程**：

```
1. blockInfoManager.lockNewBlockForWriting(blockId, newInfo)
   → 检查是否已存在（如果已存在 → 不覆盖，返回 None）
   → 获取 WRITE 锁

2. putBody(info) 调用:
   → 根据 StorageLevel.memoryMode 选择 MemoryStore 还是 DiskStore
   → MemoryStore.putBytes() 或 putIteratorAsValues/putIteratorAsBytes
   → 如果内存不够 → 可能触发驱逐或直接走 disk fallback

3. 如果 level.replication > 1 → replicate()
   → 选择 N-1 个 peer BlockManagers
   → 通过 BlockTransferService 将数据序列化后发送到远程

4. 如果 tellMaster == true:
   → 向 BlockManagerMaster 报告: UpdateBlockInfo(blockId, blockManagerId, level, size)
   → Driver 更新全局元数据

5. unlock 或 downgradeLock（取决于 keepReadLock）
```

`getOrElseUpdateRDDBlock` 是一个特别有趣的方法——当多个 Task 试图获取同一个 RDD block 时，如果 block 不存在（cache miss），多个 Task 可能同时尝试计算并缓存它。BlockManager 通过 `blockInfoManager.lockNewBlockForWriting` 保证**只有一个 Task 会执行真正的计算并缓存**，其他 Task 会阻塞等待 block 可用。

### 19.4 读路径 — 本地到远程的逐级回退

BlockManager 的读取策略是 **本地优先 + 远程回退**：

```
getLocalValues(blockId)
  ├── 1. MemoryStore.getValues(blockId)
  │     → 反序列化内存中的 bytes → Iterator[Any]
  │     → 最快路径: L1/L2/L3 内存访问
  │
  ├── 2. DiskStore.getBytes(blockId)
  │     → 从磁盘读取序列化数据 → 反序列化
  │     → 中等速度: 磁盘 I/O (或 page cache hit)
  │
  └── 3. None (本地无此 block)
        → 调用者走 getRemoteValues(blockId)
          → 从 BlockManagerMaster 获取 block 位置
          → 通过 BlockTransferService 从远程拉取
          → 可以按本地 StorageLevel 缓存拉下来的数据
```

**getOrElseUpdateRDDBlock** — 读取-计算-缓存的三合一模式：

```scala
def getOrElseUpdateRDDBlock[T](
    blockId: RDDBlockId,
    level: StorageLevel,
    classTag: ClassTag[T],
    makeIterator: () => Iterator[T]): Iterator[T] = {
  
  // 先尝试本地读
  getLocalValues(blockId) match {
    case Some(blockResult) => blockResult.data.asInstanceOf[Iterator[T]]
    case None =>
      // 本地无此 block → 尝试远程读？不，RDD 缓存不是分布式的
      // 调用 makeIterator 计算这个 partition
      // 然后将结果按 StorageLevel 缓存
      val iter = makeIterator()
      putIterator(blockId, iter, level, classTag, tellMaster = true)
  }
}
```

这个模式相当于"compute-once + cache + serve"——对 RDD cache 来说至关重要，因为只有第一次访问会触发计算，后续都是缓存命中。

### 19.5 BlockManagerMaster — 全局元数据管理

`BlockManagerMaster` 维护一张全局映射表：`BlockId → Seq[BlockManagerId]`（一个 Block 可能被复制到多个 Executor）。这张表支持：

- **Register**：BlockManager 初始化时注册到 Master
- **UpdateBlockInfo**：写入/删除 Block 时更新位置信息
- **GetLocations**：读取 Block 前查询目标 Executor 列表
- **RemoveBlock / RemoveExecutor**：清理

`BlockManagerMasterEndpoint` 是一个 `IsolatedThreadSafeRpcEndpoint`——Driver 端的 RPC 端点，负责处理所有 BlockManager 的状态更新请求。Isolated 意味着它可以做阻塞操作（不会阻塞其他 Endpoint 的消息处理）。

### 19.6 MemoryStore — 内存中的块存储与驱逐

`MemoryStore` 是 BlockManager 在内存中的存储后端。它内部用一个 `LinkedHashMap[BlockId, MemoryEntry[_]]` 维护所有内存中块的映射，保持 **LRU 访问顺序**：

```
MemoryEntry 的两类:
  SerializedMemoryEntry: 字节数组 → 紧凑，无 GC 压力
  DeserializedMemoryEntry: Java 对象数组 → 快速随机访问，GC 压力大
  
驱逐策略 (evictBlocksToFreeSpace):
  for memoryMode in (ON_HEAP, OFF_HEAP):  ← 分别驱逐
    for block in entries的 LRU 顺序:        ← 从最久未访问的块开始
      记录 blockId 和 size
      如果累计 size >= spaceToFree → break

  对每个记录的 block:
    BlockManager.dropFromMemory(blockId)
      → blockInfoManager.lockForWriting(blockId)
      → MemoryStore.remove(blockId)
      → if StorageLevel.useDisk: DiskStore.put(blockId, data)  ← 溢写至磁盘
      → blockInfoManager.unlock(blockId)
```

LRU 驱逐是一个**全栈过程**——不只是"从内存移除"，还要决定"是否溢写至磁盘"（取决于该 block 的 StorageLevel）。这就是为什么 `.persist(MEMORY_AND_DISK)` 比 `.persist(MEMORY_ONLY)` 更鲁棒——内存满时数据写到磁盘，而不是直接丢弃。

### 19.7 DiskStore / DiskBlockManager — 磁盘上的块管理

`DiskBlockManager` 管理磁盘上的存储目录结构。使用 `localDirs` 数组（由 `spark.local.dir` 或 YARN 的 `yarn.nodemanager.local-dirs` 指定），每个目录下创建可配置数量的子目录（`subDirsPerLocalDir`，默认 64）：

```
localDir[0]/
  subdir_00/
  subdir_01/
  ...
  subdir_63/
localDir[1]/
  subdir_00/
  ...
```

Block 文件的放置通过 `hash(blockId.name) % localDirs.size` 选取目录，通过 `hash(blockId.name) / localDirs.size % subDirsPerLocalDir` 选取子目录——一个简单的两级 hash 将文件分散到所有磁盘。

`DiskStore` 提供 `putBytes` 和 `getBytes` 方法。写入只是简单的文件 I/O，但读取有一个优化：如果数据写入后很快被读取（典型的 Shuffle Write → Shuffle Read 场景），文件内容大概率还在 **OS Page Cache** 中——物理 I/O 零开销。

### 19.8 Block 传输 — 从本地存储到远程节点

当远程节点请求一个 Block 时，请求通过 `BlockManagerStorageEndpoint`（Executor 端的 RPC 端点）进入系统：

```
远程 Reducer 请求 Block:
  1. BlockTransferService.fetchBlocks(host, port, blockIds, listener)
  2. → TransportClient → BlockManagerStorageEndpoint.receive()
  3.   → OpenBlocks(appId, execId, blockIds)
  4.   → BlockManager.getLocalBlockData(blockId):
        → MemoryStore/diskStore → ManagedBuffer
  5.   → OneForOneStreamManager.registerStream(clientId, buffers)
  6.   → 返回 StreamHandle(streamId, numBlocks)
  7. Reducer 端的 TransportClient:
     → fetchChunk(streamId, chunkIndex)
     → 每个 chunk 的 ManagedBuffer 通过 Netty 的 FileRegion.sendfile 发送
```

对于超大 block（超过 `MAX_REMOTE_BLOCK_SIZE_FETCH_TO_MEM`），数据先写到临时的磁盘文件再反序列化——防止大 block 撑爆内存。

### 19.9 Block 复制 — 为容错做冗余

当 `StorageLevel.replication > 1` 时（如 `MEMORY_ONLY_2`），doPut 完成后调用 `replicate()`：

```scala
private def replicate(
    blockId: BlockId,
    data: BlockData,
    level: StorageLevel,
    classTag: ClassTag[_],
    existingReplicas: Set[BlockManagerId]): Unit = {

  // 选择 N-1 个 peer（不在 existingReplicas 中，不是自己）
  val peersForReplication = blockReplicationPolicy.getPeers(
    blockManagerId, cachedPeers, level.replication - 1, existingReplicas)

  // 异步复制到每个 peer
  val futures = peersForReplication.map { peer =>
    Future {
      blockTransferService.uploadBlock(
        peer.host, peer.port, executorId, blockId, data.toNetty, level, classTag)
    }(futureExecutionContext)
  }
  // 等待所有副本完成
  futures.foreach(ThreadUtils.awaitResult(_, ...))
}
```

复制策略（`BlockReplicationPolicy`）允许自定义——默认采用随机选择，保证副本分散在不同节点/机架。

## 关键代码片段

### 示例：getOrElseUpdateRDDBlock 的并发安全性

```
场景: 3 个 Task 尝试访问同一个 RDD partition (rdd_0_5, 未缓存)

Task-1: getOrElseUpdate(rdd_0_5, MEMORY_ONLY, ...)
  → Local read → None
  → blockInfoManager.lockNewBlockForWriting(rdd_0_5, info)
    → 成功！Task-1 持有 WRITE 锁
  → makeIterator() → 真正计算 partition 的数据
  → putBody: MemoryStore.putIteratorAsValues(...)
  → downgradeLock → READ 锁
  → 返回 iterator

Task-2: getOrElseUpdate(rdd_0_5, MEMORY_ONLY, ...)
  → Local read → None
  → blockInfoManager.lockNewBlockForWriting(rdd_0_5, info)
    → 失败！rdd_0_5 已被 Task-1 锁定 → 等待
  → (Task-1 完成后, WRITE 锁释放)
  → Task-2 重新尝试 → Local read → Some
  → 返回 iterator（从缓存, 无需重算）

Task-3: 同 Task-2, 直接缓存命中
```

## 硬件视角

**MemoryStore 驱逐的隐性 I/O**：

当 execution 内存通过 `maybeGrowExecutionPool` 从 storage 回收空间时，触发的是一系列 LRU 驱逐——每个 LRU 块都可能触发 `dropFromMemory`。对于 `MEMORY_AND_DISK` 级别的块，这产生了磁盘写入：

```
execution 需要 500MB
  → storage 驱逐 LRU 块:
    Block-A (200MB, MEMORY_AND_DISK) → write to disk 200MB
    Block-B (150MB, MEMORY_AND_DISK) → write to disk 150MB
    Block-C (180MB, MEMORY_ONLY)     → drop (no disk write)
  累计 disk write: 350MB

如果 Block-A 在 30 秒后被重新访问:
  → disk read 200MB + decompress → back to memory → 200MB 内存带宽
  → 该驱逐-重读周期的总 I/O: 350MB write + 200MB read = 550MB
```

这意味着**storage→execution 的内存借用不是"免费"的**——有真实的 disk I/O 成本。每当 Spill rate > 20% 时，驱逐 + 重新缓存可能比直接 request memory 更昂贵。

**DiskBlockManager 的多磁盘均衡**：

`DiskBlockManager` 通过 hash 将文件分散到不同的 `localDirs`。如果 `localDirs = ["/disk1", "/disk2", "/disk3"]`（3 块独立 SSD），理论上随机 hash 可以实现均匀分布。但实际中，Shuffle Block 的命名模式（`shuffle_{shuffleId}_{mapId}_{reduceId}`）中 `mapId` 通常递增——假设 Shuffle Id 不变——hash 分布取决于 `mapId` 的分布，通常是均匀的。

但如果只有 1 个 `localDir`（单 SSD），所有 Shuffle Write I/O 都在同一块盘→成为瓶颈。多盘写在 100+ Executor 的生产环境中能将 Shuffle Write 吞吐提升 2-3 倍（利用 SSD 的并行性）。

## AI 时代反思

BlockManager 的 "Unified Block" 模型是一个很有意思的教学案例——LLM 可以很容易地解释这个模型的高层含义（"所有数据类型都用同一个 Block 系统管理"），但缺少跨越抽象层的深层理解：BlockManager 为什么需要 `getOrElseUpdate`？因为 RDD cache 没有分布式元数据——每个 Executor 独立决策要不要计算 + 缓存。为什么 `downgradeLock` 存在？因为"写后立即读"是一种常见模式——Task 计算了一个 partition 并缓存后，接下来可能立即需要遍历这个 partition。

这种"为什么某种设计存在"的理解恰好是 LLM 训练数据中最薄弱的——代码库中有大量设计决策的**后果**（API、方法签名），但几乎没有设计决策的**原因**。如果要构建一个真正能帮助用户理解 Spark 内核的 Agent，不应该只训练代码——还要训练"设计的演化"：`ShuffleMemoryManager（1.5）→ UnifiedMemoryManager（1.6+）` 这个演变反映了什么分布式系统的教训？

这种"设计演化"的知识目前主要存在于 JIRA Discussion、dev@spark 邮件列表和 Git 的 PR 讨论中——这些是非结构化的长尾数据，LLM 训练 pipeline 通常捕捉不到。

## 源码导航

| 文件 | 关键内容 | 行号参考 |
|------|---------|---------|
| `core/src/main/scala/org/apache/spark/storage/BlockManager.scala` | BlockManager 主类，doPut 写路径，getLocalValues/getRemoteBytes 读路径，getOrElseUpdate，replicate 远程拷贝，BlockData trait，HostLocalDirManager | 182 (class), 759 (getLocalBlockData), 997 (getLocalValues), 1152 (getRemoteBlock), 1409 (getOrElseUpdateRDDBlock), 1593 (doPut), 1910 (replicate), 2018 (putSingle) |
| `core/src/main/scala/org/apache/spark/storage/BlockManagerMaster.scala` | BlockManagerMaster，全局元数据操作 | |
| `core/src/main/scala/org/apache/spark/storage/BlockManagerMasterEndpoint.scala` | BlockManagerMasterEndpoint，Driver 端 RPC 处理，注册/更新/移除 | 51 (class) |
| `core/src/main/scala/org/apache/spark/storage/BlockInfoManager.scala` | BlockInfoManager，BlockInfo 锁管理，lockNewBlockForWriting，lockForReading，downgradeLock | |
| `core/src/main/scala/org/apache/spark/storage/BlockId.scala` | BlockId 层次结构（RDDBlockId, ShuffleBlockId, ShuffleBlockChunkId, BroadcastBlockId 等），name 命名规范 | 37 (sealed abstract class) |
| `core/src/main/scala/org/apache/spark/storage/memory/MemoryStore.scala` | MemoryStore，LinkedHashMap 维护 LRU，evictBlocksToFreeSpace 驱逐算法，putIterator/putBytes，dropFromMemory | 43 (MemoryEntry trait), 60+ (MemoryStore class) |
| `core/src/main/scala/org/apache/spark/storage/DiskStore.scala` | DiskStore，putBytes/getBytes，与 DiskBlockManager 协作 | |
| `core/src/main/scala/org/apache/spark/storage/DiskBlockManager.scala` | DiskBlockManager，localDirs + subDirs 目录结构，文件位置计算 | |
| `core/src/main/scala/org/apache/spark/storage/BlockManagerStorageEndpoint.scala` | BlockManagerStorageEndpoint，Executor 端本地存储 RPC | |
