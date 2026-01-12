
1) 第一性原理：为什么要做“双后端”？
	•	io_uring 的价值在于：把 I/O 提交与完成用 共享内存 ring（SQ/CQ） 表达，减少 syscalls、减少 wakeups，并支持注册（fixed files / buffers）降低内核路径开销。
	•	macOS 没有 io_uring；kqueue 更像 就绪通知（Reactor）。你仍然可以写高性能服务器，但模型不同。

所以工程目标不是“把 io_uring 代码移植到 macOS”，而是：

把 WebServer 的核心抽象拆出来：
业务层只看 Connection/Request/Response，
I/O 层用统一接口对接不同 OS 的事件/完成机制，
从而在 Linux/macOS 上对比“系统 I/O 模型导致的性能差异”。

⸻

2) 统一抽象：I/O Backend Interface（关键）

你需要一个最小、但能覆盖两种模型的接口。推荐用“Completion-first”的统一抽象（即使后端是 Reactor 也在内部转成 completion events）。

2.1 统一事件：CompletionEvent

enum class OpKind { Accept, Read, Write, SendFile, Close };

struct CompletionEvent {
  OpKind op;
  int fd;
  int64_t user_data;      // connection id or pointer-tag
  int32_t result;         // bytes or new fd or error(-errno)
  uint32_t flags;         // optional
};

2.2 统一后端接口：IoBackend

class IoBackend {
 public:
  virtual ~IoBackend() = default;

  virtual Status Init() = 0;
  virtual Status SubmitAccept(int listen_fd, int64_t user_data) = 0;
  virtual Status SubmitRead(int fd, uint8_t* buf, size_t cap, int64_t user_data) = 0;
  virtual Status SubmitWrite(int fd, const uint8_t* buf, size_t len, int64_t user_data) = 0;
  virtual Status SubmitSendFile(int out_fd, int file_fd, off_t offset, size_t len,
                                int64_t user_data) = 0;
  virtual Status SubmitClose(int fd, int64_t user_data) = 0;

  // Poll completions (blocking with timeout).
  virtual Status Poll(std::vector<CompletionEvent>* out, int timeout_ms) = 0;
};

2.3 两种后端映射
	•	Linux io_uring：天然 Proactor，CQE 就是 completion。
	•	macOS kqueue：是 readiness → 你内部做一次 read/write，把结果包装成 CompletionEvent，对上层伪装成 completion。

这样上层代码完全不关心 Reactor/Proactor 差异。

⸻

3) Connection 与 HTTP 层：独立于后端

3.1 Connection 状态机（建议）
	•	ConnState::Accepting / Reading / Parsing / Writing / Closing
	•	维护：
	•	read buffer（ring buffer 或 linear buffer）
	•	write buffer（small response + file response）
	•	keep-alive 状态
	•	request parser state

3.2 HTTP/1.1 parser（Phase 2）

写一个状态机解析器（不引入第三方库，练功）：
	•	REQ_LINE → HEADERS → BODY (optional) → DONE
	•	MVP 支持：
	•	GET
	•	keep-alive
	•	Content-Length（可选）
	•	只服务静态资源（Phase 3）

⸻

4) 静态文件与零拷贝（Phase 3）

Linux / macOS 支持差异：
	•	Linux：sendfile(out_fd, file_fd, &offset, len)
	•	macOS：sendfile(file_fd, out_fd, offset, &len, nullptr, 0)（签名不同）
	•	另外：可以提供 fallback：mmap + writev / read + write。

实现方式：
	•	SubmitSendFile() 在不同后端实现各自的 syscall 或者 io_uring opcode。

⸻

5) Phase 路线（你给的 3 阶段，但补全“跨 OS”）

Phase 0（强烈建议加）：基础脚手架 + kqueue MVP

原因：你现在在 macOS 开发，得先跑起来。
	•	实现 KqueueBackend：支持 Accept/Read/Write（就绪 + 真实 syscall）
	•	实现 Connection + 最小 HTTP 200 OK（固定字符串）
	•	用 wrk 跑通

Phase 1：Linux io_uring backend（liburing）
	•	IoUringBackend：SQE/CQE 提交与收割
	•	跑通 Accept/Read/Write
	•	加入可选：fixed files / registered buffers（先留开关，不强上）

Phase 2：HTTP/1.1 parser
	•	状态机 + keep-alive + path routing
	•	处理：
	•	半包/粘包（read buffer accumulation）
	•	header 限制（防止 OOM）
	•	400/404

Phase 3：静态资源 + sendfile
	•	path → filesystem mapping
	•	sendfile（Linux/macOS）
	•	ETag/Last-Modified 可选

⸻

6) 性能对比实验设计（必须写进 Promoting）

你要的不是“感觉快”，而是可以对比：

6.1 对比维度
	•	OS：macOS(kqueue) vs Linux(io_uring) vs Linux(epoll baseline 可选)
	•	workload：
	•	fixed response（CPU/协议开销极低，主要测 I/O 与调度）
	•	static file 4KB/64KB/1MB（测 sendfile / 零拷贝优势）
	•	concurrency：50 / 200 / 1000 / 5000 connections
	•	threads：1 / N（绑定 CPU 核心）

6.2 指标
	•	QPS
	•	p50/p95/p99 latency
	•	CPU utilization
	•	context switches（Linux: perf stat；macOS: Instruments System Trace）
	•	syscalls/sec（Linux: strace/perf；macOS: dtruss）

6.3 重要注意
	•	macOS 与 Linux 网络栈差异巨大，不能“公平等价”，你要做的是：
	•	保持应用层逻辑相同
	•	只换 I/O 后端
	•	用同一套 wrk script 与同样的 payload

⸻

7) 项目目录结构（建议 Claude 生成的最终形态）

ringserver/
  CMakeLists.txt
  include/ringserver/
    common/status.h
    common/config.h
    common/likely.h
    common/time.h
    net/socket_util.h
    io/io_backend.h
    io/kqueue_backend.h
    io/uring_backend.h          # linux only
    http/http_parser.h
    http/http_types.h
    server/connection.h
    server/server.h
    server/router.h
  src/
    io/kqueue_backend.cc
    io/uring_backend.cc         # linux only
    http/http_parser.cc
    server/connection.cc
    server/server.cc
    main.cc
  bench/
    wrk_scripts/
  tools/
    run_wrk.md
    run_instruments.md
    run_perf.md
  tests/
    test_http_parser.cc
    test_router.cc
  docs/
    design.md


⸻

8) Claude Code Promoting（直接复制使用）

下面这份就是你要的 “claude promoting”。它会逼 Claude 输出：工程结构、CMake、跨平台抽象、每 phase 的可编译增量、以及性能对比方法。

8) 你一个人做这个项目的“现实技巧”（让它不烂尾）
	1.	先做 fixed response（1KB 固定 body），只测调度/I/O，不被文件系统干扰。
	2.	HTTP parser 先做最小子集：request line + headers + keep-alive。
	3.	sendfile 做成独立模块，避免污染核心 I/O 抽象。
	4.	每个 Phase 都要有 wrk 脚本和运行指南，否则你很难知道优化是否生效。
