#ifndef CACHE_LAB_WORKLOADS_H_
#define CACHE_LAB_WORKLOADS_H_

#include <cmath>
#include <random>
#include <string>
#include <vector>

#include "policies.h"

namespace cache_lab {
struct Request {
    Key key;
    bool scan;
};
inline std::vector<Request> MakeTrace(const std::string& name, std::size_t count,
                                      std::uint64_t seed) {
    if (name != "uniform" && name != "zipf" && name != "loop" && name != "scan_mix" &&
        name != "interleaved" && name != "hot_shift" && name != "recency_bursts" &&
        name != "one_hit")
        throw std::invalid_argument("unknown workload");
    std::mt19937_64 rng(seed);
    std::vector<double> weights(4096);
    for (std::size_t i = 0; i < weights.size(); ++i) weights[i] = 1.0 / std::pow(i + 1, 1.1);
    std::discrete_distribution<std::size_t> zipf(weights.begin(), weights.end());
    std::vector<Request> trace;
    trace.reserve(count);
    for (std::size_t i = 0; i < count; ++i) {
        auto phase = i * 4 / count;
        Key hot = rng() % 256;
        Request request {hot, false};
        if (name == "uniform")
            request.key = rng() % 4096;
        else if (name == "zipf")
            request.key = zipf(rng);
        else if (name == "loop")
            request = {i % 768, true};
        else if (name == "one_hit")
            request = {1000000000ULL + i, true};
        else if (name == "scan_mix") {
            if ((phase == 1 || phase == 3) && (i % 2304 < 2048))
                request = {1000000000ULL + i, true};
        } else if (name == "interleaved") {
            if (rng() % 100 < 20) request = {1000000000ULL + i, true};
        } else if (name == "hot_shift") {
            request.key = phase * 4096 + hot;
            if (rng() % 100 < 5) request = {1000000000ULL + i, true};
        } else if (name == "recency_bursts") {
            // Each 64-key batch repeats four times, then moves to another region.
            request.key = ((i / 256) % 64) * 64 + i % 64;
        }
        trace.push_back(request);
    }
    return trace;
}
inline std::uint64_t TraceHash(const std::vector<Request>& trace) {
    std::uint64_t result = 14695981039346656037ULL;
    for (const auto& request : trace)
        result = Mix(result ^ request.key ^ (request.scan ? (1ULL << 63) : 0));
    return result;
}
} // namespace cache_lab
#endif
