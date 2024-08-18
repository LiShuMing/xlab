---
chapter: 23
part: 第六篇 I/O与存储栈 —— 数据的完整通路
title: io_uring：异步I/O的革命
source_anchor:
  - io_uring/io_uring.c
  - io_uring/io_uring.h
  - io_uring/opdef.c
  - io_uring/rsrc.c
  - io_uring/kbuf.c
  - io_uring/sqpoll.c
  - io_uring/rw.c
  - io_uring/net.c
  - io_uring/zcrx.c
  - io_uring/uring_cmd.c
  - io_uring/futex.c
  - io_uring/epoll.c
  - io_uring/wait.c
  - io_uring/tctx.c
  - io_uring/io-wq.c
status: done
---

# 第23章 io_uring：异步I/O的革命

## 写作目标

深入理解io_uring的设计与实现，掌握SQ/CQ共享环、固定资源、SQPOLL、零拷贝接收等核心机制。

## 章节大纲

### 23.1 io_uring的设计哲学

- 从aio到io_uring：设计缺陷与演进动机
  - aio的局限：仅支持O_DIRECT、仅支持文件I/O
  - io_uring的设计目标：统一异步接口、零拷贝、可扩展
- 核心架构：SQ(Submission Queue) + CQ(Completion Queue) 共享环
- 系统调用：io_uring_setup/io_uring_enter/io_uring_register

### 23.2 核心实现

- **精读** `io_uring/io_uring.c`（3258行）：
  - `io_uring_setup()`：ring的创建与映射
  - `io_uring_enter()`：提交与等待完成
  - SQE→请求的解析与分发
  - 完成路径：CQE的填充与通知
- `io_uring/io_uring.h`：核心数据结构
- `io_uring/opdef.c`：操作码注册表

### 23.3 固定资源注册

- **精读** `io_uring/rsrc.c`：固定文件/缓冲区注册
  -IORING_REGISTER_FILES：固定文件描述符
  - IORING_REGISTER_BUFFERS：固定用户缓冲区
  - 避免每次I/O的文件查找和页表验证
- **精读** `io_uring/kbuf.c`：缓冲区选择
  - provided buffer：应用提供的缓冲区池

### 23.4 SQPOLL：内核侧轮询

- **精读** `io_uring/sqpoll.c`：
  - 内核线程轮询SQ，无需系统调用提交
  - 适合超高IOPS场景
  - CPU亲和性与空闲超时
- `io_uring/tctx.c`：任务上下文管理

### 23.5 文件I/O操作

- **精读** `io_uring/rw.c`：读写操作
  - read/write/readv/writev
  - IORING_OP_READ/IORING_OP_WRITE
  - 与Page Cache和O_DIRECT的交互
- `io_uring/fs.c`：文件系统操作
  - openat/statx/splice

### 23.6 网络操作

- **精读** `io_uring/net.c`：网络I/O
  - send/recv/sendmsg/recvmsg
  - accept/connect
- **精读** `io_uring/zcrx.c`：零拷贝接收
  - io_uring专属的零拷贝网络接收路径
  - 与传统MSG_ZEROCOPY的对比

### 23.7 io_uring命令与扩展

- **精读** `io_uring/uring_cmd.c`：io_uring命令
  - IORING_OP_URING_CMD：驱动自定义命令
  - NVMe passthrough命令
  - *AI视角*：uring_cmd作为统一的加速器命令提交接口

### 23.8 其他功能

- `io_uring/futex.c`：futex等待/唤醒
- `io_uring/epoll.c`：epoll集成
- `io_uring/poll.c`：poll集成
- `io_uring/timeout.c`：超时操作
- `io_uring/cancel.c`：请求取消
- `io_uring/io-wq.c`：io_uring工作队列——异步执行引擎
- `io_uring/memmap.c`：内存映射管理
- `io_uring/advise.c`：madvise/fadvise集成
- `io_uring/napi.c`：NAPI集成——网络忙轮询

### 23.9 *数据库视角*：io_uring如何重塑存储引擎

- 从libaio到io_uring的迁移路径
- io_uring对存储引擎I/O模型的影响
  - 批量提交与完成：减少系统调用
  - 固定资源：减少per-I/O开销
  - SQPOLL：消除提交延迟
- 实际案例：RocksDB/io_uring集成

## 关键源文件清单

| 文件 | 行数 | 关注点 |
|------|------|--------|
| `io_uring/io_uring.c` | 3258 | 核心实现 |
| `io_uring/rsrc.c` | ~800 | 固定资源 |
| `io_uring/sqpoll.c` | ~500 | SQPOLL |
| `io_uring/rw.c` | ~600 | 文件I/O |
| `io_uring/net.c` | ~800 | 网络I/O |
| `io_uring/zcrx.c` | ~500 | 零拷贝接收 |
| `io_uring/uring_cmd.c` | ~300 | 驱动命令 |
| `io_uring/io-wq.c` | ~800 | 工作队列 |

## 跨章依赖

- 依赖第21章（块层）：io_uring的文件I/O最终通过blk-mq提交
- 依赖第22章（文件系统）：io_uring操作VFS对象
- 依赖第16章（futex）：io_uring的futex操作
