#include <immintrin.h>

#include <cstdint>
#include <iostream>
#include <vector>

// Objective: Find indices of elements equal to 10 and process them.
void filter_elements(const uint8_t* data, size_t size) {
    // Load target value into all 32 lanes
    __m256i target = _mm256_set1_epi8(10);

    for (size_t i = 0; i < size; i += 32) {
        // 1. Load 32 bytes from memory
        __m256i chunk = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(data + i));

        // 2. Compare: returns 0xFF where equal, 0x00 otherwise
        __m256i mask_vec = _mm256_cmpeq_epi8(chunk, target);

        // 3. Movemask: Compress 32 bytes into 32 bits in a GPR (General Purpose Register)
        uint32_t mask = _mm256_movemask_epi8(mask_vec);

        // 4. Efficiency: If mask is 0, no element matches in this batch of 32
        if (mask == 0) continue;

        // 5. Optimization: Use trailing zero count (TZC) to find set bits quickly
        while (mask != 0) {
            int index = __builtin_ctz(mask); // Find the first '1' bit
            // Process data[i + index]...
            mask &= (mask - 1); // Clear the lowest set bit
        }
    }
}

int main() {
    cout << __builtin_cpu_supports("sse") << endl;
    cout << __builtin_cpu_supports("sse2") << endl;
    cout << __builtin_cpu_supports("avx") << endl;
    cout << __builtin_cpu_supports("avx2") << endl;
    cout << __builtin_cpu_supports("avx512f") << endl;

    return 0;
}