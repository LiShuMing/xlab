
#include <gtest/gtest.h>
#include "common/queue/mpmc_queue.h"

#include <array>
#include <chrono>
#include <iostream>
#include <mutex>
#include <random>
#include <thread>
#include <vector>
#include <xmmintrin.h> // Include for _mm_pause
// #include <intrin.h> // For __rdtsc

using namespace std;

class MpmcQueueTest: public testing::Test {
};

size_t const thread_count = 4;
size_t const batch_size = 1;
size_t const iter_count = 2000000;

bool volatile g_start = 0;

using queue_t = MpmcQueue<int>;

unsigned thread_func(void* ctx) {
    queue_t& queue = *(queue_t*)ctx;
    int data;

    srand((unsigned)time(0) + std::hash<std::thread::id>()(this_thread::get_id()));
    size_t pause = rand() % 1000;

    while (g_start == 0) {
        std::this_thread::yield();
    }

    for (size_t i = 0; i != pause; i += 1) _mm_pause();

    for (int iter = 0; iter != iter_count; ++iter) {
        for (size_t i = 0; i != batch_size; i += 1) {
            while (!queue.enqueue(i)) {
                std::this_thread::yield();
            }
        }
        for (size_t i = 0; i != batch_size; i += 1) {
            while (!queue.dequeue(data)) {
                std::this_thread::yield();
            }
        }
    }

    return 0;
}

TEST_F(MpmcQueueTest, TestBasic) {
   queue_t queue (1024);

   std::thread threads [thread_count];
   for (int i = 0; i != thread_count; ++i) {
       threads[i] = std::thread(&thread_func, &queue);
   }

   std::this_thread::sleep_for(1s);

   uint64_t start = __builtin_ia32_rdtsc();
   g_start = 1;

   for (auto& t : threads) {
       t.join();
   }
   uint64_t end = __builtin_ia32_rdtsc();
   uint64_t time = end - start;
   ///
   /// [----------] 1 test from MpmcQueueTest
   /// [ RUN      ] MpmcQueueTest.TestBasic
   ///cycles/op=267

   std::cout << "cycles/op=" << time / (batch_size * iter_count * 2 * thread_count) << std::endl;
}