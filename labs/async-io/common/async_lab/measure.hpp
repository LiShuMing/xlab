#pragma once
#include <sys/resource.h>

#include <algorithm>
#include <array>
#include <bit>
#include <chrono>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <string_view>

namespace async_lab {
inline uint64_t NowNs() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
                   std::chrono::steady_clock::now().time_since_epoch())
            .count();
}
// Upper-bound quantiles: eight subdivisions per power of two, <=12.5% bin error.
class Histogram {
public:
    void Add(uint64_t ns) {
        ns = std::max<uint64_t>(ns, 8);
        const unsigned exponent = std::bit_width(ns) - 1;
        const uint64_t base = uint64_t {1} << exponent;
        ++bins_.at(exponent * 8 + (ns - base) / (base / 8));
        ++count_;
    }
    uint64_t Quantile(double q) const {
        if (!count_) return 0;
        const uint64_t rank = std::max<uint64_t>(1, uint64_t(q * count_ + 0.999));
        uint64_t cumulative = 0;
        for (size_t i = 0; i < bins_.size(); ++i) {
            cumulative += bins_[i];
            if (cumulative >= rank) {
                const uint64_t base = uint64_t {1} << (i / 8);
                return base + (i % 8 + 1) * (base / 8);
            }
        }
        return 0;
    }
    uint64_t count() const { return count_; }

private:
    std::array<uint64_t, 512> bins_ {};
    uint64_t count_ = 0;
};
inline uint64_t CpuNs(const rusage& u) {
    return (uint64_t(u.ru_utime.tv_sec) + u.ru_stime.tv_sec) * 1000000000ULL +
           (uint64_t(u.ru_utime.tv_usec) + u.ru_stime.tv_usec) * 1000;
}
inline rusage Usage() {
    rusage result {};
    if (getrusage(RUSAGE_SELF, &result)) throw std::runtime_error("getrusage failed");
    return result;
}
inline void Require(bool condition, std::string_view message) {
    if (!condition) throw std::runtime_error(std::string(message));
}
} // namespace async_lab
