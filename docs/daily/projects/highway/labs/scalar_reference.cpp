#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <limits>
#include <span>
#include <stdexcept>
#include <vector>

// Reference contract: at most one million int32_t values; strict greater-than.
std::int64_t SelectSum(std::span<const std::int32_t> input, std::int32_t threshold) {
    if (input.size() > 1'000'000) {
        throw std::length_error("reference input exceeds the proved sum bound");
    }
    std::int64_t sum = 0;
    for (std::int32_t value : input) {
        if (value > threshold) {
            sum += static_cast<std::int64_t>(value);
        }
    }
    return sum;
}

int main() {
    constexpr auto low = std::numeric_limits<std::int32_t>::min();
    constexpr auto high = std::numeric_limits<std::int32_t>::max();
    const std::array<std::int32_t, 5> input{low, -1, 0, 1, high};
    assert(SelectSum({}, 0) == 0);
    assert(SelectSum(input, 0) == 2'147'483'648LL);
    assert(SelectSum(input, high) == 0);
    assert(SelectSum(input, low) == 2'147'483'647LL);
    const std::vector<std::int32_t> largest(1'000'000, high);
    assert(SelectSum(largest, 0) == 2'147'483'647'000'000LL);
    const std::vector<std::int32_t> too_large(1'000'001, 0);
    bool rejected = false;
    try {
        static_cast<void>(SelectSum(too_large, 0));
    } catch (const std::length_error&) {
        rejected = true;
    }
    assert(rejected);
    std::cout << "scalar reference: boundary checks passed\n";
}
