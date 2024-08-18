---
chapter: 20
part: 第五篇 中断、时间与信号 —— 异步事件的内核处理
title: 信号与异常传递
source_anchor:
  - kernel/signal.c
  - fs/coredump.c
  - kernel/ptrace.c
  - arch/x86/kernel/signal.c
status: done
---

# 第20章 信号与异常传递

## 写作目标

理解Linux信号机制的内核实现，从信号发送到投递到处理的完整链路，以及coredump机制。

## 章节大纲

### 20.1 信号的内核表示

- `struct sigpending`：挂起信号队列
- `struct sigaction`：信号处理器
- 信号位图与实时信号队列
- 信号的分类：标准信号(1-31) vs 实时信号(32-64)

### 20.2 信号发送与投递

- **精读** `kernel/signal.c`：
  - `send_signal()`：信号发送的核心
  - `do_send_sig_info()`→`__send_signal()`
  - 信号投递时机：从内核态返回用户态时检查
  - `get_signal()`：信号出队与处理决策
  - 信号屏蔽与字操作

### 20.3 信号处理器的执行

- 信号栈帧的构建：`arch/x86/kernel/signal.c`
  - `setup_rt_frame()`：构建用户态栈帧
  - sigreturn系统调用：恢复原始上下文
- 不可中断的信号：SIGKILL/SIGSTOP
- 信号与中断的交互：信号是"用户态中断"

### 20.4 ptrace与进程跟踪

- `kernel/ptrace.c`：进程跟踪机制
  - 断点与单步执行
  - 信号注入与拦截
  - strace/gdb的内核支撑

### 20.5 coredump机制

- **精读** `fs/coredump.c`：
  - core_pattern的处理
  - ELF core文件的生成
  - pipe core pattern：将coredump导入程序处理
  - *运维视角*：数据库进程crash后的core分析

## 关键源文件清单

| 文件 | 行数 | 关注点 |
|------|------|--------|
| `kernel/signal.c` | ~4000 | 信号核心 |
| `fs/coredump.c` | ~800 | coredump |
| `kernel/ptrace.c` | ~1200 | 进程跟踪 |

## 跨章依赖

- 依赖第6章（进程）：信号投递到进程
- 依赖第1章（x86入口）：信号栈帧与用户态/内核态切换
