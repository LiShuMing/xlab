# TO-FIX

## Current Limitations

### Phase 1 Limitations (Known)
- [ ] No custom coroutine frame allocator (using default new/delete)
- [ ] Single-threaded only
- [ ] No I/O support yet (Phase 2)
- [ ] Limited error handling in examples
- [ ] Missing some edge case tests

### Phase 2 Work Items (In Progress)
- [ ] kqueue integration for macOS
- [ ] awaitable_read implementation
- [ ] awaitable_write implementation
- [ ] awaitable_accept implementation
- [ ] Echo server demo
- [ ] Handle EAGAIN properly
- [ ] Partial read/write handling
- [ ] Connection lifecycle management

## Future Improvements

### Phase 3 (Performance)
- [ ] Custom coroutine frame allocator
  - Per-thread arena allocation
  - Free list for common sizes
  - Memory pool for tasks
- [ ] Metrics collection
  - Tasks created/completed
  - Context switches
  - Syscalls per second
  - Ready queue depth
- [ ] Instruments profiling guide
  - Time Profiler templates
  - System Trace analysis
  - Memory allocation tracking

### Phase 4 (Multi-threading)
- [ ] Multi-reactor support
  - One reactor per thread
  - Thread-local schedulers
- [ ] Accept distribution
  - Round-robin connection assignment
  - SO_REUSEPORT support
- [ ] Cross-thread messaging
  - MPSC queue for thread communication
  - Work stealing (optional)

### Additional Features
- [ ] Timeout support for I/O operations
- [ ] Cancellation tokens
- [ ] Signal handling
- [ ] File I/O (pread/pwrite)
- [ ] Zero-copy networking (sendfile)
- [ ] TLS/SSL support
- [ ] HTTP parser integration
- [ ] WebSocket support

### Testing
- [ ] Fuzz testing for protocol parsers
- [ ] Stress tests (10k+ connections)
- [ ] Memory leak detection tests
- [ ] Performance regression tests

### Documentation
- [ ] API reference (Doxygen)
- [ ] Tutorial series
- [ ] Architecture decision records
- [ ] Performance tuning guide

---

# FIXED

- ✅ Task<T> coroutine type implemented
- ✅ Task<void> specialization
- ✅ Exception propagation working
- ✅ Scheduler with ready queue
- ✅ yield() awaitable
- ✅ sleep_for() awaitable
- ✅ Unit test framework
- ✅ CMake build system
- ✅ Demo programs

---

# NOTES

## Design Decisions

### Why C++20 Coroutines?
- Zero-cost abstraction potential
- Composable async code
- Type-safe
- Standardized

### Why kqueue on macOS?
- Native macOS API
- Efficient for high connection counts
- Good integration with the platform
- Foundation for portability

### Why Single-threaded First?
- Simplifies initial implementation
- Easier to debug
- Establishes core patterns
- Multi-threading added later

## Learning Resources

### C++ Coroutines
- [cppreference coroutines](https://en.cppreference.com/w/cpp/language/coroutines)
- [Lewis Baker's blog](https://lewissbaker.github.io/)
- [C++20 Coroutines: A Practical Guide](https://example.com)

### Seastar
- [Seastar docs](https://docs.seastar.io/)
- [Seastar GitHub](https://github.com/scylladb/seastar)
- "Fast IO" talk by Avi Kivity

### kqueue
- [kqueue man page](https://man.freebsd.org/cgi/man.cgi?kqueue)
- [BSD kqueue tutorial](https://wiki.netbsd.org/tutorials/kqueue_tutorial/)

## Performance Targets

### Phase 1 Benchmarks
- 1M tasks created/resumed: < 1 second
- Memory per task: ~100-200 bytes

### Phase 2 Targets
- Echo server: 10k concurrent connections
- Latency p99: < 1ms (localhost)

### Phase 3 Targets
- Coroutine allocation: < 50ns
- Context switch: < 100ns

### Phase 4 Targets
- Linear scaling up to core count
- 1M+ connections across all cores

## Common Pitfalls

1. **Coroutine frame lifetime**
   - Must outlive all references
   - Destroyed when Task is destroyed
   - Don't access after move

2. **Exception safety**
   - Always handle unhandled_exception
   - Rethrow in await_resume if needed
   - Use RAII for cleanup

3. **Memory ordering**
   - Use acquire/release for ready flag
   - Don't use relaxed ordering without reason
   - Document ordering choices

4. **I/O edge cases**
   - EAGAIN/EWOULDBLOCK handling
   - Partial reads/writes
   - Connection reset
   - Signal interruption
