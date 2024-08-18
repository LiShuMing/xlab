#include <benchmark/benchmark.h>

#include <iostream>
#include <random>

// You can get these cache info by `getconf -a | grep -i cache`
constexpr size_t CACHE_LINESIZE = 64;

// 32 KB
constexpr size_t LEVEL1_DCACHE_SIZE = 32768;
// 4 MB
constexpr size_t LEVEL2_CACHE_SIZE = 4 * 1048576;
// 36 MB
constexpr size_t LEVEL3_CACHE_SIZE = 37486592;

// Suppose that 90% of capacity of cache is used by this program
constexpr double FACTOR = 0.9;

constexpr size_t MAX_ARRAY_SIZE_L1 = FACTOR * LEVEL1_DCACHE_SIZE / CACHE_LINESIZE;
constexpr size_t MAX_ARRAY_SIZE_L2 = FACTOR * LEVEL2_CACHE_SIZE / CACHE_LINESIZE;
constexpr size_t MAX_ARRAY_SIZE_L3 = FACTOR * LEVEL3_CACHE_SIZE / CACHE_LINESIZE;
constexpr size_t MAX_ARRAY_SIZE_MEMORY = LEVEL3_CACHE_SIZE * 16 / CACHE_LINESIZE;

constexpr const size_t ITERATOR_TIMES =
        std::max(MAX_ARRAY_SIZE_L1, std::max(MAX_ARRAY_SIZE_L2, std::max(MAX_ARRAY_SIZE_L3, MAX_ARRAY_SIZE_MEMORY)));

// Size of Item equals to CACHE_LINESIZE
struct Item {
    int value;
private:
    int pad[CACHE_LINESIZE / 4 - 1];
};

static_assert(sizeof(Item) == CACHE_LINESIZE, "Item size is not equals to CACHE_LINESIZE");

template <size_t size>
struct Obj {
    Item data[size];
};

static Obj<MAX_ARRAY_SIZE_L1> obj_L1;
static Obj<MAX_ARRAY_SIZE_L2> obj_L2;
static Obj<MAX_ARRAY_SIZE_L3> obj_L3;
static Obj<MAX_ARRAY_SIZE_MEMORY> obj_MEMORY;

template <size_t size>
void init(Obj<size>& obj) {
    static std::default_random_engine e;
    static std::uniform_int_distribution<int> u(0, 1);
    for (size_t i = 0; i < size; ++i) {
        obj.data[i].value = u(e);
    }
}

#define BM_cache(level)                               \
    static void BM_##level(benchmark::State& state) { \
        init(obj_##level);                            \
        int sum = 0;                                  \
        for (auto _ : state) {                        \
            int count = ITERATOR_TIMES;               \
            size_t i = 0;                             \
            while (count-- > 0) {                     \
                sum += obj_##level.data[i].value;     \
                i++;                                  \
                if (i >= MAX_ARRAY_SIZE_##level) {    \
                    i = 0;                            \
                }                                     \
                benchmark::DoNotOptimize(sum);        \
            }                                         \
        }                                             \
    }                                                 \
    BENCHMARK(BM_##level);

BM_cache(L1);
BM_cache(L2);
BM_cache(L3);
BM_cache(MEMORY);

BENCHMARK_MAIN();