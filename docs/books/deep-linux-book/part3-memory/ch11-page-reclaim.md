---
chapter: 11
part: 第三篇 内存管理 —— 最复杂的子系统
title: 页面回收与交换
source_anchor:
  - mm/vmscan.c
  - mm/swap.c
  - mm/swapfile.c
  - mm/swap_state.c
  - mm/zswap.c
  - mm/workingset.c
  - mm/shrinker.c
  - mm/damon/
status: done
---

# 第11章 页面回收与交换

## 写作目标

深入理解Linux页面回收的完整机制，掌握LRU双链、kswapd、交换、DAMON等核心组件。

## 章节大纲

### 11.1 LRU与页面老化

- LRU双链：active list与inactive list
- `mm/swap.c`：页面在LRU链表上的操作
  - `activate_page()`：从inactive提升到active
  - `deactivate_page()`：从active降级到inactive
  - PG_referenced标志与二次机会算法
- **精读** `mm/workingset.c`：工作集估计
  - shadow entry与refault距离
  - 工作集大小与内存压力的判断

### 11.2 kswapd与页面回收

- **精读** `mm/vmscan.c`（~7000行）：
  - `kswapd()`守护进程：水位线驱动的回收
  - `shrink_lruvec()`：LRU扫描与回收
  - `shrink_active_list()`：active链表的扫描
  - `shrink_inactive_list()`：inactive链表的扫描与回收
  - 匿名页与文件页的分流回收策略
  - `get_scan_count()`：扫描比例的计算
- `mm/shrinker.c`：shrinker框架——内核子系统注册自己的回收回调
  - `shrinker_debug.c`：shrinker调试接口

### 11.3 页面写回

- `mm/page-writeback.c`：脏页写回
  - 脏页比例与writeback阈值
  - `balance_dirty_pages()`：限速写回
- `mm/fs-writeback.c`：文件系统写回

### 11.4 交换：Swap与zswap

- **精读** `mm/swapfile.c`：交换区管理
  - swap slot分配与释放
  - swap cache
- **精读** `mm/swap_state.c`：swap cache实现
- **精读** `mm/zswap.c`：压缩交换
  - 压缩存储在内存中的swap
  - zswap与zram的区别
  - 压缩算法选择
- `mm/swap_cgroup.c`：swap的cgroup记账
- *数据库视角*：如何防止Buffer Pool页面被内核回收——mlock/madvise的策略

### 11.5 内存压缩(compaction)

- `mm/compaction.c`：内存碎片整理
  - 直接压缩与后台压缩
  - `compact_zone()`的实现
  - 迁移扫描器与空闲扫描器

### 11.6 OOM Killer

- `mm/oom_kill.c`：内存不足时的进程选择
  - `oom_badness()`：打分算法
  - cgroup OOM与系统级OOM
  - *AI视角*：推理服务的内存压力与OOM——如何设置memory.low/max保护关键服务

### 11.7 DAMON：数据访问监控

- **精读** `mm/damon/`：
  - `core.c`：DAMON核心——区域分割与访问检测
  - `vaddr.c`：虚拟地址空间监控
  - `paddr.c`：物理地址空间监控
  - `lru_sort.c`：基于访问模式的LRU排序——热页promote、冷页demote
  - `reclaim.c`：主动回收冷页
  - `sysfs.c`/`sysfs-schemes.c`：用户态接口
  - `tests/`：内核自测
- *数据库视角*：DAMON与Buffer Pool替换策略的类比
- *AI视角*：推理服务中KV Cache的热度感知管理

## 关键源文件清单

| 文件 | 行数 | 关注点 |
|------|------|--------|
| `mm/vmscan.c` | ~7000 | 页面回收核心 |
| `mm/swapfile.c` | ~3500 | 交换区管理 |
| `mm/zswap.c` | ~1500 | 压缩交换 |
| `mm/workingset.c` | ~600 | 工作集估计 |
| `mm/compaction.c` | ~2500 | 内存压缩 |
| `mm/oom_kill.c` | ~1200 | OOM Killer |
| `mm/damon/core.c` | ~1500 | DAMON核心 |

## 跨章依赖

- 依赖第10章（虚拟内存）：缺页处理是回收的逆过程
- 前置第12章（大页）：compaction是大页分配的前置条件
