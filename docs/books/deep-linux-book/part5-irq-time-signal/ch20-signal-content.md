# 第20章 信号与异常传递

> 源码锚点：`kernel/signal.c`、`arch/x86/kernel/signal.c`、`fs/coredump.c`、`kernel/ptrace.c`

信号是Linux的"用户态中断"——内核通知进程异步事件的机制。从键盘中断(SIGINT)到非法内存访问(SIGSEGV)，从定时器到期(SIGALRM)到子进程退出(SIGCHLD)，信号贯穿进程生命周期的每一个重要时刻。

## 20.1 信号的内核表示

### sigpending：挂起信号队列

```c
// include/linux/signal_types.h
struct sigpending {
    struct list_head list;       // sigqueue链表
    sigset_t signal;             // 信号位图——哪些信号挂起
};

struct sigqueue {
    struct list_head list;
    int flags;                   // SIGQUEUE_PREALLOC：预分配(POSIX定时器)
    kernel_siginfo_t info;       // 信号详细信息
};
```

每个进程有两套挂起队列：
- **`task_struct->pending`**：发送给特定线程的信号
- **`signal_struct->shared_pending`**：发送给整个线程组的信号（kill发送的信号）

### 标准信号 vs 实时信号

| 特性 | 标准信号(1-31) | 实时信号(32-64) |
|------|---------------|----------------|
| 排队 | 不排队——同信号多次发送只保留一次 | 排队——每次发送都入队 |
| 优先级 | 同步信号(SIGSEGV等)优先 | 按信号值从小到大 |
| 信息量 | 可能丢失siginfo | 保留完整siginfo |
| 编号 | 固定含义(SIGKILL/SIGTERM/...) | 用户自定义 |

标准信号不排队——因为位图只能记录"有/无"。实时信号通过sigqueue链表排队——保证每次发送都能投递。

### sigaction：信号处理器

```c
struct sigaction {
    __sighandler_t sa_handler;    // 处理函数或SIG_IGN/SIG_DFL
    unsigned long sa_flags;       // SA_SIGINFO/SA_RESTART/SA_ONSTACK/...
    sigset_t sa_mask;             // 处理期间屏蔽的信号集
};
```

`sa_flags`关键标志：
- **SA_SIGINFO**：处理函数接收三个参数(handler(int, siginfo_t*, void*))，可获取信号来源等详细信息
- **SA_RESTART**：被信号中断的系统调用自动重启——否则返回EINTR
- **SA_ONSTACK**：在备用信号栈上执行——防止栈溢出时无法处理信号
- **SA_ONESHOT**/SA_RESETHAND：处理一次后恢复为SIG_DFL

## 20.2 信号发送与投递

### __send_signal_locked()：信号发送的核心

```c
// kernel/signal.c (简化)
static int __send_signal_locked(int sig, struct kernel_siginfo *info,
                                struct task_struct *t, enum pid_type type, bool force)
{
    struct sigpending *pending;
    struct sigqueue *q;

    // 1. 选择挂起队列
    pending = (type != PIDTYPE_PID) ? &t->signal->shared_pending : &t->pending;

    // 2. 标准信号不重复入队
    if (legacy_queue(pending, sig))   // sig < SIGRTMIN 且已挂起
        goto out_set;

    // 3. SIGKILL不需要siginfo
    if (sig == SIGKILL)
        goto out_set;

    // 4. 分配sigqueue并入队
    q = sigqueue_alloc(sig, t, GFP_ATOMIC, override_rlimit);
    if (q) {
        list_add_tail(&q->list, &pending->list);
        copy_siginfo(&q->info, info);     // 填充siginfo
    }
    // 如果分配失败：标准信号仍通过位图投递(丢失info)，实时信号返回-EAGAIN

out_set:
    sigaddset(&pending->signal, sig);      // 设置位图
    complete_signal(sig, t, type);         // 唤醒目标线程
}
```

`complete_signal()`决定谁接收信号——对于线程组信号，选择一个没有屏蔽该信号的线程唤醒。它设置`TIF_SIGPENDING`标志，目标线程从内核态返回用户态时会检查此标志。

### 信号投递时机

信号不是立即投递的——它在目标线程从内核态返回用户态时检查并投递：

```c
// kernel/entry/common.c (简化)
static unsigned long __exit_to_user_mode_loop(struct pt_regs *regs, unsigned long ti_work)
{
    while (ti_work & EXIT_TO_USER_MODE_WORK_LOOP) {
        // ...
        if (ti_work & (_TIF_SIGPENDING | _TIF_NOTIFY_SIGNAL))
            arch_do_signal_or_restart(regs);    // 处理信号
        // ...
    }
}
```

这意味着：即使向一个正在内核态执行的线程发送信号，信号也只能在该线程返回用户态时才被处理。这是信号被称为"用户态中断"的原因——它只在用户态/内核态边界投递。

### get_signal()：信号出队与处理决策

```c
// kernel/signal.c (简化)
bool get_signal(struct ksignal *ksig)
{
relock:
    spin_lock_irq(&sighand->siglock);

    for (;;) {
        // 1. 检查进程组退出标志——如果是group exit，直接返回SIGKILL
        if (signal->flags & SIGNAL_GROUP_EXIT) {
            signr = SIGKILL;
            goto fatal;
        }

        // 2. 优先出队同步信号(SIGSEGV/SIGBUS/SIGILL/SIGTRAP/SIGFPE/SIGSYS)
        signr = dequeue_synchronous_signal(&ksig->info);
        if (!signr)
            // 3. 出队普通信号——先检查per-thread，再检查shared
            signr = dequeue_signal(&current->blocked, &ksig->info, &type);

        if (!signr)
            return false;  // 没有挂起信号

        // 4. ptrace拦截（如果进程被跟踪）
        if (current->ptrace && signr != SIGKILL)
            signr = ptrace_signal(signr, &ksig->info, type);

        // 5. 查找sigaction
        ka = &sighand->action[signr-1];
        if (ka->sa.sa_handler == SIG_IGN)
            continue;              // 忽略
        if (ka->sa.sa_handler != SIG_DFL) {
            ksig->ka = *ka;
            break;                 // 用户注册了处理器——返回给arch代码
        }

        // 6. 默认处理
        if (sig_kernel_ignore(signr))  continue;   // 默认忽略(如SIGCHLD)
        if (sig_kernel_stop(signr))    ...          // 默认停止(SIGSTOP/SIGTSTP)
        if (sig_kernel_coredump(signr)) vfs_coredump(&ksig->info);  // core dump
        do_group_exit(signr);         // 终止进程
    }

fatal:
    spin_unlock_irq(&sighand->siglock);
    do_group_exit(signr);
}
```

同步信号优先出队——确保SIGSEGV等信号的栈帧中指令指针指向引发异常的指令，而非被其他信号的处理延迟。

### 信号屏蔽

进程通过`sigprocmask()`屏蔽信号——被屏蔽的信号不会投递，但仍然挂起：

```c
// dequeue_signal()只出队不在blocked掩码中的信号
signr = __dequeue_signal(&tsk->pending, mask, info);
if (!signr)
    signr = __dequeue_signal(&tsk->signal->shared_pending, mask, info);
```

SIGKILL和SIGSTOP不能被屏蔽——内核在`next_signal()`中不检查这两个信号的屏蔽位。

## 20.3 信号处理器的执行

### 信号栈帧的构建

x86上信号投递的核心是`setup_rt_frame()`——在用户态栈上构建一个栈帧，让CPU"假装"调用了信号处理函数：

```c
// arch/x86/kernel/signal.c (简化)
static void handle_signal(struct ksignal *ksig, struct pt_regs *regs)
{
    // 1. 处理被中断的系统调用
    if (syscall_get_nr(current, regs) != -1) {
        switch (syscall_get_error(current, regs)) {
        case -ERESTARTNOHAND:
            regs->ax = -EINTR;         // 不重启，返回EINTR
            break;
        case -ERESTARTSYS:
            if (!(ksig->ka.sa.sa_flags & SA_RESTART))
                regs->ax = -EINTR;     // SA_RESTART未设置，不重启
            else
                regs->ip -= 2;         // 重启系统调用
            break;
        case -ERESTARTNOINTR:
            regs->ip -= 2;             // 无条件重启
            break;
        }
    }

    // 2. 在用户态栈上构建栈帧
    failed = (setup_rt_frame(ksig, regs) < 0);
}
```

x64的`setup_rt_frame`在用户态栈上放置：
1. **siginfo_t**：信号详细信息
2. **ucontext_t**：被中断的寄存器状态(pt_regs)
3. **返回地址**：指向`__restore_rt`（sigreturn的蹦床代码）

然后修改pt_regs，让返回用户态时跳转到信号处理函数——CPU"以为"自己调用了handler(sig, &info, &context)。

### sigreturn：恢复原始上下文

信号处理函数返回时，执行`__restore_rt`蹦床代码——调用`rt_sigreturn`系统调用。内核从用户态栈上的ucontext_t恢复原始寄存器状态，进程从被信号中断的位置继续执行。

```
正常执行 → 信号到达 → 内核构建栈帧 → 跳转到handler
                                    → handler返回 → __restore_rt
                                    → rt_sigreturn → 恢复pt_regs
                                    → 继续正常执行
```

整个过程对用户态透明——信号处理看起来就像一个异步的函数调用。

### 不可中断的信号

SIGKILL和SIGSTOP不可屏蔽、不可捕获、不可忽略——内核在`get_signal()`中直接处理，不经过sigaction。这确保了root总能终止失控的进程。

### 信号与中断的对比

信号被称为"用户态中断"——它与硬件中断有深刻的类比：

| 特性 | 硬件中断 | 信号 |
|------|---------|------|
| 触发 | 硬件设备 | 内核/进程 |
| 投递时机 | 指令边界 | 内核态→用户态边界 |
| 上下文 | 中断上下文(不可睡眠) | 用户态上下文(可睡眠) |
| 屏蔽 | local_irq_disable | sigprocmask |
| 处理函数 | irqaction.handler | sigaction.sa_handler |

## 20.4 ptrace与进程跟踪

### ptrace机制

ptrace是Linux进程跟踪的内核基础设施——strace、gdb都依赖它：

```c
// kernel/ptrace.c
// 核心操作：
// PTRACE_ATTACH    → 附加到目标进程，目标进程成为tracee
// PTRACE_TRACEME   → 进程主动让父进程跟踪
// PTRACE_CONT      → 继续执行
// PTRACE_SINGLESTEP → 单步执行(设置TF标志)
// PTRACE_PEEKTEXT/POKETEXT → 读写目标进程内存
// PTRACE_GETREGS/SETREGS → 读写目标进程寄存器
```

### 信号注入与拦截

ptrace最强大的能力是拦截和修改信号：

```c
// kernel/signal.c (简化)
// get_signal()中：
if (current->ptrace && signr != SIGKILL)
    signr = ptrace_signal(signr, &ksig->info, type);
```

`ptrace_signal()`将信号通知给tracer——tracer可以：
- **忽略信号**：返回0，信号被丢弃
- **传递信号**：返回原信号，正常投递
- **替换信号**：返回不同信号号
- **注入信号**：通过PTRACE_CONT传递新信号

gdb的断点实现：在断点地址写入`int3`指令(0xCC)→CPU执行到此处触发SIGTRAP→ptrace拦截SIGTRAP→gdb通知用户→用户继续时恢复原始指令并设置TF单步执行一条指令→再次SIGTRAP→恢复断点指令。

## 20.5 coredump机制

### core_pattern的处理

进程收到致命信号(SIGSEGV/SIGABRT等)时，内核生成core dump——进程内存映像的快照，用于事后调试：

```c
// fs/coredump.c
void vfs_coredump(const kernel_siginfo_t *siginfo)
{
    // 1. 等待所有线程停止
    if (coredump_wait(siginfo->si_signo, &core_state) < 0)
        return;

    // 2. 解析core_pattern
    do_coredump(&cn, &cprm, &argv, &argc, binfmt);
}
```

core_pattern支持多种输出方式：
- **文件模式**：`/tmp/core.%p`——直接写入文件
- **管道模式**：`|/usr/bin/core_handler`——通过管道发送给用户态程序
- **套接字模式**：将core dump发送到网络套接字

管道模式是最灵活的——用户态程序可以压缩、上传、分析core dump。`core_pipe_limit`限制同时运行的core dump处理程序数量——防止fork bomb。

### ELF core文件的生成

ELF core文件本质是一个ELF文件——包含进程内存段的映像和元数据：

```
ELF Header
Program Headers:
  - NOTE段：prstatus(寄存器)、prpsinfo(进程信息)、auxv(辅助向量)
  - LOAD段：每个内存映射对应一个LOAD段
内存段数据
```

生成core dump时，内核遍历进程的VMA——每个VMA生成一个LOAD段，通过`dump_emit()`写入数据。大页面和特殊映射(如vdso)有特殊的dump策略。

### 数据库视角：进程crash后的core分析

数据库进程crash后，core dump是诊断的根本——SIGSEGV可能是内存越界、double-free或并发bug导致。core文件中的寄存器状态指向crash指令，backtrace显示调用链，内存映像可以检查变量值。现代数据库(如PostgreSQL)在信号处理器中主动生成诊断日志——在core dump之前输出最近的事务状态和锁信息，加速问题定位。

> **运维视角**：生产环境应确保core dump可用——`ulimit -c unlimited`解除core文件大小限制，`core_pattern`配置管道模式自动压缩和归档。大内存进程(如数据库)的core dump可能数十GB——管道模式压缩后通常可减小80%以上。`/proc/sys/kernel/core_pattern`的设置应在系统启动脚本中配置，而非依赖默认值。

---

本章建立了对信号机制的完整认知：sigpending组织挂起信号，__send_signal完成信号入队，get_signal在返回用户态时出队并决策处理方式，setup_rt_frame构建用户态栈帧让信号处理函数透明执行，ptrace拦截和修改信号实现调试，coredump在进程crash时保存内存映像。信号是用户态与内核交互的异步通道——理解信号的投递时机和处理流程，是理解进程行为和调试问题的基础。第五篇到此结束，从中断到时间到信号，构成了对内核异步事件处理的完整认知。
