# 第 4 章：Shuffle Read — 多路并发拉取与聚合

## 设计动机

Shuffle Read 是分布式计算中"数据从产生到消费"的下半场。M 个 Mapper 将各自 partition N 的数据写到磁盘（Shuffle Write）后，Reducer（负责 partition N）需要从 M 个 Mapper 中拉取这些数据。这个模式的本质是 **M-to-1 的 All-to-One 数据集合**。

Shuffle Read 面临三个核心挑战：

1. **网络效率**：Reducer 需要从 M 个不同的节点拉取数据。如果 M = 10000（大 Shuffle），依次拉取意味着 10000 次网络往返，不可接受。必须并发拉取，但并发数太高又会打垮网络栈。

2. **内存反压**：M 个数据流同时到达，每个可能几 MB 到几十 MB——Reducer 的内存有限，必须做流控（flow control），防止被 inbound 数据淹没。

3. **Piggyback 计算**：Shuffle Read 不是简单的"拷贝字节"。Reducer 拿到数据后需要反序列化、merge sort（如果 map-side 排序了）、combine（如果有 aggregator）。这是在网络 I/O 上 piggyback 的 CPU 密集型操作，必须流水线化。

Spark 的 Shuffle Read 方案是 `BlockStoreShuffleReader` + `ShuffleBlockFetcherIterator`——一条高度优化的"拉取→反序列化→排序→聚合→输出"流水线。

## 核心原理

### 4.1 总体架构 — 从 MapOutputTracker 到反序列化

Shuffle Read 的完整数据流：

```
MapOutputTracker (driver)
  ↓ getMapSizesByExecutorId: 获取 <Executor, List[(BlockId, offset, length)]>
  ↓
ShuffleBlockFetcherIterator
  ↓ 多路并发 HTTP fetch: 从各 Executor 拉取 block 数据
  ↓ 流控: maxBytesInFlight / maxReqsInFlight
  ↓
SerializerInstance.deserializeStream
  ↓ 解压 + 反序列化 → Iterator[(K, V)]
  ↓
ExternalSorter / Aggregator
  ↓ 排序 (如果有 ordering)
  ↓ Combine (如果有 aggregator)
  ↓
Output: Iterator[(K, C)]
```

### 4.2 MapOutputTracker — 数据位置的语义

`MapOutputTracker` 是 Reducer 的"导航仪"——它告诉每个 Reducer："你的 partition N 数据分散在哪些 Executor，在各自 Shuffle File 的哪个 offset 范围"。

Reducer 通过 `getMapSizesByExecutorId(shuffleId, startPartition, endPartition)` 获取：

```
返回: Iterator[(BlockManagerId, Seq[(BlockId, Long, Int)])]
示例:
  Executor-1: [(ShuffleBlockId(shuffleId=0, mapId=3, reduceId=5), offset=1024, length=5120)]
  Executor-2: [(ShuffleBlockId(shuffleId=0, mapId=7, reduceId=5), offset=2048, length=3072)]
  ...
```

这里的 (offset, length) 正是 Shuffle Write 阶段写入 Index 文件的内容。Reducer 通过 HTTP 请求：`GET /shuffleData?shuffleId=0&mapId=3&reduceId=5` → Executor-1 的 ExternalShuffleService 或 BlockManager 直接 seek + 发送对应范围的数据。

对于 Push-based Shuffle（第 5 章），`MapOutputTracker` 返回的是已经在 Shuffle Service 端合并后的数据块，不是原始的 Map-level 粒度。

### 4.3 ShuffleBlockFetcherIterator — 多路并发拉取引擎

`ShuffleBlockFetcherIterator` 是整个 Shuffle Read 的心脏——它负责把 M 个数据块通过有限的网络连接和内存缓冲区高效拉取下来。

```scala
// BlockStoreShuffleReader.scala:73
val wrappedStreams = new ShuffleBlockFetcherIterator(
  context,
  blockManager.blockStoreClient,    // 底层网络传输客户端
  blockManager,
  mapOutputTracker,
  blocksByAddress,                 // 从 MapOutputTracker 获取的数据位置
  serializerManager.wrapStream,    // 解压/解密包装器
  maxBytesInFlight,                // 飞行中的数据量上限 (默认 48MB)
  maxReqsInFlight,                 // 飞行中的请求数上限 (默认 Int.MaxValue)
  maxBlocksInFlightPerAddress,     // 每个地址飞行中的 block 数上限
  maxBlockSizeToMemory,            // 超过此大小的 block 直接写磁盘
  ...
).toCompletionIterator
```

**核心设计参数**：

| 参数 | 默认值 | 含义 |
|------|--------|------|
| `maxBytesInFlight` | 48MB | 同时传输中的数据总大小——异步发起的请求未接收完成的字节上限 |
| `maxReqsInFlight` | Int.MaxValue | 同时飞行中的请求数量上限 |
| `maxBlocksInFlightPerAddress` | Int.MaxValue | 单个节点的并发请求限制 |
| `maxBlockSizeToMemory` | Long.MaxValue | 超过此大小的 block 直接写到磁盘，不缓冲在内存 |
| `maxAttemptsOnNettyOOM` | 10 | Netty OOM 时的重试次数 |

**处理流程**：

```
while (还有 block 需要拉取) {
  // 1. 选取下一对 (executor, blocks)
  // 2. 检查 maxReqsInFlight / maxBytesInFlight / maxBlocksInFlightPerAddress
  //     → 如果有空间，异步发起 fetch 请求
  // 3. 已完成的请求 → 将收到的数据放入 results queue
  // 4. 每次 next(): 从 results queue 取下一个完成的 block
  //     → 解压 + 包装为 InputStream
  //     → 返回给上层的 flatMap (deserializeStream)
}
```

这是一种 **推拉结合（push-pull hybrid）** 的处理模型：
- Fetch 请求是异步 push 的（并发发起）
- 结果是被 pull 的（上层 `next()` 触发消费）
- 流控参数确保 push 不会压垮 pull 端的内存

**小 Block 优化 — Batch Fetch**：

当 `shouldBatchFetch = true` 且各条件满足时（serializer 支持 relocation、无 IO 加密、压缩 codec 支持 concatenation），多个相邻 partition 的 block 被合并到一个 HTTP 请求中拉取：

```scala
// BlockStoreShuffleReader.scala:46
private def fetchContinuousBlocksInBatch: Boolean = {
  val serializerRelocatable = dep.serializer.supportsRelocationOfSerializedObjects
  val codecConcatenation = if (compressed) {
    CompressionCodec.supportsConcatenationOfSerializedStreams(
      CompressionCodec.createCodec(conf))
  } else true
  val ioEncryption = conf.get(config.IO_ENCRYPTION_ENABLED)

  shouldBatchFetch && serializerRelocatable &&
    (!compressed || codecConcatenation) && !useOldFetchProtocol && !ioEncryption
}
```

Batch fetch 的好处：10000 个 block × 10 个连续 partition = 1000 个 HTTP 请求 而不是 10000 个。减少 connection overhead 和 TCP 往返。代价是"无法 fine-grained 流控"——一个 batch 中的所有 block 必须在内存中累积后才拆分。

### 4.4 Reduce-Side 的数据处理流水线

Block 拉下来的 InputStream 进入一条"反序列化 → 聚合 → 排序"的流水线：

```scala
// BlockStoreShuffleReader.scala:96
val recordIter = wrappedStreams.flatMap { case (blockId, wrappedStream) =>
  serializerInstance.deserializeStream(wrappedStream).asKeyValueIterator
}
```

`flatMap` 是关键的 **流水线化机制**——多个 block 的 InputStream 被懒加载地依次反序列化，数据一被反序列化就进入后续聚合流程（而不是等所有 block 拉完才处理）。

**reduce-side 聚合的三条分支**：

```scala
// BlockStoreShuffleReader.scala:114
val resultIter = {
  // 1. 有排序需求 → 用 ExternalSorter 做全量排序
  if (dep.keyOrdering.isDefined) {
    val sorter = new ExternalSorter(...)
    sorter.insertAllAndUpdateMetrics(interruptibleIter)
  }
  // 2. 无排序 + 有聚合 + map-side 已 combine → 只需 combine combiners
  else if (dep.mapSideCombine) {
    dep.aggregator.get.combineCombinersByKey(combinedKeyValuesIterator, context)
  }
  // 3. 无排序 + 有聚合 + map-side 未 combine → combine values
  else if (dep.aggregator.isDefined) {
    dep.aggregator.get.combineValuesByKey(keyValuesIterator, context)
  }
  // 4. 无排序 + 无聚合 → 直接透传
  else {
    interruptibleIter
  }
}
```

`combineCombinersByKey` vs `combineValuesByKey`：
- `combineCombinersByKey`：Map 端已经做过 combine，每个 key 只有一个 value（C 类型）。Rreduce 端只需把不同 Map 的同一个 key 的 combine result 合并——使用 `ExternalAppendOnlyMap`
- `combineValuesByKey`：Map 端没有 combine，每条 record 还是原始 value（V 类型）。Reduce 端需要先 group by key 再聚合——更昂贵

### 4.5 可中断迭代器 — Task 取消的支持

`InterruptibleIterator` 包裹整条流水线：

```scala
val interruptibleIter = new InterruptibleIterator[(Any, Any)](context, metricIter)
```

它定期检查 `TaskContext.isInterrupted()`——如果任务被取消（如 speculative execution 时），立即停止 Shuffle Read。这避免了"speculative task 的 clone 把 shuffle 数据全部拉下来才被 kill"——中断可以发生在任何一次 `next()` 调用的任意时刻。

### 4.6 本地 Shuffle Read — 同节点优化

如果 Reducer 与 Mapper 在同一个 Executor（Hadoop/HDFS 中常见的"数据本地性扩展到 Shuffle"），Spark 走本地读取路径：

- BlockManager 直接通过 `getLocalBytes(blockId)` 读取本地 Shuffle 文件
- 绕过网络栈、序列化、反序列化的一个环节——本地 block 传输不需要 Buffer 拷贝到网络栈
- 节省约 30% 延迟

### 4.7 Reduce-Side Spill

当 reduce-side 聚合（`ExternalAppendOnlyMap` 或 `ExternalSorter`）的内存超过阈值时，同样会 spill 到磁盘。

对于一个有 `reduceByKey` + `orderBy` 的查询：
```
Shuffle Read → combineValuesByKey (有 spill 风险) → ExternalSorter (有 spill 风险) → 输出
```

如果两阶段都 spill，磁盘 I/O 会增加到 2-3 倍。这是"大基数 shuffle key + 全局排序"场景的常见瓶颈。

### 4.8 SQL 层的 Shuffle Read 适配

在 Spark SQL 中，Reduce-Side 的处理在物理计划和 Shuffle 之间是 "SQL layer → Core layer" 的边界：

```
核心引擎层面:         SQL 层面:
Shuffle Read → 数据给到:
  ├── AQEShuffleReadExec (AQE 模式: coalesce/optimize 微调)
  ├── ShuffledRowRDD (非 AQE 模式)
  └── Custom Shuffle Reader (Native Engine Gluten/Velox)
```

在 SQL 层面，AQE 在 `AQEShuffleReadExec` 中可能合并多个 Map partition（`CoalesceShufflePartitions`），也可能复制倾斜 partition（`OptimizeSkewedJoin`）——这些都是在实际发起 Shuffle Read **之前**对 `blocksByAddress` 规划进行修改。

## 关键代码片段

### 示例：ShuffleFetch 的推拉模型

```
假设 reducer 需要拉取 100 个 mapper，maxBytesInFlight = 48MB，每个 block 约 5MB:

Step 1: 发起前 9 个 fetch (5MB × 9 = 45MB < 48MB, 第 10 个 5MB 会超出 48MB)
Step 2: 第 1 个 fetch 完成 → results queue 收到 5MB block
Step 3: reducer 调用 next() → 返回完成 block 的 stream
Step 4: 此时 in-flight = 40MB → 可以发起第 10 个 fetch
Step 5: 重复...

这样 reducer 总能保持在"48MB 的 I/O 在途"的平衡状态，
既不 idle (等待网络) 也不 OOM (接收太快)
```

## 硬件视角

**Shuffle Read 的负载三要素**：

Shuffle Read 同时消耗三种硬件资源：

1. **网络带宽**：Reducer 从 M 个 Mapper 拉取，受限于 NIC 带宽（如 10GbE = 1.25GB/s 每 Executor）
2. **内存带宽**：反序列化 → UnsafeRow 构造 → Aggregation Buffer 更新，都是在内存中操作。如果聚合 buffer 在 L2/L3 外，内存带宽可能成为瓶颈
3. **磁盘 I/O**：如果触发 reduce-side spill，数据要从内存写到磁盘再读回来——额外增加的 disk bandwidth 消耗

这三者之间存在流控：如果网络太快而 CPU 跟不上，buffer 会堆积（导致 spill 或 backpressure）；如果 CPU 太快而网络太慢，CPU 浪费在等待 I/O。

**Batch Fetch 的效率提升**：

Batch fetch 减少 HTTP 请求数，但更重要的是 **减少 TCP 三次握手和慢启动（slow start）的次数**。在一个 10000 个 mapper 的 shuffle 中：
- 不 batch：10000 次 TCP 连接（或 HTTP Keep-Alive 的 10000 次请求-响应）
- Batch (10 个一起)：1000 次连接

这意味着 9000 次 TCP 三次握手被消除。在高 BDP（带宽延迟积）环境中（如 10GbE, 0.5ms RTT），9000 次三次握手的延迟 ≈ 9000 × (0.5ms × 1.5) ≈ 6.75 秒。Batch fetch 可以节省这 6 秒。

**Disk Spill 与 L3 Cache 竞争**：

Reduce-side spill 意味着"聚合 hash table → 排序 → 写到磁盘"。在此过程中，CPU 在忙着比较 key，同时磁盘在忙着 I/O——但这两者不直接竞争同一硬件。竞争发生在 L3 cache：
- 排序操作使用了 L3 cache（比较 key、移动指针）
- 磁盘 I/O 的 DMA 不占用 L3 cache

所以 spill 的性能瓶颈是 **CPU 的排序 + key 比较**，不是磁盘本身。如果 spill 的数据量 > L3 size，排序的 cache miss 会成为瓶颈——每个比较都是 DRAM access（~100ns = ~300 cycles）。

## AI 时代反思

LLM Agent 在 Shuffle Read 的性能诊断场景中有一个尴尬的处境：Spark Web UI 上的 Shuffle Read 指标（Shuffle Read Size、Fetch Wait Time、Remote Blocks）很容易被 LLM 理解，但 LLM 给出的是"初级诊断"——"shuffle read 太大，减少 shuffle data"或"fetch wait time 太高，检查网络"——这水平相当于看文档的初学者。

真正有价值的诊断是 **数据驱动的模式匹配**：
- "这个 SQL 查询的 `maxBytesInFlight` = 48MB, 但实际 fetch 流量达到了 800MB/s，48MB 的限制导致 reducer 频繁 idle → 应该增加到 128MB"
- "batch fetch 被禁用了因为 serializer 是 `JavaSerializer` 不支持 relocation → 建议切换到 `KryoSerializer`"

这需要 Agent 不只是读取 Spark metrics，而是 **理解 Spark 配置项 + 硬件环境 + 查询模式** 的三者交互。当前的 LLM Agent 缺少这种"代码实现细节与生产配置的映射"能力——因为这类映射关系极少出现在公共文档中。

一个有前景的 AI-native Shuffle 优化方案是 **LLM-Based Config Advisor**：Agent 读取：
1. 查询的 Physical Plan → 识别出 Shuffle 的起点和终点
2. 集群配置（网络带宽、executor 内存、磁盘类型）
3. Spark Shuffle 的默认参数

→ 输出一套针对此查询的推荐配置（`maxBytesInFlight`, `batchFetch`, `spillThreshold`, ...）——这比"用户自己调参"准确，也比"固定默认值"灵活。

## 源码导航

| 文件 | 关键内容 | 行号参考 |
|------|---------|---------|
| `core/src/main/scala/org/apache/spark/shuffle/BlockStoreShuffleReader.scala` | BlockStoreShuffleReader，ShuffleBlockFetcherIterator 创建，reduce-side 处理三条分支，batch fetch 条件判断 | 33 (class), 46 (fetchContinuousBlocksInBatch), 72 (read), 114 (resultIter 分支) |
| `core/src/main/scala/org/apache/spark/storage/ShuffleBlockFetcherIterator.scala` | ShuffleBlockFetcherIterator，推拉模型实现，流控参数，fetch 请求调度 | |
| `core/src/main/scala/org/apache/spark/MapOutputTracker.scala` | MapOutputTracker，getMapSizesByExecutorId，push-based merge 支持 | |
| `core/src/main/scala/org/apache/spark/rdd/ShuffledRDD.scala` | ShuffledRDD，RDD 级别的 Shuffle Read 入口 | |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/exchange/ShuffleExchangeExec.scala` | ShuffleExchangeExec，SQL 层的 Shuffle Read 调度，AQEShuffleReadExec | |
