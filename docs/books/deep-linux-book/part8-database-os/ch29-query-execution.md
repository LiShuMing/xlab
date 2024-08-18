---
chapter: 29
part: 第八篇 数据库与OS的深度对话
title: 查询执行的硬件适配
source_anchor:
  - mm/mempolicy.c
  - mm/numa.c
  - kernel/sched/topology.c
  - arch/x86/mm/
  - kernel/bpf/trampoline.c
  - include/linux/cache.h
status: done
---

# 第29章 查询执行的硬件适配

## 写作目标

用硬件与内核原理指导查询执行引擎的优化，实现查询算子与CPU/内存层次的精确适配。

## 章节大纲

### 29.1 向量化执行与Cache Line对齐

- 向量化执行的本质：一次处理一组数据，充分利用CPU流水线
- Cache Line(64字节)对齐：`__cacheline_aligned`的实际效果
  - 列式存储的列对齐与Cache Line的关系
  - 向量宽度选择：与CPU向量寄存器宽度匹配
- prefetch策略：`__builtin_prefetch`在Hash Join/Sort中的应用
  - 何时prefetch、prefetch距离的调优
- *源码关联*：`include/linux/cache.h`

### 29.2 Hash Join/Sort的内存访问模式

- Hash Join的访问模式：构建阶段(顺序写)→探测阶段(随机读)
  - Hash表的Cache友好的设计：开地址法 vs 链地址法
  - Bucket的预取策略
- Sort的访问模式：归并排序的顺序访问 vs 快排的随机访问
- *内核对比*：`mm/page_alloc.c`中伙伴系统的per-cpu pageset——减少跨CPU缓存行访问

### 29.3 JIT编译执行与分支预测

- JIT(Just-In-Time)编译：将查询计划编译为原生代码
- 分支预测优化：消除难以预测的条件分支
- *源码关联*：`kernel/bpf/trampoline.c`——内核中的JIT实践
  - BPF JIT的代码生成策略
  - 从BPF JIT学查询JIT的优化技巧

### 29.4 NUMA感知的数据分区与调度

- **精读** `mm/mempolicy.c`：
  - MPOL_BIND/MPOL_PREFERRED/MPOL_INTERLEAVE
  - set_mempolicy/get_mempolicy系统调用
- **精读** `mm/numa.c`：
  - NUMA页面迁移：`migrate_pages()`
  - 自动NUMA平衡：`task_numa_work()`
- 查询执行的NUMA感知策略：
  - Partition按NUMA节点分布
  - Worker线程的CPU亲和性绑定
  - 内存分配的节点亲和性
- *源码关联*：`kernel/sched/topology.c`——调度域与NUMA拓扑

### 29.5 并行查询与内核调度

- 并行查询的Worker线程管理
- Worker与CFS的交互：如何避免Worker被不公正调度
- cgroup在并行查询资源隔离中的应用
- *源码关联*：`kernel/sched/fair.c`——CFS组调度保障查询组的公平性

## 关键源文件清单

| 文件 | 行数 | 关注点 |
|------|------|--------|
| `mm/mempolicy.c` | ~2500 | NUMA内存策略 |
| `mm/numa.c` | ~1500 | NUMA平衡与迁移 |
| `kernel/bpf/trampoline.c` | ~1500 | JIT实践参考 |

## 跨章依赖

- 依赖第2章（Cache/TLB/NUMA）：硬件动机
- 依赖第7章（调度器）：CFS与并行查询
- 依赖第25章（eBPF JIT）：JIT技术参考
