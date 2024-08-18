---
chapter: 8
part: 第二篇 启动与进程 —— 从第一行代码到任务调度
title: cgroup v2：资源隔离的内核实现
source_anchor:
  - kernel/cgroup/cgroup.c
  - kernel/cgroup/cgroup-internal.h
  - kernel/cgroup/cpuset.c
  - kernel/cgroup/dmem.c
  - kernel/cgroup/freezer.c
  - kernel/cgroup/pids.c
  - kernel/cgroup/rstat.c
  - mm/memcontrol.c
status: done
---

# 第8章 cgroup v2：资源隔离的内核实现

## 写作目标

深入理解cgroup v2的内核实现，掌握CPU/内存/设备内存的隔离机制，理解容器资源隔离的内核支撑。

## 章节大纲

### 8.1 cgroup核心机制

- **精读** `kernel/cgroup/cgroup.c`：
  - 层级(hierarchy)与委派(delegation)
  - cgroup文件系统接口
  - 进程迁移与资源统计
- cgroup v1 vs v2的关键差异
  - 统一层级 vs 多层级
  - 委派模型
- `kernel/cgroup/rstat.c`：递归统计(rstat)——高效聚合层级数据

### 8.2 CPU控制器

- cpu.max与cpu.weight的内核语义
- CFS组调度：cpu.cfs_quota_us/cpu.cfs_period_us
- cpu.stat中的throttle时间统计
- cpu.pressure与PSI的关联
- *AI视角*：推理服务的SLO保障——cgroup CPU限流与延迟抖动

### 8.3 内存控制器

- **精读** `mm/memcontrol.c`：
  - memory.current/memory.low/memory.max/memory.high
  - 页面计数与电荷(charge)机制
  - 内存回收触发：high→reclaim, max→OOM
  - v1 vs v2的差异：`mm/memcontrol-v1.c`
- swap与内存控制的交互
- *数据库视角*：如何防止Buffer Pool被cgroup OOM杀掉

### 8.4 cpuset与NUMA绑定

- **精读** `kernel/cgroup/cpuset.c`：
  - cpuset.cpus/cpuset.mems
  - 有效掩码的计算：parent→child约束传播
  - `cpuset-v1.c`：v1兼容层
- NUMA绑定的容器实践

### 8.5 设备内存控制器

- **精读** `kernel/cgroup/dmem.c`：
  - 设备内存(GPU/NPU显存)的cgroup隔离
  - charge/uncharge机制
  - 与memory控制器的类比
- *AI视角*：GPU显存隔离——多租户推理的关键能力

### 8.6 其他控制器

- pids：`kernel/cgroup/pids.c`——进程数限制
- freezer：`kernel/cgroup/freezer.c`——进程冻结
- rdma：`kernel/cgroup/rdma.c`——RDMA资源限制
- misc：`kernel/cgroup/misc.c`——杂项资源

## 关键源文件清单

| 文件 | 行数 | 关注点 |
|------|------|--------|
| `kernel/cgroup/cgroup.c` | ~5000 | cgroup核心 |
| `mm/memcontrol.c` | ~5000 | 内存控制器 |
| `kernel/cgroup/cpuset.c` | ~3000 | cpuset |
| `kernel/cgroup/dmem.c` | ~500 | 设备内存控制器 |

## 跨章依赖

- 依赖第7章（调度器）：cpu控制器本质是CFS组调度
- 依赖第9章（物理内存）：memory控制器依赖页面电荷机制
