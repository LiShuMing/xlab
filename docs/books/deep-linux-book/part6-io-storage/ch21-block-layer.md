---
chapter: 21
part: 第六篇 I/O与存储栈 —— 数据的完整通路
title: 通用块层
source_anchor:
  - block/blk-core.c
  - block/blk-mq.c
  - block/blk-mq-sched.c
  - block/mq-deadline.c
  - block/bfq-iosched.c
  - block/kyber-iosched.c
  - block/blk-iocost.c
  - block/blk-iolatency.c
  - block/blk-merge.c
  - block/blk-flush.c
  - block/blk-crypto.c
  - block/bio.c
status: done
---

# 第21章 通用块层

## 写作目标

深入理解Linux块I/O子系统的核心架构，掌握blk-mq多队列模型、I/O调度器和成本控制。

## 章节大纲

### 21.1 bio与request的抽象

- **精读** `block/bio.c`：
  - `struct bio`：块I/O的通用表示
  - bio_vec与多段(Multi-segment)I/O
  - bio的分裂与克隆
- `block/blk-core.c`：
  - 请求的构建与提交
  - `submit_bio()`的入口路径

### 21.2 blk-mq：多队列块层

- **精读** `block/blk-mq.c`（5330行）：
  - 软件队列(ctx)→硬件队列(hctx)→驱动的映射
  - `blk_mq_submit_bio()`：bio到request的转换
  - `blk_mq_sched_insert_request()`：请求插入调度器
  - `blk_mq_dispatch_rq_list()`：请求派发到驱动
  - 标签管理：`block/blk-mq-tag.c`
  - CPU映射：`block/blk-mq-cpumap.c`
- blk-mq调度框架：`block/blk-mq-sched.c`

### 21.3 I/O调度器

- **精读** `block/mq-deadline.c`：Deadline调度器
  - 读请求优先、写请求防饿死
  - 超时机制
- **精读** `block/bfq-iosched.c`（~6000行）：Budget Fair Queueing
  - 公平带宽分配
  - 适合桌面/交互场景
  - BFQ cgroup：`block/bfq-cgroup.c`
- **精读** `block/kyber-iosched.c`：Kyber调度器
  - 基于令牌的拥塞控制
  - 适合NVMe等快设备
- 无调度器(none)：NVMe的直接派发
- *数据库视角*：为何WAL写路径要绕过I/O调度——O_DIRECT + none调度器

### 21.4 I/O合并与优化

- `block/blk-merge.c`：请求合并
  - 物理连续的bio合并为单个request
  - 前合并/后合并
- `block/blk-flush.c`：FLUSH/FUA语义
  - 写屏障的实现
  - *数据库视角*：fsync的blk-flush路径——WAL持久化的内核支撑

### 21.5 I/O成本控制

- **精读** `block/blk-iocost.c`：I/O成本模型
  - 基于权重的带宽/IO分配
  - vrate调整
- **精读** `block/blk-iolatency.c`：I/O延迟控制
  - 目标延迟与节流
- `block/blk-throttle.c`：I/O限速
  - cgroup I/O控制器

### 21.6 块层加密

- `block/blk-crypto.c`：内联加密框架
  - 硬件加密 vs 软件加密回退
  - `block/blk-crypto-profile.c`

## 关键源文件清单

| 文件 | 行数 | 关注点 |
|------|------|--------|
| `block/blk-mq.c` | 5330 | 多队列核心 |
| `block/bfq-iosched.c` | ~6000 | BFQ调度器 |
| `block/blk-iocost.c` | ~3000 | I/O成本控制 |
| `block/blk-core.c` | ~2000 | 块层核心 |
| `block/bio.c` | ~2000 | bio抽象 |

## 跨章依赖

- 依赖第3章（NVMe）：NVMe驱动是blk-mq的消费者
- 依赖第18章（中断）：NVMe中断触发请求完成
- 前置第22章（文件系统）：文件系统通过bio提交I/O
