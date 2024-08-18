#include "benchmark/benchmark.h"

static void BM_StringCreation(benchmark::State& state) {
    size_t cnt = 0;
    for (auto _ : state) {
        std::string empty_string;
        cnt += empty_string.size();
    }
    // Prevent unused variable warning
    if (cnt == 0) {
        state.SetBytesProcessed(cnt);
    } else {
        state.SetBytesProcessed(cnt);
    }
}
// Register the function as a benchmark
BENCHMARK(BM_StringCreation);

static void BM_StringCopy(benchmark::State& state) {
    std::string x = "hello";
    size_t cnt = 0;
    for (auto _ : state) {
        std::string copy(x);
        cnt += 1;
    }
    state.SetBytesProcessed(cnt);
}
BENCHMARK(BM_StringCopy);

BENCHMARK_MAIN();
