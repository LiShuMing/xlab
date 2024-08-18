---
chapter: 10
part: 第三篇 内存管理 —— 最复杂的子系统
title: 虚拟内存与缺页
source_anchor:
  - mm/mmap.c
  - mm/vma.c
  - mm/memory.c
  - mm/rmap.c
  - mm/gup.c
  - mm/mprotect.c
  - mm/mseal.c
  - mm/mremap.c
  - mm/madvise.c
  - mm/mincore.c
status: done
---

# 第10章 虚拟内存与缺页

## 写作目标

深入理解虚拟内存的核心机制：VMA、页表、缺页异常处理、GUP，掌握用户空间地址空间的完整管理。

## 章节大纲

### 10.1 VMA：虚拟内存区域

- VMA抽象：`struct vm_area_struct`
- VMA操作集：`struct vm_operations_struct`
- **精读** `mm/vma.c`：VMA的查找/插入/合并/分裂
  - `vma_merge()`：VMA合并的条件
  - `vma_split()`：VMA分裂的场景
- `mm/vma.h`/`mm/vma_internal.h`：内部接口
- VMA树的演进：红黑树→maple tree

### 10.2 mmap与地址空间布局

- **精读** `mm/mmap.c`：
  - `do_mmap()`：地址空间的分配与映射
  - 虚拟地址空间的布局：代码段/数据段/堆/mmap区/栈
  - MAP_FIXED vs MAP_FIXED_NOREPLACE
  - unmapped_area()：空闲区域查找
- `mm/mremap.c`：地址重映射
- `mm/mmap_lock.c`：mmap_lock的读写锁语义

### 10.3 页表管理

- 四级/五级页表：PGD→P4D→PUD→PMD→PTE
- 页表项标志位：Present/R/W/NX/Dirty/Accessed
- `mm/pgtable-generic.c`：通用页表操作
- `arch/x86/mm/pgtable.c`：x86页表实现
- HugeTLB页表：`arch/x86/mm/hugetlbpage.c`

### 10.4 缺页异常处理

- **精读** `mm/memory.c`（7587行）：
  - `do_page_fault()`→`handle_mm_fault()`→`handle_pte_fault()`
  - 匿名页缺页：`do_anonymous_page()`——分配新页并建立映射
  - 文件页缺页：`do_read_fault()`/`do_wp_page()`——从文件读取
  - 写时复制(COW)：`do_wp_page()`——写保护缺页的处理
  - NUMA缺页：`do_numa_page()`——页面的节点迁移
- `arch/x86/mm/fault.c`：x86缺页异常入口

### 10.5 反向映射(RMAP)

- **精读** `mm/rmap.c`：
  - 从物理页找到所有映射它的VMA
  - `try_to_unmap()`：页面回收时的反向映射遍历
  - `page_vma_mapped_walk()`：页表项查找

### 10.6 GUP：get_user_pages

- **精读** `mm/gup.c`：
  - 从用户虚拟地址获取物理页引用
  - 快速路径：`get_user_pages_fast()`——lockless页表遍历
  - DMA与GUP：设备访问用户内存的基础
  - pin vs get：FOLL_PIN的语义——长期引用（DMA）vs 短期引用
- `mm/gup_test.c`：GUP测试接口

### 10.7 内存操作与保护

- `mm/mprotect.c`：修改VMA保护属性
- `mm/mseal.c`：内存密封——Linux 7.0新增安全特性
  - 防止VMA被修改/合并/unmap
  - *安全视角*：mseal对抗内存篡改攻击
- `mm/madvise.c`：内存使用建议——MADV_DONTNEED/MADV_HUGEPAGE等
- `mm/mincore.c`：页面驻留查询

## 关键源文件清单

| 文件 | 行数 | 关注点 |
|------|------|--------|
| `mm/memory.c` | 7587 | 缺页处理核心 |
| `mm/mmap.c` | ~3500 | mmap实现 |
| `mm/vma.c` | ~1500 | VMA管理 |
| `mm/rmap.c` | ~2500 | 反向映射 |
| `mm/gup.c` | ~3000 | 用户页获取 |
| `mm/mseal.c` | ~300 | 内存密封 |

## 跨章依赖

- 依赖第9章（物理内存）：缺页分配需要物理页面
- 前置第11章（页面回收）：RMAP是页面回收的核心依赖
