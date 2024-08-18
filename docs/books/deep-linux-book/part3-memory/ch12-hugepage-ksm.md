---
chapter: 12
part: 第三篇 内存管理 —— 最复杂的子系统
title: 大页与内存合并
source_anchor:
  - mm/hugetlb.c
  - mm/huge_memory.c
  - mm/khugepaged.c
  - mm/ksm.c
  - mm/hugetlb_cgroup.c
  - mm/hugetlb_cma.c
  - mm/hugetlb_vmemmap.c
  - mm/memory_hotplug.c
status: done
---

# 第12章 大页与内存合并

## 写作目标

深入理解大页(HugeTLB/THP)的内核实现与权衡，掌握KSM内存合并和内存热插拔机制。

## 章节大纲

### 12.1 HugeTLB：预留式大页

- **精读** `mm/hugetlb.c`（~7000行）：
  - 大页池的预留与管理
  - `alloc_huge_page()`：大页分配（从池中或CMA）
  - 大页缺页处理
  - 大页的free与池归还
- `mm/hugetlb_cgroup.c`：大页cgroup控制
- `mm/hugetlb_cma.c`：大页从CMA分配
- `mm/hugetlb_vmemmap.c`：大页的vmemmap优化——节省struct page内存
- `mm/hugetlb_sysctl.c`/`mm/hugetlb_sysfs.c`：用户态接口
- *数据库视角*：为什么传统数据库偏爱HugeTLB——稳定的TLB覆盖与可预测性能

### 12.2 THP：透明大页

- **精读** `mm/huge_memory.c`：
  - THP的分配路径：`do_huge_pmd_anonymous_page()`
  - PMD级别的缺页处理
  - THP的分裂：`__split_huge_page()`
  - THP的khugepaged整理：`mm/khugepaged.c`
    - 扫描可合并的VMA
    - collapse的触发条件与流程
- THP的利弊分析
  - 优势：减少TLB miss、减少页表层级
  - 劣势：增加写放大(COW整个大页)、内存碎片、延迟抖动
- *数据库视角*：THP对Buffer Pool的影响——何时开启、何时关闭

### 12.3 KSM：内存合并

- **精读** `mm/ksm.c`：
  - 相同页面的发现与合并
  - stable tree与unstable tree
  - COW保护：合并页面的写时复制
  - KSM的使用场景：虚拟化（KVM）与容器
- *AI视角*：推理服务中多个请求的相同前缀——KSM思想的前缀缓存类比

### 12.4 内存热插拔

- **精读** `mm/memory_hotplug.c`：
  - online/offline内存区域
  - 页面迁移与回收
  - 与NUMA的关系
- `mm/memory-tiers.c`：内存分层——HBM/DDR/NVM的抽象
  - *AI视角*：异构内存的热度感知数据放置

## 关键源文件清单

| 文件 | 行数 | 关注点 |
|------|------|--------|
| `mm/hugetlb.c` | ~7000 | HugeTLB核心 |
| `mm/huge_memory.c` | ~4000 | THP核心 |
| `mm/khugepaged.c` | ~3000 | THP整理守护 |
| `mm/ksm.c` | ~3000 | 内存合并 |
| `mm/memory_hotplug.c` | ~2000 | 内存热插拔 |
| `mm/memory-tiers.c` | ~800 | 内存分层 |

## 跨章依赖

- 依赖第2章（Cache/TLB）：大页的硬件动机是TLB效率
- 依赖第9章（物理内存）：大页分配依赖伙伴系统/CMA
