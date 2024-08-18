# 第 4 章 · 内存管理与 IO 子系统

## 导读

- **一句话**：本章回答"Flink 如何管理内存，让网络缓冲、排序缓存、State 三者之间不互相挤压导致 JVM OOM？"
- **前置知识**：JVM 内存区域（Heap、Direct、Metaspace）、OS 虚拟内存概念、第 2 章的 MemorySegment 设计。
- **读完本章你能回答**：
  - Flink TaskManager 的内存布局——框架堆/Task堆/Network/Direct 怎么划分？
  - `NetworkBufferPool` 的两级池设计精髓是什么？`redistributeBuffers()` 如何按比例重新分配？
  - `LocalBufferPool` 的 overdraft buffer 机制是什么？`maxBuffersPerChannel` 如何防止单个 subpartition 独占所有 buffer？
  - `IOManagerAsync` 的 WriterThread/ReaderThread 模型是怎样的？
  - 对比 OS 虚拟内存页管理——Flink MemorySegment 的 page 式设计

---

## 4.1 — 设计动机：JVM 内存是三个竞争者的公共池

Flink TaskManager 中有三类内存消费者：
1. **用户代码 + 框架**：算子对象、State Backend 缓存、RocksDB 原生内存
2. **Network Buffer**：上下游数据传输的缓冲区——第 16 章展开
3. **Sort/Hash/Spill Buffer**：批处理 shuffle、Join/Hash 操作的临时内存

这三者如果全部放任在堆上，任何一个需求暴涨都会引发 GC 雪崩——其他所有任务都跟着受影响。Flink 的答案：**预先切断内存池——Network 池、Sort/Spill 池、框架内存，三者物理隔离**。

---

## 4.2 — TaskManager 内存模型

Flink TaskManager 对内存切分可用下面几种模型：

```
Total Flink Memory (所有内存)
├── Framework Heap      RPC/Pekko/WebUI 的对象      (堆内)
├── Task Heap           用户代码 + 算子对象         (堆内)
├── Framework Off-Heap  (不常见)                    (堆外)
├── Task Off-Heap       默认 0                      (堆外)
├── Network Memory      NetworkBufferPool           (堆外/堆内可选)
└── Managed Memory      Sort/Hash/Spill/RocksDB     (堆外/堆内可选)
```

`Managed Memory` 是 Flink 对批计算工作负载的专用内存——RocksDB State Backend 也会把它用作写缓冲和 Block Cache。它由 `taskmanager.memory.managed.fraction` 控制（默认 0.4 = 40% Flink 内存）。

### 参数速查

```yaml
taskmanager.memory.process.size: 1728m        # 整个 JVM 进程的最大内存
taskmanager.memory.flink.size: 1280m          # Flink 可控内存的总额（分框架+任务+Network+Managed）
taskmanager.memory.task.heap.size: 512m       # 用户代码堆
taskmanager.memory.managed.size: 512m         # Managed Memory
taskmanager.memory.network.min: 64m
taskmanager.memory.network.max: 1g
```

### 为什么默认尽量推外

- **Network Memory** 默认走 Direct Memory——不受 GC 扫描，不触发 GC 暂停
- **Managed Memory** 默认也推外——Sort Buffer、Hash Table 在 Direct Memory 中操作

这其实是一个计算机体系结构层面的设计：**把"流数据"从 JVM 内存体系中抽离到 OS 级虚拟内存空间**，类似 OS 中对 I/O buffer 使用 DMA 直接进入内核空间而不经过用户空间拷贝（零拷贝）。

---

## 4.3 — NetworkBufferPool：全局 Buffer 池源码走读

`NetworkBufferPool` 是 Flink 网络栈的全局内存段池（`flink-runtime/.../io/network/buffer/NetworkBufferPool.java:63`）：

```java
public class NetworkBufferPool
        implements BufferPoolFactory, MemorySegmentProvider, AvailabilityProvider {

    private final int totalNumberOfMemorySegments;        // 总段数
    private final int memorySegmentSize;                  // 每段大小
    private final ArrayDeque<MemorySegment> availableMemorySegments;  // 空闲段队列
    private volatile boolean isDestroyed;                 // 销毁标记

    private final Object factoryLock = new Object();     // 池管理锁
    private final Set<LocalBufferPool> allBufferPools = new HashSet<>();     // 所有子池
    private final Set<LocalBufferPool> resizableBufferPools = new HashSet<>(); // 可调子池
    private int numTotalRequiredBuffers;                  // 所有子池的保证段数之和
    private final Duration requestSegmentsTimeout;       // 请求超时
}
```

### 构造函数：启动时一次性分配

```java
// NetworkBufferPool.java:102-161
public NetworkBufferPool(
        int numberOfSegmentsToAllocate, int segmentSize, Duration requestSegmentsTimeout) {
    this.totalNumberOfMemorySegments = numberOfSegmentsToAllocate;
    this.memorySegmentSize = segmentSize;
    this.availableMemorySegments = new ArrayDeque<>(numberOfSegmentsToAllocate);

    for (int i = 0; i < numberOfSegmentsToAllocate; i++) {
        availableMemorySegments.add(
                MemorySegmentFactory.allocateUnpooledOffHeapMemory(segmentSize, null));
        // ↑ 全部分配为堆外内存！
    }

    LOG.info("Allocated {} MB for network buffer pool (number of memory segments: {}, bytes per segment: {}).",
            allocatedMb, availableMemorySegments.size(), segmentSize);
}
```

**关键设计**：`MemorySegmentFactory.allocateUnpooledOffHeapMemory()` 将所有网络缓冲分配为堆外 Direct Memory。启动时一次性分配所有段，运行时不再增长或缩小。

### createBufferPool：创建子池并重分配

```java
// NetworkBufferPool.java:475-525
private BufferPool internalCreateBufferPool(
        int numRequiredBuffers, int maxUsedBuffers,
        int numSubpartitions, int maxBuffersPerChannel, int maxOverdraftBuffersPerGate)
        throws IOException {

    synchronized (factoryLock) {
        // 检查：保证段数不能超过总量
        if (numTotalRequiredBuffers + numRequiredBuffers > totalNumberOfMemorySegments) {
            throw new IOException("Insufficient number of network buffers: required "
                    + numRequiredBuffers + ", but only "
                    + (totalNumberOfMemorySegments - numTotalRequiredBuffers) + " available.");
        }

        this.numTotalRequiredBuffers += numRequiredBuffers;

        LocalBufferPool localBufferPool = new LocalBufferPool(
                this, numRequiredBuffers, maxUsedBuffers,
                numSubpartitions, maxBuffersPerChannel, maxOverdraftBuffersPerGate);

        allBufferPools.add(localBufferPool);
        if (numRequiredBuffers < maxUsedBuffers) {
            resizableBufferPools.add(localBufferPool);  // ← 可调大小的池
        }

        redistributeBuffers();  // ★ 重新分配缓冲段给所有子池

        return localBufferPool;
    }
}
```

### redistributeBuffers：按比例分配空闲段

```java
// NetworkBufferPool.java:594-669
private void redistributeBuffers() {
    assert Thread.holdsLock(factoryLock);

    // 总空闲段 = 总段数 - 所有子池的保证段数之和
    final int numAvailableMemorySegment = totalNumberOfMemorySegments - numTotalRequiredBuffers;

    if (numAvailableMemorySegment == 0) {
        // 没有空闲段，每个池只保留保证段数
        for (LocalBufferPool bufferPool : resizableBufferPools) {
            bufferPool.setNumBuffers(bufferPool.getNumberOfRequiredMemorySegments());
        }
        return;
    }

    // 按各池的"容量"比例分配空闲段
    long totalCapacity = 0;
    for (LocalBufferPool bufferPool : resizableBufferPools) {
        int excessMax = bufferPool.getMaxNumberOfMemorySegments()
                - bufferPool.getNumberOfRequiredMemorySegments();
        totalCapacity += Math.min(numAvailableMemorySegment, excessMax);
    }

    // 按比例切分
    for (LocalBufferPool bufferPool : resizableBufferPools) {
        int excessMax = bufferPool.getMaxNumberOfMemorySegments()
                - bufferPool.getNumberOfRequiredMemorySegments();
        if (excessMax == 0) continue;

        totalPartsUsed += Math.min(numAvailableMemorySegment, excessMax);
        final int mySize = checkedDownCast(
                memorySegmentsToDistribute * totalPartsUsed / totalCapacity
                        - numDistributedMemorySegment);

        numDistributedMemorySegment += mySize;
        bufferPool.setNumBuffers(bufferPool.getNumberOfRequiredMemorySegments() + mySize);
    }
}
```

**重分配公式**：每个可调子池分到的额外段数 = `空闲段总数 × (该池的容量 / 所有池的容量之和)`。这是一个"保证基数 + 按比例分增量"的模式——类似 OS 的内存 overcommit 管理。

### Pooled vs Unpooled 段

```java
// NetworkBufferPool.java:170-228
// Pooled 段：通过 LocalBufferPool 分配，不修改 numTotalRequiredBuffers
@Nullable
public MemorySegment requestPooledMemorySegment() {
    synchronized (availableMemorySegments) {
        return internalRequestMemorySegment();  // 直接从空闲队列取
    }
}

// Unpooled 段：直接从全局池分配，需要增加 numTotalRequiredBuffers 并重分配
@Override
public List<MemorySegment> requestUnpooledMemorySegments(int numberOfSegmentsToRequest) {
    synchronized (factoryLock) {
        tryRedistributeBuffers(numberOfSegmentsToRequest);  // ← 增加保证数 + 重分配
    }
    return internalRequestMemorySegments(numberOfSegmentsToRequest);
}
```

**Unpooled 段**用于 `RemoteInputChannel` 的 exclusive credit——这些段永久绑定到某个 channel，不会归还给 `LocalBufferPool`。

---

## 4.4 — LocalBufferPool：Task 级 Buffer 池源码走读

`LocalBufferPool` 是每个 Task 使用的缓冲池（`flink-runtime/.../io/network/buffer/LocalBufferPool.java:71`）：

```java
public class LocalBufferPool implements BufferPool {
    private final NetworkBufferPool networkBufferPool;       // 全局池
    private final int numberOfRequiredMemorySegments;        // 保证段数（最小值）
    private final ArrayDeque<MemorySegment> availableMemorySegments; // 本池空闲段
    private final ArrayDeque<BufferListener> registeredListeners;    // 等待 buffer 的监听者
    private final int maxNumberOfMemorySegments;             // 最大段数
    @GuardedBy("availableMemorySegments")
    private int currentPoolSize;                             // 当前池大小（动态调整）
    @GuardedBy("availableMemorySegments")
    private int numberOfRequestedMemorySegments;             // 已从全局池申请的段数
    private final int maxBuffersPerChannel;                  // 每个通道最大 buffer 数
    @GuardedBy("availableMemorySegments")
    private final int[] subpartitionBuffersCount;            // 每个 subpartition 的 buffer 计数
    private int maxOverdraftBuffersPerGate;                  // 透支 buffer 上限
}
```

### requestMemorySegment：buffer 申请的核心逻辑

```java
// LocalBufferPool.java:393-419
@Nullable
private MemorySegment requestMemorySegment(int targetChannel) {
    MemorySegment segment = null;
    synchronized (availableMemorySegments) {
        checkDestroyed();

        if (!availableMemorySegments.isEmpty()) {
            segment = availableMemorySegments.poll();       // ① 优先从本池空闲队列取
        } else if (isRequestedSizeReached()) {
            // ② 本池已满，尝试透支
            segment = requestOverdraftMemorySegmentFromGlobal();
        }

        if (segment == null) {
            return null;  // ③ 完全没 buffer 可用 → 返回 null（触发反压）
        }

        if (targetChannel != UNKNOWN_CHANNEL) {
            if (++subpartitionBuffersCount[targetChannel] == maxBuffersPerChannel) {
                unavailableSubpartitionsCount++;  // ← 该 subpartition 达到上限
            }
        }

        checkAndUpdateAvailability();  // 更新可用状态 + 通知等待者
    }
    return segment;
}
```

### Overdraft Buffer 机制

```java
// LocalBufferPool.java:450-460
@GuardedBy("availableMemorySegments")
private MemorySegment requestOverdraftMemorySegmentFromGlobal() {
    // 透支段数 = 已申请段数 - 当前池大小
    // 如果透支段数 >= 最大透支上限，拒绝申请
    if (numberOfRequestedMemorySegments - currentPoolSize >= maxOverdraftBuffersPerGate) {
        return null;
    }
    return requestPooledMemorySegment();  // 从全局池拿
}
```

**Overdraft buffer** 是 Flink 1.14+ 引入的机制——即使 LocalBufferPool 的 `currentPoolSize` 已满，也允许少量"透支"从全局池申请额外段。这避免了因为 `maxBuffersPerChannel` 限制导致的局部死锁：某个 subpartition 达到上限后，其他 subpartition 仍然可以通过 overdraft buffer 获得缓冲。

### maxBuffersPerChannel：防止单个 subpartition 独占

```java
// LocalBufferPool.java:514-518
@GuardedBy("availableMemorySegments")
private boolean shouldBeAvailable() {
    return !availableMemorySegments.isEmpty() && unavailableSubpartitionsCount == 0;
}
```

`shouldBeAvailable()` 要求两个条件同时满足：
1. 有空闲段
2. 没有 subpartition 达到 `maxBuffersPerChannel` 上限

这防止了"某一个慢消费者 subpartition 独占所有 buffer，导致其他 subpartition 也被饿死"的问题——这是网络栈反压的关键保障。

### recycle：Buffer 回收

```java
// LocalBufferPool.java:579-609
private void recycle(MemorySegment segment, int channel) {
    synchronized (availableMemorySegments) {
        if (channel != UNKNOWN_CHANNEL) {
            if (subpartitionBuffersCount[channel]-- == maxBuffersPerChannel) {
                unavailableSubpartitionsCount--;  // ← 离开上限状态
            }
        }

        if (isDestroyed || hasExcessBuffers()) {
            returnMemorySegment(segment);  // ← 多余段归还给全局池
        } else {
            listener = registeredListeners.poll();
            if (listener == null) {
                availableMemorySegments.add(segment);  // ← 放回本池空闲队列
            }
        }
    }
}
```

Buffer 永远不"丢失"——要么放回本池空闲队列，要么归还给全局池，要么直接给等待的 listener。这个"Buffer 永不丢失"的保证是 Flink 网络栈可靠性的基础。

### 可用性通知机制

```java
// LocalBufferPool.java:482-511
@GuardedBy("availableMemorySegments")
private void requestMemorySegmentFromGlobalWhenAvailable() {
    requestingNotificationOfGlobalPoolAvailable = true;
    assertNoException(
            networkBufferPool.getAvailableFuture().thenRun(this::onGlobalPoolAvailable));
    // ↑ 注册回调：全局池有段可用时通知本池
}

private void onGlobalPoolAvailable() {
    synchronized (availableMemorySegments) {
        requestingNotificationOfGlobalPoolAvailable = false;
        if (isDestroyed || availabilityHelper.isApproximatelyAvailable()) {
            return;  // 已经可用了，不需要再申请
        }
        toNotify = checkAndUpdateAvailability();  // 尝试从全局池申请 + 更新状态
    }
    mayNotifyAvailable(toNotify);
}
```

当 `LocalBufferPool` 自身没有空闲段且全局池也没有时，它注册一个回调到全局池的 `AvailabilityFuture`——一旦全局池有段回收，就会通知所有等待的 `LocalBufferPool`。

---

## 4.5 — IOManager：异步 IO 与磁盘溢写

### 设计

`IOManager` 管理着 Flink 所有对磁盘的异步 IO——包括：
- 排序溢写（Spill to Disk）
- Hash Join 中把大的 Hash 表写盘
- Checkpoint 时的 State 写入文件

### IOManagerAsync：生产级实现

`IOManagerAsync` 是生产级实现（`flink-runtime/.../io/disk/iomanager/IOManagerAsync.java:40`）：

```java
public class IOManagerAsync extends IOManager implements UncaughtExceptionHandler {
    private final WriterThread[] writers;    // 每个 temp 目录一个写线程
    private final ReaderThread[] readers;    // 每个 temp 目录一个读线程
    private final AtomicBoolean isShutdown = new AtomicBoolean();
}
```

**线程模型**：每个临时目录配一个 `WriterThread` 和一个 `ReaderThread`——它们各自维护一个 `RequestQueue`，生产者提交请求到队列，IO 线程从队列取出请求执行。

### WriterThread 主循环

```java
// IOManagerAsync.java:496-543
private static final class WriterThread extends Thread {
    protected final RequestQueue<WriteRequest> requestQueue;
    private volatile boolean alive;

    @Override
    public void run() {
        while (this.alive) {
            WriteRequest request = null;
            while (alive && request == null) {
                request = requestQueue.take();  // ← 阻塞等待写请求
            }

            IOException ioex = null;
            try {
                request.write();               // ← 执行写操作
            } catch (IOException e) {
                ioex = e;
            }

            request.requestDone(ioex);         // ← 通知完成（成功或失败）
        }
    }
}
```

ReaderThread 结构完全对称——`request.read()` 替代 `request.write()`。

### 创建 Writer/Reader 的 API

```java
// IOManager.java:152-206
// 带回调队列的 Block Writer
public BlockChannelWriter<MemorySegment> createBlockChannelWriter(
        ID channelID, LinkedBlockingQueue<MemorySegment> returnQueue) throws IOException;

// 带回调函数的 Block Writer
public BlockChannelWriterWithCallback<MemorySegment> createBlockChannelWriter(
        ID channelID, RequestDoneCallback<MemorySegment> callback) throws IOException;

// Block Reader
public BlockChannelReader<MemorySegment> createBlockChannelReader(
        ID channelID, LinkedBlockingQueue<MemorySegment> returnQueue) throws IOException;

// Buffer 级别的 Writer/Reader（用于 Checkpoint 等）
public BufferFileWriter createBufferFileWriter(ID channelID) throws IOException;
public BufferFileReader createBufferFileReader(
        ID channelID, RequestDoneCallback<Buffer> callback) throws IOException;
```

两种回调模式：
1. **returnQueue**：写完的 `MemorySegment` 放入阻塞队列，调用方从队列取回——适合批量场景
2. **RequestDoneCallback**：写完后直接调回调函数——适合流式场景

### 异步 IO 的完整流程

```
排序/Join 算子:
  1. 算子请求 IOManager 创建 BlockChannelWriter(channelID, returnQueue)
  2. 算子将 MemorySegment 提交给 Writer: writer.writeBlock(segment)
     → Writer 将 WriteRequest 放入 WriterThread.requestQueue
  3. 算子继续处理数据（不需要等写完成）
  4. WriterThread 从 requestQueue 取出请求 → request.write() → FileChannel.write()
  5. 写完后 request.requestDone() → segment 放入 returnQueue
  6. 算子从 returnQueue 取回 segment，重新用于内存排序
```

关键在于步骤 3：算子提交写请求后**不阻塞**，可以继续处理内存中的数据。只有当内存中的段全部写完需要更多段时，才从 `returnQueue` 取回已写完的段——这就是"生产者-消费者"的异步模型。

---

## 4.6 — 与 OS 虚拟内存管理的类比

Flink 的内存体系跟我学计算机体系结构时遇到的虚拟内存极其相似：

| OS 概念 | Flink 对应 | 说明 |
|---------|-----------|------|
| 物理页框 | `MemorySegment`（固定 32KB） | 原子分配单元 |
| 虚拟页表 | `MemorySegmentSource` — 段所有权 | 索引到物理存储 |
| 页换出 | 排序/哈希溢写 — IOManager | 内存压力 → 写盘 |
| 页换入 | 从磁盘读回 — IOManager.async read | 需要时拉回内存 |
| 页面故障 | "Buffer 耗尽"条件 | 向父池请求新段 |
| 页面替换 | `redistributeBuffers()` 按比例重分配 | 归还/重新分配 MemorySegment |
| Overcommit | Overdraft Buffer | 临时超额分配 |

这不是巧合——这确实就是 Flink 设计者从 OS 虚拟内存管理中获取的灵感。关键差异是：Flink 的"页"大小是 32KB，远大于 OS 的 4KB 页——因为计算引擎的工作集的特征是"少量大数据流"，少量大对象暂存更优（减少页表项数量，提高段拷贝效率）。

`redistributeBuffers()` 类似 OS 的页面调度器——当新的 `LocalBufferPool` 创建或旧的销毁时，空闲段按比例重新分配给所有可调池。这跟 Linux 的 `kswapd` 在内存压力下回收页框的逻辑异曲同工。

---

## 4.7 — 横向对比

### vs Spark 内存管理

Spark 1.6+ 统一内存管理：
- **Execution Memory** ≈ Flink Managed Memory（Shuffle 临时内存）
- **Storage Memory**（RDD Cache）— Flink 无直接对应（Flink 用 state backend 替代 RDD cache）
- 两者**可以互相借用**——这是 Spark 比 Flink 灵活的地方，也是它比 Flink 复杂的地方

Flink Network Buffer 是独立的（Spark 这边没有"网络缓冲池"概念——依赖 Netty 的 Channel 内部缓冲）。

Flink 的 `maxBuffersPerChannel` + overdraft 机制是 Spark 没有的——Spark 不需要这个因为它没有"持续运行的算子"之间的 credit-based flow control。

### vs StarRocks

StarRocks 的 BE 节点内存分配完全由 C++ 管理——Arena allocator 为每个 Fragment 分配一块大内存，处理完一并回收。比 Flink 简单很多——不需要在 JVM 和 Direct Memory 之间周旋。

---

## 4.8 — 调优与实战陷阱

### Managed Memory + RocksDB 的组合

RocksDB State Backend 使用 Managed Memory 作为它的写缓冲 + Block Cache。如果你配置 `taskmanager.memory.managed.size: 256mb` 且用 RocksDB，实际上每个 Slot 分到很小的 Buffer → RocksDB 频繁刷盘 → 吞吐急剧下降。

推荐公式：**Managed Memory / 每个 TM 的 Slot 数** 至少要 50-100MB 给每个 RocksDB 实例。

### Network Buffer 不够 → 反压

如果你在 Web UI 中看到高反压，但 TM CPU 很低——大概率是 Network Buffer 不够（第 11 章细讲）。先大胆翻倍 `taskmanager.memory.network.max`。

NetworkBufferPool 的 usage warning（`NetworkBufferPool.java:393-421`）会在使用率超过 100% 时打印警告——这说明所有 `LocalBufferPool` 的最大需求之和超过了全局池的总量，某些请求必然会等待。

### Direct Memory OOM 最坑

`io.netty.util.internal.OutOfDirectMemoryError` 不一定是 Network Buffer 超了——也可能是用户代码里自己分配了 DirectBuffer。检查：
```
-XX:MaxDirectMemorySize 是否等于 taskmanager.memory.network.max + 其他 Direct 用途
```

### IOManager 的 temp 目录配置

`IOManagerAsync` 为每个临时目录创建一对读写线程。如果只配了一个目录，所有溢写 IO 串行化在这个目录的磁盘上——吞吐瓶颈。建议配置多个目录分布在不同磁盘：
```yaml
io.tmp.dirs: /disk1/flink-tmp,/disk2/flink-tmp,/disk3/flink-tmp
```

---

## 本章要点回顾

1. Flink 内存 = 框架堆 + Task 堆 + Network（Direct）+ Managed（Direct）——四个物理隔离池，互相不会挤压。
2. `NetworkBufferPool` 构造时一次性分配所有堆外 `MemorySegment`，`redistributeBuffers()` 按比例将空闲段分配给各 `LocalBufferPool`。
3. `LocalBufferPool` 的关键机制：保证基数 + 按比例弹性增长 + overdraft 透支 + `maxBuffersPerChannel` 防独占 + 可用性通知回调链。
4. `IOManagerAsync` 的 WriterThread/ReaderThread 提供生产者-消费者式的异步 IO——returnQueue 或 RequestDoneCallback 两种完成通知模式。
5. Flink 内存管理与 OS 虚拟内存管理高度相似——MemorySegment（页框）、IOManager（页交换）、redistributeBuffers（页面调度器）。

## 源码导航

- NetworkBufferPool：`flink-runtime/.../io/network/buffer/NetworkBufferPool.java`（L63，构造 L102，createBufferPool L475，redistributeBuffers L594）
- LocalBufferPool：`flink-runtime/.../io/network/buffer/LocalBufferPool.java`（L71，requestMemorySegment L393，recycle L579，overdraft L450）
- IOManager 抽象：`flink-runtime/.../io/disk/iomanager/IOManager.java`（L41）
- IOManagerAsync：`flink-runtime/.../io/disk/iomanager/IOManagerAsync.java`（L40，WriterThread L436，ReaderThread L327）
- MemorySegment：`flink-core/.../core/memory/MemorySegment.java`
- MemorySegmentFactory：`flink-core/.../core/memory/MemorySegmentFactory.java`
- 内存配置解析：`flink-runtime/.../taskexecutor/TaskManagerServicesConfiguration.java`
- TaskManager 内存切分：`flink-runtime/.../taskexecutor/TaskManagerServices.java`
