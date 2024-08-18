# 第 18 章：Memory Management — 统一内存模型与任务级仲裁

## 设计动机

分布式计算引擎的内存管理需要回答两个问题：

1. **总量控制**：一个 Executor JVM 有 8GB 堆内存，多少给 Cache（storage），多少给 Shuffle/Join/Aggregate（execution），多少留给 JVM 自己的开销？
2. **任务间公平**：一个 Executor 同时运行 4 个 Task。如果 Task-1 先抢占了 3GB 的 execution 内存，Task-2/3/4 在需要内存时怎么办？要不要让 Task-1"吐出来"？

这两个问题的难度在于：**storage 和 execution 的需求是动态波动且方向彼此相反的**。在查询早期，数据被读入后需要 execution 内存做 Shuffle Write 和 Aggregation。在查询后期，Shuffle Read 的结果可能被 cache，需要 storage 内存。如果静态划分"storage=2GB, execution=4GB"，总会有"一边堆满溢写、另一边空空如也"的时刻。

Spark 的 UnifiedMemoryManager 引入了**借用机制**——storage 和 execution 之间可以互相借用空闲内存。但这个机制有一个硬约束：**execution 可以通过驱逐缓存块从 storage 回收借出的内存，但 storage 永远不能驱逐 execution**。

为什么？因为 execution 内存里的数据是"活"的——Shuffle Write 的 buffer、Hash Join 的 probe table、Aggregate 的 hash map——驱逐它们意味着要重新计算或溢写，而驱逐 cached RDD block 只需要重新从源数据读取。两者的驱逐代价相差几个数量级。

## 核心原理

### 18.1 内存层次结构 — 从 JVM Heap 到 Off-Heap

Spark Executor 的可用内存按以下层次划分：

```
Executor JVM 进程内存 (e.g. 8GB)
│
├── Reserved Memory (预留内存): 300MB
│   └── 用途: JVM 自身开销、内部数据结构、Unsafe row 引用
│       在 getMaxMemory 中统一定义: systemMemory - reservedMemory
│
├── Usable Memory: systemMemory - 300MB
│   └── spark.memory.fraction 控制比例 (默认 0.6)
│       │
│       ├── Unified Memory Pool (约 4.6GB for 8GB heap, fraction=0.6)
│       │   ├── Execution Memory (默认 50%, 约 2.3GB)
│       │   │   └── 用途: Shuffle Write buffers, Hash Join probe table,
│       │   │         Aggregate hash map, Sort buffers
│       │   └── Storage Memory (默认 50%, 约 2.3<｜image｜>）
│       │       └── 用途: RDD/DataFrame cache, broadcast variables
│       │
│       └── User Memory (约 1.9GB)
│           └── 用途: 用户自定义数据结构、UDF 状态、
│                 Spark 内部元数据 (task info, partition metadata)
│
└── Off-Heap Memory (可选, spark.memory.offHeap.enabled=true)
    └── spark.memory.offHeap.size 控制
        ├── Execution Off-Heap: maxOffHeap * (1 - storageFraction)
        └── Storage Off-Heap:  maxOffHeap * storageFraction
```

`getMaxMemory` 的计算逻辑：

```scala
// UnifiedMemoryManager.scala:462
private def getMaxMemory(conf: SparkConf): Long = {
  val systemMemory = conf.get(TEST_MEMORY)  // 实际是 spark.executor.memory 或 spark.driver.memory
  val reservedMemory = 300 * 1024 * 1024    // RESERVED_SYSTEM_MEMORY_BYTES
  val usableMemory = systemMemory - reservedMemory
  val memoryFraction = conf.get(config.MEMORY_FRACTION)  // 默认 0.6
  (usableMemory * memoryFraction).toLong
}
```

举例：`spark.executor.memory = 8GB` → systemMemory=8GB, reservedMemory=300MB, usableMemory=7.7GB, unifiedPool=7.7×0.6=4.62GB, storageRegion=4.62×0.5=2.31GB, executionRegion=4.62-2.31=2.31GB。

### 18.2 MemoryManager 抽象类 — 四个池的架构

`MemoryManager` 是整个系统的基类，每个 JVM 只有一个实例。它维护**四个内存池**：

| 池 | 类 | 用途 |
|----|-----|------|
| onHeapExecutionMemoryPool | ExecutionMemoryPool | 堆内执行内存 |
| onHeapStorageMemoryPool | StorageMemoryPool | 堆内存储内存 |
| offHeapExecutionMemoryPool | ExecutionMemoryPool | 堆外执行内存 |
| offHeapStorageMemoryPool | StorageMemoryPool | 堆外存储内存 |

四个池共享同一个 `MemoryManager` 实例作为同步锁（`lock`），所有 acquire/release 操作都需要获取该锁。在设计上是一个粗粒度锁——但争用通常不高，因为 memory acquire 的频次远低于数据处理的频次（数据是成批（pages）分配的，不是逐行申请）。

```scala
// MemoryManager.scala:39
private[spark] abstract class MemoryManager(
    conf: SparkConf,
    numCores: Int,
    onHeapStorageMemory: Long,    // 初始 storage 池大小 = maxMemory * storageFraction
    onHeapExecutionMemory: Long)  // 初始 execution 池大小 = maxMemory - onHeapStorageMemory
  extends Logging {

  // 四个内存池
  protected val onHeapStorageMemoryPool = new StorageMemoryPool(this, MemoryMode.ON_HEAP)
  protected val offHeapStorageMemoryPool = new StorageMemoryPool(this, MemoryMode.OFF_HEAP)
  protected val onHeapExecutionMemoryPool = new ExecutionMemoryPool(this, MemoryMode.ON_HEAP)
  protected val offHeapExecutionMemoryPool = new ExecutionMemoryPool(this, MemoryMode.OFF_HEAP)
}
```

**页面大小**（pageSizeBytes）由内存总量、核数和 GC 类型共同决定：

```scala
// MemoryManager.scala:251
private lazy val defaultPageSizeBytes = {
  val minPageSize = 1MB
  val maxPageSize = 64MB
  val safetyFactor = 16
  val size = nextPowerOf2(maxTungstenMemory / cores / safetyFactor)
  val chosenPageSize = clamp(size, 1MB, 64MB)
  // G1GC/ZGC/ShenandoahGC: 对齐 heap region size
  if (isG1GC && onHeap) chosenPageSize - LONG_ARRAY_OFFSET
  else chosenPageSize
}
```

例如：8 核 Executor，4.62GB 统一池 → 4.62GB / 8 / 16 ≈ 36.9MB → nextPowerOf2=32MB → 页大小=32MB。使用 G1GC 时，要将页面大小调整得与 Region Size（通常是 2 的幂）对齐，减少内存浪费。

### 18.3 UnifiedMemoryManager — 借用的规则

`UnifiedMemoryManager` 的核心逻辑在 `acquireExecutionMemory` 和 `acquireStorageMemory` 中。

**Execution 借用 Storage**：

```scala
// UnifiedMemoryManager.scala:160
def maybeGrowExecutionPool(extraMemoryNeeded: Long): Unit = {
  if (extraMemoryNeeded > 0) {
    // 可以从 storage 回收的 = max(空闲内存, 超出 storageRegionSize 的 memory)
    // 如果 storage 已用 < storageRegionSize: 只能回收空闲部分
    // 如果 storage 已用 > storageRegionSize: 回收空闲 + 超出的部分 (驱逐缓存)
    val memoryReclaimableFromStorage = math.max(
      storagePool.memoryFree,
      storagePool.poolSize - storageRegionSize)
    if (memoryReclaimableFromStorage > 0) {
      val spaceToReclaim = storagePool.freeSpaceToShrinkPool(
        math.min(extraMemoryNeeded, memoryReclaimableFromStorage))
      storagePool.decrementPoolSize(spaceToReclaim)
      executionPool.incrementPoolSize(spaceToReclaim)
    }
  }
}
```

`freeSpaceToShrinkPool` 是一个多步回收过程：先释放 storage 的空闲内存（不驱逐），如果还不够，驱逐 cached blocks 直到释放足够内存或没有更多可驱逐块。

**Storage 借用 Execution**：

```scala
// UnifiedMemoryManager.scala:239
if (numBytes > storagePool.memoryFree) {
  val memoryBorrowedFromExecution =
    Math.min(executionPool.memoryFree, numBytes - storagePool.memoryFree)
  executionPool.decrementPoolSize(memoryBorrowedFromExecution)
  storagePool.incrementPoolSize(memoryBorrowedFromExecution)
}
```

Storage 只能"借" execution 的**空闲**内存——不能驱逐 execution 的已用内存。如果 execution 已经用满了，storage 的 `acquireMemory` 直接返回 false → 块不会被缓存。

**Unmanaged Memory** 是 Spark 4.0 引入的特性，用于追踪 Spark 内存管理系统外部的内存占用（如 RocksDB state store），防止这些"隐形"内存占用导致 OOM。由一个后台 polling 线程定期查询已注册的 `UnmanagedMemoryConsumer` 并汇总。

### 18.4 ExecutionMemoryPool — 任务间内存仲裁

`ExecutionMemoryPool` 实现了"N 个任务公平共享 memory pool"的策略。核心理念：**保证每个活跃任务都能至少获取 pool 的 1/(2N) 的内存，但限制最多获取 pool 的 1/N**。

```scala
// ExecutionMemoryPool.scala:113
while (true) {
  val numActiveTasks = memoryForTask.keys.size
  val curMem = memoryForTask(taskAttemptId)

  // 先尝试扩大 execution pool (从 storage 回收借用)
  maybeGrowPool(numBytes - memoryFree)

  val maxPoolSize = computeMaxPoolSize()
  val maxMemoryPerTask = maxPoolSize / numActiveTasks    // 1/N
  val minMemoryPerTask = poolSize / (2 * numActiveTasks)  // 1/2N

  val maxToGrant = math.min(numBytes, math.max(0, maxMemoryPerTask - curMem))
  val toGrant = math.min(maxToGrant, memoryFree)

  // 如果不能满足最小保证 → 阻塞等待 (wait)
  if (toGrant < numBytes && curMem + toGrant < minMemoryPerTask) {
    lock.wait()
  } else {
    memoryForTask(taskAttemptId) += toGrant
    return toGrant
  }
}
```

这种设计的关键洞察：N 是**动态变化**的。当一个新的 Task 启动时（N 增加），每个 Task 的 `maxMemoryPerTask` 和 `minMemoryPerTask` 都降低——如果某个老 Task 之前占用了大量内存（超过了新的 1/N），新的 Task 会阻塞在 `lock.wait()`。当老 Task 释放内存时（`releaseMemory` 调用 `lock.notifyAll()`），唤醒等待中的 Task。

**举例**：

```
Executor 有 4GB execution pool, 当前 2 个 Task 在运行:
  Task-1: 已占用 1.5GB, 再申请 1GB
  Task-2: 已占用 0.5GB, 正在计算

  N=2: maxPerTask = 2GB, minPerTask = 1GB
  Task-1 已有 1.5GB → 最多可再得 0.5GB (到达 2GB 上限)
  如果申请 1GB → 只能得到 0.5GB

新的 Task-3 启动:
  N=3: maxPerTask = 1.33GB, minPerTask = 0.67GB
  Task-1 现有 2GB > 1.33GB → 超了！
  Task-3 申请 1GB → 只能得到 0.67GB (minPerTask)
  → lock.wait() 等待 Task-1 释放内存
```

这个策略从 Spark 1.6 开始使用，取代了早期（1.5）的 `ShuffleMemoryManager`。1/(2N) ~ 1/N 的公平窗口是一个工程上的实用近似，在实现简单性和公平性之间取得了平衡。

### 18.5 TaskMemoryManager — 单任务内的页面管理

`MemoryManager` 负责"池间借用"和"任务间公平"；`TaskMemoryManager` 负责**单任务内部的 Tungsten 页面分配和内存回收**。

每个 `TaskMemoryManager` 维护一个**页表**（pageTable）——类似操作系统的虚拟内存页表：

```java
// TaskMemoryManager.java:90
private final MemoryBlock[] pageTable = new MemoryBlock[PAGE_TABLE_SIZE];  // 8192 entries
```

使用 13-bit page number + 51-bit offset 的编码方式，将 64-bit 地址映射到 (baseObject, offset)：

- **On-heap 模式**：baseObject 指向 long[] 数组（页的实际存储），offset 是数组内偏移
- **Off-heap 模式**：baseObject=null，直接使用 64-bit 绝对地址

这种设计允许在数据结构（hash table、sort buffer）中存储 64-bit 的"指针"——而不是 (Object, offset) 对——兼容 on-heap 和 off-heap 两种模式。

**内存不足时的 spill 链**：

当 `acquireExecutionMemory` 返回的字节数小于请求量时，`TaskMemoryManager` 触发 spill：

```java
// TaskMemoryManager.java:159
public long acquireExecutionMemory(long required, MemoryConsumer requestingConsumer) {
  long got = memoryManager.acquireExecutionMemory(required, taskAttemptId, mode);

  if (got < required) {
    // 构建按内存用量排序的 consumer 列表
    TreeMap<Long, List<MemoryConsumer>> sortedConsumers = new TreeMap<>();
    for (MemoryConsumer c: consumers) {
      if (c.getUsed() > 0 && c.getMode() == mode) {
        long key = c == requestingConsumer ? 0 : c.getUsed();
        sortedConsumers.computeIfAbsent(key, k -> new ArrayList<>()).add(c);
      }
    }
    // 迭代 spill: 优先 spill 内存 >= need 的最小 consumer
    while (got < required && !sortedConsumers.isEmpty()) {
      Map.Entry<Long, List<MemoryConsumer>> entry =
        sortedConsumers.ceilingEntry(required - got);  // 找内存量 >= need 的最小者
      if (entry == null) entry = sortedConsumers.lastEntry();  // 没有？spill 最大的
      List<MemoryConsumer> cList = entry.getValue();
      got += trySpillAndAcquire(requestingConsumer, required - got, cList, cList.size() - 1);
    }
  }
  consumers.add(requestingConsumer);
  return got;
}
```

Spill 的启发式策略是"优先 spill 内存量刚好能满足所需的最小 consumer"——这样既避免了 unnecessary spill，又不会产生太多小 spill 文件。

### 18.6 MemoryConsumer — Spill 的抽象

`MemoryConsumer` 是所有需要 Tungsten 内存的组件的抽象父类——`ShuffleExternalSorter`、`BytesToBytesMap`（Hash Join probe table）、`UnsafeExternalRowSorter` 等都是它的子类：

```java
// MemoryConsumer.java:32
public abstract class MemoryConsumer {
  protected final TaskMemoryManager taskMemoryManager;
  private final long pageSize;
  private final MemoryMode mode;
  protected final AtomicLong used;

  public abstract long spill(long size, MemoryConsumer trigger) throws IOException;
}
```

`spill(size, trigger)` 方法由子类实现——释放至少 `size` 字节的 Tungsten 页面。返回值是实际上释放的字节数。

这构成了一个**层次化的 spill 链**：

```
TaskMemoryManager 发现内存不足
  → 1. 向 MemoryManager 申请内存 (可能触发 storage 驱逐)
  → 2. 如果还不够 → 排序 consumer，依次调用 spill()
    → ShuffleExternalSorter.spill() → 将排序后的指针数组写出到 spill file
    → BytesToBytesMap.spill() → 将 hash table 中已满的 page 写出
  → 3. 如果 spill 后还不够 → 返回实际所得 → 调用者处理部分分配
```

### 18.7 On-Heap vs Off-Heap — 选择的代价

`MemoryMode` 枚举定义在 `memory.MemoryMode`：

```java
public enum MemoryMode { ON_HEAP, OFF_HEAP }
```

`MemoryManager.tungstenMemoryMode` 根据 `spark.memory.offHeap.enabled` 配置决定：

```scala
// MemoryManager.scala:228
final val tungstenMemoryMode: MemoryMode = {
  if (conf.get(MEMORY_OFFHEAP_ENABLED)) {
    MemoryMode.OFF_HEAP
  } else {
    MemoryMode.ON_HEAP
  }
}
```

| 维度 | On-Heap | Off-Heap |
|------|---------|----------|
| GC 影响 | 大对象导致 Full GC | 无 GC 开销 |
| 分配速度 | 快（JVM TLAB） | 慢（Unsafe.allocateMemory） |
| 序列化/反序列化 | 需要 UnsafeRow→对象 转换 | 直接操作字节 |
| 内存上限 | JVM heap max | 独立于 heap, 理论上 unlimited |
| Address 编码 | Object+offset, 需页表翻译 | 裸 64-bit 地址 |
| 数据序列化要求 | 低 (对象即可) | 高 (必须序列化) |

Off-Heap 的页表开销很小——pageTable 只有 8192 个 entry × 8 字节 = 64KB——但代价是**每次 on-heap 地址转换都需要一次页表查找 + Object 基址检索**。JIT 编译器通常能将这些查找优化为直接寄存器访问——hot path 上几乎零开销。

选择 Off-Heap 的典型场景：
- 堆内存有限（<4GB），需要额外内存做大型 Shuffle/Aggregate
- 使用 G1GC 但无法调整到避免长时间停顿的规模
- 与 Native Engine（Gluten/Velox）集成，内存通过 Unsafe 传递

## 关键代码片段

### 示例：一次完整的 Execution Memory Acquire

```
场景: 4 个 Task 在 8GB Executor 上运行, 池大小=2.31GB, Task-4 需要 500MB 做 Shuffle

1. TaskMemoryManager.acquireExecutionMemory(500MB, ShuffleExternalSorter)
2.   → MemoryManager.acquireExecutionMemory(500MB, task4, ON_HEAP)
3.     → UnifiedMemoryManager.acquireExecutionMemory:
         N=4, maxPerTask=578MB, minPerTask=289MB
         Task-4 已有 200MB → maxToGrant=min(500, 578-200)=378MB
         memoryFree=100MB → toGrant=100MB (不够 500MB)
         curMem+toGrant=300MB >= minPerTask(289MB) → 不阻塞
         返回 100MB
4.   → TaskMemoryManager 得到 100MB, 还需要 400MB
5.   → 构建 sortedConsumers: Task-1(800MB), Task-2(600MB), Task-3(300MB)
6.   → 轮到 ceilingEntry(400MB): Task-2(600MB) 或 Task-3(300MB, 不够)
     → 选 Task-2, 调用 ShuffleExternalSorter.spill()
     → spill 释放了 200MB 的 Tungsten 页面
7.   → 再次 acquireExecutionMemory(300MB, task4):
         N=4, Task-4 已有 300MB, memoryFree=300MB
         maxToGrant=min(300, 578-300)=278MB
         toGrant=278MB
         返回 278MB
8.   → Task-4 总共得到 378MB, 不够 500MB,
       但已到 1/N 上限 → 只能等待其他 task 释放或自适应
```

## 硬件视角

**GC 压力与 Page Size 的关系**：

Tungsten 的 on-heap 内存分配使用 `long[]` 数组作为页面存储。对于 32MB 的 page size：

- 每个页面是一个 `new long[4,194,304]`（32MB / 8 字节）
- G1GC 默认 Region Size = 4MB（或 2MB 或 8MB，取决于 heap size）
- 一个 32MB 页面连续跨越 8 个 G1 region → 部分成为 Humongous Object

Humongous Object 在 G1GC 中的处理比较昂贵——它占用一整个 region 甚至多个 region，GC 需要特别处理。这就是为什么 `defaultPageSizeBytes` 在多 GC 模式下会用 `LONG_ARRAY_OFFSET` 调整大小——让页面能整除 region size，避免产生跨 region 的 humongous 碎片。

**内存带宽的静默消耗**：

UnifiedMemoryManager 的借用机制看似简单（几条 CAS + synchronized），但驱逐缓存块（从 storage 回收）的代价不只是"失去缓存"——如果这些 cache 块被频繁驱逐又重建，会导致**内存带宽的隐形浪费**：

```
cache A 的 chunk → 从 storage pool 驱逐 (释放 32MB)
  → 10 秒后, 下游 Stage 需要 chunk A
  → 从源数据重新读取 → 解压 → 缓存 (重新占用 32MB)
  → 累计消耗: 32MB 内存带宽 + 解压 CPU + 驱逐时的 GC pressure
```

如果在驱逐-重建之间 execution 只需要了 5MB——这就是一个负优化（32MB vs 5MB）。现代 Spark 的驱逐最小粒度是一个完整的 block，这意味着小块 execution 需求可能触发大块 storage 驱逐→"内存浪费的放大效应"。

## AI 时代反思

内存管理是 LLM Agent 的一个有意思的"测试场"——因为它同时涉及数字、策略和反直觉的行为。一个 Agent 在做内存诊断时需要理解的不是"内存满了"这个简单事，而是"为什么这个 Task 的 execution memory 在 1/2N 以下却在 spill？"——这可能是因为 N 突然增加了（推测执行启动了一个 duplicate task），或者另一个 Task 占用了远超 1/N 的内存在 slow GC。

传统的 LLM 对这类问题的解读是**单向且粗略**的——"内存不够，增大 executor 内存"——但真实生产中的最优解往往是"降低 spark.memory.storageFraction 到 0.3（减少 storage 池，给 execution 留更多缓冲区，减少 spill 次数）"或"启用 off-heap 来绕过 GC 对堆内大页面的影响"。

从这个角度看，**LLM Agent 在内存管理中最有能力的角色不是纯诊断，而是"配置推荐 + 解释"**：
- Agent 读取过去 50 个查询的 memory metrics（peak execution memory, spill size, storage eviction rate）
- 做非常简单的统计分析（p95 spill bytes / total shuffle bytes → 真正的内存短板在哪里）
- 推荐一组调整并**解释为什么**——"你的查询中 execution memory 在 p95 下仅占用 60% 的池，但 storage 会在 80% 的查询中被驱逐→建议增加 executionFraction"

这种推荐的"格式"恰好是 LLM 的强项——将统计数字转化为自然语言解释——而它的"弱点"（数学建模不精确）在这里影响不大，因为调参本身就是一个近似优化。

## 源码导航

| 文件 | 关键内容 | 行号参考 |
|------|---------|---------|
| `core/src/main/scala/org/apache/spark/memory/MemoryManager.scala` | MemoryManager 抽象类，四个内存池初始化，tungstenMemoryMode 决策，defaultPageSizeBytes 计算，GC-aware 页面大小调整 | 39 (abstract class), 49-56 (four pools), 228 (tungstenMemoryMode), 251 (defaultPageSizeBytes) |
| `core/src/main/scala/org/apache/spark/memory/UnifiedMemoryManager.scala` | UnifiedMemoryManager，acquireExecutionMemory (storage→execution 借用+mEvict)，acquireStorageMemory (execution→storage 空闲借用)，getMaxMemory 计算，unmanaged memory polling | 58 (class), 134 (acquireExecutionMemory), 206 (acquireStorageMemory), 462 (getMaxMemory) |
| `core/src/main/scala/org/apache/spark/memory/ExecutionMemoryPool.scala` | ExecutionMemoryPool，acquireMemory 公平仲裁 1/2N~1/N，releaseMemory 释放通知，wait/notifyAll 阻塞机制 | 43 (class), 92 (acquireMemory with while loop), 154 (releaseMemory) |
| `core/src/main/scala/org/apache/spark/memory/StorageMemoryPool.scala` | StorageMemoryPool，acquireMemory (evict to make space)，freeSpaceToShrinkPool (execution 回收 storage 空间) | 35 (class), 68 (acquireMemory), 121 (freeSpaceToShrinkPool) |
| `core/src/main/java/org/apache/spark/memory/TaskMemoryManager.java` | TaskMemoryManager，页表 pageTable，13+51-bit 地址编码，acquireExecutionMemory spill loop，TreeMap 排序 consumer spill 优先级 | 56 (class), 90 (pageTable), 146 (construct), 159 (acquireExecutionMemory with spill) |
| `core/src/main/java/org/apache/spark/memory/MemoryConsumer.java` | MemoryConsumer 抽象类，spill(size, trigger) 方法签名，used AtomicLong 追踪 | 32 (abstract class), 66 (spill) |
| `common/utils-java/src/main/java/org/apache/spark/memory/MemoryMode.java` | MemoryMode 枚举 ON_HEAP/OFF_HEAP | |
