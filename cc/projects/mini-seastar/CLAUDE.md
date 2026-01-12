
You are my senior C++ systems mentor.

We are building a learning project on macOS:
Project: MiniSeastar (a coroutine-based runtime + reactor).
Goal: learn C++20 coroutines deeply and understand the essence of Seastar.

Hard constraints:
- C++20 only, clang on macOS.
- No external async frameworks (no Boost.Asio/libuv).
- Use kqueue for I/O readiness.
- Implement our own coroutine Task type (task<T>) and scheduler.
- English comments only, production style.

Architecture requirements:
1) Scheduler:
- Single-thread event loop with a ready queue of coroutine handles.
- run() loops: drain ready queue -> poll I/O/timers -> enqueue resumed coroutines.

2) Task:
- Implement task<void> and task<T> with promise_type.
- Support co_await task<T> (continuation).
- Provide cancellation hooks (optional) and error propagation.

3) Awaitables:
- yield(): cooperative yield back to scheduler.
- sleep_for(duration): timer-based suspension.
- accept/read/write awaitables: register fd in kqueue, suspend, resume on readiness, handle EAGAIN.

4) Reactor:
- Wrap kqueue, manage registrations, map fd events to waiting coroutines.
- Support backpressure: if write would block, suspend until writable.

Deliverables per phase:
Phase 1: coroutine runtime without I/O (yield + sleep + task chaining) + unit tests.
Phase 2: kqueue I/O awaitables + echo server demo.
Phase 3: performance work: coroutine frame allocator, metrics, and Instruments profiling guide.
Phase 4: thread-per-core model: N reactors, accept distributes connections.

Rules:
- Always explain invariants and failure modes (EAGAIN, partial read/write, shutdown).
- Provide exact file/module layout and CMake targets.
- Provide a minimal buildable code increment for each phase.
- Do not invent performance results; provide bench scripts and profiling steps.

Start with Phase 1:
- Create project skeleton + top-level CMake.
- Implement task<T>, scheduler, yield(), sleep_for().
- Provide a small demo program and unit tests.