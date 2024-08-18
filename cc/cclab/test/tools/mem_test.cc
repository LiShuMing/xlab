#include <stdio.h>
#include <time.h>
#include <x86intrin.h>  // rdtsc 指令
#include <stdio.h>
#include <stdlib.h>
#include <cstring>

#define ALLOC_SIZE 1024 * 1 

#define ITERATIONS 10

int main() {
    struct timespec ts;
    unsigned long long start, end;

    start = __rdtsc();  // 读取 CPU 时间戳
    for (int i = 0; i < ITERATIONS; i++) {
        void *ptr = malloc(ALLOC_SIZE);
        if (!ptr) {
            printf("Memory allocation failed at iteration %d\n", i);
            return 1;
        }
        //printf("Allocated 100MB, iteration: %d\n", i);
        memset(ptr, 1, ALLOC_SIZE);
        free(ptr);

        clock_gettime(CLOCK_MONOTONIC, &ts);
    }
    end = __rdtsc();

    double avg_cycles = (end - start) / (double)ITERATIONS;
    printf("Average mem clock_gettime() cycles: %.2f\n", avg_cycles);

    return 0;
}