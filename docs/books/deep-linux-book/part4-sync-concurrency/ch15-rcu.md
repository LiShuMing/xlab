---
chapter: 15
part: 第四篇 同步与并发 —— 多核的正确性保障
title: RCU：读多写一的无等待同步
source_anchor:
  - kernel/rcu/tree.c
  - kernel/rcu/tree.h
  - kernel/rcu/tree_plugin.h
  - kernel/rcu/tree_nocb.h
  - kernel/rcu/tree_exp.h
  - kernel/rcu/tree_stall.h
  - kernel/rcu/srcutree.c
  - kernel/rcu/tiny.c
  - kernel/rcu/update.c
  - kernel/rcu/sync.c
status: done
---

# 第15章 RCU：读多写一的无等待同步

## 写作目标

深入理解RCU的设计哲学与内核实现，掌握RCU宽限期、回调、NOCB等核心机制，理解RCU思想在数据库并发控制中的映射。

## 章节大纲

### 15.1 RCU的设计哲学

- 读写问题的本质：读不阻塞写、写不阻塞读
- RCU的核心思想：
  - 读端无开销（无锁、无原子操作）
  - 写端延迟回收（等待所有读者离开）
  - 宽限期(Grace Period)的语义
- RCU vs 读写锁 vs 序列锁的性能对比

### 15.2 Tree RCU：可扩展的RCU实现

- **精读** `kernel/rcu/tree.c`/`kernel/rcu/tree.h`：
  - rcu_node树的层级组织——适应大规模CPU
  - 宽限期的启动与推进：`rcu_gp_kthread()`
  - CPU的静止状态(quiescent state)报告
  - `rcu_read_lock()`/`rcu_read_unlock()`的实现
  - `synchronize_rcu()`的等待机制
  - `call_rcu()`的回调注册与执行
- **精读** `kernel/rcu/tree_plugin.h`：
  - 可抢占RCU的增强
  - 加速宽限期(expedited GP)

### 15.3 宽限期加速与NOCB

- **精读** `kernel/rcu/tree_exp.h`：
  - expedited宽限期：主动IPI驱动的快速等待
  - 与正常宽限期的对比
- **精读** `kernel/rcu/tree_nocb.h`：
  - NOCB(No Callback)：卸载回调到per-CPU kthread
  - 减少软中断上下文的回调执行
  - 适用于实时场景

### 15.4 SRCU：可睡眠的RCU

- **精读** `kernel/rcu/srcutree.c`：
  - `srcu_read_lock()`/`srcu_read_unlock()`可睡眠
  - 每个srcu_struct独立的宽限期
  - 与Tree RCU的区别

### 15.5 RCU stall检测

- **精读** `kernel/rcu/tree_stall.h`：
  - 宽限期超时检测
  - stall警告的输出格式与诊断
  - 常见stall原因分析

### 15.6 小型RCU与工具

- `kernel/rcu/tiny.c`：单CPU/小系统的简化RCU
- `kernel/rcu/update.c`：RCU更新基础设施
- `kernel/rcu/sync.c`：RCU同步原语
- `kernel/rcu/rcuscale.c`：RCU可扩展性测试
- `kernel/rcu/refscale.c`：RCU读端性能基准

### 15.7 *数据库视角*：RCU与乐观并发控制

- RCU的思想与OCC(Optimistic Concurrency Control)的共鸣：
  - 读不阻塞写 → 乐观读不加锁
  - 延迟回收 → MVCC的旧版本保留
  - 宽限期 → 快照隔离的可见性判断
- 引擎中的latch耦合与RCU的类比

## 关键源文件清单

| 文件 | 行数 | 关注点 |
|------|------|--------|
| `kernel/rcu/tree.c` | ~4000 | Tree RCU核心 |
| `kernel/rcu/tree_nocb.h` | ~1500 | NOCB卸载 |
| `kernel/rcu/tree_exp.h` | ~800 | 加速宽限期 |
| `kernel/rcu/srcutree.c` | ~800 | SRCU实现 |
| `kernel/rcu/tree_stall.h` | ~600 | stall检测 |

## 跨章依赖

- 依赖第14章（自旋锁与互斥锁）：RCU是读写模式的替代方案
- 前置第16章（futex）：用户态同步的内核支撑
