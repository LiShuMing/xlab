#ifndef HASHMAP_LAB_BENCH_BENCH_H_
#define HASHMAP_LAB_BENCH_BENCH_H_

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <optional>
#include <random>
#include <stdexcept>
#include <string>
#include <string_view>
#include <type_traits>
#include <vector>

#include "maps/maps.h"

namespace hashmap_lab {
using Clock = std::chrono::steady_clock;

struct Options {
    std::string method = "std";
    std::string case_name = "short64";
    std::string mode = "lookup";
    std::string distribution = "uniform";
    std::size_t size = 4096;
    std::uint64_t seed = 42;
    int hit = 100;
    int repeat = 5;
    double batch_ms = 20;
    double load = 0.75;
};

template <typename Key>
struct Dataset {
    std::vector<std::string> strings;
    std::vector<Key> keys;
    std::vector<Key> alternates;
    std::vector<Key> queries;
    std::vector<std::uint32_t> expected;
    std::vector<std::size_t> churn_indices;
    std::uint64_t trace_hash = 14695981039346656037ULL;
    std::size_t key_payload_bytes = 0;
};

inline void HashByte(std::uint64_t& hash, unsigned char value) {
    hash = (hash ^ value) * 1099511628211ULL;
}

template <typename Key>
Dataset<Key> MakeDataset(const Options& options, std::vector<std::string> fixed = {}) {
    Dataset<Key> result;
    constexpr std::size_t kQueries = 16384;
    std::size_t count = fixed.empty() ? options.size : fixed.size();
    if constexpr (std::is_same_v<Key, std::string_view>) {
        result.strings.reserve(count * 2 + kQueries);
        for (std::size_t i = 0; i < count; ++i) {
            std::string key = fixed.empty() ? "key-" + std::to_string(Mix(i + 17)) : fixed[i];
            result.key_payload_bytes += key.size();
            result.strings.push_back(key);
        }
        for (std::size_t i = 0; i < count; ++i) {
            // Same length and common prefix: misses cannot win by a length-only rejection.
            std::string key = result.strings[i];
            key.back() = '~';
            result.strings.push_back(key);
        }
        for (std::size_t i = 0; i < count; ++i) {
            result.keys.push_back(result.strings[i]);
            result.alternates.push_back(result.strings[count + i]);
        }
    } else {
        result.key_payload_bytes = count * sizeof(Key);
        for (std::size_t i = 0; i < count; ++i) {
            result.keys.push_back(Mix(i * 2));
            result.alternates.push_back(Mix(i * 2 + 1));
        }
    }
    std::mt19937_64 rng(options.seed);
    std::vector<std::size_t> order(kQueries);
    std::iota(order.begin(), order.end(), 0);
    // Explicit Fisher-Yates gives the same trace across C++ standard-library implementations.
    for (std::size_t i = order.size(); i > 1; --i) std::swap(order[i - 1], order[rng() % i]);
    result.expected.resize(kQueries);
    result.queries.resize(kQueries);
    const std::size_t hits = kQueries * options.hit / 100;
    for (std::size_t i = 0; i < kQueries; ++i) {
        std::size_t index = rng() % count;
        if (options.distribution == "hot" && rng() % 10 < 9)
            index %= std::min(count, std::size_t {8});
        bool hit = order[i] < hits;
        result.queries[i] = hit ? result.keys[index] : result.alternates[index];
        result.expected[i] = hit ? index + 1 : 0;
    }
    if constexpr (std::is_same_v<Key, std::string_view>) {
        // Query characters live in separate allocations from build keys, including short strings.
        const std::size_t first_query = result.strings.size();
        for (Key query : result.queries) result.strings.emplace_back(query);
        for (std::size_t i = 0; i < kQueries; ++i)
            result.queries[i] = result.strings[first_query + i];
    }
    for (std::size_t i = 0; i < kQueries; ++i) {
        if constexpr (std::is_same_v<Key, std::string_view>) {
            for (unsigned char c : result.queries[i]) HashByte(result.trace_hash, c);
        } else {
            for (int shift = 0; shift < 64; shift += 8) {
                HashByte(result.trace_hash, (result.queries[i] >> shift) & 255);
            }
        }
        for (int shift = 0; shift < 32; shift += 8) {
            HashByte(result.trace_hash, (result.expected[i] >> shift) & 255);
        }
        HashByte(result.trace_hash, 255);
    }
    for (std::size_t i = 0; i < 4096; ++i) {
        auto index = rng() % count;
        result.churn_indices.push_back(index);
        for (int shift = 0; shift < 64; shift += 8)
            HashByte(result.trace_hash, (index >> shift) & 255);
    }
    return result;
}

inline void Consume(std::uint64_t value) {
#if defined(__GNUC__) || defined(__clang__)
    asm volatile("" : "+r"(value) : : "memory");
#else
#error "The benchmark needs a compiler barrier implementation for this compiler"
#endif
}

struct Diagnostics {
    double probes = -1;
    double comparisons = -1;
    std::size_t max_probes = 0;
};

template <typename Map, typename Key>
Diagnostics Diagnose(const Map&, const Dataset<Key>&) {
    return {};
}
template <typename Key>
Diagnostics Diagnose(const LinearMap<Key>& map, const Dataset<Key>& data) {
    std::size_t probes = 0, comparisons = 0, maximum = 0;
    for (Key key : data.queries) {
        auto stats = map.Diagnose(key);
        probes += stats.probes;
        comparisons += stats.comparisons;
        maximum = std::max(maximum, stats.probes);
    }
    return {double(probes) / data.queries.size(), double(comparisons) / data.queries.size(),
            maximum};
}

template <typename Map, typename Key>
void Verify(const Map& map, const Dataset<Key>& data) {
    if (map.Size() != data.keys.size()) throw std::runtime_error("size mismatch");
    for (std::size_t i = 0; i < data.keys.size(); ++i) {
        if (map.Find(data.keys[i]) != std::optional<std::uint32_t>(i + 1)) {
            throw std::runtime_error("stored value mismatch");
        }
        if (map.Find(data.alternates[i])) throw std::runtime_error("false positive");
    }
    for (std::size_t i = 0; i < data.queries.size(); ++i) {
        if (map.Find(data.queries[i]).value_or(0) != data.expected[i]) {
            throw std::runtime_error("query mismatch at " + std::to_string(i));
        }
    }
}

template <typename Map, typename Key>
[[gnu::noinline]] std::uint64_t LookupBatch(const Map& map, const Dataset<Key>& data) {
    std::uint64_t sum = 0;
    for (Key key : data.queries) sum += map.Find(key).value_or(0);
    return sum;
}

inline void PrintHeader() {
    std::cout << "mode,case_name,key_type,n,method,hit,distribution,target_load,actual_load,seed,"
                 "sample,operations,elapsed_ns,ns_per_op,checksum,trace_hash,map_bytes,key_payload_"
                 "bytes,"
                 "capacity,mean_probes,mean_comparisons,max_probes,algorithm\n";
}

template <typename Key>
void PrintSample(const Options& options, const Dataset<Key>& data, int sample,
                 std::size_t operations, double elapsed, std::uint64_t checksum, std::size_t bytes,
                 std::size_t capacity, Diagnostics diagnostics, const std::string& algorithm) {
    std::cout << std::setprecision(12) << options.mode << ',' << options.case_name << ','
              << (std::is_same_v<Key, std::string_view> ? "string" : "uint64") << ','
              << data.keys.size() << ',' << options.method << ',' << options.hit << ','
              << options.distribution << ',' << options.load << ','
              << double(data.keys.size()) / capacity << ',' << options.seed << ',' << sample << ','
              << operations << ',' << elapsed << ',' << elapsed / operations << ',' << checksum
              << ',' << data.trace_hash << ',' << bytes << ',' << data.key_payload_bytes << ','
              << capacity << ',';
    if (diagnostics.probes >= 0) std::cout << diagnostics.probes;
    std::cout << ',';
    if (diagnostics.comparisons >= 0) std::cout << diagnostics.comparisons;
    std::cout << ',';
    if (diagnostics.probes >= 0) std::cout << diagnostics.max_probes;
    std::cout << ',' << algorithm << '\n';
}

template <typename Map, typename Key>
void RunLookup(const Map& map, const Options& options, const Dataset<Key>& data,
               const std::string& algorithm) {
    Verify(map, data);
    const auto expected_sum =
            std::accumulate(data.expected.begin(), data.expected.end(), std::uint64_t {0});
    for (int warm = 0; warm < 3; ++warm) Consume(LookupBatch(map, data));
    for (int sample = 0; sample < options.repeat; ++sample) {
        std::uint64_t checksum = 0;
        std::size_t passes = 0;
        auto start = Clock::now();
        auto end = start;
        do {
            auto value = LookupBatch(map, data);
            Consume(value);
            checksum += value;
            ++passes;
            end = Clock::now();
        } while (std::chrono::duration<double, std::milli>(end - start).count() < options.batch_ms);
        if (checksum != expected_sum * passes) throw std::runtime_error("timed checksum mismatch");
        double elapsed = std::chrono::duration<double, std::nano>(end - start).count();
        // Untimed diagnostics run after the measurement; these are not hardware counters.
        auto diagnostics = Diagnose(map, data);
        PrintSample(options, data, sample, passes * data.queries.size(), elapsed, checksum,
                    map.Bytes(), map.Capacity(), diagnostics, algorithm);
    }
}

template <typename Map, typename Key>
void Populate(Map& map, const Dataset<Key>& data) {
    for (std::size_t i = 0; i < data.keys.size(); ++i) map.Insert(data.keys[i], i + 1);
}

template <typename Map, typename Key>
[[gnu::noinline]] std::uint64_t ChurnBatch(Map& map, const Dataset<Key>& data) {
    std::uint64_t successful = 0;
    for (std::size_t i : data.churn_indices) {
        successful += map.Erase(data.keys[i]);
        successful += map.Insert(data.alternates[i], i + 1);
        successful += map.Erase(data.alternates[i]);
        successful += map.Insert(data.keys[i], i + 1);
    }
    return successful;
}

template <typename Map, typename Key>
void RunMutable(const Options& options, const Dataset<Key>& data) {
    const std::string algorithm =
            (std::is_same_v<Key, std::string_view> ? "fnv1a-mix/" : "integer-mix/") +
            options.method;
    Map map(options.mode == "build-growing" ? 0 : data.keys.size(), options.load);
    Populate(map, data);
    Verify(map, data);
    if (options.mode == "lookup") {
        RunLookup(map, options, data, algorithm);
        return;
    }
    for (int sample = 0; sample < options.repeat; ++sample) {
        std::uint64_t checksum = 0;
        std::size_t operations = 0;
        auto start = Clock::now();
        auto end = start;
        do {
            if (options.mode == "churn") {
                auto result = ChurnBatch(map, data);
                if (result != data.churn_indices.size() * 4)
                    throw std::runtime_error("churn failed");
                Consume(result);
                checksum += result;
                operations += data.churn_indices.size() * 4;
            } else {
                // This metric includes destruction: a complete build/destroy cycle per pass.
                Map fresh(options.mode == "build-reserved" ? data.keys.size() : 0, options.load);
                Populate(fresh, data);
                auto value = fresh.Find(data.keys.back()).value_or(0) + fresh.Size();
                Consume(value);
                checksum += value;
                operations += data.keys.size();
            }
            end = Clock::now();
        } while (std::chrono::duration<double, std::milli>(end - start).count() < options.batch_ms);
        double elapsed = std::chrono::duration<double, std::nano>(end - start).count();
        Verify(map, data);
        if (options.mode != "churn" && checksum != operations * 2) {
            throw std::runtime_error("build checksum mismatch");
        }
        PrintSample(options, data, sample, operations, elapsed, checksum, map.Bytes(),
                    map.Capacity(), {}, algorithm);
    }
}

template <typename Table>
class PerfectAdapter {
public:
    explicit PerfectAdapter(const Table& table) : table_(table) {}
    auto Find(std::string_view key) const { return table_.lookup(key); }
    std::size_t Size() const { return table_.size(); }
    std::size_t Capacity() const { return table_.table_size(); }
    std::size_t Bytes() const { return sizeof(Table); }

private:
    const Table& table_;
};

template <typename Table>
void RunPerfectLookup(const Table& table, const Options& options,
                      const Dataset<std::string_view>& data) {
    RunLookup(PerfectAdapter<Table>(table), options, data, std::string(table.algorithm_name()));
}

void RunPerfect(const Options& options, const Dataset<std::string_view>& data);
} // namespace hashmap_lab
#endif // HASHMAP_LAB_BENCH_BENCH_H_
