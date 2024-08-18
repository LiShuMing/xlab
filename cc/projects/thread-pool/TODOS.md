# TO-FIX

## Known Issues

### Current Limitations
- [ ] Fixed deque capacity (1024 tasks per worker)
- [ ] No task cancellation mechanism
- [ ] No priority levels (all tasks equal)
- [ ] std::function overhead for small tasks
- [ ] No work affinity (tasks may migrate)

### Minor Issues
- [ ] Spurious wakeups possible in worker threads
- [ ] No dynamic thread count adjustment
- [ ] Limited error propagation from worker threads
- [ ] Stop() doesn't interrupt running tasks

## Planned Improvements

### Phase 3: Performance
- [ ] Dynamic deque resizing
  - Grow-only strategy
  - Memory-mapped circular buffers
  - Backpressure when full
- [ ] Small-buffer optimization for tasks
  - Inline storage for small functors
  - Avoid std::function allocation
- [ ] Performance counters
  - Tasks submitted/completed
  - Steal attempts/successes
  - CAS failure rate
  - Queue depth histograms
- [ ] NUMA-aware allocation
  - Thread-local storage per NUMA node
  - Memory pinning options

### Phase 4: Advanced Features
- [ ] Task priorities
  - High/medium/low queues
  - Priority inheritance
- [ ] Task dependencies
  - DAG-based execution
  - Continuation chains
- [ ] Work affinity
  - Pin tasks to specific workers
  - Cache-aware scheduling
- [ ] Dynamic thread pool
  - Auto-scale based on load
  - Idle thread timeout
- [ ] Exception aggregation
  - Collect exceptions from all workers
  - Configurable error handling

### Testing
- [ ] Fuzz testing for WSDeque
- [ ] Stress tests (1M+ tasks)
- [ ] Long-running stability tests
- [ ] Performance regression tests
- [ ] TSan/ASan CI integration

### Documentation
- [ ] API reference (Doxygen)
- [ ] More examples
  - Parallel algorithms (sort, reduce)
  - Pipeline patterns
  - Producer-consumer
- [ ] Troubleshooting guide
  - Debugging deadlocks
  - Performance tuning
  - Common pitfalls

---

# FIXED

- ✅ Initial thread pool implementation
- ✅ Global queue mode
- ✅ Work-stealing mode
- ✅ Chase-Lev deque algorithm
- ✅ Memory ordering implementation
- ✅ Unit tests
- ✅ Benchmarks
- ✅ Comprehensive documentation

---

# NOTES

## Design Decisions

### Why Chase-Lev Algorithm?
- Industry standard for work-stealing
- Lock-free steal operation
- Good cache locality
- Proven in production (Java ForkJoinPool, etc.)

### Why Fixed Capacity?
- Simplifies implementation
- Avoids ABA problem with resizing
- 1024 is sufficient for most use cases
- Can add dynamic resizing later

### Why std::function?
- Flexibility (any callable)
- Type erasure
- Trade-off: some allocation overhead
- Future: small-buffer optimization

## Performance Targets

### Current (Phase 2)
- Throughput: 1M+ tiny tasks/second per core
- Latency p50: < 1 microsecond
- Latency p99: < 10 microseconds

### Future (Phase 3)
- Throughput: 5M+ tasks/second per core
- Zero-allocation for small tasks
- Dynamic scaling

## Memory Ordering Reference

### acquire
- Loads only
- Ensures subsequent loads see prior stores

### release
- Stores only
- Ensures prior stores are visible before this store

### acq_rel
- Read-modify-write only
- Combines acquire and release

### seq_cst
- Default for most operations
- Strongest ordering
- Use only when necessary

## Common Patterns

### Fork-Join
```cpp
auto left = pool.Submit(compute, begin, mid);
auto right = compute(mid, end);  // Reuse thread
return left.get() + right.get();
```

### Parallel For
```cpp
std::vector<std::future<void>> futures;
for (int i = 0; i < n; ++i) {
  futures.push_back(pool.Submit([i]() { process(i); }));
}
for (auto& f : futures) f.get();
```

## References

- Chase, D., & Lev, Y. (2005). "Dynamic Circular Work-Stealing Deque"
- Lea, D. (2000). "A Java Fork/Join Framework"
- "C++ Concurrency in Action" - Anthony Williams
