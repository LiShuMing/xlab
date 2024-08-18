---
chapter: 2
part: 第一篇 硬件与架构 —— 计算的物理边界
title: 内存层次：Cache、TLB与NUMA
source_anchor:
  - arch/x86/mm/init_64.c
  - arch/x86/mm/numa.c
  - arch/x86/mm/srat.c
  - arch/x86/mm/tlb.c
  - arch/x86/kernel/cpu/
  - include/linux/cache.h
status: done
---

# 第2章 内存层次：Cache、TLB与NUMA

## 写作目标

建立对内存层次结构的精确认知，理解Cache/TLB/NUMA如何决定软件性能，这是后续内存管理(第三篇)和数据库优化(第八篇)的硬件基础。

## 章节大纲

### 2.1 Cache层级与缓存行

- L1I/L1D/L2/L3的容量、延迟、带宽谱系
- 缓存行(64字节)与伪共享(False Sharing)
  - `__cacheline_aligned` 与 `____cacheline_internodealigned` 的源码定义
  - per-CPU变量的缓存行对齐实践
- 缓存一致性协议(MESI)：Modified/Exclusive/Shared/Invalid
- 预取(Prefetch)：硬件预取策略与`__builtin_prefetch`
- *数据库视角*：Buffer Pool页对齐策略——为什么数据库页大小(8KB)是缓存行的整数倍

### 2.2 TLB与页表遍历

- TLB层级：L1 STLB/L1 DTLB/L2 STLB
- TLB miss的代价：Page Table Walk的硬件流程
- x86四级/五级页表：PGD→P4D→PUD→PMD→PTE
- **精读** `arch/x86/mm/init_64.c`：页表填充与内核映射建立
  - `kernel_physical_mapping_init()`：物理内存的内核映射
  - `init_top_pgt`：顶级页表的构建
- TLB刷新：`arch/x86/mm/tlb.c`
  - 局部刷新 vs 全局刷新(INVPCID)
  - lazy TLB：进程切换时避免刷新
- PCID(Page Context Identifier)：地址空间标识符

### 2.3 NUMA拓扑与访存代价

- NUMA的硬件根源：QPI/UPI互连与内存控制器集成
- NUMA拓扑发现：
  - **精读** `arch/x86/mm/numa.c`：`numa_init()`流程
  - SRAT(System Resource Affinity Table)解析：`arch/x86/mm/srat.c`
  - ACPI与NUMA节点的建立
- NUMA距离矩阵与访存延迟量化
- 跨节点访存的带宽惩罚
- *数据库视角*：NUMA感知的数据分区——Partition的物理放置策略
- *AI视角*：GPU显存与主机内存的NUMA关系

### 2.4 大页与TLB效率

- 2MB/1GB大页的TLB覆盖效率计算
- TLB miss率对大内存工作集的影响
- *AI视角*：LLM推理的KV Cache为何需要大页——参数量增长与TLB压力

## 关键源文件清单

| 文件 | 行数 | 关注点 |
|------|------|--------|
| `arch/x86/mm/init_64.c` | ~1500 | 内核页表建立 |
| `arch/x86/mm/numa.c` | ~600 | NUMA拓扑发现 |
| `arch/x86/mm/srat.c` | ~300 | SRAT表解析 |
| `arch/x86/mm/tlb.c` | ~400 | TLB刷新与lazy TLB |
| `include/linux/cache.h` | ~50 | 缓存行对齐宏定义 |

## 跨章依赖

- 本章是第9章（物理内存管理）的前置：理解伙伴系统的NUMA感知分配
- 本章是第12章（大页）的前置：TLB效率是大页的硬件动机
