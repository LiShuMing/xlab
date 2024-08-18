# AI Agent Guidelines

## Overview

This document provides guidelines for AI Agents working on the MiniSeastar project.

## Project Architecture

MiniSeastar is a C++20 coroutine-based asynchronous runtime inspired by Seastar. It's designed for learning modern C++ coroutines and high-performance async I/O patterns.

```
cc/projects/mini-seastar/
├── include/miniseastar/    # Public headers
│   ├── task.hpp           # Coroutine Task<T> type
│   ├── scheduler.hpp      # Coroutine scheduler
│   ├── awaitables.hpp     # Awaitable types (sleep, yield)
│   └── runtime.hpp        # Runtime and reactor
├── src/                    # Implementation
│   ├── scheduler.cpp      # Scheduler implementation
│   └── runtime.cpp        # Runtime/reactor implementation
├── examples/               # Demo programs
│   ├── 01_coro_demo.cpp       # Basic coroutine demo
│   ├── 02_sleep_demo.cpp      # Timer/sleep demo
│   ├── 03_task_chain.cpp      # Task chaining
│   └── 04_pingpong_bench.cpp  # Benchmark
├── tests/                  # Unit tests
│   ├── test_task.cpp
│   ├── test_scheduler.cpp
│   └── test_awaitables.cpp
├── docs/                   # Documentation
│   └── PHASE1_SUMMARY.md
├── CMakeLists.txt         # Build configuration
└── README.md
```

## Key Components

### Task<T> (`include/miniseastar/task.hpp`)
- C++20 coroutine type with promise_type
- Supports co_await for continuation chaining
- Exception propagation via std::exception_ptr
- Both task<T> and task<void> supported

```cpp
task<int> compute() {
    co_return 42;
}

task<void> async_main() {
    int result = co_await compute();
    std::cout << result << std::endl;
}
```

### Scheduler (`include/miniseastar/scheduler.hpp`)
- Single-thread event loop
- Ready queue of coroutine handles
- Runs: drain queue → poll I/O/timers → resume

```cpp
scheduler sched;
sched.schedule(async_task());
sched.run();  // Event loop
```

### Awaitables (`include/miniseastar/awaitables.hpp`)
- `yield()` - Cooperative multitasking
- `sleep_for(duration)` - Timer-based suspension
- I/O awaitables (Phase 2) - kqueue-based

### Runtime/Reactor (`include/miniseastar/runtime.hpp`)
- kqueue integration (macOS)
- Manages file descriptor events
- Maps events to waiting coroutines

## Build System

```bash
# Create build directory
mkdir build && cd build

# Configure
cmake ..

# Build everything
cmake --build .

# Run tests
./miniseastar_tests

# Run demos
./coro_demo
./sleep_demo
./task_chain_demo
./pingpong_bench

# With AddressSanitizer
cmake .. -DMS_USE_ASAN=ON
cmake --build .
```

## Dependencies

- **C++20/23** - Coroutine support required
- **CMake 3.16+** - Build system
- **GoogleTest** - Testing (submodule)
- **macOS** - kqueue for I/O (current target)

## Development Phases

### Phase 1: Coroutine Runtime (COMPLETED)
- task<T> implementation
- Scheduler with ready queue
- yield() and sleep_for()
- Unit tests
- Demos

### Phase 2: kqueue I/O (IN PROGRESS)
- awaitable_read/accept/write
- Echo server demo
- Connection management

### Phase 3: Performance (PLANNED)
- Coroutine frame allocator
- Metrics collection
- Instruments profiling

### Phase 4: Thread-per-Core (PLANNED)
- Multiple reactors
- Accept distribution
- Cross-thread messaging

## Coding Standards

### C++ Features
- Use C++20 coroutines
- Use std::move for Task<T>
- RAII for resource management
- Explicit memory ordering for atomics

### Error Handling
- Exception propagation via promise
- Check EAGAIN for I/O
- Handle partial reads/writes

### Naming
- `Task<T>` - PascalCase for types
- `co_await` - Standard C++ keyword
- `miniseastar::` - Namespace

## Common Tasks

### Adding a New Awaitable

```cpp
// In awaitables.hpp
struct MyAwaitable {
    bool await_ready() const noexcept { return false; }
    void await_suspend(std::coroutine_handle<> h) {
        // Register with reactor
    }
    ReturnType await_resume() {
        return result;
    }
};
```

### Writing a Test

```cpp
// In tests/test_*.cpp
TEST(TaskTest, BasicCoroutine) {
    auto t = []() -> task<int> {
        co_return 42;
    }();

    scheduler sched;
    sched.schedule(t);
    sched.run_once();

    EXPECT_EQ(t.get(), 42);
}
```

### Creating a Demo

```cpp
// In examples/XX_*.cpp
task<void> demo() {
    std::cout << "Starting demo" << std::endl;
    co_await sleep_for(100ms);
    std::cout << "After sleep" << std::endl;
}

int main() {
    scheduler sched;
    sched.schedule(demo());
    sched.run();
    return 0;
}
```

## Prohibited Actions

1. **DO NOT** use blocking I/O in coroutines
2. **DO NOT** copy Task<T> (only move)
3. **DO NOT** ignore exception_ptr in void tasks
4. **DO NOT** use std::coroutine_handle directly (wrap in Task)
5. **DO NOT** forget to resume the scheduler

## Performance Considerations

- Task<T> is move-only (efficient)
- Use std::move for large values in co_return
- Minimize allocations in hot paths
- Consider custom allocator for coroutine frames

## Debugging Tips

### With LLDB
```bash
lldb ./coro_demo
breakpoint set -n miniseastar::scheduler::run
coroutine backtrace  # If supported
```

### With AddressSanitizer
```bash
cmake .. -DMS_USE_ASAN=ON
./miniseastar_tests 2>&1 | head -50
```

### Coroutine Frame Inspection
```cpp
// Add logging in promise_type
std::cout << "Coroutine frame at: " << this << std::endl;
```

## Resources

- [C++ Coroutines TS](https://en.cppreference.com/w/cpp/language/coroutines)
- [Seastar Documentation](https://docs.seastar.io/)
- [kqueue Tutorial](https://wiki.netbsd.org/tutorials/kqueue_tutorial/)
- [C++20 Coroutines in Action](https://cppreference.com/)

## Communication Style

- Explain coroutine invariants clearly
- Reference specific phases when discussing features
- Show example code for new concepts
- Document memory ordering decisions
