# Work-Stealing Thread Pool (WSTP)

A production-quality work-stealing thread pool implementation in modern C++20, designed for learning and real-world use on macOS.

## Table of Contents

1. [Why Work-Stealing?](#why-work-stealing)
2. [Architecture Overview](#architecture-overview)
3. [Memory Ordering Deep Dive](#memory-ordering-deep-dive)
4. [API Reference](#api-reference)
5. [Building](#building)
6. [Testing](#testing)
7. [Benchmarking](#benchmarking)
8. [Profiling on macOS](#profiling-on-macos)
9. [Design Decisions](#design-decisions)

---

## Why Work-Stealing?

### The Problem with Global Queue

A traditional thread pool uses a single global queue protected by a mutex:

```cpp
// Traditional global queue - bottleneck!
std::queue<Task> global_queue;
std::mutex queue_mutex;

// Thread 1: push
{
  std::lock_guard lock(queue_mutex);
  queue.push(task);  // Contention!
}

// Thread 2: pop
{
  std::lock_guard lock(queue_mutex);
  auto task = queue.front();  // Contention!
  queue.pop();
}
```

**Bottlenecks:**
- **Lock contention**: More threads = more contention on the mutex
- **Cache line ping-pong**: All threads access the same queue structure
- **Context switches**: Threads block on the mutex when queue is empty
- **Load imbalance**: One thread may be overloaded while others idle

### The Work-Stealing Solution

Each worker has its own deque (double-ended queue):

```
Worker 0          Worker 1          Worker 2
┌─────────┐       ┌─────────┐       ┌─────────┐
│ Task A  │       │ Task D  │       │ Task G  │
│ Task B  │       │ Task E  │       │ Task H  │
└────┬────┘       └────┬────┘       └────┬────┘
     │                 │                 │
     └─ Local: LIFO    └─ Local: LIFO    └─ Local: LIFO
        push/pop          push/pop          push/pop

              ↑                          ↓
              └────── Steal: FIFO ───────┘
```

**Key insight:**
- **Owner thread**: `push_bottom()` / `pop_bottom()` - local, almost no contention
- **Thief thread**: `steal_top()` - remote, occasional contention when idle

This reduces global synchronization to a minimum while keeping all CPU cores busy.

---

## Architecture Overview

### File Structure

```
thread-pool/
  CMakeLists.txt          # Build configuration
  DESIGN.md               # Detailed design notes
  include/wstp/
    cache_padding.h       # Cache line alignment utilities
    status.h              # Status/error types
    task.h                # Task type definition
    thread_pool.h         # ThreadPool class (main API)
    ws_deque.h            # Work-stealing deque
  src/
    thread_pool.cc        # Implementation
    ws_deque.cc           # Deque implementation
  tests/
    test_thread_pool.cc   # ThreadPool unit tests
    test_ws_deque.cc      # Deque unit tests
  bench/
    bench_latency.cc      # Latency benchmarks
    bench_throughput.cc   # Throughput benchmarks
```

### Two Modes

```cpp
// Phase 1: Global queue (baseline, for comparison)
ThreadPool pool(4, false);  // false = use global mutex queue

// Phase 2: Work-stealing (recommended for production)
ThreadPool pool(4, true);   // true = use per-thread deques
```

---

## Memory Ordering Deep Dive

This is the most important part for understanding concurrent programming.

### What is Memory Ordering?

In C++, `std::atomic` operations have different "memory orders" that control:
1. **Visibility**: When changes are visible to other threads
2. **Reordering**: Whether the CPU/hardware can reorder operations

### Memory Orderings in WSTP

| Ordering | Use Case | Guarantee |
|----------|----------|-----------|
| `relaxed` | Counter increments | No ordering guarantees |
| `acquire` | Reading shared state | All prior writes visible |
| `release` | Publishing data | All prior writes visible to readers |
| `acq_rel` | CAS operations | Full barrier on success/failure |

### Why Each Operation Uses Specific Ordering

#### 1. `push_bottom()` - Release

```cpp
void WSDeque::PushBottom(Task task) {
  size_t b = bottom_.load(std::memory_order_relaxed);
  buffer_[b & mask] = std::move(task);              // Write task data
  bottom_.store(b + 1, std::memory_order_release);  // Release index
}
```

**Why release?** We must ensure the task data is written BEFORE the index is published. If a thief reads `bottom > b`, it must see the task data, not stale memory.

#### 2. `pop_bottom()` - Acquire

```cpp
Task WSDeque::PopBottom() {
  size_t b = bottom_.load(std::memory_order_acquire) - 1;
  std::atomic_thread_fence(std::memory_order_acquire);
  size_t t = top_.load(std::memory_order_acquire);
  // ... use consistent top/bottom values
}
```

**Why acquire?** We must see a consistent snapshot of `top` and `bottom`. If `top` was updated by a thief, we must see that update.

#### 3. `steal_top()` - Acquire + AcqRel CAS

```cpp
Task WSDeque::StealTop() {
  size_t t = top_.load(std::memory_order_acquire);  // Acquire consistent view
  size_t b = bottom_.load(std::memory_order_acquire);
  if (t >= b) return nullptr;  // Empty

  Task task = std::move(buffer_[t & mask]);

  // CAS must be acq_rel to synchronize with both push and pop
  bool success = top_.compare_exchange_strong(
      t, t + 1, std::memory_order_acq_rel, std::memory_order_acquire);

  return success ? task : nullptr;
}
```

**Why acq_rel for CAS?** On success, we must publish our `top` update so other threads see it. On failure, we must acquire the latest state.

### Single-Element Race

The most subtle bug in work-stealing deques:

```
Timeline:
───────────────────────────────────────────────────────────
T1 (owner):  reads b=1, reads t=0, size=1
             decrements b to 0
T2 (thief):  reads t=0, reads task at buffer[0]
             CAS top: 0→1
T1 (owner):  CAS top: 0→1 (FAILS! Thief won)
```

**Solution:** The CAS in `pop_bottom()` detects this race and returns `nullptr`, letting the owner know the task was stolen.

---

## API Reference

### ThreadPool Class

```cpp
namespace wstp {

class ThreadPool {
 public:
  // Create pool with num_threads workers
  // use_work_stealing: true = work-stealing, false = global queue
  explicit ThreadPool(size_t num_threads = 0, bool use_work_stealing = false);

  // Destructor calls Stop()
  ~ThreadPool();

  // Submit a callable for execution
  // Returns std::future with the result
  // Throws std::runtime_error if pool is stopped
  template <typename F>
  std::future<std::invoke_result_t<F>> Submit(F&& f);

  // Submit with arguments
  template <typename F, typename... Args>
  std::future<std::invoke_result_t<F, Args...>> Submit(F&& f, Args&&... args);

  // Graceful stop - waits for all submitted tasks to complete
  // Idempotent (safe to call multiple times)
  void Stop();

  // Get number of worker threads
  size_t NumThreads() const;

  // Get approximate queue size (for debugging)
  size_t QueueSize() const;

  // Check if pool is stopped
  bool IsStopped() const;
};

}  // namespace wstp
```

### Usage Examples

#### Basic Usage

```cpp
#include "wstp/thread_pool.h"

int main() {
  wstp::ThreadPool pool(4, true);  // 4 threads, work-stealing mode

  // Submit a simple task
  auto future = pool.Submit([]() { return 42; });
  int result = future.get();  // result == 42

  // Submit with arguments
  auto sum_future = pool.Submit([](int a, int b) { return a + b; }, 3, 4);
  int sum = sum_future.get();  // sum == 7

  // Stop the pool (waits for all tasks to complete)
  pool.Stop();

  return 0;
}
```

#### Parallel Computation

```cpp
wstp::ThreadPool pool(std::thread::hardware_concurrency(), true);
const int N = 1000000;
std::vector<int> data(N);
std::iota(data.begin(), data.end(), 1);

std::atomic<int> sum{0};
std::vector<std::future<void>> futures;

int chunk_size = N / pool.NumThreads();
for (int i = 0; i < pool.NumThreads(); ++i) {
  int start = i * chunk_size;
  int end = (i == pool.NumThreads() - 1) ? N : start + chunk_size;
  futures.push_back(pool.Submit([&data, &sum, start, end]() {
    int local_sum = 0;
    for (int j = start; j < end; ++j) {
      local_sum += data[j];
    }
    sum.fetch_add(local_sum);
  }));
}

// Wait for all
for (auto& f : futures) {
  f.get();
}

pool.Stop();
```

#### Fork-Join Pattern

```cpp
// Recursive parallel sum using work-stealing
std::function<int(int, int)> parallel_sum = [&](int begin, int end) -> int {
  int size = end - begin;
  if (size <= 1000) {
    // Sequential base case
    return std::accumulate(data.begin() + begin, data.begin() + end, 0);
  }
  int mid = begin + size / 2;
  auto left = pool.Submit(parallel_sum, begin, mid);
  int right = parallel_sum(mid, end);  // Continue recursively
  return left.get() + right;
};

auto future = pool.Submit(parallel_sum, 0, N);
int total = future.get();
```

---

## Building

### Prerequisites

- macOS (Apple Silicon or Intel)
- CMake 3.16+
- C++20 compatible compiler (AppleClang 15+)
- Git (for submodules)

### Build Steps

```bash
cd thread-pool
mkdir build && cd build

# Configure with CMake
cmake -DCMAKE_BUILD_TYPE=Release ..

# Build all targets
cmake --build . -j4

# Or build specific targets
cmake --build . --target wstp          # Library only
cmake --build . --target test_thread_pool  # ThreadPool tests
cmake --build . --target test_ws_deque     # Deque tests
cmake --build . --target bench_throughput  # Throughput benchmark
cmake --build . --target bench_latency     # Latency benchmark
```

### Build Options

```bash
# Debug build with sanitizers
cmake -DCMAKE_BUILD_TYPE=Debug -DCMAKE_CXX_FLAGS="-fsanitize=address" ..

# Release build with optimizations
cmake -DCMAKE_BUILD_TYPE=Release ..

# Build with more threads
cmake --build . -j8
```

---

## Testing

### Run All Tests

```bash
cd build
ctest --output-on-failure
```

### Run Specific Tests

```bash
# Run thread pool tests
./test_thread_pool

# Run deque tests
./test_ws_deque

# Run with verbose output
./test_thread_pool --gtest_filter=*Basic*
./test_thread_pool --gtest_filter=ThreadPoolTest.*
```

### Test Categories

**ThreadPool Tests:**
- `BasicSubmission` - Single task submission
- `MultipleSubmissions` - Many tasks
- `VoidTaskExecution` - Tasks without return value
- `StopIdempotent` - Multiple Stop() calls
- `SubmitAfterStop` - Behavior after shutdown
- `ParallelSum` - Parallel computation
- `WorkStealingBasic` - Work-stealing mode
- `StressTest` - High contention

**WSDeque Tests:**
- `EmptyDeques` - Empty state
- `PushPop` - Basic push/pop operations
- `SingleElementRace` - Owner/thief race handling
- `MultipleOwnersMultipleThieves` - Concurrent access

---

## Benchmarking

### Throughput Benchmarks

```bash
# Run throughput benchmarks
./bench_throughput --benchmark_min_time=5s

# Run specific benchmark
./bench_throughput --benchmark_filter="BM_Throughput_TinyTask_WorkStealing"

# Output to CSV
./bench_throughput --benchmark_format=csv > results.csv
```

**Key Benchmarks:**
- `BM_Throughput_TinyTask_GlobalQueue` - Baseline: tiny tasks with global queue
- `BM_Throughput_TinyTask_WorkStealing` - Work-stealing mode
- `BM_ForkJoin_LinearChain_*` - Fork-join pattern performance

### Latency Benchmarks

```bash
# Run latency benchmarks
./bench_latency --benchmark_min_time=5s

# Key metrics:
# - avg_ns: Average submit-to-start latency
# - min_ns: Best case latency
# - max_ns: Worst case latency
```

### Interpreting Results

Expected results (may vary by hardware):

| Benchmark | Global Queue | Work-Stealing | Improvement |
|-----------|-------------|---------------|-------------|
| Tiny task throughput | ~X tasks/s | ~Y tasks/s | ~2-5x |
| p50 latency | ~A ns | ~B ns | ~30% faster |
| p99 latency | ~C ns | ~D ns | ~50% faster |

---

## Profiling on macOS

### Using Instruments

1. **Time Profiler** - Find CPU hotspots:
   ```
   Open Instruments > Time Profiler
   Select your binary (e.g., ./bench_throughput)
   Run with: ./bench_throughput --benchmark_min_time=60
   Look for: Time spent in mutex operations
   ```

2. **System Trace** - Analyze scheduling:
   ```
   Open Instruments > System Trace
   Run workload
   Look for:
     - Context switches (should decrease with work-stealing)
     - Wake-up events
     - Block times
   ```

3. **Allocations** - Track memory:
   ```
   Open Instruments > Allocations
   Check for memory growth patterns
   ```

### What to Look For

**In Global Queue Mode:**
- High time in `pthread_mutex_lock` - lock contention
- Many context switches - threads blocking
- Single CPU core busy while others idle

**In Work-Stealing Mode:**
- Less time in locks (only during steal)
- Fewer context switches
- More even CPU utilization

### Custom Counters (Phase 3 TODO)

```cpp
struct Stats {
  size_t total_tasks_submitted;
  size_t total_tasks_completed;
  size_t steal_attempts;
  size_t successful_steals;
  size_t failed_cas;  // CAS contention
  size_t idle_spins;  // Worker idle time
};

auto stats = pool.GetStats();
std::cout << "Steal success rate: "
          << (double)stats.successful_steals / stats.steal_attempts << "\n";
```

---

## Design Decisions

### Why Not std::jthread?

**Issue:** AppleClang 15 doesn't have `<stop_token>` header.

**Solution:** Use `std::thread` with manual stop flag. The pattern is the same:

```cpp
// What we wanted (C++23 style):
std::jthread worker([](std::stop_token st) {
  while (!st.stop_requested()) { work(); }
});

// What we use (C++20 compatible):
std::thread worker([this]() {
  while (!stopped_.load(std::memory_order_acquire)) { work(); }
});
```

### Why Fixed-Capacity Deque?

**Issue:** Dynamic resizing requires coordination between owner and thieves.

**Solution:** Start with fixed 1024 capacity. Phase 4+ could add:
- Lazy growth (owner grows only)
- Backpressure when full
- Task rejection with error

### Why Round-Robin Submission?

**Issue:** All tasks to one deque causes initial imbalance.

**Solution:** Round-robin across deques:

```cpp
static std::atomic<size_t> round_robin{0};
size_t idx = round_robin.fetch_add(1, std::memory_order_relaxed) % num_threads_;
deques_[idx]->PushBottom(task);
```

This spreads initial work evenly.

### Why Not Lock-Free Queue?

**Issue:** Lock-free queues (like Michael-Scott) are complex and have high overhead for single-producer/single-consumer patterns.

**Solution:** Global queue uses mutex (simple, efficient). Per-thread deques use lock-free Chase-Lev algorithm.

---

## Known Limitations

1. **No task cancellation** - Once submitted, task runs to completion
2. **Fixed deque capacity** - 1024 tasks per worker
3. **No priority levels** - All tasks have equal priority
4. **No work affinity** - Tasks can migrate between workers
5. **std::function overhead** - Small allocations for non-capturing lambdas

---

## Future Improvements (Phase 4+)

- [ ] Dynamic deque resize
- [ ] Small-buffer optimization (InlineFunction<64>)
- [ ] Task priorities (high/med/low)
- [ ] NUMA-aware allocation
- [ ] Work-affinized scheduling
- [ ] Task dependencies DAG

---

## References

1. Chase, D., & Lev, Y. (2005). "Dynamic Circular Work-Stealing Deque"
2. C++ Concurrency in Action, Anthony Williams
3. Preshing on Programming - Lock-Free Programming
4. Intel/AMD Memory Ordering Documentation

---

## License

MIT License - See project root for details.
