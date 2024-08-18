---
chapter: 22
part: 第六篇 I/O与存储栈 —— 数据的完整通路
title: 文件系统
source_anchor:
  - fs/super.c
  - fs/inode.c
  - fs/dcache.c
  - fs/namei.c
  - fs/file.c
  - mm/filemap.c
  - fs/direct-io.c
  - fs/ext4/
  - fs/xfs/
  - fs/btrfs/
  - fs/iomap/
  - fs/netfs/
  - fs/fs-writeback.c
  - fs/sync.c
status: done
---

# 第22章 文件系统

## 写作目标

深入理解VFS核心抽象、Page Cache机制、Ext4/XFS/Btrfs的设计，以及现代文件系统基础设施(iomap/netfs)。

## 章节大纲

### 22.1 VFS四对象

- **精读** `fs/super.c`：superblock——文件系统实例
- **精读** `fs/inode.c`：inode——文件元数据
- **精读** `fs/dcache.c`：dentry——目录项缓存
  - dentry缓存与LRU回收
- **精读** `fs/file.c`：file——打开文件描述
- `fs/namei.c`：路径名解析
  - `path_lookup()`：从路径到inode的查找
  - RCU路径查找：无锁快速路径

### 22.2 Page Cache

- **精读** `mm/filemap.c`：
  - 页缓存：文件数据的内存缓存
  - 读路径：`filemap_read()`→检查缓存→命中返回/未命中从磁盘读
  - 写路径：`filemap_write()`→写入缓存→标记脏页→延迟写回
  - 预读：`mm/readahead.c`
- `fs/fs-writeback.c`：脏页写回
  - `wb_writeback()`：写回工作线程
  - 脏页过期与主动同步

### 22.3 Ext4

- `fs/ext4/` 目录概览
- 日志系统(jbd2)：`fs/jbd2/`
  - 事务模型：handle→transaction→commit
  - 日志模式：journal/ordered/writeback
- Extent映射：`fs/ext4/extents.c`
- Fast Commit：`fs/ext4/fast_commit.c`
- Delayed Allocation：延迟块分配减少碎片
- *数据库视角*：Ext4 ordered模式对WAL持久性的保障

### 22.4 XFS

- `fs/xfs/` 目录概览
- 分配组(Allocation Group)：并发扩展
- B+树索引
- 日志：`fs/xfs/xfs_log.c`
- 扩展属性与 reflink
- *数据库视角*：XFS的并发分配对高并发写入场景的优势

### 22.5 Btrfs

- `fs/btrfs/` 目录概览
- COW(Copy-On-Write)：数据与元数据的写时复制
- 子卷(Subvolume)与快照
- 校验和(Checksum)：数据完整性保障
- 多设备管理：条带化/镜像
- *数据库视角*：COW与数据库MVCC的类比

### 22.6 iomap与netfs：现代基础设施

- **精读** `fs/iomap/`：
  - iomap：基于范围的I/O映射抽象
  - `buffered-io.c`：缓冲I/O
  - `direct-io.c`：直接I/O
  - 替代传统buffer_head的轻量接口
- **精读** `fs/netfs/`：
  - netfs：网络文件系统辅助层
  - fscache：本地缓存框架
  - `read_collect.c`/`write_issue.c`：读写管线

### 22.7 O_DIRECT与同步语义

- **精读** `fs/direct-io.c`：O_DIRECT实现
  - 绕过Page Cache直接I/O
  - 对齐要求与限制
- **精读** `fs/sync.c`：
  - fsync/fdatasync/sync的内核路径
  - 文件元数据与数据的持久化顺序
- *数据库视角*：O_DIRECT的设计动机——消除双缓冲，掌控I/O调度

## 关键源文件清单

| 文件/目录 | 行数 | 关注点 |
|-----------|------|--------|
| `mm/filemap.c` | ~3500 | Page Cache |
| `fs/ext4/` | — | Ext4全家桶 |
| `fs/xfs/` | — | XFS全家桶 |
| `fs/btrfs/` | — | Btrfs全家桶 |
| `fs/iomap/` | — | iomap基础设施 |
| `fs/direct-io.c` | ~600 | O_DIRECT |
| `fs/sync.c` | ~200 | 同步语义 |

## 跨章依赖

- 依赖第21章（块层）：文件系统通过bio提交I/O
- 依赖第10章（虚拟内存）：Page Cache使用address_space映射
- 前置第23章（io_uring）：io_uring的文件I/O操作
