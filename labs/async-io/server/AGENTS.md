# RingServer agent guide

Read [repository RULES](../../../RULES.md) before work and again before any Git write.
Only the authorized Gmail Author/Committer identity is permitted. Never commit private corporate
material, credentials, build trees, dependency downloads or raw runtime data. Do not push implicitly.

## Current implementation

Read [README](README.md), CMakeLists.txt and the current diff. The former Phase 0–3 notes are historical,
not proof of implementation or a reason to recreate placeholders.

- C++20; Linux epoll, optional io_uring and opt-in libkqueue `kqueue-compat`.
- Native macOS kqueue remains a separate, unverified path; Linux compatibility is not native proof.
- One event loop, bounded GET-only HTTP subset, fixed 1024-byte body.
- No static files/sendfile, TLS, multithreading, SQPOLL or multishot.
- No FetchContent: explicit dependency prefixes, no configure-time network access.
- Native test and client targets need no GoogleTest/Benchmark dependencies.
- libkqueue uses Linux epoll internally and a resource-monitor thread; one event loop is not one process thread.

## Invariants

- Backend returns a completed accept with the new fd, never a readiness event disguised as a read.
- Handle partial read/write and EAGAIN without losing bytes or treating retry as EOF.
- Connection ID must match even when fd matches.
- Cancelled io_uring targets retain owned buffers until the target CQE and cancellation ack are drained.
- Never detach a task or free buffers still referenced by the kernel.
- Bounded connection/request/operation state; close slow clients; no implicit backend fallback.
- Count success only after the full valid response is written. Cross-check against client payload checks.
- Measure basic/detailed overhead separately. User-space submit counts are not syscall counts.
- Bind benchmark server to loopback. Own and reap every launched test/benchmark child.

## Validation

From the topic directory:

```sh
make build
make test
python3 scripts/benchmark.py --build build --out results/new-run --repeats 5
```

Use standard CXX/CXXFLAGS/LDFLAGS for toolchain choice. An epoll-only standalone build must work without
liburing. Platform-specific sources must be conditionally selected. Linux success is not macOS proof.
For Linux compatibility: `make deps-kqueue`, `KQUEUE_COMPAT=ON make build`, then
`make test BACKENDS='epoll uring kqueue-compat'`. Never rename this path to native `kqueue`.
Keep source/header names and error handling consistent with the Google C++ style and root formatter.
Do not silence a failing test or regenerate expectations to hide a defect.

Runtime evidence stays in ignored results/. A reviewed Markdown summary may be retained in the topic.
No source commit or push is authorized merely by running the experiment.

## Engineering conventions

Formerly kept in a separate `RULES.md`; only the parts that still match the current code are kept.
The old Phase 0-3 design notes are superseded by the implementation notes above.

- **Backend contract**: completion-first, non-blocking, 64-bit `user_data` token, negative `result`
  carries `-errno`. Exactly one pending read/write per connection. Keep the interface in
  `include/ringserver/io/io_backend.hpp` authoritative instead of copying its signatures here.
- **Errors**: use `ringserver::Status` (`include/ringserver/common/status.hpp`); `kAgain`/
  `kWouldBlock` means retry, `kConnectionReset`/`kEndOfFile` means close, never treat retry as EOF.
- **Resources**: file descriptors are RAII (move-only) wrappers; no manual `close`, no detached
  work, no buffer freed while the kernel still references it.
- **Buffers and backpressure**: read buffers have explicit initial and maximum sizes; when pending
  output exceeds the documented threshold, stop reading until it drains.
- **Platform abstraction**: platform-specific sources are selected conditionally, never by an
  implicit fallback; Linux results are not macOS results.
- **Performance**: prefer zero-copy, buffer reuse and fewer syscalls; measure before claiming.
- **Docs**: classes and public methods carry Doxygen-style comments stating ownership, threading
  and error behaviour.
- **Commit messages**: `<type>(<scope>): <description>` with `feat`/`fix`/`docs`/`refactor`/
  `perf`/`test`.
