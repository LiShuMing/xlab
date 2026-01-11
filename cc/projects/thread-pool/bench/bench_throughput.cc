#include <atomic>
#include <chrono>
#include <thread>
#include <vector>

#include "benchmark/benchmark.h"
#include "wstp/thread_pool.h"

namespace wstp {

// Measure throughput of tiny tasks (minimal work per task)
// This stress-tests the queue contention
static void BM_Throughput_TinyTask_GlobalQueue(benchmark::State& state) {
  const int num_threads = static_cast<int>(state.range(0));
  const int tasks_per_thread = static_cast<int>(state.range(1));
  std::atomic<int> counter{0};

  for (auto _ : state) {
    ThreadPool pool(num_threads, false);

    std::vector<std::future<void>> futures;
    futures.reserve(num_threads * tasks_per_thread);

    for (int t = 0; t < num_threads; ++t) {
      for (int i = 0; i < tasks_per_thread; ++i) {
        futures.push_back(pool.Submit([&counter]() {
          counter.fetch_add(1, std::memory_order_relaxed);
        }));
      }
    }

    pool.Stop();
    benchmark::ClobberMemory();
  }

  state.counters["tasks_total"] = benchmark::Counter(
      static_cast<int64_t>(num_threads) * tasks_per_thread,
      benchmark::Counter::kIsRate);
}

static void BM_Throughput_TinyTask_WorkStealing(benchmark::State& state) {
  const int num_threads = static_cast<int>(state.range(0));
  const int tasks_per_thread = static_cast<int>(state.range(1));
  std::atomic<int> counter{0};

  for (auto _ : state) {
    ThreadPool pool(num_threads, true);

    std::vector<std::future<void>> futures;
    futures.reserve(num_threads * tasks_per_thread);

    for (int t = 0; t < num_threads; ++t) {
      for (int i = 0; i < tasks_per_thread; ++i) {
        futures.push_back(pool.Submit([&counter]() {
          counter.fetch_add(1, std::memory_order_relaxed);
        }));
      }
    }

    pool.Stop();
    benchmark::ClobberMemory();
  }

  state.counters["tasks_total"] = benchmark::Counter(
      static_cast<int64_t>(num_threads) * tasks_per_thread,
      benchmark::Counter::kIsRate);
}

// Measure latency from submit to start of execution
static void BM_Latency_SubmitToStart_GlobalQueue(benchmark::State& state) {
  const int num_threads = static_cast<int>(state.range(0));
  const int tasks_per_batch = static_cast<int>(state.range(1));

  for (auto _ : state) {
    ThreadPool pool(num_threads, false);

    std::vector<std::chrono::nanoseconds> latencies;
    latencies.reserve(tasks_per_batch);

    for (int i = 0; i < tasks_per_batch; ++i) {
      auto start = std::chrono::high_resolution_clock::now();
      auto future = pool.Submit([]() { /* no-op */ });
      future.get();
      auto end = std::chrono::high_resolution_clock::now();
      latencies.push_back(end - start);
    }

    pool.Stop();

    // Calculate statistics
    std::sort(latencies.begin(), latencies.end());
    auto p50 = latencies[latencies.size() / 2];
    auto p99 = latencies[static_cast<size_t>(latencies.size() * 0.99)];

    state.counters["p50_latency_ns"] = benchmark::Counter(
        static_cast<double>(p50.count()), benchmark::Counter::kDefaults);
    state.counters["p99_latency_ns"] = benchmark::Counter(
        static_cast<double>(p99.count()), benchmark::Counter::kDefaults);
  }
}

static void BM_Latency_SubmitToStart_WorkStealing(benchmark::State& state) {
  const int num_threads = static_cast<int>(state.range(0));
  const int tasks_per_batch = static_cast<int>(state.range(1));

  for (auto _ : state) {
    ThreadPool pool(num_threads, true);

    std::vector<std::chrono::nanoseconds> latencies;
    latencies.reserve(tasks_per_batch);

    for (int i = 0; i < tasks_per_batch; ++i) {
      auto start = std::chrono::high_resolution_clock::now();
      auto future = pool.Submit([]() { /* no-op */ });
      future.get();
      auto end = std::chrono::high_resolution_clock::now();
      latencies.push_back(end - start);
    }

    pool.Stop();

    std::sort(latencies.begin(), latencies.end());
    auto p50 = latencies[latencies.size() / 2];
    auto p99 = latencies[static_cast<size_t>(latencies.size() * 0.99)];

    state.counters["p50_latency_ns"] = benchmark::Counter(
        static_cast<double>(p50.count()), benchmark::Counter::kDefaults);
    state.counters["p99_latency_ns"] = benchmark::Counter(
        static_cast<double>(p99.count()), benchmark::Counter::kDefaults);
  }
}

// Fork-join pattern: parent submits child tasks recursively
static void BM_ForkJoin_LinearChain_GlobalQueue(benchmark::State& state) {
  const int num_threads = static_cast<int>(state.range(0));
  const int chain_length = static_cast<int>(state.range(1));
  std::atomic<int> counter{0};

  for (auto _ : state) {
    ThreadPool pool(num_threads, false);

    // Linear chain: submit A, which submits B, which submits C...
    std::function<void(int)> chain_task = [&pool, &counter, &chain_task](int depth) {
      if (depth == 0) {
        counter.fetch_add(1, std::memory_order_relaxed);
        return;
      }
      pool.Submit([&pool, &counter, &chain_task, depth]() { chain_task(depth - 1); })
          .get();
    };

    pool.Submit([&pool, &counter, &chain_task, chain_length]() {
      chain_task(chain_length);
    }).get();

    pool.Stop();
  }
}

static void BM_ForkJoin_LinearChain_WorkStealing(benchmark::State& state) {
  const int num_threads = static_cast<int>(state.range(0));
  const int chain_length = static_cast<int>(state.range(1));
  std::atomic<int> counter{0};

  for (auto _ : state) {
    ThreadPool pool(num_threads, true);

    std::function<void(int)> chain_task = [&pool, &counter, &chain_task](int depth) {
      if (depth == 0) {
        counter.fetch_add(1, std::memory_order_relaxed);
        return;
      }
      pool.Submit([&pool, &counter, &chain_task, depth]() { chain_task(depth - 1); })
          .get();
    };

    pool.Submit([&pool, &counter, &chain_task, chain_length]() {
      chain_task(chain_length);
    }).get();

    pool.Stop();
  }
}

// Register benchmarks
BENCHMARK(BM_Throughput_TinyTask_GlobalQueue)
    ->Args({4, 10000})
    ->Args({8, 10000})
    ->Unit(benchmark::kMicrosecond);

BENCHMARK(BM_Throughput_TinyTask_WorkStealing)
    ->Args({4, 10000})
    ->Args({8, 10000})
    ->Unit(benchmark::kMicrosecond);

BENCHMARK(BM_Latency_SubmitToStart_GlobalQueue)
    ->Args({4, 1000})
    ->Args({8, 1000})
    ->Unit(benchmark::kMicrosecond);

BENCHMARK(BM_Latency_SubmitToStart_WorkStealing)
    ->Args({4, 1000})
    ->Args({8, 1000})
    ->Unit(benchmark::kMicrosecond);

BENCHMARK(BM_ForkJoin_LinearChain_GlobalQueue)
    ->Args({4, 10})
    ->Args({8, 10})
    ->Unit(benchmark::kMicrosecond);

BENCHMARK(BM_ForkJoin_LinearChain_WorkStealing)
    ->Args({4, 10})
    ->Args({8, 10})
    ->Unit(benchmark::kMicrosecond);

BENCHMARK_MAIN();

}  // namespace wstp
