#ifndef UTILS_H
#define UTILS_H

#include <chrono>
#include <iostream>

namespace llvm_jit {

class Timer {
public:
    Timer() : start_time(std::chrono::high_resolution_clock::now()) {}

    double elapsed_ns() const {
        auto end_time = std::chrono::high_resolution_clock::now();
        return std::chrono::duration<double, std::nano>(end_time - start_time).count();
    }

    double elapsed_us() const { return elapsed_ns() / 1000.0; }
    double elapsed_ms() const { return elapsed_us() / 1000.0; }
    double elapsed_s() const { return elapsed_ms() / 1000.0; }

private:
    std::chrono::high_resolution_clock::time_point start_time;
};

inline void warmup(size_t iterations = 10000) {
    volatile double sum = 0.0;
    for (size_t i = 0; i < iterations; ++i) {
        sum += static_cast<double>(i) * 0.001;
    }
}

} // namespace llvm_jit

#endif // UTILS_H
