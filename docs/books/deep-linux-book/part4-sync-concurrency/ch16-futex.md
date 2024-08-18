---
chapter: 16
part: 第四篇 同步与并发 —— 多核的正确性保障
title: futex与用户态同步
source_anchor:
  - kernel/futex/core.c
  - kernel/futex/pi.c
  - kernel/futex/requeue.c
  - kernel/futex/syscalls.c
  - kernel/futex/waitwake.c
  - kernel/futex/futex.h
status: done
---

# 第16章 futex与用户态同步

## 写作目标

深入理解futex的内核实现，掌握从用户态快速路径到内核回退的完整机制，理解PI futex和requeue优化。

## 章节大纲

### 16.1 futex的设计哲学

- 用户态同步的困境：spin(浪费CPU) vs syscall(开销大)
- futex的核心思想：用户态快速路径 + 内核回退
- futex的三个操作：wait/wake/requeue

### 16.2 futex核心实现

- **精读** `kernel/futex/core.c`：
  - futex的哈希表：按uaddr查找等待队列
  - `futex_wait_queue()`：加入等待队列
  - `futex_wake_mark()`：唤醒等待者
  - futex_key：区分不同地址空间的futex
- `kernel/futex/futex.h`：内部接口

### 16.3 wait与wake

- **精读** `kernel/futex/waitwake.c`：
  - `futex_wait()`：原子检查+条件等待
  - `futex_wake()`：唤醒指定数量的等待者
  - 批量唤醒的优化

### 16.4 PI futex：优先级继承

- **精读** `kernel/futex/pi.c`：
  - 优先级继承：解决futex的优先级反转
  - `futex_lock_pi()`/`futex_unlock_pi()`
  - 与rtmutex的关系：PI futex底层使用rtmutex
- *实时系统视角*：PI futex对实时应用的保障

### 16.5 requeue：条件变量优化

- **精读** `kernel/futex/requeue.c`：
  - `futex_requeue()`：从一个futex移到另一个
  - 条件变量广播的优化：避免thundering herd
  - cmp_requeue_pi：带PI的requeue

### 16.6 futex系统调用接口

- **精读** `kernel/futex/syscalls.c`：
  - `futex()`系统调用的op分发
  - FUTEX_WAIT/FUTEX_WAKE/FUTEX_REQUEUE/FUTEX_CMP_REQUEUE
  - FUTEX_LOCK_PI/FUTEX_UNLOCK_PI
  - FUTEX_WAIT_BITSET/FUTEX_WAKE_BITSET

### 16.7 *数据库视角*：futex与条件变量

- pthread_mutex/pthread_cond底层对futex的使用
- 数据库锁管理器中的条件等待与futex的映射
- 批量唤醒优化在数据库唤醒场景的应用

## 关键源文件清单

| 文件 | 行数 | 关注点 |
|------|------|--------|
| `kernel/futex/core.c` | ~1000 | futex核心 |
| `kernel/futex/waitwake.c` | ~600 | wait/wake实现 |
| `kernel/futex/pi.c` | ~800 | PI futex |
| `kernel/futex/requeue.c` | ~500 | requeue优化 |
| `kernel/futex/syscalls.c` | ~400 | 系统调用接口 |

## 跨章依赖

- 依赖第14章（rtmutex）：PI futex底层使用rtmutex
- 依赖第6章（进程）：wait/wake与进程状态转换
