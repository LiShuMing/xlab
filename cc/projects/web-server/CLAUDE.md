You are my senior systems programming mentor and pair engineer.

We are building a cross-platform web server project on macOS and Linux:
Project: RingServer (ring-based async I/O design).

Goal:
- Implement a web server that can run on macOS and Linux, with pluggable I/O backends.
- On Linux, use io_uring (liburing) to implement a proactor-style completion model.
- On macOS, use kqueue to implement a reactor-style backend that we adapt into the same completion-event interface.
- Provide a fair performance comparison between macOS and Linux backends using wrk, and document results and profiling methodology.

Hard constraints:
- Language: modern C++20.
- Build: CMake + Ninja.
- macOS must build and run without io_uring (no io_uring dependency).
- Linux build enables io_uring backend via compile-time option.
- No handwaving: define invariants, failure modes, and semantics (keep-alive, partial reads, backpressure).
- English comments only, production-grade style (Google C++ style).
- Do NOT invent performance numbers. Provide benchmark scripts and explain how to measure.

Architecture requirements:
1) Unified I/O abstraction:
   - Define IoBackend interface that exposes submission APIs (Accept/Read/Write/SendFile/Close)
     and Poll() that returns completion events.
   - Define CompletionEvent with: op kind, fd, user_data, result bytes/new fd/error.
   - io_uring backend uses true completion events (CQE).
   - kqueue backend turns readiness into completion by performing the syscall internally and emitting CompletionEvent.

2) Server architecture:
   - Connection object with read buffer, write buffer, state machine.
   - HTTP/1.1 parser implemented as a state machine (no external parser library).
   - Support: GET, keep-alive, basic headers, 400/404 handling.
   - Phase 3 supports static files and zero-copy sendfile (platform-specific).

Phased plan (must follow):
Phase 0: macOS MVP (kqueue)
- Implement KqueueBackend (Accept/Read/Write).
- Implement minimal HTTP response "200 OK" fixed payload.
- Provide wrk command lines and a doc on how to run and profile on macOS (Instruments).

Phase 1: Linux io_uring backend (liburing)
- Implement IoUringBackend (Accept/Read/Write) using liburing.
- Keep the same server/connection/http code.
- Add build option: -DRINGSERVER_ENABLE_URING=ON.
- Optional toggles (documented, may be TODO): fixed files, registered buffers.

Phase 2: HTTP/1.1 parser
- Implement a robust incremental parser (handles partial reads, pipelining optional).
- Add unit tests for parser (gtest).
- Extend routing: / -> fixed response, /static/<path> -> file serving (Phase 3).

Phase 3: Static files + zero-copy
- Implement SendFile abstraction:
  - Linux: sendfile(...) or io_uring sendfile opcode if available.
  - macOS: sendfile(...) signature for macOS.
  - Provide fallback path: read+write or mmap+writev.
- Add benchmarks: fixed 1KB response and static file 4KB/64KB/1MB.

Deliverables for each phase (mandatory):
A) docs/design.md updates: architecture, invariants, OS differences, and why reactor/proactor differ.
B) Exact file list and module split, with CMake target definitions.
C) Buildable code with clear TODOs for next phases.
D) Unit tests where applicable (HTTP parser at least).
E) Performance methodology:
   - wrk commands (connections, threads, duration),
   - metrics to record (QPS, p95/p99, CPU, context switches),
   - profiling steps:
     * macOS Instruments (Time Profiler + System Trace),
     * Linux perf stat/perf record,
     * syscall rate measurement.

Implementation rules:
- Use non-blocking sockets.
- Handle EAGAIN/EWOULDBLOCK correctly.
- Implement backpressure: do not unboundedly grow write buffers; if write would block, register interest and resume.
- Use RAII for fd management (unique_fd).
- Ensure graceful shutdown (SIGINT) and connection cleanup.

Start now with Phase 0:
- Provide the project skeleton (directories + top-level CMake).
- Implement KqueueBackend + minimal server loop with fixed 200 OK response.
- Provide a simple main() and instructions to run wrk on macOS.
- Include a short profiling checklist using Instruments.

