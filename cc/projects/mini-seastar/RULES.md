# Project Rules and Standards

## Overview

This document defines the engineering standards, coding conventions, and best practices for the MiniSeastar C++ coroutine runtime project.

## Code Style

### C++ Standards

- **C++ Standard**: C++20 (C++23 for full features)
- **Compiler**: Clang (Apple Clang on macOS)
- **Coroutine Support**: `-fcoroutines-ts` flag required

### Commands

```bash
# Configure and build
mkdir build && cd build
cmake ..
cmake --build .

# Run tests
./miniseastar_tests

# Run specific test
./miniseastar_tests --gtest_filter=TaskTest.*

# With sanitizers
cmake .. -DMS_USE_ASAN=ON
cmake --build .
./miniseastar_tests
```

## Project Structure

```
cc/projects/mini-seastar/
├── include/miniseastar/    # Public API headers
│   ├── task.hpp           # Task<T> coroutine type
│   ├── scheduler.hpp      # Coroutine scheduler
│   ├── awaitables.hpp     # Awaitable utilities
│   └── runtime.hpp        # Runtime/reactor
├── src/                    # Implementation
│   ├── scheduler.cpp
│   └── runtime.cpp
├── examples/               # Demo programs
├── tests/                  # Unit tests
├── docs/                   # Documentation
└── CMakeLists.txt
```

## Naming Conventions

- **Types**: `PascalCase` (e.g., `Task<T>`, `Scheduler`, `TaskPromise`)
- **Functions**: `snake_case` (e.g., `await_ready`, `set_continuation`)
- **Variables**: `snake_case_` with trailing underscore for members
- **Macros**: `SCREAMING_SNAKE_CASE` with `MINISEASTAR_` prefix
- **Namespaces**: `miniseastart::` (all lowercase)
- **Template Parameters**: `SingleCapital` (e.g., `T`, `U`)

## Coroutine Patterns

### Task Definition

```cpp
template<typename T>
class Task {
public:
    using promise_type = TaskPromise<T>;
    using handle_type = coroutine_ns::coroutine_handle<promise_type>;

    // Move-only
    Task(Task&&) noexcept;
    Task& operator=(Task&&) noexcept;

    // No copy
    Task(const Task&) = delete;
    Task& operator=(const Task&) = delete;

    // Destructor destroys coroutine frame
    ~Task();

private:
    handle_type handle_;
};
```

### Promise Type Requirements

```cpp
template<typename T>
class TaskPromise {
public:
    // Called when coroutine starts
    auto initial_suspend() noexcept { return suspend_always{}; }

    // Called when coroutine ends
    auto final_suspend() noexcept { return suspend_always{}; }

    // Handle return value
    void return_value(T value);

    // Handle exceptions
    void unhandled_exception();

    // Get Task from promise
    Task<T> get_return_object();
};
```

### Awaiter Pattern

```cpp
struct MyAwaiter {
    // Check if we need to suspend
    [[nodiscard]] bool await_ready() const noexcept;

    // Called when suspending
    void await_suspend(coroutine_ns::coroutine_handle<> handle) noexcept;

    // Called when resuming
    [[nodiscard]] ReturnType await_resume();
};
```

## Memory Management

### Coroutine Frame

- Frame allocated on heap by default
- Custom allocator can be added later (Phase 3)
- Task destructor destroys the frame
- Never destroy a running coroutine

### Move Semantics

```cpp
// Good - Move construction
Task<int> create_task() {
    co_return 42;
}

Task<int> t = create_task();  // Move

// Good - Pass to scheduler
sched.schedule(std::move(t));

// Bad - Copy (compilation error)
// Task<int> t2 = t;  // ERROR: copy constructor deleted
```

## Exception Handling

### Promise Exception Storage

```cpp
void unhandled_exception() noexcept {
    exception_ptr_ = std::current_exception();
    ready_.store(true, std::memory_order_release);
}
```

### Exception Propagation

```cpp
task<void> may_throw() {
    throw std::runtime_error("error");
    co_return;
}

task<void> caller() {
    try {
        co_await may_throw();
    } catch (const std::exception& e) {
        // Handle exception
    }
}
```

## Memory Ordering

### Atomic Operations

```cpp
// Store with release (happens-before relationship)
ready_.store(true, std::memory_order_release);

// Load with acquire (synchronizes-with release store)
bool is_ready = ready_.load(std::memory_order_acquire);
```

### Invariants

1. `return_value` / `unhandled_exception` use `release`
2. `get_result` / `is_ready` use `acquire`
3. This ensures proper synchronization between producer and consumer

## Error Handling Guidelines

### I/O Errors

```cpp
task<ssize_t> awaitable_read(int fd, void* buf, size_t count) {
    ssize_t n = ::read(fd, buf, count);
    if (n < 0) {
        if (errno == EAGAIN || errno == EWOULDBLOCK) {
            // Register with kqueue and suspend
            co_await wait_for_readable(fd);
            n = ::read(fd, buf, count);  // Retry
        } else {
            throw std::system_error(errno, std::system_category());
        }
    }
    co_return n;
}
```

### Partial Operations

```cpp
task<void> write_all(int fd, const void* buf, size_t count) {
    const char* p = static_cast<const char*>(buf);
    while (count > 0) {
        ssize_t n = co_await awaitable_write(fd, p, count);
        if (n < 0) throw std::runtime_error("write failed");
        p += n;
        count -= n;
    }
}
```

## Testing Standards

### Test Structure

```cpp
#include <gtest/gtest.h>
#include "miniseastar/task.hpp"

using namespace miniseastar;

class TaskTest : public ::testing::Test {
protected:
    void SetUp() override {
        // Setup code
    }

    void TearDown() override {
        // Cleanup code
    }
};

TEST_F(TaskTest, BasicCoroutine) {
    auto t = []() -> task<int> {
        co_return 42;
    }();

    // Test code
    EXPECT_EQ(t.get(), 42);
}
```

### Test Categories

1. **Unit tests** - Individual components
2. **Integration tests** - Component interaction
3. **Benchmark tests** - Performance measurements

## Documentation

### Header Documentation

```cpp
/**
 * Task<T> - A C++20 coroutine-based future type.
 *
 * Task<T> represents an asynchronous computation that will eventually
 * produce a value of type T. It supports:
 *   - co_await for composition
 *   - Exception propagation
 *   - Continuation chaining
 *
 * Example:
 *   task<int> compute() {
 *       co_return 42;
 *   }
 *
 *   task<void> caller() {
 *       int result = co_await compute();
 *   }
 *
 * @tparam T The return type of the coroutine
 */
template<typename T>
class Task { ... };
```

### Implementation Comments

```cpp
// Synchronization: release store happens-before acquire load
ready_.store(true, std::memory_order_release);

// Invariant: continuation_ is valid only if has_continuation() returns true
if (promise.has_continuation()) {
    promise.continuation().resume();
}
```

## Build Configuration

### CMake Options

| Option | Description | Default |
|--------|-------------|---------|
| `CMAKE_BUILD_TYPE` | Build configuration | RelWithDebInfo |
| `MS_USE_ASAN` | Enable AddressSanitizer | OFF |
| `CMAKE_CXX_STANDARD` | C++ standard | 23 |

### Compiler Flags

```cmake
# Always
-fcoroutines-ts           # Enable coroutines
-std=c++23               # C++ standard

# Debug/ASAN
-fsanitize=address       # AddressSanitizer
-fno-omit-frame-pointer  # Better stack traces

# Release
-O2                      # Optimization
-DNDEBUG                # Disable asserts
```

## Git Workflow

### Commit Messages

Format: `<type>(<scope>): <description>`

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `refactor`: Code restructuring
- `perf`: Performance improvement
- `test`: Test changes

Scopes:
- `task`, `scheduler`, `awaitable`, `runtime`, `test`

Examples:
```
feat(task): add cancellation support
fix(scheduler): handle empty ready queue
docs(readme): add phase 2 roadmap
perf(task): optimize coroutine frame allocation
```

## Performance Guidelines

### Hot Path Optimizations

1. **Avoid heap allocation in tight loops**
2. **Use move semantics for large objects**
3. **Minimize atomic operations**
4. **Batch operations when possible**

### Profiling

```bash
# Build with debug symbols
cmake .. -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build .

# Run with Instruments (macOS)
instruments -t "Time Profiler" ./pingpong_bench
```

## Safety Guidelines

### Thread Safety

- Task<T> is NOT thread-safe by default
- Use atomics for shared state
- Scheduler is single-threaded (Phase 1-3)

### Resource Management

```cpp
// Good - RAII
class FileDescriptor {
    int fd_;
public:
    explicit FileDescriptor(int fd) : fd_(fd) {}
    ~FileDescriptor() { if (fd_ >= 0) ::close(fd_); }
    // Move-only...
};

// Bad - Manual cleanup
int fd = ::open(path, O_RDONLY);
// ... don't forget to close!
```

## Phase Requirements

### Phase 1 Checklist
- [x] Task<T> implementation
- [x] Scheduler with ready queue
- [x] yield() and sleep_for()
- [x] Unit tests
- [x] Demo programs

### Phase 2 Checklist
- [ ] kqueue integration
- [ ] awaitable_read/write/accept
- [ ] Echo server demo
- [ ] Connection management

### Phase 3 Checklist
- [ ] Custom coroutine allocator
- [ ] Metrics collection
- [ ] Profiling guide

### Phase 4 Checklist
- [ ] Multi-reactor support
- [ ] Thread-per-core model
- [ ] Cross-thread messaging
