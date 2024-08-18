# AI Agent Guidelines

## Overview

This document provides guidelines for AI Agents working on the RingServer cross-platform web server project.

## Project Architecture

RingServer is a high-performance web server with pluggable I/O backends, supporting both io_uring (Linux) and kqueue (macOS) through a unified completion-event interface.

```
cc/projects/web-server/
├── include/ringserver/          # Public headers
│   ├── common/                  # Shared utilities
│   │   ├── status.hpp          # Status/error types
│   │   ├── likely.hpp          # Branch prediction hints
│   │   └── util.hpp            # General utilities
│   ├── io/                      # I/O backend layer
│   │   ├── io_backend.hpp      # Abstract IoBackend interface
│   │   └── kqueue_backend.hpp  # macOS kqueue implementation
│   ├── server/                  # HTTP server layer
│   │   ├── connection.hpp      # Connection state machine
│   │   └── server.hpp          # Main server class
│   └── http/                    # HTTP layer (Phase 2)
├── src/                         # Implementation
│   ├── common/
│   ├── io/
│   ├── server/
│   └── main.cpp                # Entry point
├── tests/                       # Unit tests
│   └── http/
├── bench/                       # Benchmarks
│   └── http/
├── CMakeLists.txt              # Build configuration
├── README.md                   # Design documentation
└── CLAUDE.md                   # Development guidelines
```

## Key Components

### IoBackend (`include/ringserver/io/io_backend.hpp`)
Unified I/O abstraction layer:

```cpp
class IoBackend {
 public:
  virtual Status Init() = 0;
  virtual Status SubmitAccept(int listen_fd, int64_t user_data) = 0;
  virtual Status SubmitRead(int fd, uint8_t* buf, size_t cap, int64_t user_data) = 0;
  virtual Status SubmitWrite(int fd, const uint8_t* buf, size_t len, int64_t user_data) = 0;
  virtual Status SubmitSendFile(int out_fd, int file_fd, off_t offset, size_t len, int64_t user_data) = 0;
  virtual Status SubmitClose(int fd, int64_t user_data) = 0;
  virtual Status Poll(std::vector<CompletionEvent>* out, int timeout_ms) = 0;
};
```

### CompletionEvent
Unified completion event structure:

```cpp
enum class OpKind { Accept, Read, Write, SendFile, Close };

struct CompletionEvent {
  OpKind op;           // Operation type
  int fd;              // File descriptor
  int64_t user_data;   // Connection ID or context
  int32_t result;      // Bytes transferred or error (-errno)
  uint32_t flags;      // Optional flags
};
```

### KqueueBackend (`include/ringserver/io/kqueue_backend.hpp`)
macOS implementation using kqueue:
- Converts readiness events to completion events
- Performs actual I/O syscalls internally
- Presents unified completion interface

### IoUringBackend (Linux, Phase 1)
Linux implementation using io_uring:
- True completion-based I/O
- SQE/CQE submission and completion
- Optional: fixed files, registered buffers

### Connection (`include/ringserver/server/connection.hpp`)
HTTP connection state machine:
- Read buffer (ring buffer or linear)
- Write buffer
- Connection state: Accepting → Reading → Parsing → Writing → Closing
- Keep-alive support

## Build System

```bash
# macOS (kqueue only)
mkdir build && cd build
cmake ..
cmake --build .

# Linux with io_uring
mkdir build && cd build
cmake -DRINGSERVER_ENABLE_URING=ON ..
cmake --build .

# Run server
./ringserver

# Run tests
./ringserver_test

# Run benchmarks
./ringserver_bench
```

## Dependencies

- **CMake 3.16+**
- **C++20 compiler**
- **Threads** (pthread)
- **liburing** (Linux only, optional)
- **GoogleTest** (fetched)
- **Google Benchmark** (fetched)

## Development Phases

### Phase 0: macOS MVP (IN PROGRESS)
- KqueueBackend implementation
- Fixed "200 OK" response
- wrk benchmarking
- Instruments profiling

### Phase 1: Linux io_uring
- IoUringBackend with liburing
- Same server/connection/http code
- Build option: `-DRINGSERVER_ENABLE_URING=ON`

### Phase 2: HTTP/1.1 Parser
- State machine parser
- Keep-alive support
- 400/404 handling
- Unit tests

### Phase 3: Static Files + Zero-Copy
- Path to filesystem mapping
- sendfile() on Linux/macOS
- Fallback: read+write
- ETag/Last-Modified (optional)

## Common Tasks

### Adding a New I/O Backend

1. Inherit from `IoBackend`
2. Implement all virtual methods
3. Add platform detection in CMake
4. Update factory method

```cpp
class MyBackend : public IoBackend {
 public:
  Status Init() override;
  Status SubmitAccept(int listen_fd, int64_t user_data) override;
  // ... implement all methods
};
```

### Handling Completion Events

```cpp
void Server::HandleCompletion(const CompletionEvent& event) {
  switch (event.op) {
    case OpKind::Accept:
      HandleAccept(event);
      break;
    case OpKind::Read:
      HandleRead(event);
      break;
    case OpKind::Write:
      HandleWrite(event);
      break;
    // ...
  }
}
```

### Connection State Machine

```cpp
enum class ConnState {
  kAccepting,   // Waiting for accept completion
  kReading,     // Reading request
  kParsing,     // Parsing HTTP
  kProcessing,  // Handling request
  kWriting,     // Writing response
  kClosing      // Closing connection
};
```

## Error Handling

### Status Codes

```cpp
Status status = backend_->SubmitRead(fd, buf, size, conn_id);
if (!status.ok()) {
  LOG_ERROR("SubmitRead failed: {}", status.message());
  CloseConnection(conn_id);
}
```

### Completion Errors

```cpp
if (event.result < 0) {
  // Error: -errno
  int err = -event.result;
  HandleError(conn_id, err);
}
```

## Prohibited Actions

1. **DO NOT** use blocking I/O
2. **DO NOT** ignore EAGAIN/EWOULDBLOCK
3. **DO NOT** unboundedly grow buffers (implement backpressure)
4. **DO NOT** leak file descriptors (use RAII)
5. **DO NOT** mix readiness and completion models without clear abstraction

## Performance Methodology

### Benchmarking with wrk

```bash
# Fixed response test
wrk -t4 -c100 -d30s http://localhost:8080/

# Static file test
wrk -t4 -c100 -d30s http://localhost:8080/static/4kb.txt

# Keep-alive test
wrk -t4 -c100 -d30s -H "Connection: keep-alive" http://localhost:8080/
```

### Metrics to Record

- QPS (requests per second)
- p50/p95/p99 latency
- CPU utilization
- Context switches
- Syscalls/sec

### Profiling

**macOS Instruments:**
- Time Profiler: Find CPU hotspots
- System Trace: Context switches, wakeups

**Linux perf:**
```bash
perf stat -e cycles,instructions,cache-misses,context-switches ./ringserver
perf record -g ./ringserver
perf report
```

## Resources

- [io_uring documentation](https://unixism.net/loti/)
- [kqueue man page](https://man.freebsd.org/cgi/man.cgi?kqueue)
- [HTTP/1.1 RFC 7230](https://tools.ietf.org/html/rfc7230)

## Communication Style

- Emphasize I/O model differences (Reactor vs Proactor)
- Reference specific syscalls and flags
- Show before/after performance comparisons
- Document OS-specific behaviors
