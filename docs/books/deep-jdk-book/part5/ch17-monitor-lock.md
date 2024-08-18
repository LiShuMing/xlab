# 第 17 章 同步原语：Monitor 与锁

> 源码路径：`src/hotspot/share/oops/markWord.hpp`、`src/hotspot/share/runtime/basicLock.hpp`、`src/hotspot/share/runtime/objectMonitor.cpp`、`src/hotspot/share/runtime/synchronizer.cpp`

Java 的 `synchronized` 关键字在 HotSpot 中经历了一条精巧的优化路径：从无锁到偏向锁、轻量级锁、重量级锁的逐级膨胀。本章从对象头中的 `markWord` 出发，追踪锁的完整生命周期。

---

## 17.1 `markWord`：对象头与锁状态

### 17.1.1 markWord 的锁状态编码

64 位 `markWord` 的低 3 位编码锁状态：

```
markWord 低 3 位：
┌─────┬─────┬──────┐
│  2  │  1  │  0   │
│fwd  │lock │lock  │
│bit  │ 1   │ 0    │
└─────┴─────┴──────┘

锁状态：
  01 (lock=01, fwd=0) → 无锁（unlocked）
  01 (lock=01, fwd=1) → 偏向锁（biased）
  00                  → 轻量级锁（thin locked）
  10                  → 重量级锁（fat locked / inflated）
  11                  → 标记状态（GC 使用）
```

### 17.1.2 各锁状态下 markWord 的布局

```
无锁（unlocked）：
┌─────────────────────────────┬──────┬──────┬──────┐
│ unused:22   hash:31         │ gap  │ age  │  0   │ 01
└─────────────────────────────┴──────┴──────┴──────┘

偏向锁（biased）：
┌─────────────────────────────┬──────┬──────┬──────┐
│ thread:54   epoch:2         │ gap  │ age  │  1   │ 01
└─────────────────────────────┴──────┴──────┴──────┘
  thread: 持有偏向锁的线程 ID
  epoch:  偏向锁批量重偏向的时间戳

轻量级锁（thin locked）：
┌───────────────────────────────────────────────┬──────┐
│ lock_record_ptr:62                             │  00  │
└───────────────────────────────────────────────┴──────┘
  lock_record_ptr: 指向栈上 LockRecord 的指针

重量级锁（fat locked）：
┌───────────────────────────────────────────────┬──────┐
│ monitor_ptr:62                                 │  10  │
└───────────────────────────────────────────────┴──────┘
  monitor_ptr: 指向 ObjectMonitor 的指针
```

### 17.1.3 偏向锁的争议与演进

偏向锁（Biased Locking）在 JDK 15 中被默认禁用，JDK 18 中被废弃：

```
偏向锁的问题：
1. 撤销开销大：当锁对象被其他线程访问时，需要撤销偏向
   撤销需要 safepoint → 全线程暂停
2. 现代应用锁竞争模式变化：无竞争场景减少
3. 与 VirtualThread 冲突：虚拟线程频繁挂载/卸载导致大量偏向锁撤销

替代方案：
  轻量级锁在无竞争场景下的开销已足够低
  -XX:-UseBiasedLocking  # JDK 15+ 默认
```

---

## 17.2 `basicLock / lockStack`：锁记录与栈上锁

### 17.2.1 LockRecord

轻量级锁使用栈上的 `LockRecord` 存储 lock 信息：

```cpp
// basicLock.hpp
class BasicLock {
    markWord _displaced_header;  // 保存的无锁 markWord
};

// 解释器栈帧中的 LockRecord：
struct LockRecord {
    BasicLock   _lock;           // 锁数据
    oop         _obj;            // 锁对象
    LockRecord* _next;           // 链表（可重入）
};
```

### 17.2.2 轻量级锁的加锁过程

```
1. 在当前栈帧分配 LockRecord
2. 将对象的无锁 markWord 保存到 LockRecord._displaced_header
3. CAS 将 markWord 替换为指向 LockRecord 的指针
4. 成功 → 获得轻量级锁
5. 失败 → 检查是否为自己持有（重入）或竞争（膨胀）
```

```cpp
// synchronizer.cpp（简化）
void ObjectSynchronizer::enter(Handle obj, BasicLock* lock, TRAPS) {
    markWord mark = obj->mark();
    // 快速路径：CAS 替换 markWord
    if (mark.is_unlocked()) {
        markWord locked = mark.set_lock_record(lock);
        if (obj->cas_set_mark(locked, mark) == mark) {
            return;  // 成功获得轻量级锁
        }
    }
    // 慢速路径
    inflate(THREAD, obj(), inflate_cause_monitor_enter)->enter(THREAD);
}
```

### 17.2.3 LockStack（JDK 27 新特性）

JDK 27 引入 `LockStack` 优化轻量级锁——将锁记录直接存储在 JavaThread 对象中，而非栈帧中：

```cpp
// lockStack.hpp
class LockStack {
    // 内联数组：存储当前线程持有的轻量级锁
    static const int CAPACITY = 8;
    oop _base[CAPACITY];
};
```

LockStack 的优势：
1. 不需要在每个栈帧中分配 LockRecord
2. 锁重入检查更快（直接查询 LockStack）
3. 减少了栈帧的内存占用

---

## 17.3 `objectMonitor.cpp`：重量级 Monitor 实现

### 17.3.1 ObjectMonitor 的结构

当轻量级锁竞争激烈时，膨胀为重量级锁，创建 `ObjectMonitor`：

```cpp
// objectMonitor.hpp
class ObjectMonitor {
    oop          _object;         // 关联的锁对象
    markWord     _header;         // 保存的原始 markWord

    // 等待队列（双向链表）
    ObjectWaiter* _EntryList;     // 阻塞等待锁的线程
    ObjectWaiter* _WaitSet;       // 执行 wait() 的线程

    // 持有者
    void*        _owner;          // 持有锁的线程（JavaThread* 或 LockRecord*）
    int          _recursions;     // 重入次数
    int          _count;          // 等待计数

    // 公平性
    bool         _is_busy;        // 监视器是否正在使用
};
```

### 17.3.2 Monitor 的 Enter/Exit

```
enter() 过程：
1. 尝试 CAS 设置 _owner 为当前线程
2. 成功 → 获得锁
3. 失败 → 自旋等待（spin）
4. 自旋失败 → 进入 _EntryList 阻塞（park）
5. 持有者 exit() → 唤醒 _EntryList 中的线程

exit() 过程：
1. 检查重入计数，非零则递减返回
2. 检查 _EntryList 是否有等待者
3. 有 → 唤醒一个等待者（策略：cxdq 默认值决定公平性）
4. 无 → 释放锁
```

### 17.3.3 wait/notify 的实现

```cpp
// objectMonitor.cpp
void ObjectMonitor::wait(jlong millis, bool interruptible, TRAPS) {
    // 1. 创建 ObjectWaiter 节点
    ObjectWaiter node(THREAD);
    node._notifier = nullptr;

    // 2. 加入 _WaitSet
    AddWaiter(&node);

    // 3. 释放锁（exit）
    exit(true, THREAD);

    // 4. 阻塞当前线程（park）
    Self->_Stalled = 0;
    ParkEvent * const ev = Self->_ParkEvent;
    ev->park(millis);

    // 5. 被唤醒后重新竞争锁
    reenter(IEntry, THREAD);
}

void ObjectMonitor::notify(TRAPS) {
    // 从 _WaitSet 中取一个线程
    ObjectWaiter* waiter = DequeueWaiter();
    if (waiter != nullptr) {
        // 将其移入 _EntryList 或直接 unpark
        EnterI(waiter);
    }
}
```

---

## 17.4 `synchronizer.cpp`：`synchronized` 的字节码到 Monitor 的映射

### 17.4.1 字节码层面的同步

```java
synchronized (obj) {
    // 临界区
}
```

编译为字节码：

```
monitorenter     // 进入同步块
// 临界区字节码
monitorexit      // 退出同步块（正常路径）
// 异常处理路径
monitorexit      // 退出同步块（异常路径）
```

### 17.4.2 `synchronized` 方法的实现

`synchronized` 方法不使用 `monitorenter/monitorexit` 字节码，而是在方法标志位中设置 `ACC_SYNCHRONIZED`：

```cpp
// 方法入口代码检查 ACC_SYNCHRONIZED
if (method->is_synchronized()) {
    // 进入监视器
    if (method->is_static()) {
        ObjectSynchronizer::enter(Handle(method->klass()->java_mirror()), ...);
    } else {
        ObjectSynchronizer::enter(Handle(receiver), ...);
    }
}
```

### 17.4.3 锁膨胀的完整流程

```
对象创建 → 无锁（markWord = hash + age + 01）

线程 A 第一次 synchronized(obj)：
  → 偏向锁（如果启用）或轻量级锁

线程 B 也 synchronized(obj)：
  → 撤销偏向锁 / CAS 竞争轻量级锁
  → 如果竞争失败 → 膨胀为重量级锁

重量级锁：
  → 创建 ObjectMonitor
  → markWord 指向 ObjectMonitor
  → 后续所有线程通过 ObjectMonitor 竞争

锁降级：
  → 重量级锁不降级（膨胀是单向的）
  → 只有在 GC 的 deflate_idle_monitors 阶段回收
```

---

## 17.5 [体系结构视角] CAS 指令、LL/SC 与锁的硬件成本模型

### 17.5.1 CAS 的硬件实现

x86 使用 `lock cmpxchg` 指令实现 CAS：

```asm
; CAS(addr, expected, new_value)
lock cmpxchg [rdi], rax    ; 原子比较并交换
```

`lock` 前缀锁定缓存行，确保多核一致性。硬件成本：

```
无竞争 CAS：~10-20 个时钟周期
有竞争 CAS：~50-200 个时钟周期（缓存行在核间传递）
```

### 17.5.2 LL/SC（ARM/RISC-V）

ARM 和 RISC-V 使用 LL/SC（Load-Linked/Store-Conditional）对实现 CAS：

```
ARM:
  ldaxr x0, [addr]        // 独占加载
  cmp   x0, expected
  b.ne  fail
  stlxr w1, new_val, [addr] // 独占存储
  cbnz  w1, retry          // 如果被干扰，重试
```

LL/SC 的优势是不会锁定缓存行，但在高竞争下容易失败重试（ABA 问题）。

### 17.5.3 各级锁的硬件成本

| 锁类型 | 加锁成本 | 解锁成本 | 适用场景 |
|--------|---------|---------|---------|
| 偏向锁 | ~0（无 CAS） | ~1000+（撤销需 safepoint） | 单线程反复加锁 |
| 轻量级锁 | ~10ns（CAS） | ~10ns（CAS） | 低竞争，短持有 |
| 重量级锁 | ~500ns（park/unpark） | ~200ns（unpark） | 高竞争，长持有 |
| 自旋锁 | ~10ns/次 | ~10ns | 极短持有，低竞争 |

### 17.5.4 自旋等待的硬件行为

HotSpot 在膨胀为重量级锁之前执行自适应自旋（adaptive spinning）：

```cpp
// objectMonitor.cpp
// 自旋次数根据历史成功率动态调整
if (DoSpin) {
    for (int i = 0; i < spin_count; i++) {
        if (TryLock()) return;  // 自旋中尝试获取
        Pause();                // CPU pause 指令，减少功耗
    }
}
```

x86 的 `pause` 指令（约 140 个时钟周期）减少自旋时的功耗和流水线压力。

---

## 小结

本章深入了 JVM 的同步原语：

1. **markWord** 的低 3 位编码锁状态，不同状态存储不同的元数据
2. **偏向锁**在 JDK 15+ 被默认禁用，撤销开销是其致命缺陷
3. **轻量级锁**使用 CAS + LockRecord 实现无竞争场景的高效同步
4. **重量级锁**使用 ObjectMonitor 管理等待队列，park/unpark 实现线程阻塞
5. **锁膨胀**是单向的，只有 GC 的 deflate 阶段回收
6. **CAS 的硬件成本**从 ~10ns（无竞争）到 ~200ns（有竞争），决定了锁的选择策略

下一章将深入安全点与内存屏障——JVM 并发的底层机制。
