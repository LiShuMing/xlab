# AI Agent Guidelines

## Overview

This document provides guidelines for AI Agents working on the MiniSeastar project.

## Project Architecture

MiniSeastar is a C++20 coroutine-based asynchronous runtime inspired by Seastar. It's designed for learning modern C++ coroutines and high-performance async I/O patterns.

```
labs/runtime/reactor/
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

## 工程规范

以下条款原先独立成 `RULES.md`，已并入本文件。

### 协程契约

- `Task<T>` 必须 move-only（拷贝构造/赋值 `= delete`），析构负责销毁协程帧；
  构造/移动均 `noexcept`。
- promise 类型必须实现 `initial_suspend`/`final_suspend`（均为 `suspend_always`）、
  `return_value`（或 `return_void`）、`unhandled_exception`、`get_return_object`。
- awaiter 三个方法齐备：`await_ready() const noexcept`、`await_suspend(coroutine_handle<>) noexcept`、
  `await_resume()`。

### 协程帧与内存

- 帧默认堆分配；自定义 allocator 属于 Phase 3。
- 析构 `Task` 会销毁帧——**不得销毁运行中的协程**，不得 move 后继续引用旧对象。

### 异常与内存序

- `unhandled_exception` 存 `std::current_exception()` 并用 `release` 置 ready。
- 不变量：写侧（`return_value`/`unhandled_exception`）用 `release`，读侧
  （`get_result`/`is_ready`）用 `acquire`；不用无理由的 `relaxed`。
- 异常在 `await_resume` 中重抛，调用方用 `try`/`catch` 接收；清理一律 RAII。

### I/O 错误与部分操作

- `EAGAIN`/`EWOULDBLOCK` 不是错误：注册可读/可写后挂起并重试；其余 errno 抛
  `std::system_error(errno, std::system_category())`。
- 读写在循环里推进游标，直到字节数满足；短读写、连接重置、信号中断都要处理。

### 测试与文档

- gtest fixture（`SetUp`/`TearDown`）；三层覆盖：单元（单组件）、集成（组件交互）、
  基准（性能）。
- 头文件注释写清类型职责、组合方式与示例（`@tparam` 等）；实现处注释只解释同步关系
  与不变量（如“release 与 acquire 成对”“continuation_ 仅在 has_continuation() 为真时有效”）。

### 构建

- CMake 选项：`CMAKE_BUILD_TYPE`（默认 `RelWithDebInfo`）、`MS_USE_ASAN`（默认 OFF）、
  `CMAKE_CXX_STANDARD`（默认 23）。
- 编译旗标：`-fcoroutines-ts -std=c++23`；ASAN 构建加 `-fsanitize=address -fno-omit-frame-pointer`；
  发布加 `-O2 -DNDEBUG`。

### 线程与资源安全

- `Task<T>` 默认非线程安全；共享状态用原子；调度器在 Phase 1–3 是单线程的。
- 文件描述符等系统资源一律 RAII 包装（move-only），不写手工 `close`。

### 提交信息

`<type>(<scope>): <description>`，scope 取 `task`/`scheduler`/`awaitable`/`runtime`/`test`，
type 取 `feat`/`fix`/`docs`/`refactor`/`perf`/`test`，例如
`perf(task): optimize coroutine frame allocation`。

## 待办（原 TODOS.md）

### Phase 1 遗留

- [ ] 自定义协程帧 allocator（现用默认 new/delete）
- [ ] 仅单线程；示例错误处理有限；部分边界用例缺失

### Phase 2（kqueue，进行中）

- [ ] kqueue 集成；`awaitable_read`/`awaitable_write`/`awaitable_accept`
- [ ] echo server demo；连接生命周期管理；`EAGAIN` 与部分读写处理

### Phase 3（性能）

- [ ] 协程帧 allocator：按线程 arena、常用尺寸 free list、任务内存池
- [ ] 指标采集：任务创建/完成数、上下文切换、每秒 syscall、ready 队列深度
- [ ] Instruments 采样指南（Time Profiler / System Trace / 内存分配）

### Phase 4（多线程）

- [ ] 多 reactor：每线程一个 reactor、线程本地调度器
- [ ] accept 分发（轮询、`SO_REUSEPORT`）；跨线程消息（MPSC 队列，可选 work stealing）

### 其他特性与验证

- [ ] I/O 超时、取消令牌、信号处理、文件 I/O（`pread`/`pwrite`）、`sendfile` 零拷贝
- [ ] TLS/SSL、HTTP 解析器、WebSocket
- [ ] 协议解析 fuzz、万连接压力、内存泄漏检测、性能回归
- [ ] 文档：Doxygen API 参考、系列教程、架构决策记录、调优指南

### 设计决策（沿用）

- 选 C++20 协程：零开销潜力、可组合、类型安全；选 kqueue：macOS 原生、高连接数高效；
  先单线程：易实现易调试，先立核心模式。

### 性能目标

Phase 1：百万次创建/恢复 < 1s，单任务内存 ~100–200B。Phase 2：echo 万并发连接，
localhost p99 < 1ms。Phase 3：协程分配 < 50ns，上下文切换 < 100ns。Phase 4：随核数
线性扩展、全核 1M+ 连接。

### 常见陷阱

1. 协程帧生命周期：必须比引用活得更久，随 `Task` 销毁而销毁，move 后不得访问原对象。
2. 异常安全：必须实现 `unhandled_exception`，必要时在 `await_resume` 重抛，用 RAII 清理。
3. 内存序：ready 标志用 acquire/release，不用无理由的 relaxed，并把选择写进注释。
4. I/O 边界：`EAGAIN`/`EWOULDBLOCK`、部分读写、连接重置、信号中断。

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
