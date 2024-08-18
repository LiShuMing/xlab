# 第 3 章：Shuffle Write — 三条路径与决策树

## 设计动机

Shuffle 是分布式计算中最昂贵的操作。它将 Mapper 的输出按分区键重新分配到 Reducer——本质是一次全量数据的"网络重分布"。在 Spark 中，每条 Shuffle 路径都经过了精心设计，针对不同的数据特征选择不同的写策略。

MapReduce 论文奠定了"Sort-based Shuffle"的基础：Mapper 按 key 排序后写入本地磁盘，Reducer 通过 HTTP 拉取。Spark 继承了这个模型，但做了大量优化，引申出三条不同的写路径：

| 写路径 | 实现类 | 核心思想 |
|--------|--------|---------|
| BypassMergeSort | `BypassMergeSortShuffleWriter` | 不排序，每个 partition 一个文件，最后合并 |
| Serialized (Unsafe) | `UnsafeShuffleWriter` | 序列化后基于 partition id 排序，cache-efficient 指针数组 |
| Deserialized (Sort) | `SortShuffleWriter` | 反序列化为 Java 对象，排序时可聚合 |

`SortShuffleManager` 是三条路径的"交通调度员"——它根据 Shuffle Dependency 的特征（partitioner 类型、序列化器能力、是否需要 map-side combine）决定走哪条路。

理解 Shuffle Write 的关键在于理解 **每字节的旅程**：从 JVM 对象 → 序列化 → 缓冲区 → 排序 → 磁盘 或 从 JVM 对象 → 序列化 → 缓冲区 → 直接写出（无需排序）→ 磁盘。每条路径在 CPU、内存、I/O 之间有各自的平衡。

## 核心原理

### 3.1 SortShuffleManager — 三条路径的决策树

`SortShuffleManager.registerShuffle` 是决策入口：

```scala
// SortShuffleManager.scala:90
override def registerShuffle[K, V, C](
    shuffleId: Int, dependency: ShuffleDependency[K, V, C]): ShuffleHandle = {
  if (SortShuffleWriter.shouldBypassMergeSort(conf, dependency)) {
    new BypassMergeSortShuffleHandle[K, V](shuffleId, dependency)
  } else if (SortShuffleManager.canUseSerializedShuffle(dependency)) {
    new SerializedShuffleHandle[K, V](shuffleId, dependency)
  } else {
    new BaseShuffleHandle(shuffleId, dependency)
  }
}
```

决策树清晰直接：

```
1. canBypassMergeSort?
   ├─ YES → BypassMergeSortShuffleWriter (每个 partition 一个文件, 不排序)
   └─ NO → 继续

2. canUseSerializedShuffle?
   ├─ YES → UnsafeShuffleWriter (序列化后排序, 高效指针排序)
   └─ NO → SortShuffleWriter (反序列化排序, 支持 map-side combine)
```

**BypassMergeSort 条件**：

```scala
// SortShuffleWriter.scala
def shouldBypassMergeSort(conf: SparkConf, dep: ShuffleDependency[_, _, _]): Boolean = {
  dep.partitioner.numPartitions <= bypassMergeThreshold  // 默认 200
    && !dep.mapSideCombine  // 无 map-side 预聚合
}
```

`bypassMergeThreshold`（默认 200）是关键参数——当 partition 数少且不需要聚合时，为每个 partition 打开单独的文件直接写出，最后用 NIO `transferTo` 零拷贝合并。完全避免了排序的 CPU 开销和 spill 的 I/O 开销。

**Serialized Shuffle 条件**：

```scala
// SortShuffleManager.scala:227
def canUseSerializedShuffle(dependency: ShuffleDependency[_, _, _]): Boolean = {
  !dependency.serializer.supportsRelocationOfSerializedObjects  // false → can't use
    && !dependency.mapSideCombine                                 // false → can't use
    && numPartitions <= MAX_SHUFFLE_OUTPUT_PARTITIONS_FOR_SERIALIZED_MODE // 16777216
}
```

三个必须同时满足：
1. **Serializer 支持序列化对象重定位**：KryoSerializer 和 Spark SQL 的 custom serializers 支持（JavaSerializer 不支持）
2. **无 map-side combine**：序列化后无法执行 `reduceByKey` 的聚合逻辑
3. **partition 数 ≤ 16777216**：`PackedRecordPointer` 用 24-bit 存储 partition id

**Deserialized Sort（回退路径）**：以上两条都不满足时——这是最通用的路径，但效率最低。

### 3.2 BypassMergeSortShuffleWriter — 零排序直写

这是三条路径中最简单、最快的一条——但仅在 partition 数少（≤ bypassMergeThreshold）时可用。

**执行流程**：

```
for each record in input:
  partitionId = partitioner.getPartition(record.key)
  serialize record
  write serialized bytes to File(partitionId)  // 每个 partition 独立的临时文件

after all records processed:
  for each partition 0..N-1:
    将 File(partitionId) 的内容追加到最终 output file
    (使用 FileChannel.transferTo → 零拷贝)
    write partition offset to index file
  delete temporary files
```

```java
// BypassMergeSortShuffleWriter.java
// 为每个 partition 分配独立的 DiskBlockObjectWriter
DiskBlockObjectWriter[] partitionWriters = new DiskBlockObjectWriter[numPartitions];
long[] partitionLengths = new long[numPartitions];

// 写阶段: 每行直接写对应 partition 的文件
while (records.hasNext()) {
  Product2<K, V> record = records.next();
  int partition = partitioner.getPartition(record._1());
  partitionWriters[partition].write(record._1(), record._2());
}

// 合并阶段: 利用 NIO transferTo 零拷贝合并
FileChannel out = new FileOutputStream(outputFile).getChannel();
for (int i = 0; i < numPartitions; i++) {
  File file = partitionWriters[i].file();  // 临时文件
  FileChannel in = new FileInputStream(file).getChannel();
  // transferTo: DMA 引擎直接从磁盘缓冲区→网络栈 或 磁盘→磁盘
  // 数据不经过用户态 JVM 内存
  in.transferTo(0, in.size(), out);
  partitionLengths[i] = out.position();
  in.close();
  file.delete();
}
out.close();

// 写 index 文件: reducer 通过它定位自己 partition 的数据范围
IndexShuffleBlockResolver.writeIndexFileAndCommit(
  shuffleId, mapId, partitionLengths, ...);
```

**关键优化点**：

1. **零排序**：数据不排序——partitioner 直接决定去向，适用于 HashPartitioner（partition 由 hash 决定）
2. **transferTo**：临时文件合并使用 `FileChannel.transferTo`——OS 内核态 DMA，不经过用户态
3. **index 文件**：记录每个 partition 在 output file 中的 offset + length，reducer 直接 seek 到对应位置

**代价**：同时打开 `numPartitions` 个文件和序列化器——每个文件有一个输出缓冲区。对于 200 个 partition：200 × 32KB buffer ≈ 6.4MB。如果 partition 数过大（如 10000），同时打开 10000 个文件 + 10000 × 32KB ≈ 320MB 的 buffer——不可扩展。

### 3.3 UnsafeShuffleWriter — 序列化 + 指针排序

这是 Spark 默认 Shuffle Write 的"高配路径"——它把数据分批序列化到内存页中，构建"partition id + page pointer"数组，然后用效率极高的缓存友好排序。

**核心数据结构**：

```
ShuffleExternalSorter:
  - 内存页: 序列化后的 record 连续存储
  - inMemSorter (ShuffleInMemorySorter): 8 字节的 PackedRecordPointer 数组
    - 每个 8 字节: [24-bit partition id][13-bit page number][27-bit page offset]
    - partition id = 目标 partition (0 ~ 166777215)
    - page number + page offset → 指向序列化数据的在内存页中的地址
```

**执行流程**：

```
阶段 1: 序列化写入
  for each record in input:
    serializedBytes = serializer.serialize(record)
    pageOffset = allocatePage(serializedBytes.length)
    Platform.copyMemory(serializedBytes → page)
    构建 PackedRecordPointer(partitionId, pageNum, pageOffset)
    inMemSorter.insertRecord(pointer)

阶段 2: 排序 (当内存不足时触发 spill)
    inMemSorter.spill():
      - 对 PackedRecordPointer 数组按 partition id 排序
        - 使用 TimSort: O(N log N)
        - 排序的是 8 字节指针, 不是原始数据!
      - 按有序指针将各 partition 的序列化数据写出到 spill file
      - 释放内存页

阶段 3: 最终合并
    - 所有 spill files + remaining in-memory data
    - 对每个 partition: 将多个 spill file 中该 partition 的数据拼接
    - 写出最终 single output file
```

```java
// UnsafeShuffleWriter.java 的核心写循环:
while (records.hasNext()) {
  insertRecordIntoSorter(records.next());
}

// insertRecordIntoSorter:
void insertRecordIntoSorter(Product2<K, V> record) {
  // 1. 序列化
  serBuffer.reset();
  serOutputStream.writeKey(record._1());
  serOutputStream.writeValue(record._2());
  serOutputStream.flush();

  // 2. 分配内存页
  long pageCursor = allocatePage(serializedRecordSize);

  // 3. 拷贝到页中 (unsafe copyMemory)
  Platform.copyMemory(serBuffer.getBuf(), Platform.BYTE_ARRAY_OFFSET,
    page.getBaseObject(), page.getBaseOffset() + pageCursor,
    serializedRecordSize);

  // 4. 构建 8 字节指针
  long recordAddress = encodePageAddress(page, pageCursor);
  long pointer = PackedRecordPointer.packPointer(
    recordAddress, partitionId);

  // 5. 添加到排序器
  sorter.insertRecord(pointer, partitionId);
}
```

**为什么 UnsafeShuffle 是 cache-efficient？**

排序的对象是 8 字节的 `PackedRecordPointer`，不是原始 record。10 亿条 record 的排序：
- 原始 record 排序（反序列化）：每条 record 约 100-1000 字节 → 100GB+ total
- 指针排序（Unsafe 模式）：每条 8 字节 → 8GB total

在 L3 cache（约 40MB）中，可以容纳约 500 万条指针。8GB 相比 100GB → "内存容量压力" 8× 降低，"cache 命中率"随排序轮次显著提高。

**Spill 逻辑**：

当内存中 `ShuffleExternalSorter` 的内存页超过 Task 内存限制时，触发 spill：

1. 对 `inMemSorter` 中的指针数组按 `partitionId` 排序
2. 按有序指针顺序读取各 partition 的序列化数据
3. 按 partition 写入 spill file：每个 spill file 内部 [partition header: id + length] [serialized records of this partition]

Spill file 的格式使后续合并只需要 **直接拼接**（如果 compression codec 支持 compressed data concatenation），不需要解压和重新压缩。这类似于 LZ4/ZSTD streaming mode——多个压缩块可以 concat 为一个有效压缩文件。

### 3.4 SortShuffleWriter — 反序列化排序

当 UnsafeShuffle 不可用时，使用这条"基础路径"。它的行为类似于经典的 MapReduce Map-Side Sort：

```scala
// SortShuffleWriter.scala
override def write(records: Iterator[Product2[K, V]]): Unit = {
  // 1. 如果有 map-side combine → 使用 ExternalSorter 进行聚合
  sorter = if (dep.mapSideCombine) {
    new ExternalSorter[K, V, C](
      context, dep.aggregator, Some(dep.partitioner),
      dep.keyOrdering, dep.serializer)
  } else {
    // 没有聚合 → 只排序
    new ExternalSorter[K, V, V](
      context, aggregator = None, Some(dep.partitioner),
      ordering = None, dep.serializer)
  }

  // 2. 插入所有 records
  sorter.insertAll(records)

  // 3. 写出文件：sorter 内部已将 partition 内的数据排序并溢写到磁盘
  val mapOutputWriter = shuffleExecutorComponents.createMapOutputWriter(
    shuffleId, mapId, sorter.partitionedIterator.size)
  sorter.writePartitionedMapOutput(mapOutputWriter)
}
```

`ExternalSorter` 是这里的关键——它支持"排序的同时可选 map-side combine"：
- 如果有 `aggregator`：创建 `AppendOnlyMap`（开放寻址哈希表），在内存中对相同 key 做 `reduceByKey` 语义——将多次出现的同一 key 合并成一条 record。当内存满时 spill。
- 如果没有 `aggregator`：只在内存缓冲区中排序（`PartitionedAppendOnlyMap`），按 partition 分开，当内存满时 spill。

spill 过程：按键的 partition 排序→按 partition 写出 spill files。最终合并阶段类似于 UnsafeShuffle 的 merge——但这里 record 已被反序列化，所以合并时可以**同时调用 combiner**（如果有的话）。

### 3.5 Index 文件 — 随机访问的索引

Shuffle Write 的最终产物是 **一个 data file + 一个 index file**：

```
data file:  [partition_0_data][partition_1_data]...[partition_N-1_data]
index file: [offset_0, length_0][offset_1, length_1]...  (每对 8 字节 = long + long)
```

```scala
// IndexShuffleBlockResolver.scala
def writeIndexFileAndCommit(
    shuffleId: Int, mapId: Long, lengths: Array[Long],
    dataTmp: File): Unit = {
  val indexFile = getIndexFile(shuffleId, mapId)
  val out = new DataOutputStream(new BufferedOutputStream(
    new FileOutputStream(indexFile)))

  // 记录每个 partition 的 offset
  var offset = 0L
  for (length <- lengths) {
    out.writeLong(offset)  // partition 在 data file 中的起始偏移
    out.writeLong(length)  // partition 的大小
    offset += length
  }
  out.close()
}
```

Index 文件的设计很简单但关键：Reducer 通过 `ShuffleBlockFetcherIterator` 读取 index file → 得到自己 partition 的 (offset, length) → 精确请求该范围的数据。这是 O(1) 的"精确寻址"——Reducer 不需要扫描整个 data file。

### 3.6 三条路径的内存与 I/O 对比

| 维度 | BypassMergeSort | UnsafeShuffle | SortShuffle |
|------|----------------|---------------|-------------|
| 排序开销 | 零 | O(N log N) (8字节指针) | O(N log N) (完整对象比较) |
| 内存数据形态 | 对象（序列化后写磁盘） | 序列化字节 | Java 对象 |
| 同时打开文件数 | numPartitions 个 | 1 | 1 |
| Spill 粒度 | 无 spill | 序列化 partition 批量写 | 排序后 partition 批量写 |
| Map-side combine | 不支持 | 不支持 | 支持 |
| 合并开销 | transferTo 零拷贝 | 拼接 (concat) 序列化数据 | 排序 + 合并 |
| 适用 partition 数 | ≤ 200 | ≤ 16M | 无限 |

## 关键代码片段

### 示例：决策树在物理上的体现

```
RDD 操作:   rdd.reduceByKey(_ + _, numPartitions = 100)
Shuffle Dependency: mapSideCombine = true
→ SortShuffleWriter (唯一支持 map-side combine 的路径)

RDD 操作:   rdd.map(x => (x.key, x.value)).groupByKey(numPartitions = 50)
Shuffle Dependency: mapSideCombine = false, partitions ≤ 200
→ BypassMergeSortShuffleWriter (最快路径)

SQL 操作:  SELECT ... GROUP BY large_key, partitions = 500
Spark SQL serializer + no map-side combine + partitions ≤ 16M
→ UnsafeShuffleWriter (高效指针排序)
```

## 硬件视角

**transferTo 的 DMA 路径**：

BypassMergeSort 的合并阶段使用 `FileChannel.transferTo`——这是一个"零拷贝"操作。在 Linux 上，`transferTo` 使用 `sendfile64` 系统调用，通过 DMA 引擎将数据从 page cache → socket buffer 或 page cache → page cache，**不进入 CPU 寄存器**。对于现代 Intel/AMD 架构，这意味着：

- 数据走的是 **DMA 控制器** 而不是 CPU core
- CPU L3 cache 完全不受这次传输影响——可以用于后面查询的计算
- 对于 50 个 partition × 10MB = 500MB 的合并：无 transferTo → CPU 需要从 page cache 读 500MB → L3 → 写 500MB → L1 污染约 500MB。transferTo → CPU 完全空闲

**UnsafeShuffle 的排序 Cache 行为**：

`ShuffleInMemorySorter` 对 `PackedRecordPointer[]` 的排序使用的 TimSort 是 **缓存自适应（cache-aware）**。它在局部小范围内对连续 8 字节元素排序（一个 cache line = 64 字节 = 8 个 pointer）→ L1 hit 率接近 100%。当 run 合并时，跨度增长到多个 L3 block——但相比"完整对象排序"，8 字节指针排序的 L3 压力低了两个数量级。

**写 Amplification**：

三条路径有不同的写放大（write amplification = 实际写入字节 / 最终输出字节）：

- BypassMergeSort: 1.0× (直接写到文件，合并是 transferTo，无额外拷贝)
- UnsafeShuffle: 1.0× (序列化字节直接写出) 或 1.0-2.0× (如有 spill → 多次写入 + 合并)
- SortShuffle: 1.0-3.0× (序列化 + 反序列化 + spill → 数据被拷贝多次)

Spill 是写放大的主要来源——一个典型的 100GB Shuffle with batch spill 可能导致 200GB 到 300GB 的累计写 I/O。这和其他数据库的"External Sort with spill"的 I/O 放大模式相同。

## AI 时代反思

LLM 在 Shuffle 相关问题上有一个"知识盲区"：Shuffle 的物理实现（BypassMergeSort vs UnsafeShuffle vs SortShuffle）很少出现在 LLM 的训练数据中——因为这类细节通常不在博客、Stack Overflow、文档中详细描述。LLM 可以准确描述"Shuffle 是 Map Reduce 的数据重分布"，但几乎无法解释"为什么 PackedRecordPointer 是 8 字节"或"transferTo 为什么更快"。

这意味着在"调试 Shuffle 性能问题"的场景中，目前的 LLM Agent 能提供的帮助非常有限——它只能基于高层次描述给出通用建议（"减少 Shuffle 数据量"、"增加 partition 数"），无法在代码级别精准定位瓶颈。

但如果我们将 LLM Agent 与日志系统（driver/executor logs）结合，它可以做一件事：**模式识别**。一个 Agent 可以读取 shuffle 相关的 Spark metrics（spill size, write time, peak memory），然后匹配"这个 profile 最像 BypassMergeSort 在不该有的场景中被使用了"或"这个 profile 最像 Serializer 不支持 relocation 导致了回退到 SortShuffle"。这是"日志 + LLM 的模式匹配"——不只是"检查数字"，而是"解释模式"。

另一个有趣的方向：**LLM 是否可以生成更好的 `bypassMergeThreshold` 默认值？** 当前的阈值是固定的 200——但在不同硬件环境下，最优值不同：
- NVMe SSD + 大量内存 → transferTo 收益大 → 可以把 threshold 提高到 1000
- HDD + 小内存 → 同时打开太多文件会 segregate seek → threshold 应该降低到 50

LLM 可以通过"理解"硬件配置文本（从 `spark-submit` 的 GPU-memory config、磁盘类型 label）来动态推荐这个值——这比人工调参更智能。

## 源码导航

| 文件 | 关键内容 | 行号参考 |
|------|---------|---------|
| `core/src/main/scala/org/apache/spark/shuffle/sort/SortShuffleManager.scala` | SortShuffleManager，registerShuffle 决策树，canUseSerializedShuffle 条件，BypassMergeSort/Serialized/Base 三个 ShuffleHandle | 73 (class), 90 (registerShuffle), 227 (canUseSerializedShuffle), 264 (SerializedShuffleHandle), 274 (BypassMergeSortShuffleHandle) |
| `core/src/main/java/org/apache/spark/shuffle/sort/BypassMergeSortShuffleWriter.java` | BypassMergeSortShuffleWriter，per-partition 临时文件，transferTo 零拷贝合并，index 文件生成 | 84 (class), write (main method), merge (transferTo) |
| `core/src/main/java/org/apache/spark/shuffle/sort/UnsafeShuffleWriter.java` | UnsafeShuffleWriter，ShuffleExternalSorter 交互，PackedRecordPointer，serialized sorting | 70 (class), write (main method), insertRecordIntoSorter |
| `core/src/main/java/org/apache/spark/shuffle/sort/ShuffleExternalSorter.java` | ShuffleExternalSorter，内存页管理，spill 逻辑，partition-sorted 写出 | |
| `core/src/main/java/org/apache/spark/shuffle/sort/ShuffleInMemorySorter.java` | ShuffleInMemorySorter，PackedRecordPointer 数组，TimSort 排序 | |
| `core/src/main/scala/org/apache/spark/shuffle/sort/SortShuffleWriter.scala` | SortShuffleWriter，ExternalSorter 集成，map-side combine 支持 | |
| `core/src/main/scala/org/apache/spark/shuffle/IndexShuffleBlockResolver.scala` | IndexShuffleBlockResolver，index file 读写，data file 命名规范 | |
| `core/src/main/java/org/apache/spark/shuffle/sort/PackedRecordPointer.java` | PackedRecordPointer，24-bit partition + 40-bit page address 编码 | |
