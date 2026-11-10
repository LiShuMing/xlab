#include <time.h>

#include <array>
#include <chrono>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <string>
#include <type_traits>

#include "policies.h"
#include "reference_lru.h"
#include "workloads.h"

namespace cache_lab {
namespace {
using Clock = std::chrono::steady_clock;
struct Config {
    std::string algorithm = "lru", workload = "scan_mix";
    std::size_t capacity = 512, count = 65536, window_size = 2048;
    unsigned window_percent = 1, protected_percent = 80, aging_factor = 10, repeats = 3;
    std::uint64_t seed = 42;
    double batch_ms = 20;
};
Config Parse(int argc, char** argv) {
    Config c;
    for (int i = 1; i < argc; i += 2) {
        if (i + 1 == argc) throw std::invalid_argument("option needs value");
        std::string option = argv[i], value = argv[i + 1];
        auto number = [&]() {
            std::size_t used;
            if (value.empty() || value[0] == '-') throw std::invalid_argument("negative number");
            auto n = std::stoull(value, &used);
            if (used != value.size()) throw std::invalid_argument("invalid integer");
            return n;
        };
        if (option == "--algorithm")
            c.algorithm = value;
        else if (option == "--workload")
            c.workload = value;
        else if (option == "--capacity")
            c.capacity = number();
        else if (option == "--count")
            c.count = number();
        else if (option == "--seed")
            c.seed = number();
        else if (option == "--window-size")
            c.window_size = number();
        else if (option == "--window-percent" || option == "--protected-percent" ||
                 option == "--aging-factor" || option == "--repeats") {
            auto n = number();
            if (n > 100) throw std::invalid_argument("parameter exceeds 100");
            if (option == "--window-percent")
                c.window_percent = n;
            else if (option == "--protected-percent")
                c.protected_percent = n;
            else if (option == "--aging-factor")
                c.aging_factor = n;
            else
                c.repeats = n;
        } else if (option == "--batch-ms") {
            std::size_t used;
            c.batch_ms = std::stod(value, &used);
            if (used != value.size()) throw std::invalid_argument("invalid batch duration");
        } else
            throw std::invalid_argument("unknown option " + option);
    }
    if (!c.count || c.count > 1048576 || c.count % 4 || c.capacity > 65536 || !c.window_size ||
        c.window_size > c.count || !c.repeats || c.repeats > 20 || !std::isfinite(c.batch_ms) ||
        c.batch_ms <= 0 || c.batch_ms > 10000 || !c.window_percent || c.window_percent > 50 ||
        c.protected_percent > 95 || !c.aging_factor)
        throw std::invalid_argument("invalid dimensions or timing");
    return c;
}
std::uint64_t CpuNs() {
    timespec t {};
    if (clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &t))
        throw std::runtime_error("CPU clock unavailable");
    return std::uint64_t(t.tv_sec) * 1000000000ULL + t.tv_nsec;
}
inline std::uint64_t Nanoseconds(Clock::duration duration) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(duration).count();
}
inline void Consume(std::uint64_t value) {
#if defined(__GNUC__) || defined(__clang__)
    asm volatile("" : : "g"(value) : "memory");
#else
#error "compiler barrier required"
#endif
}
template <typename Policy>
Policy Make(const Config& c) {
    if constexpr (std::is_same_v<Policy, WTinyLfu>)
        return Policy(c.capacity, c.window_percent, c.protected_percent, c.aging_factor);
    else if constexpr (std::is_same_v<Policy, Slru>)
        return Policy(c.capacity, c.protected_percent);
    else
        return Policy(c.capacity);
}
struct Replay {
    std::uint64_t hits = 0, digest = 0;
};
template <typename Policy>
[[gnu::noinline]] Replay RunTrace(const Config& c, const std::vector<Request>& trace) {
    auto policy = Make<Policy>(c);
    Replay replay;
    for (const auto& request : trace) {
        bool hit = policy.Access(request.key);
        replay.hits += hit;
        replay.digest = Mix(replay.digest ^ request.key ^ hit);
    }
    return replay;
}
struct Window {
    std::size_t begin = 0, end = 0;
    std::uint64_t hits = 0, points = 0, point_hits = 0, scans = 0, scan_hits = 0;
    std::uint64_t wall_ns = 0;
    Events events;
    Layout layout;
};
Events Difference(Events after, Events before) {
    return {after.admissions - before.admissions, after.evictions - before.evictions,
            after.rejections - before.rejections, after.promotions - before.promotions,
            after.demotions - before.demotions,   after.resets - before.resets,
            after.ghost_hits - before.ghost_hits};
}
struct Latency {
    std::vector<std::uint64_t> times;
    std::array<std::uint64_t, 64> histogram {};
    void Add(std::uint64_t value) {
        times.push_back(value);
        std::size_t bin = 0;
        for (auto v = value; v > 1 && bin < 63; v >>= 1) ++bin;
        ++histogram[bin];
    }
    void Print() {
        std::sort(times.begin(), times.end());
        auto quantile = [&](double p) {
            return times[std::size_t(std::ceil(p * times.size())) - 1];
        };
        std::cout << "{\"count\":" << times.size();
        if (times.empty())
            std::cout << ",\"p50\":null,\"p95\":null,\"p99\":null,\"maximum\":null";
        else
            std::cout << ",\"p50\":" << quantile(.5) << ",\"p95\":" << quantile(.95)
                      << ",\"p99\":" << quantile(.99) << ",\"maximum\":" << times.back();
        std::cout << ",\"histogram\":[";
        for (std::size_t i = 0; i < histogram.size(); ++i) {
            if (i) std::cout << ',';
            std::cout << histogram[i];
        }
        std::cout << "]}";
    }
};
void PrintEvents(Events e) {
    std::cout << "{\"admissions\":" << e.admissions << ",\"evictions\":" << e.evictions
              << ",\"rejections\":" << e.rejections << ",\"promotions\":" << e.promotions
              << ",\"demotions\":" << e.demotions << ",\"sketch_resets\":" << e.resets
              << ",\"ghost_hits\":" << e.ghost_hits << '}';
}
void PrintLayout(Layout l) {
    std::cout << "{\"resident\":" << l.resident << ",\"history\":" << l.history
              << ",\"sketch_bytes\":" << l.sketch_bytes << ",\"window\":" << l.window
              << ",\"probation\":" << l.probation << ",\"protected\":" << l.protected_size
              << ",\"arc_target\":" << l.arc_target << '}';
}
template <typename Policy>
void Benchmark(const Config& c) {
    auto trace = MakeTrace(c.workload, c.count, c.seed);
    std::vector<Window> windows;
    std::array<Latency, 5> latency;
    std::array<Latency, 4> phase_latency;
    Replay expected;
    {
        auto policy = Make<Policy>(c);
        Events previous;
        for (std::size_t begin = 0; begin < trace.size(); begin += c.window_size) {
            Window w;
            w.begin = begin;
            w.end = std::min(trace.size(), begin + c.window_size);
            for (auto i = begin; i < w.end; ++i) {
                auto start = Clock::now();
                bool hit = policy.Access(trace[i].key);
                auto elapsed = Nanoseconds(Clock::now() - start);
                latency[0].Add(elapsed);
                latency[trace[i].scan ? 2 : 1].Add(elapsed);
                latency[hit ? 3 : 4].Add(elapsed);
                phase_latency[i * 4 / trace.size()].Add(elapsed);
                w.wall_ns += elapsed;
                w.hits += hit;
                if (trace[i].scan) {
                    ++w.scans;
                    w.scan_hits += hit;
                } else {
                    ++w.points;
                    w.point_hits += hit;
                }
                expected.hits += hit;
                expected.digest = Mix(expected.digest ^ trace[i].key ^ hit);
            }
            auto events = policy.GetEvents();
            w.events = Difference(events, previous);
            previous = events;
            w.layout = policy.GetLayout();
            if (w.layout.resident > c.capacity || w.layout.history > c.capacity)
                throw std::runtime_error("capacity invariant violated");
            windows.push_back(w);
        }
    }
    for (int warm = 0; warm < 2; ++warm) {
        auto replay = RunTrace<Policy>(c, trace);
        if (replay.digest != expected.digest || replay.hits != expected.hits)
            throw std::runtime_error("warmup mismatch");
        Consume(replay.digest);
    }
    struct Sample {
        std::uint64_t operations, elapsed, cpu, hits, digest;
    };
    std::vector<Sample> samples;
    for (unsigned repeat = 0; repeat < c.repeats; ++repeat) {
        auto cpu = CpuNs();
        auto start = Clock::now(), end = start;
        std::uint64_t passes = 0, hits = 0, digest = 0;
        do {
            auto replay = RunTrace<Policy>(c, trace);
            Consume(replay.digest);
            hits += replay.hits;
            digest += replay.digest;
            ++passes;
            end = Clock::now();
        } while (std::chrono::duration<double, std::milli>(end - start).count() < c.batch_ms);
        auto cpu_elapsed = CpuNs() - cpu;
        if (hits != expected.hits * passes || digest != expected.digest * passes)
            throw std::runtime_error("timed replay mismatch");
        samples.push_back(
                {passes * trace.size(), Nanoseconds(end - start), cpu_elapsed, hits, digest});
    }
    Latency clock_floor;
    for (int i = 0; i < 4096; ++i) {
        auto start = Clock::now();
        auto end = Clock::now();
        clock_floor.Add(Nanoseconds(end - start));
    }
    std::cout << std::setprecision(12) << "{\"algorithm\":\"" << c.algorithm << "\",\"workload\":\""
              << c.workload << "\",\"capacity\":" << c.capacity << ",\"count\":" << c.count
              << ",\"seed\":" << c.seed << ",\"window_percent\":" << c.window_percent
              << ",\"protected_percent\":" << c.protected_percent
              << ",\"aging_factor\":" << c.aging_factor << ",\"window_size\":" << c.window_size
              << ",\"trace_hash\":\"" << TraceHash(trace) << "\",\"hit_digest\":\""
              << expected.digest << "\",\"hits\":" << expected.hits << ",\"latency\":{\"all\":";
    latency[0].Print();
    std::cout << ",\"point\":";
    latency[1].Print();
    std::cout << ",\"scan\":";
    latency[2].Print();
    std::cout << ",\"hit\":";
    latency[3].Print();
    std::cout << ",\"miss\":";
    latency[4].Print();
    std::cout << "},\"clock_floor\":";
    clock_floor.Print();
    std::cout << ",\"phase_latency\":[";
    for (std::size_t i = 0; i < 4; ++i) {
        if (i) std::cout << ',';
        phase_latency[i].Print();
    }
    std::cout << "],\"windows\":[";
    for (std::size_t i = 0; i < windows.size(); ++i) {
        if (i) std::cout << ',';
        const auto& w = windows[i];
        std::cout << "{\"begin\":" << w.begin << ",\"end\":" << w.end << ",\"hits\":" << w.hits
                  << ",\"points\":" << w.points << ",\"point_hits\":" << w.point_hits
                  << ",\"scans\":" << w.scans << ",\"scan_hits\":" << w.scan_hits
                  << ",\"policy_wall_ns\":" << w.wall_ns << ",\"events\":";
        PrintEvents(w.events);
        std::cout << ",\"layout\":";
        PrintLayout(w.layout);
        std::cout << '}';
    }
    std::cout << "],\"samples\":[";
    for (std::size_t i = 0; i < samples.size(); ++i) {
        if (i) std::cout << ',';
        const auto& s = samples[i];
        std::cout << "{\"repeat\":" << i << ",\"operations\":" << s.operations
                  << ",\"elapsed_ns\":" << s.elapsed << ",\"cpu_ns\":" << s.cpu
                  << ",\"ns_per_op\":" << double(s.elapsed) / s.operations
                  << ",\"cpu_ns_per_op\":" << double(s.cpu) / s.operations << ",\"hits\":" << s.hits
                  << ",\"hit_digest\":\"" << s.digest << "\"}";
    }
    std::cout << "]}\n";
}
} // namespace
} // namespace cache_lab

int main(int argc, char** argv) {
    using namespace cache_lab;
    try {
        auto c = Parse(argc, argv);
        if (c.algorithm == "fifo")
            Benchmark<Fifo>(c);
        else if (c.algorithm == "lru")
            Benchmark<Lru>(c);
        else if (c.algorithm == "lfu")
            Benchmark<Lfu>(c);
        else if (c.algorithm == "slru")
            Benchmark<Slru>(c);
        else if (c.algorithm == "wtinylfu")
            Benchmark<WTinyLfu>(c);
        else if (c.algorithm == "arc")
            Benchmark<Arc>(c);
        else if (c.algorithm == "reference-lru")
            Benchmark<ReferenceLru>(c);
        else
            throw std::invalid_argument("unknown or unavailable algorithm");
    } catch (const std::exception& error) {
        std::cerr << "cache_bench: " << error.what() << '\n';
        return 1;
    }
}
