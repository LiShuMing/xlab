# 第 19 章 虚拟线程：协程的 JVM 实现

> 源码路径：`src/java.base/share/classes/java/lang/VirtualThread.java`、`src/hotspot/share/runtime/continuation.cpp`、`src/hotspot/share/runtime/continuationFreezeThaw.cpp`、`src/hotspot/share/oops/stackChunkOop.hpp`

虚拟线程（Virtual Thread）是 JDK 21 引入的轻量级线程，它将线程的调度从操作系统移到了 JVM 用户态。一个虚拟线程只占用几百字节（而非传统线程的 1MB 栈），可以轻松创建百万级并发。本章从 Java API 到 HotSpot 内部实现，深入虚拟线程的完整机制。

---

## 19.1 `VirtualThread.java`：虚拟线程的 Java API

### 19.1.1 创建与启动

```java
// 方式 1：Thread.ofVirtual()
Thread vt = Thread.ofVirtual()
    .name("my-vthread")
    .start(() -> System.out.println("Hello from virtual thread"));

// 方式 2：Executors
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    executor.submit(() -> doWork());
}

// 方式 3：Thread.startVirtualThread
Thread.startVirtualThread(() -> doWork());
```

### 19.1.2 虚拟线程 vs 平台线程

| 特性 | 平台线程 | 虚拟线程 |
|------|---------|---------|
| 实现 | OS 线程（1:1） | JVM 协程（M:N） |
| 栈大小 | 固定 ~1MB | 按需增长，几百字节起 |
| 创建成本 | ~1ms | ~1μs |
| 调度 | OS 调度器 | ForkJoinPool 调度 |
| 阻塞 | 阻塞 OS 线程 | 卸载（unmount），释放载体线程 |
| 数量上限 | 数千 | 数百万 |

### 19.1.3 挂载与卸载

虚拟线程运行在载体线程（carrier thread）上。当虚拟线程执行阻塞操作时，它从载体线程上「卸载」，释放载体线程给其他虚拟线程使用：

```
载体线程 (ForkJoinPool worker)
  │
  ├── 挂载 VT-1 → 执行代码
  │     │
  │     └── VT-1 执行 Socket.read()（阻塞操作）
  │           │
  │           └── 卸载 VT-1（冻结栈帧到堆）
  │
  ├── 挂载 VT-2 → 执行代码
  │     │
  │     └── VT-2 正常完成
  │
  └── [VT-1 的 I/O 完成] → 重新挂载 VT-1
```

---

## 19.2 `continuation.cpp / continuationFreezeThaw.cpp`：Continuation 的冻结与解冻

### 19.2.1 Continuation 的概念

虚拟线程的核心是 Continuation——一种可以被暂停（冻结）和恢复（解冻）的执行流。在 HotSpot 中，Continuation 是 JVM 内部的原语：

```cpp
// continuation.hpp
class Continuation {
    stackChunkOop  _tail;        // 栈块链表（最新的一块）
    oop            _scope;       // 作用域对象
    int            _num_frames;  // 冻结的帧数
    int            _num_interpreted_frames;
};
```

### 19.2.2 冻结（Freeze）

当虚拟线程执行阻塞操作时，调用 `Continuation.freeze()`：

```
冻结过程：
1. 从当前栈帧开始，逐帧复制到堆上的 stackChunkOop
2. 对于每个帧：
   a. 解释器帧：复制局部变量、操作数栈、bcp、cpCache 等
   b. 编译器帧：复制所有栈槽和寄存器值（使用 oop_map 定位 oop）
3. 释放载体线程的栈空间
4. 记录返回地址，以便解冻时恢复

关键：冻结不是序列化，而是内存复制
   栈帧从载体线程栈直接复制到堆上的 stackChunkOop
   没有序列化/反序列化开销
```

```cpp
// continuationFreezeThaw.cpp（简化）
int Continuation::freeze(JavaThread* current) {
    // 遍历当前线程栈上的帧
    frame f = current->last_frame();
    while (true) {
        // 复制帧到 stackChunk
        freeze_frame(f, chunk);
        f = f.sender(&map);
        if (is_entry_frame(f)) break;
    }
    // 返回冻结的帧数
    return num_frames;
}
```

### 19.2.3 解冻（Thaw）

当虚拟线程被唤醒时，调用 `Continuation.thaw()`：

```
解冻过程：
1. 从 stackChunkOop 复制帧回载体线程栈
2. 恢复每个帧的 oop 引用
3. 修改返回地址，让执行流跳回到阻塞点之后
4. 载体线程继续执行虚拟线程的代码
```

### 19.2.4 部分冻结与解冻

虚拟线程的栈可以按需增长——不一次冻结/解冻所有帧，而是按栈块（stack chunk）分片：

```
虚拟线程栈的堆表示：
stackChunkOop-3 (最新的帧)
  │ _parent
  ▼
stackChunkOop-2
  │ _parent
  ▼
stackChunkOop-1 (最老的帧)
```

每个 stackChunk 的大小固定（默认 32KB），栈增长时分配新的 chunk，栈缩小时释放。

---

## 19.3 `continuationEntry / continuationWrapper`：Continuation 栈帧

### 19.3.1 ContinuationEntry

Continuation 在载体线程栈上有一个特殊的入口帧：

```cpp
// continuationEntry.hpp
class ContinuationEntry {
    oop  _continuation;          // Continuation 对象
    oop  _scope;                 // 作用域
    int  _num_frames;            // 冻结前的帧数
    address _return_pc;          // 冻结点的返回地址
};
```

`ContinuationEntry` 是冻结/解冻的锚点——冻结时从该帧开始复制，解冻时恢复到该帧。

### 19.3.2 ContinuationWrapper

`ContinuationWrapper` 是 Continuation 在 HotSpot 内部的 C++ 包装：

```cpp
// continuation.hpp
class ContinuationWrapper {
    oop  _continuation;         // Java Continuation 对象
    stackChunkOop _tail;        // 最新栈块
};
```

---

## 19.4 `stackChunkOop`：栈 chunks 的堆存储

### 19.4.1 stackChunkOop 的结构

`stackChunkOop` 是存储在 Java 堆上的栈帧块：

```cpp
// stackChunkOop.hpp
class StackChunkOopDesc : public InstanceOopDesc {
    int       _size;             // chunk 大小
    int       _sp;               // 栈指针偏移
    int       _pc_offset;        // 程序计数器偏移
    int       _num_frames;       // 帧数
    int       _max_size;         // 最大允许大小
    oop       _parent;           // 指向父 chunk
    uint8_t   _gc_mode;          // GC 模式标记
};
```

### 19.4.2 GC 对 stackChunkOop 的影响

stackChunkOop 是 Java 堆上的普通对象，受 GC 管理：

```
GC 扫描 stackChunkOop：
1. 遍历 chunk 中的每个帧
2. 使用 oop_map 定位帧中的 oop 引用
3. 标记这些引用指向的对象

ZGC/Shenandoah 的读屏障：
  当解冻栈帧时，读屏障确保 oop 引用指向正确的对象副本
```

这是虚拟线程实现中最复杂的部分——GC 可能移动 stackChunkOop 中的对象，而解冻时必须正确处理这些引用。

---

## 19.5 `lockStack / mountUnmountDisabler`：虚拟线程的挂载与锁

### 19.5.1 虚拟线程与 synchronized

虚拟线程在 `synchronized` 块内阻塞时，会**钉住（pin）**载体线程——不卸载，而是直接阻塞载体线程：

```
原因：
  synchronized 持有的锁记录在载体线程栈上
  如果卸载虚拟线程，锁记录丢失，无法正确释放锁

JDK 21 的行为：
  synchronized 块内的阻塞 → pin 载体线程
  ReentrantLock 的 await → 正常卸载

最佳实践：
  虚拟线程中使用 ReentrantLock 替代 synchronized
```

### 19.5.2 固定（Pinning）的场景

| 操作 | 是否 Pin | 替代方案 |
|------|---------|---------|
| `synchronized` 块内阻塞 | 是 | `ReentrantLock` |
| `Object.wait()` | 是 | `Condition.await()` |
| `synchronized` 方法 | 是 | `ReentrantLock` |
| Native 方法 | 是 | 避免 |
| `Thread.sleep()` | 否 | 正常卸载 |
| NIO 阻塞 I/O | 否 | 正常卸载 |

### 19.5.3 MountUnmountDisabler

JDK 27 引入 `MountUnmountDisabler`，在特定区域禁止挂载/卸载操作：

```cpp
// 虚拟线程执行某些操作时（如 GC、Deopt）需要禁止卸载
class MountUnmountDisabler {
    // 引用计数，非零时禁止卸载
    int _count;
};
```

---

## 19.6 `jdk.internal.vm.Continuation`：JDK 内部 API

### 19.6.1 Continuation 的内部接口

```java
// jdk.internal.vm.Continuation（简化）
class Continuation {
    // 进入 Continuation
    static void enter(Continuation cont, ContinuationScope scope);

    // 让出 Continuation（冻结当前执行流）
    static void yield(ContinuationScope scope);

    // 恢复 Continuation（解冻并继续执行）
    static void run(Continuation cont);
}
```

### 19.6.2 VirtualThread 使用 Continuation

```java
// VirtualThread.java（简化）
class VirtualThread extends Thread {
    private final Continuation cont;

    VirtualThread(Runnable task) {
        this.cont = new Continuation(VTHREAD_SCOPE, () -> {
            task.run();
        });
    }

    void run() {
        // 挂载到载体线程，执行 Continuation
        cont.run();
    }

    // 阻塞时自动 yield
    static void park() {
        Continuation.yield(VTHREAD_SCOPE);
    }
}
```

---

## 19.7 [AI 时代思考] 百万级虚拟线程与 LLM Agent 并发模型

### 19.7.1 LLM Agent 的并发特征

LLM Agent 系统有独特的并发模式：

```
1. 大量并发 Agent（数千到数万）
2. 每个 Agent 有独立的对话上下文
3. Agent 之间的交互是 I/O 密集的（API 调用、数据库查询）
4. Agent 等待 LLM 推理结果时阻塞

传统线程模型：
  10,000 个 Agent × 1MB/线程 = 10GB 内存（仅栈）
  不可行

虚拟线程模型：
  10,000 个 Agent × ~1KB/虚拟线程 = 10MB 内存
  完全可行
```

### 19.7.2 结构化并发

JDK 21+ 的结构化并发（Structured Concurrency）与虚拟线程配合：

```java
// 结构化并发处理多个 LLM Agent
try (var scope = new StructuredTaskScope.ShutdownOnFailure()) {
    List<Subtask<String>> tasks = agents.stream()
        .map(agent -> scope.fork(() -> agent.run()))
        .toList();

    scope.join();
    scope.throwIfFailed();

    List<String> results = tasks.stream()
        .map(Subtask::get)
        .toList();
}
```

### 19.7.3 虚拟线程在推理服务中的注意事项

```
1. 避免 synchronized → 使用 ReentrantLock
2. 避免在虚拟线程中执行 CPU 密集型计算 → 使用平台线程池
3. 推理请求用虚拟线程，推理计算用平台线程
4. 载体线程池大小 = CPU 核数（ForkJoinPool 默认）
5. 监控 Pin 事件：-Djdk.tracePinnedThreads=short
```

---

## 小结

本章深入了虚拟线程的实现：

1. **虚拟线程**是 JVM 层面的协程，栈按需增长，可轻松创建百万级
2. **冻结/解冻**是 Continuation 的核心——将栈帧复制到堆上的 stackChunkOop
3. **stackChunkOop** 是 GC 管理的堆对象，GC 扫描需要遍历其中的 oop 引用
4. **Pinning** 是虚拟线程的陷阱——`synchronized` 块内阻塞会钉住载体线程
5. **结构化并发**为虚拟线程提供了清晰的生命周期管理
6. **LLM Agent 场景**下，虚拟线程是构建高并发 Agent 调度框架的理想选择

第五篇到此完成。我们已理解了 JVM 并发与同步的全貌：线程模型、锁、安全点、内存屏障、虚拟线程。第六篇将深入 JDK 核心类库。
