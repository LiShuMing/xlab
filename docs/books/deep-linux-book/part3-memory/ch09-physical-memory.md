---
chapter: 9
part: 第三篇 内存管理 —— 最复杂的子系统
title: 物理内存管理
source_anchor:
  - mm/page_alloc.c
  - mm/slub.c
  - mm/cma.c
  - mm/percpu.c
  - mm/mempool.c
  - mm/memblock.c
  - mm/mm_init.c
  - include/linux/mmzone.h
status: done
---

# 第9章 物理内存管理

## 写作目标

深入理解Linux物理内存管理的三大分配器：伙伴系统、SLUB、percpu，掌握从memblock到伙伴系统的初始化过程。

## 章节大纲

### 9.1 早期内存分配：memblock

- **精读** `mm/memblock.c`：
  - memblock的用途：内核启动早期，伙伴系统尚未初始化
  - region管理：memory/reserved两种类型
  - memblock_alloc()的分配语义
- **精读** `mm/mm_init.c`：从memblock到伙伴系统的过渡

### 9.2 伙伴系统

- **精读** `mm/page_alloc.c`（7833行）：
  - `struct zone`与`struct pglist_data`：`include/linux/mmzone.h`
  - MIGRATE_TYPES：可移动/可回收/不可移动——反碎片的分类策略
  - `alloc_pages()`的完整路径：
    - 快速路径：`rmqueue()`——从per-cpu pageset或伙伴链表分配
    - 慢速路径：`__alloc_pages_slowpath()`——回收/压缩/OOM
  - `free_pages()`：页面释放与伙伴合并
  - 水位线(WM_MARK)：min/low/high与kswapd唤醒
  - per-cpu pageset：冷热页分离
- `mm/page_frag_cache.c`：页碎片缓存——小于一页的快速分配
- *数据库视角*：大页分配为何需要CMA配合——连续物理页的稀缺性

### 9.3 SLUB分配器

- **精读** `mm/slub.c`：
  - kmalloc/kfree的快速路径：per-CPU slub
  - slab的组织：partial/full/free链表
  - 对象分配：`slab_alloc_node()`
  - 内联元数据：对象的freelist指针复用
  - 调试模式：redzone/poison/tracking
- kmalloc的slab cache族：`mm/slab_common.c`
- *源码对比*：SLAB vs SLUB vs SLOB的设计取舍

### 9.4 CMA：连续内存分配器

- **精读** `mm/cma.c`：
  - CMA区域的声明与初始化
  - cma_alloc()/cma_release()
  - CMA与伙伴系统的关系：CMA区域在空闲时可被伙伴系统借用
  - `mm/hugetlb_cma.c`：大页从CMA分配
- *AI视角*：大模型推理的显存分配为何需要连续物理内存

### 9.5 percpu分配器

- **精读** `mm/percpu.c`：
  - per-CPU变量的地址空间布局
  - chunk管理与分配
  - `mm/percpu-km.c` vs `mm/percpu-vm.c`：两种后端

### 9.6 mempool：保证成功的内存池

- **精读** `mm/mempool.c`：
  - 预分配与紧急储备
  - *数据库视角*：数据库引擎中的内存池与内核mempool的设计共鸣

## 关键源文件清单

| 文件 | 行数 | 关注点 |
|------|------|--------|
| `mm/page_alloc.c` | 7833 | 伙伴系统核心 |
| `mm/slub.c` | ~6000 | SLUB分配器 |
| `mm/cma.c` | ~400 | CMA分配器 |
| `mm/memblock.c` | ~1200 | 早期内存分配 |
| `mm/mm_init.c` | ~800 | 内存初始化 |
| `include/linux/mmzone.h` | ~1100 | zone/node数据结构 |

## 跨章依赖

- 依赖第2章（Cache/TLB/NUMA）：理解NUMA node与pglist_data的关系
- 前置第10章（虚拟内存）：物理页面是虚拟内存的底层支撑
