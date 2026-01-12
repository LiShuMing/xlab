#include <chrono>
#include <iostream>
#include <random>
#include <vector>

#include "benchmark/benchmark.h"
#include "vagg/ht/hash_table.h"
#include "vagg/ops/aggregate_op.h"
#include "vagg/ops/scan_op.h"

namespace vagg {

// Benchmark: Hash table insert performance
static void BM_HashTable_Insert(benchmark::State& state) {
  const size_t num_keys = state.range(0);
  const int key_range = state.range(1);

  for (auto _ : state) {
    HashTable<int32_t, int64_t> ht;

    // Generate keys
    std::mt19937 rng(42);
    std::uniform_int_distribution<int32_t> dist(0, key_range - 1);

    for (size_t i = 0; i < num_keys; ++i) {
      int32_t key = dist(rng);
      auto* entry = ht.FindOrInsert(key);
      entry->value += 1;
    }

    benchmark::ClobberMemory();
  }

  state.counters["keys_per_second"] = benchmark::Counter(
      static_cast<int64_t>(state.range(0)),
      benchmark::Counter::kIsRate);
}

BENCHMARK(BM_HashTable_Insert)
    ->Args({10000, 10000})    // 10K keys, 10K range (low cardinality)
    ->Args({100000, 100000})  // 100K keys, 100K range (high cardinality)
    ->Args({1000000, 1000000}) // 1M keys, 1M range (high cardinality)
    ->Unit(benchmark::kMillisecond);

// Benchmark: Aggregation throughput
static void BM_Aggregation_Throughput(benchmark::State& state) {
  const size_t num_rows = state.range(0);
  const int key_range = state.range(1);
  const size_t batch_size = 4096;

  for (auto _ : state) {
    auto source = std::make_unique<GeneratedDataSource>(
        num_rows, batch_size,
        GeneratedDataSource::Distribution::kUniform,
        key_range);

    auto agg = std::make_unique<HashAggregateOp>(
        std::make_unique<ScanOp>(std::move(source)));

    ExecContext ctx;
    agg->Prepare(&ctx);

    // Consume all output
    KeyValueChunk chunk;
    size_t total_rows = 0;
    while (true) {
      Status status = agg->Next(&chunk);
      if (status.code() == StatusCode::kEndOfFile) break;
      total_rows += chunk.num_rows();
    }

    benchmark::ClobberMemory();
  }

  state.counters["rows_per_second"] = benchmark::Counter(
      static_cast<int64_t>(state.range(0)),
      benchmark::Counter::kIsRate);
}

BENCHMARK(BM_Aggregation_Throughput)
    ->Args({100000, 1000})     // 100K rows, 1K unique keys (low cardinality)
    ->Args({1000000, 10000})   // 1M rows, 10K unique keys (medium)
    ->Args({1000000, 1000000}) // 1M rows, 1M unique keys (high cardinality)
    ->Unit(benchmark::kMillisecond);

// Benchmark: Hash table statistics at different load factors
static void BM_HashTable_Statistics(benchmark::State& state) {
  const size_t num_entries = state.range(0);

  for (auto _ : state) {
    HashTable<int32_t, int64_t> ht;
    ht.ResetStats();

    for (size_t i = 0; i < num_entries; ++i) {
      ht.FindOrInsert(static_cast<int32_t>(i));
    }

    auto stats = ht.GetStats();
    // Access stats to prevent optimization
    benchmark::DoNotOptimize(stats.average_probes);
  }
}

BENCHMARK(BM_HashTable_Statistics)
    ->Args({10000})
    ->Args({100000})
    ->Args({1000000})
    ->Unit(benchmark::kMillisecond);

// Benchmark: Scan + Aggregate pipeline
static void BM_Pipeline_ScanAggregate(benchmark::State& state) {
  const size_t num_rows = state.range(0);
  const size_t batch_size = state.range(1);

  for (auto _ : state) {
    auto source = std::make_unique<GeneratedDataSource>(
        num_rows, batch_size,
        GeneratedDataSource::Distribution::kUniform,
        100000);

    auto scan = std::make_unique<ScanOp>(std::move(source));
    auto agg = std::make_unique<HashAggregateOp>(std::move(scan));

    ExecContext ctx;
    agg->Prepare(&ctx);

    // Consume output
    KeyValueChunk chunk;
    while (agg->Next(&chunk).code() != StatusCode::kEndOfFile) {
      // Just consume
    }
  }

  state.counters["rows_per_second"] = benchmark::Counter(
      static_cast<int64_t>(num_rows),
      benchmark::Counter::kIsRate);
}

BENCHMARK(BM_Pipeline_ScanAggregate)
    ->Args({1000000, 1024})
    ->Args({1000000, 4096})
    ->Args({1000000, 16384})
    ->Unit(benchmark::kMillisecond);

// Main
BENCHMARK_MAIN();

}  // namespace vagg
