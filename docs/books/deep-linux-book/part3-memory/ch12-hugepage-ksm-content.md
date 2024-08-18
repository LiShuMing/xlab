# 第12章 大页与内存合并

> 源码锚点：`mm/hugetlb.c`、`mm/huge_memory.c`、`mm/khugepaged.c`、`mm/ksm.c`、`mm/memory_hotplug.c`、`mm/memory-tiers.c`

大页减少TLB miss，KSM合并相同页面节省内存——两者从不同角度优化内存效率。本章深入HugeTLB预留式大页、THP透明大页、KSM内存合并和内存热插拔。

## 12.1 HugeTLB：预留式大页

HugeTLB提供确定性的大页分配——大页从预留池中分配，保证成功。这是对TLB效率最直接的优化。

### 大页池的管理

```c
// mm/hugetlb.c
// 大页池按大小管理：
// hugepages-2048kB  → 2MB大页(x86_64默认)
// hugepages-1048576kB → 1GB大页
```

HugeTLB的分配流程：
1. **预留**：系统启动或运行时通过`/proc/sys/vm/nr_hugepages`预留大页
2. **分配**：`alloc_huge_page()`从池中取大页，池空则分配失败
3. **释放**：大页归还池，可供后续分配

HugeTLB的确定性是其核心价值——大页已经预留好，分配不会因碎片或内存压力失败。代价是预留的内存不能被其他用途使用，即使大页未被分配也占用物理内存。

### CMA大页：动态预留

`mm/hugetlb_cma.c`允许大页从CMA区域动态分配——不预留，需要时从CMA迁移获得：

```c
// mm/hugetlb_cma.c
hugetlb_cma_reserve()  // 启动时声明CMA区域
cma_alloc(hugetlb_cma, ...)  // 需要时从CMA分配大页
```

CMA大页解决了HugeTLB的内存浪费问题——CMA区域在空闲时可以被伙伴系统借用，需要时再迁移回收。

### vmemmap优化

每个4KB页面需要一个64字节的`struct page`。2MB大页需要512个`struct page`(32KB)，1GB大页需要262144个`struct page`(16MB!)。`mm/hugetlb_vmemmap.c`优化了这个问题——大页的`struct page`可以复用：只需前几个`struct page`有实际内容，其余可以释放。1GB大页可以节省约16MB - 256B ≈ 16MB的`struct page`内存。

> **数据库视角**：为什么传统数据库偏爱HugeTLB。数据库的Buffer Pool通常占用数十GB内存，使用4KB页面会导致大量TLB miss。2MB大页将TLB覆盖范围扩大512倍——同样数量的TLB条目覆盖的内存从几MB扩大到几GB。PostgreSQL默认启用HugeTLB，Oracle强烈建议使用HugeTLB。确定性分配是另一个关键原因——Buffer Pool初始化时一次性分配所有大页，不会因运行时内存碎片而失败。

## 12.2 THP：透明大页

### 设计哲学

HugeTLB需要应用主动使用`shmget`/`mmap`配合`MAP_HUGETLB`——对已有应用不友好。THP(Transparent Huge Page)在内核层面自动将4KB页面合并为2MB大页，对应用透明。

### THP的分配路径

```c
// mm/huge_memory.c
// PMD级别的缺页处理
static vm_fault_t do_huge_pmd_anonymous_page(struct vm_fault *vmf)
{
    // 尝试分配2MB大页
    page = alloc_transhugepage(vma, haddr);
    if (page) {
        // 建立PMD映射（跳过PTE层）
        set_huge_zero_page(pgtable, vma, haddr, pmd);
    } else {
        // 分配失败，回退到4KB页面
        return VM_FAULT_FALLBACK;
    }
}
```

THP在PMD级别建立映射——一个PMD条目直接映射2MB物理页，跳过了512个PTE。这减少了页表层级和内存占用，也提高了TLB效率。

### khugepaged：后台整理

不是所有分配都能直接获得大页——内存碎片可能导致分配失败。`mm/khugepaged.c`在后台扫描可合并的VMA，将连续的4KB页面整理为大页：

```c
// mm/khugepaged.c
// 扫描条件：
// 1. VMA标记为VM_HUGEPAGE或系统默认启用THP
// 2. VMA大小 >= 2MB
// 3. 区域内的4KB页面足够连续
// 4. 有足够的空闲大页或可迁移页面
```

collapse的流程：
1. 扫描进程的VMA，找到候选区域
2. 检查区域内的4KB页面是否全部在内存中
3. 分配新的2MB大页
4. 将4KB页面的内容复制到大页
5. 建立PMD映射，替换原有的512个PTE
6. 释放4KB页面

### THP的利弊

**优势**：
- 减少TLB miss——2MB页面只需1个TLB条目
- 减少页表层级——PMD直接映射
- 对应用透明——无需修改代码

**劣势**：
- COW写放大——fork后写入2MB页面需要复制整个2MB
- 内存碎片——2MB连续物理页难以获得
- 延迟抖动——khugepaged的collapse操作可能增加延迟
- 内存浪费——不足2MB的VMA也分配2MB

> **数据库视角**：THP对Buffer Pool的影响。THP对Buffer Pool是双刃剑：优势是TLB效率提升，劣势是COW写放大。PostgreSQL默认关闭THP——因为Buffer Pool的页面可能被fork的后端进程共享，THP的2MB COW在checkpoint时可能导致延迟飙升。Redis也建议关闭THP——因为fork+copy-on-write的RDB持久化场景下，THP的COW写放大导致内存使用量翻倍。

## 12.3 KSM：内存合并

KSM(Kernel Samepage Merging)发现内容完全相同的物理页，将它们合并为同一个页面（COW保护）：

```
进程A的页面X (内容: 全零) ──┐
                              ├──→ 共享页面Z (COW保护)
进程B的页面Y (内容: 全零) ──┘
```

### KSM的实现

```c
// mm/ksm.c
// 两棵树：
// stable tree：已经合并的页面（内容不再变化）
// unstable tree：候选合并的页面（内容可能变化）

// 流程：
// 1. 页面被madvise(MADV_MERGEABLE)标记
// 2. ksm守护进程扫描这些页面
// 3. 计算页面内容的校验和，在unstable tree中查找匹配
// 4. 找到匹配→逐字节比较→确认相同→合并为COW共享页
// 5. 共享页移入stable tree
```

KSM的核心数据结构是两棵树——`stable_tree`存储已合并的页面（内容不变），`unstable_tree`存储待合并的候选页面。页面内容的校验和快速过滤不匹配的候选，逐字节比较只在校验和匹配时执行。

KSM在KVM虚拟化中广泛使用——多个虚拟机运行相同OS时，大量内存页内容相同（如相同的内核代码、相同的共享库），KSM可以节省30-50%的内存。

> **AI视角**：推理服务中多个请求的相同前缀——KSM思想的前缀缓存类比。LLM推理中，不同请求的prompt可能有相同前缀（如系统提示词），对应的KV Cache内容完全相同。vLLM等推理框架实现了"前缀缓存"(Prefix Caching)——类似KSM的思想，发现相同前缀的KV Cache，共享存储，避免重复计算。KSM的stable/unstable tree结构也可以启发KV Cache的去重设计。

## 12.4 内存热插拔

### online/offline

`mm/memory_hotplug.c`支持在运行时添加或移除物理内存：

```
物理内存热添加(hot-add)：
  1. ACPI通知新内存设备
  2. 创建新的mem_section
  3. 建立struct page和页表映射
  4. 将内存online到伙伴系统

物理内存热移除(hot-remove)：
  1. 将内存offline——迁移所有页面到其他节点
  2. 释放struct page
  3. 撤销页表映射
  4. 通知ACPI移除设备
```

offline的关键挑战：必须将目标区域内的所有页面迁移走——包括用户页面、内核页面、不可移动页面。如果区域内有不可移动页面，offline失败。

### 内存分层：memory-tiers

`mm/memory-tiers.c`抽象异构内存的层次结构：

```
Tier 0: HBM (GPU显存) — 带宽最高、延迟最低
Tier 1: DDR5 DRAM — 主内存
Tier 2: CXL内存 — 扩展内存
Tier 3: NVM — 持久内存
Tier 4: Swap — 磁盘交换
```

DAMON和memory-tiers结合实现**热度感知数据放置**——热数据在Tier 0/1，温数据在Tier 2，冷数据在Tier 3/4。这是CXL异构内存管理的核心，第33章将深入讨论。

> **AI视角**：异构内存的热度感知数据放置。推理服务的内存具有明显的热度层级：当前token的KV Cache最热(HBM)，近期token的KV Cache较热(DDR)，已完成请求的KV Cache最冷(CXL/Swap)。结合DAMON的访问模式监控和memory-tiers的分层抽象，内核可以实现自动的KV Cache分级存储——第33章将详细分析这一架构。

---

本章建立了对大页和内存合并的认知：HugeTLB提供确定性大页分配，THP透明地将4KB页面合并为大页，KSM合并相同内容页面节省内存，内存热插拔支持运行时扩缩容，memory-tiers抽象异构内存层次。大页优化TLB效率，KSM优化内存使用效率——两者从不同维度提升内存子系统性能。第13章将转向内存安全与调试。
