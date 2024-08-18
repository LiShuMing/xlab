# 第6章 进程：抽象、创建与切换

> 源码锚点：`include/linux/sched.h`、`kernel/fork.c`、`kernel/exit.c`、`arch/x86/kernel/process_64.c`、`fs/exec.c`

进程是操作系统最核心的抽象——CPU的执行载体，资源的拥有者，调度的基本单位。Linux中进程和线程的区分比其他Unix更模糊：它们都是`task_struct`，差异仅在于共享程度。本章深入进程的内核表示、创建、切换与退出的完整生命周期。

## 6.1 task_struct：进程的内核画像

### 核心字段精读

`task_struct`是Linux进程的完整描述，定义在`include/linux/sched.h`中，约2200行。它是内核中最大也最重要的数据结构：

```c
// include/linux/sched.h
struct task_struct {
    struct thread_info    thread_info;      // 线程信息（必须第一个！）
    unsigned int          __state;          // 进程状态
    unsigned int          saved_state;      // 保存状态（用于spinlock sleeper）
    void                  *stack;           // 内核栈
    refcount_t            usage;            // 引用计数
    unsigned int          flags;            // PF_*标志
    // ---- 调度相关 ----
    int                   prio;             // 动态优先级
    int                   static_prio;      // 静态优先级
    int                   normal_prio;      // 归一化优先级
    unsigned int          rt_priority;      // 实时优先级
    struct sched_entity   se;               // CFS调度实体
    struct sched_rt_entity rt;              // RT调度实体
    struct sched_dl_entity dl;              // Deadline调度实体
    const struct sched_class *sched_class;  // 调度类
    unsigned int          policy;           // 调度策略
    // ---- 内存相关 ----
    struct mm_struct      *mm;              // 用户地址空间（内核线程为NULL）
    struct mm_struct      *active_mm;       // 活跃地址空间（内核线程借用）
    // ---- 进程关系 ----
    struct task_struct    *real_parent;     // 真实父进程
    struct task_struct    *parent;          // ptrace父进程
    struct list_head      children;         // 子进程链表
    struct list_head      sibling;          // 兄弟进程链表
    struct task_struct    *group_leader;    // 线程组组长
    // ---- 标识 ----
    pid_t                 pid;              // 进程ID
    pid_t                 tgid;             // 线程组ID（=组leader的pid）
    struct nsproxy        *nsproxy;         // 命名空间代理
    // ---- 信号 ----
    struct signal_struct  *signal;          // 信号共享信息
    struct sighand_struct *sighand;         // 信号处理器
    sigset_t              blocked;          // 阻塞信号集
    struct sigpending     pending;          // 私有待处理信号
    // ---- 文件 ----
    struct fs_struct      *fs;              // 文件系统信息(根目录/当前目录)
    struct files_struct   *files;           // 打开文件表
    // ---- 退出 ----
    int                   exit_state;       // 退出状态
    int                   exit_code;        // 退出码
    int                   exit_signal;      // 退出时发给父进程的信号
    // ---- 凭证 ----
    const struct cred     __rcu *real_cred; // 真实凭证
    const struct cred     __rcu *cred;      // 有效凭证
    // ---- cgroup ----
    struct css_set        *cgroups;         // cgroup集合
    // ---- 架构相关 ----
    struct thread_struct  thread;           // 保存寄存器等架构状态
    ...
};
```

### 进程状态

`__state`字段的取值定义了进程的生命周期状态：

| 状态 | 值 | 含义 |
|------|---|------|
| TASK_RUNNING | 0 | 正在运行或等待CPU |
| TASK_INTERRUPTIBLE | 1 | 可中断睡眠——可被信号唤醒 |
| TASK_UNINTERRUPTIBLE | 2 | 不可中断睡眠——只能被事件唤醒 |
| TASK_STOPPED | 4 | 停止——收到SIGSTOP等信号 |
| TASK_TRACED | 8 | 被ptrace跟踪 |
| EXIT_ZOMBIE | 16 | 僵尸——已退出但父进程未wait |
| EXIT_DEAD | 32 | 最终死亡——父进程已wait |

状态转换的核心路径：

```
fork → TASK_RUNNING
  ↓
schedule → TASK_RUNNING (on_rq)
  ↓ 等待事件
TASK_INTERRUPTIBLE / TASK_UNINTERRUPTIBLE
  ↓ 事件发生或信号到达
TASK_RUNNING
  ↓ 调度选中
在CPU上执行
  ↓ exit()
EXIT_ZOMBIE → (父进程wait) → EXIT_DEAD
```

`saved_state`字段用于"spinlock sleeper"场景：当进程在不可中断睡眠中等待spinlock，但被信号唤醒时，`__state`临时设为RUNNING，`saved_state`保存原来的UNINTERRUPTIBLE。获得spinlock后恢复`saved_state`。

### thread_info与内核栈

x86_64上，`thread_info`嵌入在`task_struct`开头（`CONFIG_THREAD_INFO_IN_TASK`），而内核栈是独立分配的。`task_struct->stack`指向内核栈（通常是16KB，即4页）：

```
内核栈布局（x86_64）：
高地址 ┌──────────────────┐
       │ pt_regs (中断帧)  │  ← 进程从用户态进入内核时保存
       │                  │
       ├──────────────────┤
       │                  │
       │  栈增长方向 ↓    │
       │                  │
低地址 └──────────────────┘  ← task_struct->stack
```

栈溢出检测：`set_task_stack_end_magic()`在栈底写入一个魔数(`STACK_END_MAGIC = 0x57AC6E9D`)，内核在关键路径检查这个魔数是否被覆盖。

### PID/TGID与命名空间

Linux区分PID和TGID：
- **PID**：每个`task_struct`有唯一的pid，线程也有自己的pid
- **TGID**：线程组ID，等于线程组leader的pid

从用户态看到的"进程ID"实际上是TGID，"线程ID"是PID。`getpid()`返回TGID，`gettid()`返回PID。

PID命名空间使不同命名空间中的进程看到不同的PID值。同一个进程在父命名空间和子命名空间中有不同的PID。`nsproxy`管理进程所属的所有命名空间。

## 6.2 fork/clone3：进程创建

### 精读 kernel/fork.c

进程创建的核心是`copy_process()`，所有创建方式（fork/clone/vfork/clone3/kernel_thread）最终都调用它：

```c
// kernel/fork.c
__latent_entropy struct task_struct *copy_process(
    struct pid *pid, int trace, int node,
    struct kernel_clone_args *args)
{
    const u64 clone_flags = args->flags;

    // 1. 标志合法性检查
    if ((clone_flags & CLONE_THREAD) && !(clone_flags & CLONE_SIGHAND))
        return ERR_PTR(-EINVAL);
    if ((clone_flags & CLONE_SIGHAND) && !(clone_flags & CLONE_VM))
        return ERR_PTR(-EINVAL);

    // 2. 复制task_struct
    p = dup_task_struct(current, node);
    p->flags &= ~PF_KTHREAD;
    if (args->kthread)
        p->flags |= PF_KTHREAD;
    p->flags |= PF_FORKNOEXEC;

    // 3. 复制凭证
    retval = copy_creds(p, clone_flags);

    // 4. 检查资源限制
    if (is_rlimit_overlimit(task_ucounts(p), UCOUNT_RLIMIT_NPROC, rlimit(RLIMIT_NPROC)))
        goto bad_fork_cleanup_count;
    if (data_race(nr_threads >= max_threads))
        goto bad_fork_cleanup_count;

    // 5. 逐子系统复制
    retval = copy_semundo(clone_flags, p);
    retval = copy_files(clone_flags, p, args->no_files);
    retval = copy_fs(clone_flags, p);
    retval = copy_sighand(clone_flags, p);
    retval = copy_signal(clone_flags, p);
    retval = copy_mm(clone_flags, p);        // 内存地址空间！
    retval = copy_namespaces(clone_flags, p);
    retval = copy_io(clone_flags, p);
    retval = copy_thread(p, args);           // 架构相关！
    ...
}
```

`copy_process()`的clone_flags约束链——这些约束不是随意的，而是反映了资源共享的内在逻辑：

1. **CLONE_THREAD → CLONE_SIGHAND**：线程必须共享信号处理器（否则同一进程中的线程对信号的处理不一致）
2. **CLONE_SIGHAND → CLONE_VM**：共享信号处理器必须共享地址空间（信号处理器的代码和栈在地址空间中）

### COW的精确时机：copy_mm()

`copy_mm()`是fork最关键的步骤——新进程如何获得自己的地址空间：

```c
// kernel/fork.c
static int copy_mm(u64 clone_flags, struct task_struct *tsk)
{
    struct mm_struct *mm, *oldmm;

    oldmm = current->mm;
    if (!oldmm)                    // 内核线程没有mm
        return 0;

    if (clone_flags & CLONE_VM) {  // 线程：共享地址空间
        mmget(oldmm);
        mm = oldmm;
        goto good_mm;
    }

    mm = dup_mm(tsk);              // 进程：复制地址空间
    if (!mm)
        return -ENOMEM;
good_mm:
    tsk->mm = mm;
    tsk->active_mm = mm;
    return 0;
}
```

`CLONE_VM`是进程和线程的分水岭：
- **CLONE_VM设置（线程）**：新旧进程共享同一个`mm_struct`，对地址空间的修改互相可见
- **CLONE_VM未设置（进程）**：调用`dup_mm()`复制地址空间

`dup_mm()`调用`dup_mmap()`复制VMA和页表：

```c
// kernel/fork.c (简化)
static int dup_mmap(struct mm_struct *mm, struct mm_struct *oldmm)
{
    // 遍历父进程的所有VMA
    for (mpnt = oldmm->mmap; mpnt; mpnt = mpnt->vm_next) {
        // 复制VMA结构
        tmp = vm_area_dup(mpnt);
        // 复制页表项——设置写保护！
        copy_page_range(tmp, mpnt);
    }
}
```

**COW的核心**：`copy_page_range()`在复制页表时，将所有可写页的PTE（页表项）设置为只读。当父进程或子进程尝试写入这些页时，触发页面保护异常(Page Fault)，内核此时才真正复制物理页面——这就是"写时复制"(Copy-On-Write)。

COW使得fork()的代价从"复制所有物理页面"降为"复制页表+清写权限"，对于拥有数十GB内存的数据库进程，这差别巨大。

### copy_thread()：架构相关的寄存器设置

`copy_thread()`设置新进程的架构相关状态，使新进程被调度时从正确的位置开始执行：

```c
// arch/x86/kernel/process.c (简化)
int copy_thread(struct task_struct *p, const struct kernel_clone_args *args)
{
    struct thread_struct *tsk = &p->thread;
    struct pt_regs *childregs = task_pt_regs(p);

    if (unlikely(args->fn)) {
        // 内核线程：从kernel_thread_func开始执行
        memset(childregs, 0, sizeof(struct pt_regs));
        childregs->sp = (unsigned long)childregs;
        tsk->io_bitmap = NULL;
        tsk->func = args->fn;
        tsk->arg = args->arg;
    } else {
        // 用户进程：从fork系统调用返回
        *childregs = *current_pt_regs();   // 复制父进程的寄存器
        childregs->ax = 0;                 // 返回值设为0（子进程fork返回0）
        childregs->sp = (unsigned long)args->stack;
        if (args->tls)
            tsk->fsbase = args->tls;
    }
}
```

关键点：子进程的`childregs->ax = 0`——这就是fork()在子进程中返回0的原因。父进程的返回值（子进程的PID）由系统调用机制在父进程的寄存器中设置，子进程则直接从`copy_thread`设置的初始值开始。

### clone3系统调用

`clone3()`是现代Linux创建进程/线程的系统调用，替代了旧的`clone()`/`fork()`/`vfork()`：

```c
// struct kernel_clone_args的关键字段
struct kernel_clone_args {
    u64         flags;          // CLONE_*标志组合
    int         *pidfd;         // 返回pidfd
    int         child_tid;      // 子进程的TID地址
    int         parent_tid;     // 父进程看到的TID
    int         exit_signal;    // 子进程退出时发送的信号
    unsigned long stack;        // 用户栈地址
    unsigned long stack_size;   // 栈大小
    unsigned long tls;          // TLS地址
    ...
};
```

重要的CLONE标志：

| 标志 | 含义 | 共享/隔离 |
|------|------|----------|
| CLONE_VM | 共享地址空间 | 共享 |
| CLONE_FS | 共享文件系统信息 | 共享 |
| CLONE_FILES | 共享文件描述符表 | 共享 |
| CLONE_SIGHAND | 共享信号处理器 | 共享 |
| CLONE_THREAD | 放入同一线程组 | 共享 |
| CLONE_NEWNS | 新mount命名空间 | 隔离 |
| CLONE_NEWPID | 新PID命名空间 | 隔离 |
| CLONE_NEWNET | 新网络命名空间 | 隔离 |
| CLONE_NEWUSER | 新用户命名空间 | 隔离 |

pthread_create()使用`CLONE_VM | CLONE_FS | CLONE_FILES | CLONE_SIGHAND | CLONE_THREAD | CLONE_SYSVSEM`——线程几乎共享一切。

vfork()使用`CLONE_VM | CLONE_VFORK`——子进程借用父进程的地址空间，父进程阻塞直到子进程exec或exit。

> **数据库视角**：连接池进程模型 vs 线程模型 vs 协程的内核成本对比。fork()的COW使得进程创建成本主要在页表复制而非物理内存拷贝，但多进程模型仍比多线程有更高的创建和切换成本。PostgreSQL的每个连接一个进程模型在连接数达到数千时面临挑战——每个进程独立的地址空间意味着无法共享Buffer Pool的页表项，TLB压力更大。MySQL的每连接一线程模型切换更快（共享地址空间），但线程数过多时调度器压力增大。协程模型（如PostgreSQL的异步I/O提案）将并发从内核调度中解放出来，用户态调度器可以在一次内核调度中处理多个I/O操作。

## 6.3 exec：程序替换

### fs/exec.c：从旧mm到新mm

execve()系统调用将当前进程的地址空间替换为新程序的映像——进程还是那个进程（PID不变），但内存内容完全替换：

```c
// fs/exec.c (调用链简化)
// do_execveat_common() → exec_binprm() → load_elf_binary()

static int load_elf_binary(struct linux_binprm *bprm)
{
    // 1. 读取ELF头和程序头表
    // 2. 释放旧地址空间
    // 3. 建立新地址空间（按ELF段映射）
    // 4. 设置入口点
    // 5. 返回用户态，从入口点开始执行
}
```

exec的核心步骤：

1. **分配`linux_binprm`**：保存执行参数（文件路径、argv、envp）
2. **打开可执行文件**：通过`open_exec()`打开ELF文件
3. **验证ELF头**：检查魔数、架构、类型
4. **释放旧地址空间**：`flush_old_exec()` → `exec_mmap()`——分配新的`mm_struct`，释放旧的
5. **建立新映射**：按ELF的`PT_LOAD`段创建VMA，映射代码段、数据段
6. **设置栈**：将argv、envp拷贝到新栈上
7. **设置入口点**：`start_thread()`设置寄存器，使进程从ELF入口开始执行

`exec_mmap()`是地址空间切换的关键——它分配新的`mm_struct`，切换`current->mm`，然后释放旧的`mm_struct`。此时进程的地址空间已经完全改变，但PID、打开的文件描述符（除非设了`FD_CLOEXEC`）、信号处置（重置为默认）等都保持不变。

### start_thread()

```c
// arch/x86/kernel/process_64.c
static void start_thread_common(struct pt_regs *regs, unsigned long new_ip,
                                unsigned long new_sp,
                                u16 _cs, u16 _ss, u16 _ds)
{
    loadsegment(fs, 0);
    loadsegment(es, _ds);
    loadsegment(ds, _ds);
    load_gs_index(0);

    regs->ip  = new_ip;     // ELF入口点(e_entry)
    regs->sp  = new_sp;     // 新栈顶
    regs->csx = _cs;        // __USER_CS
    regs->ssx = _ss;        // __USER_DS
    regs->flags = X86_EFLAGS_IF | X86_EFLAGS_FIXED;
}
```

`start_thread()`设置`pt_regs`使得进程从内核返回用户态时，从ELF入口点开始执行。这是exec与fork的区别——fork的子进程从fork系统调用返回，exec后的进程从新程序的入口开始。

## 6.4 上下文切换

### 精读 arch/x86/kernel/process_64.c

上下文切换发生在`schedule()`选中下一个进程时，核心是保存旧进程的CPU状态、恢复新进程的CPU状态。x86_64上的`__switch_to()`负责架构相关的切换：

```c
// arch/x86/kernel/process_64.c
__switch_to(struct task_struct *prev_p, struct task_struct *next_p)
{
    struct thread_struct *prev = &prev_p->thread;
    struct thread_struct *next = &next_p->thread;
    int cpu = smp_processor_id();

    // 1. FPU状态切换
    switch_fpu(prev_p, cpu);

    // 2. 保存FS/GS段寄存器
    save_fsgs(prev_p);

    // 3. 加载TLS（线程局部存储）
    load_TLS(next, cpu);

    // 4. 加载FS/GS段寄存器
    x86_fsgsbase_load(prev, next);

    // 5. 加载PKRU（保护键权限寄存器）
    x86_pkru_load(prev, next);

    // 6. 切换current指针和栈顶
    raw_cpu_write(current_task, next_p);
    raw_cpu_write(cpu_current_top_of_stack, task_top_of_stack(next_p));

    // 7. 更新内核栈(sp0)
    update_task_stack(next_p);

    // 8. 其他切换（DS/ES段、调试寄存器等）
    switch_to_extra(prev_p, next_p);
}
```

注意`__switch_to()`只处理架构相关的切换。调用者`context_switch()`还负责：
- **`switch_mm_irqs_off()`**：切换地址空间（CR3/页表）
- **寄存器保存/恢复**：由`switch_to`宏通过汇编完成

完整的切换流程：

```c
// kernel/sched/core.c (简化)
static __always_inline struct rq *context_switch(
    struct rq *rq, struct task_struct *prev,
    struct task_struct *next)
{
    // 切换地址空间
    if (!next->mm) {  // 切到内核线程
        enter_lazy_tlb(prev->active_mm, next);
        next->active_mm = prev->active_mm;
    } else {          // 切到用户进程
        switch_mm_irqs_off(prev->active_mm, next->mm, next);
    }

    // 切换寄存器和栈
    switch_to(prev, next, prev);
    // 返回时，当前CPU已经在执行next进程
    // prev现在是"上一个进程"的指针
}
```

### 内核线程的lazy TLB

内核线程没有`mm_struct`（`mm == NULL`），但它需要访问内核空间——内核空间在所有进程的页表中映射相同。当切到内核线程时，不需要切换CR3——直接借用前一个进程的`active_mm`，这就是**lazy TLB**优化：

```c
if (!next->mm) {
    enter_lazy_tlb(prev->active_mm, next);
    next->active_mm = prev->active_mm;
}
```

`enter_lazy_tlb()`告诉TLB刷新机制：这个CPU上的`active_mm`可能被"偷用"，不要在这个CPU上刷新它的TLB。当切回用户进程时，再检查是否需要刷新。

### FS/GS与per-CPU数据

x86_64的GS基址在内核中用于per-CPU数据访问。`current`宏通过GS基址实现：

```
内核态：MSR_GS_BASE → per-CPU区域 → current_task成员 → task_struct指针
用户态：MSR_KERNEL_GS_BASE → 用户态GS基址（TLS等）
```

切换时`save_fsgs()`和`x86_fsgsbase_load()`保存/恢复FS和GS的selector和base。GS的切换比较特殊——内核使用`MSR_GS_BASE`，用户态使用`MSR_KERNEL_GS_BASE`，`swapgs`指令在两者之间交换。

### FPU状态切换

FPU/SSE/AVX寄存器是x86上最宽的寄存器——AVX-512的寄存器状态高达2KB以上。每次上下文切换都保存/恢复这些状态代价很高，所以Linux使用**lazy FPU**策略：

- 切换时只调用`switch_fpu()`标记旧进程的FPU状态为"需要保存"
- 新进程先使用FPU"借用"旧状态
- 当新进程首次使用FPU指令时，触发`#NM`设备不可用异常
- 异常处理器此时才真正保存旧状态、加载新状态

现代CPU使用`XSAVE`/`XRSTOR`指令批量保存/恢复所有扩展状态，Linux在`switch_fpu()`中管理`xsave`区域。

### 上下文切换的开销构成

| 开销项 | 代价 | 说明 |
|--------|------|------|
| 寄存器保存/恢复 | ~50ns | callee-saved寄存器(~10个) |
| CR3切换 | ~100ns | 页表切换+TLB失效 |
| FPU切换 | ~200ns | lazy模式下大部分时候避免 |
| 内核栈切换 | ~20ns | 修改sp0和current_task |
| 调度器决策 | ~200ns | 选择下一个进程 |
| Cache影响 | ~1-10μs | 新进程的working set未在Cache中 |

**Cache影响是最难量化的**——切换后新进程的代码和数据可能不在Cache中，需要从内存重新加载。对于工作集大的数据库进程，这可能占总开销的90%以上。

> **数据库视角**：大量短查询场景下上下文切换对吞吐的影响。每个查询涉及多次上下文切换：客户端→后端进程(网络中断)、查询执行中的I/O等待(自愿切换)、锁争用(非自愿切换)。当QPS达到10万+时，上下文切换开销可能消耗5-10%的CPU时间。减少切换的策略：io_uring减少I/O路径的切换、绑定CPU减少跨核迁移的Cache损失、连接池复用减少进程创建/销毁。

## 6.5 进程退出与资源回收

### 精读 kernel/exit.c

`do_exit()`是进程退出的入口，由系统调用`exit_group()`、致命信号等触发：

```c
// kernel/exit.c
void __noreturn do_exit(long code)
{
    struct task_struct *tsk = current;

    // 1. 内核线程特殊处理
    kthread = tsk_is_kthread(tsk);
    if (unlikely(kthread))
        kthread_do_exit(kthread, code);

    // 2. 设置PF_EXITING——从此进程不会再睡眠
    exit_signals(tsk);  /* sets PF_EXITING */

    // 3. 释放地址空间
    exit_mm();

    // 4. 释放其他资源
    exit_sem(tsk);
    exit_shm(tsk);
    exit_files(tsk);
    exit_fs(tsk);
    exit_nsproxy_namespaces(tsk);
    exit_thread(tsk);

    // 5. cgroup退出
    cgroup_task_exit(tsk);

    // 6. 通知父进程
    exit_notify(tsk, group_dead);

    // 7. 最终调度——永不返回
    preempt_disable();
    do_task_dead();
}
```

`do_exit()`的资源释放顺序有讲究：

**`exit_signals(tsk)`设置`PF_EXITING`**：这必须在其他释放之前。一旦设置了`PF_EXITING`，信号处理代码不会再将信号投递给这个进程，同时`copy_process()`中检查`PF_EXITING`的代码会避免fork竞争。

**`exit_mm()`释放地址空间**：调用`mmput()`递减`mm_struct`的引用计数。如果计数归零，释放所有VMA、页表和物理页面。对于COW页，只有最后一个持有者的`mmput()`才会真正释放物理页。

**`exit_files()`/`exit_fs()`释放文件资源**：递减`files_struct`和`fs_struct`的引用计数。如果其他进程共享（通过CLONE_FILES/CLONE_FS），则只递减计数不释放。

### 僵尸进程与wait

进程退出后不会立即消失——它变成僵尸(ZOMBIE)状态，保留`task_struct`和少量信息（退出码、资源使用统计），等待父进程调用`wait()`/`waitpid()`收集：

```
进程调用exit()
  ↓
EXIT_ZOMBIE：task_struct保留，地址空间已释放
  ↓ 父进程wait()
EXIT_DEAD：task_struct被释放，进程彻底消失
```

僵尸进程不占CPU和内存（除了`task_struct`和内核栈），但如果父进程从不wait，僵尸会累积，最终耗尽PID资源。

`exit_notify()`中，如果父进程已退出，子进程被"领养"到init进程(PID 1)——`forget_original_parent()`将子进程移到init的子进程链表，确保所有僵尸最终都被wait。

如果init进程退出，内核panic——`do_exit()`中有显式检查：

```c
if (unlikely(is_global_init(tsk)))
    panic("Attempted to kill init! exitcode=0x%08x\n",
          tsk->signal->group_exit_code ?: (int)code);
```

### do_task_dead()：最终调度

```c
// kernel/sched/core.c (简化)
void __noreturn do_task_dead(void)
{
    set_special_state(TASK_DEAD);
    // 触发最后一次调度
    __schedule(SM_NONE);
    BUG();  // 不应该到达这里
}
```

进程将状态设为`TASK_DEAD`后调用`__schedule()`。调度器选中下一个进程后，不会将`TASK_DEAD`的进程放回运行队列。当`put_prev_task()`发现前一个进程的状态是`TASK_DEAD`，会释放其`task_struct`引用。

---

本章建立了对进程生命周期的精确认知：`task_struct`是进程的内核画像，`copy_process()`逐子系统复制创建新进程，COW延迟物理页拷贝直到写入发生，`__switch_to()`完成寄存器和地址空间的切换，`do_exit()`逐子系统释放资源并以僵尸状态等待父进程回收。进程是调度的对象——第7章将深入调度器如何在这些进程之间分配CPU时间。
