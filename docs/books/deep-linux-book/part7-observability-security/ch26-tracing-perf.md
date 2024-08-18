---
chapter: 26
part: 第七篇 可观测性、安全与调试 —— 让系统透明
title: 跟踪与性能分析
source_anchor:
  - kernel/trace/
  - tools/perf/
  - kernel/kprobes.c
status: done
---

# 第26章 跟踪与性能分析

## 写作目标

掌握Linux内核跟踪与性能分析的核心工具链，建立"看到什么→推断什么→验证什么"的方法论。

## 章节大纲

### 26.1 ftrace：函数跟踪

- `kernel/trace/`：
  - function tracer：函数调用追踪
  - function_graph tracer：调用图追踪
  - trace事件(TRACE_EVENT宏)
  - trace buffer的管理
- `kernel/kprobes.c`：动态探针
  - kprobe/kretprobe机制
  - 基于int3的断点插入

### 26.2 perf：硬件性能计数器

- `tools/perf/`：
  - PMU(Performance Monitoring Unit)
  - 采样模式：perf record
  - 计数模式：perf stat
  - 火焰图生成与分析
  - off-CPU分析：`perf sched`
  - 缓存命中/缺失分析

### 26.3 BPF跟踪工具链

- bpftrace：一行式BPF跟踪
- BCC(BPF Compiler Collection)：Python+BPF工具集
- libbpf：CO-RE工具链
- *源码关联*：`kernel/bpf/task_iter.c`等迭代器的使用

### 26.4 性能分析方法论

- 火焰图与偏距分析
- Latency分布直方图与尾延迟追踪
- *数据库视角*：一条慢查询的内核态时间都花在哪里
  - 步骤1：perf record -g 定位热点函数
  - 步骤2：off-cpu分析找到等待点
  - 步骤3：bpftrace追踪锁竞争
  - 步骤4：io_uring completion延迟分析

## 关键源文件清单

| 文件/目录 | 关注点 |
|-----------|--------|
| `kernel/trace/` | ftrace/trace事件 |
| `kernel/kprobes.c` | 动态探针 |
| `tools/perf/` | perf工具链 |

## 跨章依赖

- 依赖第25章（eBPF）：BPF跟踪工具使用eBPF基础设施
