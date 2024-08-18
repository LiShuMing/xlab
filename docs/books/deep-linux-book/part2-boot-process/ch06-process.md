---
chapter: 6
part: 第二篇 启动与进程 —— 从第一行代码到任务调度
title: 进程：抽象、创建与切换
source_anchor:
  - include/linux/sched.h
  - kernel/fork.c
  - kernel/exit.c
  - arch/x86/kernel/process_64.c
  - kernel/exec_domain.c
  - fs/exec.c
status: done
---

# 第6章 进程：抽象、创建与切换

## 写作目标

深入理解进程在内核中的表示、创建、切换与退出的完整生命周期，建立对"进程就是task_struct"的精确认知。

## 章节大纲

### 6.1 task_struct：进程的内核画像

- **精读** `include/linux/sched.h`：task_struct核心字段
  - 状态字段：TASK_RUNNING/TASK_INTERRUPTIBLE/TASK_UNINTERRUPTIBLE等
  - 调度相关：prio/static_prio/normal_prio/rt_priority
  - 内存描述符：mm_struct指针
  - 文件与信号：files_struct/signal_struct
  - 命名空间：nsproxy
  - cgroup：css_set
- thread_info与内核栈：arm64的thread_info在task_struct中，x86的per-CPU
- 进程标识：PID/TGID/PID namespace

### 6.2 fork/clone3：进程创建

- **精读** `kernel/fork.c`：
  - `copy_process()`：逐子系统的拷贝
  - COW的精确时机：`dup_mmap()`中页表项的写保护设置
  - 文件描述符拷贝：`dup_fd()`
  - 信号处理器拷贝
- clone3系统调用：flags参数的含义
- vfork：与fork的差异——子进程借用父进程的地址空间
- *数据库视角*：连接池进程模型 vs 线程模型 vs 协程的内核成本对比

### 6.3 exec：程序替换

- `fs/exec.c`：`do_execveat_common()`
- ELF加载器：`fs/binfmt_elf.c`
- 从旧mm到新mm的切换
- setuid/setgid与能力(capability)的设置

### 6.4 上下文切换

- **精读** `arch/x86/kernel/process_64.c`：`__switch_to()`
  - 寄存器保存与恢复（callee-saved约定）
  - FPU/AVX状态切换
  - GS基址切换（per-CPU数据与thread_info）
  - TLB切换与PCID
- 上下文切换的开销构成：寄存器/FP/MM/TLB
- *数据库视角*：大量短查询场景下上下文切换对吞吐的影响

### 6.5 进程退出与资源回收

- **精读** `kernel/exit.c`：`do_exit()`
  - 逐子系统资源释放
  - 变为僵尸状态(TASK_DEAD)
  - 父进程通知与wait
- 孤儿进程与init进程领养

## 关键源文件清单

| 文件 | 行数 | 关注点 |
|------|------|--------|
| `include/linux/sched.h` | ~2200 | task_struct定义 |
| `kernel/fork.c` | ~2800 | 进程创建 |
| `kernel/exit.c` | ~900 | 进程退出 |
| `arch/x86/kernel/process_64.c` | ~600 | 上下文切换 |
| `fs/exec.c` | ~1900 | 程序替换 |
| `fs/binfmt_elf.c` | ~1300 | ELF加载 |

## 跨章依赖

- 依赖第1章：理解syscall入口与特权级切换
- 依赖第2章：理解COW的页表操作
- 前置第7章（调度器）：进程是调度的主体
