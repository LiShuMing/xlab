# 第18章 中断子系统

> 源码锚点：`kernel/irq/irqdesc.c`、`kernel/irq/irqdomain.c`、`kernel/irq/chip.c`、`kernel/irq/manage.c`、`kernel/irq/msi.c`、`kernel/softirq.c`、`kernel/workqueue.c`

中断是CPU响应外部事件的根本机制——从网卡收包到定时器到期，从键盘输入到NVMe完成，一切异步事件都通过中断通知内核。Linux的中断子系统采用分层架构：硬件中断快进快出，延迟处理交给软中断和工作队列。

## 18.1 中断描述符与域

### struct irq_desc：中断描述符

内核为每个中断号维护一个`irq_desc`——中断的"身份证"：

```c
// include/linux/irqdesc.h
struct irq_desc {
    struct irq_common_data  irq_common_data;   // 跨芯片公共数据
    struct irq_data         irq_data;           // 芯片层数据(irq号、hwirq、chip)
    irq_flow_handler_t      handle_irq;         // 高层流控处理函数
    struct irqaction        *action;             // 中断处理动作链表
    unsigned int            depth;               // 禁用嵌套深度
    raw_spinlock_t          lock;                // SMP保护锁
    unsigned long           threads_oneshot;     // oneshot线程位掩码
    atomic_t                threads_active;      // 活跃线程数
    wait_queue_head_t       wait_for_threads;    // 线程同步等待队列
    struct mutex            request_mutex;       // request/free互斥
    // ...
} ____cacheline_internodealigned_in_smp;
```

关键字段解析：
- **`irq_data`**：包含Linux IRQ号、硬件IRQ号(`hwirq`)、`irq_chip`指针、`irq_domain`指针——是中断硬件抽象的核心
- **`handle_irq`**：流控处理函数，决定中断的处理流程（边沿触发/电平触发/快速EOI等）
- **`action`**：中断处理动作链表——共享中断时多个处理函数串在链表上
- **`depth`**：`disable_irq()`嵌套深度——每次disable加1，enable减1，归零时才真正启用

### 中断描述符的索引

`CONFIG_SPARSE_IRQ`配置下，`irq_desc`通过maple tree索引（旧版使用radix tree）：

```c
// kernel/irq/irqdesc.c
static struct maple_tree sparse_irqs = MTREE_INIT_EXT(sparse_irqs,
                    MT_FLAGS_ALLOC_RANGE | MT_FLAGS_LOCK_EXTERN | MT_FLAGS_USE_RCU,
                    sparse_irq_lock);
```

maple tree支持范围查询和RCU安全遍历——适合稀疏IRQ号空间（MSI-X可能产生大量不连续的IRQ号）。`irq_to_desc()`通过maple tree查找对应的`irq_desc`。

### irq_domain：硬件中断号到Linux IRQ的映射

不同中断控制器有各自的硬件中断号空间——ACPI APIC有256个中断，GICv3可能有上千个。`irq_domain`负责将硬件中断号(hwirq)映射到全局的Linux IRQ号：

```c
// include/linux/irqdomain.h
struct irq_domain {
    const char      *name;
    const struct irq_domain_ops *ops;
    void            *host_data;       // 域私有数据
    struct fwnode_handle *fwnode;     // 固件节点(ACPI/DT)
    struct irq_domain *parent;        // 父域(层级域)
    // ...
};

struct irq_domain_ops {
    int  (*map)(struct irq_domain *d, unsigned int virq, irq_hw_number_t hw);
    void (*unmap)(struct irq_domain *d, unsigned int virq);
    int  (*xlate)(struct irq_domain *d, struct device_node *node,
                  const u32 *intspec, unsigned int intsize,
                  unsigned long *out_hwirq, unsigned int *out_type);
    // 层级域操作
    int  (*alloc)(struct irq_domain *d, unsigned int virq, unsigned int nr_irqs, void *arg);
    void (*free)(struct irq_domain *d, unsigned int virq, unsigned int nr_irqs);
    int  (*translate)(struct irq_domain *d, struct irq_fwspec *fwspec,
                      unsigned long *out_hwirq, unsigned int *out_type);
};
```

`xlate`/`translate`将设备树(DT)或ACPI的中断描述翻译为hwirq和触发类型。`map`/`alloc`在映射创建时设置`irq_desc`的chip和handler。

### 层级域(Hierarchical Domain)

现代中断控制器形成层级——例如GIC -> GPIO Controller -> 设备。层级域通过`parent`指针连接，中断分配从叶子域向根域逐层传播：

```
设备中断请求
  → GPIO irq_domain::alloc()   (设置GPIO层的chip/handler)
    → GIC irq_domain::alloc()  (设置GIC层的chip/handler)
      → 分配Linux IRQ号
```

MSI域就是层级域的典型应用——MSI控制器作为PCI域的子域，负责分配MSI向量并配置设备。

## 18.2 中断控制器与处理

### irq_chip：硬件中断控制器抽象

`irq_chip`是中断控制器的操作集——屏蔽、确认、EOI等硬件操作：

```c
// include/linux/irq.h
struct irq_chip {
    const char  *name;
    unsigned int (*irq_startup)(struct irq_data *data);   // 启动中断
    void        (*irq_shutdown)(struct irq_data *data);   // 关闭中断
    void        (*irq_enable)(struct irq_data *data);     // 启用中断
    void        (*irq_disable)(struct irq_data *data);    // 禁用中断
    void        (*irq_ack)(struct irq_data *data);        // 确认中断
    void        (*irq_mask)(struct irq_data *data);       // 屏蔽中断
    void        (*irq_mask_ack)(struct irq_data *data);   // 确认+屏蔽
    void        (*irq_unmask)(struct irq_data *data);     // 取消屏蔽
    void        (*irq_eoi)(struct irq_data *data);        // 中断结束
    int         (*irq_set_affinity)(struct irq_data *data, const struct cpumask *dest, bool force);
    int         (*irq_set_type)(struct irq_data *data, unsigned int flow_type);
    void        (*irq_compose_msi_msg)(struct irq_data *data, struct msi_msg *msg);
    void        (*ipi_send_mask)(struct irq_data *data, const struct cpumask *dest);
    // ...
};
```

x86的IO-APIC chip实现了`mask`/`unmask`/`set_affinity`等操作；ARM GIC chip实现了`eoi`/`set_type`等操作。每个`irq_desc`通过`irq_data.chip`指针关联到具体的`irq_chip`。

### 流控处理函数：边沿触发 vs 电平触发

`handle_irq`决定中断的流控策略——不同触发方式有不同的处理流程：

**边沿触发(`handle_edge_irq`)**：
```c
// kernel/irq/chip.c (简化)
void handle_edge_irq(struct irq_desc *desc)
{
    // 1. 如果中断正在处理中(IRQS_INPROGRESS)，设置PENDING，mask后返回
    //    边沿触发可能丢失中断——必须记录并重放
    // 2. mask_ack中断
    // 3. 调用handle_irq_event()执行action链表
    // 4. 如果有PENDING，清除PENDING，unmask，重新处理
}
```

边沿触发的核心难题：中断线上的脉冲转瞬即逝，处理期间新到达的中断可能丢失。Linux的方案——设置`IRQS_PENDING`标志，处理完后检查并重放。

**电平触发(`handle_level_irq`)**：
```c
// kernel/irq/chip.c (简化)
void handle_level_irq(struct irq_desc *desc)
{
    mask_ack_irq(desc);           // 立即mask+ack，防止中断线持续活跃导致重入
    handle_irq_event(desc);       // 执行action链表
    cond_unmask_irq(desc);        // 条件unmask——oneshot时等线程完成才unmask
}
```

电平触发先mask中断线——因为中断线持续活跃，不mask会立即再次触发。action处理完设备后，中断线回到非活跃状态，此时unmask安全。

**快速EOI(`handle_fasteoi_irq`)**：现代中断控制器(如GIC)在硬件层面管理中断流控，只需要一个`eoi`回调。这是最简单的流控——硬件处理了mask/unmask的复杂性。

### handle_irq_event：执行中断处理动作链

```c
// kernel/irq/handle.c (简化)
irqreturn_t handle_irq_event(struct irq_desc *desc)
{
    desc->istate &= ~IRQS_PENDING;
    irqd_set(&desc->irq_data, IRQD_IRQ_INPROGRESS);
    raw_spin_unlock(&desc->lock);

    ret = handle_irq_event_percpu(desc);    // 遍历action链表，调用每个handler

    raw_spin_lock(&desc->lock);
    irqd_clear(&desc->irq_data, IRQD_IRQ_INPROGRESS);
    return ret;
}
```

关键：调用handler前释放`desc->lock`——handler可能长时间运行，持有自旋锁会阻塞其他CPU的中断处理。`IRQD_IRQ_INPROGRESS`标志防止同一中断在另一个CPU上重入。

## 18.3 中断管理

### request_threaded_irq()：中断注册

```c
// kernel/irq/manage.c
int request_threaded_irq(unsigned int irq, irq_handler_t handler,
                         irq_handler_t thread_fn, unsigned long irqflags,
                         const char *devname, void *dev_id)
```

参数解析：
- **`handler`**：硬中断上下文的快速处理函数，负责检查中断来源并返回`IRQ_WAKE_THREAD`或`IRQ_HANDLED`
- **`thread_fn`**：线程化处理函数，在内核线程中执行，可以睡眠
- **`irqflags`**：`IRQF_SHARED`(共享)、`IRQF_ONESHOT`(oneshot)、`IRQF_TRIGGER_*`(触发类型)等

注册流程(`__setup_irq`)：
1. 分配`irqaction`结构，填入handler/thread_fn/flags
2. 如果需要线程化，创建内核线程`irq/%d-%s`
3. 将action加入`desc->action`链表（共享中断时追加到尾部）
4. 调用`irq_startup()`启用中断线

### 中断线程化(Threaded IRQ)

传统中断处理在硬中断上下文执行——不能睡眠、不能长时间运行。线程化中断将处理分为两层：

```
硬件中断 → handler(硬中断上下文，快速判断) → 返回IRQ_WAKE_THREAD
                                            → 唤醒irq内核线程
                                            → thread_fn(进程上下文，可睡眠)
```

```c
// kernel/irq/manage.c (简化)
static int irq_thread(void *data)
{
    struct irqaction *action = data;

    // 设置实时调度策略SCHED_FIFO
    sched_set_fifo(current);

    while (!irq_wait_for_interrupt(desc, action)) {
        // 等待IRQTF_RUNTHREAD标志被设置
        action_ret = handler_fn(desc, action);
        irq_finalize_oneshot(desc, action);  // oneshot时处理unmask
        wake_threads_waitq(desc);
    }
    return 0;
}
```

线程化中断的优势：
- **可睡眠**：thread_fn可以调用可能睡眠的函数（I2C通信、内存分配等）
- **可抢占**：不会长时间关闭抢占，减少延迟
- **oneshot语义**：`IRQF_ONESHOT`标志下，硬中断handler返回后中断线保持masked，直到thread_fn执行完毕才unmask——避免在thread_fn处理期间中断重入

### 共享中断(Shared IRQ)

PCI设备可能共享中断线——多个设备的`irqaction`串在同一个`desc->action`链表上。handler必须能判断中断是否来自自己的设备——如果返回`IRQ_NONE`，内核继续调用下一个handler。如果所有handler都返回`IRQ_NONE`，内核报告spurious interrupt。

### 强制线程化

`threadirqs`内核启动参数将所有非`IRQF_NO_THREAD`的中断强制线程化——用于调试和实时场景：

```c
// kernel/irq/manage.c
static int __init setup_forced_irqthreads(char *arg)
{
    static_branch_enable(&force_irqthreads_key);
    return 0;
}
early_param("threadirqs", setup_forced_irqthreads);
```

强制线程化时，原有handler被移到secondary action，新的primary handler只返回`IRQ_WAKE_THREAD`。

## 18.4 中断亲和性与均衡

### IRQ亲和性

中断亲和性决定中断由哪个CPU处理——`irq_set_affinity()`将中断绑定到指定CPU集合：

```c
// kernel/irq/manage.c (简化)
int irq_do_set_affinity(struct irq_data *data, const struct cpumask *mask, bool force)
{
    // 1. 过滤掉离线CPU
    cpumask_and(tmp_mask, prog_mask, cpu_online_mask);
    // 2. 调用chip的irq_set_affinity设置硬件路由
    ret = chip->irq_set_affinity(data, tmp_mask, force);
    // 3. 更新desc的亲和性掩码
    cpumask_copy(desc->irq_common_data.affinity, mask);
    // 4. 通知中断线程更新CPU亲和性
    irq_set_thread_affinity(desc);
}
```

x86上通过IO-APIC的重定向表(REDTbl)设置中断路由目标CPU——这是硬件级别的中断亲和性。

### 中断迁移

CPU热插拔时，需要将该CPU上的中断迁移到其他CPU。`CONFIG_GENERIC_PENDING_IRQ`机制实现延迟迁移——设置`IRQD_SETAFFINITY_PENDING`标志，在下一次中断到达时完成迁移：

```
CPU offline → 设置pending affinity → 中断到达时在新CPU上处理 → 清除pending
```

### 数据库视角：NVMe中断与查询线程的CPU亲和性

NVMe多队列将I/O完成中断分散到多个MSI-X向量——每个向量可以绑定到不同CPU。数据库查询线程的CPU亲和性应与NVMe完成队列的亲和性对齐——查询线程在CPU N上提交I/O，完成中断也路由到CPU N，避免跨CPU的cache bouncing。

## 18.5 MSI/MSI-X

### MSI机制

传统PCI共享中断线——多个设备共享一个IRQ，handler需要逐个判断。MSI(Message Signaled Interrupt)通过写入特定地址发出中断——每个MSI向量是独立的中断，无需共享。

MSI-X是MSI的增强版：
- MSI最多32个向量，MSI-X最多2048个
- MSI-X每个向量可以独立屏蔽，MSI只能全局屏蔽
- MSI-X的地址和数据表在设备内存中，软件可编程

### MSI域管理

MSI通过层级`irq_domain`管理——MSI域作为PCI域的子域：

```c
// kernel/irq/msi.c
// MSI域的核心操作：
// 1. 分配MSI向量 → irq_domain_alloc_irqs()
// 2. 编写MSI消息 → irq_chip::irq_compose_msi_msg()
// 3. 写入设备MSI表 → irq_chip::irq_write_msi_msg()
```

NVMe驱动申请多个MSI-X向量时，MSI域为每个向量分配一个Linux IRQ号，配置对应的MSI消息（地址+数据），然后将消息写入NVMe的MSI-X表——每个完成队列对应一个MSI-X向量。

## 18.6 软中断、tasklet与workqueue

### 软中断(Softirq)

硬中断处理必须快进快出——但很多工作不能在中断上下文中完成（如网络协议栈处理）。软中断是硬中断的延迟处理机制：

```c
// include/linux/interrupt.h
enum {
    HI_SOFTIRQ=0,       // 高优先级tasklet
    TIMER_SOFTIRQ,       // 定时器
    NET_TX_SOFTIRQ,      // 网络发送
    NET_RX_SOFTIRQ,      // 网络接收
    BLOCK_SOFTIRQ,       // 块设备完成
    IRQ_POLL_SOFTIRQ,    // IO轮询
    TASKLET_SOFTIRQ,     // 普通tasklet
    SCHED_SOFTIRQ,       // 调度器负载均衡
    HRTIMER_SOFTIRQ,     // 高精度定时器
    RCU_SOFTIRQ,         // RCU回调
    NR_SOFTIRQS
};
```

软中断的核心特征：
- **per-CPU**：每个CPU独立处理自己的软中断，不需要跨CPU同步
- **可重入**：同一个软中断可以在不同CPU上同时执行
- **不可睡眠**：在软中断上下文中不能调用可能睡眠的函数

### 软中断的执行

```c
// kernel/softirq.c (简化)
static void handle_softirqs(bool ksirqd)
{
    pending = local_softirq_pending();  // 获取挂起的软中断位图

restart:
    set_softirq_pending(0);             // 清除挂起位图
    local_irq_enable();

    while ((softirq_bit = ffs(pending))) {
        h += softirq_bit - 1;
        h->action();                    // 执行软中断处理函数
        h++;
        pending >>= softirq_bit;
    }

    local_irq_disable();
    pending = local_softirq_pending();
    if (pending && time_before(jiffies, end) && --max_restart)
        goto restart;                   // 2ms内最多重启10次

    wakeup_softirqd();                  // 超过限制交给ksoftirqd
}
```

软中断执行时机：
1. **`irq_exit()`**：硬中断返回时，如果不在嵌套中断中，立即执行挂起的软中断
2. **`local_bh_enable()`**：启用软中断时检查并执行
3. **`ksoftirqd`**：内核线程，处理积压的软中断——防止软中断独占CPU

ksoftirqd的存在确保公平性——软中断积压过多时交给调度器管理，不会饿死用户态进程。

### raise_softirq()

```c
// kernel/softirq.c
void raise_softirq(unsigned int nr)
{
    local_irq_save(flags);
    raise_softirq_irqoff(nr);
    local_irq_restore(flags);
}

inline void raise_softirq_irqoff(unsigned int nr)
{
    __raise_softirq_irqoff(nr);       // 设置per-CPU位图
    if (!in_interrupt() && should_wake_ksoftirqd())
        wakeup_softirqd();             // 非中断上下文时唤醒ksoftirqd
}
```

在中断上下文中raise_softirq只设置位图——软中断会在`irq_exit()`时执行。在进程上下文中raise_softirq会唤醒ksoftirqd立即处理。

### tasklet：基于软中断的延迟机制

tasklet是软中断的简化接口——同一时刻同一tasklet只在一个CPU上执行（内置串行化）：

```c
// tasklet基于HI_SOFTIRQ和TASKLET_SOFTIRQ实现
// HI_SOFTIRQ优先级最高——用于高优先级tasklet
// TASKLET_SOFTIRQ优先级较低——用于普通tasklet
```

tasklet正在被逐步淘汰——新代码应使用线程化中断或工作队列。

### 工作队列(workqueue)

工作队列是延迟工作的最高层抽象——在进程上下文执行，可以睡眠：

```c
// kernel/workqueue.c
// 标准工作队列
system_wq           // 普通优先级，per-CPU
system_highpri_wq   // 高优先级，per-CPU
system_long_wq      // 长时间运行的工作
system_unbound_wq   // 不绑定CPU
system_freezable_wq // 可冻结(suspend时暂停)
```

CMWQ(Concurrency Managed Workqueue)的核心设计：
- **worker_pool**：每个CPU两个pool(普通和高优先级)，管理一组worker线程
- **动态管理**：pool根据工作负载动态创建和销毁worker——有pending工作但无idle worker时创建新worker
- **并发控制**：`max_active`限制每个CPU上同时执行的工作项数量

```c
// 使用示例
void my_work_handler(struct work_struct *work)
{
    // 进程上下文，可以睡眠
    msleep(100);
    result = do_slow_operation();
}

DECLARE_WORK(my_work, my_work_handler);
schedule_work(&my_work);  // 提交到system_wq
```

### 分层架构的意义

```
硬件中断(硬中断上下文)
  → 快速应答、mask/ack、唤醒线程
  ↓
软中断(软中断上下文，不可睡眠)
  → 网络协议栈、块设备完成等高频操作
  ↓
工作队列(进程上下文，可睡眠)
  → 可睡眠的延迟操作、长时间运行的任务
```

层次越高，灵活性越大，但延迟越高——硬中断微秒级，软中断亚毫秒级，工作队列毫秒级。

## 18.7 IPI与核间中断

IPI(Inter-Processor Interrupt)是CPU之间的中断——一个CPU向另一个CPU发送中断请求：

```c
// kernel/irq/ipi.c
// IPI通过irq_domain管理——每个IPI类型对应一个IRQ
// 核心IPI类型：
// RESCHEDULE    → 目标CPU重新调度
// CALL_FUNCTION → 目标CPU执行函数调用
// TLB_FLUSH     → 目标CPU刷新TLB
```

x86通过ICR(Interrupt Command Register)发送IPI——写入目标APIC ID和向量号。ARM通过GIC的SGI(Software Generated Interrupt)发送IPI。

`smp_call_function()`系列函数利用CALL_FUNCTION IPI——在指定CPU上执行函数，等待完成。RCU的宽限期加速(expedited GP)也使用IPI强制CPU报告静止状态。

## 18.8 源码精读：NVMe中断的完整路径

以NVMe为例，跟踪一个I/O完成中断从硬件到应用的全路径：

```
1. NVMe设备完成I/O → 写入完成队列 → 发出MSI-X中断
2. APIC接收中断 → 确认中断向量 → 通知目标CPU
3. CPU执行中断入口 → 保存上下文 → 调用handle_arch_irq()
4. generic_handle_irq() → handle_fasteoi_irq()  (GIC/APIC使用fasteoi流控)
5. handle_irq_event() → 遍历action链表
6. nvme_irq() handler → 检查完成队列 → 提取完成条目 → 返回IRQ_WAKE_THREAD
7. 唤醒nvme内核线程 → nvme_thread_fn()处理I/O完成
8. raise_softirq(BLOCK_SOFTIRQ) → 软中断执行block处理
9. block softirq → 调用请求的完成回调 → 唤醒等待I/O的进程
```

这个路径覆盖了中断子系统的所有层次：MSI-X向量→irq_desc→flow handler→action handler→线程化处理→软中断→进程唤醒。理解这条路径是理解内核中断处理的钥匙。

> **数据库视角**：NVMe中断亲和性与查询线程的CPU亲和性对齐。数据库的I/O延迟由两部分组成：中断处理延迟和进程唤醒延迟。将NVMe完成队列中断绑定到查询线程所在的CPU，可以减少I/O完成后的cache miss和跨CPU迁移开销。现代数据库(如RocksDB)使用io_uring的SQPOL模式——轮询完成队列而非依赖中断——在I/O QPS极高时进一步降低延迟，但会消耗CPU。选择中断模式还是轮询模式，取决于I/O强度与CPU资源的权衡。

---

本章建立了对Linux中断子系统的完整认知：irq_desc是中断的核心描述符，irq_domain映射硬件中断号到Linux IRQ，irq_chip抽象中断控制器操作，流控函数处理边沿/电平触发的差异，线程化中断允许可睡眠的处理，软中断和工作队列实现分层延迟处理。中断子系统是内核响应外部事件的基础——后续的时间子系统(定时器中断)和信号(软件中断)都建立在此之上。第19章将讨论时间子系统。
