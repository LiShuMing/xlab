# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### In Progress
- Dynamic deque resizing
- Performance counters and statistics
- NUMA-aware allocation

## [0.2.0] - 2024-XX-XX

### Added
- **Work-Stealing Mode**
  - Chase-Lev work-stealing deque implementation
  - Per-thread task queues
  - Lock-free steal operation
  - Configurable via `use_work_stealing` parameter

- **Memory Ordering Documentation**
  - Detailed explanation of acquire/release semantics
  - Single-element race handling
  - Memory fence usage

- **Performance Benchmarks**
  - Throughput benchmarks (tiny tasks, fork-join)
  - Latency benchmarks (p50, p99)
  - Comparison: work-stealing vs global queue

- **Profiling Guide**
  - Instruments (Time Profiler, System Trace)
  - Expected performance metrics
  - Bottleneck identification

### Changed
- Improved CAS failure handling in steal_top
- Optimized cache line padding for atomic variables
- Better task distribution with round-robin submission

### Fixed
- Race condition in single-element deque
- Spurious wakeups in worker threads
- Memory ordering in PopBottom

## [0.1.0] - 2024-XX-XX

### Added
- **Core ThreadPool Implementation**
  - Global queue mode (baseline)
  - Work-stealing mode
  - std::future-based result retrieval
  - Graceful shutdown with Stop()

- **WSDeque Implementation**
  - Fixed-capacity circular buffer
  - PushBottom (owner, LIFO)
  - PopBottom (owner, LIFO)
  - StealTop (thief, FIFO, lock-free)
  - Atomic index management

- **API Features**
  - Submit() with automatic std::future
  - Submit() with arguments
  - Stop() - graceful shutdown
  - NumThreads() - query worker count
  - QueueSize() - approximate queue size
  - IsStopped() - state check

- **Build System**
  - CMake 3.16+ configuration
  - C++20 standard
  - GoogleTest integration
  - Benchmark support

- **Unit Tests**
  - ThreadPool tests (functional, stress)
  - WSDeque tests (edge cases, races)
  - GoogleTest framework

- **Documentation**
  - Comprehensive README
  - DESIGN.md with architecture notes
  - Memory ordering deep dive
  - Profiling guide

### Project Structure
```
thread-pool/
├── include/wstp/
│   ├── cache_padding.h       # Cache line alignment
│   ├── status.h              # Status codes
│   ├── task.h                # Task type
│   ├── thread_pool.h         # Main API
│   └── ws_deque.h            # Work-stealing deque
├── src/
│   ├── thread_pool.cc        # Implementation
│   └── ws_deque.cc           # Deque implementation
├── tests/
│   ├── test_thread_pool.cc   # Pool tests
│   └── test_ws_deque.cc      # Deque tests
├── bench/
│   ├── bench_throughput.cc   # Throughput
│   └── bench_latency.cc      # Latency
├── CMakeLists.txt
├── DESIGN.md
└── README.md
```

### Technical Details

**Work-Stealing Algorithm:**
```cpp
// Owner thread (local)
PushBottom:  LIFO, relaxed read + release write
PopBottom:   LIFO, relaxed read + acquire fence

// Thief thread (remote)
StealTop:    FIFO, acquire read + acq_rel CAS
```

**Memory Ordering Strategy:**
- `relaxed`: Counter increments, owner reads
- `release`: Publishing data (push, update)
- `acquire`: Consuming data (steal, pop)
- `acq_rel`: CAS operations (synchronize both directions)

**Cache Line Optimization:**
```cpp
// 64-byte cache line alignment
alignas(64) std::atomic<size_t> bottom_{0};
alignas(64) std::atomic<size_t> top_{0};
```

### Dependencies
- CMake 3.16+
- C++20 compiler
- GoogleTest

### Platform
- Primary: macOS (Apple Silicon/Intel)
- Uses C++20 atomics
- Tested with Apple Clang 15+

## [0.0.1] - 2024-XX-XX

### Added
- Project initialization
- Basic thread pool with global queue
- Initial CMake setup

## Phase Roadmap

### Phase 1: Global Queue ✅
- Mutex-protected global queue
- Basic thread pool
- Tests

### Phase 2: Work-Stealing ✅
- WSDeque implementation
- Per-thread queues
- Lock-free steal

### Phase 3: Performance 🚧
- Dynamic resizing
- Performance counters
- Profiling tools

### Phase 4: Advanced 📋
- NUMA awareness
- Work affinities
- Task priorities
