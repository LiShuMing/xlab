#include <time.h>

#include <array>
#include <chrono>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <random>
#include <string>

#include "bench/bench.h"
#include "maps/state_maps.h"

namespace hashmap_lab::states {
namespace {
struct Config {
    std::string method = "std", name = "few-groups", distribution = "uniform";
    std::size_t n = 65536, ndv = 64, state_bytes = 16;
    std::uint64_t seed = 42;
    int null_percent = 10, repeat = 5;
    double batch_ms = 20;
};
Config Parse(int argc, char** argv) {
    Config c;
    for (int i = 1; i < argc; i += 2) {
        if (i + 1 == argc) throw std::invalid_argument("option needs value");
        std::string key = argv[i], value = argv[i + 1];
        auto number = [&]() {
            std::size_t used = 0;
            if (value.empty() || value[0] == '-') throw std::invalid_argument("negative number");
            auto result = std::stoull(value, &used);
            if (used != value.size()) throw std::invalid_argument("invalid number");
            return result;
        };
        if (key == "--method")
            c.method = value;
        else if (key == "--case")
            c.name = value;
        else if (key == "--distribution")
            c.distribution = value;
        else if (key == "--n")
            c.n = number();
        else if (key == "--ndv")
            c.ndv = number();
        else if (key == "--seed")
            c.seed = number();
        else if (key == "--state-bytes")
            c.state_bytes = number();
        else if (key == "--null-percent") {
            auto percent = number();
            if (percent > 100) throw std::invalid_argument("invalid null percentage");
            c.null_percent = percent;
        } else if (key == "--repeat") {
            auto repeat = number();
            if (!repeat || repeat > 1000) throw std::invalid_argument("invalid repeat");
            c.repeat = repeat;
        } else if (key == "--batch-ms") {
            std::size_t used = 0;
            c.batch_ms = std::stod(value, &used);
            if (used != value.size()) throw std::invalid_argument("invalid timing");
        } else
            throw std::invalid_argument("unknown option " + key);
    }
    if (!c.n || c.n % 4 || c.n > 262144 || !c.ndv || c.ndv > c.n || c.ndv > 32768 ||
        !std::isfinite(c.batch_ms) || c.batch_ms <= 0 || c.batch_ms > 10000)
        throw std::invalid_argument("invalid dimensions/timing");
    if (c.state_bytes != 16 && c.state_bytes != 256 && c.state_bytes != 4096)
        throw std::invalid_argument("state size must be 16/256/4096 bytes");
    if (c.name != "few-groups" && c.name != "many-groups" && c.name != "unique")
        throw std::invalid_argument("unknown case");
    if (c.distribution != "uniform" && c.distribution != "phases")
        throw std::invalid_argument("unknown distribution");
    if (c.name == "unique" && (c.ndv != c.n || c.null_percent || c.distribution != "uniform"))
        throw std::invalid_argument("unique requires n=ndv, no NULL, uniform");
    if (c.method != "std" && c.method != "std-eager" && c.method != "inline" &&
        c.method != "arena-lazy")
        throw std::invalid_argument("unknown state strategy");
    return c;
}

std::uint64_t CpuNanoseconds() {
    timespec value {};
    if (clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &value) != 0)
        throw std::runtime_error("CPU clock unavailable");
    return std::uint64_t(value.tv_sec) * 1000000000ULL + value.tv_nsec;
}
template <std::size_t Bytes>
struct Input {
    std::vector<Row> rows;
    std::map<Key, State<Bytes>> groups;
    std::uint64_t checksum = 0, trace = 14695981039346656037ULL, digest = 0;
    std::size_t null_rows = 0;
};
template <std::size_t Bytes>
Input<Bytes> MakeInput(const Config& c) {
    Input<Bytes> input;
    input.rows.reserve(c.n);
    std::mt19937_64 rng(c.seed);
    for (std::size_t i = 0; i < c.n; ++i) {
        auto index = c.name == "unique" ? i : rng() % c.ndv;
        if (c.distribution == "phases") {
            if (i < c.n / 4)
                index %= std::max(std::size_t {1}, c.ndv / 8);
            else if (i >= c.n / 2 && i < c.n * 3 / 4)
                index %= std::min(c.ndv, std::size_t {8});
            else if (i >= c.n * 3 / 4)
                index = c.ndv - 1 - index % std::min(c.ndv, std::size_t {8});
        }
        Row row {{Mix(index), rng() % 100 < static_cast<unsigned>(c.null_percent)}, rng()};
        if (row.key.is_null) row.key.value = 0;
        input.null_rows += row.key.is_null;
        input.rows.push_back(row);
        // Independent reference updates all semantic fields without calling State::Add.
        auto& words = input.groups[row.key].words;
        ++words[0];
        words[1] += row.value;
        std::uint64_t bin = 0;
        if constexpr (Bytes > 16) {
            auto slot = 2 + row.value % (words.size() - 2);
            words[slot] += row.value;
            bin = words[slot];
        }
        input.checksum += words[0] + words[1] + bin;
        for (int shift = 0; shift < 64; shift += 8) {
            HashByte(input.trace, row.key.value >> shift);
            HashByte(input.trace, row.value >> shift);
        }
        HashByte(input.trace, row.key.is_null);
    }
    for (const auto& [key, state] : input.groups) {
        input.digest = Mix(input.digest ^ key.value ^ key.is_null);
        for (auto word : state.words) input.digest = Mix(input.digest ^ word);
    }
    return input;
}
struct CycleResult {
    std::uint64_t checksum = 0;
    std::array<std::uint64_t, 4> wall {}, cpu {};
};
template <typename Map>
[[gnu::noinline]] CycleResult Cycle(const std::vector<Row>& rows) {
    Memory memory;
    Map map(&memory);
    CycleResult result;
    for (std::size_t phase = 0; phase < 4; ++phase) {
        auto cpu = CpuNanoseconds();
        auto start = Clock::now();
        for (std::size_t i = phase * rows.size() / 4; i < (phase + 1) * rows.size() / 4; ++i)
            result.checksum += map.Add(rows[i]);
        auto end = Clock::now();
        result.cpu[phase] = CpuNanoseconds() - cpu;
        result.wall[phase] =
                std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
    }
    return result;
}
struct Diagnostic {
    Memory memory;
    Work work;
    std::size_t size = 0, capacity = 0, live_bytes = 0;
    std::array<std::size_t, 4> new_groups {}, rehashes {};
};
template <typename Map, std::size_t Bytes>
Diagnostic Verify(const Input<Bytes>& input) {
    Diagnostic result;
    {
        Map map(&result.memory);
        std::uint64_t checksum = 0;
        for (std::size_t phase = 0; phase < 4; ++phase) {
            auto before = map.Size();
            auto rehashes = map.GetWork().rehashes;
            for (std::size_t i = phase * input.rows.size() / 4;
                 i < (phase + 1) * input.rows.size() / 4; ++i)
                checksum += map.Add(input.rows[i]);
            result.new_groups[phase] = map.Size() - before;
            result.rehashes[phase] = map.GetWork().rehashes - rehashes;
        }
        if (checksum != input.checksum || map.Size() != input.groups.size())
            throw std::runtime_error("aggregate stream/group count mismatch");
        for (const auto& [key, expected] : input.groups) {
            auto state = map.Find(key);
            if (!state || *state != expected) throw std::runtime_error("full histogram mismatch");
        }
        result.work = map.GetWork();
        result.size = map.Size();
        result.capacity = map.Capacity();
        result.live_bytes = result.memory.live;
    }
    if (result.memory.live) throw std::runtime_error("state allocator leaked");
    return result;
}

template <typename TimedMap, typename CheckedMap, std::size_t Bytes>
void Run(const Config& c, const Input<Bytes>& input) {
    auto diagnostic = Verify<CheckedMap>(input);
    auto map_bytes = sizeof(TimedMap) + diagnostic.live_bytes;
    for (int warmup = 0; warmup < 2; ++warmup) {
        auto result = Cycle<TimedMap>(input.rows);
        if (result.checksum != input.checksum) throw std::runtime_error("warmup checksum");
        Consume(result.checksum);
    }
    for (int sample = 0; sample < c.repeat; ++sample) {
        std::array<std::uint64_t, 4> phase_wall {}, phase_cpu {};
        std::uint64_t checksum = 0;
        std::size_t passes = 0;
        auto cpu_start = CpuNanoseconds();
        auto start = Clock::now(), end = start;
        do {
            auto result = Cycle<TimedMap>(input.rows);
            Consume(result.checksum);
            checksum += result.checksum;
            for (std::size_t phase = 0; phase < 4; ++phase) {
                phase_wall[phase] += result.wall[phase];
                phase_cpu[phase] += result.cpu[phase];
            }
            ++passes;
            end = Clock::now();
        } while (std::chrono::duration<double, std::milli>(end - start).count() < c.batch_ms);
        auto cpu_ns = CpuNanoseconds() - cpu_start;
        auto elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
        if (checksum != input.checksum * passes) throw std::runtime_error("timed checksum");
        auto operations = passes * input.rows.size();
        std::cout << std::setprecision(12) << "state-build," << c.name << ",uint64," << c.n << ','
                  << c.method << ",0," << c.distribution << ",0.75,"
                  << double(diagnostic.size) / diagnostic.capacity << ',' << c.seed << ',' << sample
                  << ',' << operations << ',' << elapsed << ',' << double(elapsed) / operations
                  << ',' << checksum << ',' << input.trace << ',' << map_bytes << ','
                  << input.rows.size() * 8 << ',' << diagnostic.capacity << ",,,,state-layout/"
                  << c.method << ',' << diagnostic.size << ',' << input.null_rows << ','
                  << double(cpu_ns) / operations << ',' << c.ndv << ',' << c.null_percent << ','
                  << Bytes << ',' << input.digest << ','
                  << diagnostic.memory.peak + sizeof(TimedMap) << ','
                  << diagnostic.memory.allocations << ',' << diagnostic.memory.requested << ','
                  << diagnostic.work.initializations << ',' << diagnostic.work.initialized_bytes
                  << ',' << diagnostic.work.relocated_bytes << ',' << diagnostic.work.rehashes;
        for (std::size_t phase = 0; phase < 4; ++phase)
            std::cout << ',' << double(phase_wall[phase]) / (operations / 4) << ','
                      << double(phase_cpu[phase]) / (operations / 4) << ','
                      << diagnostic.new_groups[phase] << ',' << diagnostic.rehashes[phase];
        std::cout << '\n';
    }
}
template <std::size_t Bytes>
void Dispatch(const Config& c) {
    auto input = MakeInput<Bytes>(c);
    if (c.method == "std")
        Run<StdAggregate<Bytes, false>, StdAggregate<Bytes, false, true>>(c, input);
    else if (c.method == "std-eager")
        Run<StdAggregate<Bytes, true>, StdAggregate<Bytes, true, true>>(c, input);
    else if (c.method == "inline")
        Run<InlineAggregate<Bytes>, InlineAggregate<Bytes, true>>(c, input);
    else
        Run<ArenaAggregate<Bytes>, ArenaAggregate<Bytes, true>>(c, input);
}
} // namespace
} // namespace hashmap_lab::states

int main(int argc, char** argv) {
    try {
        auto config = hashmap_lab::states::Parse(argc, argv);
        std::cout << "mode,case_name,key_type,n,method,hit,distribution,target_load,actual_load,"
                     "seed,sample,operations,elapsed_ns,ns_per_op,checksum,trace_hash,map_bytes,"
                     "key_payload_bytes,capacity,mean_probes,mean_comparisons,max_probes,algorithm,"
                     "ndv,null_rows,cpu_ns_per_op,ndv_config,null_percent,state_bytes,state_digest,"
                     "peak_map_bytes,allocations,allocated_bytes,state_init_count,state_init_bytes,"
                     "state_relocated_bytes,rehashes";
        for (int phase = 1; phase <= 4; ++phase)
            std::cout << ",phase" << phase << "_ns_per_op,phase" << phase << "_cpu_ns_per_op,phase"
                      << phase << "_new_groups,phase" << phase << "_rehashes";
        std::cout << '\n';
        if (config.state_bytes == 16)
            hashmap_lab::states::Dispatch<16>(config);
        else if (config.state_bytes == 256)
            hashmap_lab::states::Dispatch<256>(config);
        else
            hashmap_lab::states::Dispatch<4096>(config);
    } catch (const std::exception& error) {
        std::cerr << "hashmap_states: " << error.what() << '\n';
        return 1;
    }
}
