# 第7章 调度器：CFS与实时

> 源码锚点：`kernel/sched/fair.c`、`kernel/sched/rt.c`、`kernel/sched/deadline.c`、`kernel/sched/core.c`、`kernel/sched/topology.c`、`kernel/sched/pelt.c`、`kernel/sched/psi.c`、`kernel/sched/sched.h`

调度器是操作系统的心脏——它决定哪个进程获得CPU时间、获得多少、何时被抢占。Linux调度器从单一的O(1)调度器演化为多调度类架构，CFS(完全公平调度器)服务普通进程，实时调度器服务延迟敏感任务，Deadline调度器提供确定性保障。本章深入每个调度类的设计哲学与实现。

## 7.1 调度器框架

### __schedule()：调度的主循环

所有调度最终汇聚到`__schedule()`——这是调度器的核心入口：

```c
// kernel/sched/core.c
static void __sched notrace __schedule(int sched_mode)
{
    struct task_struct *prev, *next;
    bool preempt = sched_mode > SM_NONE;
    struct rq *rq;
    int cpu;

    cpu = smp_processor_id();
    rq = cpu_rq(cpu);
    prev = rq->curr;

    local_irq_disable();
    rq_lock(rq, &rf);
    smp_mb__after_spinlock();

    update_rq_clock(rq);

    // 处理当前进程状态
    prev_state = READ_ONCE(prev->__state);
    if (!preempt && prev_state) {
        // 自愿让出CPU（sleep/等待），将进程从运行队列移除
        try_to_block_task(rq, prev, &prev_state, ...);
        switch_count = &prev->nvcsw;  // 自愿上下文切换计数
    }

    // 选择下一个进程
    next = pick_next_task(rq, rq->donor, &rf);

    // 如果选中的进程与当前不同，执行上下文切换
    if (likely(prev != next)) {
        rq = context_switch(rq, prev, next, &rf);
    }
}
```

`__schedule()`的调度模式(`sched_mode`)：
- **SM_NONE**：自愿调度，进程主动sleep/等待
- **SM_PREEMPT**：抢占调度，时钟中断或唤醒导致的抢占
- **SM_IDLE**：idle调度，CPU无事可做

### 调度类优先级链

`pick_next_task()`按调度类优先级选择进程：

```c
// 调度类优先级（从高到低）
stop_sched_class      // 停机调度（迁移线程，最高优先级，不可抢占）
  ↓
dl_sched_class        // Deadline调度（SCHED_DEADLINE）
  ↓
rt_sched_class        // 实时调度（SCHED_FIFO/SCHED_RR）
  ↓
fair_sched_class      // CFS公平调度（SCHED_NORMAL/SCHED_BATCH）
  ↓
idle_sched_class      // idle调度（swapper，最低优先级）
```

`pick_next_task()`从最高优先级的调度类开始询问，如果该类没有可运行进程，就询问下一个调度类。这保证了实时进程总是优先于普通进程。

### 运行队列：struct rq

每个CPU有一个运行队列`struct rq`，是调度器最核心的数据结构：

```c
// kernel/sched/sched.h (简化)
struct rq {
    raw_spinlock_t      lock;           // 运行队列自旋锁
    unsigned int        nr_running;     // 队列中进程总数
    struct task_struct  *curr;          // 当前正在运行的进程
    struct task_struct  *donor;         // 实际消耗CPU时间的进程(proxy exec)
    u64                 clock;          // 运行队列时钟
    struct cfs_rq       cfs;            // CFS子队列
    struct rt_rq        rt;             // RT子队列
    struct dl_rq        dl;             // Deadline子队列
    ...
};
```

每个调度类有自己的子队列——`cfs_rq`、`rt_rq`、`dl_rq`。调度器先在`dl_rq`中查找，再在`rt_rq`中查找，最后在`cfs_rq`中查找。

## 7.2 CFS：完全公平调度器

### 设计哲学：理想公平与vruntime

CFS的核心思想是**完全公平**：在一个理想的处理器上，所有可运行进程应该获得完全相等的CPU时间。现实处理器无法同时运行多个进程，但CFS通过追踪每个进程获得的"虚拟运行时间"(vruntime)来近似公平。

CFS当前使用EEVDF(Earliest Eligible Virtual Deadline First)算法替代了传统的红黑树vruntime方案，但vruntime的概念仍然核心——它衡量进程已经消耗了多少"公平份额"的CPU时间。

```c
// kernel/sched/fair.c
static void update_curr(struct cfs_rq *cfs_rq)
{
    struct sched_entity *curr = cfs_rq->curr;
    s64 delta_exec;

    delta_exec = update_se(rq, curr);               // 实际运行时间
    curr->vruntime += calc_delta_fair(delta_exec, curr);  // 更新vruntime
    resched = update_deadline(cfs_rq, curr);         // 更新截止时间

    if (resched || !protect_slice(curr))
        resched_curr_lazy(rq);                       // 请求重新调度
}
```

`calc_delta_fair()`将实际运行时间转换为vruntime增量——权重越高的进程（nice值越低），vruntime增长越慢。nice 0的进程权重为1024，nice -5的权重约3121，所以nice -5的进程vruntime增长速度只有nice 0的约1/3，能获得3倍的CPU时间。

### place_entity()：新进程的vruntime初始化

新进程或刚唤醒的进程如何设置初始vruntime？如果直接设为0，它会独占CPU直到vruntime追上其他进程。如果设为当前最小vruntime，它可能等待很久才能运行。

```c
// kernel/sched/fair.c
place_entity(struct cfs_rq *cfs_rq, struct sched_entity *se, int flags)
{
    u64 vslice, vruntime = avg_vruntime(cfs_rq);

    se->slice = sysctl_sched_base_slice;       // 默认时间片
    vslice = calc_delta_fair(se->slice, se);    // 时间片的vruntime等价值

    if (sched_feat(PLACE_LAG) && cfs_rq->nr_queued && se->vlag) {
        lag = se->vlag;
        // 保持进程的lag——补偿睡眠进程的vruntime
    }

    se->vruntime = vruntime - lag;
    se->deadline = se->vruntime + vslice;
}
```

EEVDF的放置策略：
- **新进程(fork)**：lag=0，放在当前平均vruntime位置，deadline为vruntime+vslice
- **唤醒进程(wakeup)**：保持出队时的lag（虚拟延迟），允许补偿睡眠时间
- **滞后(lag>0)**：进程欠了CPU时间，deadline更早，更快被调度
- **超前(lag<0)**：进程多占了CPU时间，deadline更晚，等待更久

### CFS子队列：红黑树与deadline

```c
// kernel/sched/sched.h
struct cfs_rq {
    struct load_weight  load;                  // 总负载
    unsigned int        nr_queued;             // 队列中进程数
    struct rb_root_cached tasks_timeline;      // 按deadline排序的红黑树
    struct sched_entity *curr;                 // 当前运行的实体
    u64                 min_vruntime;          // 最小vruntime追踪
    ...
};
```

CFS的红黑树按`deadline`排序——deadline最早的任务在树的最左节点，是下一个被调度的候选。`tasks_timeline`是缓存了最左节点的红黑树，`__pick_first_entity()`可以在O(1)时间找到下一个要运行的进程。

### 时间片计算

CFS的时间片不是固定的——它由进程权重和运行队列中的进程数决定：

```c
// sysctl_sched_base_slice 默认值 (通常1.5ms)
// 实际时间片 = base_slice * (weight / total_weight)
```

nice 0的进程权重1024，如果有4个nice 0的进程，每个获得1/4的CPU时间。时间片不能太短（调度开销增大）也不能太长（响应延迟增大）。`sysctl_sched_base_slice`（旧名`sched_min_granularity_ns`）控制最小时间片，默认约1.5ms。

### 组调度

CFS支持组调度——cgroup中的进程组作为一个调度实体参与竞争，组内再公平分配。这使得两个用户各运行10个进程时，每个用户获得50%的CPU（而非每个进程5%）。

组调度的实现：`task_group`包含自己的`cfs_rq`，嵌套在父cfs_rq中。调度时先在顶层cfs_rq选择group，再在group的cfs_rq中选择task。

> **数据库视角**：长查询与短查询的调度公平性。CFS的vruntime机制自然地处理了长短查询的公平性——长查询积累了更多vruntime，自然被降低优先级。但数据库场景有一个独特问题：长事务可能持有锁，如果被降低优先级导致延迟释放锁，反而降低了系统吞吐。PostgreSQL的后端进程模型中，这个问题由用户态的锁管理器处理，不依赖内核调度公平性。

## 7.3 实时调度：RT与Deadline

### RT调度器：SCHED_FIFO与SCHED_RR

实时调度器在`kernel/sched/rt.c`中实现，支持两种策略：

| 策略 | 时间片 | 优先级范围 | 行为 |
|------|--------|-----------|------|
| SCHED_FIFO | 无限 | 1-99 | 一直运行直到主动让出或被更高优先级抢占 |
| SCHED_RR | 轮转(默认100ms) | 1-99 | 时间片用完重新排队，同优先级轮转 |

RT运行队列使用**位图+优先级链表**：

```c
// kernel/sched/sched.h
struct rt_rq {
    struct rt_prio_array active;     // 优先级数组
    ...
};

struct rt_prio_array {
    DECLARE_BITMAP(bitmap, MAX_RT_PRIO+1);  // 位图：哪些优先级有进程
    struct list_head queue[MAX_RT_PRIO];     // 每个优先级一个链表
};
```

查找最高优先级进程：先在位图中找最高位（`__find_first_bit`，O(1)），然后从对应链表头取进程。这比CFS的红黑树更简单高效——实时调度对确定性要求更高。

### 实时带宽限制

RT进程如果不加限制，可以完全饿死普通进程。Linux通过`rt_runtime`/`rt_period`限制RT进程的CPU使用：

- `rt_period_us`：统计周期，默认1秒
- `rt_runtime_us`：周期内RT最多运行时间，默认0.95秒

RT进程在0.95秒内用完配额后会被节流(throttled)，剩余0.05秒留给普通进程。这防止了RT进程bug导致的系统完全无响应。

### Deadline调度器：SCHED_DEADLINE

`kernel/sched/deadline.c`实现了SCHED_DEADLINE策略，基于**最早截止时间优先(EDF)**算法：

```c
// SCHED_DEADLINE的三个参数
runtime   // 每个周期内保证的运行时间
period    // 周期
deadline  // 截止时间（通常等于period）
```

示例：一个实时任务需要每10ms运行3ms：
```
runtime = 3ms, period = 10ms, deadline = 10ms
```

调度器保证在每个period内，该任务至少获得runtime的CPU时间。如果多个Deadline任务的总bandwidth超过100%，新的Deadline任务无法被接纳(admission control)。

CBS(Const Bandwidth Server)为Deadline任务提供带宽隔离——即使任务没有用完runtime，也不会获得额外时间，防止一个任务影响其他任务的保证。

> **AI视角**：推理服务的SLO保障。推理服务通常有延迟SLO（如P99 < 100ms）。SCHED_DEADLINE可以为推理进程提供硬性延迟保证——设置runtime=50ms, period=100ms，确保每100ms内推理进程至少运行50ms。结合cgroup的cpu.max限制，可以在多租户环境中为不同优先级的推理任务分配差异化保障。但SCHED_DEADLINE的接纳控制意味着总bandwidth不能超100%，这限制了可部署的任务数量。

## 7.4 调度域与负载均衡

### 调度域层级

SMP系统中，调度器需要决定进程在哪个CPU上运行。调度域(Scheduling Domain)描述CPU的拓扑关系：

```
调度域层级（从内到外）：
SMT (Hyper-Threading) → MC (多核) → NUMA → DIE
```

```c
// kernel/sched/topology.c
// 典型的调度域拓扑
CPU 0,1 (SMT siblings) → Core 0
CPU 2,3 (SMT siblings) → Core 1
Core 0,1 → NUMA Node 0
NUMA Node 0,1 → Die
```

每层调度域有不同的负载均衡策略：
- **SMT级**：共享L1/L2的兄弟线程，最积极的均衡
- **MC级**：共享L3的核，中等积极的均衡
- **NUMA级**：跨节点，最保守——跨节点迁移的Cache和内存访问代价最高

### 负载均衡触发时机

负载均衡在以下时机触发：

1. **周期性均衡**：每隔一段时间(由`sched_latency_ns`决定)，调度器检查是否需要均衡
2. **唤醒均衡**：进程被唤醒时，选择负载最轻的CPU（考虑Cache亲和性）
3. **fork均衡**：新进程创建时选择目标CPU
4. **主动均衡**：某个CPU负载极高时，其他CPU主动拉取任务

`find_busiest_group()`在调度域中寻找最忙的组，`load_balance()`将任务从最忙组迁移到当前CPU。

## 7.5 PELT与PSI

### PELT：Per-Entity Load Tracking

PELT在`kernel/sched/pelt.c`中实现，追踪每个调度实体（进程/cgroup）的负载和利用率：

```c
// kernel/sched/pelt.c
___update_load_sum(u64 now, struct sched_avg *sa,
                   unsigned long load, unsigned long runnable, int running)
{
    // 1. 计算时间差
    delta = now - sa->last_update_time;

    // 2. 按周期衰减
    decay_load(sa->load_sum, periods);
    decay_load(sa->runnable_sum, periods);
    decay_load(sa->util_sum, periods);

    // 3. 累加新周期
    accumulate_sum(delta, sa, load, runnable, running);
}
```

PELT的核心是**几何衰减**——最近1ms的负载权重为1，1ms前的权重为0.881(=y^1)，2ms前为0.775(=y^2)，以此类推。衰减因子y=0.881^(1ms)，约对应32ms的半衰期。这使得PELT对负载变化的响应既不太快也不太慢。

PELT追踪三个信号：

| 信号 | 含义 | 用途 |
|------|------|------|
| load_avg | 可运行负载（包含等待CPU的时间） | 负载均衡 |
| util_avg | 利用率（只包含实际运行时间） | CPU频率调节(CPUFreq) |
| runnable_avg | 可运行时间占比 | 负载均衡决策 |

**load vs utilization的区别**：一个进程100%时间可运行但只在50%时间实际运行（另外50%等待I/O），load_avg=100%，util_avg=50%。load反映"需要多少CPU"，util反映"实际用了多少CPU"。

### PSI：Pressure Stall Information

PSI在`kernel/ssched/psi.c`中实现，量化系统的资源压力：

```
some：至少一个任务等待资源
full：所有任务都在等待资源（CPU完全空闲不算）
```

PSI追踪三种资源的压力：
- **CPU**：任务等待CPU时间
- **Memory**：任务等待内存回收
- **I/O**：任务等待I/O完成

```c
// PSI的状态位
TSK_IOWAIT     // 等待I/O
TSK_MEMDELAY   // 等待内存
TSK_ONCPU      // 在CPU上运行
```

PSI的计算：在时间窗口(默认2s或10s)内，统计some和full状态的占比，输出到`/proc/pressure/`：

```
# /proc/pressure/cpu
some avg10=0.12 avg60=0.08 avg300=0.04 total=1234567

# /proc/pressure/memory
some avg10=0.50 avg60=0.30 avg300=0.10 total=9876543
full avg10=0.10 avg60=0.05 avg300=0.02 total=1234567
```

- **avg10/60/300**：最近10秒/60秒/300秒的平均压力百分比
- **total**：累计微秒数

PSI的优势：它提供了比负载平均值(load average)更精确的信号。load average无法区分CPU压力和I/O压力，PSI可以。PSI还可以通过`/proc/pressure/`的fd + `POLLPRI`实现压力阈值通知——当压力超过阈值时触发事件，驱动自动扩缩容。

> **数据库视角**：用PSI诊断查询排队的原因。当查询延迟升高时，PSI可以快速定位瓶颈——如果CPU some压力高，是CPU不足；如果memory some/full压力高，是内存回收导致停顿；如果I/O some压力高，是磁盘瓶颈。这比传统的load average（只反映可运行+不可中断睡眠进程数）精确得多。

## 7.6 调度器扩展

### sched_ext：BPF可编程调度器

Linux 6.12引入了`sched_ext`(sched_ext)——通过BPF程序实现自定义调度策略：

```c
// kernel/sched/ext.c
// sched_ext允许通过BPF实现：
// - 自定义任务选择策略
// - 自定义时间片分配
// - 自定义负载均衡决策
// - 自定义唤醒目标CPU选择
```

sched_ext的关键设计：
1. **安全回退**：如果BPF调度器出现bug（如死锁、饿死），内核自动回退到CFS
2. **低开销**：BPF程序经过JIT编译，调度路径无需切换到用户态
3. **可观测**：BPF调度器的决策过程可以通过tracepoint观测

sched_ext的核心操作：
- `select_cpu()`：为唤醒的任务选择目标CPU
- `enqueue()`：将任务加入调度队列
- `dispatch()`：选择下一个运行的任务
- `running()`/`stopping()`：任务开始/停止运行的回调
- `yield()`：任务主动让出CPU

> **AI视角**：用BPF实现推理任务的定制调度策略。例如：为推理进程实现"预算调度"——每个推理进程有QPS预算，预算用完后降低优先级；或者实现"延迟感知调度"——根据请求的SLO动态调整时间片；或者实现"GPU感知调度"——将等待GPU的推理进程与CPU密集型进程分开调度，避免GPU空闲时CPU仍在执行推理前处理。这些策略不适合加入CFS，但通过sched_ext可以快速实验和部署。

---

本章建立了对Linux调度器的全面认知：`__schedule()`是调度的入口，调度类优先级链保证实时进程优先，CFS通过vruntime和EEVDF实现公平调度，RT/Deadline提供不同层次的实时保障，PELT/PSI提供负载追踪和压力量化，sched_ext开启可编程调度的新范式。第8章将讨论cgroup如何将这些调度能力组合为资源隔离机制。
