# 第23章 io_uring：异步I/O的革命

> 源码锚点：`io_uring/io_uring.c`、`io_uring/rsrc.c`、`io_uring/sqpoll.c`、`io_uring/rw.c`、`io_uring/net.c`、`io_uring/zcrx.c`、`io_uring/uring_cmd.c`、`io_uring/io-wq.c`

io_uring是Linux异步I/O的革命——通过共享内存环替代系统调用，通过SQPOLL消除提交开销，通过固定资源减少per-I/O验证，通过零拷贝接收消除数据复制。它不仅适用于文件I/O，还支持网络、定时器、futex等操作，成为Linux统一的异步编程接口。

## 23.1 io_uring的设计哲学

### 从aio到io_uring

Linux传统的异步I/O(aio)有严重局限：仅支持O_DIRECT文件I/O、每个操作需要系统调用、内部实现复杂且效率低。io_uring从零设计，解决了所有这些问题：

| 特性 | aio | io_uring |
|------|-----|----------|
| 操作类型 | 仅O_DIRECT文件 | 文件/网络/定时器/futex/... |
| 提交方式 | 系统调用 | 共享内存环(零系统调用) |
| 完成通知 | 信号/轮询 | CQ环 |
| 资源管理 | 每次验证 | 固定注册 |
| 扩展性 | 差 | uring_cmd自定义命令 |

### 核心架构：SQ + CQ共享环

io_uring的核心是两个共享内存环——Submission Queue(SQ)和Completion Queue(CQ)：

```
用户态                              内核态
┌─────────────┐                   ┌─────────────┐
│ SQ环         │  ──SQE数组──→    │ 读取SQE      │
│ (提交队列)   │                   │ 解析为请求    │
└─────────────┘                   │ 执行I/O      │
                                  │ 填充CQE      │
┌─────────────┐  ←──CQE数组──    │              │
│ CQ环         │                   └─────────────┘
│ (完成队列)   │
└─────────────┘
```

- **SQ**：用户写入SQE(Submission Queue Entry)，内核消费
- **CQ**：内核写入CQE(Completion Queue Entry)，用户消费
- **共享内存**：SQ和CQ通过mmap映射到用户态和内核态——零拷贝通信

### 三个系统调用

```c
// io_uring_setup(entries, params)  → 创建ring实例
// io_uring_enter(ring_fd, ...)     → 提交SQE/等待CQE
// io_uring_register(ring_fd, ...)  → 注册固定资源
```

io_uring_setup创建ring并返回文件描述符；io_uring_enter触发内核处理SQE；io_uring_register注册固定文件/缓冲区。在SQPOLL模式下，连io_uring_enter都不需要——内核线程自动轮询SQ。

## 23.2 核心实现

### io_uring_setup()：ring的创建与映射

```c
// io_uring/io_uring.c (简化)
// 创建流程：
// 1. 分配io_ring_ctx结构
// 2. 分配SQE数组(共享内存)
// 3. 分配CQ环(共享内存)
// 4. 创建io-wq工作队列
// 5. 返回fd + 偏移量(用户态mmap)
```

用户态通过mmap将SQE数组和CQ环映射到自己的地址空间——之后通过直接读写内存与内核通信，无需系统调用。

### SQE→请求的解析与分发

```c
// io_uring/io_uring.c (简化)
// SQE包含：opcode(操作码) + flags + addr/len/off等参数
// 内核根据opcode查找opdef表，获取对应的处理函数
// io_uring/opdef.c：操作码注册表
```

每个SQE的opcode对应一个处理函数——read/write/send/recv/openat/close/timeout等。opdef表定义了每个操作码的参数格式、异步执行策略等。

### 完成路径

I/O完成时，内核填充CQE(user_data + result)放入CQ环——用户态通过检查CQ的head/tail指针发现完成事件。如果用户请求了事件通知，内核还会通过eventfd或信号通知。

## 23.3 固定资源注册

### IORING_REGISTER_FILES

```c
// io_uring/rsrc.c
// 注册文件描述符数组 → 内核为每个fd获取引用，存入固定表
// 后续SQE使用索引而非fd → 内核直接查表，无需fget()/fput()
// 消除每次I/O的文件查找和引用计数开销
```

### IORING_REGISTER_BUFFERS

注册用户缓冲区数组 → 内核pin住页面，存入固定表。后续SQE使用缓冲区索引 → 内核直接获取已pin的页面，无需get_user_pages()。

固定资源对高IOPS场景至关重要——每个I/O节省几微秒的查找/验证开销，在百万IOPS下就是显著的整体提升。

### Provided Buffer

`io_uring/kbuf.c`提供缓冲区选择机制——应用预注册一组缓冲区，内核在I/O完成时自动选择一个填入数据。这避免了应用预先分配固定大小缓冲区的限制——内核根据实际数据量选择合适的缓冲区。

## 23.4 SQPOLL：内核侧轮询

```c
// io_uring/sqpoll.c
// 创建内核线程io_uring-sq → 绑定到指定CPU
// 线程循环：检查SQ → 有SQE则解析执行 → 无SQE则休眠
// 用户态：写入SQE → 唤醒SQPOLL线程(或等待自动轮询)
```

SQPOLL消除提交延迟——用户态写入SQE后，SQPOLL线程立即处理，无需io_uring_enter系统调用。适合超高IOPS场景(如NVMe百万IOPS)。

SQPOLL的空闲超时：无SQE一段时间后，线程进入休眠——用户态需要io_uring_enter唤醒。这平衡了延迟和CPU占用。

## 23.5 文件I/O操作

### io_uring/rw.c：读写操作

```c
// IORING_OP_READ/IORING_OP_WRITE
// 支持：read/write/readv/writev
// 可选：固定缓冲区索引、偏移量、强制O_DIRECT
```

读写的执行路径：
- **缓冲I/O**：通过`filemap_read()`/`filemap_write()`操作Page Cache
- **直接I/O**(O_DIRECT)：通过`iomap_dio_rw()`直接与块设备交互
- **异步执行**：如果I/O不能立即完成，交给io-wq工作队列异步执行

### io_uring/fs.c：文件系统操作

openat/statx/unlinkat/renameat/splice等——覆盖文件系统元数据操作。这些操作通常在io-wq中异步执行。

## 23.6 网络操作

### io_uring/net.c：网络I/O

```c
// IORING_OP_SEND/IORING_OP_RECV
// IORING_OP_ACCEPT/IORING_OP_CONNECT
// IORING_OP_SENDMSG/IORING_OP_RECVMSG
```

网络操作与文件I/O使用相同的SQ/CQ机制——统一的异步编程模型。accept/connect等可能阻塞的操作在io-wq中执行。

### io_uring/zcrx.c：零拷贝接收

零拷贝接收(zcrx)是io_uring专属的网络零拷贝路径：

```
传统recv：内核skb → 拷贝到用户缓冲区 → 用户处理
zcrx：    内核skb → 注册用户缓冲区(页面) → 数据直接DMA到用户空间
```

zcrx避免了网络数据的内核→用户态拷贝——在高速网络(100Gbps+)上，数据拷贝成为瓶颈，zcrx消除这一开销。

## 23.7 io_uring命令与扩展

### IORING_OP_URING_CMD

`io_uring/uring_cmd.c`提供驱动自定义命令接口——驱动注册`uring_cmd`处理函数，用户通过SQE提交驱动特定命令：

```
NVMe passthrough命令：
  SQE { opcode: IORING_OP_URING_CMD, cmd_op: NVME_URING_CMD_IO }
  → 内核调用NVMe驱动的uring_cmd处理函数
  → 构建NVMe命令提交到blk-mq
```

uring_cmd是io_uring的扩展机制——任何设备驱动都可以注册自己的异步命令接口。

> **AI视角**：uring_cmd作为统一的加速器命令提交接口。GPU驱动可以注册uring_cmd——用户态通过SQE提交GPU命令，内核异步执行，CQ返回结果。这避免了ioctl的系统调用开销，为GPU/DSA等加速器提供高效的命令提交通道。

## 23.8 其他功能

- **futex**(`io_uring/futex.c`)：异步等待/唤醒futex——与第16章futex机制集成
- **epoll**(`io_uring/epoll.c`)：将epoll事件集成到io_uring完成路径
- **timeout**(`io_uring/timeout.c`)：定时器操作——超时后产生CQE
- **cancel**(`io_uring/cancel.c`)：取消已提交的请求
- **io-wq**(`io_uring/io-wq.c`)：io_uring的工作队列——不能在线程上下文直接执行的操作在此异步执行
- **NAPI**(`io_uring/napi.c`)：网络忙轮询集成——在io_uring_enter等待时轮询网络设备

## 23.9 数据库视角：io_uring如何重塑存储引擎

### 从libaio到io_uring的迁移

传统数据库使用libaio——每个I/O需要系统调用提交和完成检查。io_uring的批量提交/完成减少系统调用次数：

```
libaio：  提交N个I/O → N次io_submit + N次io_getevents → 2N次系统调用
io_uring：提交N个I/O → 写入N个SQE + 1次io_uring_enter → 1次系统调用
          完成N个I/O → 检查CQ环 → 0次系统调用
```

### 固定资源减少per-I/O开销

```
传统：每次I/O → fget()查找fd → get_user_pages()pin缓冲区 → I/O → fput() + unpin
io_uring：注册资源 → 每次I/O → 直接查表 → I/O → 无清理开销
```

### RocksDB/io_uring集成

RocksDB已支持io_uring——将多个SSTable读请求批量提交到一个io_uring实例，利用SQPOLL消除提交延迟。实测在NVMe SSD上，io_uring比libaio提升15-30%的IOPS。

---

本章建立了对io_uring的完整认知：SQ/CQ共享环实现零系统调用通信，固定资源消除per-I/O验证开销，SQPOLL消除提交延迟，zcrx实现网络零拷贝接收，uring_cmd提供驱动扩展接口，io-wq处理阻塞操作。io_uring是Linux异步编程的未来——统一的异步接口覆盖文件/网络/定时器/加速器，从数据库到AI训练都在向io_uring迁移。
