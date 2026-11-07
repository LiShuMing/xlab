#include <atomic>
#include <chrono>
#include <iostream>
#include <limits>
#include <thread>
#include <vector>

#include "benchmark/benchmark.h"
#include "wstp/thread_pool.h"

namespace wstp {

// Benchmark for measuring submit-to-start latency more precisely
// This separates the time to get a worker from the actual task execution

static void BM_OnlySubmitLatency_GlobalQueue(benchmark::State& state) {
  const int num_threads = static_cast<int>(state.range(0));
  const int batch_size = static_cast<int>(state.range(1));

  for (auto _ : state) {
    ThreadPool pool(num_threads, false);

    // Pre-warm: submit one task to ensure workers are active
    pool.Submit([]() { std::this_thread::sleep_for(std::chrono::microseconds(1)); }).get();

    std::vector<std::chrono::nanoseconds> latencies;
    latencies.reserve(batch_size);

    for (int i = 0; i < batch_size; ++i) {
      auto start = std::chrono::high_resolution_clock::now();
      auto future = pool.Submit([]() { /* no-op */ });
      future.get();
      auto end = std::chrono::high_resolution_clock::now();
      latencies.push_back(end - start);
    }

    pool.Stop();

    // Report statistics
    double sum = 0;
    double min_ns = std::numeric_limits<double>::max();
    double max_ns = 0;
    for (auto& lat : latencies) {
      double ns = static_cast<double>(lat.count());
      sum += ns;
      min_ns = std::min(min_ns, ns);
      max_ns = std::max(max_ns, ns);
    }

    state.counters["avg_ns"] = sum / batch_size;
    state.counters["min_ns"] = min_ns;
    state.counters["max_ns"] = max_ns;
  }
}

static void BM_OnlySubmitLatency_WorkStealing(benchmark::State& state) {
  const int num_threads = static_cast<int>(state.range(0));
  const int batch_size = static_cast<int>(state.range(1));

  for (auto _ : state) {
    ThreadPool pool(num_threads, true);

    // Pre-warm
    pool.Submit([]() { std::this_thread::sleep_for(std::chrono::microseconds(1)); }).get();

    std::vector<std::chrono::nanoseconds> latencies;
    latencies.reserve(batch_size);

    for (int i = 0; i < batch_size; ++i) {
      auto start = std::chrono::high_resolution_clock::now();
      auto future = pool.Submit([]() { /* no-op */ });
      future.get();
      auto end = std::chrono::high_resolution_clock::now();
      latencies.push_back(end - start);
    }

    pool.Stop();

    double sum = 0;
    double min_ns = std::numeric_limits<double>::max();
    double max_ns = 0;
    for (auto& lat : latencies) {
      double ns = static_cast<double>(lat.count());
      sum += ns;
      min_ns = std::min(min_ns, ns);
      max_ns = std::max(max_ns, ns);
    }

    state.counters["avg_ns"] = sum / batch_size;
    state.counters["min_ns"] = min_ns;
    state.counters["max_ns"] = max_ns;
  }
}

// Measure throughput when tasks have varying work
static void BM_VaryingWork_GlobalQueue(benchmark::State& state) {
  const int num_threads = static_cast<int>(state.range(0));
  const int num_tasks = static_cast<int>(state.range(1));

  for (auto _ : state) {
    ThreadPool pool(num_threads, false);
    std::atomic<int> completed{0};

    for (int i = 0; i < num_tasks; ++i) {
      pool.Submit([&completed, i]() {
        // Varying work: i % 10 determines work amount
        volatile int work = i % 10;
        for (volatile int j = 0; j < work * 100; ++j) {
          benchmark::DoNotOptimize(j);
        }
        completed.fetch_add(1, std::memory_order_relaxed);
      });
    }

    pool.Stop();
  }
}

static void BM_VaryingWork_WorkStealing(benchmark::State& state) {
  const int num_threads = static_cast<int>(state.range(0));
  const int num_tasks = static_cast<int>(state.range(1));

  for (auto _ : state) {
    ThreadPool pool(num_threads, true);
    std::atomic<int> completed{0};

    for (int i = 0; i < num_tasks; ++i) {
      pool.Submit([&completed, i]() {
        volatile int work = i % 10;
        for (volatile int j = 0; j < work * 100; ++j) {
          benchmark::DoNotOptimize(j);
        }
        completed.fetch_add(1, std::memory_order_relaxed);
      });
    }

    pool.Stop();
  }
}

// Work distribution test - are tasks evenly distributed?
static void BM_WorkDistribution_GlobalQueue(benchmark::State& state) {
  const int num_threads = static_cast<int>(state.range(0));
  const int num_tasks = static_cast<int>(state.range(1));

  for (auto _ : state) {
    // Use std::vector<int> instead of std::atomic<int>
    std::vector<int> thread_counters(num_threads, 0);

    ThreadPool pool(num_threads, false);

    for (int i = 0; i < num_tasks; ++i) {
      pool.Submit([&thread_counters, i, num_threads]() {
        thread_counters[i % num_threads]++;
      });
    }

    pool.Stop();

    // Calculate variance
    int64_t sum = 0;
    for (auto& c : thread_counters) {
      sum += c;
    }
    double avg = static_cast<double>(sum) / num_threads;

    int64_t variance_sum = 0;
    for (auto& c : thread_counters) {
      double diff = c - avg;
      variance_sum += static_cast<int64_t>(diff * diff);
    }

    state.counters["variance"] = static_cast<double>(variance_sum) / num_threads;
  }
}

BENCHMARK(BM_OnlySubmitLatency_GlobalQueue)
    ->Args({4, 5000})
    ->Args({8, 5000})
    ->Unit(benchmark::kMicrosecond);

BENCHMARK(BM_OnlySubmitLatency_WorkStealing)
    ->Args({4, 5000})
    ->Args({8, 5000})
    ->Unit(benchmark::kMicrosecond);

BENCHMARK(BM_VaryingWork_GlobalQueue)
    ->Args({4, 10000})
    ->Args({8, 10000})
    ->Unit(benchmark::kMicrosecond);

BENCHMARK(BM_VaryingWork_WorkStealing)
    ->Args({4, 10000})
    ->Args({8, 10000})
    ->Unit(benchmark::kMicrosecond);

BENCHMARK(BM_WorkDistribution_GlobalQueue)
    ->Args({4, 10000})
    ->Args({8, 10000})
    ->Unit(benchmark::kMicrosecond);

BENCHMARK_MAIN();

}  // namespace wstp
