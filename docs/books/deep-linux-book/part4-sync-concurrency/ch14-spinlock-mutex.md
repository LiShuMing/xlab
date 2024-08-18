---
chapter: 14
part: 第四篇 同步与并发 —— 多核的正确性保障
title: 自旋锁与互斥锁
source_anchor:
  - kernel/locking/qspinlock.c
  - kernel/locking/qspinlock.h
  - kernel/locking/mutex.c
  - kernel/locking/rtmutex.c
  - kernel/locking/rwsem.c
  - kernel/locking/percpu-rwsem.c
  - kernel/locking/osq_lock.c
  - kernel/locking/ww_mutex.h
  - kernel/locking/mcs_spinlock.h
status: done
---

# 第14章 自旋锁与互斥锁

## 写作目标

深入理解Linux内核锁的实现，从MCS锁到qspinlock、从mutex到rtmutex，掌握多核同步的内核基础设施。

## 章节大纲

### 14.1 自旋锁：从Ticket Lock到qspinlock

- 自旋锁的语义：忙等、不可睡眠
- **精读** `kernel/locking/mcs_spinlock.h`：MCS锁原理
  - 每个CPU一个节点，形成等待队列
  - 避免总线风暴(bus spin)
- **精读** `kernel/locking/qspinlock.c`/`kernel/locking/qspinlock.h`：
  - 四级队列：locked/pending/编码队列
  - 原子操作与cmpxchg的精巧配合
  - PV(ParaVirtual)优化：`qspinlock_paravirt.h`——虚拟化场景减少自旋
  - 统计：`qspinlock_stat.h`
- `kernel/locking/spinlock.c`/`kernel/locking/spinlock_debug.c`

### 14.2 mutex：乐观自旋的互斥锁

- **精读** `kernel/locking/mutex.c`：
  - 三态：unlocked/locked/no waiters → locked/waiters
  - 乐观自旋(optimistic spinning)：持锁者在运行则自旋等待
  - MCS锁用于排队：`osq_lock.c`——乐观自旋的排队机制
  - 等待队列：waiter链表
  - 手工抢锁：ww_mutex(`ww_mutex.h`)——避免死锁的迭代模式
- `kernel/locking/mutex-debug.c`

### 14.3 rtmutex：优先级继承互斥锁

- **精读** `kernel/locking/rtmutex.c`：
  - 优先级继承(PI)：解决优先级反转
  - 红黑树组织等待者
  - 死锁检测
- `kernel/locking/rtmutex_api.c`：RT mutex API
- `kernel/locking/ww_rt_mutex.c`：ww_mutex的rt_mutex后端

### 14.4 读写信号量

- **精读** `kernel/locking/rwsem.c`：
  - 读者并发、写者独占
  - 乐观自旋与等待队列
  - 读者偏爱 vs 写者偏爱
- `kernel/locking/percpu-rwsem.c`：per-CPU读写信号量
  - 读路径零开销（per-CPU计数）
  - 写路径等待所有CPU切换
- `kernel/locking/qrwlock.c`：队列读写锁

### 14.5 其他同步原语

- `kernel/locking/semaphore.c`：计数信号量
- `kernel/locking/completion.c`：完成量
- `kernel/sched/wait.c`/`kernel/sched/wait_bit.c`：等待队列

## 关键源文件清单

| 文件 | 行数 | 关注点 |
|------|------|--------|
| `kernel/locking/qspinlock.c` | ~400 | qspinlock核心 |
| `kernel/locking/mutex.c` | ~700 | mutex核心 |
| `kernel/locking/rtmutex.c` | ~1200 | PI mutex |
| `kernel/locking/rwsem.c` | ~800 | 读写信号量 |
| `kernel/locking/osq_lock.c` | ~200 | 乐观自旋队列 |

## 跨章依赖

- 依赖第1章（x86）：原子操作与LOCK前缀
- 前置第15章（RCU）：读写信号量 vs RCU的读写模式对比
