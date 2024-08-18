# 第11章 页面回收与交换

> 源码锚点：`mm/vmscan.c`、`mm/swap.c`、`mm/swapfile.c`、`mm/zswap.c`、`mm/workingset.c`、`mm/compaction.c`、`mm/oom_kill.c`、`mm/damon/`

物理内存是有限资源。当可用内存低于水位线时，内核必须回收页面——将不活跃的页面释放或写入交换区。本章深入页面回收的完整机制：LRU老化、kswapd守护、交换、压缩和OOM。

## 11.1 LRU与页面老化

### LRU双链

Linux使用双链表近似LRU(Least Recently Used)：

```
Active list: 最近被访问的页面
  ↕ (双向迁移)
Inactive list: 最近未被访问的页面
```

页面在双链表间的迁移：
- 新分配的页面进入inactive链表头部
- 被再次访问时从inactive提升到active（`activate_page()`）
- active链表尾部的页面被降级到inactive（`deactivate_page()`）
- inactive链表尾部的页面被回收

### 二次机会算法

LRU双链实现了"二次机会"(Second Chance)——页面进入inactive后，如果被访问过（PG_referenced标志），不会被立即回收，而是提升到active。只有经过两次检查都未被访问的页面才被回收：

```
新页面 → inactive(第1次机会)
  ↓ 被访问 → active
  ↓ 未被访问，降到inactive尾部(第2次机会)
  ↓ 仍未被访问 → 回收
```

### workingset：工作集估计

`mm/workingset.c`实现了工作集大小估计，核心是**refault距离**：

当页面从inactive链表被回收后，其在LRU中的位置被一个"shadow entry"记录。如果该页面很快被重新访问(refault)，通过shadow entry计算"refault距离"——距离越短，说明工作集越大、内存越紧张。

```c
// mm/workingset.c (简化)
// refault距离 < inactive链表大小 → 工作集 > 可用内存 → 内存压力
// 将refault页面直接提升到active链表，避免再次被回收
```

refault距离的核心洞察：如果一个页面被回收后很快又被访问，说明它属于活跃工作集，不应该被回收。工作集估计帮助内核区分"暂时不用但会再用"和"真的不再用"的页面。

## 11.2 kswapd与页面回收

### kswapd守护进程

每个NUMA节点一个kswapd守护进程，在后台执行页面回收：

```c
// mm/vmscan.c (简化)
static int kswapd(void *p)
{
    for (;;) {
        // 等待唤醒——zone空闲页低于low水位线
        wait_event_interruptible(pgdat->kswapd_wait, ...);

        // 循环回收直到空闲页高于high水位线
        while (pgdat->nr_free_pages < high_wmark_pages(zone)) {
            balance_pgdat(pgdat, ...);
        }
    }
}
```

### shrink_lruvec()：LRU扫描与回收

```c
// mm/vmscan.c
static void shrink_lruvec(struct lruvec *lruvec, struct scan_control *sc)
{
    // 计算每种类型页面的扫描数量
    get_scan_count(lruvec, sc);

    // 扫描inactive链表
    shrink_inactive_list(nr_to_scan, lruvec, sc, LRU_INACTIVE_FILE);
    shrink_inactive_list(nr_to_scan, lruvec, sc, LRU_INACTIVE_ANON);

    // 扫描active链表（降级到inactive）
    shrink_active_list(nr_to_scan, lruvec, sc, LRU_ACTIVE_FILE);
    shrink_active_list(nr_to_scan, lruvec, sc, LRU_ACTIVE_ANON);
}
```

`get_scan_count()`根据内存压力和配置计算各类页面的扫描比例。匿名页和文件页有不同的回收策略：
- **文件页**：干净页直接丢弃（可从文件重新读取），脏页写回后丢弃
- **匿名页**：必须写入swap后才能回收，代价更高

`swappiness`参数(0-200)控制匿名页和文件页的回收偏好：值越高，越倾向回收匿名页；值为0时，尽量不回收匿名页（除非内存极度紧张）。

### shrinker框架

内核子系统（如dentry缓存、inode缓存）通过`register_shrinker()`注册自己的回收回调：

```c
// mm/shrinker.c
struct shrinker {
    unsigned long (*count_objects)(struct shrinker *, ...);
    unsigned long (*scan_objects)(struct shrinker *, ...);
    int seeks;     // 回收代价（越大越不倾向回收）
    int batch;     // 每次回收数量
};
```

页面回收时，shrinker被调用来释放内核缓存中的对象——如`shrink_dentry_cache()`释放未使用的dentry，`shrink_icache_sb()`释放未使用的inode。

## 11.3 页面写回

脏页必须写回存储设备后才能回收。`mm/page-writeback.c`管理脏页的写回策略：

- **后台写回**：当脏页比例超过`background_ratio`(默认10%)，唤醒`flusher`线程写回
- **限速写回**：当脏页比例超过`dirty_ratio`(默认20%)，`balance_dirty_pages()`限制产生脏页的进程
- **周期写回**：定期写回存在超过`dirty_expire_interval`(默认30秒)的脏页

限速机制对数据库写入性能有直接影响——大量WAL写入可能触发限速，导致事务提交延迟增加。

## 11.4 交换：Swap与zswap

### swap的原理

当物理内存不足时，匿名页被写入swap设备，释放物理页面。访问swap中的页面时触发缺页，内核将其读回内存。

```c
// mm/swapfile.c
// swap slot分配：从swap area中找到空闲slot
swp_entry_t get_swap_page()

// swap out：将页面写入swap
int swap_writepage(struct page *page, struct writeback_control *wbc)

// swap in：从swap读回页面
struct page *swap_readahead(swp_entry_t entry)
```

### swap cache

swap cache(`mm/swap_state.c`)是swap子系统的缓存——已经被写入swap但仍在内存中的页面同时在swap cache中。这避免了重复写入——如果页面被swap out后又被访问，页面既在内存中也在swap中，后续swap out只需更新即可。

### zswap：压缩交换

`mm/zswap.c`将swap页面压缩后存储在内存中，而不是写入磁盘：

```
匿名页 → zswap压缩 → 存储在内存的压缩池中
                      (压缩比通常2:1到5:1)
```

zswap的优势：避免磁盘I/O，swap in只需解压而非磁盘读取。代价是消耗CPU进行压缩/解压，以及压缩池占用的内存。

zswap vs zram：
- **zswap**：压缩缓存层，后端仍使用真实swap设备，压缩池满时写回磁盘
- **zram**：基于RAM的块设备，所有swap都在内存中，无磁盘后端

> **数据库视角**：如何防止Buffer Pool页面被内核回收。数据库的Buffer Pool是性能关键——页面被回收和swap out会导致查询延迟飙升。防护策略：1) `mlock()`锁定关键页面（如WAL缓冲区）；2) `madvise(MADV_HUGEPAGE)`使用大页减少TLB miss；3) 设置`vm.swappiness=0`最小化swap；4) 设置cgroup `memory.low`保护Buffer Pool；5) 监控`/proc/vmstat`的`pgmajfault`指标，及时发现swap in。

## 11.5 内存压缩(compaction)

伙伴系统可能无法分配大块连续内存（外部碎片），即使总空闲内存足够。compaction通过迁移页面来消除碎片：

```c
// mm/compaction.c
// 两个扫描器从zone两端向中间移动：
// 迁移扫描器：找到可移动的页面
// 空闲扫描器：找到空闲的页面块
// 将迁移扫描器找到的页面搬到空闲扫描器找到的位置
```

compaction与大页分配密切相关——THP需要2MB连续物理页，compaction为THP创造条件。直接compaction在分配路径中同步执行，后台compaction由kcompactd守护进程执行。

## 11.6 OOM Killer

当所有回收手段都失败时，OOM Killer选择一个进程杀死，释放内存：

```c
// mm/oom_kill.c
long oom_badness(struct task_struct *p, ...)
{
    // 打分公式：内存占用 × (10 + oom_score_adj) / 1000
    // oom_score_adj: -1000(永不杀) 到 1000(优先杀)
    points = get_mm_rss(p->mm) + get_mm_counter(p->mm, MM_SWAPENTS) +
             mm_pgtables_bytes(p->mm) / PAGE_SIZE;
    return points;
}
```

OOM Killer选择内存占用最大的进程——这通常意味着数据库进程首当其冲。防护：设置`oom_score_adj=-1000`使关键进程免疫OOM。

cgroup OOM与系统级OOM的区别：cgroup OOM只在cgroup内部选择，系统级OOM在整个系统中选择。cgroup `memory.oom_group`设置后，OOM时杀死cgroup中的所有进程。

## 11.7 DAMON：数据访问监控

DAMON(Data Access MONitor)是Linux 5.15引入的内存访问模式监控框架：

```
DAMON架构：
用户态接口(sysfs) → DAMON核心 → 访问检测 → 操作方案
                   (core.c)   (vaddr/paddr) (lru_sort/reclaim)
```

### 核心机制

DAMON将地址空间划分为**区域(region)**，对每个区域采样检测访问状态：

```c
// mm/damon/core.c
// 1. 初始：将地址空间划分为若干区域
// 2. 采样：在每个区域中随机选取一个页面，检查Accessed位
// 3. 自适应调整：合并访问模式相似的区域，分裂访问模式变化的区域
// 4. 统计：计算每个区域的访问频率
```

DAMON的采样频率和区域大小可以自适应调整——活跃区域被更细粒度地监控，不活跃区域被合并。这保证了低开销（通常<1% CPU）和合理的精度。

### 基于DAMON的LRU排序

`mm/damon/lru_sort.c`根据DAMON的访问模式主动调整页面在LRU中的位置：
- 热页(hot)：提升到active链表，防止被回收
- 冷页(cold)：降级到inactive链表尾部，优先回收

这比传统的被动LRU更精确——DAMON基于实际的访问模式，而非等待页面自然老化。

### 基于DAMON的主动回收

`mm/damon/reclaim.c`在内存压力出现前主动回收冷页——比kswapd更早、更有针对性地回收。

> **数据库视角**：DAMON与Buffer Pool替换策略的类比。数据库的Buffer Pool替换策略(LRU/LFU/Clock)与内核的页面回收策略面临相同问题——如何识别热页和冷页。DAMON的自适应采样思想可以启发Buffer Pool的优化：不必扫描整个Buffer Pool，而是采样检测页面的访问模式，动态调整替换优先级。

> **AI视角**：推理服务中KV Cache的热度感知管理。LLM推理的KV Cache占用大量GPU显存，不同请求的KV Cache热度差异巨大——正在生成的token的KV Cache是热的，已完成的请求的KV Cache是冷的。DAMON的思想可以应用到KV Cache管理：监控KV Cache的访问模式，热页保留在GPU显存，冷页降级到主机内存或CXL内存，按需换入。

---

本章建立了对页面回收完整机制的认知：LRU双链实现页面老化，kswapd在后台回收，swap将匿名页换出到磁盘，zswap在内存中压缩存储，compaction消除碎片，OOM在极端情况下杀死进程，DAMON提供精确的访问模式监控。第12章将讨论大页如何减少TLB压力，以及KSM如何合并相同页面。
