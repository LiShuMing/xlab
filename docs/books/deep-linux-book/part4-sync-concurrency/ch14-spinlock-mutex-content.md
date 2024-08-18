# 第14章 自旋锁与互斥锁

> 源码锚点：`kernel/locking/qspinlock.c`、`kernel/locking/mutex.c`、`kernel/locking/rtmutex.c`、`kernel/locking/rwsem.c`、`kernel/locking/osq_lock.c`、`kernel/locking/percpu-rwsem.c`

多核系统中最基本的同步问题：如何保护共享数据不被并发破坏。自旋锁和互斥锁是内核最核心的两种锁机制——前者在中断上下文忙等，后者在进程上下文可睡眠。本章深入它们的实现，理解Linux如何在可扩展性和公平性之间权衡。

## 14.1 自旋锁：从Ticket Lock到qspinlock

### 自旋锁的语义

自旋锁(spinlock)在无法获取锁时忙等(spin)——不断循环检查锁状态。关键约束：
- **不可睡眠**：持锁期间不能调用可能睡眠的函数（如kmalloc(GFP_KERNEL)、schedule）
- **短持锁时间**：适合保护临界区极短的操作（如修改链表头、更新计数器）
- **中断安全**：中断处理程序中使用自旋锁时必须先禁用本地中断

### MCS锁：消除总线风暴

传统的Test-And-Set自旋锁有一个严重问题——所有等待者在同一个变量上自旋，每次锁释放导致所有CPU的Cache行失效，产生**总线风暴**(bus spin)。MCS锁解决了这个问题：

```c
// kernel/locking/mcs_spinlock.h
struct mcs_spinlock {
    struct mcs_spinlock *next;   // 下一个等待者
    int locked;                  // 1=需要等待, 0=获得锁
};
```

MCS锁的关键：每个CPU在自己的`mcs_spinlock`节点上自旋——这是一个局部变量，位于自己的Cache行中，不会因其他CPU获得锁而失效。释放锁时，持锁者将后继者的`locked`设为0——只有后继者的Cache行被失效，而非所有等待者。

### qspinlock：四级队列

qspinlock(Queued Spinlock)是Linux当前的默认自旋锁实现，基于MCS思想但更加紧凑：

```c
// kernel/locking/qspinlock.c
// qspinlock的32位原子变量布局：
// [31:28] 3位: 锁的尾部编码
// [27:0]  28位: 尾部CPU索引
// 当锁空闲时，值为0
// 当锁被持有时，最低位为1
// 当有等待者时，高位编码等待队列的尾部
```

qspinlock的四状态设计：

1. **locked, no waiters**：锁被持有，无等待者。一个原子`cmpxchg`即可获取。
2. **locked, one pending**：锁被持有，一个CPU在乐观自旋(紧挨着锁的下一个候选)。它直接在锁变量上自旋。
3. **locked, one pending + queued**：超过一个等待者时，通过MCS节点链表排队。
4. **unlocked**：锁空闲，第一个等待者获取。

qspinlock的精巧之处：无等待者时只需一个原子操作；有少量等待者时乐观自旋减少延迟；大量等待者时MCS排队保证公平性。

### PV优化：虚拟化场景

在虚拟化环境中，虚拟CPU可能被宿主机调度出去——此时自旋锁的自旋完全浪费CPU时间。`qspinlock_paravirt.h`实现了PV优化：当自旋超过阈值时，虚拟CPU主动让出(yield)，而非持续自旋。

## 14.2 mutex：乐观自旋的互斥锁

mutex在语义上与自旋锁互补——无法获取锁时进程睡眠，而非自旋。但mutex引入了**乐观自旋**(optimistic spinning)——如果持锁者正在运行，等待者先自旋一小段时间再睡眠。

```c
// kernel/locking/mutex.c
struct mutex {
    atomic_long_t owner;        // 持锁者task_struct指针(低位编码状态)
    struct list_head wait_list; // 睡眠等待者链表
    ...
};
```

### mutex的三态

```
unlocked:           owner = 0
locked, no waiters: owner = task_struct*（低位0）
locked, waiters:    owner = task_struct*（低位1=MUTEX_FLAG_WAITERS）
```

`MUTEX_FLAG_WAITERS`标记有睡眠等待者——释放锁时需要唤醒第一个等待者。

### 乐观自旋

```c
// kernel/locking/mutex.c (简化)
__mutex_lock_common(mutex, state, subclass, ...)
{
    // 1. 快速路径：原子cmpxchg获取锁
    if (atomic_long_try_cmpxchg_acquire(&lock->owner, &zero, current))
        return;

    // 2. 乐观自旋：持锁者正在运行，自旋等待
    if (mutex_optimistic_spin(lock, ...))
        return;  // 自旋期间获得了锁

    // 3. 慢速路径：加入等待队列，睡眠
    osq_lock(&lock->osq);     // 在乐观自旋队列中排队
    for (;;) {
        set_current_state(TASK_UNINTERRUPTIBLE);
        if (__mutex_trylock(lock))  // 偶尔尝试获取
            break;
        schedule();                   // 睡眠等待
    }
}
```

乐观自旋的判断：`mutex_optimistic_spin()`检查持锁者是否在当前CPU或近邻CPU上运行——如果是，说明持锁者即将释放锁，自旋比睡眠+唤醒更快。持锁者的CPU信息通过`task_struct->on_cpu`获取。

### osq_lock：乐观自旋队列

`kernel/locking/osq_lock.c`实现乐观自旋的排队——避免多个等待者同时自旋造成的Cache行争用：

```c
// kernel/locking/osq_lock.c
struct optimistic_spin_queue {
    atomic_t tail;    // 队列尾部的CPU编号
};
struct optimistic_spin_node {
    struct optimistic_spin_node *next, *prev;
    int locked;       // 1=需要等待, 0=轮到自己
    int cpu;          // CPU编号
};
```

osq_lock是MCS锁的变体——每个CPU在自己的节点上自旋，prev释放时将next的locked设为0。

### ww_mutex：避免死锁的迭代模式

ww_mutex(wait-wound mutex)解决了多个锁的获取顺序问题——当多个事务需要获取相同的多个mutex时，可能产生ABBA死锁。ww_mutex使用"wound"（伤害）策略：低优先级事务如果获取锁时发现高优先级事务已经在等待，主动释放已持有的锁（被"伤害"），让高优先级事务继续。

## 14.3 rtmutex：优先级继承互斥锁

优先级反转(Priority Inversion)是实时系统的经典问题：低优先级任务持有锁，高优先级任务等待锁，中优先级任务抢占低优先级任务——高优先级任务被间接地降低了优先级。

rtmutex通过**优先级继承**(Priority Inheritance, PI)解决：当高优先级任务等待rtmutex时，持锁的低优先级任务临时继承高优先级，尽快执行完临界区并释放锁。

```c
// kernel/locking/rtmutex.c
struct rt_mutex_base {
    raw_spinlock_t  wait_lock;       // 保护内部数据
    struct rb_root_cached waiters;   // 红黑树：按优先级排序的等待者
    struct task_struct *owner;        // 持锁者
};
```

等待者用红黑树组织——按优先级排序，最高优先级的等待者在树的最左节点，可以O(1)找到。当锁释放时，最高优先级的等待者被唤醒。

优先级继承的传播：如果A等待B持有的锁，B继承A的优先级；如果B又在等待C持有的锁，C也继承A的优先级——继承沿等待链传播。

rtmutex是PREEMPT_RT内核的基础——在RT内核中，普通mutex底层使用rtmutex，所有锁操作都可抢占。

## 14.4 读写信号量

rwsem(Read-Write Semaphore)允许读者并发、写者独占：

```c
// kernel/locking/rwsem.c
struct rw_semaphore {
    atomic_long_t count;       // 读者计数+写者标志
    struct list_head wait_list;// 等待者链表
    wait_queue_head_t wait;    // 等待队列
    ...
};
```

rwsem的count字段编码了读者数量和写者状态。当有活跃读者时，写者必须等待所有读者退出；当有活跃写者时，读者和写者都必须等待。

**读者偏爱 vs 写者偏爱**：Linux的rwsem默认偏爱写者——当写者等待时，新的读者不能获取锁，避免写者饥饿。这对于数据库等写者敏感的场景更合适。

### percpu-rwsem：读路径零开销

```c
// kernel/locking/percpu-rwsem.c
struct percpu_rw_semaphore {
    struct rw_semaphore rw_sem;       // 写路径使用的普通rwsem
    struct percpu_ref readers;        // per-CPU读者计数
    ...
};
```

percpu-rwsem的关键优化：读路径只需递增本地CPU的per-CPU计数器——无原子操作、无Cache行争用。写路径需要等待所有CPU的读者计数归零——代价较高，但写者通常很少。

percpu-rwsem适用于读极多写极少的场景——如`cgroup_threadgroup_rwsem`（保护进程的cgroup关系，读多写少）。

## 14.5 其他同步原语

### 完成量(completion)

```c
// kernel/locking/completion.c
struct completion {
    unsigned int done;          // 完成标志
    struct swait_queue_head wait; // 等待队列
};
```

completion用于"事件通知"模式——一个任务完成工作后通知另一个任务。`complete()`唤醒等待者，`wait_for_completion()`睡眠等待。与信号量的区别：completion的语义更明确——一次`complete()`对应一次`wait_for_completion()`。

### 等待队列

```c
// kernel/sched/wait.c
// 等待队列是内核中"条件等待"的基础
wait_event_interruptible(wq, condition)
  → while (!condition) { schedule(); }
wake_up(&wq)
  → 唤醒等待队列上的进程
```

等待队列贯穿整个内核——中断处理、设备驱动、信号处理都依赖等待队列实现"等待条件满足"的语义。

---

本章建立了对内核锁机制的层级认知：qspinlock用MCS排队消除总线风暴，mutex用乐观自旋平衡延迟与CPU效率，rtmutex用优先级继承防止优先级反转，rwsem和percpu-rwsem优化读写场景。每种锁在特定场景下有独特优势——理解这些权衡才能选择正确的同步原语。第15章将讨论RCU——一种完全不同的同步范式：读端无开销。
