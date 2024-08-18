# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### In Progress (Phase 2)
- kqueue integration for macOS
- I/O awaitables (read, write, accept)
- Echo server implementation

## [0.2.0] - 2024-XX-XX

### Added
- **Phase 2: kqueue I/O Integration**
  - kqueue reactor implementation
  - awaitable_read() for non-blocking reads
  - awaitable_write() for non-blocking writes
  - awaitable_accept() for incoming connections
  - Echo server demo
  - Connection state management

### Changed
- Refactored scheduler for I/O integration
- Optimized event loop for mixed I/O and timer events

## [0.1.0] - 2024-XX-XX

### Added
- **Phase 1: Core Coroutine Runtime** (COMPLETED)
  - Task<T> coroutine type with promise_type
  - Task<void> specialization for void-returning coroutines
  - TaskAwaiter for co_await support
  - Exception propagation via std::exception_ptr
  - Move semantics (Task is move-only)
  - Continuation support for chaining

- **Scheduler Implementation**
  - Single-thread event loop
  - Ready queue for coroutine handles
  - run() loop: drain queue → poll → resume
  - Schedule API for submitting tasks

- **Awaitables**
  - yield() - Cooperative multitasking
  - sleep_for(duration) - Timer-based suspension
  - Min-heap timer queue

- **Build System**
  - CMake 3.16+ configuration
  - C++23 standard
  - Coroutine flags for Apple Clang
  - AddressSanitizer option
  - GoogleTest integration

- **Unit Tests**
  - test_task.cpp - Task<T> tests
  - test_scheduler.cpp - Scheduler tests
  - test_awaitables.cpp - Awaitable tests
  - Main test runner

- **Demo Programs**
  - 01_coro_demo.cpp - Basic coroutine demo
  - 02_sleep_demo.cpp - Timer and sleep demo
  - 03_task_chain.cpp - Task chaining demo
  - 04_pingpong_bench.cpp - Performance benchmark

- **Documentation**
  - Comprehensive README
  - Phase 1 implementation summary
  - CLAUDE.md with development guidelines

### Project Structure
```
mini-seastar/
├── include/miniseastar/
│   ├── task.hpp           # Task<T> coroutine type
│   ├── scheduler.hpp      # Scheduler interface
│   ├── awaitables.hpp     # Awaitable utilities
│   └── runtime.hpp        # Runtime/reactor
├── src/
│   ├── scheduler.cpp      # Scheduler implementation
│   └── runtime.cpp        # Runtime implementation
├── tests/
│   ├── main.cpp           # Test runner
│   ├── test_task.cpp      # Task tests
│   ├── test_scheduler.cpp # Scheduler tests
│   └── test_awaitables.cpp # Awaitable tests
├── examples/
│   ├── 01_coro_demo.cpp
│   ├── 02_sleep_demo.cpp
│   ├── 03_task_chain.cpp
│   └── 04_pingpong_bench.cpp
├── docs/
│   └── PHASE1_SUMMARY.md
└── CMakeLists.txt
```

### Technical Details

**Task<T> Implementation:**
- Uses std::experimental::coroutine on Apple Clang
- Type-erased result storage with std::variant
- Atomic ready flag for synchronization
- Continuation handle for chaining

**Memory Ordering:**
- return_value/unhandled_exception: memory_order_release
- get_result/is_ready: memory_order_acquire
- Ensures proper happens-before relationship

**Scheduler Loop:**
```cpp
void run() {
    while (!done) {
        // 1. Drain ready queue
        while (auto task = ready_queue.pop()) {
            task.resume();
        }

        // 2. Poll for I/O and timers
        auto timeout = get_next_timer_timeout();
        poll_io(timeout);

        // 3. Process I/O completions
        process_io_completions();
    }
}
```

### Dependencies
- CMake 3.16+
- C++20/23 compiler with coroutine support
- GoogleTest (submodule)

### Platform
- Primary: macOS with Apple Clang
- Uses kqueue for I/O multiplexing
- Experimental coroutines support

## [0.0.1] - 2024-XX-XX

### Added
- Project initialization
- CMake setup
- Basic project structure

## Phase Roadmap

### Phase 1: Core Runtime ✅
- Task<T> type
- Scheduler
- yield/sleep
- Tests

### Phase 2: I/O Integration 🚧
- kqueue reactor
- I/O awaitables
- Echo server

### Phase 3: Performance 📋
- Custom allocator
- Metrics
- Profiling

### Phase 4: Multi-threading 📋
- Multi-reactor
- Thread-per-core
- Sharding
