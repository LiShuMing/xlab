# AI Agent Guidelines

## Overview

This document provides guidelines for AI Agents working on the Work-Stealing Thread Pool (WSTP) project.

## Project Architecture

WSTP is a production-quality work-stealing thread pool implementation in modern C++20, designed for high-performance parallel task execution.

```
cc/projects/thread-pool/
├── include/wstp/              # Public API headers
│   ├── cache_padding.h        # Cache line alignment
│   ├── status.h              # Status/error types
│   ├── task.h                # Task type definition
│   ├── thread_pool.h         # ThreadPool class (main API)
│   └── ws_deque.h            # Work-stealing deque
├── src/                       # Implementation
│   ├── thread_pool.cc        # ThreadPool implementation
│   └── ws_deque.cc           # WSDeque implementation
├── tests/                     # Unit tests
│   ├── test_thread_pool.cc   # ThreadPool tests
│   └── test_ws_deque.cc      # Deque tests
├── bench/                     # Benchmarks
│   ├── bench_throughput.cc   # Throughput benchmarks
│   └── bench_latency.cc      # Latency benchmarks
├── CMakeLists.txt            # Build configuration
├── DESIGN.md                 # Detailed design notes
└── README.md                 # Comprehensive documentation
```

## Key Components

### ThreadPool (`include/wstp/thread_pool.h`)
Main API for submitting tasks and managing the thread pool.

```cpp
wstp::ThreadPool pool(4, true);  // 4 threads, work-stealing mode
auto future = pool.Submit([]() { return 42; });
int result = future.get();
pool.Stop();
```

### WSDeque (`include/wstp/ws_deque.h`)
Chase-Lev work-stealing deque with lock-free operations.

```cpp
// Owner thread (local operations)
deque.PushBottom(task);  // LIFO
auto task = deque.PopBottom();  // LIFO

// Thief thread (steal operation)
auto task = deque.StealTop();  // FIFO, lock-free
```

### Memory Ordering
Critical for correctness:
- `push_bottom`: `memory_order_release`
- `pop_bottom`: `memory_order_acquire`
- `steal_top`: `memory_order_acq_rel` for CAS

## Build System

```bash
# Create build directory
mkdir build && cd build

# Configure
cmake -DCMAKE_BUILD_TYPE=Release ..

# Build all targets
cmake --build . -j4

# Run tests
ctest --output-on-failure

# Run specific test
./test_thread_pool

# Run benchmarks
./bench_throughput
./bench_latency
```

## Dependencies

- **CMake 3.16+**
- **C++20 compiler** (Apple Clang 15+ on macOS)
- **GoogleTest** (submodule)

## Common Tasks

### Adding a New Feature

1. Update header in `include/wstp/`
2. Implement in `src/`
3. Add tests in `tests/`
4. Update documentation

### Writing a Test

```cpp
// tests/test_thread_pool.cc
TEST(ThreadPoolTest, MyNewFeature) {
  ThreadPool pool(2, true);

  auto future = pool.Submit([]() {
    return compute_something();
  });

  EXPECT_EQ(future.get(), expected_value);
  pool.Stop();
}
```

### Adding a Benchmark

```cpp
// bench/bench_throughput.cc
static void BM_MyBenchmark(benchmark::State& state) {
  ThreadPool pool(state.range(0), true);

  for (auto _ : state) {
    // Benchmark code
    std::vector<std::future<int>> futures;
    for (int i = 0; i < 1000; ++i) {
      futures.push_back(pool.Submit([i]() { return i * 2; }));
    }
    for (auto& f : futures) {
      f.get();
    }
  }

  pool.Stop();
}
BENCHMARK(BM_MyBenchmark)->Arg(1)->Arg(2)->Arg(4);
```

## Thread Safety Guidelines

### Safe Operations
- `Submit()` - Thread-safe
- `Stop()` - Thread-safe, idempotent
- `NumThreads()` - Thread-safe
- `IsStopped()` - Thread-safe

### Unsafe Operations
- None - all public APIs are thread-safe

### Internal Synchronization
- Global queue: mutex protected
- Per-thread deques: lock-free Chase-Lev algorithm
- Stop flag: atomic with acquire/release

## Memory Ordering Rules

### Push Bottom (Owner)
```cpp
void PushBottom(Task task) {
  size_t b = bottom_.load(relaxed);
  buffer_[b & mask] = std::move(task);
  bottom_.store(b + 1, release);  // Release: publish task
}
```

### Pop Bottom (Owner)
```cpp
Task PopBottom() {
  size_t b = bottom_.load(relaxed) - 1;
  bottom_.store(b, relaxed);
  fence(acquire);  // Ensure top/bottom consistency
  size_t t = top_.load(acquire);
  // ... handle race with thief
}
```

### Steal Top (Thief)
```cpp
Task StealTop() {
  size_t t = top_.load(acquire);  // Acquire: see published tasks
  size_t b = bottom_.load(acquire);
  if (t < b) {
    Task task = buffer_[t & mask];
    if (top_.compare_exchange_strong(t, t + 1, acq_rel)) {
      return task;  // AcqRel: synchronize with push and pop
    }
  }
  return nullptr;
}
```

## Prohibited Actions

1. **DO NOT** use `std::memory_order_relaxed` for index updates without careful analysis
2. **DO NOT** ignore CAS failure in steal_top (retry or return nullptr)
3. **DO NOT** submit tasks after Stop() without checking IsStopped()
4. **DO NOT** forget to call pool.Stop() or use RAII
5. **DO NOT** use blocking operations in submitted tasks (blocks worker)

## Performance Considerations

### Optimal Task Size
- Too small: overhead dominates
- Too large: underutilization
- Sweet spot: 1-10ms per task

### Work-Stealing vs Global Queue
- Work-stealing: better for fine-grained parallelism
- Global queue: simpler, good for coarse-grained
- Hybrid: future consideration

### False Sharing
- Cache line alignment (64 bytes) for hot data
- Separate cache lines for different threads

## Debugging Tips

### Detecting Race Conditions
```bash
# Build with TSan (ThreadSanitizer)
cmake -DCMAKE_CXX_FLAGS="-fsanitize=thread" ..
cmake --build .
./test_thread_pool
```

### Checking Memory Ordering
```bash
# Build with ASan (AddressSanitizer)
cmake -DCMAKE_CXX_FLAGS="-fsanitize=address" ..
cmake --build .
```

### Profiling
```bash
# Instruments (macOS)
instruments -t "Time Profiler" ./bench_throughput

# Count steals
# Add logging in StealTop() to count successful steals
```

## Resources

- [Chase-Lev Paper](https://doi.org/10.1145/1073970.1073974)
- [C++ Memory Model](https://en.cppreference.com/w/cpp/atomic/memory_order)
- [Preshing on Programming](https://preshing.com/)

## Communication Style

- Emphasize memory ordering correctness
- Reference specific C++ standard sections
- Show before/after code examples
- Explain trade-offs clearly
