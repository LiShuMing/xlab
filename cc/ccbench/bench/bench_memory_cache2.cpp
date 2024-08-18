#include <benchmark/benchmark.h>

#include <iostream>
#include <random>
#include <vector>
#include <algorithm>
#include <cstring>

// You can get these cache info by `getconf -a | grep -i cache`
constexpr size_t CACHE_LINESIZE = 64;

// 32 KB L1
constexpr size_t LEVEL1_DCACHE_SIZE = 32768;
// 4 MB L2
constexpr size_t LEVEL2_CACHE_SIZE = 4 * 1024 * 1024;
// 36 MB L3
constexpr size_t LEVEL3_CACHE_SIZE = 36 * 1024 * 1024;

// Size of Item equals to CACHE_LINESIZE
struct Item {
    int value;
private:
    int pad[CACHE_LINESIZE / 4 - 1];
};

static_assert(sizeof(Item) == CACHE_LINESIZE, "Item size is not equals to CACHE_LINESIZE");

// Global random engine
static std::mt19937_64 g_rng(42);

// Dynamic arrays for each cache level
static std::vector<Item> obj_L1;
static std::vector<Item> obj_L2;
static std::vector<Item> obj_L3;
static std::vector<Item> obj_MEMORY;

// Random indices for random access
static std::vector<size_t> random_indices_L1;
static std::vector<size_t> random_indices_L2;
static std::vector<size_t> random_indices_L3;
static std::vector<size_t> random_indices_MEMORY;

// Initialize arrays with random data
static void init_array(std::vector<Item>& array) {
    std::uniform_int_distribution<int> u(0, 1);
    for (auto& item : array) {
        item.value = u(g_rng);
    }
}

// Initialize random indices
static void init_random_indices(std::vector<size_t>& indices, size_t array_size, size_t num_indices) {
    indices.resize(num_indices);
    if (array_size > 0) {
        std::uniform_int_distribution<size_t> dist(0, array_size - 1);
        for (auto& idx : indices) {
            idx = dist(g_rng);
        }
    }
}

// One-time setup before all benchmarks
void setup_benchmarks() {
    // Calculate array sizes based on 100% cache factor
    size_t size_l1 = LEVEL1_DCACHE_SIZE / CACHE_LINESIZE;
    size_t size_l2 = LEVEL2_CACHE_SIZE / CACHE_LINESIZE;
    size_t size_l3 = LEVEL3_CACHE_SIZE / CACHE_LINESIZE;
    size_t size_memory = LEVEL3_CACHE_SIZE * 16 / CACHE_LINESIZE;

    // Allocate and initialize
    obj_L1.resize(size_l1);
    obj_L2.resize(size_l2);
    obj_L3.resize(size_l3);
    obj_MEMORY.resize(size_memory);

    init_array(obj_L1);
    init_array(obj_L2);
    init_array(obj_L3);
    init_array(obj_MEMORY);

    // Pre-compute random indices (enough for all iterations)
    size_t max_iters = 1000000;  // 1M random accesses
    init_random_indices(random_indices_L1, size_l1, max_iters);
    init_random_indices(random_indices_L2, size_l2, max_iters);
    init_random_indices(random_indices_L3, size_l3, max_iters);
    init_random_indices(random_indices_MEMORY, size_memory, max_iters);
}

// Get array reference by name
static std::vector<Item>& get_array(const std::string& level) {
    if (level == "L1") return obj_L1;
    if (level == "L2") return obj_L2;
    if (level == "L3") return obj_L3;
    return obj_MEMORY;
}

// Get random indices reference by name
static std::vector<size_t>& get_random_indices(const std::string& level) {
    if (level == "L1") return random_indices_L1;
    if (level == "L2") return random_indices_L2;
    if (level == "L3") return random_indices_L3;
    return random_indices_MEMORY;
}

// Calculate array size for a given cache factor
static size_t calc_size(size_t full_size, double factor) {
    return static_cast<size_t>(full_size * factor / 100.0);
}

// Sequential access benchmark
template <typename ArrayType>
static void BM_Seq(benchmark::State& state, ArrayType& array, double factor) {
    // Get the effective array size based on factor
    // For L1/L2/L3, we use a subset of the array
    size_t orig_size = array.size();
    size_t effective_size = static_cast<size_t>(orig_size * factor / 100.0);
    if (effective_size == 0) effective_size = 1;

    int sum = 0;
    size_t i = 0;

    // Number of total accesses per benchmark iteration
    const size_t accesses_per_iter = 1000;

    for (auto _ : state) {
        for (size_t iter = 0; iter < accesses_per_iter; ++iter) {
            sum += array[i].value;
            i++;
            if (i >= effective_size) i = 0;
            benchmark::DoNotOptimize(sum);
        }
    }

    state.SetItemsProcessed(state.iterations() * accesses_per_iter);
}

// Random access benchmark
template <typename ArrayType, typename IndexArray>
static void BM_Random(benchmark::State& state, ArrayType& array, IndexArray& indices, double factor) {
    size_t orig_size = array.size();
    size_t effective_size = static_cast<size_t>(orig_size * factor / 100.0);
    if (effective_size == 0) effective_size = 1;

    int sum = 0;
    size_t idx = 0;

    const size_t accesses_per_iter = 1000;

    for (auto _ : state) {
        for (size_t iter = 0; iter < accesses_per_iter; ++iter) {
            // Use pre-computed random index, modulo to ensure it's in range
            size_t raw_idx = indices[idx++ % indices.size()] % effective_size;
            sum += array[raw_idx].value;
            benchmark::DoNotOptimize(sum);
        }
    }

    state.SetItemsProcessed(state.iterations() * accesses_per_iter);
}

// Register benchmarks with all combinations
#define REGISTER_BENCHMARK(level, array_ref, indices_ref)                                     \
    static void BM_##level##_seq(benchmark::State& state) {                                   \
        BM_Seq(state, array_ref, state.range(0));                                             \
    }                                                                                          \
    BENCHMARK(BM_##level##_seq)->ArgsProduct({{50, 70, 90, 100}, {0}})->Iterations(10000);    \
                                                                                               \
    static void BM_##level##_random(benchmark::State& state) {                                \
        BM_Random(state, array_ref, indices_ref, state.range(0));                             \
    }                                                                                          \
    BENCHMARK(BM_##level##_random)->ArgsProduct({{50, 70, 90, 100}, {1}})->Iterations(10000);

// Register all benchmarks
REGISTER_BENCHMARK(L1, obj_L1, random_indices_L1)
REGISTER_BENCHMARK(L2, obj_L2, random_indices_L2)
REGISTER_BENCHMARK(L3, obj_L3, random_indices_L3)
REGISTER_BENCHMARK(MEMORY, obj_MEMORY, random_indices_MEMORY)

// Custom main that initializes data once
int main(int argc, char** argv) {
    // Initialize all data structures once
    setup_benchmarks();

    ::benchmark::Initialize(&argc, argv);
    ::benchmark::RunSpecifiedBenchmarks();
    ::benchmark::Shutdown();
    return 0;
}
