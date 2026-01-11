# Work-Stealing Thread Pool - Design Notes

## Phase 1: Global Queue Baseline

### Why Global Queue?
All workers compete for a single mutex-protected queue. This creates:
- **Lock contention**: More threads = more contention on the mutex
- **Cache line ping-pong**: All threads access the same queue structure
- **Context switches**: Threads block on the mutex when queue is empty

This serves as a baseline to measure the improvement from work-stealing.

### Interface (Phase 1)
```cpp
ThreadPool pool(num_threads, false);  // false = global queue mode
auto future = pool.Submit([]() { return 42; });
pool.Stop();
```

### Stop Semantics
- Graceful stop: waits for all submitted tasks to complete
- `Stop()` is idempotent (safe to call multiple times)
- `Submit` after `Stop()` returns a future that throws `std::runtime_error`

### Memory Ordering
- Mutex provides full memory barrier, so no explicit ordering needed
- `stopped_` flag uses `memory_order_acquire` for visibility

---

## Phase 2: Work-Stealing Design

### Core Insight
- Owner thread: push/pop at bottom (LIFO) - local, no contention
- Thief thread: steal from top (FIFO) - remote, occasional contention
- Each worker has its own deque, reducing global synchronization

### Chase-Lev Deque Implementation

**Data structures:**
```cpp
std::atomic<size_t> bottom_;  // Owner writes, thieves read
std::atomic<size_t> top_;     // Thieves CAS-update, owner reads
std::vector<Task> buffer_;    // Ring buffer (power of 2 capacity)
```

**Invariants:**
- `top >= 0`, `bottom >= top`
- `Size = bottom - top`
- Empty when `bottom == top`

**Operations:**

1. **push_bottom()** (owner only):
   ```cpp
   buffer[bottom & mask] = task;
   bottom_.store(bottom + 1, release);  // Release: task visible before index
   ```

2. **pop_bottom()** (owner only):
   ```cpp
   bottom--;                  // Acquire: see consistent state
   if (top < bottom) {
     return buffer[bottom & mask];  // Multi-element: just return
   }
   // Single element: race with thief
   bool stolen = !top_.compare_exchange_strong(top, top + 1, acq_rel, acquire);
   if (stolen) return nullptr;  // Thief won
   return task;
   ```

3. **steal_top()** (thief only):
   ```cpp
   if (top >= bottom) return nullptr;  // Empty
   task = buffer[top & mask];
   if (!top_.compare_exchange_strong(top, top + 1, acq_rel, acquire)) {
     return nullptr;  // CAS failed: another thief won
   }
   return task;
   ```

### Memory Ordering Justification

| Operation | Order | Rationale |
|-----------|-------|-----------|
| push bottom | release | Task data must be visible before `bottom` index update; prevents thief seeing index increment but stale data |
| pop bottom | acquire | Must see consistent `top`/`bottom` state; ensures we don't pop a task that was stolen |
| steal read | acquire | See consistent `top`/`bottom`; pair with CAS release |
| steal CAS | acq_rel | Success: synchronizes with previous acquires; Failure: acquire to see updated state |

### Single-Element Race
When size == 1, owner pop and thief steal race:
```
Owner: bottom--, reads task
Thief: reads task, CAS top++
```
Only one can succeed. The CAS determines the winner.

---

## Phase 3: Cache Padding & Observability

### False Sharing Prevention
```
Cache line: 64 bytes on most CPUs (including Apple Silicon)

struct Worker {
  WSTP_CACHELINE_ALIGN std::atomic<size_t> top_;  // offset 0
  char padding1[64 - sizeof(std::atomic<size_t>)];  // fill to 64

  std::atomic<size_t> bottom_;  // offset 64
  char padding2[64 - sizeof(std::atomic<size_t>)];  // fill to 64

  std::vector<Task> buffer_;  // starts at offset 128
};
```

### Performance Counters (for debugging/analysis)
```cpp
struct Stats {
  size_t total_tasks_submitted;   // All submitted tasks
  size_t total_tasks_completed;   // Successfully executed
  size_t steal_attempts;          // How many steals tried
  size_t successful_steals;       // Steals that got work
  size_t failed_cas;              // CAS failures (contention)
  size_t idle_spins;              // Times worker found nothing
};
```

---

## Build & Run

### Build
```bash
cd wstp
mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
cmake --build . --target all
```

### Tests
```bash
./test_thread_pool
./test_ws_deque
ctest
```

### Benchmarks
```bash
./bench_throughput --benchmark_min_time=5s
./bench_latency --benchmark_min_time=5s
```

---

## macOS Instruments Profiling

### Time Profiler
1. Open Instruments
2. Select Time Profiler template
3. Run the benchmark binary
4. Look for:
   - Time spent in mutex operations (global queue mode)
   - Thread state (running vs waiting)
   - CPU utilization across cores

### System Trace
1. Select System Trace template
2. Run workload
3. Look for:
   - Context switches (should be lower in work-stealing mode)
   - Wake-up events
   - Block times

### What to Measure
| Metric | Phase 1 (Global) | Phase 2 (Stealing) | Expected |
|--------|------------------|-------------------|----------|
| Lock contention | High | Low | 10x+ reduction |
| Context switches | High | Low | 50%+ reduction |
| Throughput | Baseline | Higher | Depends on workload |
| Latency p99 | Higher | Lower | Especially under load |

---

## Known Limitations & TODOs

### Phase 1/2
- Fixed deque capacity (1024 tasks)
- No task priority
- No work cancellation (except Stop)
- `std::function` has heap allocation overhead

### Future Improvements (Phase 4+)
- Dynamic deque resize
- Small-buffer optimization for small tasks
- Task priorities
- Work-affinized scheduling
- NUMA-aware allocation
