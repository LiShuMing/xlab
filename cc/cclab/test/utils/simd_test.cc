#include <gtest/gtest.h>

#include <atomic>
#include <cstring>
#include <functional>
#include <iostream>
#include <list>
#include <map>
#include <queue>
#include <shared_mutex>
#include <stack>
#include <string>
#include <vector>
#include <emmintrin.h>
#include <stdio.h>

#include "utils/defer.h"

using namespace std;

namespace test {} // namespace test

// Basic Test
class SIMDTest : public testing::Test {};

void print_m128i(const std::string& prefix, __m128i value) {
    uint8_t result[16];
    _mm_storeu_si128((__m128i*)result, value);
    // print m128 from high to low
    printf("%s:", prefix.c_str());
    for (int i = 15; i >= 0; i--) {
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

TEST_F(SIMDTest, TestSelectIf) {
}


int main(int argc, char **argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}