# AI Agent Guidelines

## Overview

This document provides guidelines for AI Agents working on the Work-Stealing Thread Pool (WSTP) project.

## Project Architecture

WSTP is a work-stealing thread pool experiment in modern C++20.

The current deque uses a mutex-protected growing ring buffer to preserve task
ownership; it is not lock-free. Local pops are LIFO and steals are FIFO. The
Chase-Lev and index-ordering examples in this document describe the historical
design. `Stop()` drains accepted tasks, and concurrent stop calls wait for joins.
Use `../../../tools/build-windows.ps1 -Project thread-pool` from this directory,
or consult the root `WINDOWS.md`. Benchmarks require `XLAB_BUILD_BENCHMARKS=ON`.

```
labs/runtime/pool/
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

## 工程规范

以下条款原先独立成 `RULES.md`，已并入本文件。

### 错误处理

- 错误传播用 `wstp::Status`（`StatusCode`：`kOk`/`kInvalidArgument`/`kQueueFull`/`kStopped`/`kUnknown`）。
- 公开 API 用异常报告不可恢复错误；内部用 `Status`/`std::optional` 报告预期失败。
- 线程入口必须 catch 所有异常并记录，不允许异常逸出线程函数。

### 测试

- 用 gtest fixture（`SetUp`/`TearDown`）管资源，测试结束后必须 `Stop()` 线程池。
- 四类必覆盖：功能正确性、高竞争压力、边界（空/单元素/队列满）、线程安全（TSan 验证）。
- 命名 `ClassName_TestDescription`，如 `WSDeque_SingleElementRace`。

### 文档

- 类注释写算法名称、各操作复杂度与内存序职责（哪一步 release 发布、哪一步 acquire 消费、
  CAS 用 acq_rel）。
- 公开方法注释带 `@param`/`@return`/`@throws` 与 `@threadsafe` 标记。

### 性能

- 热路径内联且避免分配；小任务优先栈上存储而不是 `std::function` 堆分配。
- 跨线程频繁写的原子量用 `alignas(64)` 避免伪共享；热数据与冷数据分开布局。

### 构建

- 构建类型 `Release`/`Debug`/`RelWithDebInfo`；竞态用 `-fsanitize=thread`、内存用
  `-fsanitize=address`、未定义行为用 `-fsanitize=undefined`。
- 警告：`-Wall -Wextra -Wpedantic -Werror=return-type -Werror=uninitialized`。

### 提交信息

`<type>(<scope>): <description>`，scope 取 `deque`/`pool`/`api`/`bench`/`test`，
type 取 `feat`/`fix`/`perf`/`refactor`/`test`/`docs`，例如 `perf(deque): reduce CAS failures`。

### 安全检查清单

线程安全：共享状态均为 atomic 或 mutex 保护；内存序显式；TSan 无竞态；死锁顺序有文档；
无 use-after-free（智能指针或 RAII）。
无锁代码额外检查：ABA 已考虑；CAS 循环有退避；内存回收策略明确；进度保证
（lock-free vs wait-free）有文档。

## 待办（原 TODOS.md）

### 已知局限

- [ ] deque 容量固定（每 worker 1024 个任务），无动态扩容与满时反压
- [ ] 无任务取消机制；`Stop()` 不中断正在运行的任务
- [ ] 无优先级、无任务亲和（任务可能迁移）
- [ ] `std::function` 对小任务有分配开销
- [ ] worker 可能偶发虚假唤醒；无线程数动态调整；worker 异常回传有限

### 计划改进

- [ ] 动态 deque 扩容（grow-only、内存映射环形缓冲、满时反压）
- [ ] 小对象优化：小 functor 内联存储，去掉 `std::function` 分配
- [ ] 性能计数器：提交/完成数、steal 尝试与成功数、CAS 失败率、队列深度直方图
- [ ] NUMA 感知分配：按 NUMA 节点线程本地存储与内存绑定
- [ ] 任务优先级、任务依赖（DAG 执行、continuation 链）、工作亲和
- [ ] 线程池自动伸缩（按负载、空闲超时）、worker 异常汇聚
- [ ] 测试补强：WSDeque fuzz、百万级压力、长稳定运行、性能回归、TSan/ASan 进 CI
- [ ] 文档补强：Doxygen API 参考、并行算法/流水线/生产者消费者示例、死锁与调优排障指南

### 设计决策（沿用）

- 选用 Chase-Lev：steal 无锁、缓存局部性好，Java `ForkJoinPool` 等已验证。
- 容量固定：简化实现并避开扩容带来的 ABA，1024 对大多数场景够用，动态扩容列为后续。
- `std::function` 任务：保留任意可调用体的灵活性，代价是小任务分配开销，后续做小对象优化。

### 性能目标

当前（Phase 2）：单核百万级微小任务/秒，p50 < 1µs、p99 < 10µs。
目标（Phase 3）：单核 5M+ 任务/秒、小任务零分配、动态伸缩。

## Resources

- [Chase-Lev Paper](https://doi.org/10.1145/1073970.1073974)
- [C++ Memory Model](https://en.cppreference.com/w/cpp/atomic/memory_order)
- [Preshing on Programming](https://preshing.com/)

## Communication Style

- Emphasize memory ordering correctness
- Reference specific C++ standard sections
- Show before/after code examples
- Explain trade-offs clearly
