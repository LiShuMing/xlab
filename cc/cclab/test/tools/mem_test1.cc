#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <x86intrin.h> 
#include <unistd.h>  
#include <thread>
#include <chrono>

#define ALLOC_SIZE (1024 * 10)
#define ITERATIONS 10000000

long long time_diff_ns(struct timespec start, struct timespec end) {
    return (end.tv_sec - start.tv_sec) * 1000000000LL + (end.tv_nsec - start.tv_nsec);
}

int main() {
    for (int i = 0; i < ITERATIONS; i++) {
        struct timespec ts_start, ts_end;
        unsigned long long start, end;
        long long malloc_time = 0, memset_time = 0, free_time = 0;

        clock_gettime(CLOCK_MONOTONIC, &ts_start);
        void *ptr = malloc(ALLOC_SIZE);
        if (!ptr) {
            printf("Memory allocation failed at iteration %d\n", i);
            return 1;
        }

        memset(ptr, 1, ALLOC_SIZE);
        free(ptr);
        clock_gettime(CLOCK_MONOTONIC, &ts_end);
        malloc_time += time_diff_ns(ts_start, ts_end);

        printf("Average malloc() time: %.2f ns\n", (double)malloc_time);
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
    return 0;
}