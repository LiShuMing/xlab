---
chapter: 30
part: 第八篇 数据库与OS的深度对话
title: 并发控制与内核同步的映射
source_anchor:
  - kernel/locking/mcs_spinlock.h
  - kernel/locking/qspinlock.c
  - kernel/rcu/
  - kernel/futex/
  - kernel/locking/rwsem.c
status: done
---

# 第30章 并发控制与内核同步的映射

## 写作目标

将数据库并发控制机制与内核同步原语进行映射，理解两者设计思想的共鸣与差异。

## 章节大纲

### 30.1 乐观并发控制与RCU

- 数据库OCC(Optimistic Concurrency Control)：
  - 读不加锁、写时验证
  - 冲突检测与回滚
- 内核RCU：
  - 读不加锁、写时延迟回收
  - 宽限期保证所有读者离开
- 思想共鸣：
  - 读多写一场景的最优策略
  - 避免读端同步开销
  - 代价在写端
- MVCC与RCU的类比：
  - 旧版本保留 vs 延迟回收
  - 快照可见性判断 vs 宽限期

### 30.2 Latch耦合与读写信号量

- 数据库中的latch：短持锁，保护内存结构
  - Buffer Pool的hash table latch
  - B+树遍历的latch coupling
- 内核读写信号量：`kernel/locking/rwsem.c`
  - 读者并发、写者独占
  - 乐观自旋
- 映射：
  - latch ≈ 内核的rwsem
  - latch coupling ≈ RCU的读端无锁遍历

### 30.3 事务锁管理器与futex

- 数据库事务锁：长持锁，保护逻辑一致性
  - 行锁/表锁/意向锁
  - 等待队列与死锁检测
- 内核futex：`kernel/futex/`
  - 用户态快速路径 + 内核等待队列
  - PI futex解决优先级反转
- 映射：
  - 事务锁的等待/唤醒 ≈ futex的wait/wake
  - 死锁检测 ≈ lockdep
  - 锁升级 ≈ futex requeue

### 30.4 无锁数据结构在引擎中的实践

- 从`kernel/locking/mcs_spinlock.h`学MCS锁
  - 公平排队、避免总线风暴
- 无锁队列：内核的`include/linux/llist.h`
  - 单生产者单消费者的无锁设计
- 原子操作的正确使用：
  - `READ_ONCE/WRITE_ONCE` vs `atomic_t`
  - 内存序的选择
- *数据库视角*：无锁B+树的挑战与进展

## 关键源文件清单

| 文件 | 关注点 |
|------|--------|
| `kernel/locking/mcs_spinlock.h` | MCS锁原理 |
| `kernel/locking/rwsem.c` | 读写信号量 |
| `kernel/futex/core.c` | futex等待队列 |
| `kernel/locking/lockdep.c` | 死锁检测 |

## 跨章依赖

- 综合运用第四篇（同步与并发）全部内容
