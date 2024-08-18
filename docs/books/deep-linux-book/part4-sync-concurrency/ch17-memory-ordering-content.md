# 第17章 内存序与屏障

> 源码锚点：`arch/x86/include/asm/barrier.h`、`include/asm-generic/barrier.h`、`include/linux/compiler.h`、`kernel/locking/lockdep.c`

并发正确性不仅需要锁——还需要内存序(Memory Ordering)。编译器和CPU都会重排内存操作，导致多线程程序看到不一致的内存状态。内存屏障是程序员的显式约束，告诉编译器和CPU哪些操作不能重排。

## 17.1 内存序的硬件根源

### 编译器重排

编译器为了优化性能，可能重排内存操作——只要单线程语义不变：

```c
// 源代码
data = 1;
flag = true;

// 编译器可能重排为
flag = true;
data = 1;    // flag设为true时data可能还是0！
```

在单线程中两种顺序等价，但在多线程中，另一个线程可能看到`flag==true`但`data==0`。

### CPU重排：Store Buffer与Invalidate Queue

现代CPU使用Store Buffer和Invalidate Queue提高性能，但导致了内存可见性的延迟：

**Store Buffer**：CPU写入数据时，数据先进入Store Buffer（比L1 Cache快得多），稍后才写入Cache。这意味着CPU自己能立即看到写入，但其他CPU可能延迟看到。

**Invalidate Queue**：CPU收到Cache行失效请求时，先放入Invalidate Queue（确认收到但不立即处理），稍后才真正失效Cache行。这意味着CPU可能继续读取过时的Cache行。

### x86的TSO模型

x86实现TSO(Total Store Order)——只允许StoreLoad重排：

```
允许的重排：Store → Load (写后读可重排为读后写)
禁止的重排：Load → Store, Load → Load, Store → Store
```

StoreLoad重排的根源就是Store Buffer——CPU在Store还在Buffer中时执行了后续的Load。

### ARM/RISC-V的弱序模型

ARM和RISC-V使用弱序(Weakly Ordered)内存模型——允许所有四种重排。这意味着在ARM上正确的代码需要比x86更多的内存屏障。Linux内核代码必须在最弱的架构上正确——因此内核使用保守的屏障抽象。

## 17.2 内存屏障

### x86屏障指令

| 指令 | 语义 | 映射 |
|------|------|------|
| mfence | 全屏障(Store+Load) | `smp_mb()` |
| sfence | 写屏障(Store) | `smp_wmb()` |
| lfence | 读屏障(Load) | `smp_rmb()` |
| LOCK前缀 | 全屏障 | 原子操作自带 |

x86上`mfence`是最强的屏障——确保之前的所有内存操作在之后的所有内存操作之前完成。`LOCK`前缀指令（如`lock cmpxchg`）也提供全屏障语义。

### Linux内核的屏障抽象

```c
// include/asm-generic/barrier.h
smp_mb()     // 全屏障：所有之前的读写操作在所有之后的读写操作之前完成
smp_wmb()    // 写屏障：所有之前的写在所有之后的写之前完成
smp_rmb()    // 读屏障：所有之前的读在所有之后的读之前完成
```

x86上的映射：
- `smp_mb()` → `asm volatile("mfence":::"memory")` （或`lock addl $0, ...`）
- `smp_wmb()` → 空操作（x86的TSO保证Store-Store不重排）
- `smp_rmb()` → 空操作（x86的TSO保证Load-Load不重排）

ARM上的映射：
- `smp_mb()` → `dmb ish`
- `smp_wmb()` → `dmb ishst`
- `smp_rmb()` → `dmb ishld`

### smp_store_release()/smp_load_acquire()

消息传递(Message Passing)是最常见的同步模式：

```c
// 生产者
data = 42;                          // 写入数据
smp_store_release(&flag, 1);        // 发布标志

// 消费者
if (smp_load_acquire(&flag) == 1)   // 获取标志
    use(data);                       // 读取数据——保证看到42
```

`release`语义：确保之前的所有写操作在release之前完成（写屏障）
`acquire`语义：确保之后的所有读操作在acquire之后开始（读屏障）

acquire/release比`mb()`轻量——在x86上，`smp_store_release()`就是普通的`WRITE_ONCE()`+编译器屏障，`smp_load_acquire()`就是普通的`READ_ONCE()`+编译器屏障，因为x86的TSO已经提供了足够的保证。

### READ_ONCE()/WRITE_ONCE()

```c
// include/linux/compiler.h
// READ_ONCE：防止编译器将读操作优化掉、重排或合并
#define READ_ONCE(x) (*(volatile typeof(x) *)&(x))

// WRITE_ONCE：防止编译器将写操作优化掉、重排或合并
#define WRITE_ONCE(x, val) (*(volatile typeof(x) *)&(x) = (val))
```

`READ_ONCE`/`WRITE_ONCE`不提供CPU级别的内存屏障——它们只防止编译器优化。它们是并发编程的最小保障——确保每次访问都真正从内存读取/写入，而非使用缓存的寄存器值。

典型使用：内核中轮询某个标志变量时，必须用`READ_ONCE`——否则编译器可能将循环优化为只读一次。

## 17.3 lockdep：死锁检测

### 锁依赖图的构建

lockdep在运行时构建锁的依赖图，检测潜在的死锁：

```c
// kernel/locking/lockdep.c
// 每次获取锁时，lockdep记录：
// 1. 锁类(lock_class)——同一把锁的不同实例归为同一类
// 2. 获取顺序——A→B表示先获取A再获取B
// 3. 中断上下文——是否在中断中获取
```

lockdep的核心数据结构是**锁依赖图**——节点是锁类，边表示获取顺序。如果图中出现环，就存在死锁风险。

### 死锁模式检测

**AA死锁**：同一把锁被递归获取（自旋锁和mutex不可递归）。

**ABBA死锁**：
```
线程1: lock(A) → lock(B)
线程2: lock(B) → lock(A)
→ 死锁！lockdep在发现A→B和B→A时报告
```

**IRQ死锁**：
```
进程上下文: lock(A)
中断: lock(A)  → 死锁！中断抢占进程后尝试获取同一把锁
→ lockdep在发现中断上下文获取进程上下文持有的锁时报告
```

### lockdep的局限性

lockdep只能检测**执行过的路径**——如果某个锁顺序从未在运行中被触发，lockdep无法检测。这意味着：
- 测试覆盖率决定检测覆盖率
- 罕见路径的死锁可能漏检
- lockdep有性能开销，生产环境通常关闭

### 锁类与统计

lockdep将同一把锁的不同实例归为同一"锁类"(lock_class)——例如所有`inode->i_lock`属于同一个锁类。这使得lockdep能从有限的执行中推断出通用的死锁模式。

`/proc/lockdep_stats`显示lockdep的统计信息，`/proc/lockdep_chains`显示已观察到的锁链。

## 17.4 其他检测工具

### KCSAN：并发SANitizer

`kernel/kcsan/`检测数据竞争(data race)——两个线程同时访问同一内存，至少一个是写操作，且无同步保护：

```c
// KCSAN的检测策略：
// 1. 在每次内存访问前插入观测点
// 2. 延迟观测点的执行（引入随机延迟）
// 3. 在延迟期间检查是否有其他CPU修改了同一地址
// 4. 如果修改了→报告数据竞争
```

KCSAN与KASAN互补：KASAN检测越界/UAF，KCSAN检测并发竞争。

### 锁压力测试

`kernel/locking/locktorture.c`对各种锁实现进行压力测试——长时间高并发获取/释放，验证锁的正确性和公平性。`kernel/locking/test-ww_mutex.c`专门测试ww_mutex的死锁避免逻辑。

> **数据库视角**：内存序对无锁数据结构正确性的影响。数据库引擎中使用无锁数据结构(如lock-free hash table)时，内存序是最常见的bug来源。一个经典的错误：发布数据后发布指针，但没有在两者之间插入`smp_store_release()`——ARM/RISC-V上其他线程可能看到指针更新但数据尚未写入。内核的`rcu_assign_pointer()`/`rcu_dereference()`就是正确的消息传递模式——数据库的无锁数据结构应遵循相同的acquire/release语义。

---

本章建立了对内存序的完整认知：编译器和CPU的重排是并发bug的硬件根源，内存屏障是程序员的显式约束，acquire/release是消息传递的标准模式，lockdep在运行时检测死锁，KCSAN检测数据竞争。内存序是并发正确性的基础设施——没有正确的内存序，所有锁和RCU的保证都是空中楼阁。第四篇到此结束，从自旋锁/互斥锁到RCU、futex、内存序，构成了对内核同步机制的完整认知。
