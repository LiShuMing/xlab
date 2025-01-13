#include <gtest/gtest.h>

#include <atomic>
#include <cstring>
#include <functional>
#include <iostream>
#include <list>
#include <map>
#include <queue>
#include <shared_mutex>
#include <random>  
#include <stack>
#include <string>
#include <vector>
#include <stdio.h>

#ifdef __AVX2__
#include <emmintrin.h>
#include <immintrin.h>
#endif

#include "utils/defer.h"

using namespace std;

namespace test {

// x86 and x86-64 can perform unaligned loads/stores directly;
// modern PowerPC hardware can also do unaligned integer loads and stores;
// but note: the FPU still sends unaligned loads and stores to a trap handler!

#define UNALIGNED_LOAD16(_p) (*reinterpret_cast<const uint16_t *>(_p))
#define UNALIGNED_LOAD32(_p) (*reinterpret_cast<const uint32_t *>(_p))
#define UNALIGNED_LOAD64(_p) (*reinterpret_cast<const uint64_t *>(_p))

#define UNALIGNED_STORE16(_p, _val) (*reinterpret_cast<uint16_t *>(_p) = (_val))
#define UNALIGNED_STORE32(_p, _val) (*reinterpret_cast<uint32_t *>(_p) = (_val))
#define UNALIGNED_STORE64(_p, _val) (*reinterpret_cast<uint64_t *>(_p) = (_val))


} // namespace test

// Basic Test
class SIMDTest : public testing::Test {};

template<typename T>
void print_vector(const std::string& prefix, const std::vector<T>& vec) {
    printf("%s:", prefix.c_str());
    int sz = vec.size();
    for (int i = sz; i >= 0; i--) {
        if ((i + 1) % 4 == 0) {
            printf(" | ");
        }
        printf("%02X ", vec[i]);
    }
    printf("\n");
}
#ifdef __AVX2__

void print_m128i(const std::string& prefix, __m128i value) {
    uint8_t result[16];
    _mm_storeu_si128((__m128i*)result, value);
    // print m128 from high to low
    printf("%s:", prefix.c_str());
    for (int i = 15; i >= 0; i--) {
        if ((i + 1) % 4 == 0) {
            printf(" | ");
        }
        printf("%02X ", result[i]);
    }
    printf("\n");
}

void print_m256i(const std::string& prefix, __m256i value) {
    uint8_t result[32];
    _mm256_storeu_si256((__m256i*)result, value);
    // print m256 from high to low
    printf("%s:", prefix.c_str());
    for (int i = 31; i >= 0; i--) {
        if ((i + 1) % 4 == 0) {
            printf(" | ");
        }
        printf("%02X ", result[i]);
    }
    printf("\n");
}

TEST_F(SIMDTest, Test1) {
    __m128i value = _mm_set_epi8(0xAB, 0xCD, 0xEF, 0x12, 0x34, 0x56, 0x78, 0x90,
                                 0xAB, 0xCD, 0xEF, 0x12, 0x34, 0x56, 0x78, 0x90);
    print_m128i("value", value);
    // value:AB CD EF 12 34 56 78 90 AB CD EF 12 34 56 78 90

    __m128i mask = _mm_set1_epi8(0xF);
    print_m128i("mask", mask);
    // mask:0F 0F 0F 0F 0F 0F 0F 0F 0F 0F 0F 0F 0F 0F 0F 0F

    // shift right 4 bits
    __m128i result = _mm_srli_epi64(value, 4);
    print_m128i("step1:", result);
    // step1::0A BC DE F1 23 45 67 89 0A BC DE F1 23 45 67 89

    result = _mm_unpacklo_epi8(result, value);
    print_m128i("step2:", result);
    // value: AB CD EF 12 34 56 78 90 | AB CD EF 12 34 56 78 90
    // step1: 0A BC DE F1 23 45 67 89 | 0A BC DE F1 23 45 67 89
    // step2: AB 0A CD BC EF DE 12 F1 | 34 23 56 45 78 67 90 89

    result = _mm_and_si128(result, mask);
    print_m128i("step3:", result);
    // step2: AB 0A CD BC EF DE 12 F1 | 34 23 56 45 78 67 90 89
    // mask : 0F 0F 0F 0F 0F 0F 0F 0F 0F 0F 0F 0F 0F 0F 0F 0F
    // step3: 0B 0A 0D 0C 0F 0E 02 01 04 03 06 05 08 07 00 09
}

template <typename T, bool left_const = false, bool right_const = false, std::enable_if_t<sizeof(T) == 1, int> = 1>
inline void avx2_select_if(uint8_t*& selector, T*& dst, const T*& a, const T*& b, int size) {
    const T* dst_end = dst + size;
    while (dst + 32 < dst_end) {
        __m256i loaded_mask = _mm256_loadu_si256(reinterpret_cast<__m256i*>(selector));
        loaded_mask = _mm256_cmpeq_epi8(loaded_mask, _mm256_setzero_si256());
        loaded_mask = ~loaded_mask;
        __m256i vec_a;
        __m256i vec_b;
        if constexpr (!left_const) {
            vec_a = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(a));
        } else {
            vec_a = _mm256_set1_epi8(*a);
        }
        if constexpr (!right_const) {
            vec_b = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(b));
        } else {
            vec_b = _mm256_set1_epi8(*b);
        }
        __m256i res = _mm256_blendv_epi8(vec_b, vec_a, loaded_mask);
        _mm256_storeu_si256(reinterpret_cast<__m256i*>(dst), res);
        dst += 32;
        selector += 32;
        if (!left_const) {
            a += 32;
        }
        if (!right_const) {
            b += 32;
        }
    }
}

// _mm256_blend_epi32
template <typename T, std::enable_if_t<sizeof(T) == 4, int> = 4>
inline void avx2_select_if(uint8_t*& selector, T*& dst, const T*& a, const T*& b, int size) {
    const T* dst_end = dst + size;

    while (dst + 8 < dst_end) {
        uint64_t value = UNALIGNED_LOAD64(selector);
        // convert 8 * 8 bits to v
        __m128i v = _mm_set1_epi64x(value);
        print_m128i("v              :", v);
        __m256i loaded_mask = _mm256_cvtepi8_epi32(v);
        print_m256i("loaded_mask    :", loaded_mask);
        // compare to 0
        __m256i cond = _mm256_cmpeq_epi8(loaded_mask, _mm256_setzero_si256());
        print_m256i("cond           :", cond);
        cond = ~cond;
        print_m256i("cond           :", cond);

        // Mask Shuffle
        // convert 0x 10 00 00 00 14 00 00 00
        // to      0x 00 00 00 10 00 00 00 14
        __m256i mask = _mm256_set_epi8(0x0c, 0xff, 0xff, 0xff, 0x08, 0xff, 0xff, 0xff, 0x04, 0xff, 0xff, 0xff, 0x00,
                                       0xff, 0xff, 0xff, 0x0c, 0xff, 0xff, 0xff, 0x08, 0xff, 0xff, 0xff, 0x04, 0xff,
                                       0xff, 0xff, 0x00, 0xff, 0xff, 0xff);
        print_m256i("mask           :", mask);
        cond = _mm256_shuffle_epi8(cond, mask);
        print_m256i("cond           :", cond);

        __m256i vec_a = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(a));
        __m256i vec_b = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(b));
        print_m256i("vec_a          :", vec_a);
        print_m256i("vec_b          :", vec_b);
        __m256 res =
                _mm256_blendv_ps(_mm256_castsi256_ps(vec_b), _mm256_castsi256_ps(vec_a), _mm256_castsi256_ps(cond));
        // print_m256i("res            :", res);
        _mm256_storeu_si256(reinterpret_cast<__m256i*>(dst), _mm256_castps_si256(res));

        dst += 8;
        selector += 8;
        a += 8;
        b += 8;
    }
}

TEST_F(SIMDTest, TestSelectIf1) {
    size_t num_elements = 16;
    std::vector<uint8_t> selector(num_elements);
    std::vector<int32_t> a(num_elements);
    std::vector<int32_t> b(num_elements);
    //std::vector<int32_t> dst_simd(num_elements);
    //std::vector<int32_t> dst_non_simd(num_elements);
    std::mt19937 rnd(42); 
    std::uniform_int_distribution<> dist(0, 1);
    for (int i = 0; i < num_elements; ++i) {
        selector[i] = dist(rnd);
        a[i] = static_cast<int32_t>(i);
        b[i] = static_cast<int32_t>(num_elements - i);
    }
    print_vector("selector:", selector);
    print_vector("a       :", a);
    print_vector("b       :", b);
    std::vector<int32_t> ans(num_elements);
    auto* selector_ptr = selector.data();
    auto* ans_ptr = ans.data();
    const auto* a_ptr = a.data();
    const auto* b_ptr = b.data();
    avx2_select_if<int32_t>(selector_ptr, ans_ptr, a_ptr, b_ptr, num_elements);
    print_vector("ans     :", ans);
}
#endif