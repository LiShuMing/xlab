---
chapter: 7
part: 第二篇 启动与进程 —— 从第一行代码到任务调度
title: 调度器：CFS与实时
source_anchor:
  - kernel/sched/fair.c
  - kernel/sched/rt.c
  - kernel/sched/deadline.c
  - kernel/sched/core.c
  - kernel/sched/topology.c
  - kernel/sched/pelt.c
  - kernel/sched/psi.c
  - kernel/sched/sched.h
  - kernel/sched/features.h
status: done
---

# 第7章 调度器：CFS与实时

## 写作目标

深入理解Linux调度器的设计哲学与实现，掌握CFS/实时/Deadline三大策略，理解PELT/PSI等现代调度基础设施。

## 章节大纲

### 7.1 调度器框架

- **精读** `kernel/sched/core.c`：调度器核心
  - `schedule()`函数的主循环
  - `pick_next_task()`：选择下一个任务的策略
  - `enqueue_task()`/`dequeue_task()`：任务入队出队
- `kernel/sched/sched.h`：调度器内部数据结构
  - `struct rq`：运行队列
  - `struct cfs_rq`/`struct rt_rq`/`struct dl_rq`
  - 调度类(sched_class)的优先级链

### 7.2 CFS：完全公平调度器

- **精读** `kernel/sched/fair.c`（14276行）：
  - 设计哲学：理想公平与vruntime
  - 红黑树：按vruntime排序的运行队列
  - 时间片计算：`sched_slice()`
  - 新进程的vruntime初始化：`place_entity()`
  - 睡眠进程的vruntime补偿
  - 组调度(cgroup公平性)
- CFS的调优参数：`sched_latency_ns`/`sched_min_granularity_ns`
- *数据库视角*：长查询与短查询的调度公平性——如何避免长查询饿死短查询

### 7.3 实时调度：RT与Deadline

- **精读** `kernel/sched/rt.c`：
  - SCHED_FIFO与SCHED_RR
  - 实时运行队列：位图+优先级链表
  - 实时带宽限制：rt_runtime/rt_period
- **精读** `kernel/sched/deadline.c`：
  - SCHED_DEADLINE：最早截止时间优先(EDF)
  - 带宽预留模型：runtime/period/deadline
  - CBS(Const Bandwidth Server)：带宽隔离
- *AI视角*：推理服务的SLO保障——Deadline调度的适配潜力

### 7.4 调度域与负载均衡

- **精读** `kernel/sched/topology.c`：
  - 调度域层级：SMT→MC→NUMA→Die
  - SDTL(Scheduling Domain Topology Level)
  - 负载均衡触发时机与算法
- `kernel/sched/fair.c`中负载均衡相关函数
  - `load_balance()`
  - `find_busiest_group()`

### 7.5 PELT与PSI

- PELT(Per-Entity Load Tracking)：**精读** `kernel/sched/pelt.c`
  - 信号衰减与几何级数
  - 从per-task到per-cgroup的负载追踪
  - 利用率(utilization) vs 负载(load)的区别
- PSI(Pressure Stall Information)：**精读** `kernel/sched/psi.c`
  - some/full的语义：至少一个/全部任务阻塞
  - 窗口追踪与聚合
  - *数据库视角*：用PSI诊断查询排队的原因——CPU压力还是内存压力

### 7.6 调度器扩展

- ext_sched_class：`kernel/sched/ext.c`、`kernel/sched/ext.h`
  - BPF可编程调度器
  - idle回调：`kernel/sched/ext_idle.c`
  - *AI视角*：用BPF实现推理任务的定制调度策略

## 关键源文件清单

| 文件 | 行数 | 关注点 |
|------|------|--------|
| `kernel/sched/fair.c` | 14276 | CFS核心 |
| `kernel/sched/core.c` | ~9000 | 调度器框架 |
| `kernel/sched/rt.c` | ~3000 | 实时调度 |
| `kernel/sched/deadline.c` | ~2500 | Deadline调度 |
| `kernel/sched/topology.c` | ~2500 | 调度域 |
| `kernel/sched/pelt.c` | ~400 | PELT追踪 |
| `kernel/sched/psi.c` | ~1000 | 压力追踪 |
| `kernel/sched/ext.c` | ~5000 | BPF可编程调度 |

## 跨章依赖

- 依赖第6章（进程）：进程是调度的对象
- 前置第8章（cgroup）：cgroup是调度公平性的分组机制
