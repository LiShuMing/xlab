
#include <gtest/gtest.h>
#include "common/mpmc_queue.h"

#include <array>
#include <chrono>
#include <iostream>
#include <mutex>
#include <random>
#include <thread>
#include <vector>
#include <xmmintrin.h> // Include for _mm_pause
// #include <intrin.h> // For __rdtsc


class SIMDTest: public testing::Test {
};

#ifdef __SSE2__
#include <emmintrin.h>
#include <smmintrin.h>
#include <immintrin.h>
#include <xmmintrin.h>
#include <emmintrin.h>
#include <immintrin.h>

TEST_F(SIMDTest, TestBasic) {
    __m128 src = _mm_set_ps(1.0f, 2.0f, 3.0f, 4.0f);  // 单精度数据

    __m128d low = _mm_cvtps_pd(_mm_movehl_ps(src, src));

    __m128d high = _mm_cvtps_pd(src);
}
#endif