# 第 22 章 `java.util.concurrent` 并发框架

> 源码路径：`src/java.base/share/classes/java/util/concurrent/`

`java.util.concurrent`（JUC）是 Java 并发编程的核心框架，由 Doug Lea 设计。它的实现大量使用 `VarHandle`、CAS、`LockSupport.park/unpark` 和 `ForkJoinPool`，是理解 Java 并发的最佳实践库。本章深入几个核心组件的源码。

---

## 22.1 `ForkJoinPool`：工作窃取调度器源码剖析

### 22.1.1 ForkJoinPool 的架构

```
ForkJoinPool
├── WorkQueue[] queues     // 工作队列数组
│   ├── queues[0]          // 外部提交队列（共享）
│   ├── queues[1]          // worker-1 的工作队列（独享）
│   ├── queues[3]          // worker-2 的工作队列（独享）
│   └── ...
├── ForkJoinWorkerThread[] workers  // 工作线程
└── volatile long stealCount        // 窃取计数
```

### 22.1.2 WorkQueue 的双端队列

```java
// ForkJoinPool.java（简化）
static final class WorkQueue {
    int           top;           // 栈顶（LIFO，当前线程操作端）
    int           base;          // 栈底（FIFO，其他线程窃取端）
    ForkJoinTask<?>[] array;     // 任务数组

    // 当前线程 push（LIFO）
    void push(ForkJoinTask<?> t) {
        ForkJoinTask<?>[] a = array;
        a[top] = t;
        top = nextTop;
    }

    // 其他线程窃取（FIFO）
    ForkJoinTask<?> poll() {
        int b = base;
        if (b < top) {
            ForkJoinTask<?> t = array[b];
            if (CAS_BASE(b, b + 1))  // CAS 竞争
                return t;
        }
        return null;
    }
}
```

### 22.1.3 工作窃取算法

```
1. Worker 线程从自己的 WorkQueue 的 top 取任务（LIFO）
2. 如果自己的队列空了，从其他 worker 的 base 窃取（FIFO）
3. 如果所有队列都空，进入休眠（park）

窃取的优势：
  - LIFO 保证缓存局部性（最近提交的任务最热）
  - FIFO 窃取保证大任务先被窃取（减少窃取次数）
  - CAS 无锁窃取，避免锁竞争
```

### 22.1.4 ForkJoinPool 与虚拟线程

JDK 21 的虚拟线程默认使用 ForkJoinPool 作为载体线程池：

```java
// VirtualThread.java
private static final ForkJoinPool DEFAULT_CARRIER_POOL =
    new ForkJoinPool(CARRIER_COUNT, ...);
```

---

## 22.2 `CompletableFuture`：异步编程模型

### 22.2.1 CompletableFuture 的链式调用

```java
CompletableFuture<String> future = CompletableFuture
    .supplyAsync(() -> fetchData())          // 异步获取数据
    .thenApply(data -> process(data))        // 同步转换
    .thenCompose(result -> saveAsync(result)) // 异步组合
    .exceptionally(ex -> fallback());         // 异常处理
```

### 22.2.2 CompletableFuture 的内部实现

```java
// CompletableFuture.java（简化）
class CompletableFuture<T> {
    volatile Object result;    // 结果或异常
    volatile Completion stack; // 依赖链栈

    // Completion 是依赖链的节点
    abstract static class Completion {
        volatile Completion next;  // 链表
        abstract CompletableFuture<?> fire();
    }
}
```

当 `result` 被设置时，触发栈上所有 `Completion` 节点：

```
1. CAS 设置 result（确保只设置一次）
2. 遍历 stack 中的 Completion 节点
3. 对每个节点调用 fire()，执行后续操作
4. fire() 可能将结果传播到下一个 CompletableFuture
```

### 22.2.3 线程池选择

```
supplyAsync(() -> ...)             → ForkJoinPool.commonPool()
supplyAsync(() -> ..., executor)   → 指定的 Executor
thenApply(fn)                      → 调用者线程
thenApplyAsync(fn)                 → ForkJoinPool.commonPool()
```

---

## 22.3 `ConcurrentHashMap`：并发哈希表的分段与 CAS

### 22.3.1 ConcurrentHashMap 的结构

JDK 8+ 的 `ConcurrentHashMap` 不再使用分段锁（Segment），而是使用 CAS + `synchronized`：

```
ConcurrentHashMap
├── volatile Node<K,V>[] table     // 哈希表
├── volatile Node<K,V>[] nextTable // 扩容时的新表
├── volatile long baseCount        // 基础计数
├── CounterCell[] counterCells     // 分散计数
└── volatile int sizeCtl           // 控制标志
```

### 22.3.2 put 操作的并发控制

```java
// ConcurrentHashMap.java（简化）
final V putVal(K key, V value) {
    int hash = spread(key.hashCode());
    for (Node<K,V>[] tab = table;;) {
        Node<K,V> f; int n, i;
        if (tab == null || (n = tab.length) == 0)
            tab = initTable();                    // 懒初始化
        else if ((f = tab[i = (n-1) & hash]) == null) {
            if (casTabAt(i, null, new Node<>(hash, key, value)))  // CAS 插入
                break;
        }
        else if (f.hash == MOVED)
            tab = helpTransfer(tab, f);           // 协助扩容
        else {
            synchronized (f) {                     // 锁住桶头节点
                // 遍历链表/红黑树，插入或更新
            }
        }
    }
    addCount(1L);  // 更新计数
    return null;
}
```

### 22.3.3 扩容的并发化

扩容时多个线程可以协作：

```
1. 线程检测到需要扩容（sizeCtl < 0 表示正在扩容）
2. 线程认领一段桶（stride = 桶数 / CPU数）
3. 线程将认领的桶从旧表迁移到新表
4. 在旧表的位置放置 ForwardingNode（hash = MOVED）
5. 其他线程遇到 ForwardingNode 时协助迁移

优势：扩容不阻塞读操作，多线程加速迁移
```

---

## 22.4 `StampedLock`：乐观读锁

### 22.4.1 StampedLock 的模式

```java
StampedLock sl = new StampedLock();

// 1. 乐观读（无锁）
long stamp = sl.tryOptimisticRead();
// ... 读数据 ...
if (!sl.validate(stamp)) {
    // 乐观读失败，升级为悲观读锁
    stamp = sl.readLock();
    try { /* 重新读数据 */ } finally { sl.unlockRead(stamp); }
}

// 2. 悲观读锁
long stamp = sl.readLock();
try { /* 读数据 */ } finally { sl.unlockRead(stamp); }

// 3. 写锁
long stamp = sl.writeLock();
try { /* 写数据 */ } finally { sl.unlockWrite(stamp); }
```

### 22.4.2 StampedLock 的内部实现

```java
// StampedLock.java（简化）
class StampedLock {
    volatile long state;  // 锁状态：读计数 + 写标志 + 版本号

    // 乐观读：检查 state 的版本号
    long tryOptimisticRead() {
        long s = state;
        return (s & WBIT) != 0 ? 0L : (s & SBITS);  // 无写锁时返回版本号
    }

    // 验证乐观读
    boolean validate(long stamp) {
        VarHandle.acquireFence();  // LoadLoad 屏障
        return (state & SBITS) == (stamp & SBITS);  // 版本号未变
    }
}
```

---

## 22.5 `atomic / VarHandle`：原子变量与底层映射

### 22.5.1 AtomicInteger 的实现

```java
// AtomicInteger.java
class AtomicInteger {
    private volatile int value;

    public int getAndIncrement() {
        return U.getAndAddInt(this, VALUE, 1);
        // → Unsafe.getAndAddInt()
        //   → VarHandle.getAndAdd()
        //     → AtomicAccess::xchg() (HotSpot)
        //       → lock xadd [addr], 1  (x86)
    }
}
```

### 22.5.2 LongAdder 的分散计数

`LongAdder` 使用分散计数避免 CAS 热点：

```java
// LongAdder.java
class LongAdder extends Striped64 {
    // 基础值 + Cell[] 分散值
    volatile long base;
    volatile Cell[] cells;

    void add(long x) {
        Cell[] as;
        if ((as = cells) != null || !casBase(b, b + x)) {
            // CAS 竞争 → 分散到 Cell
            int index = getProbe() & (as.length - 1);
            Cell a = as[index];
            a.cas(v, v + x);  // 每个 Cell 独立 CAS，减少竞争
        }
    }

    long sum() {
        long sum = base;
        for (Cell c : cells) sum += c.value;
        return sum;
    }
}
```

---

## 22.6 [体系结构视角] `@Contended` 与 False Sharing 的硬件真相

### 22.6.1 False Sharing 的实测影响

```
两个线程各自更新相邻的 volatile long（同一缓存行）：

无填充：
  吞吐量：~50M ops/s

@Contended 填充（128 字节隔离）：
  吞吐量：~500M ops/s

提升：10 倍
```

### 22.6.2 JDK 内部使用 @Contended

JDK 内部大量使用 `@Contended` 避免 false sharing：

```java
@jdk.internal.vm.annotation.Contended
class Striped64.Cell {
    volatile long value;
}

@jdk.internal.vm.annotation.Contended
class ForkJoinPool.WorkQueue { ... }

@jdk.internal.vm.annotation.Contended
class StampedLock { ... }
```

### 22.6.3 用户代码启用 @Contended

```
默认情况下，@Contended 只对 JDK 内部类生效。
用户代码需要：
-XX:-RestrictContended  # 允许用户类使用 @Contended
```

---

## 小结

本章深入了 JUC 并发框架的核心组件：

1. **ForkJoinPool** 使用工作窃取算法，LIFO 执行 + FIFO 窃取，CAS 无锁
2. **CompletableFuture** 通过 Completion 链实现异步组合
3. **ConcurrentHashMap** 使用 CAS 插入 + `synchronized` 桶锁，多线程协作扩容
4. **StampedLock** 的乐观读通过版本号验证，避免加锁
5. **LongAdder** 分散计数避免 CAS 热点，是高并发计数的最佳选择
6. **@Contended** 消除 false sharing，对高频更新的共享变量效果显著

下一章将深入 NIO 与内存映射。
