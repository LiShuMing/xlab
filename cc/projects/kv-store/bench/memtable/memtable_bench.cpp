#include <benchmark/benchmark.h>
#include <map>
#include <random>
#include <string>
#include <unordered_map>

#include "tinykv/memtable/memtable.hpp"

namespace tinykv {
namespace {

// Benchmark state
std::unique_ptr<MemTable> memtable_;

// Benchmark: Sequential Put
void BM_SeqPut(benchmark::State& state) {
    memtable_ = std::make_unique<MemTable>();

    int i = 0;
    for (auto _ : state) {
        memtable_->Put("key" + std::to_string(i), "value");
        ++i;
    }
}
BENCHMARK(BM_SeqPut);

// Benchmark: Random Put
void BM_RandomPut(benchmark::State& state) {
    memtable_ = std::make_unique<MemTable>();

    std::mt19937 rng(state.range(0));
    std::uniform_int_distribution<int> dist(0, 1000000);

    for (auto _ : state) {
        memtable_->Put("key" + std::to_string(dist(rng)), "value");
    }
}
BENCHMARK(BM_RandomPut)->Range(0, 42);

// Benchmark: Random Get (after filling)
void BM_RandomGet(benchmark::State& state) {
    memtable_ = std::make_unique<MemTable>();

    std::mt19937 fill_rng(42);
    std::uniform_int_distribution<int> dist(0, 1000000);

    // Fill with 10000 entries
    for (int i = 0; i < 10000; ++i) {
        memtable_->Put("key" + std::to_string(dist(fill_rng)), "value");
    }

    std::mt19937 query_rng(state.range(0));
    std::string value;
    for (auto _ : state) {
        benchmark::DoNotOptimize(
            memtable_->Get("key" + std::to_string(dist(query_rng)), &value));
    }
}
BENCHMARK(BM_RandomGet)->Range(0, 42);

// Benchmark: Sequential Get
void BM_SeqGet(benchmark::State& state) {
    memtable_ = std::make_unique<MemTable>();

    // Fill sequentially
    for (int i = 0; i < state.range(0); ++i) {
        memtable_->Put("key" + std::to_string(i), "value");
    }

    int i = 0;
    std::string value;
    for (auto _ : state) {
        benchmark::DoNotOptimize(
            memtable_->Get("key" + std::to_string(i), &value));
        ++i;
    }
}
BENCHMARK(BM_SeqGet)->Range(1000, 10000);

// Benchmark: Mixed workload (Put/Get/Delete)
void BM_Mixed(benchmark::State& state) {
    memtable_ = std::make_unique<MemTable>();

    std::mt19937 rng(state.range(0));
    std::uniform_int_distribution<int> op_dist(0, 99);  // 0-49: Put, 50-99: Get
    std::uniform_int_distribution<int> key_dist(0, 10000);
    std::string value;

    for (auto _ : state) {
        int op = op_dist(rng);
        std::string key = "key" + std::to_string(key_dist(rng));

        if (op < 50) {
            memtable_->Put(key, "value");
        } else {
            benchmark::DoNotOptimize(memtable_->Get(key, &value));
        }
    }
}
BENCHMARK(BM_Mixed)->Range(0, 42);

// Benchmark: Iterator traversal
void BM_IteratorTraversal(benchmark::State& state) {
    memtable_ = std::make_unique<MemTable>();

    // Fill
    for (int i = 0; i < state.range(0); ++i) {
        memtable_->Put("key" + std::to_string(i), "value");
    }

    for (auto _ : state) {
        for (auto it = memtable_->NewIterator(); it.Valid(); it.Next()) {
            benchmark::DoNotOptimize(it.CurrentKey());
        }
    }
}
BENCHMARK(BM_IteratorTraversal)->Range(1000, 10000);

// Comparison benchmarks against std::map
void BM_StdMapPut(benchmark::State& state) {
    std::map<std::string, std::string> map;
    int i = 0;
    for (auto _ : state) {
        map["key" + std::to_string(i)] = "value";
        ++i;
    }
}
BENCHMARK(BM_StdMapPut);

void BM_StdMapGet(benchmark::State& state) {
    std::map<std::string, std::string> map;

    // Fill
    for (int i = 0; i < state.range(0); ++i) {
        map["key" + std::to_string(i)] = "value";
    }

    std::mt19937 rng(state.range(0));
    std::uniform_int_distribution<int> dist(0, state.range(0) - 1);
    std::string value;
    int i = 0;
    for (auto _ : state) {
        benchmark::DoNotOptimize(map.find("key" + std::to_string(dist(rng))));
        ++i;
    }
}
BENCHMARK(BM_StdMapGet)->Range(1000, 10000);

void BM_StdUnorderedMapPut(benchmark::State& state) {
    std::unordered_map<std::string, std::string> map;
    int i = 0;
    for (auto _ : state) {
        map["key" + std::to_string(i)] = "value";
        ++i;
    }
}
BENCHMARK(BM_StdUnorderedMapPut);

void BM_StdUnorderedMapGet(benchmark::State& state) {
    std::unordered_map<std::string, std::string> map;

    // Fill
    for (int i = 0; i < state.range(0); ++i) {
        map["key" + std::to_string(i)] = "value";
    }

    std::mt19937 rng(state.range(0));
    std::uniform_int_distribution<int> dist(0, state.range(0) - 1);
    int i = 0;
    for (auto _ : state) {
        benchmark::DoNotOptimize(map.find("key" + std::to_string(dist(rng))));
        ++i;
    }
}
BENCHMARK(BM_StdUnorderedMapGet)->Range(1000, 10000);

// Memory usage benchmark
void BM_MemoryUsage(benchmark::State& state) {
    memtable_ = std::make_unique<MemTable>();

    for (auto _ : state) {
        for (int i = 0; i < state.range(0); ++i) {
            memtable_->Put("key" + std::to_string(i), "value");
        }
        benchmark::DoNotOptimize(memtable_->ApproximateMemoryUsage());
    }
}
BENCHMARK(BM_MemoryUsage)->Range(1000, 10000);

}  // namespace
}  // namespace tinykv

BENCHMARK_MAIN();
