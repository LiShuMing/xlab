# 第9章 物理内存管理

> 源码锚点：`mm/page_alloc.c`、`mm/slub.c`、`mm/cma.c`、`mm/percpu.c`、`mm/mempool.c`、`mm/memblock.c`、`include/linux/mmzone.h`

物理内存管理是内核最基础也最复杂的子系统。从启动早期的memblock到伙伴系统、从页级分配到slab缓存、从普通内存到CMA连续区，每一层都为上层提供更精细的分配语义。本章逐层深入这些分配器的设计与实现。

## 9.1 早期内存分配：memblock

伙伴系统在启动过程中尚未初始化，内核需要一个临时的分配器来管理早期内存——这就是memblock。

```c
// mm/memblock.c
// memblock管理两种区域：
// memory: 可用的物理内存范围（来自e820）
// reserved: 已被保留（分配出去）的范围

struct memblock {
    bool bottom_up;                     // 分配方向
    phys_addr_t current_limit;          // 当前限制
    struct memblock_type memory;        // 可用内存
    struct memblock_type reserved;      // 保留内存
};
```

`memblock_alloc()`从memory区域中找到一块满足大小和对齐要求的空闲范围，将其添加到reserved区域，返回虚拟地址。memblock的特点：
- **简单**：线性搜索region数组，不需要复杂的伙伴系统
- **只增不减**：memblock没有free操作——启动早期的分配都是永久的
- **过渡性**：`mm_core_init()`建立伙伴系统后，memblock管理的内存被移交给伙伴系统

过渡流程：`mem_init()`→`memblock_free_all()`→将memblock的memory区域中未被保留的页面释放到伙伴系统。

## 9.2 伙伴系统

### zone与node

物理内存按两级结构组织：

```
NUMA Node (pglist_data)
├── Zone DMA      ← <16MB（ISA设备）
├── Zone DMA32    ← <4GB（32位DMA设备）
└── Zone Normal   ← 其余物理内存
```

```c
// include/linux/mmzone.h
struct zone {
    unsigned long _watermark[NR_WMARK];   // min/low/high水位线
    struct per_cpu_pages __percpu *per_cpu_pageset;  // per-CPU页面缓存
    struct free_area free_area[NR_PAGE_ORDERS];      // 伙伴系统自由链表
    spinlock_t lock;                       // zone锁
    unsigned long zone_start_pfn;          // 起始页帧号
    unsigned long spanned_pages;           // 跨越页数(含洞)
    unsigned long managed_pages;           // 伙伴系统管理的页数
    ...
};

struct free_area {
    struct list_head free_list[MIGRATE_TYPES];  // 按迁移类型分链表
    unsigned long nr_free;                      // 空闲块数
};
```

每个NUMA节点一个`pglist_data`，每个zone一个`struct zone`。zone是伙伴系统管理的基本单位。

### 伙伴系统的核心算法

伙伴系统将空闲页面按2的幂次方组织——order 0是1页(4KB)，order 1是2页(8KB)，...，order 10是1024页(4MB)。`free_area[order]`的链表挂的是大小为2^order的连续空闲块。

**分配**：请求order=n的块。如果`free_area[n]`非空，直接取。如果为空，从`free_area[n+1]`取一块，分裂为两个"伙伴"，一个返回，一个挂入`free_area[n]`。

**释放**：释放order=n的块。检查其伙伴是否空闲——如果空闲，合并为order=n+1的块，递归向上合并。伙伴的地址可以通过块的地址异或(2^n * PAGE_SIZE)快速计算。

### MIGRATE_TYPES：反碎片策略

伙伴系统按迁移类型(migratetype)将空闲块分类：

| 类型 | 含义 | 可移动性 |
|------|------|---------|
| UNMOVABLE | 内核分配的页面 | 不可移动 |
| MOVABLE | 用户页面 | 可移动（通过页表修改） |
| RECLAIMABLE | 可回收页面（文件缓存） | 可回收后重用 |
| CMA | CMA保留区域 | 可借用/归还 |

为什么要分类？不可移动的页面散布在内存中会造成外部碎片——即使总空闲内存足够，也无法分配连续的大块。将不可移动页面集中在UNMOVABLE链表中，可以保护MOVABLE区域的连续性。

### alloc_pages()的完整路径

```c
// mm/page_alloc.c (调用链简化)
alloc_pages(gfp_mask, order)
  → __alloc_pages(gfp_mask, order, preferred_nid, nodemask)
    → get_page_from_freelist()           // 快速路径
      → rmqueue(preferred_zone, zone, order, migratetype)
        → __rmqueue_smallest(zone, order, migratetype)  // 从伙伴链表取
        → __rmqueue_cma_fallback()       // CMA回退
        → __rmqueue_fallback()           // 跨migratetype回退
    → __alloc_pages_slowpath()           // 慢速路径
      → wake_all_kswapds()               // 唤醒kswapd回收
      → __alloc_pages_direct_reclaim()   // 直接回收
      → __alloc_pages_direct_compact()   // 直接压缩
      → __alloc_pages_may_oom()          // OOM Killer
```

**快速路径**：从per-CPU pageset或伙伴链表分配，无锁或轻量级锁。大部分分配走快速路径。

**慢速路径**：快速路径失败后进入，可能执行内存回收、压缩、甚至OOM Kill——代价高但确保分配成功。

### per-CPU pageset：冷热页分离

```c
// include/linux/mmzone.h
struct per_cpu_pages {
    int count;              // 列表中的页面数
    int high;               // 高水位——超过则返还给伙伴系统
    int batch;              // 一次批量分配/释放的页数
    struct list_head lists[NR_PCP_LISTS];  // 按order和migratetype分
};
```

per-CPU pageset是伙伴系统的快速缓存——每个CPU维护自己的空闲页列表，分配和释放无需获取zone锁。批量操作：当列表空时一次从伙伴系统取`batch`页，当列表超过`high`时一次返还`batch`页。这减少了锁竞争，也提高了Cache局部性。

### 水位线与kswapd

每个zone有三个水位线：

```
high ─── kswapd停止回收
  |
low  ─── kswapd开始回收
  |
min  ─── 直接回收（分配进程自己回收）
```

当zone空闲页面低于`low`时唤醒kswapd后台回收，低于`min`时分配进程自己执行直接回收。水位线的计算基于zone大小和`sysctl_min_free_kbytes`参数。

## 9.3 SLUB分配器

伙伴系统只能分配2的幂次方个页面——对于内核中大量的小对象分配（如`task_struct`、`dentry`、`inode`），直接用伙伴系统浪费巨大。SLUB分配器在伙伴系统之上提供任意大小对象的分配。

### kmalloc/kfree的快速路径

```c
// mm/slub.c (调用链简化)
kmem_cache_alloc(cache, flags)
  → slab_alloc_node(cache, s, flags, node)
    // 快速路径：从per-CPU slab分配
    object = c->freelist;         // 取空闲对象
    c->freelist = get_freepointer(s, object);  // 更新freelist
    return object;

    // 慢速路径：当前slab用完了
    → ___slab_alloc(cache, flags, node)
      → new_slab(cache, flags)    // 分配新的slab
        → allocate_slab(cache, flags)
          → alloc_slab_page()     // 从伙伴系统分配页面
```

SLUB的per-CPU slab是分配的快速路径——每个CPU维护当前活跃的slab，freelist指针直接指向下一个空闲对象。分配只需读取freelist、更新指针，通常无需任何锁。

### 内联元数据

SLUB将空闲对象的freelist指针存储在对象本身中——空闲时对象的前8字节是下一个空闲对象的地址。这避免了额外的元数据开销。

### slab cache族

`kmalloc()`使用预定义的slab cache族：`kmalloc-64`、`kmalloc-128`、`kmalloc-192`、...、`kmalloc-8K`。请求特定大小时，向上取整到最近的cache。这意味着kmalloc(65)实际分配128字节——内部碎片率约50%。

### SLAB vs SLUB vs SLOB

| 特征 | SLAB | SLUB | SLOB |
|------|------|------|------|
| 复杂度 | 高 | 中 | 低 |
| 快速路径 | per-CPU | per-CPU | 全局链表 |
| 元数据 | 额外结构 | 内联freelist | 最小 |
| 碎片管理 | 好 | 好 | 差 |
| 调试 | 中 | 强 | 弱 |
| 适用 | 历史默认 | 当前默认 | 嵌入式 |

## 9.4 CMA：连续内存分配器

某些设备（GPU、摄像头、DMA引擎）需要连续的物理内存。但系统运行一段时间后，物理内存碎片化严重，很难找到大的连续区域。CMA(Contiguous Memory Allocator)解决这个问题。

```c
// mm/cma.c
struct cma {
    unsigned long count;              // CMA区域页数
    unsigned long *bitmap;            // 分配位图
    unsigned long order_per_bit;      // 每位代表的order
    struct mutex lock;
};
```

CMA的关键设计：**CMA区域在空闲时可被伙伴系统借用**。CMA区域标记为MIGRATE_CMA，伙伴系统可以将MOVABLE页面放在CMA区域。当设备需要连续内存时，CMA将这些借用的页面迁移走，腾出连续空间。

```c
cma_alloc(cma, count, align)
  → 从bitmap中找到count个连续位
  → 将该范围内的MOVABLE页面迁移到其他位置
  → 标记位图为已分配
  → 返回连续物理内存的起始页
```

`hugetlb_cma`——大页从CMA分配：当系统配置了大页但没有足够的连续内存时，`hugetlb_cma_init()`预留CMA区域，`alloc_huge_page()`从CMA分配大页。这避免了启动时预留大页导致的内存浪费。

> **AI视角**：大模型推理的显存分配为何需要连续物理内存。GPU通过DMA访问主机内存时，许多GPU架构要求物理连续的缓冲区（虽然IOMMU可以缓解这个问题）。大模型推理中的KV Cache分配大量连续缓冲区，CMA为这些分配提供保障。第33章将深入CXL异构内存场景下的连续内存管理。

## 9.5 percpu分配器

per-CPU变量是Linux内核最重要的优化之一——每个CPU有自己的副本，访问无需锁。`mm/percpu.c`管理per-CPU变量的内存：

```
per-CPU地址空间布局：
percpu_base_ptr → [CPU0区域][CPU1区域][CPU2区域]...
                   ↓         ↓         ↓
                  同一偏移   同一偏移   同一偏移
```

每个per-CPU变量在所有CPU的副本位于各自区域的同一偏移。`this_cpu_ptr(var)`通过`%gs:offset`快速访问当前CPU的副本。

percpu分配器管理chunk——大块连续的虚拟地址空间，按需分配给per-CPU变量。两种后端：
- **km后端**：用kmalloc分配物理页面，适合小chunk
- **vm后端**：用vmalloc分配虚拟地址空间，适合大chunk

## 9.6 mempool：保证成功的内存池

```c
// mm/mempool.c
mempool_create(min_nr, alloc_fn, free_fn, pool_data)
```

mempool预分配`min_nr`个对象作为紧急储备。正常分配时先从slab分配器获取，失败时从储备中取。释放时如果储备未满则还回储备，否则还给slab分配器。

mempool保证在内存紧张时仍能分配成功——这对于I/O路径等不能失败的场景至关重要。例如块设备的bio结构就使用mempool——即使在内存回收的压力下，也需要能分配bio来完成I/O操作。

> **数据库视角**：数据库引擎中的内存池与内核mempool的设计共鸣。数据库的Buffer Pool本质上是一个应用层的mempool——预分配固定大小的页面缓存，确保查询处理不会因内存分配失败而中断。内核mempool的设计思想（预分配+紧急储备）与数据库的Buffer Pool预分配策略异曲同工。

---

本章建立了对物理内存管理的层级认知：memblock服务启动早期，伙伴系统管理物理页面，SLUB提供小对象分配，CMA保障连续内存，percpu优化锁竞争，mempool确保关键路径不失败。每一层都建立在前一层之上，共同构成完整的内存分配体系。第10章将讨论这些物理页面如何映射到虚拟地址空间。
