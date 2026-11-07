# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### In Progress
- HTTP/1.1 parser state machine
- Static file serving
- sendfile() zero-copy support

## [0.2.0] - 2024-XX-XX

### Added
- **HTTP/1.1 Parser**
  - Incremental state machine parser
  - Request line parsing (GET only)
  - Header field parsing
  - Keep-alive connection support
  - 400 Bad Request handling
  - 404 Not Found handling

- **Router**
  - Path-based routing
  - Static file handler
  - Fixed response handler

- **Unit Tests**
  - HTTP parser tests (gtest)
  - Router tests
  - Connection state machine tests

### Changed
- Improved buffer management with ring buffers
- Better error handling in connection lifecycle

## [0.1.0] - 2024-XX-XX

### Added
- **Project Skeleton**
  - CMake build system
  - Directory structure
  - GoogleTest integration
  - Google Benchmark integration

- **I/O Backend Abstraction**
  - IoBackend interface
  - CompletionEvent structure
  - OpKind enumeration

- **KqueueBackend (macOS)**
  - kqueue-based I/O multiplexing
  - SubmitAccept for incoming connections
  - SubmitRead for reading data
  - SubmitWrite for writing data
  - SubmitClose for closing connections
  - Poll() for completion events

- **Server Core**
  - Server class with event loop
  - Connection state machine
  - Fixed "200 OK" response
  - Basic keep-alive support

- **Build System**
  - CMakeLists.txt with platform detection
  - macOS kqueue support (always enabled)
  - Linux io_uring support (optional)

### Project Structure
```
web-server/
├── include/ringserver/
│   ├── common/
│   │   ├── status.hpp
│   │   ├── likely.hpp
│   │   └── util.hpp
│   ├── io/
│   │   ├── io_backend.hpp
│   │   └── kqueue_backend.hpp
│   ├── server/
│   │   ├── connection.hpp
│   │   └── server.hpp
│   └── http/
├── src/
│   ├── common/
│   ├── io/
│   ├── server/
│   └── main.cpp
├── tests/
│   └── http/
├── bench/
│   └── http/
└── CMakeLists.txt
```

### Technical Details

**Completion-First Abstraction:**
```cpp
// Unified interface regardless of backend
struct CompletionEvent {
  OpKind op;           // Accept, Read, Write, SendFile, Close
  int fd;              // File descriptor
  int64_t user_data;   // Connection context
  int32_t result;      // Bytes or error (-errno)
};
```

**Kqueue Adaptation:**
```cpp
// kqueue provides readiness, we convert to completion
void KqueueBackend::Poll(...) {
  // 1. kevent() to get readiness
  // 2. Perform actual I/O syscall
  // 3. Package result as CompletionEvent
}
```

### Dependencies
- CMake 3.16+
- C++20 compiler
- GoogleTest
- Google Benchmark
- liburing (Linux, optional)

### Platform Support
- macOS: kqueue backend (primary development)
- Linux: io_uring backend (optional)

## [0.0.1] - 2024-XX-XX

### Added
- Project initialization
- Initial design documentation
- CLAUDE.md with development guidelines

## Phase Roadmap

### Phase 0: macOS MVP ✅
- KqueueBackend
- Fixed 200 OK response
- wrk benchmarking

### Phase 1: Linux io_uring 🚧
- IoUringBackend
- Same server code
- Optional build

### Phase 2: HTTP Parser 🚧
- State machine parser
- Keep-alive
- Error handling

### Phase 3: Static Files 📋
- Path mapping
- sendfile() zero-copy
- ETag/Last-Modified

### Phase 4: Performance 📋
- Profiling and optimization
- Comparison study
- Documentation
