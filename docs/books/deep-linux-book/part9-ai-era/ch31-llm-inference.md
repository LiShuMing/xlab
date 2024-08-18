---
chapter: 31
part: 第九篇 AI时代的OS与硬件适配
title: LLM推理的系统视角
source_anchor:
  - mm/vmscan.c
  - mm/page_alloc.c
  - mm/page_table_check.c
  - kernel/sched/fair.c
  - mm/hmm.c
  - mm/migrate.c
  - mm/migrate_device.c
status: done
---

# 第31章 LLM推理的系统视角

## 写作目标

从操作系统原理出发重新审视LLM推理的系统瓶颈，建立推理优化与OS机制的深层映射。

## 章节大纲

### 31.1 推理阶段的访存瓶颈

- 自回归生成的访存模式：逐token生成，每步需读取全部权重
- 算力bound vs 带宽bound：
  - Prefill阶段：算力bound（并行处理输入token）
  - Decode阶段：带宽bound（逐token生成）
- Memory Wall：模型参数量增长 >> 带宽增长
- *OS映射*：与Page Cache的命中率问题本质相同——工作集 >> 缓存容量

### 31.2 KV Cache管理

- KV Cache的本质：每个请求的注意力缓存
- KV Cache的内存挑战：
  - 单请求内存：layer × head × dim × seq_len
  - 多请求并发：内存随batch size线性增长
- 分页KV Cache：PagedAttention(vLLM)
  - *OS映射*：与虚拟内存分页系统的类比
    - KV Block ≈ Page
    - Block Table ≈ Page Table
    - `mm/page_table_check.c`：页表检查的KV Block管理启发
  - 外部碎片问题的相同解法
- KV Cache换出：CPU内存作为GPU显存的swap
  - *OS映射*：`mm/swapfile.c`的swap机制类比
- 前缀缓存(Prefix Caching)：
  - 共享系统提示的KV Block复用
  - *OS映射*：`mm/ksm.c`的内存合并——相同页面的共享

### 31.3 连续批处理(Continuous Batching)

- 静态批处理 vs 连续批处理
- iteration-level调度：每步可加入/移出请求
- *OS映射*：`kernel/sched/fair.c`的CFS调度类比
  - 请求 ≈ 进程
  - iteration ≈ 时间片
  - preemption ≈ 请求完成移出batch
- 或读调度(Orca)：优先调度KV Cache未换出的请求

### 31.4 推理引擎的内存管理

- vLLM的PagedAttention：分页显存管理
- TensorRT-LLM的KV Cache复用
- *OS映射*：`mm/vmscan.c`回收策略的类比
  - 热度感知回收：最近生成的token的KV Block优先保留
  - 工作集估计：`mm/workingset.c`的refault距离类比

### 31.5 Speculative Decoding的系统视角

- 小模型猜测 + 大模型验证
- *OS映射*：分支预测(Spectre)的类比——预测与验证

## 关键源文件清单

| 文件 | 关注点 |
|------|--------|
| `mm/vmscan.c` | 页面回收→KV Cache回收类比 |
| `mm/page_table_check.c` | 页表检查→KV Block管理类比 |
| `mm/ksm.c` | 内存合并→前缀缓存类比 |
| `kernel/sched/fair.c` | CFS→批处理调度类比 |

## 跨章依赖

- 综合运用第三篇（内存管理）的页面管理思想
- 综合运用第二篇（调度器）的调度策略
