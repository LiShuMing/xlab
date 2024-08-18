#include <pthread.h>

#ifdef __linux__
#include <sched.h>
#endif

#include <chrono>
#include <iostream>

int main(int argc, char* argv[]) {
    pthread_t thread = pthread_self();
    
#ifdef __linux__
    for (int cpu_id = 0; cpu_id < CPU_SETSIZE; cpu_id++) {
        cpu_set_t cpuset;
        CPU_ZERO(&cpuset);
        CPU_SET(cpu_id, &cpuset);

        if (pthread_setaffinity_np(thread, sizeof(cpu_set_t), &cpuset) != 0) {
            return 1;
        }

        if (pthread_getaffinity_np(thread, sizeof(cpu_set_t), &cpuset) != 0) {
            return 1;
        }
        for (int i = 0; i < CPU_SETSIZE; i++) {
            if (CPU_ISSET(i, &cpuset) && cpu_id != i) {
                return 1;
            }
        }

        std::cout << "Testing cpu(" << cpu_id << ")" << std::endl;
        // volatile int64_t cnt = 0;
        int64_t cnt = 0;
        auto start = std::chrono::steady_clock::now();

        /*
         * !!! Please use `-O0` to compile this source file, otherwise the following loop maybe optimized out !!!
         */
        // while (cnt <= 1_000_000_000L) {
        while (cnt <= 1000000000L) {
            __asm__ volatile("" : "+r"(cnt));  // 空汇编指令，阻止优化
            cnt++;
        }
        auto end = std::chrono::steady_clock::now();

        std::cout << "cost:"
                  << std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count()
                  << "(ms), result:" << cnt << std::endl;
    }
#else
    // macOS doesn't support CPU affinity, run benchmark on default core
    std::cout << "Testing on default CPU core (CPU affinity not supported on macOS)" << std::endl;
    int64_t cnt = 0;
    auto start = std::chrono::steady_clock::now();

    /*
     * !!! Please use `-O0` to compile this source file, otherwise the following loop maybe optimized out !!!
     */
    while (cnt <= 1000000000L) {
        __asm__ volatile("" : "+r"(cnt));  // 空汇编指令，阻止优化
        cnt++;
    }
    auto end = std::chrono::steady_clock::now();

    std::cout << "cost:"
              << std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count()
              << "(ms), result:" << cnt << std::endl;
#endif

    return 0;
}