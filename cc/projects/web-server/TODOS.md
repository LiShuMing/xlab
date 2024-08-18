# TO-FIX

## Known Issues

### Current Limitations
- [ ] Only fixed "200 OK" response (no real HTTP parsing yet)
- [ ] No static file serving
- [ ] No proper request routing
- [ ] Limited error handling (400/404 not implemented)
- [ ] No request body handling (POST/PUT)
- [ ] No chunked transfer encoding
- [ ] No compression (gzip)
- [ ] No TLS/HTTPS support

### Platform-Specific
- [ ] Linux io_uring backend not implemented yet
- [ ] No epoll backend for older Linux
- [ ] Windows IOCP not considered

## Planned Improvements

### Phase 1: Linux io_uring
- [ ] IoUringBackend implementation
- [ ] SQE/CQE submission loop
- [ ] Fixed file registration (optional)
- [ ] Registered buffers (optional)
- [ ] Linux build CI

### Phase 2: HTTP/1.1 Parser
- [ ] State machine parser
  - REQ_LINE → HEADERS → BODY → DONE
  - Incremental parsing (handle partial data)
  - Buffer management for pipelining
- [ ] Request structure
  - Method (GET, HEAD, POST, PUT, DELETE)
  - Path (with query string)
  - Headers (unordered_map)
  - Body (optional)
- [ ] Response structure
  - Status code
  - Headers
  - Body
- [ ] Error responses
  - 400 Bad Request
  - 404 Not Found
  - 405 Method Not Allowed
  - 500 Internal Server Error

### Phase 3: Static File Serving
- [ ] Path to filesystem mapping
- [ ] File existence check
- [ ] MIME type detection
- [ ] sendfile() zero-copy
  - Linux: sendfile()
  - macOS: sendfile() (different signature)
  - Fallback: read+write
- [ ] Partial content (Range header)
- [ ] Caching headers
  - ETag generation
  - Last-Modified
  - Cache-Control
  - If-None-Match (304 response)

### Phase 4: Advanced Features
- [ ] Connection pooling
- [ ] Keep-alive timeout management
- [ ] Request pipelining
- [ ] WebSocket support (optional)
- [ ] HTTP/2 (optional, very complex)

### Performance
- [ ] Request latency histograms
- [ ] Connection counters
- [ ] Request rate tracking
- [ ] Memory usage monitoring
- [ ] Profiling guide completion

### Testing
- [ ] Unit tests for HTTP parser
- [ ] Integration tests with curl
- [ ] Load tests with wrk
- [ ] Fuzz testing for parser

### Documentation
- [ ] API reference (Doxygen)
- [ ] Architecture diagrams
- [ ] Performance tuning guide
- [ ] Deployment guide

---

# FIXED

- ✅ Project skeleton
- ✅ CMake build system
- ✅ I/O backend abstraction
- ✅ KqueueBackend for macOS
- ✅ Server event loop
- ✅ Connection management
- ✅ Basic benchmarking setup

---

# NOTES

## Design Decisions

### Why Completion-First Abstraction?
- Unified code path for different I/O models
- Easier to reason about
- Matches io_uring's natural model
- kqueue adapts by doing syscall internally

### Why Not Use Existing Libraries?
- Learning exercise
- Full control over I/O path
- No dependencies for core
- Can optimize for specific use case

### Why C++20?
- Concepts for cleaner interfaces
- Coroutines (future use)
- Better constexpr
- std::span for buffer views

## Performance Targets

### Current (Phase 0)
- 10k+ concurrent connections
- 100k+ requests/second (fixed response)
- p99 latency < 10ms (localhost)

### Future (Phase 3)
- 50k+ concurrent connections
- 200k+ requests/second
- Zero-copy static file serving
- < 5ms p99 latency

## Platform Differences

### kqueue (macOS)
- Readiness notification
- Level-triggered or edge-triggered
- Requires syscall to perform I/O
- Good for moderate concurrency

### io_uring (Linux)
- Completion notification
- True async I/O
- Can batch many operations
- Best for high concurrency

## Resources

- [io_uring paper](https://kernel.dk/io_uring.pdf)
- [kqueue paper](http://people.freebsd.org/~jlemon/papers/kqueue.pdf)
- [HTTP/1.1 RFC 7230-7235](https://tools.ietf.org/html/rfc7230)
- [High Performance Browser Networking](https://hpbn.co/)

## Debugging Tips

### Enable Debug Logging
```cpp
#define RINGSERVER_DEBUG 1
LOG_DEBUG("Accept completed: fd={}", fd);
```

### Check File Descriptors
```bash
# macOS
lsof -p $(pgrep ringserver)

# Linux
ls -la /proc/$(pgrep ringserver)/fd/
```

### Network Debugging
```bash
# Capture traffic
sudo tcpdump -i lo0 -n port 8080

# Check connections
netstat -an | grep 8080
```

## Common Pitfalls

1. **Forgetting to handle EAGAIN**
   - Always check for EAGAIN/EWOULDBLOCK
   - Re-register interest if needed

2. **Buffer overflow**
   - Check buffer capacity before appending
   - Implement backpressure

3. **Resource leaks**
   - Always close file descriptors
   - Use RAII (UniqueFd)

4. **Missing error checks**
   - Check all syscall return values
   - Handle errors gracefully
