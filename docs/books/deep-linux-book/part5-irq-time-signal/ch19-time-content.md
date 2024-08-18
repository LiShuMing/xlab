# 第19章 时间子系统

> 源码锚点：`kernel/time/clocksource.c`、`kernel/time/timekeeping.c`、`kernel/time/clockevents.c`、`kernel/time/hrtimer.c`、`kernel/time/timer.c`、`kernel/time/tick-sched.c`、`kernel/time/posix-timers.c`、`arch/x86/entry/vdso/common/vclock_gettime.c`

时间子系统为内核和用户态提供时间服务——从纳秒级高精度定时器到秒级wall clock，从CPU时间统计到NTP频率调整。Linux的时间子系统采用分层架构：硬件时钟源提供原始计数器，timekeeping模块维护系统时间，hrtimer和timer wheel提供不同精度的定时服务。

## 19.1 时钟源与时间保持

### struct clocksource：硬件时钟源抽象

时钟源是单调递增的硬件计数器——TSC、HPET、ACPI PM Timer等。内核通过`clocksource`抽象统一访问：

```c
// include/linux/clocksource.h
struct clocksource {
    u64     (*read)(struct clocksource *cs);    // 读取当前计数值
    u64     mask;          // 计数器掩码(处理回绕)
    u32     mult;          // 周期→纳秒的乘数
    u32     shift;         // 周期→纳秒的移位数
    u64     max_idle_ns;   // 最大空闲时间(防止溢出)
    u32     maxadj;        // 最大mult调整值(~11%)
    const char *name;
    int     rating;         // 评分(越高越好)
    enum vdso_clock_mode vdso_clock_mode;  // vDSO是否可用
    // ...
};
```

**rating评分体系**：
- 1-99：不可用，仅用于启动和测试
- 100-199：基本可用，但不理想
- 200-299：良好，正确可用
- 300-399：理想，快速且精确
- 400-499：完美，必须使用

x86平台的典型时钟源：TSC(rating 300+) > HPET(rating 250) > ACPI PM Timer(rating 200)。内核自动选择最高rating的时钟源。

### 周期到纳秒的转换

时钟源返回的是硬件周期数，需要转换为纳秒。内核使用定点数乘法+移位实现高效转换：

```
纳秒 = (周期数 * mult) >> shift
```

`clocks_calc_mult_shift()`计算最优的mult/shift对——在保证精度和避免溢出之间取平衡。更大的shift意味着更高精度，但转换范围更小。

### 时钟源Watchdog

时钟源可能不稳定——TSC在频率缩放时可能漂移，HPET可能固件有bug。时钟源watchdog机制检测不稳定的时钟源：

```
watchdog(HPET) → 定期读取被监视时钟源(TSC)和watchdog
→ 如果两者偏差超过阈值 → 标记TSC为unstable → 降级到次优时钟源
```

watchdog是内核自我保护的重要机制——防止不可靠的时钟源破坏系统时间。

### timekeeping：系统时间的维护

`timekeeping`模块基于时钟源维护各种系统时钟：

```c
// kernel/time/timekeeping.c
struct timekeeper {
    struct clocksource  *clock;     // 当前时钟源
    u64                 cycle_last; // 上次读取的周期值
    u64                 mult;       // 调整后的周期→纳秒乘数
    u32                 shift;
    // 各种时钟基准
    struct tk_read_base base[4];   // CLOCK_REALTIME/MONOTONIC/...
    // NTP调整
    s32                 ntp_error;
    long                ntp_tick;
};
```

关键时钟类型：
- **CLOCK_REALTIME**：系统wall clock，可被NTP/用户调整，可能跳变
- **CLOCK_MONOTONIC**：单调递增时钟，不受NTP跳变影响，但受频率调整影响
- **CLOCK_MONOTONIC_RAW**：纯硬件时钟，不受NTP任何调整
- **CLOCK_BOOTTIME**：类似MONOTONIC，包含休眠时间

timekeeping在每次tick（或hrtimer中断）时更新——读取时钟源的当前周期值，计算经过的纳秒数，更新各时钟基准。`ktime_get()`/`ktime_get_ns()`是内核获取时间的标准接口。

### NTP频率调整

`kernel/time/ntp.c`实现NTP频率调整——系统与NTP服务器同步时，不是一步到位地修改时间，而是微调时钟源的mult值，让系统时间逐渐对齐：

```
NTP调整 → 修改timekeeper.mult → 每个tick多走/少走一点纳秒 → 逐渐同步
```

这避免了时间跳变——对数据库等依赖时间单调性的应用至关重要。mult的调整范围被限制在`maxadj`(~11%)内——超过此范围说明时钟源有严重问题。

## 19.2 时钟事件与tick

### struct clock_event_device：可编程定时器

时钟事件设备是可编程的定时器硬件——可以设置"在N纳秒后产生中断"：

```c
// include/linux/clockchips.h
struct clock_event_device {
    void (*event_handler)(struct clock_event_device *);  // 中断回调
    int  (*set_next_event)(unsigned long evt, struct clock_event_device *);
    int  (*set_next_ktime)(ktime_t expires, struct clock_event_device *);
    ktime_t next_event;          // 下一次事件的到期时间
    unsigned int features;       // 特性标志
    int  (*set_state_periodic)(struct clock_event_device *);
    int  (*set_state_oneshot)(struct clock_event_device *);
    int  (*set_state_shutdown)(struct clock_event_device *);
    const char *name;
    int  rating;
    // ...
};
```

两种工作模式：
- **周期模式(Periodic)**：以固定频率产生中断——传统tick模式，每1/HZ秒一次
- **单次模式(Oneshot)**：每次设置下一次中断的精确时间——高精度模式的基础

x86的Local APIC Timer和HPET都可以作为时钟事件设备。Local APIC Timer是per-CPU的——每个CPU独立设置下次中断时间。

### tick设备管理

tick设备是时钟事件设备的高层封装，为调度器和时间轮提供定期的tick中断：

```c
// kernel/time/tick-sched.c
// 每个CPU一个tick_sched结构
static DEFINE_PER_CPU(struct tick_sched, tick_cpu_sched);
```

### NOHZ_IDLE：空闲CPU关闭tick

CPU进入idle时不需要定期tick——关闭tick可以让CPU深度睡眠，节省功耗：

```
CPU进入idle → tick_nohz_idle_enter() → 编程时钟事件设备为下一个定时器到期时间
→ CPU长时间无工作 → 无tick中断 → 深度睡眠
→ 定时器到期或中断到来 → tick_nohz_idle_exit() → 更新jiffies → 恢复tick
```

idle期间的jiffies更新通过`tick_do_update_jiffies64()`补偿——在退出idle时一次性追上。

### NOHZ_FULL：孤立CPU的tickless

`NOHZ_FULL`模式更进一步——非idle的CPU也可以无tick运行。适用于实时工作负载：一个CPU专门运行实时任务，完全不受tick中断干扰：

```
isolcpus=3 → CPU 3运行实时任务 → 只在需要调度时才有中断 → 延迟极低
```

NOHZ_FULL的限制：CPU上只能运行一个任务（或SCHED_FIFO任务），不能有定时器回调。内核通过`timer_migration`将定时器迁移到housekeeping CPU。

## 19.3 hrtimer：高精度定时器

### 红黑树组织定时器

hrtimer使用红黑树组织每个CPU上的定时器——按到期时间排序，O(log n)插入/删除：

```c
// kernel/time/hrtimer.c
struct hrtimer_clock_base {
    struct timerqueue_head  active;     // 红黑树根节点
    ktime_t                 offset;     // 时钟偏移量
    struct hrtimer_cpu_base *cpu_base;  // 所属CPU base
    unsigned int            index;      // 时钟类型索引
};

struct hrtimer_cpu_base {
    raw_spinlock_t          lock;
    unsigned int            active_bases;  // 活跃时钟基准位图
    struct hrtimer_clock_base clock_base[4]; // MONOTONIC/REALTIME/BOOTTIME/TAI
    ktime_t                 expires_next;  // 下一个到期时间
    struct hrtimer          *next_timer;   // 下一个到期的定时器
    // ...
};
```

每个CPU有4个`hrtimer_clock_base`——分别对应MONOTONIC、REALTIME、BOOTTIME、TAI四种时钟。活跃的base通过`active_bases`位图快速索引。

### hrtimer_start_range_ns()

```c
// kernel/time/hrtimer.c (简化)
static bool __hrtimer_start_range_ns(struct hrtimer *timer, ktime_t tim,
                                      u64 delta_ns, const enum hrtimer_mode mode,
                                      struct hrtimer_clock_base *base)
{
    // 1. 如果是相对模式，转换为绝对时间
    if (mode & HRTIMER_MODE_REL)
        tim = ktime_add_safe(tim, __hrtimer_cb_get_time(base->clockid));

    // 2. 从红黑树中移除（如果已入队）
    bool was_armed = remove_hrtimer(timer, base, HRTIMER_STATE_ENQUEUED);

    // 3. 设置到期时间
    hrtimer_set_expires_range_ns(timer, tim, delta_ns);

    // 4. 插入红黑树
    bool first = enqueue_hrtimer(timer, base, mode, was_armed);

    // 5. 如果是第一个到期的定时器，重新编程时钟事件设备
    return first;  // 调用方据此决定是否reprogram
}
```

关键优化：如果新定时器是最早到期的，需要立即重新编程时钟事件设备——否则硬件中断可能在旧的时间点触发，错过新的更早到期时间。

### hrtimer的到期执行

```c
// kernel/time/hrtimer.c (简化)
static void __run_hrtimer(struct hrtimer_cpu_base *cpu_base,
                           struct hrtimer_clock_base *base,
                           struct hrtimer *timer, ktime_t now, unsigned long flags)
{
    base->running = timer;                     // 标记正在运行
    __remove_hrtimer(timer, base, HRTIMER_STATE_INACTIVE, false);  // 从红黑树移除
    fn = ACCESS_PRIVATE(timer, function);

    raw_spin_unlock_irqrestore(&cpu_base->lock, flags);  // 释放锁
    restart = fn(timer);                       // 执行回调
    raw_spin_lock_irq(&cpu_base->lock);        // 重新获取锁

    // 如果回调返回RESTART且定时器未重新入队，自动重新入队
    if (restart == HRTIMER_RESTART && !timer->is_queued)
        enqueue_hrtimer(timer, base, HRTIMER_MODE_ABS, false);

    base->running = NULL;
}
```

hrtimer回调在硬中断上下文执行（高精度模式）或软中断上下文执行（低精度模式）。回调不能睡眠，必须快速完成。

### 高精度模式 vs 低精度模式

**高精度模式**(`CONFIG_HIGH_RES_TIMERS`)：时钟事件设备工作在oneshot模式，hrtimer到期时直接在硬中断上下文执行回调。精度取决于硬件定时器，通常在微秒级。

**低精度模式**：时钟事件设备工作在周期模式，hrtimer到期检查在tick中断中进行。精度为1/HZ秒（1ms或4ms或10ms）。

内核启动时处于低精度模式，在时钟事件设备可用后切换到高精度模式。如果高精度模式检测到问题（如中断hang），会自动降级到低精度模式。

### 软中断模式

hrtimer可以在软中断中执行——`HRTIMER_MODE_SOFT`标志的定时器在`HRTIMER_SOFTIRQ`软中断中处理，允许更长的执行时间而不阻塞硬中断。周期定时器（如调度器的sched_tick）使用软中断模式——避免在硬中断中长时间占用CPU。

## 19.4 POSIX定时器

### timer_create/timer_settime

`kernel/time/posix-timers.c`实现POSIX定时器——用户态通过`timer_create()`/`timer_settime()`创建和设置定时器：

```c
// 内核为每个POSIX定时器创建一个hrtimer
// timer_settime → hrtimer_start() 设置到期时间
// 到期时 → 发送信号(SIGEV_SIGNAL)或启动线程(SIGEV_THREAD)
```

信号通知模式：定时器到期时向进程发送信号（默认SIGRTMIN+timerid）。内核通过`siginfo_t`的`si_value`传递定时器ID和用户数据。

线程通知模式：内核创建辅助线程执行用户指定的通知函数。glibc在用户态实现了线程通知——内核只负责发送信号，glibc的信号处理器调用用户函数。

### CPU时间定时器

`kernel/time/posix-cpu-timers.c`实现基于CPU时间的定时器——`CLOCK_PROCESS_CPUTIME_ID`/`CLOCK_THREAD_CPUTIME_ID`：

```c
// CPU时间定时器不在hrtimer上——它挂在进程/线程的cputime上
// 每次时钟中断检查：进程/线程的CPU时间是否超过定时器设置
// 超过 → 发送信号
```

`RLIMIT_CPU`资源限制也通过CPU时间定时器实现——进程CPU时间超过限制时发送SIGXCPU信号。

## 19.5 时间轮(Timer Wheel)

### 多级时间轮的设计

`kernel/time/timer.c`实现低精度定时器——多级时间轮，9级(HZ>100)或8级(HZ<=100)：

```c
// kernel/time/timer.c
#define LVL_BITS    6           // 每级64个桶
#define LVL_SIZE    (1 << 6)    // 64
#define LVL_CLK_SHIFT  3        // 每级时钟除以8
#define LVL_DEPTH   9           // 9级(HZ=1000)
#define WHEEL_SIZE  (LVL_SIZE * LVL_DEPTH)  // 576个桶
```

HZ=1000时的各级粒度和范围：

| 级别 | 粒度 | 范围 |
|------|------|------|
| 0 | 1ms | 0 - 63ms |
| 1 | 8ms | 64ms - 511ms |
| 2 | 64ms | 512ms - ~4s |
| 3 | 512ms | ~4s - ~32s |
| 4 | ~4s | ~32s - ~4min |
| 5 | ~32s | ~4min - ~34min |
| 6 | ~4min | ~34min - ~4h |
| 7 | ~34min | ~4h - ~1d |
| 8 | ~4h | ~1d - ~12d |

### 定时器入队

```c
// 定时器根据到期时间选择级别
// 级别 = 最高有效位位置 / LVL_CLK_SHIFT
// 桶号 = (expires >> (level * LVL_CLK_SHIFT)) & LVL_MASK
```

核心思想：近期的定时器放入低级别桶(高精度)，远期的定时器放入高级别桶(低精度)。大多数定时器是短期超时（网络、I/O），集中在0-2级，高级别桶通常很空。

### 与旧版时间轮的区别

旧版时间轮需要级联(cascading)——高级别桶到期时，将其中的定时器逐个移到低级别。这导致最坏情况O(n)的延迟。新版时间轮取消了级联——高级别桶的定时器保持原位，到期时直接执行（允许一定延迟）。因为超时定时器通常被取消而非到期，精度损失可接受。

### timer_base

```c
// kernel/time/timer.c
struct timer_base {
    raw_spinlock_t      lock;
    struct timer_list   *running_timer;
    unsigned long       clk;            // 当前时钟
    unsigned long       next_expiry;    // 下一个到期时间
    bool                is_idle;        // CPU是否idle
    DECLARE_BITMAP(pending_map, WHEEL_SIZE);  // 桶占用位图
    struct hlist_head   vectors[WHEEL_SIZE];  // 576个桶
};
```

`pending_map`位图实现O(1)的"下一个到期桶"查找——`ffs(pending_map >> offset)`快速定位有定时器的桶。这比遍历空桶高效得多。

## 19.6 vDSO与快速时间获取

### vDSO的原理

`gettimeofday()`/`clock_gettime()`是高频调用的系统调用——每次进入内核开销约1-2微秒。vDSO(Virtual Dynamic Shared Object)将时间获取从系统调用变为普通的函数调用：

```
传统方式：用户态 → syscall → 内核timekeeping → 返回 → 用户态  (~1-2μs)
vDSO方式：用户态 → 读取共享内存中的时间数据 → 用户态            (~20-50ns)
```

### vDSO的实现

```c
// arch/x86/entry/vdso/common/vclock_gettime.c
int __vdso_gettimeofday(struct __kernel_old_timeval *tv, struct timezone *tz)
{
    return __cvdso_gettimeofday(tv, tz);
}

int __vdso_clock_gettime(clockid_t clock, struct __kernel_timespec *ts)
{
    return __cvdso_clock_gettime(clock, ts);
}
```

vDSO的核心在`lib/vdso/gettimeofday.c`——它读取内核映射到用户态的`vdso_data`结构：

```c
// 简化的vDSO获取时间流程：
// 1. 读取vdso_data中的时钟源信息(mult, shift, cycle_last, base_time)
// 2. 通过rdtsc读取TSC当前值
// 3. 计算delta = tsc - cycle_last
// 4. 纳秒 = (delta * mult) >> shift + base_ns
// 5. 检查seqcount——如果期间内核更新了数据，重试
```

关键：内核在更新timekeeping时，同时更新`vdso_data`——包括当前周期值、mult/shift、基础时间等。用户态通过seqcount检测并发更新——读取期间如果内核更新了数据，重新读取。

### vDSO的限制

vDSO只支持特定时钟类型（MONOTONIC、REALTIME、BOOTTIME等）——不支持的时钟类型仍然需要系统调用。时间调整(NTP step)后，vDSO可能暂时不可用——内核设置`vdso_clock_mode = VDSO_CLOCKMODE_NONE`，强制走系统调用路径直到数据稳定。

### 数据库视角：高精度时间戳获取

数据库几乎每个操作都需要时间戳——WAL日志、事务开始/提交时间、查询超时等。vDSO对数据库性能至关重要：高频时间戳获取（每秒百万次）从1-2μs降到20-50ns，减少99%的开销。Percona和PostgreSQL都依赖`clock_gettime(CLOCK_MONOTONIC)`获取时间戳——在x86上几乎全部通过vDSO完成，无需进入内核。

`statement_timeout`的实现：数据库设置hrtimer定时器——查询开始时`hrtimer_start()`，到期时回调函数发送SIGINT信号取消查询。内核hrtimer的微秒级精度确保超时控制的准确性。

---

本章建立了对Linux时间子系统的完整认知：clocksource抽象硬件时钟源，timekeeping维护系统时间，hrtimer提供高精度定时器，时间轮提供低精度定时器，tick管理驱动调度器和时间轮，NOHZ减少不必要的tick中断，vDSO加速用户态时间获取。时间子系统是内核定时服务的基础——调度器的tick、POSIX定时器、数据库的超时控制都依赖于此。第20章将讨论信号——另一种异步事件通知机制。
