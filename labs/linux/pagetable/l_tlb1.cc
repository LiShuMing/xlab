/**
 * TLB (Translation Lookaside Buffer) Microbenchmark
 *
 * Measures memory access performance with different strides to demonstrate:
 * 1. TLB pressure at different access patterns
 * 2. Impact of page size (4KB vs 2MB huge pages)
 * 3. Cache vs TLB behavior differences
 *
 * Run with perf to see TLB metrics:
 *   perf stat -e dTLB-load-misses,dTLB-store-misses,cycles,instructions,cache-misses ./bench_tlb
 *
 * Expected results:
 *   - stride=64B: Low TLB miss, cache-friendly
 *   - stride=4KB: High TLB miss (new page each access)
 *   - stride=2MB (with huge pages): Very low TLB miss
 */


// ================================================================================
// TLB Microbenchmark
// ================================================================================
// This benchmark measures memory access performance with different access patterns.
// Run with perf to see detailed TLB metrics:
//   perf stat -e dTLB-load-misses,dTLB-store-misses,cycles,instructions,cache-misses ./bench_tlb

// Expected behavior:
//   - stride=64B:   Low TLB miss, cache-friendly, sequential access pattern
//   - stride=4KB:   HIGH TLB miss (new page each access), cache-friendly
//   - stride=2MB:   Very low TLB miss if using huge pages
//   - random:       High TLB miss + cache miss, worst case

// Key insight: When working set > TLB coverage, performance degrades sharply.
// ================================================================================

// Huge pages available: 0
// Page size: 4096 bytes
// Default huge page size: 2 MB (typically)
// TLB entries: ~64-128 for 4KB pages

// Configuration:
//   Working set size: 1.00 GB
//   Number of accesses: 16777216

// Allocating 1.00 GB...
// Touching pages...

// ================================================================================
// Benchmark Results (4KB Pages)
// ================================================================================

// Running sequential           (sequential):    283.56 ms, throughput:      56.43 MB/s

// Running stride_64B           (stride=    64 bytes):   183.53 ms, throughput:    5579.32 MB/s
// Running stride_4KB           (stride=  4096 bytes):   592.62 ms, throughput:  110586.33 MB/s
// Running stride_2MB           (stride=2097152 bytes):   326.12 ms, throughput: 102891409.47 MB/s

// Random access (1677721 iterations):
// Running random               (random):        219.05 ms, throughput:       7.30 MB/s


//   TLB Analysis for stride=64:
//     Working set: 1.00 GB
//     Pages needed: 262144
//     Accesses per page: 64
//     TLB coverage (64 entries @ 4KB): 256 KB
//     Pages fitting in TLB: ~64
//     Fraction of WS in TLB: 0.024414%

//   TLB Analysis for stride=4096:
//     Working set: 1.00 GB
//     Pages needed: 262144
//     Accesses per page: 1
//     TLB coverage (64 entries @ 4KB): 256 KB
//     Pages fitting in TLB: ~64
//     Fraction of WS in TLB: 0.024414%

//   TLB Analysis for stride=2097152:
//     Working set: 1.00 GB
//     Pages needed: 262144
//     Accesses per page: 0
//     TLB coverage (64 entries @ 4KB): 256 KB
//     Pages fitting in TLB: ~64
//     Fraction of WS in TLB: 0.024414%

// ================================================================================
// Summary and Expected Observations
// ================================================================================

// 1. Stride=64B:
//    - ~64 accesses per page
//    - Low TLB miss rate (reuse same pages)
//    - High cache hit rate (spatial locality)

// 2. Stride=4KB:
//    - 1 access per page
//    - HIGH TLB miss rate (64 entries -> 256KB coverage)
//    - For 1GB working set: 262144 pages, only 64 in TLB = 99.98Successiss
//    - This is the 'cliff' where performance drops sharply

// 3. Stride=2MB:
//    - With 4KB pages: ~512 pages needed, high TLB miss
//    - With 2MB huge pages: ~512 pages, but only 512/64 = 8 entries needed!
//    - TLB miss drops dramatically with huge pages

// 4. Random access:
//    - Worst of both worlds: cache miss + TLB miss
//    - Memory-bound, very slow

// To verify with perf:
//   perf stat -e dTLB-load-misses,dTLB-store-misses ./bench_tlb
//   Compare dTLB-load-misses for stride=64B vs stride=4KB
// ================================================================================

//  Performance counter stats for './l_tlb1':

//         35,262,627      dTLB-load-misses                                            
//          2,348,897      dTLB-store-misses                                           
//      6,655,647,805      cycles                                                      
//      3,329,132,075      instructions              #    0.50  insn per cycle         
//         38,388,090      cache-misses                                                

//        2.080657331 seconds time elapsed

//        1.644362000 seconds user
//        0.436096000 seconds sys

#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <chrono>
#include <new>
#include <random>
#include <sys/mman.h>
#include <unistd.h>

// Configuration
constexpr size_t GB = 1024 * 1024 * 1024;
constexpr size_t MB = 1024 * 1024;
constexpr size_t KB = 1024;

// Default: 1GB working set
constexpr size_t DEFAULT_SIZE = 1 * GB;

// Strides to test
constexpr size_t STRIDES[] = {64, 4096, 2 * MB};

// Number of iterations per test
constexpr int ITERATIONS = 100;

// Prevent compiler from optimizing away the access
__attribute__((noinline)) void do_not_optimize(volatile void* ptr) {
    asm volatile("" : : "r"(ptr) : "memory");
}

/**
 * Memory access with given stride
 * Uses non-temporal stores to avoid cache pollution
 */
template <size_t STRIDE>
void access_with_stride(volatile uint8_t* data, size_t size, size_t num_accesses) {
    uint64_t sum = 0;
    size_t index = 0;

    for (size_t i = 0; i < num_accesses; ++i) {
        // Stride through memory
        index = (i * STRIDE) % size;
        sum += data[index];
        do_not_optimize(&data[index]);
    }

    // Use sum to prevent dead code elimination
    if (sum == UINT64_MAX) {
        printf("Impossible value: %lu\n", sum);
    }
}

/**
 * Sequential access (cache-friendly baseline)
 */
void sequential_access(volatile uint8_t* data, size_t size, size_t num_accesses) {
    uint64_t sum = 0;
    for (size_t i = 0; i < num_accesses; ++i) {
        sum += data[i % size];
        do_not_optimize(&data[i % size]);
    }
    if (sum == UINT64_MAX) {
        printf("Impossible value: %lu\n", sum);
    }
}

/**
 * Random access (cache-unfriendly, TLB-unfriendly)
 */
void random_access(volatile uint8_t* data, size_t size, size_t num_accesses,
                   std::mt19937& rng) {
    std::uniform_int_distribution<size_t> dist(0, size - 1);
    uint64_t sum = 0;

    for (size_t i = 0; i < num_accesses; ++i) {
        size_t index = dist(rng);
        sum += data[index];
        do_not_optimize(&data[index]);
    }
    if (sum == UINT64_MAX) {
        printf("Impossible value: %lu\n", sum);
    }
}

/**
 * Allocate memory with optional huge pages
 */
uint8_t* allocate_memory(size_t size, bool use_huge_pages = false) {
    uint8_t* ptr = nullptr;

    if (use_huge_pages) {
        // Try Transparent Huge Pages first (kernel handles it)
        // Or use madvise to promote to huge pages
        ptr = static_cast<uint8_t*>(
            mmap(nullptr, size, PROT_READ | PROT_WRITE,
                 MAP_PRIVATE | MAP_ANONYMOUS, -1, 0));

        if (ptr != MAP_FAILED) {
            // Try to enable transparent huge pages
            madvise(ptr, size, MADV_HUGEPAGE);
        }
    } else {
        ptr = static_cast<uint8_t*>(
            mmap(nullptr, size, PROT_READ | PROT_WRITE,
                 MAP_PRIVATE | MAP_ANONYMOUS, -1, 0));
    }

    if (ptr == MAP_FAILED) {
        ptr = static_cast<uint8_t*>(std::aligned_alloc(4096, size));
        if (!ptr) {
            throw std::bad_alloc();
        }
        // Touch all pages to ensure they're allocated
        for (size_t i = 0; i < size; i += 4096) {
            ptr[i] = 0;
        }
    }

    return ptr;
}

void free_memory(uint8_t* ptr, size_t size) {
    if (ptr) {
        munmap(ptr, size);
    }
}

/**
 * Print memory configuration
 */
void print_memory_config() {
    long page_size = sysconf(_SC_PAGESIZE);
    long huge_page_size = 0;

    // Try to get huge page size
    FILE* fp = fopen("/proc/sys/vm/nr_hugepages", "r");
    if (fp) {
        long nr_hugepages;
        if (fscanf(fp, "%ld", &nr_hugepages) == 1) {
            printf("Huge pages available: %ld\n", nr_hugepages);
        }
        fclose(fp);
    }

    printf("Page size: %ld bytes\n", page_size);
    printf("Default huge page size: 2 MB (typically)\n");
    printf("TLB entries: ~64-128 for 4KB pages\n\n");
}

void print_header() {
    printf("================================================================================\n");
    printf("TLB Microbenchmark\n");
    printf("================================================================================\n");
    printf("This benchmark measures memory access performance with different access patterns.\n");
    printf("Run with perf to see detailed TLB metrics:\n");
    printf("  perf stat -e dTLB-load-misses,dTLB-store-misses,cycles,instructions,cache-misses ./bench_tlb\n\n");
    printf("Expected behavior:\n");
    printf("  - stride=64B:   Low TLB miss, cache-friendly, sequential access pattern\n");
    printf("  - stride=4KB:   HIGH TLB miss (new page each access), cache-friendly\n");
    printf("  - stride=2MB:   Very low TLB miss if using huge pages\n");
    printf("  - random:       High TLB miss + cache miss, worst case\n\n");
    printf("Key insight: When working set > TLB coverage, performance degrades sharply.\n");
    printf("================================================================================\n\n");
}

/**
 * Run a single benchmark
 */
template <size_t STRIDE>
void run_benchmark(const char* name, uint8_t* data, size_t data_size, size_t num_accesses) {
    printf("Running %-20s (stride=%6zu bytes): ", name, STRIDE);

    auto start = std::chrono::high_resolution_clock::now();
    access_with_stride<STRIDE>(data, data_size, num_accesses);
    auto end = std::chrono::high_resolution_clock::now();

    auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end - start);
    double ms = duration.count() / 1000.0;
    double throughput = (num_accesses * STRIDE) / (1024.0 * 1024.0 * (ms / 1000.0));

    printf("%8.2f ms, ", ms);
    printf("throughput: %10.2f MB/s\n", throughput);
}

void run_random_benchmark(uint8_t* data, size_t data_size, size_t num_accesses,
                          std::mt19937& rng) {
    printf("Running %-20s (random):      ", "random");

    auto start = std::chrono::high_resolution_clock::now();
    random_access(data, data_size, num_accesses, rng);
    auto end = std::chrono::high_resolution_clock::now();

    auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end - start);
    double ms = duration.count() / 1000.0;
    double throughput = (num_accesses * sizeof(uint8_t)) / (1024.0 * 1024.0 * (ms / 1000.0));

    printf("%8.2f ms, ", ms);
    printf("throughput: %10.2f MB/s\n", throughput);
}

void run_sequential_benchmark(uint8_t* data, size_t data_size, size_t num_accesses) {
    printf("Running %-20s (sequential):  ", "sequential");

    auto start = std::chrono::high_resolution_clock::now();
    sequential_access(data, data_size, num_accesses);
    auto end = std::chrono::high_resolution_clock::now();

    auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end - start);
    double ms = duration.count() / 1000.0;
    double throughput = (num_accesses * sizeof(uint8_t)) / (1024.0 * 1024.0 * (ms / 1000.0));

    printf("%8.2f ms, ", ms);
    printf("throughput: %10.2f MB/s\n", throughput);
}

/**
 * Calculate TLB pressure
 */
void print_tlb_analysis(size_t data_size, size_t stride) {
    size_t page_size = 4096;
    size_t pages_needed = (data_size + page_size - 1) / page_size;
    size_t accesses_per_page = page_size / stride;

    printf("\n  TLB Analysis for stride=%zu:\n", stride);
    printf("    Working set: %.2f GB\n", data_size / (double)GB);
    printf("    Pages needed: %zu\n", pages_needed);
    printf("    Accesses per page: %zu\n", accesses_per_page);
    printf("    TLB coverage (64 entries @ 4KB): 256 KB\n");
    printf("    Pages fitting in TLB: ~64\n");
    printf("    Fraction of WS in TLB: %.6f%%\n",
           64.0 * page_size / (double)data_size * 100);
}

void print_summary() {
    printf("\n================================================================================\n");
    printf("Summary and Expected Observations\n");
    printf("================================================================================\n");
    printf("\n1. Stride=64B:\n");
    printf("   - ~64 accesses per page\n");
    printf("   - Low TLB miss rate (reuse same pages)\n");
    printf("   - High cache hit rate (spatial locality)\n\n");

    printf("2. Stride=4KB:\n");
    printf("   - 1 access per page\n");
    printf("   - HIGH TLB miss rate (64 entries -> 256KB coverage)\n");
    printf("   - For 1GB working set: 262144 pages, only 64 in TLB = 99.98% miss\n");
    printf("   - This is the 'cliff' where performance drops sharply\n\n");

    printf("3. Stride=2MB:\n");
    printf("   - With 4KB pages: ~512 pages needed, high TLB miss\n");
    printf("   - With 2MB huge pages: ~512 pages, but only 512/64 = 8 entries needed!\n");
    printf("   - TLB miss drops dramatically with huge pages\n\n");

    printf("4. Random access:\n");
    printf("   - Worst of both worlds: cache miss + TLB miss\n");
    printf("   - Memory-bound, very slow\n\n");

    printf("To verify with perf:\n");
    printf("  perf stat -e dTLB-load-misses,dTLB-store-misses ./bench_tlb\n");
    printf("  Compare dTLB-load-misses for stride=64B vs stride=4KB\n");
    printf("================================================================================\n");
}

int main() {
    print_header();
    print_memory_config();

    // Configuration
    size_t data_size = DEFAULT_SIZE;
    size_t num_accesses = data_size / 64;  // Touch all data

    printf("Configuration:\n");
    printf("  Working set size: %.2f GB\n", data_size / (double)GB);
    printf("  Number of accesses: %zu\n\n", num_accesses);

    // Allocate memory
    printf("Allocating %.2f GB...\n", data_size / (double)GB);
    uint8_t* data = allocate_memory(data_size, false);

    // Touch pages to ensure they're allocated
    printf("Touching pages...\n");
    for (size_t i = 0; i < data_size; i += 4096) {
        data[i] = 1;
    }

    printf("\n================================================================================\n");
    printf("Benchmark Results (4KB Pages)\n");
    printf("================================================================================\n\n");

    // Run benchmarks
    run_sequential_benchmark(data, data_size, num_accesses);
    printf("\n");
    run_benchmark<64>("stride_64B", data, data_size, num_accesses);
    run_benchmark<4096>("stride_4KB", data, data_size, num_accesses);
    run_benchmark<2 * MB>("stride_2MB", data, data_size, num_accesses);

    printf("\n");

    // Random access (fewer iterations because it's slow)
    std::mt19937 rng(42);
    size_t random_accesses = num_accesses / 10;
    printf("Random access (%zu iterations):\n", random_accesses);
    run_random_benchmark(data, data_size, random_accesses, rng);

    // Print analysis
    printf("\n");
    for (size_t stride : STRIDES) {
        print_tlb_analysis(data_size, stride);
    }

    print_summary();

    // Cleanup
    free_memory(data, data_size);

    return 0;
}
