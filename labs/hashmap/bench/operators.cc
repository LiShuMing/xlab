#include <time.h>

#include <chrono>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <random>
#include <string>

#include "bench/bench.h"
#include "maps/operator_maps.h"

namespace hashmap_lab::operators {
namespace {
struct Config {
    std::string method = "std", case_name = "agg-dense8", mode = "aggregate",
                distribution = "uniform";
    std::size_t n = 65536, ndv = 64, domain = 256;
    int hit = 50, null_percent = 0, repeat = 5;
    std::uint64_t seed = 42;
    double batch_ms = 20, load = 0.75;
};
Config Parse(int argc, char** argv) {
    Config c;
    for (int i = 1; i < argc; i += 2) {
        if (i + 1 == argc) throw std::invalid_argument("option needs value");
        std::string k = argv[i], v = argv[i + 1];
        std::size_t used = 0;
        auto number = [&]() {
            if (v.empty() || v[0] == '-') throw std::invalid_argument("negative number");
            auto n = std::stoull(v, &used);
            if (used != v.size()) throw std::invalid_argument("invalid number");
            return n;
        };
        auto real = [&]() {
            auto n = std::stod(v, &used);
            if (used != v.size() || !std::isfinite(n)) throw std::invalid_argument("invalid real");
            return n;
        };
        if (k == "--method")
            c.method = v;
        else if (k == "--case")
            c.case_name = v;
        else if (k == "--mode")
            c.mode = v;
        else if (k == "--distribution")
            c.distribution = v;
        else if (k == "--n")
            c.n = number();
        else if (k == "--ndv")
            c.ndv = number();
        else if (k == "--domain")
            c.domain = number();
        else if (k == "--hit" || k == "--null-percent") {
            auto p = number();
            if (p > 100) throw std::invalid_argument("percentage >100");
            if (k == "--hit")
                c.hit = p;
            else
                c.null_percent = p;
        } else if (k == "--repeat") {
            auto r = number();
            if (r > 1000) throw std::invalid_argument("too many repeats");
            c.repeat = r;
        } else if (k == "--seed")
            c.seed = number();
        else if (k == "--batch-ms")
            c.batch_ms = real();
        else if (k == "--load")
            c.load = real();
        else
            throw std::invalid_argument("unknown option " + k);
    }
    if (!c.n || c.n > 1000000 || !c.ndv || c.ndv > c.n || c.domain > 1048576 || c.repeat < 1 ||
        c.batch_ms <= 0 || c.batch_ms > 10000 || c.load != 0.75)
        throw std::invalid_argument("invalid dimensions/timing; operator tables use load 0.75");
    if (c.distribution != "uniform" && c.distribution != "hot" && c.distribution != "phases")
        throw std::invalid_argument("unknown distribution");
    if (c.case_name != "agg-dense8" && c.case_name != "agg-dense16" &&
        c.case_name != "agg-sparse64" && c.case_name != "agg-composite32x2" &&
        c.case_name != "join-dense" && c.case_name != "join-sparse" && c.case_name != "join-skew" &&
        c.case_name != "semi-dense")
        throw std::invalid_argument("unknown operator case");
    bool agg = c.case_name.starts_with("agg-");
    bool semi = c.case_name.starts_with("semi-");
    if ((agg && c.mode != "aggregate") || (semi && c.mode != "semi-probe") ||
        (!agg && !semi && c.mode != "join-build" && c.mode != "join-probe"))
        throw std::invalid_argument("case/mode mismatch");
    if ((agg && c.method != "std" && c.method != "flat-u64" && c.method != "flat-fp" &&
         c.method != "flat-bytes" && c.method != "direct") ||
        (semi && c.method != "std" && c.method != "bitmap") ||
        (!agg && !semi && c.method != "bucket" && c.method != "chain" && c.method != "chain-fp" &&
         c.method != "direct"))
        throw std::invalid_argument("unsupported operator strategy");
    if (c.domain && c.domain < c.ndv) throw std::invalid_argument("domain smaller than NDV");
    if ((c.method == "direct" || c.method == "bitmap") && !c.domain)
        throw std::invalid_argument("direct strategy needs bounded domain");
    return c;
}
struct Input {
    std::vector<Row> build, probe;
    std::vector<Group> groups;
    std::vector<State> expected;
    std::uint64_t trace = 14695981039346656037ULL, agg_checksum = 0, probe_checksum = 0,
                  semi_checksum = 0;
    std::size_t actual_ndv = 0, null_rows = 0, probe_hits = 0;
};
std::uint64_t Key(const Config& c, std::size_t index) {
    if (c.domain) return 17 + index * std::max(std::size_t {1}, c.domain / c.ndv);
    if (c.case_name == "agg-composite32x2") {
        auto left = static_cast<std::uint32_t>(index / 32),
             right = static_cast<std::uint32_t>(index % 32);
        return (std::uint64_t(left) << 32) | right;
    }
    return Mix(index + 17);
}
Input MakeInput(const Config& c) {
    Input input;
    input.build.reserve(c.n);
    std::mt19937_64 rng(c.seed);
    std::map<std::pair<bool, std::uint64_t>, State> reference;
    std::map<std::uint64_t, State> join_reference;
    auto index_for = [&](std::size_t i, std::size_t total) {
        std::size_t index = rng() % c.ndv;
        if (c.distribution == "hot" && rng() % 10 < 9) index %= std::min(c.ndv, std::size_t {8});
        if (c.distribution == "phases") {
            if (i < total / 4)
                index %= std::max(std::size_t {1}, c.ndv / 8);
            else if (i >= total / 2 && i < 3 * total / 4)
                index %= std::min(c.ndv, std::size_t {8});
            else if (i >= 3 * total / 4)
                index = c.ndv - 1 - index % std::min(c.ndv, std::size_t {8});
        }
        return index;
    };
    for (std::size_t i = 0; i < c.n; ++i) {
        Row row;
        row.key = Key(c, index_for(i, c.n));
        row.value = 1 + rng() % 17;
        row.is_null = rng() % 100 < static_cast<unsigned>(c.null_percent);
        Encode(row);
        input.build.push_back(row);
        input.null_rows += row.is_null;
        auto& state = reference[{row.is_null, row.is_null ? 0 : row.key}];
        state.Add(row.value);
        input.agg_checksum += state.count + state.sum;
        if (!row.is_null) {
            ++join_reference[row.key].count;
            join_reference[row.key].sum += i + 1;
        }
    }
    input.actual_ndv = join_reference.size();
    for (auto [key, state] : reference) input.groups.push_back({key.first, key.second, state});
    std::vector<std::uint64_t> present_keys;
    for (std::size_t index = 0; index < c.ndv; ++index) {
        auto key = Key(c, index);
        if (join_reference.contains(key)) present_keys.push_back(key);
    }
    for (std::size_t i = 0; i < 16384; ++i) {
        Row row;
        auto index = index_for(i, 16384);
        bool hit = rng() % 100 < static_cast<unsigned>(c.hit);
        if (hit && !present_keys.empty())
            row.key = present_keys[index % present_keys.size()];
        else if (c.domain / c.ndv >= 2 && rng() % 2)
            row.key = Key(c, index) + 1;
        else
            row.key = Key(c, index + c.ndv);
        row.is_null = rng() % 100 < static_cast<unsigned>(c.null_percent);
        Encode(row);
        input.probe.push_back(row);
        auto found = join_reference.find(row.key);
        State expected;
        if (!row.is_null && found != join_reference.end()) expected = found->second;
        input.expected.push_back(expected);
        input.probe_checksum += expected.count + expected.sum;
        input.semi_checksum += expected.count != 0;
        input.probe_hits += expected.count != 0;
    }
    // Canonical input trace is independent of table layout and includes all state inputs.
    for (const auto* rows : {&input.build, &input.probe}) {
        for (const Row& row : *rows) {
            for (int shift = 0; shift < 64; shift += 8) {
                HashByte(input.trace, row.key >> shift);
                HashByte(input.trace, row.value >> shift);
            }
            HashByte(input.trace, row.is_null);
        }
    }
    return input;
}

template <typename Map>
std::uint64_t AggregateInto(Map& map, const std::vector<Row>& rows) {
    std::uint64_t checksum = 0;
    for (const auto& row : rows) {
        const auto& state = row.is_null ? map.AddNull(row.value)
                                        : map.Add(RowKey<typename Map::KeyType>(row), row.value);
        checksum += state.count + state.sum;
    }
    return checksum;
}
template <typename Map>
[[gnu::noinline]] std::uint64_t AggregateCycle(const Config& c, const Input& input) {
    Map map(17, c.domain);
    return AggregateInto(map, input.build);
}
template <typename Table>
[[gnu::noinline]] std::uint64_t ProbeBatch(const Table& table, const Input& input) {
    std::uint64_t checksum = 0;
    for (const Row& row : input.probe) {
        auto state = table.Probe(row);
        checksum += state.count + state.sum;
    }
    return checksum;
}
template <typename Table>
[[gnu::noinline]] std::uint64_t BuildCycle(const Config& c, const Input& input) {
    Table table(input.build, 17, c.domain);
    auto result = table.Probe(input.probe[0]);
    return result.count + result.sum;
}
template <typename Set>
[[gnu::noinline]] std::uint64_t SemiBatch(const Set& set, const Input& input) {
    std::uint64_t result = 0;
    for (const Row& row : input.probe) result += set.Contains(row);
    return result;
}

std::uint64_t CpuNanoseconds() {
    timespec value {};
    if (clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &value) != 0) {
        throw std::runtime_error("process CPU clock unavailable");
    }
    return std::uint64_t(value.tv_sec) * 1000000000ULL + value.tv_nsec;
}

template <typename Function>
void Measure(const Config& c, const Input& input, std::size_t operations, std::uint64_t expected,
             std::size_t bytes, std::size_t capacity, Function run, const std::string& algorithm,
             double probes = -1, double comparisons = -1, std::uint64_t max_steps = 0) {
    for (int i = 0; i < 2; ++i) {
        auto value = run();
        if (value != expected) throw std::runtime_error("warmup checksum");
        Consume(value);
    }
    for (int sample = 0; sample < c.repeat; ++sample) {
        auto cpu_start = CpuNanoseconds();
        auto start = Clock::now(), end = start;
        std::uint64_t checksum = 0;
        std::size_t passes = 0;
        do {
            auto value = run();
            Consume(value);
            checksum += value;
            ++passes;
            end = Clock::now();
        } while (std::chrono::duration<double, std::milli>(end - start).count() < c.batch_ms);
        auto cpu_end = CpuNanoseconds();
        if (checksum != expected * passes) throw std::runtime_error("timed operator checksum");
        auto elapsed = std::chrono::duration<double, std::nano>(end - start).count();
        auto cpu_ns = double(cpu_end - cpu_start);
        auto count = operations * passes;
        std::cout << std::setprecision(12) << c.mode << ',' << c.case_name << ",operator," << c.n
                  << ',' << c.method << ',' << c.hit << ',' << c.distribution << ",0.75,"
                  << double(input.actual_ndv) / capacity << ',' << c.seed << ',' << sample << ','
                  << count << ',' << elapsed << ',' << elapsed / count << ',' << checksum << ','
                  << input.trace << ',' << bytes << ',' << input.build.size() * 8 << ',' << capacity
                  << ',';
        if (probes >= 0) std::cout << probes;
        std::cout << ',';
        if (comparisons >= 0) std::cout << comparisons;
        std::cout << ',';
        if (probes >= 0) std::cout << max_steps;
        std::cout << ',' << algorithm << ',' << input.actual_ndv << ',' << input.null_rows << ','
                  << input.probe.size() << ',' << double(input.probe_hits) / input.probe.size()
                  << ',' << cpu_ns / count << ',' << input.probe_checksum << ',' << c.ndv << ','
                  << c.domain << ',' << c.null_percent << '\n';
    }
}
template <typename Map>
void RunAggregate(const Config& c, const Input& input) {
    Map map(17, c.domain);
    if (AggregateInto(map, input.build) != input.agg_checksum || map.Snapshot() != input.groups)
        throw std::runtime_error("full aggregate state mismatch");
    Measure(
            c, input, input.build.size(), input.agg_checksum, map.Bytes(), map.Capacity(),
            [&]() { return AggregateCycle<Map>(c, input); }, "append-only-count-sum/" + c.method);
}
template <typename Table>
void RunJoin(const Config& c, const Input& input) {
    Table table(input.build, 17, c.domain);
    JoinStats total;
    std::uint64_t maximum = 0;
    for (std::size_t i = 0; i < input.probe.size(); ++i) {
        if (table.Probe(input.probe[i]) != input.expected[i])
            throw std::runtime_error("join duplicate/null/miss mismatch");
        JoinStats stats;
        table.template Probe<true>(input.probe[i], &stats);
        total.steps += stats.steps;
        total.comparisons += stats.comparisons;
        maximum = std::max(maximum, stats.steps);
    }
    if (c.mode == "join-build") {
        auto first = input.expected[0];
        Measure(
                c, input, input.build.size(), first.count + first.sum, table.Bytes(),
                table.Capacity(), [&]() { return BuildCycle<Table>(c, input); },
                "row-id-chains-build/" + c.method);
    } else {
        Measure(
                c, input, input.probe.size(), input.probe_checksum, table.Bytes(), table.Capacity(),
                [&]() { return ProbeBatch(table, input); }, "row-id-chains-probe/" + c.method,
                double(total.steps) / input.probe.size(),
                double(total.comparisons) / input.probe.size(), maximum);
    }
}
template <typename Set>
void RunSemi(const Config& c, const Input& input) {
    Set set(17, c.domain);
    for (const auto& row : input.build) set.Insert(row);
    for (std::size_t i = 0; i < input.probe.size(); ++i) {
        if (set.Contains(input.probe[i]) != (input.expected[i].count != 0))
            throw std::runtime_error("semi membership mismatch");
    }
    Measure(
            c, input, input.probe.size(), input.semi_checksum, set.Bytes(), set.Capacity(),
            [&]() { return SemiBatch(set, input); }, "membership-only/" + c.method);
}
} // namespace
} // namespace hashmap_lab::operators

int main(int argc, char** argv) {
    using namespace hashmap_lab;
    using namespace hashmap_lab::operators;
    try {
        auto c = Parse(argc, argv);
        auto input = MakeInput(c);
        std::cout << "mode,case_name,key_type,n,method,hit,distribution,target_load,actual_load,"
                     "seed,sample,operations,elapsed_ns,ns_per_op,checksum,trace_hash,map_bytes,"
                     "key_payload_bytes,capacity,mean_probes,mean_comparisons,max_probes,algorithm,"
                     "ndv,null_rows,query_rows,actual_hit_ratio,cpu_ns_per_op,join_result_digest,"
                     "ndv_config,domain,null_percent\n";
        if (c.mode == "aggregate") {
            if (c.method == "std")
                RunAggregate<StdAggregate<std::uint64_t>>(c, input);
            else if (c.method == "flat-u64")
                RunAggregate<FlatAggregate<std::uint64_t, false>>(c, input);
            else if (c.method == "flat-fp")
                RunAggregate<FlatAggregate<std::uint64_t, true>>(c, input);
            else if (c.method == "flat-bytes")
                RunAggregate<FlatAggregate<std::string_view, true>>(c, input);
            else
                RunAggregate<DirectAggregate>(c, input);
        } else if (c.mode == "semi-probe") {
            if (c.method == "std")
                RunSemi<StdSet>(c, input);
            else
                RunSemi<BitmapSet>(c, input);
        } else {
            if (c.method == "bucket")
                RunJoin<JoinTable<JoinKind::kBucket>>(c, input);
            else if (c.method == "chain")
                RunJoin<JoinTable<JoinKind::kLinear>>(c, input);
            else if (c.method == "chain-fp")
                RunJoin<JoinTable<JoinKind::kFingerprint>>(c, input);
            else
                RunJoin<JoinTable<JoinKind::kDirect>>(c, input);
        }
    } catch (const std::exception& error) {
        std::cerr << "hashmap_operators: " << error.what() << '\n';
        return 1;
    }
}
