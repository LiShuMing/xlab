# 第2章 内存层次：Cache、TLB与NUMA

> 源码锚点：`arch/x86/mm/init_64.c`、`arch/x86/mm/numa.c`、`arch/x86/mm/srat.c`、`arch/x86/mm/tlb.c`、`include/linux/cache.h`

CPU越来越快，内存越来越慢——这个趋势已经持续了三十年。Cache、TLB、NUMA，三层硬件机制都是为了弥合这道鸿沟。理解它们，是理解Linux内存管理（第三篇）和数据库性能调优（第八篇）的硬件前提。

## 2.1 Cache层级与缓存行

### L1/L2/L3：容量与延迟的谱系

现代x86处理器的Cache层级：

| 层级 | 容量 | 延迟 | 带宽 | 关联度 | 共享范围 |
|------|------|------|------|--------|---------|
| L1I | 32-64 KB | 3-4 cyc | ~1 TB/s | 8-way | 每核心 |
| L1D | 32-64 KB | 4-5 cyc | ~1 TB/s | 8-way | 每核心 |
| L2 | 256 KB-2 MB | 12-14 cyc | ~500 GB/s | 16-way | 每核心或每核心对 |
| L3 | 8-64 MB | 30-50 cyc | ~200 GB/s | 12-16-way | 全部核心共享 |

关键观察：**L1到主存的延迟差距约100倍**（4 cyc vs 300+ cyc），但容量差距约1000倍（64 KB vs 64 GB）。这个不匹配是所有内存性能问题的根源。

L3的延迟范围很大（30-50 cyc），因为它受NUMA距离影响——访问远端节点的L3需要穿越互连，延迟翻倍。

### 缓存行：数据传输的最小单位

Cache不是按字节操作的，而是按**缓存行(Cache Line)**——x86上固定为64字节。一次Cache miss会导致整行64字节从下一级加载，即使你只需要1个字节。

缓存行对软件设计的深远影响：

**1. 空间局部性(Spatial Locality)**——连续内存访问的性能优势。遍历数组时，第一个元素的miss会把后续63字节也加载到Cache，后续访问全部命中。这是为什么数组的顺序遍历比链表快一个数量级。

**2. 伪共享(False Sharing)**——多核编程的隐形杀手。如果两个CPU各自修改同一缓存行的不同字段，虽然逻辑上没有共享数据，但硬件层面的缓存行争用会导致反复的Cache失效和重新加载。

Linux内核提供了专门的宏来对抗伪共享，定义在`include/linux/cache.h`中：

```c
// include/linux/cache.h
#ifndef __cacheline_aligned
#define __cacheline_aligned                    \
  __attribute__((__aligned__(SMP_CACHE_BYTES), \
               __section__(".data..cacheline_aligned")))
#endif

#ifndef ____cacheline_internodealigned_in_smp
#if defined(CONFIG_SMP)
#define ____cacheline_internodealigned_in_smp \
    __attribute__((__aligned__(1 << (INTERNODE_CACHE_SHIFT))))
#endif
#endif
```

- `__cacheline_aligned`：对齐到SMP_CACHE_BYTES（x86上为64字节），将变量放到专用的`.data..cacheline_aligned`段
- `____cacheline_internodealigned_in_smp`：对齐到INTERNODE_CACHE_SHIFT，这是跨节点缓存行大小——在某些架构上，跨NUMA节点的缓存行比节点内更大，需要更大的对齐

内核中广泛使用的实践——`task_struct`中的热字段分组：

```c
// 通过 __cacheline_group_begin/end 将字段分组到不同缓存行
__cacheline_group_begin_aligned(read_write);
// 频繁读写的热字段放在一组
__cacheline_group_end_aligned(read_write);

__cacheline_group_begin_aligned(read_only);
// 只读字段放在另一组，避免被写操作invalidate
__cacheline_group_end_aligned(read_only);
```

`cache.h`还定义了`CACHELINE_PADDING(name)`宏，在结构体中插入padding确保字段落在不同缓存行：

```c
#if defined(CONFIG_SMP)
struct cacheline_padding {
    char x[0];
} ____cacheline_internodealigned_in_smp;
#define CACHELINE_PADDING(name)  struct cacheline_padding name
#endif
```

另一个重要的注解是`__read_mostly`，将变量放到只读热路径段，减少与写操作的缓存行冲突：

```c
// include/linux/cache.h
// "__read_mostly is used to keep rarely changing variables out of
//  frequently updated cachelines."
#ifndef __read_mostly
#define __read_mostly
#endif
```

**3. per-CPU变量**——Linux内核避免伪共享的终极武器。per-CPU变量为每个CPU维护一份独立副本，彻底消除跨CPU的缓存行争用。因为每个CPU只访问自己的副本，不需要任何锁，也不存在伪共享。典型例子：`DEFINE_PER_CPU(struct vm_event_state, vm_event_states)`——每个CPU独立的VM事件计数器。

### 缓存一致性协议：MESI

多核系统中，同一内存地址可能存在于多个核心的Cache中。如何保证一致性？x86使用MESI协议，每个缓存行维护2-bit状态：

| 状态 | 含义 | 可读 | 可写 | 其他Cache有副本 |
|------|------|------|------|----------------|
| **M**odified | 已修改，与内存不一致 | 是 | 是 | 否 |
| **E**xclusive | 独占，与内存一致 | 是 | 是 | 否 |
| **S**hared | 共享，与内存一致 | 是 | 否(需先升级) | 是 |
| **I**nvalid | 无效 | 否 | 否 | — |

MESI的状态转换由硬件自动维护，但对软件性能影响巨大：

- **写一个Shared状态的行**：必须先向其他核心发送Invalidate消息，等待确认后才能升级为Exclusive/Modified。这个等待(ack)在跨NUMA节点时尤其昂贵。
- **伪共享的代价**：CPU A写字段X，CPU B写字段Y，X和Y在同一缓存行。每次写都导致对方的缓存行失效(Invalidate)，对方下次读必须重新从内存或远端Cache加载。

### 预取(Prefetch)

硬件预取器监控访问模式，自动预测并提前加载：

- **流预取(Stream Prefetch)**：检测到连续地址访问，自动预取后续缓存行
- **步长预取(Strided Prefetch)**：检测到固定步长访问（如数组遍历），按步长预取
- **相邻预取(Spatial Prefetch)**：一次miss会自动预取相邻缓存行

软件也可以主动预取：`__builtin_prefetch(addr, rw, locality)`。内核在热路径中使用它，例如`mm/page_alloc.c`中的伙伴系统分配。但预取是一把双刃剑——预取无用数据会浪费带宽、污染Cache，反而降低性能。大多数情况下，依赖硬件预取比手动预取更安全。

> **数据库视角**：Buffer Pool的页对齐策略。数据库页大小(通常8KB)恰好是缓存行(64B)的整数倍——128个缓存行。这不是巧合：页对齐确保一页的数据在Cache中是连续的，顺序扫描页内的行能最大化空间局部性。而如果页不对齐，一页的尾部和下一页的头部可能共享缓存行，导致跨页的伪共享。

## 2.2 TLB与页表遍历

### TLB：虚拟到物理的缓存

虚拟地址到物理地址的翻译需要遍历多级页表，每次内存访问都要翻译——如果不缓存翻译结果，每条指令的取指和每次数据访问都要遍历4-5级页表，开销不可接受。

TLB(Translation Lookaside Buffer)就是页表翻译的缓存。x86的TLB层级：

| TLB | 条目数 | 覆盖(4KB页) | 覆盖(2MB大页) |
|-----|--------|------------|--------------|
| L1 ITLB | 64 | 256 KB | 128 MB |
| L1 DTLB | 64 | 256 KB | 128 MB |
| L2 STLB | 1536 | 6 MB | — |

L2 STLB(Second-level Unified TLB)统一缓存指令和数据的翻译结果，是L1 ITLB/DTLB的后备。

### TLB miss的代价：Page Table Walk

当TLB中没有目标虚拟地址的翻译时，CPU必须遍历页表——硬件自动完成的Page Table Walk：

```
CR3 → PGD → P4D → PUD → PMD → PTE → 物理地址
       │      │      │      │      │
       4K     4K     4K     4K     4K      每级访问一次内存
```

四级页表需要4次内存访问（PGD通常在Cache中），五级页表需要5次。如果每一级都miss L3 Cache，一次Page Table Walk可能需要100-200个时钟周期。这是为什么大页如此重要——2MB大页只需遍历到PMD就得到物理地址，省掉了PTE这一级。

### x86四级/五级页表

x86-64的虚拟地址格式（以48位/57位为例）：

```
57位虚拟地址(5级页表):
┌──────┬──────┬──────┬──────┬──────┬──────┬──────────┐
│ P4D  │ PGD  │ PUD  │ PMD  │ PTE  │ 页内偏移          │
│ 9bit │ 9bit │ 9bit │ 9bit │ 9bit │ 12bit             │
└──────┴──────┴──────┴──────┴──────┴──────┴──────────┘

48位虚拟地址(4级页表):
┌──────┬──────┬──────┬──────┬──────────┐
│ PGD  │ PUD  │ PMD  │ PTE  │ 页内偏移  │
│ 9bit │ 9bit │ 9bit │ 9bit │ 12bit     │
└──────┴──────┴──────┴──────┴──────────┘
```

每级9位索引，12位页内偏移。每级页表项512个（2^9），每项8字节，恰好一页（4KB）。五级页表支持57位虚拟地址空间——128 PB，远超当前需求。

### 精读 init_64.c：内核页表映射的建立

内核启动时，必须为全部物理内存建立虚拟映射（直接映射区）。这是`kernel_physical_mapping_init()`的工作，定义在`arch/x86/mm/init_64.c`中：

```c
// arch/x86/mm/init_64.c
static unsigned long __meminit
__kernel_physical_mapping_init(unsigned long paddr_start,
                               unsigned long paddr_end,
                               unsigned long page_size_mask,
                               pgprot_t prot, bool init)
{
    bool pgd_changed = false;
    unsigned long vaddr, vaddr_start, vaddr_end, vaddr_next, paddr_last;

    paddr_last = paddr_end;
    vaddr = (unsigned long)__va(paddr_start);  // 物理地址→虚拟地址
    vaddr_end = (unsigned long)__va(paddr_end);
    vaddr_start = vaddr;

    for (; vaddr < vaddr_end; vaddr = vaddr_next) {
        pgd_t *pgd = pgd_offset_k(vaddr);     // 获取PGD项
        p4d_t *p4d;

        vaddr_next = (vaddr & PGDIR_MASK) + PGDIR_SIZE;  // 下一个PGD项

        if (pgd_val(*pgd)) {                  // PGD项已存在
            p4d = (p4d_t *)pgd_page_vaddr(*pgd);
            paddr_last = phys_p4d_init(p4d, __pa(vaddr),
                                       __pa(vaddr_end),
                                       page_size_mask, prot, init);
            continue;
        }

        p4d = alloc_low_page();               // 分配新的P4D页
        paddr_last = phys_p4d_init(p4d, __pa(vaddr), __pa(vaddr_end),
                                   page_size_mask, prot, init);

        spin_lock(&init_mm.page_table_lock);
        if (pgtable_l5_enabled())              // 5级页表
            pgd_populate_init(&init_mm, pgd, p4d, init);
        else                                   // 4级页表，P4D折叠
            p4d_populate_init(&init_mm, p4d_offset(pgd, vaddr),
                              (pud_t *) p4d, init);
        spin_unlock(&init_mm.page_table_lock);
        pgd_changed = true;
    }

    if (pgd_changed)
        sync_global_pgds(vaddr_start, vaddr_end - 1);  // 同步到所有CPU

    return paddr_last;
}
```

这个函数的核心逻辑：从物理内存起始到结束，逐级填充页表。`page_size_mask`控制是否使用大页映射——如果物理地址对齐，PMD级别直接映射2MB大页，PUD级别直接映射1GB大页，省掉下层页表的分配和填充。

大页映射的决策在`phys_pmd_init()`中：

```c
// 如果允许2MB大页且物理地址对齐
if (page_size_mask & (1<<PG_LEVEL_2M)) {
    pages++;
    set_pmd_init(pmd,
                 pfn_pmd(paddr >> PAGE_SHIFT, prot_sethuge(prot)),
                 init);
    paddr_last = paddr_next;
    continue;  // 跳过PTE级别的分配
}
```

内核直接映射区使用大页是重要的性能优化——内核频繁访问的数据结构（task_struct、page数组等）如果映射在小页上，TLB miss率会非常高。

### TLB刷新与lazy TLB

修改页表后，旧的TLB条目必须被无效化，否则CPU可能使用过期的翻译。`arch/x86/mm/tlb.c`实现了TLB刷新机制。

**局部刷新 vs 全局刷新：**

- **局部刷新(INVLPG)**：只无效化单个虚拟地址的TLB条目。修改单个PTE时使用。
- **全局刷新**：无效化所有非全局TLB条目。进程切换时使用。

x86的PCID机制允许更精细的控制：

```c
// arch/x86/mm/tlb.c — PCID/ASID的关系
// kPCID - [1, MAX_ASID_AVAILABLE]   内核PCID
// uPCID - [2048 + 1, 2048 + MAX_ASID_AVAILABLE]  用户PCID (KPTI)
static inline u16 kern_pcid(u16 asid) { return asid + 1; }
static inline u16 user_pcid(u16 asid) {
    u16 ret = kern_pcid(asid);
#ifdef CONFIG_MITIGATION_PAGE_TABLE_ISOLATION
    ret |= 1 << X86_CR3_PTI_PCID_USER_BIT;  // KPTI: 高位置1
#endif
    return ret;
}
```

**lazy TLB**——进程切换的优化。当新进程使用与旧进程相同的`mm_struct`（内核线程借用`active_mm`），不需要刷新TLB——翻译结果仍然有效。`tlb.c`中的`switch_mm_irqs_off()`会检查是否需要切换地址空间，避免不必要的CR3写入和TLB冲刷。

```c
// arch/x86/mm/tlb.c — build_cr3_noflush: 切换地址空间但不刷新TLB
static inline unsigned long build_cr3_noflush(pgd_t *pgd, u16 asid, unsigned long lam)
{
    VM_WARN_ON_ONCE(!boot_cpu_has(X86_FEATURE_PCID));
    return build_cr3(pgd, asid, lam) | CR3_NOFLUSH;  // NOFLUSH位: 保留TLB
}
```

`CR3_NOFLUSH`是PCID带来的关键优化——切换CR3时可以保留当前PCID对应的TLB条目，下次切回时无需重新Page Table Walk。没有PCID时，每次写CR3都会冲刷所有TLB。

### PCID(Page Context Identifier)

PCID是CR3寄存器低12位中可用的地址空间标识符（x86-64上CR3的低12位因为页对齐而未使用）。PCID让TLB条目携带地址空间标签，同一虚拟地址在不同地址空间可以共存于TLB中。

Linux的PCID使用策略：每个CPU维护一个小的ASID数组（`TLB_NR_DYN_ASIDS`，通常6-8个），缓存最近使用的地址空间。当ASID用尽时，才需要冲刷TLB并重新分配。这比传统的"每次切换都冲刷"高效得多。

## 2.3 NUMA拓扑与访存代价

### NUMA的硬件根源

NUMA(Non-Uniform Memory Access)的出现源于一个简单的物理限制：**内存控制器集成到CPU Die中**。

在早期Front-Side Bus架构中，所有CPU通过北桥芯片访问内存，延迟一致(UMA)。但当内存控制器集成到CPU后，每个CPU Die有了自己的本地内存，跨Die访问必须经过互连总线(QPI/UPI)，延迟更高。

```
NUMA节点0                    NUMA节点1
┌─────────────────┐         ┌─────────────────┐
│  CPU 0-15       │  UPI    │  CPU 16-31      │
│  ┌───────────┐  │◄───────►│  ┌───────────┐  │
│  │MC: DDR0-3 │  │ 互连    │  │MC: DDR4-7 │  │
│  └───────────┘  │         │  └───────────┘  │
│  本地内存 256GB  │         │  本地内存 256GB  │
└─────────────────┘         └─────────────────┘
    本地访问 ~80ns              远端访问 ~140ns
```

### NUMA拓扑发现

Linux通过ACPI表发现NUMA拓扑，核心流程在`arch/x86/mm/numa.c`和`arch/x86/mm/srat.c`中。

**精读 `arch/x86/mm/srat.c`**——SRAT(System Resource Affinity Table)解析：

SRAT是ACPI表之一，描述CPU和内存与"近邻域"(Proximity Domain)的归属关系。`srat.c`中有两个核心回调：

```c
// SRAT中的x2APIC CPU亲和性回调
void __init
acpi_numa_x2apic_affinity_init(struct acpi_srat_x2apic_cpu_affinity *pa)
{
    int pxm, node, apic_id;

    if (srat_disabled()) return;
    if ((pa->flags & ACPI_SRAT_CPU_ENABLED) == 0) return;

    pxm = pa->proximity_domain;         // 近邻域ID
    apic_id = pa->apic_id;              // APIC ID
    node = acpi_map_pxm_to_node(pxm);   // 映射到Linux节点号

    set_apicid_to_node(apic_id, node);  // APIC ID → 节点号
    node_set(node, numa_nodes_parsed);
    pr_debug("SRAT: PXM %u -> APIC 0x%04x -> Node %u\n", pxm, apic_id, node);
}
```

流程：ACPI SRAT表 → 近邻域(PXM) → Linux节点号(node) → APIC ID到节点的映射。每个APIC ID对应一个CPU核心，这样CPU到节点的映射就建立了。

**精读 `arch/x86/mm/numa.c`**——节点到CPU的映射：

```c
// arch/x86/mm/numa.c
// CPU → 节点 的per-CPU映射
DEFINE_EARLY_PER_CPU(int, x86_cpu_to_node_map, NUMA_NO_NODE);

void numa_set_node(int cpu, int node)
{
    int *cpu_to_node_map = early_per_cpu_ptr(x86_cpu_to_node_map);
    if (cpu_to_node_map) {
        cpu_to_node_map[cpu] = node;
        return;
    }
    per_cpu(x86_cpu_to_node_map, cpu) = node;
    set_cpu_numa_node(cpu, node);  // 设置调度器可见的节点信息
}
```

内核命令行可以通过`numa=fake=N`模拟NUMA拓扑，通过`numa=off`禁用NUMA，通过`numa=noacpi`跳过SRAT解析。

### NUMA距离矩阵

ACPI的SLIT(System Locality Information Table)描述节点间的相对距离：

```
节点    0     1     2     3
  0    10    21    31    21
  1    21    10    21    31
  2    31    21    10    21
  3    21    31    21    10
```

值10表示本地（基准），21表示1跳，31表示2跳。这些值是相对值，不是纳秒。实际延迟需要通过`numactl --hardware`或PMU计数器测量。

### 跨节点访存的带宽惩罚

延迟不是唯一的代价——带宽也是。UPI互连的带宽约10-20 GB/s每链路，而本地内存带宽约50-80 GB/s。跨节点访存不仅慢，还会占用互连带宽，影响其他跨节点通信。

量化示例（2-socket Intel Xeon）：
- 本地DDR访问：~80ns，带宽~60 GB/s
- 跨节点DDR访问：~140ns，带宽~30 GB/s（受互连限制）

> **数据库视角**：NUMA感知的数据分区。在分布式数据库中，如果Partition的物理存储与查询它的Worker线程不在同一NUMA节点，每次数据访问都是远端访问，延迟翻倍。优化策略：(1) Partition按NUMA节点分布，Worker绑定在同一节点；(2) 使用`numactl --interleave=all`交错分配，均匀分布到所有节点（牺牲单次访问延迟，换取总体带宽平衡）；(3) Linux的`mm/mempolicy.c`提供`MPOL_BIND`/`MPOL_PREFERRED`/`MPOL_INTERLEAVE`三种策略，第29章会深入讨论。

> **AI视角**：GPU与主机内存的NUMA关系。多GPU服务器中，每个GPU通过PCIe连接到特定的NUMA节点。GPU访问远端节点的主机内存需要穿越UPI互连，带宽和延迟都受影响。NCCL的拓扑感知通信和CUDA的`cudaMemcpy`都会考虑NUMA距离。最佳实践：将GPU相关的CPU线程绑定到GPU所在的NUMA节点。

## 2.4 大页与TLB效率

### TLB覆盖的计算

TLB的覆盖范围 = TLB条目数 × 页大小。以Intel Skylake为例：

| 页大小 | L1 DTLB覆盖 | L2 STLB覆盖 |
|--------|------------|------------|
| 4 KB | 64 × 4K = 256 KB | 1536 × 4K = 6 MB |
| 2 MB | 64 × 2M = 128 MB | — |
| 1 GB | 专用条目 | — |

关键洞察：**4KB小页的L2 STLB只能覆盖6 MB**。这意味着任何工作集超过6 MB的热数据区都会遭遇TLB miss，每次miss带来100+周期的Page Table Walk代价。

### TLB miss率对大内存工作集的影响

以一个128 GB的数据库Buffer Pool为例：

- 4KB页：需要32M个页表项，L2 STLB的1536个条目只能覆盖0.005%
- 2MB大页：需要64K个页表项，L1 DTLB即可覆盖128 MB，L2 STLB的覆盖范围成倍扩展
- 1GB大页：只需128个页表项，L1 DTLB完全覆盖

TLB miss率直接影响内存访问延迟：

```
有效访存延迟 = TLB命中概率 × Cache命中延迟
             + TLB命中概率 × Cache miss延迟
             + TLB miss概率 × (Page Table Walk延迟 + 访存延迟)
```

假设4KB页的TLB miss率为5%，2MB大页的TLB miss率为0.1%：

- 4KB：5% × 200 cyc = 10 cyc 额外开销/访存
- 2MB：0.1% × 200 cyc = 0.2 cyc 额外开销/访存

50倍的差异，在高频内存访问场景（如数据库Buffer Pool扫描）中，累积效果惊人。

> **AI视角**：LLM推理的KV Cache为何需要大页。一个70B参数模型的推理，KV Cache可能占用数GB到数十GB。以4KB页映射，TLB miss率极高，每次自回归生成都需要遍历全部KV Cache——每个token的生成都伴随大量TLB miss。使用2MB大页可以将KV Cache的TLB覆盖范围从6 MB扩展到3 GB（L2 STLB），大幅减少Page Table Walk的开销。这也是vLLM等推理框架推荐使用大页的原因。

---

本章建立了对内存层次的精确认知：Cache层级与伪共享决定了数据结构设计，TLB与页表遍历决定了页大小选择，NUMA拓扑决定了数据放置策略。这三个硬件机制是第三篇内存管理的基石——伙伴系统需要NUMA感知、页面回收需要理解Cache行为、大页的动机就是TLB效率。理解硬件约束，才能理解软件设计的选择。
