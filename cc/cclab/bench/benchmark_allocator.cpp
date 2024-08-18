#include "benchmark/benchmark.h"

#include "default_init_default.h"

template <class T, typename A = std::allocator<T>>
static void BM_Stl_Resize(benchmark::State& state) {
    for (auto _: state) {
        std::vector<T> vec;
        vec.resize(state.range(0));
    }
}

template <class T, typename A = std::allocator<T>>
static void BM_Raw_Resize(benchmark::State& state) {
    for (auto _: state) {
        raw::raw_vector<T> vec;
        vec.resize(state.range(0));
        std::vector<T> rv1(std::move(reinterpret_cast<std::vector<T> &>(vec)));
    }
}

BENCHMARK_TEMPLATE(BM_Stl_Resize, uint8_t, uint8_t)->RangeMultiplier(8)->Range(1, 8 << 10);
BENCHMARK_TEMPLATE(BM_Raw_Resize, uint8_t, uint8_t)->RangeMultiplier(8)->Range(1, 8 << 10);

BENCHMARK_MAIN();
