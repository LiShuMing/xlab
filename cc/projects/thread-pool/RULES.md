# Project Rules and Standards

## Overview

This document defines the engineering standards, coding conventions, and best practices for the Work-Stealing Thread Pool (WSTP) project.

## Code Style

### C++ Standards

- **C++ Standard**: C++20
- **Compiler**: Apple Clang 15+ (primary target)
- **Build System**: CMake 3.16+

### Commands

```bash
# Configure and build
mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
cmake --build . -j4

# Run tests
ctest --output-on-failure

# Run specific test
./test_thread_pool --gtest_filter=ThreadPoolTest.BasicSubmission

# Run benchmarks
./bench_throughput
./bench_latency
```

## Project Structure

```
cc/projects/thread-pool/
├── include/wstp/              # Public headers
│   ├── cache_padding.h        # Cache line utilities
│   ├── status.h              # Status types
│   ├── task.h                # Task definition
│   ├── thread_pool.h         # Main API
│   └── ws_deque.h            # Work-stealing deque
├── src/                       # Implementation
│   ├── thread_pool.cc
│   └── ws_deque.cc
├── tests/                     # Unit tests
│   ├── test_thread_pool.cc
│   └── test_ws_deque.cc
├── bench/                     # Benchmarks
│   ├── bench_throughput.cc
│   └── bench_latency.cc
├── CMakeLists.txt
├── DESIGN.md
└── README.md
```

## Naming Conventions

- **Namespaces**: `snake_case` (e.g., `wstp`)
- **Classes**: `PascalCase` (e.g., `ThreadPool`, `WSDeque`)
- **Functions**: `PascalCase` for public API (e.g., `Submit`, `Stop`)
- **Private methods**: `snake_case_` with trailing underscore
- **Member variables**: `snake_case_` with trailing underscore
- **Constants**: `kPascalCase` (e.g., `kDefaultCapacity`)
- **Macros**: `SCREAMING_SNAKE_CASE` with `WSTP_` prefix
- **Template parameters**: `PascalCase` (e.g., `T`, `F`, `Allocator`)

## Header Organization

```cpp
#ifndef WSTP_THREAD_POOL_H
#define WSTP_THREAD_POOL_H

// 1. Standard library headers
#include <atomic>
#include <condition_variable>
#include <future>
#include <mutex>
#include <thread>
#include <vector>

// 2. Project headers
#include "wstp/task.h"
#include "wstp/ws_deque.h"

namespace wstp {

// Class documentation
/**
 * ThreadPool manages a pool of worker threads for parallel task execution.
 *
 * Features:
 *   - Work-stealing mode for high performance
 *   - Global queue mode for comparison
 *   - std::future-based result retrieval
 *   - Graceful shutdown with Stop()
 *
 * Thread Safety:
 *   All public methods are thread-safe.
 */
class ThreadPool {
  // ...
};

}  // namespace wstp

#endif  // WSTP_THREAD_POOL_H
```

## Memory Ordering Rules

### Critical Principle

**Every atomic operation must have an explicit memory order.**

### Allowed Orderings

| Operation | Ordering | Justification |
|-----------|----------|---------------|
| Counter increments | `relaxed` | No synchronization needed |
| Index reads in owner | `relaxed` | Owner sees its own writes |
| Index writes (publish) | `release` | Ensure data visibility |
| Index reads (consume) | `acquire` | See published data |
| CAS success | `acq_rel` | Full barrier |
| CAS failure | `acquire` | Reload latest state |

### Example Patterns

```cpp
// Publishing data (release)
class Publisher {
  void Publish(Data d) {
    data_ = std::move(d);  // Write data
    ready_.store(true, std::memory_order_release);  // Publish
  }
  Data data_;
  std::atomic<bool> ready_{false};
};

// Consuming data (acquire)
class Consumer {
  Data Consume() {
    while (!ready_.load(std::memory_order_acquire)) {
      // Spin or yield
    }
    return data_;  // Guaranteed to see published data
  }
};
```

## Error Handling

### Status Codes

Use `wstp::Status` for error propagation:

```cpp
enum class StatusCode {
  kOk = 0,
  kInvalidArgument,
  kQueueFull,
  kStopped,
  kUnknown
};

class Status {
 public:
  bool Ok() const { return code_ == StatusCode::kOk; }
  StatusCode Code() const { return code_; }
  const char* Message() const { return message_.c_str(); }

 private:
  StatusCode code_;
  std::string message_;
};
```

### Exception Policy

- **Public API**: Use exceptions for unrecoverable errors
- **Internal**: Use Status or std::optional for expected failures
- **Thread entry**: Catch all exceptions, store error

```cpp
void WorkerThread() {
  try {
    while (running_) {
      RunTask();
    }
  } catch (const std::exception& e) {
    error_ = e.what();
    running_ = false;
  }
}
```

## Testing Standards

### Test Structure

```cpp
#include <gtest/gtest.h>
#include "wstp/thread_pool.h"

using namespace wstp;

class ThreadPoolTest : public ::testing::Test {
 protected:
  void SetUp() override {
    // Setup code
  }

  void TearDown() override {
    // Cleanup code
  }
};

TEST_F(ThreadPoolTest, BasicSubmission) {
  // Arrange
  ThreadPool pool(2, true);

  // Act
  auto future = pool.Submit([]() { return 42; });

  // Assert
  EXPECT_EQ(future.get(), 42);
  pool.Stop();
}
```

### Test Categories

1. **Functional tests** - Correctness
2. **Stress tests** - High contention
3. **Edge cases** - Empty, single element, full
4. **Thread safety** - TSan verified

### Test Naming

Format: `ClassName_TestDescription`

Examples:
- `ThreadPool_BasicSubmission`
- `WSDeque_SingleElementRace`
- `ThreadPool_StressTest`

## Documentation

### Class Documentation

```cpp
/**
 * Work-stealing double-ended queue.
 *
 * Implements the Chase-Lev algorithm for lock-free work stealing.
 *
 * Operations:
 *   - PushBottom: O(1), owned by worker thread
 *   - PopBottom: O(1), owned by worker thread
 *   - StealTop: O(1), lock-free, may fail (contention)
 *
 * Memory Ordering:
 *   - Push uses release to publish tasks
 *   - Steal uses acquire to consume tasks
 *   - CAS uses acq_rel for synchronization
 *
 * @tparam T The element type (must be movable)
 */
template<typename T>
class WSDeque {
  // ...
};
```

### Method Documentation

```cpp
/**
 * Submit a task for execution.
 *
 * @param f The callable to execute
 * @return std::future containing the result
 * @throws std::runtime_error if pool is stopped
 * @threadsafe
 *
 * Example:
 *   auto future = pool.Submit([]() { return compute(); });
 *   int result = future.get();
 */
template <typename F>
std::future<std::invoke_result_t<F>> Submit(F&& f);
```

## Performance Guidelines

### Hot Path Optimizations

```cpp
// Good: Inline hot path
inline Task WSDeque::PopBottom() {
  // Fast path: no contention expected
  size_t b = bottom_.load(std::memory_order_relaxed) - 1;
  // ...
}

// Good: Avoid allocations
using Task = std::function<void()>;  // May allocate
// Better: Small buffer optimization
using Task = InlineFunction<64>;     // Stack allocated
```

### Cache Considerations

```cpp
// Good: Cache line alignment
struct alignas(64) PaddedAtomic {
  std::atomic<size_t> value;
};

// Good: Separate hot and cold data
class ThreadPool {
  // Hot data (frequently accessed)
  alignas(64) std::atomic<bool> stopped_{false};

  // Cold data (rarely accessed)
  std::string name_;
  std::chrono::steady_clock::time_point creation_time_;
};
```

## Build Configuration

### CMake Options

```cmake
# Build type
set(CMAKE_BUILD_TYPE Release)  # Release, Debug, RelWithDebInfo

# Sanitizers
set(CMAKE_CXX_FLAGS "-fsanitize=address")      # ASan
set(CMAKE_CXX_FLAGS "-fsanitize=thread")       # TSan
set(CMAKE_CXX_FLAGS "-fsanitize=undefined")    # UBSan

# Optimizations
set(CMAKE_CXX_FLAGS_RELEASE "-O3 -march=native")
```

### Compiler Warnings

```cmake
add_compile_options(
  -Wall
  -Wextra
  -Wpedantic
  -Werror=return-type
  -Werror=uninitialized
)
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
- `deque`, `pool`, `api`, `bench`, `test`

Examples:
```
feat(deque): add dynamic resizing
fix(pool): handle spurious wakeups
perf(deque): reduce CAS failures
refactor(api): use std::move for tasks
```

## Safety Guidelines

### Thread Safety Checklist

- [ ] All shared state is atomic or mutex-protected
- [ ] Memory orders are explicitly specified
- [ ] No data races (verified with TSan)
- [ ] No deadlocks (lock ordering documented)
- [ ] No use-after-free (smart pointers or RAII)

### Lock-Free Checklist

- [ ] ABA problem considered
- [ ] CAS loops have backoff
- [ ] Memory reclamation strategy
- [ ] Progress guarantee documented (lock-free vs wait-free)

## Resources

- [C++ Memory Model](https://en.cppreference.com/w/cpp/atomic/memory_order)
- [Chase-Lev Paper](https://doi.org/10.1145/1073970.1073974)
- [Thread Safety Analysis](https://clang.llvm.org/docs/ThreadSafetyAnalysis.html)
