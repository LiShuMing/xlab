---
title: 深度Linux：从硬件到AI时代的计算适配
version: 0.1
kernel_version: Linux 7.0.0
source_tree: /home/admin/work/linux
date: 2026-04-30
author: shuming.lsm
---

# 深度Linux：从硬件到AI时代的计算适配

## 定位

面向数据库Query Engine工程师，以Linux 7.0内核源码为锚点，逐层从硬件到AI重构对计算系统的深度理解。

## 叙事主线

**硬件 → 内核抽象 → I/O → 可观测 → 数据库 → AI**

每层都是下一层的前置，没有跳跃。每章在讲原理后都有"数据库视角"或"AI视角"的回扣，让知识不悬空。

## 写作原则

1. **用源码证明原理**：每讲一个机制，都指向具体的源文件和函数，读者能随时从书跳进源码验证
2. **问题驱动**：不讲"内核有哪些数据结构"，而讲"为什么这样设计、不这样会怎样"
3. **双重视角**：每章在讲原理后都有"数据库视角"或"AI视角"的回扣
4. **精读指定源文件**：对关键子系统标注核心源文件及行数，建立阅读锚点

## 目标读者画像

- 数据库Query Engine资深工程师
- 熟悉SQL优化、执行引擎、存储引擎
- 正在学习计算机体系结构
- 关注LLM推理、Agent相关知识
- 思考AI时代如何利用操作系统、硬件适配计算

## 源码树关键目录索引

| 目录 | 对应篇 |
|------|--------|
| `arch/x86/` | 第一篇、第五篇 |
| `drivers/accel/`, `drivers/cxl/`, `drivers/nvme/`, `drivers/gpu/drm/` | 第一篇、第九篇 |
| `init/`, `kernel/sched/`, `kernel/cgroup/` | 第二篇 |
| `mm/` | 第三篇 |
| `kernel/locking/`, `kernel/rcu/`, `kernel/futex/` | 第四篇 |
| `kernel/irq/`, `kernel/time/` | 第五篇 |
| `block/`, `fs/`, `io_uring/`, `net/` | 第六篇 |
| `kernel/bpf/`, `kernel/trace/`, `security/`, `tools/perf/` | 第七篇 |
| `kernel/liveupdate/`, `rust/`, `arch/x86/coco/` | 第九篇 |

## 篇章结构

| 篇 | 名称 | 章节 | 源码锚点 |
|----|------|------|----------|
| 一 | 硬件与架构 | 第1-4章 | `arch/x86/`, `drivers/` |
| 二 | 启动与进程 | 第5-8章 | `init/`, `kernel/`, `kernel/sched/`, `kernel/cgroup/` |
| 三 | 内存管理 | 第9-13章 | `mm/` |
| 四 | 同步与并发 | 第14-17章 | `kernel/locking/`, `kernel/rcu/`, `kernel/futex/` |
| 五 | 中断、时间与信号 | 第18-20章 | `kernel/irq/`, `kernel/time/` |
| 六 | I/O与存储栈 | 第21-24章 | `block/`, `fs/`, `io_uring/`, `net/` |
| 七 | 可观测性、安全与调试 | 第25-27章 | `kernel/bpf/`, `kernel/trace/`, `security/` |
| 八 | 数据库与OS的深度对话 | 第28-30章 | 回扣前七篇源码 |
| 九 | AI时代的OS与硬件适配 | 第31-35章 | `drivers/accel/`, `drivers/cxl/`, `mm/damon/`, `kernel/liveupdate/`, `rust/` |

## 附录

| 编号 | 标题 |
|------|------|
| A | 源码阅读路线图：按本书章节顺序的源码目录导航 |
| B | 关键数据结构速查：task_struct/mm_struct/vm_area_struct/bio/sk_buff字段精解 |
| C | 内核自测体系：tools/testing/selftests/的使用 |
| D | Rust内核开发入门：rust/kernel/绑定与驱动模板 |
| E | 术语中英对照表 |
