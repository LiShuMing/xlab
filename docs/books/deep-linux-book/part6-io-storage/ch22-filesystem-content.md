# 第22章 文件系统

> 源码锚点：`fs/super.c`、`fs/inode.c`、`fs/dcache.c`、`fs/namei.c`、`mm/filemap.c`、`fs/ext4/`、`fs/xfs/`、`fs/iomap/`、`fs/direct-io.c`、`fs/sync.c`

文件系统是用户数据与存储设备之间的桥梁——将字节流组织为文件，将文件组织为目录树，提供持久性、一致性和并发访问的保证。Linux通过VFS(Virtual File System)统一不同文件系统的接口，通过Page Cache加速文件访问。

## 22.1 VFS四对象

### superblock：文件系统实例

superblock代表一个已挂载的文件系统实例：

```c
// fs/super.c
struct super_block {
    dev_t               s_dev;          // 设备号
    unsigned long       s_flags;        // 挂载标志
    const struct super_operations *s_op;  // 操作集
    struct dentry       *s_root;        // 根dentry
    struct xattr_handler **s_xattr;     // 扩展属性
    struct list_head    s_inodes;       // 所有inode链表
    // ...
};
```

`super_operations`提供文件系统级别的操作：`alloc_inode()`/`destroy_inode()`/`write_inode()`/`evict_inode()`等。每个文件系统类型(Ext4/XFS/Btrfs)注册自己的`super_operations`。

### inode：文件元数据

inode是文件的核心——存储元数据(大小/权限/时间戳)和数据块映射：

```c
// fs/inode.c
struct inode {
    umode_t         i_mode;         // 文件类型和权限
    loff_t          i_size;         // 文件大小
    struct timespec i_atime/mtime/ctime;  // 访问/修改/变更时间
    const struct inode_operations *i_op;  // inode操作
    const struct file_operations  *i_fop; // 文件操作
    struct address_space *i_mapping;      // 页缓存映射
    struct super_block *i_sb;             // 所属superblock
    // ...
};
```

`inode_operations`：`lookup()`(目录查找)、`create()`(创建文件)、`link()`/`unlink()`(硬链接)、`rename()`等。
`file_operations`：`read()`/`write()`/`mmap()`/`fsync()`/`ioctl()`等——进程通过fd操作文件时调用。

### dentry：目录项缓存

dentry将路径名映射到inode——是路径查找的核心加速结构：

```c
// fs/dcache.c
struct dentry {
    struct qstr         d_name;     // 名称
    struct inode        *d_inode;   // 关联的inode
    struct dentry       *d_parent;  // 父dentry
    struct list_head    d_child;    // 兄弟链表
    struct list_head    d_subdirs;  // 子目录链表
    // ...
};
```

dentry缓存(dcaching)是VFS最重要的优化——路径查找时，每个路径分量在dentry缓存中查找，命中则直接获取inode，否则读取磁盘目录项并创建新dentry。

dentry LRU回收：当内存紧张时，未使用的dentry从LRU链表回收——释放关联的inode和内存。

### file：打开文件描述

```c
// fs/file.c
struct file {
    struct path     f_path;         // dentry + vfsmount
    const struct file_operations *f_op;
    loff_t          f_pos;          // 文件偏移量
    unsigned int    f_flags;        // 打开标志(O_RDONLY/O_DIRECT/...)
    // ...
};
```

进程通过fd（文件描述符）引用`file`对象——`fdtable`数组索引到`file`指针。

### 路径名解析

`fs/namei.c`实现路径名解析——将路径字符串转换为dentry+inode：

```
path_lookup("/home/user/file.txt")
  → 查找根dentry "/"
  → 在"/"的子目录中查找"home" → 获取home的dentry
  → 在"home"的子目录中查找"user" → 获取user的dentry
  → 在"user"的目录中查找"file.txt" → 获取file.txt的dentry+inode
```

**RCU路径查找**：无锁快速路径——在RCU读锁保护下遍历dentry缓存，不获取任何自旋锁。大部分路径查找通过RCU路径完成，只在需要修改或遇到并发修改时降级到锁路径。

## 22.2 Page Cache

### 页缓存：文件数据的内存缓存

`mm/filemap.c`是Page Cache的核心——文件数据缓存在内存中，避免重复磁盘I/O：

```c
// 每个inode有一个address_space管理页缓存
struct address_space {
    struct inode        *host;          // 所属inode
    struct xarray       i_pages;       // 页缓存(XArray索引)
    unsigned long       nrpages;       // 缓存页数
    unsigned long       nrexceptional; // DAX/换出项
    const struct address_space_operations *a_ops;
};
```

XArray按页索引(page index)组织缓存页——查找第N页时，在XArray中查找index=N的条目。

### 读路径

```
filemap_read()
  → 在address_space中查找页
  → 命中 → 返回数据
  → 未命中 → 分配新页，调用a_ops->readpage()从磁盘读取
            → 加入页缓存，返回数据
```

预读(readahead)：检测到顺序访问模式时，预读后续页面——减少I/O次数。`mm/readahead.c`实现自适应预读算法。

### 写路径

```
write() → 写入Page Cache（不立即写磁盘）
  → 标记页为脏(PG_dirty)
  → 延迟写回：定时器/内存压力触发

fsync() → 确保脏页写回磁盘
  → 提交脏页对应的bio
  → 等待I/O完成
  → 提交FLUSH确保数据持久化
```

### 脏页写回

`fs/fs-writeback.c`管理脏页写回：

- **周期写回**：`wb_writeback()`内核线程定期扫描脏页，超过30秒的脏页强制写回
- **内存压力写回**：空闲内存不足时，唤醒写回线程
- **主动同步**：`fsync()`/`sync()`触发立即写回

## 22.3 Ext4

### 日志系统(jbd2)

Ext4的日志系统(jbd2)保证文件系统一致性——崩溃后通过日志恢复：

```
事务模型：
  1. handle = journal_start()    → 开始事务
  2. 修改元数据(带handle)        → 记录到日志
  3. journal_stop(handle)        → 结束事务
  4. commit                      → 日志提交到磁盘
  5. checkpoint                  → 元数据写回最终位置，释放日志空间
```

三种日志模式：
- **journal**：数据和元数据都写入日志——最安全，最慢
- **ordered**(默认)：元数据写入日志，数据在元数据之前写回——保证元数据指向的数据块是有效的
- **writeback**：仅元数据写入日志——最快，崩溃后可能看到旧数据

### Extent映射

Ext4使用extent(而非传统块映射)描述文件数据位置：

```
一个extent: [逻辑起始块, 长度, 物理起始块]
  → 代替逐块的间接映射
  → 大文件只需少量extent——减少元数据开销
```

`fs/ext4/extents.c`实现extent树——支持大文件的稀疏映射。

### Fast Commit

`fs/ext4/fast_commit.c`是jbd2的优化——轻微的元数据修改(如时间戳更新)不写入完整日志，只记录变更的差量。减少日志I/O量。

### Delayed Allocation

Ext4延迟块分配——`write()`只写入Page Cache，不分配磁盘块。直到`fsync()`或写回时才分配。这减少了碎片——分配器可以基于全局信息选择最优位置。

> **数据库视角**：Ext4的ordered模式对WAL持久性的保障。数据库的WAL文件使用O_DIRECT+fsync——O_DIRECT绕过Page Cache，fsync确保数据到达磁盘。在ordered模式下，即使不使用O_DIRECT，元数据日志也保证数据先于元数据写回——WAL写入后即使崩溃也不会丢失。

## 22.4 XFS

### 分配组(Allocation Group)

XFS将设备分为多个AG(Allocation Group)——每个AG有独立的superblock、空间位图和inode位图：

```
AG0: [superblock | 空间位图 | inode位图 | 数据块...]
AG1: [superblock | 空间位图 | inode位图 | 数据块...]
...
```

多AG允许并发分配——不同CPU在不同AG中分配空间，无需全局锁。这是XFS在高并发写入场景优于Ext4的关键。

### B+树索引

XFS广泛使用B+树——空间管理、extent映射、目录项都使用B+树索引。B+树的高度平衡确保O(log n)的查找效率。

### Reflink

XFS支持reflink(写时复制链接)——两个文件共享相同的数据块，修改时才复制：

```
文件A ──→ 数据块P
文件B ──→ 数据块P (reflink)
修改B → 复制P到P' → B指向P'
```

reflink是快照的基础——数据库的快照备份可以使用reflink实现秒级快照。

> **数据库视角**：XFS的并发分配对高并发写入的优势。数据库的Buffer Pool刷脏页时，多个线程并发写不同表空间——XFS的多AG允许这些写入在不同AG中并行分配，不竞争同一把锁。PostgreSQL推荐XFS作为生产文件系统。

## 22.5 Btrfs

### COW(Copy-On-Write)

Btrfs是全COW文件系统——任何修改都写入新位置，不覆盖旧数据：

```
修改数据块P：
  1. 分配新块P'
  2. 写入修改后的数据到P'
  3. 更新父节点指向P'（父节点也需要COW）
  4. 一路向上COW直到根节点
  5. 原子切换根指针——新树可见，旧树保留给快照
```

COW保证崩溃一致性——写操作要么完全可见，要么完全不可见。不需要传统日志。

### 子卷与快照

Btrfs的子卷是独立的文件树——共享底层的chunk分配池。快照是子卷的COW副本——创建快照只复制元数据树，不复制数据。

### 校验和

Btrfs为每个数据块存储校验和(checksum)——读取时验证，检测静默数据损坏。这是数据库文件系统的重要特性——磁盘可能返回错误数据而不报告错误。

> **数据库视角**：COW与数据库MVCC的类比。Btrfs的COW保证"读取看到一致性快照"——类似于MVCC的快照隔离。数据库的WAL写入是append-only的——与COW的"只写新位置"天然契合。

## 22.6 iomap与netfs：现代基础设施

### iomap

`fs/iomap/`提供基于范围的I/O映射抽象——替代传统的buffer_head接口：

```c
// iomap描述一段连续的磁盘映射
struct iomap {
    u64     addr;       // 磁盘偏移
    u64     offset;     // 文件偏移
    u64     length;     // 长度
    u16     type;       // IOMAP_MAPPED/IOMAP_HOLE/IOMAP_UNWRITTEN
    // ...
};
```

iomap更轻量——一次映射大范围，而非逐块映射。XFS和ext4(部分)已迁移到iomap。

### netfs

`fs/netfs/`为网络文件系统(CIFS/NFS/9p)提供辅助层——统一缓存和读写逻辑，减少重复代码。fscache提供本地缓存框架——网络文件系统的数据缓存在本地磁盘，减少网络往返。

## 22.7 O_DIRECT与同步语义

### O_DIRECT

O_DIRECT绕过Page Cache——数据直接在用户缓冲区和磁盘之间传输：

```
O_DIRECT写：用户缓冲区 → DMA → 磁盘
普通写：    用户缓冲区 → Page Cache → 延迟写回 → 磁盘
```

O_DIRECT的限制：缓冲区必须对齐(通常512字节或4K)，长度必须是扇区的整数倍。

数据库使用O_DIRECT的原因——**消除双缓冲**：数据库有自己的Buffer Pool(Page Cache)，如果文件系统也有Page Cache，同一数据在内存中存在两份——浪费内存且增加一致性管理的复杂度。

### fsync/fdatasync/sync

```c
// fs/sync.c
// fsync(fd)：确保文件数据+元数据持久化
// fdatasync(fd)：仅确保数据持久化(元数据非必要时不同步)
// sync()：所有文件系统的脏数据写回
```

fsync的完整路径：
```
fsync(fd)
  → 文件系统：将inode的脏页提交为bio
  → 块层：提交bio
  → 驱动：写入设备
  → 块层：提交FLUSH(确保设备写缓存刷出)
  → 等待所有I/O完成
```

这是数据库事务提交的关键路径——WAL的fsync延迟直接影响事务吞吐。

> **数据库视角**：O_DIRECT的设计动机——消除双缓冲，掌控I/O调度。数据库的Buffer Pool知道哪些页即将被访问、哪些页可以被牺牲——比操作系统的Page Cache更智能。使用O_DIRECT后，数据库完全掌控I/O调度：后台刷脏页与前台查询I/O的优先级、WAL写的优先级等。

---

本章建立了对Linux文件系统的完整认知：VFS四对象(superblock/inode/dentry/file)统一文件系统接口，Page Cache加速文件访问，Ext4的jbd2日志保证一致性，XFS的多AG支持并发分配，Btrfs的全COW提供快照和校验和，iomap/netfs是现代基础设施，O_DIRECT让数据库掌控I/O调度。
