# 第16章 futex与用户态同步

> 源码锚点：`kernel/futex/core.c`、`kernel/futex/pi.c`、`kernel/futex/requeue.c`、`kernel/futex/syscalls.c`、`kernel/futex/waitwake.c`

用户态程序需要高效的同步原语——pthread_mutex、pthread_cond、semaphore等都依赖内核的futex(Fast Userspace muTEX)机制。futex的精髓在于"用户态快速路径+内核回退"——无竞争时完全在用户态完成，有竞争时才进入内核。

## 16.1 futex的设计哲学

### 用户态同步的困境

用户态同步有两种极端：
- **自旋(spin)**：不进入内核，但浪费CPU时间
- **系统调用(syscall)**：不浪费CPU，但每次操作都有上下文切换开销

对于一个经常无竞争的mutex，99%的lock/unlock操作不需要内核参与——用户态的原子操作足以完成。但1%有竞争的情况需要内核参与——等待者必须睡眠，释放者必须唤醒。

### futex的核心思想

futex将同步分为两层：
1. **用户态快速路径**：原子操作检查/修改共享变量，无竞争时直接返回
2. **内核回退**：竞争时通过系统调用进入内核，等待或唤醒

```c
// pthread_mutex_lock的futex实现(简化)
void pthread_mutex_lock(pthread_mutex_t *m) {
    // 快速路径：尝试原子获取
    if (atomic_cmpxchg(&m->lock, 0, 1) == 0)
        return;  // 无竞争，直接获得锁

    // 慢速路径：进入内核等待
    futex(FUTEX_WAIT, &m->lock, 1, ...);
}
```

futex的核心操作：
- **FUTEX_WAIT**：原子检查值+条件等待——如果`*uaddr == val`，则睡眠
- **FUTEX_WAKE**：唤醒指定数量的等待者
- **FUTEX_REQUEUE**：将等待者从一个futex移到另一个（条件变量优化）

## 16.2 futex核心实现

### 哈希表与等待队列

```c
// kernel/futex/core.c
// futex使用全局哈希表，按用户地址查找等待队列
struct futex_hash_bucket {
    struct plist_head chain;   // 等待者链表
} hash_table[FUTEX_HASH_SIZE];

// futex_key区分不同地址空间的futex
struct futex_key {
    u64 iword;              // 编码了mm_struct、页偏移、页内偏移
};
```

多个进程可能在不同地址空间有相同虚拟地址的futex——`futex_key`通过`(mm_struct, 物理页, 页内偏移)`三元组唯一标识一个futex。这确保了不同进程中映射同一物理页的futex能正确地互相等待/唤醒。

### futex_wait_queue()

```c
// kernel/futex/core.c (简化)
void futex_wait_queue(futex_hash_bucket *hb, struct futex_q *q,
                      struct hrtimer_sleeper *timeout)
{
    // 1. 将futex_q加入哈希桶的等待链表
    plist_add(&q->list, &hb->chain);

    // 2. 设置进程状态为TASK_INTERRUPTIBLE
    set_current_state(TASK_INTERRUPTIBLE);

    // 3. 释放哈希桶锁
    spin_unlock(&hb->lock);

    // 4. 如果没有被唤醒，则调度睡眠
    if (!q->bitset && !timeout->task)
        schedule();
}
```

关键：设置`TASK_INTERRUPTIBLE`和释放锁之间的顺序——如果先释放锁再设置状态，可能在设置前被唤醒，导致丢失唤醒。futex通过将等待者加入链表后释放锁来避免这个问题——唤醒者在链表上能找到等待者。

## 16.3 wait与wake

### futex_wait()：原子检查+条件等待

```c
// kernel/futex/waitwake.c (简化)
int futex_wait(u32 __user *uaddr, unsigned int flags, u32 val,
               ktime_t *abs_time, u32 bitset)
{
    // 1. 原子检查：*uaddr是否仍等于val
    //    如果不等，立即返回EAGAIN——值已被修改
    if (get_user(uval, uaddr) || uval != val)
        return -EAGAIN;

    // 2. 获取哈希桶锁
    hb = hash_futex(&key);
    spin_lock(&hb->lock);

    // 3. 再次检查（持锁状态下）
    //    防止检查和入队之间的竞争

    // 4. 入队等待
    futex_wait_queue(hb, &q, timeout);

    // 5. 被唤醒后清理
    return 0;
}
```

两次检查是futex_wait的正确性关键——第一次在无锁状态下快速检查（避免不必要的锁操作），第二次在持锁状态下确认（防止TOCTOU竞争）。

### futex_wake()：唤醒等待者

```c
// kernel/futex/waitwake.c (简化)
int futex_wake(u32 __user *uaddr, unsigned int flags, int nr_wake, u32 bitset)
{
    // 1. 查找哈希桶
    hb = hash_futex(&key);

    // 2. 遍历等待链表，唤醒nr_wake个等待者
    plist_for_each_entry_safe(this, next, &hb->chain, list) {
        if (match_futex(&this->key, &key)) {
            wake_futex(this);  // 唤醒等待者
            if (++ret >= nr_wake)
                break;
        }
    }
}
```

`wake_futex()`将等待者从链表移除，将其进程状态设为`TASK_RUNNING`，然后将其加入调度器的运行队列。

## 16.4 PI futex：优先级继承

### 优先级反转问题

用户态mutex也可能出现优先级反转——低优先级线程持有mutex，高优先级线程等待，中优先级线程抢占低优先级线程。PI futex(PI = Priority Inheritance)通过优先级继承解决。

### PI futex与rtmutex的关系

PI futex底层使用rtmutex——内核的优先级继承互斥锁：

```c
// kernel/futex/pi.c (简化)
int futex_lock_pi(u32 __user *uaddr, unsigned int flags, ktime_t *time, int trylock)
{
    // 1. 原子获取：尝试将uaddr从0改为自己的TID
    if (cmpxchg_futex_value_locked(&curval, uaddr, 0, current->pid))
        return 0;  // 无竞争，直接获得

    // 2. 有竞争：通过rtmutex等待
    ret = rt_mutex_timed_futex_lock(&q.pi_state->pi_mutex, time);

    // 3. 获得锁后更新uaddr为自己的TID
}
```

PI futex的`uaddr`存储持锁线程的TID——0表示未锁定，非零表示持锁者。rtmutex的优先级继承机制自动在内核中传播优先级，解决了用户态的优先级反转。

## 16.5 requeue：条件变量优化

### 条件变量的thundering herd问题

`pthread_cond_broadcast()`唤醒所有等待者——但如果这些等待者需要获取同一个mutex，它们会被串行唤醒，产生"惊群效应"(thundering herd)：大量线程被唤醒、竞争mutex、大部分立即再次睡眠。

### futex_requeue()的优化

```c
// kernel/futex/requeue.c (简化)
int futex_requeue(u32 __user *uaddr1, unsigned int flags,
                  u32 __user *uaddr2, int nr_wake, int nr_requeue)
{
    // 1. 唤醒nr_wake个等待者在uaddr1上
    // 2. 将nr_requeue个等待者从uaddr1移到uaddr2——不唤醒，只是改排队位置
}
```

`futex_requeue()`的精妙之处：等待者从一个等待队列移到另一个，但**不被唤醒**——它们继续睡眠，等待在新的futex(uaddr2，即mutex)上被唤醒。这避免了广播唤醒的惊群效应——线程从cond等待队列移到mutex等待队列，只有获得mutex时才真正被唤醒。

```
pthread_cond_broadcast的实现：
  1. FUTEX_REQUEUE(cond_futex, mutex_futex, wake=1, requeue=INT_MAX)
     → 唤醒1个等待者(让它去获取mutex)
     → 其余等待者移到mutex的等待队列(继续睡眠)
```

## 16.6 futex系统调用接口

```c
// kernel/futex/syscalls.c
SYSCALL_DEFINE6(futex, u32 __user *, uaddr, int, op, u32, val,
                const struct __kernel_timespec __user *, utime,
                u32 __user *, uaddr2, u32, val3)
{
    switch (op) {
    case FUTEX_WAIT:      ...
    case FUTEX_WAKE:      ...
    case FUTEX_REQUEUE:   ...
    case FUTEX_CMP_REQUEUE: ...
    case FUTEX_LOCK_PI:   ...
    case FUTEX_UNLOCK_PI: ...
    case FUTEX_WAIT_BITSET: ...
    case FUTEX_WAKE_BITSET: ...
    }
}
```

Linux 5.14引入了`futex_waitv()`系统调用——一次等待多个futex（类似epoll但用于futex），减少了多条件等待时的系统调用次数。

> **数据库视角**：futex与条件变量。数据库的锁管理器使用条件变量实现事务的等待/唤醒——事务T1等待锁时在条件变量上睡眠，锁释放时唤醒等待者。futex的requeue优化直接适用于此场景：`lock_grant()`唤醒一个等待者时，使用requeue将其他等待者从"锁释放通知"移到"mutex获取"队列，避免不必要的唤醒。现代数据库引擎(如MySQL InnoDB)直接使用futex实现自定义同步原语，而非依赖glibc的pthread实现——可以获得更好的延迟和吞吐。

---

本章建立了对futex机制的深度认知：用户态快速路径+内核回退的设计哲学，哈希表组织等待队列，原子检查+条件等待的正确性保证，PI futex用rtmutex解决优先级反转，requeue优化条件变量广播。futex是用户态同步的内核基础——理解futex才能理解pthread_mutex/pthread_cond的延迟来源和优化空间。第17章将讨论内存序——所有并发正确性的底层保障。
