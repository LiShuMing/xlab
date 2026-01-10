#include <benchmark/benchmark.h>
#include <vector>
#include <random>

// Using 256MB to ensure we exceed most L3 Caches (First Principle: Bypass Cache)
const size_t kNumElements = 32 * 1024 * 1024; 

static void BM_MemoryBandwidth_Triad(benchmark::State& state) {
  // 1. Setup Phase: Allocate memory outside the timed loop
  std::vector<double> a(kNumElements, 1.1);
  std::vector<double> b(kNumElements, 2.2);
  std::vector<double> c(kNumElements, 0.0);
  double scalar = 3.3;

  // 2. The Benchmark Loop
  for (auto _ : state) {
    // We use a simple loop to saturate the memory controller
    for (size_t i = 0; i < kNumElements; ++i) {
      c[i] = a[i] + scalar * b[i];
    }
    // Prevent the compiler from optimizing away the entire loop
    benchmark::DoNotOptimize(c.data());
    benchmark::ClobberMemory();
  }

  // 3. Counter Phase: Calculate processed bytes per iteration
  // Triad: 2 Reads (a, b) + 1 Write (c) per element
  int64_t bytes_per_iter = static_cast<int64_t>(kNumElements * sizeof(double) * 3);
  state.SetBytesProcessed(state.iterations() * bytes_per_iter);
}

// Register with multi-threading to saturate all memory channels
BENCHMARK(BM_MemoryBandwidth_Triad)
    ->Unit(benchmark::kMillisecond)
    ->Threads(8) // Adjust based on your CPU cores
    ->UseRealTime();

BENCHMARK_MAIN();