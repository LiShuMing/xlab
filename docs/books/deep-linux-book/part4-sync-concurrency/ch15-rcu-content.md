# 第15章 RCU：读多写一的无等待同步

> 源码锚点：`kernel/rcu/tree.c`、`kernel/rcu/tree.h`、`kernel/rcu/tree_nocb.h`、`kernel/rcu/tree_exp.h`、`kernel/rcu/srcutree.c`、`kernel/rcu/tree_stall.h`

RCU(Read-Copy-Update)是Linux内核最独特的同步机制——读端零开销（无锁、无原子操作、无Cache行失效），写端通过复制+延迟回收实现更新。这种不对称设计使其成为内核中读多写少场景的首选方案。

## 15.1 RCU的设计哲学

### 读写问题的本质

传统的读写同步方案都有代价：
- **读写锁**：读端需要原子地递增/递减读者计数——Cache行争用
- **序列锁**：读端需要重试——写者频繁时读端饥饿
- **RCU**：读端只增加一个编译器屏障——零同步开销

RCU的核心思想：
1. **读端无等待**：读者直接读取共享数据，不加锁、不递增计数
2. **写端复制更新**：写者创建数据的新副本，修改副本，然后原子地替换指针
3. **延迟回收**：旧数据在所有潜在的读者离开后才被释放——这就是"宽限期"(Grace Period)

### RCU vs 读写锁的性能对比

| 操作 | 读写锁 | RCU |
|------|--------|-----|
| 读进入 | 原子递增计数 | `preempt_disable()`或空操作 |
| 读退出 | 原子递减计数 | `preempt_enable()`或空操作 |
| 写更新 | 等待所有读者退出 | 等待宽限期后释放旧数据 |
| 读端Cache影响 | 修改共享计数器→Cache行失效 | 无共享修改→无Cache影响 |

对于N个CPU并发读的场景，读写锁的读端开销是O(N)（每个CPU修改共享计数器导致Cache行乒乓），RCU的读端开销是O(1)。

## 15.2 Tree RCU：可扩展的RCU实现

### rcu_node树：大规模CPU的可扩展性

单个宽限期需要所有CPU报告静止状态——如果有数千个CPU，单个全局锁成为瓶颈。Tree RCU将CPU组织为一棵树：

```
                    [rcu_node level 0] (根)
                   /         |         \
          [rcu_node lvl 1] [rcu_node lvl 1] [rcu_node lvl 1]
          /    |    \       /    |    \
       CPU0  CPU1  CPU2  CPU3  CPU4  CPU5  ...
```

每个`rcu_node`管理其子节点（或叶子CPU）的静止状态报告。CPU向上级`rcu_node`报告，`rcu_node`汇总后向上级报告，直到根节点。这使得宽限期的管理复杂度为O(log N)而非O(N)。

### 宽限期的启动与推进

```c
// kernel/rcu/tree.c (简化)
static int __noreturn rcu_gp_kthread(void *unused)
{
    for (;;) {
        // 等待宽限期请求
        wait_event_interruptible(rsp->gp_wq, ...);

        // 启动新宽限期
        rcu_gp_start(rsp);

        // 等待所有CPU经历静止状态
        for (;;) {
            if (rcu_gp_in_progress(rsp))
                break;  // 宽限期结束
            schedule_timeout_idle(1);
        }

        // 宽限期结束，执行回调
        rcu_gp_end(rsp);
    }
}
```

宽限期的推进：每个CPU在调度器tick、上下文切换、idle进入等时刻报告自己的静止状态。当所有CPU都经历了至少一个静止状态，宽限期结束——这意味着所有在宽限期开始前开始的读端临界区都已经退出。

### rcu_read_lock()/rcu_read_unlock()

在非抢占内核中，`rcu_read_lock()`就是`preempt_disable()`——禁止抢占保证了当前CPU不会经历上下文切换（一种静止状态），因此读端临界区不会被宽限期跨越。

在可抢占RCU中，`rcu_read_lock()`增加per-CPU的嵌套计数，被抢占时将任务从leaf `rcu_node`中移除——这样宽限期不需要等待被抢占的读者。

### synchronize_rcu()：等待宽限期

```c
// kernel/rcu/update.c
void synchronize_rcu(void)
{
    // 注册一个回调，在下一个宽限期结束后执行
    // 或者直接等待宽限期结束
    if (rcu_scheduler_active == RCU_SCHEDULER_INACTIVE)
        return;  // 启动早期无需等待

    wait_rcu_gp(call_rcu);
}
```

`synchronize_rcu()`阻塞调用者直到宽限期结束——保证所有在调用前开始的RCU读端临界区已经退出。这是写端延迟回收的等待机制。

### call_rcu()：异步回调

```c
// kernel/rcu/tree.c
void call_rcu(struct rcu_head *head, rcu_callback_t func)
{
    // 将回调加入当前CPU的回调队列
    // 在下一个宽限期结束后执行func(head)
}
```

`call_rcu()`注册一个回调，在宽限期结束后异步执行——不阻塞调用者。这是RCU最常用的延迟回收接口。

典型的使用模式：

```c
// 写端：替换指针，延迟释放旧数据
old = rcu_dereference(p);
rcu_assign_pointer(p, new);
call_rcu(&old->rcu_head, free_old_data);

// 读端：在RCU临界区内安全读取
rcu_read_lock();
p = rcu_dereference(ptr);
if (p)
    do_something(p);
rcu_read_unlock();
```

`rcu_dereference()`确保指针读取有正确的内存屏障，`rcu_assign_pointer()`确保新指针在发布前的所有写操作对读者可见。

## 15.3 宽限期加速与NOCB

### expedited宽限期

正常宽限期依赖CPU自然经历静止状态——可能需要数十毫秒。`synchronize_rcu_expedited()`主动向每个CPU发送IPI(Inter-Processor Interrupt)，强制报告静止状态，将宽限期缩短到毫秒级。

代价：IPI中断所有CPU，对延迟敏感的工作负载有影响。只在确实需要快速完成宽限期时使用。

### NOCB：卸载回调执行

`kernel/rcu/tree_nocb.h`实现了NOCB(No-Offload Callbacks)机制——将RCU回调从软中断上下文卸载到per-CPU内核线程：

```
普通模式：软中断 → RCU回调 → 可能延迟其他软中断
NOCB模式：per-CPU kthread → RCU回调 → 不影响软中断延迟
```

NOCB对实时系统至关重要——RCU回调可能执行任意代码（包括`kfree()`），在软中断中执行会增加中断延迟。NOCB将回调移到可调度的内核线程中，使实时任务的可调度性不受RCU回调影响。

## 15.4 SRCU：可睡眠的RCU

普通RCU的读端临界区不可睡眠（`preempt_disable()`）。SRCU(Source-based RCU)允许读端临界区内睡眠：

```c
// kernel/rcu/srcutree.c
// SRCU使用每个srcu_struct的独立计数器
int srcu_read_lock(struct srcu_struct *ssp)
{
    int idx = READ_ONCE(ssp->srcu_idx);  // 选择当前活跃的计数器
    this_cpu_inc(ssp->sda->srcu_lock_count[idx]);  // 递增本地CPU计数
    return idx;
}

void srcu_read_unlock(struct srcu_struct *ssp, int idx)
{
    this_cpu_inc(ssp->sda->srcu_unlock_count[idx]);  // 递减本地CPU计数
}
```

SRCU的宽限期判定：当`srcu_lock_count[idx] == srcu_unlock_count[idx]`（所有读者都已退出），宽限期结束。与Tree RCU不同，SRCU的宽限期是per-srcu_struct的——不同的SRCU实例有独立的宽限期。

SRCU的代价：读端有per-CPU计数器的原子操作，比普通RCU的`preempt_disable()`重。只在需要睡眠的读端临界区使用。

## 15.5 RCU stall检测

宽限期可能因各种原因卡住——某个CPU长时间不报告静止状态。`kernel/rcu/tree_stall.h`检测这种情况：

```
RCU stall的典型输出：
INFO: rcu_sched self-detected stall on CPU
  2-....: (1 GPs behind) idle=...
  NMI backtrace for cpu 2
  ...
```

常见stall原因：
1. **长时间关中断**：`local_irq_save()`后执行了大量工作
2. **长时间自旋锁**：持锁时间过长
3. **无限循环**：内核bug导致CPU无法调度
4. **固件问题**：BIOS/UEFI长期占用CPU（SMI）

`rcu_cpu_stall_timeout`参数控制stall超时（默认21秒），`rcupdate.rcu_cpu_stall_suppress`可以临时抑制stall警告。

## 15.6 小型RCU与工具

- **tiny.c**：单CPU或小系统的简化RCU——无需rcu_node树，宽限期通过上下文切换直接推进
- **update.c**：RCU基础设施，包括`synchronize_rcu()`的通用实现
- **sync.c**：RCU同步原语——允许在RCU读端临界区内等待回调完成
- **rcuscale.c**：RCU可扩展性测试——测量大量CPU下宽限期的延迟
- **refscale.c**：RCU读端性能基准——比较RCU/读写锁/SRCU等的读端开销

> **数据库视角**：RCU与乐观并发控制。RCU的思想与数据库的OCC(Optimistic Concurrency Control)高度共鸣：RCU读不阻塞写→OCC乐观读不加锁；RCU延迟回收→MVCC保留旧版本直到所有活跃事务不再可见；RCU宽限期→快照隔离的可视性判断。PostgreSQL的MVCC中，旧版本的行在所有活跃快照都不再需要时才能被vacuum回收——这与RCU宽限期结束后释放旧数据本质相同。理解RCU有助于理解数据库并发控制中"延迟清理"的设计模式。

---

本章建立了对RCU的深度认知：Tree RCU用rcu_node树实现可扩展的宽限期管理，乐观自旋与睡眠等待平衡延迟和效率，NOCB卸载回调保障实时性，SRCU允许可睡眠的读端临界区，stall检测帮助诊断宽限期卡住问题。RCU是Linux内核最精巧的同步机制——理解其设计哲学有助于在正确的场景选择RCU而非传统锁。第16章将讨论futex——另一种用户态的同步基础。
