# Project Rules and Standards

## Overview

This document defines the engineering standards, coding conventions, and best practices for the RingServer web server project.

## Code Style

### C++ Standards

- **C++ Standard**: C++20
- **Compiler**: Clang (macOS), GCC/Clang (Linux)
- **Build System**: CMake 3.16+

### Commands

```bash
# Configure and build (macOS)
mkdir build && cd build
cmake ..
cmake --build .

# Configure and build (Linux with io_uring)
cmake -DRINGSERVER_ENABLE_URING=ON ..
cmake --build .

# Run
./ringserver

# Test
./ringserver_test

# Benchmark
./ringserver_bench
```

## Project Structure

```
cc/projects/web-server/
├── include/ringserver/
│   ├── common/              # Shared utilities
│   │   ├── status.hpp
│   │   ├── likely.hpp
│   │   └── util.hpp
│   ├── io/                  # I/O backends
│   │   ├── io_backend.hpp
│   │   └── kqueue_backend.hpp
│   ├── server/              # HTTP server
│   │   ├── connection.hpp
│   │   └── server.hpp
│   └── http/                # HTTP protocol
├── src/
│   ├── common/
│   ├── io/
│   ├── server/
│   └── main.cpp
├── tests/
├── bench/
└── CMakeLists.txt
```

## Naming Conventions

- **Namespaces**: `snake_case` (e.g., `ringserver`)
- **Classes**: `PascalCase` (e.g., `IoBackend`, `KqueueBackend`)
- **Methods**: `PascalCase` for public API (e.g., `SubmitRead`, `Poll`)
- **Private methods**: `snake_case_` with trailing underscore
- **Member variables**: `snake_case_` with trailing underscore
- **Constants**: `kPascalCase` (e.g., `kDefaultPort`)
- **Macros**: `SCREAMING_SNAKE_CASE` with `RINGSERVER_` prefix
- **Enums**: `PascalCase` with `k` prefix for values

## Header Organization

```cpp
#ifndef RINGSERVER_IO_BACKEND_HPP
#define RINGSERVER_IO_BACKEND_HPP

// 1. Standard library headers
#include <cstdint>
#include <vector>

// 2. Project headers
#include "ringserver/common/status.hpp"

namespace ringserver {

// Forward declarations
class Connection;

// Documentation
/**
 * Abstract interface for I/O backends.
 *
 * Implementations:
 *   - KqueueBackend: macOS kqueue (Reactor → Completion adapter)
 *   - IoUringBackend: Linux io_uring (true completion)
 */
class IoBackend {
  // ...
};

}  // namespace ringserver

#endif  // RINGSERVER_IO_BACKEND_HPP
```

## I/O Backend Interface

### Design Principles

1. **Completion-First Model**: All backends present completion events
2. **Non-blocking**: All operations are asynchronous
3. **User Data**: 64-bit token for connection identification
4. **Error Handling**: Negative result indicates -errno

### Interface Definition

```cpp
class IoBackend {
 public:
  virtual ~IoBackend() = default;

  // Initialize the backend
  virtual Status Init() = 0;

  // Submit operations
  virtual Status SubmitAccept(int listen_fd, int64_t user_data) = 0;
  virtual Status SubmitRead(int fd, uint8_t* buf, size_t cap, int64_t user_data) = 0;
  virtual Status SubmitWrite(int fd, const uint8_t* buf, size_t len, int64_t user_data) = 0;
  virtual Status SubmitSendFile(int out_fd, int file_fd, off_t offset, size_t len,
                                int64_t user_data) = 0;
  virtual Status SubmitClose(int fd, int64_t user_data) = 0;

  // Poll for completions (blocking with timeout)
  virtual Status Poll(std::vector<CompletionEvent>* out, int timeout_ms) = 0;
};
```

## Error Handling

### Status Pattern

```cpp
class Status {
 public:
  static Status OK() { return Status(); }
  static Status Error(int code, const char* msg);

  bool ok() const { return code_ == 0; }
  int code() const { return code_; }
  const char* message() const { return msg_; }

 private:
  int code_ = 0;
  const char* msg_ = nullptr;
};
```

### Usage

```cpp
Status status = backend_->SubmitRead(fd, buf, size, conn_id);
if (!status.ok()) {
  LOG_ERROR("SubmitRead failed: {} (code={})", status.message(), status.code());
  return status;
}
```

### Completion Errors

```cpp
void HandleCompletion(const CompletionEvent& event) {
  if (event.result < 0) {
    int err = -event.result;
    if (err == EAGAIN || err == EWOULDBLOCK) {
      // Retry logic
    } else if (err == ECONNRESET) {
      // Peer closed connection
      CloseConnection(event.user_data);
    } else {
      // Other error
      LOG_ERROR("I/O error: {}", strerror(err));
      CloseConnection(event.user_data);
    }
    return;
  }

  // Success: result >= 0 (bytes transferred)
  ProcessSuccess(event);
}
```

## RAII for File Descriptors

```cpp
class UniqueFd {
 public:
  explicit UniqueFd(int fd = -1) : fd_(fd) {}
  ~UniqueFd() { Close(); }

  // Move only
  UniqueFd(UniqueFd&& other) noexcept : fd_(other.Release()) {}
  UniqueFd& operator=(UniqueFd&& other) noexcept {
    if (this != &other) {
      Close();
      fd_ = other.Release();
    }
    return *this;
  }

  // Delete copy
  UniqueFd(const UniqueFd&) = delete;
  UniqueFd& operator=(const UniqueFd&) = delete;

  int get() const { return fd_; }
  bool valid() const { return fd_ >= 0; }

  int Release() {
    int tmp = fd_;
    fd_ = -1;
    return tmp;
  }

  void Close() {
    if (fd_ >= 0) {
      ::close(fd_);
      fd_ = -1;
    }
  }

 private:
  int fd_;
};
```

## Connection State Machine

### States

```cpp
enum class ConnState {
  kAccepting,    // Waiting for accept completion
  kReading,      // Reading request data
  kParsing,      // Parsing HTTP request
  kProcessing,   // Handling request (routing, etc.)
  kWriting,      // Writing response
  kClosing,      // Closing connection
  kClosed        // Connection closed
};
```

### State Transitions

```
kAccepting → kReading (accept completed)
kReading → kParsing (read complete or buffer full)
kParsing → kProcessing (request parsed)
kParsing → kReading (need more data)
kProcessing → kWriting (response ready)
kWriting → kClosing (write complete, no keep-alive)
kWriting → kReading (keep-alive, wait for next request)
kClosing → kClosed (close completed)
```

## Buffer Management

### Read Buffer

```cpp
class ReadBuffer {
 public:
  static constexpr size_t kInitialSize = 4 * 1024;
  static constexpr size_t kMaxSize = 64 * 1024;

  // Append data
  void Append(const uint8_t* data, size_t len);

  // Consume bytes
  void Consume(size_t len);

  // Get available write space
  size_t WritableBytes() const;

  // Get readable data
  const uint8_t* ReadableData() const;
  size_t ReadableBytes() const;

  // Find CRLF (for HTTP parsing)
  const uint8_t* FindCrlf() const;

 private:
  std::vector<uint8_t> buffer_;
  size_t read_index_ = 0;
  size_t write_index_ = 0;
};
```

### Backpressure

```cpp
// When write buffer exceeds threshold, stop reading
static constexpr size_t kMaxWriteBufferSize = 64 * 1024;

void Connection::HandleWriteAvailable() {
  if (write_buffer_.Size() > kMaxWriteBufferSize) {
    // Pause reading
    backend_->CancelRead(fd_);
  }
}
```

## Testing Standards

### Unit Tests

```cpp
#include <gtest/gtest.h>
#include "ringserver/http/http_parser.hpp"

using namespace ringserver;

class HttpParserTest : public ::testing::Test {
 protected:
  void SetUp() override {
    parser_.Reset();
  }

  HttpParser parser_;
};

TEST_F(HttpParserTest, ParseSimpleRequest) {
  const char* request = "GET / HTTP/1.1\r\nHost: localhost\r\n\r\n";
  auto result = parser_.Parse(request, strlen(request));

  EXPECT_TRUE(result.ok());
  EXPECT_EQ(result->method, HttpMethod::kGet);
  EXPECT_EQ(result->path, "/");
}
```

### Benchmarks

```cpp
#include <benchmark/benchmark.h>
#include "ringserver/http/http_parser.hpp"

static void BM_HttpParser(benchmark::State& state) {
  const char* request = "GET / HTTP/1.1\r\nHost: localhost\r\n\r\n";
  HttpParser parser;

  for (auto _ : state) {
    parser.Reset();
    auto result = parser.Parse(request, strlen(request));
    benchmark::DoNotOptimize(result);
  }
}
BENCHMARK(BM_HttpParser);
```

## Platform Abstraction

### Platform Detection

```cpp
// CMake defines:
// - RINGSERVER_PLATFORM_APPLE (macOS)
// - RINGSERVER_ENABLE_URING (Linux with io_uring)

#ifdef RINGSERVER_PLATFORM_APPLE
  #include <sys/event.h>
  // kqueue specific
#elif defined(RINGSERVER_ENABLE_URING)
  #include <liburing.h>
  // io_uring specific
#endif
```

### Platform-Specific Implementations

```cpp
std::unique_ptr<IoBackend> CreateBackend() {
#ifdef RINGSERVER_PLATFORM_APPLE
  return std::make_unique<KqueueBackend>();
#elif defined(RINGSERVER_ENABLE_URING)
  return std::make_unique<IoUringBackend>();
#else
  #error "No I/O backend available for this platform"
#endif
}
```

## Build Configuration

### CMake Options

| Option | Description | Default |
|--------|-------------|---------|
| `CMAKE_BUILD_TYPE` | Build configuration | Release |
| `RINGSERVER_ENABLE_URING` | Enable io_uring (Linux) | OFF |
| `CMAKE_CXX_COMPILER` | C++ compiler | Platform default |

### Compiler Flags

```cmake
# Common flags
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -Wextra -Wpedantic")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Werror=return-type")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fno-omit-frame-pointer")

# Debug flags
set(CMAKE_CXX_FLAGS_DEBUG "-O0 -g -fsanitize=address")

# Release flags
set(CMAKE_CXX_FLAGS_RELEASE "-O3 -DNDEBUG -march=native")
```

## Git Workflow

### Commit Messages

Format: `<type>(<scope>): <description>`

Types:
- `feat`: New feature
- `fix`: Bug fix
- `perf`: Performance improvement
- `refactor`: Code restructuring
- `test`: Test changes
- `docs`: Documentation

Scopes:
- `io`, `server`, `http`, `kqueue`, `uring`, `common`

Examples:
```
feat(kqueue): implement SubmitAccept and SubmitRead
fix(server): handle EAGAIN correctly in write path
perf(http): optimize header parsing with lookup table
docs(readme): add benchmarking instructions
```

## Performance Guidelines

### Zero-Copy

```cpp
// Good: sendfile for static files
SubmitSendFile(conn_fd, file_fd, offset, len, conn_id);

// Bad: read into buffer then write
read(file_fd, buffer, len);
write(conn_fd, buffer, len);
```

### Buffer Reuse

```cpp
// Connection pool for buffer reuse
class ConnectionPool {
 public:
  Connection* Acquire();
  void Release(Connection* conn);

 private:
  std::vector<std::unique_ptr<Connection>> available_;
};
```

### Syscall Reduction

```cpp
// Good: Batch completions
std::vector<CompletionEvent> events;
backend_->Poll(&events, timeout_ms);
for (const auto& event : events) {
  HandleCompletion(event);
}

// Bad: Poll one at a time
while (true) {
  CompletionEvent event;
  backend_->Poll(&event, timeout_ms);  // Inefficient
}
```

## Documentation

### Class Documentation

```cpp
/**
 * KqueueBackend implements IoBackend using BSD kqueue.
 *
 * Platform: macOS, FreeBSD
 *
 * Design:
 *   kqueue provides readiness notifications (Reactor model).
 *   We adapt this to a completion model by performing the actual
 *   I/O syscall when readiness is signaled, then emitting a
 *   CompletionEvent.
 *
 * Thread Safety:
 *   Not thread-safe. Must be used from a single thread.
 *
 * Example:
 *   auto backend = std::make_unique<KqueueBackend>();
 *   backend->Init();
 *   backend->SubmitAccept(listen_fd, 0);
 *   // ... event loop
 */
class KqueueBackend : public IoBackend {
  // ...
};
```

### Method Documentation

```cpp
/**
 * Submit an accept operation.
 *
 * When a connection is available, a CompletionEvent with:
 *   - op = OpKind::Accept
 *   - result = new file descriptor (>= 0) or -errno
 *   - user_data = the user_data passed here
 *
 * @param listen_fd The listening socket file descriptor
 * @param user_data Opaque token returned in completion event
 * @return Status::OK() on successful submission, error otherwise
 */
Status SubmitAccept(int listen_fd, int64_t user_data) override;
```

## Resources

- [io_uring by example](https://unixism.net/loti/)
- [kqueue tutorial](https://wiki.netbsd.org/tutorials/kqueue_tutorial/)
- [High Performance Browser Networking](https://hpbn.co/)
