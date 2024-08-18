---
chapter: 28
part: 第八篇 数据库与OS的深度对话
title: 存储引擎与OS的协作
source_anchor:
  - mm/fadvise.c
  - mm/madvise.c
  - fs/sync.c
  - mm/page-writeback.c
  - fs/fs-writeback.c
  - mm/filemap.c
  - fs/direct-io.c
  - fs/dax.c
  - mm/mmap.c
  - mm/mlock.c
status: done
---

# 第28章 存储引擎与OS的协作

## 写作目标

用前七篇的原理重新审视存储引擎与操作系统的协作关系，打通"理解OS→设计更好引擎"的链路。

## 章节大纲

### 28.1 Buffer Pool vs Page Cache：双缓冲问题

- 双缓冲的本质：数据库Buffer Pool与内核Page Cache各维护一份缓存
- 内存浪费：同一数据在内存中存在两份
- `POSIX_FADV_DONTNEED`：`mm/fadvise.c`——告诉内核哪些页面不再需要
- `MADV_DONTNEED`/`MADV_REMOVE`：`mm/madvise.c`——更精细的内存建议
- `O_DIRECT`绕过Page Cache：`fs/direct-io.c`
- 各大数据库的策略对比：
  - PostgreSQL：依赖OS Page Cache
  - MySQL InnoDB：O_DIRECT + 自管理Buffer Pool
  - RocksDB：直接I/O + 自管理缓存

### 28.2 WAL与fsync：持久化的内核路径

- **精读** `fs/sync.c`：
  - `do_fsync()`→`vfs_fsync()`→`blkdev_issue_flush()`
  - fsync的完整路径：数据+元数据+FLUSH
  - fdatasync：仅数据
- **精读** `block/blk-flush.c`：
  - FLUSH/FUA的块层实现
  - barrier语义与设备写缓存
- 掉电安全的完整链路：WAL写入→fsync→FLUSH→设备持久化
- *坑*：设备写缓存(WC)的谎言——fsync可能不保证持久化

### 28.3 Checkpoint与页面写回的交互

- **精读** `mm/page-writeback.c`：脏页写回
- **精读** `fs/fs-writeback.c`：写回工作线程
- Checkpoint触发的大量脏页与内核writeback的竞争
- `MADV_HUGEPAGE`/`MADV_NOHUGEPAGE`：THP建议

### 28.4 mmap在存储引擎中的争议

- **精读** `mm/mmap.c`的mmap路径
- mmap的优势：零拷贝读取、内核管理页面换入换出
- mmap的劣势：
  - 缺页中断的不可控延迟
  - 页面回收对延迟的影响
  - I/O调度的不可控性
- LMDB的mmap-first设计 vs InnoDB的O_DIRECT设计
- *源码实证*：`mm/memory.c`中缺页路径的延迟分析

### 28.5 DAX：持久内存的直接访问

- **精读** `fs/dax.c`：
  - DAX(Direct Access)：绕过Page Cache直接访问持久内存
  - PMEM的原子写入语义
  - *数据库视角*：NVM-aware存储引擎的设计

### 28.6 mlock与内存锁定

- **精读** `mm/mlock.c`：
  - mlock/munlock：锁定页面不被回收
  - RLIMIT_MEMLOCK的限制
  - *数据库视角*：锁定Buffer Pool的关键页面

## 关键源文件清单

| 文件 | 行数 | 关注点 |
|------|------|--------|
| `mm/fadvise.c` | ~200 | fadvise实现 |
| `mm/madvise.c` | ~800 | madvise实现 |
| `fs/sync.c` | ~200 | 同步语义 |
| `block/blk-flush.c` | ~400 | FLUSH/FUA |
| `fs/dax.c` | ~1500 | DAX直接访问 |
| `mm/mlock.c` | ~600 | 内存锁定 |

## 跨章依赖

- 综合运用第9-12章（内存管理）、第21-22章（块层与文件系统）
