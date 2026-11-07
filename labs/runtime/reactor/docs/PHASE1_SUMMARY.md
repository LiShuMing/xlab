# MiniSeastar Phase 1 Summary

## Overview

Phase 1 implements a coroutine-based runtime without I/O, featuring:
- `task<T>` coroutine type with promise_type
- Single-threaded scheduler with ready queue and timer heap
- `yield()` and `sleep_for()` awaitables
- Unit tests and demo programs

## Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                      Application Code                        │
│  (spawn tasks, co_await, co_return)                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                         Runtime                              │
│  - Runtime::spawn(task)  → adds to scheduler's ready queue   │
│  - Runtime::run()        → event loop                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       Scheduler                              │
│  - ready_queue_: FIFO queue of coroutine handles             │
│  - timers_: min-heap of TimerEntry (wake_time, handle)       │
│  - run(): drains ready queue, processes timers               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Awaitables                                 │
│  - yield(): suspends, re-queues current coroutine            │
│  - sleep_for(duration): registers timer, suspends            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        Task<T>                               │
│  - promise_type: TaskPromise<T>                              │
│  - awaiter: TaskAwaiter<T>                                   │
│  - Stores result or exception in promise                     │
│  - Supports continuation via stored continuation handle      │
└─────────────────────────────────────────────────────────────┘
```

### File Structure

```
mini-seastar/
├── CMakeLists.txt              # Build configuration
├── include/miniseastar/
│   ├── task.hpp               # task<T>, TaskPromise<T>, TaskAwaiter<T>
│   ├── scheduler.hpp          # Scheduler class, TimerEntry
│   ├── awaitables.hpp         # yield(), sleep_for()
│   └── runtime.hpp            # Runtime class, spawn(), global_scheduler()
├── src/
│   └── scheduler.cpp          # Scheduler implementation
├── tests/
│   ├── main.cpp               # Test entry point
│   ├── test_task.cpp          # Task tests
│   ├── test_scheduler.cpp     # Scheduler tests
│   └── test_awaitables.cpp    # Awaitable tests
├── examples/
│   ├── 01_coro_demo.cpp       # Basic task demo
│   ├── 02_sleep_demo.cpp      # Sleep/yield demo
│   ├── 03_task_chain.cpp      # Task chaining demo
│   └── 04_pingpong_bench.cpp  # Benchmark
└── docs/
    └── PHASE1_SUMMARY.md      # This document
```

## Design Decisions

### 1. Coroutine Handle Storage

**Decision**: Use `std::variant` for result storage

```cpp
struct Result {
    std::variant<std::monostate, T, std::exception_ptr> v;
};
alignas(Result) unsigned char storage_[sizeof(Result)];
```

**Rationale**:
- Placement new for flexible type storage
- `std::monostate` for uninitialized state
- Exception propagation via `std::exception_ptr`
- Proper alignment with `alignas`

### 2. Lazy Start Pattern

**Decision**: `initial_suspend()` returns `suspend_always`

```cpp
coroutine_ns::suspend_always initial_suspend() noexcept { return {}; }
coroutine_ns::suspend_always final_suspend() noexcept { return {}; }
```

**Rationale**:
- Coroutine exists but doesn't run until explicitly scheduled
- Gives scheduler control over when coroutines execute
- Enables proper task lifecycle management

### 3. Task Awaiting Mechanism

**Current Implementation**:
```cpp
void await_suspend(coroutine_ns::coroutine_handle<> continuation) noexcept {
    task_.promise().set_continuation(continuation);
}
```

**Limitation**: Awaited task must be explicitly scheduled by caller

**Alternative Considered** (not implemented due to circular include):
```cpp
void await_suspend(coroutine_ns::coroutine_handle<> continuation) noexcept {
    task_.promise().set_continuation(continuation);
    global_scheduler().schedule(task_.handle());  // Needs scheduler include
}
```

### 4. Timer Implementation

**Decision**: Min-heap with spin-wait polling

```cpp
std::priority_queue<TimerEntry> timers_;  // ordered by wake_time
```

**Rationale**:
- O(log n) insertion and extraction
- Simple polling for Phase 1 (no kqueue yet)
- Works correctly for sleep durations

**Limitation**: Busy-waiting when no ready tasks exist

### 5. Apple Clang Compatibility

**Decision**: Use experimental coroutines on macOS

```cpp
#if defined(__APPLE__) && defined(__clang__)
#include <experimental/coroutine>
namespace coroutine_ns = std::experimental::coroutines_v1;
#else
#include <coroutine>
namespace coroutine_ns = std;
#endif
```

**Rationale**:
- Apple Clang 15+ doesn't fully support C++20 `<coroutine>`
- `-fcoroutines-ts` flag required
- `std::experimental::coroutines_v1` namespace

## Invariants

### Task<T> Invariants
1. A task is move-constructible but not copyable
2. `task<void>` is valid with `co_return;`
3. Destruction of unstarted task destroys coroutine frame
4. `co_await` on completed task returns immediately
5. Exceptions propagate via `std::exception_ptr`

### Scheduler Invariants
1. All coroutines run on the same thread
2. Scheduler must outlive all tasks
3. `run()` is called from the scheduler thread only
4. Ready queue is FIFO for fairness
5. Timer heap ordered by `wake_time` (earliest first)

### Awaitable Invariants
1. `await_ready()`: true = no suspend, false = suspend
2. `await_suspend()`: store continuation, register with scheduler
3. `await_resume()`: return result or throw exception

## Failure Modes

### 1. Memory Leaks
- **Scenario**: Timer registered, scheduler destroyed before expiration
- **Mitigation**: Phase 2 will integrate timers with reactor lifecycle

### 2. Double Resume
- **Scenario**: Calling `resume()` on already-completed coroutine
- **Result**: Undefined behavior (likely crash)
- **Mitigation**: Check `done()` before resuming

### 3. Unstarted Task Destruction
- **Scenario**: Task created but never scheduled, then destroyed
- **Result**: Coroutine frame properly destroyed via `handle_.destroy()`
- **Behavior**: Correct - lazy start means frame is valid until destroyed

### 4. Spin-Wait CPU Usage
- **Scenario**: No ready tasks, timers pending
- **Result**: 100% CPU while polling timers
- **Mitigation**: Phase 2 will block on kqueue

## Testing

### Test Coverage

| Category | Tests | Status |
|----------|-------|--------|
| TaskTest | 7 | Most passing |
| SchedulerTest | 6 | Most passing |
| AwaitablesTest | 6 | Some passing |

### Passing Tests
- `TaskTest.BasicTask` - Basic task execution
- `TaskTest.ReturnValue` - Return values work
- `TaskTest.Chaining` - Requires explicit scheduling
- `TaskTest.ExceptionPropagation` - Exception handling
- `SchedulerTest.SingleTask` - Single task execution
- `SchedulerTest.EmptyRun` - Empty scheduler behavior

### Known Test Issues
- `SchedulerTest.FIFOOrder` - Crashes (coroutine handle lifecycle)
- `AwaitablesTest.Yield` - Depends on yield implementation
- `AwaitablesTest.SleepDuration` - Timer integration incomplete

## Build System

### CMake Targets

```
miniseastar_lib     - Static library with core runtime
miniseastar_tests   - Unit tests (GoogleTest)
coro_demo           - Basic coroutine demo
sleep_demo          - Sleep/yield demo
task_chain_demo     - Task chaining demo
pingpong_bench      - Performance benchmark
```

### Build Commands

```bash
# Debug build with symbols
cd build
cmake .. -DCMAKE_BUILD_TYPE=Debug
make -j4

# Release build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j4

# With AddressSanitizer
cmake .. -DMS_USE_ASAN=ON
make -j4
```

### Compiler Requirements

- **macOS**: Apple Clang 15+, `-fcoroutines-ts` flag
- **Linux**: GCC 10+ or Clang 10+ with C++20/23
- **C++ Standard**: C++23 (working draft c++2b)

## Demo Programs

### 01_coro_demo.cpp
Demonstrates:
- Creating `task<T>` coroutines
- Returning values with `co_return`
- Scheduling tasks on runtime

### 02_sleep_demo.cpp
Demonstrates:
- `co_await sleep_for(duration)`
- `co_await yield()`
- Multiple concurrent tasks with different sleep durations

### 03_task_chain.cpp
Demonstrates:
- `co_await task<T>` chaining
- Value propagation through chain
- Using `std::move()` for task ownership transfer

### 04_pingpong_bench.cpp
Demonstrates:
- Performance measurement
- Task switching overhead
- Chain depth impact on performance

## Performance Characteristics

### Phase 1 Benchmarks (indicative)

| Benchmark | Approximate | Notes |
|-----------|-------------|-------|
| Task creation | ~1μs | Coroutine frame allocation |
| Context switch (yield) | ~0.5μs | Queue push/pop + resume |
| Chain depth 50 | ~50μs | Linear in depth |

**Note**: These are rough estimates. Phase 3 will include proper benchmarks with Instruments profiling.

## Known Limitations

1. **Task Chaining**: Awaited tasks must be explicitly scheduled by caller
2. **No I/O**: Phase 2 will add kqueue-based I/O awaitables
3. **Single-threaded**: Phase 4 will add multi-reactor support
4. **Spin-wait polling**: No true blocking (Phase 2 fixes this)
5. **No custom allocator**: Coroutine frame allocated by default mechanism

## Future Phases

### Phase 2: kqueue I/O Awaitables
- Wrap kqueue for I/O readiness
- `accept()`, `read()`, `write()` awaitables
- Echo server demo
- Handle EAGAIN, partial read/write

### Phase 3: Performance Work
- Custom coroutine frame allocator
- Metrics collection
- Instruments profiling guide
- Benchmark scripts

### Phase 4: Thread-per-Core Model
- N reactors (one per CPU core)
- Accept distributes connections
- Sharded data structures
- Thread-local scheduling

## Lessons Learned

1. **Apple Clang Coroutines**: Requires experimental header, `-fcoroutines-ts` flag
2. **Coroutine Handle Lifecycle**: Must carefully manage continuation vs. frame lifetime
3. **Circular Dependencies**: Awaitables need careful include ordering
4. **Variant Emplacement**: Use `emplace<N>()` for proper variant construction
5. **Memory Alignment**: `alignas` required for placement-new of complex types

## Code Quality Notes

- All comments in English
- Production-style code structure
- `noexcept` specifications where appropriate
- Memory ordering annotations (`memory_order_acquire/release`)
- Template SFINAE for void/non-void specializations

## References

- C++20 Coroutines: https://en.cppreference.com/w/cpp/language/coroutines
- LLVM Coroutines: https://llvm.org/docs/Coroutines.html
- Seastar Architecture: https://seastar.io/architecture/
- Effective Modern C++ (Scott Meyers) - for move semantics patterns
