# 第 18 章 安全点与内存屏障

> 源码路径：`src/hotspot/share/runtime/safepoint.cpp`、`src/hotspot/share/runtime/safepointMechanism.cpp`、`src/hotspot/share/runtime/orderAccess.cpp`、`src/hotspot/share/runtime/handshake.cpp`

安全点是 JVM 实现 Stop-The-World（STW）暂停的机制——GC、逆优化、类重定义等操作都需要在安全点执行。内存屏障是 Java 内存模型（JMM）的硬件映射，确保多线程程序在弱内存模型上的正确性。本章深入这两个底层机制。

---

## 18.1 `safepoint.cpp`：安全点机制与 STW

### 18.1.1 安全点的概念

安全点是线程执行中的一个位置，在该位置线程的栈和对象引用状态是已知的、稳定的。JVM 在安全点可以安全地执行：

- GC（垃圾收集）
- 逆优化（Deoptimization）
- 类重定义（HotSwap）
- 线程栈遍历
- 偏向锁撤销

### 18.1.2 安全点的发起

```cpp
// safepoint.cpp
void SafepointSynchronize::begin() {
    // 1. 设置全局安全点状态
    _state = _synchronizing;

    // 2. 通知所有线程进入安全点
    SafepointMechanism::arm_all_pollers();

    // 3. 等待所有线程到达安全点
    int waiting_to_block = Threads::number_of_threads();
    while (waiting_to_block > 0) {
        // 等待线程自行检查并阻塞
        SpinPause();
        waiting_to_block = count_threads_not_at_safepoint();
    }

    // 4. 所有线程到达，安全点开始
    _state = _synchronized;
}
```

### 18.1.3 安全点的结束

```cpp
// safepoint.cpp
void SafepointSynchronize::end() {
    // 1. 重置全局状态
    _state = _not_synchronized;

    // 2. 解除轮询保护
    SafepointMechanism::disarm_all_pollers();

    // 3. 唤醒所有阻塞的线程
    for (JavaThread* t = Threads::first(); t; t = t->next()) {
        t->mux_release();
    }
}
```

---

## 18.2 `safepointMechanism.cpp`：安全点轮询的实现

### 18.2.1 轮询机制

线程在执行过程中定期检查安全点标志。如果标志被设置，线程自行暂停。检查点放在：

1. **解释器**：每条字节码的 dispatch 之间
2. **JIT 编译代码**：方法返回和循环回边处
3. **JNI 代码**：从 native 返回时

### 18.2.2 内存页保护机制

HotSpot 使用内存页保护实现零开销的安全点轮询：

```cpp
// safepointMechanism.hpp
class SafepointMechanism {
    // 全局轮询页
    static address _polling_page;

    // 每个线程的本地轮询变量
    // 嵌入在 JavaThread 对象中
};
```

**工作原理**：

```
正常状态：
  _polling_page 可读可写
  线程每次轮询只是读取 _polling_page → 不触发异常 → 继续执行
  开销：1 条 load 指令（~1ns）

安全点状态：
  mprotect(_polling_page, PROT_NONE)  → 页不可访问
  线程读取 _polling_page → SIGSEGV → 信号处理器 → 线程阻塞
```

这种设计的关键：**无安全点时，轮询的开销几乎为零**——只是一次普通的内存读取。

### 18.2.3 本地轮询变量

JDK 27 使用每个线程的本地轮询变量，替代全局轮询页：

```cpp
// 嵌入在 JavaThread 中
volatile uintptr_t _polling_word;   // 本地安全点标志

// 编译器生成的轮询代码：
// test [thread + _polling_word_offset], 0
// 如果为 0 → 正常
// 如果非 0 → 需要进入安全点
```

本地轮询变量的优势：可以针对单个线程设置安全点（Handshake），而不需要全局 STW。

---

## 18.3 `orderAccess.cpp`：内存序与 CPU 屏障映射

### 18.3.1 Java 内存模型的操作

JMM 定义了以下内存排序操作：

| JMM 操作 | 含义 | HotSpot 实现（x86） |
|---------|------|-------------------|
| LoadLoad | Load₁ 必须在 Load₂ 之前完成 | 无需屏障（x86 强排序） |
| StoreStore | Store₁ 必须在 Store₂ 之前完成 | `sfence` 或 `mfence` |
| LoadStore | Load 必须在 Store 之前完成 | 无需屏障 |
| StoreLoad | Store 必须在 Load 之前完成 | `mfence` 或 `lock addl $0, $0` |

x86 是强内存模型（TSO），只允许 Store-Load 重排，因此只需要 StoreLoad 屏障。

### 18.3.2 volatile 的屏障映射

```java
// Java 代码
volatile int x;
x = 1;      // volatile 写
int y = x;  // volatile 读
```

```
volatile 写：
  StoreStore 屏障  →  sfence（x86 可省略）
  写 x = 1
  StoreLoad �屏碍  →  mfence / lock addl $0, $0

volatile 读：
  读 y = x
  LoadLoad 屏障   →  无需（x86）
  LoadStore 屏障  →  无需（x86）
```

x86 上 volatile 写的开销主要来自 StoreLoad 屏障（`mfence` 约 30-50ns）。

### 18.3.3 AArch64 的屏障映射

ARM 是弱内存模型，需要更多屏障：

```
AArch64 volatile 写：
  dmb ish       // StoreStore 屏障
  str x1, [x0]  // 写
  dmb ish       // StoreLoad 屏障

AArch64 volatile 读：
  ldr x1, [x0]  // 读
  dmb ish       // LoadLoad + LoadStore 屏障
```

`dmb ish`（Data Memory Barrier, Inner Shareable）确保内共享域内的内存操作顺序。

---

## 18.4 `handshake.cpp`：线程握手——安全点的替代

### 18.4.1 Handshake 的动机

安全点需要 STW——所有线程暂停，对延迟敏感的应用影响很大。Handshake 是安全点的轻量级替代——它可以对单个线程执行操作，而不需要全局暂停。

### 18.4.2 Handshake 的实现

```cpp
// handshake.cpp
class HandshakeOperation {
    ThreadClosure* _thread_cl;
    bool           _executed;
};

void Handshake::execute(HandshakeOperation* op) {
    // 1. 设置目标线程的握手标志
    target->set_handshake_operation(op);

    // 2. 等待目标线程执行操作
    while (!op->_executed) {
        // 如果目标线程在安全点，由 VMThread 代为执行
        if (target->is_at_safepoint()) {
            op->_thread_cl->do_thread(target);
            op->_executed = true;
            break;
        }
        SpinPause();
    }
}
```

### 18.4.3 Handshake 的检查点

线程在以下位置检查握手标志：

```
1. 解释器 dispatch 之间
2. JIT 编译代码的 safepoint poll 处
3. 从 native 返回时
4. VMThread 执行安全点时（如果线程已在安全点）
```

### 18.4.4 Handshake vs Safepoint

| 特性 | Safepoint | Handshake |
|------|-----------|-----------|
| 影响范围 | 全部线程 | 单个线程 |
| 暂停时间 | 所有线程中最慢的 | 仅目标线程 |
| 实现复杂度 | 简单 | 复杂 |
| 适用场景 | GC、Deopt | 栈遍历、偏向锁撤销、线程采样 |

JDK 27 已将大量偏向锁撤销和线程采样从全局安全点迁移到 Handshake，显著降低了 STW 暂停的频率和时长。

---

## 18.5 [体系结构视角] Store Buffer、Load Buffer 与 Java Memory Model 的硬件映射

### 18.5.1 Store Buffer 的影响

现代 CPU 的写操作不直接写入 L1 Cache，而是进入 Store Buffer：

```
无 Store Buffer：
  写 x=1 → 直接写入 L1 Cache → MESI 协议传播

有 Store Buffer：
  写 x=1 → 写入 Store Buffer → 继续执行
  Store Buffer 异步写入 L1 Cache → MESI 协议传播

结果：写操作对其他核不可见，直到 Store Buffer 排空
```

这就是 Store-Load 重排的硬件原因——Store Buffer 中的写还没被其他核看到，后续的 Load 可能读到旧值。

### 18.5.2 x86 TSO 模型

x86 实现了 Total Store Order（TSO）——唯一的重排是 Store-Load：

```
x86 允许的重排：
  Store → Load（Store 在 Buffer 中，Load 先执行）

x86 禁止的重排：
  Load → Load   ✓ 不重排
  Load → Store   ✓ 不重排
  Store → Store  ✓ 不重排（Store Buffer 是 FIFO）
```

### 18.5.3 volatile 与硬件屏障的完整映射

```
Java 层：              HotSpot 层：              x86 指令：
volatile 写           release_store            [正常写入]
                      StoreLoad 屏障           mfence / lock addl $0, $0

volatile 读           acquire_load             [正常读取]

final 字段写           release_store            [正常写入]
（构造器结束）         StoreStore 屏障          sfence（x86 可省略）
```

### 18.5.4 安全点的内存序含义

安全点不仅是线程暂停——它还隐含了内存屏障语义：

```
进入安全点时：
1. 线程必须完成所有挂起的写操作（排空 Store Buffer）
2. 线程的栈帧和对象引用对 GC 完全可见
3. 确保 GC 看到的是一致的堆状态

这是 GC 正确性的基础——如果线程有未完成的写操作，
GC 可能扫描到半初始化的对象。
```

---

## 小结

本章深入了 JVM 的安全点和内存屏障机制：

1. **安全点**通过内存页保护实现零开销轮询，无安全点时开销约 1ns
2. **本地轮询变量**支持单线程的安全点（Handshake），避免全局 STW
3. **内存屏障**在 x86 上主要是 StoreLoad（`mfence`），AArch64 需要更多屏障
4. **Handshake** 是安全点的轻量级替代，已逐步替代偏向锁撤销等场景的全局 STW
5. **Store Buffer** 是硬件层面的重排根源，Java volatile 通过 `mfence` 确保可见性
6. **安全点隐含内存屏障**，确保 GC 看到一致的堆状态

下一章将深入虚拟线程——JVM 的协程实现。
