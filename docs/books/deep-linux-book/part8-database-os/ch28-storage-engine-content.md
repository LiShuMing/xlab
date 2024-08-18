# 第28章 存储引擎与OS的协作

> 源码锚点：`mm/fadvise.c`、`mm/madvise.c`、`fs/sync.c`、`block/blk-flush.c`、`mm/page-writeback.c`、`fs/dax.c`、`mm/mlock.c`

存储引擎是数据库与操作系统交互最密集的组件——Buffer Pool管理、WAL持久化、Checkpoint写回，每一步都依赖OS的内存和I/O服务。理解OS的内部机制，才能设计出与OS高效协作的存储引擎。

## 28.1 Buffer Pool vs Page Cache：双缓冲问题

### 双缓冲的本质

数据库Buffer Pool缓存数据页，内核Page Cache也缓存文件数据——同一数据在内存中存在两份。这是内存浪费——64GB内存的机器，双缓冲可能浪费20-30GB。

### 各大数据库的策略

| 数据库 | 策略 | Buffer Pool | Page Cache |
|--------|------|-------------|------------|
| PostgreSQL | 依赖OS | 共享Buffer | 大量使用 |
| MySQL InnoDB | O_DIRECT | 自管理 | 绕过 |
| RocksDB | 直接I/O+自管理缓存 | 自管理Block Cache | 绕过 |

PostgreSQL的设计哲学：利用OS Page Cache——OS比应用更了解全局内存压力，且PostgreSQL的Buffer Pool较小(通常几百MB)，剩余内存留给Page Cache。但这意味着双缓冲——同一页可能同时在Buffer Pool和Page Cache中。

InnoDB的设计哲学：O_DIRECT绕过Page Cache——InnoDB自己管理Buffer Pool，不需要OS代劳。通过`innodb_flush_method=O_DIRECT`设置。

### POSIX_FADV_DONTNEED与MADV_DONTNEED

无法使用O_DIRECT时，可以通过建议性接口减少双缓冲：

```c
// mm/fadvise.c
posix_fadvise(fd, offset, len, POSIX_FADV_DONTNEED);
// → 告诉内核这些页面不再需要 → 内核可以释放Page Cache中的对应页

// mm/madvise.c
madvise(addr, len, MADV_DONTNEED);
// → 直接丢弃指定范围的页面映射 → 下次访问需要重新从磁盘读取
```

注意：`POSIX_FADV_DONTNEED`只是建议——内核可能忽略。`MADV_DONTNEED`更强——立即丢弃页面。

## 28.2 WAL与fsync：持久化的内核路径

### fsync的完整路径

```
fsync(fd)
  → do_fsync() → vfs_fsync() → ext4_sync_file()
    → 提交inode的脏页为bio → 写入设备
    → 提交日志(如果有) → 确保元数据持久化
    → blkdev_issue_flush() → 发送FLUSH命令
      → 设备刷出写缓存 → 数据真正持久化
```

### FLUSH/FUA与设备写缓存

`block/blk-flush.c`实现FLUSH/FUA语义：

- **FLUSH**：告诉设备"把写缓存中的数据刷到持久介质"——确保之前的写入真正持久化
- **FUA(Force Unit Access)**：告诉设备"这份数据绕过写缓存，直接写入持久介质"

大多数SSD有易失性写缓存(Write Back Cache)——fsync只保证数据到达设备写缓存，不一定到达闪存芯片。如果fsync后立即掉电，数据可能丢失。FLUSH命令强制设备刷出写缓存——这才是真正的持久化保证。

### 设备写缓存的谎言

某些设备的FLUSH实现是空操作——声称数据已持久化但实际仍在缓存中。数据库管理员应验证设备的FLUSH语义——通过掉电测试确认数据真正持久化。

掉电安全的完整链路：
```
WAL写入 → fsync → FLUSH → 设备刷写缓存 → 数据到达闪存 → 真正持久化
```

## 28.3 Checkpoint与页面写回的交互

### Checkpoint触发的I/O风暴

数据库Checkpoint需要将大量脏页写回磁盘——可能瞬间产生大量写I/O。内核的writeback也有自己的节奏——两者竞争I/O带宽：

```
Checkpoint → 大量脏页写回 → 填满设备写队列
  → 前台查询的读I/O被排队 → 延迟飙升
```

优化策略：
- **分摊Checkpoint**：将一次大量写回分散到长时间段内——InnoDB的模糊Checkpoint
- **I/O优先级**：Checkpoint的写I/O使用低优先级——不阻塞前台读I/O
- **fadvise提示**：Checkpoint写完的页面使用`POSIX_FADV_DONTNEED`释放Page Cache

### THP建议

```c
madvise(addr, len, MADV_HUGEPAGE);    // 使用透明大页——减少TLB缺失
madvise(addr, len, MADV_NOHUGEPAGE);   // 禁用大页——防止碎片化
```

数据库Buffer Pool通常启用THP——大页减少页表项数量，减少TLB缺失。但KHugepaged的后台整理可能引入延迟——数据库应预先分配大页(`vm.nr_hugepages`)而非依赖运行时整理。

## 28.4 mmap在存储引擎中的争议

### mmap的优势

- **零拷贝读取**：数据直接在进程地址空间中访问，无需read()系统调用
- **内核管理页面换入换出**：不需要应用自己实现页面替换算法
- **代码简洁**：mmap后像访问内存一样访问文件

### mmap的劣势

- **缺页中断的不可控延迟**：页面不在内存时触发缺页中断——延迟取决于I/O速度，且无法取消
- **I/O调度不可控**：缺页触发的读I/O由内核发起，应用无法指定优先级或调度策略
- **页面回收干扰**：内核可能回收正在使用的页面——导致不可控的缺页中断
- **信号处理复杂**：SIGBUS(文件截断)和SIGSEGV(映射失败)需要特殊处理
- **无法异步I/O**：mmap的缺页是同步的——无法与io_uring集成

### LMDB vs InnoDB

- **LMDB**：mmap-first设计——所有数据通过mmap访问，利用OS的页面管理。适合读多写少、数据量不超过内存的场景
- **InnoDB**：O_DIRECT设计——自己管理Buffer Pool，完全控制I/O。适合高并发写入、数据量超过内存的场景

> **源码实证**：`mm/memory.c`中缺页路径的延迟分析。缺页中断→`do_page_fault()`→`handle_mm_fault()`→`__do_fault()`→文件系统readpage→bio提交→等待I/O完成。整个路径涉及多次锁获取和函数调用——延迟在100μs到10ms之间，远高于Buffer Pool命中的100ns。

## 28.5 DAX：持久内存的直接访问

### DAX机制

`fs/dax.c`实现DAX(Direct Access)——绕过Page Cache直接访问持久内存(PMEM)：

```
传统路径：文件读取 → Page Cache → 数据拷贝
DAX路径：  文件读取 → 直接访问PMEM的物理地址 → 无数据拷贝
```

DAX不需要Page Cache——PMEM本身就是持久的，不需要内核缓存。缺页中断时，直接映射PMEM的物理页到进程地址空间——没有I/O操作。

### PMEM的原子写入

PMEM的写入需要显式刷新——CPU写入先进入缓存，必须通过`clwb`/`clflushopt`刷出缓存行，再通过`sfence`确保顺序。DAX在文件系统层面处理这些刷新——应用使用fsync确保数据持久化。

> **数据库视角**：NVM-aware存储引擎的设计。PMEM的延迟约200-300ns——比DRAM慢5-10倍，但比NVMe SSD快1000倍。NVM-aware存储引擎将热数据放DRAM、温数据放PMEM、冷数据放SSD——构建三级存储层次。PMEM还可用于WAL——fsync在PMEM上几乎免费(无需FLUSH命令)。

## 28.6 mlock与内存锁定

### mlock机制

`mm/mlock.c`实现mlock——锁定页面不被回收：

```c
mlock(addr, len);   // 锁定指定地址范围的页面
mlockall(MCL_CURRENT | MCL_FUTURE);  // 锁定所有当前和未来的页面
```

锁定后的页面不会被内核回收——即使内存紧张也不换出。这对延迟敏感的应用很重要——Buffer Pool的关键页面(如索引根节点)被锁定后，不会因内存压力产生不可控的缺页中断。

RLIMIT_MEMLOCK限制非特权用户的锁定内存量——默认8KB。数据库通常以root运行或提高此限制。

> **数据库视角**：锁定Buffer Pool的关键页面。Oracle SGA的"锁住SGA"功能使用mlockall——确保整个共享内存区不被换出。Redis的`--lock-memory`选项类似。对于延迟敏感的数据库操作，mlock消除了页面回收引入的不可控延迟。

---

本章建立了对存储引擎与OS协作的深度认知：双缓冲问题及其解决方案，WAL持久化的内核路径与设备写缓存陷阱，Checkpoint与writeback的I/O竞争，mmap的争议与取舍，DAX对持久内存的直接访问，mlock的内存锁定。理解OS机制才能设计出与OS高效协作的存储引擎——不是对抗OS，而是利用OS。
