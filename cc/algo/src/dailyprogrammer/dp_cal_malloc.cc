// malloc_rss_demo.c
// Demonstrate: malloc(N) != N bytes of physical memory, lazy paging, allocator metadata/rounding,
// heap vs mmap behavior, and (glibc) malloc_trim.
//
// Build: gcc -O2 -Wall -Wextra -std=c11 -o malloc_rss_demo malloc_rss_demo.c
// Run:   ./malloc_rss_demo
//
// Notes:
// - RSS numbers come from /proc/self/statm (Linux).
// - malloc_usable_size / malloc_trim are glibc extensions. Program still runs without them,
//   but those parts will print "N/A".

#define _GNU_SOURCE
#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#if defined(__GLIBC__)
#include <malloc.h>  // malloc_usable_size, malloc_trim
#endif

static long page_size_bytes(void) {
    long ps = sysconf(_SC_PAGESIZE);
    return ps > 0 ? ps : 4096;
}

// Read RSS from /proc/self/statm: fields are in pages: size resident shared text lib data dt
static long rss_kb(void) {
    FILE* f = fopen("/proc/self/statm", "r");
    if (!f) return -1;
    unsigned long size_pages = 0, resident_pages = 0;
    int rc = fscanf(f, "%lu %lu", &size_pages, &resident_pages);
    fclose(f);
    if (rc != 2) return -1;

    long ps = page_size_bytes();
    unsigned long rss_bytes = resident_pages * (unsigned long)ps;
    return (long)(rss_bytes / 1024);
}

static void print_rss(const char* tag) {
    long r = rss_kb();
    if (r < 0) {
        printf("%-35s RSS: (unavailable)\n", tag);
    } else {
        printf("%-35s RSS: %ld KB\n", tag, r);
    }
}

// Touch one byte per page to force physical page allocation (fault in pages).
static void touch_pages(uint8_t* p, size_t nbytes) {
    long ps = page_size_bytes();
    volatile uint8_t sink = 0;

    for (size_t off = 0; off < nbytes; off += (size_t)ps) {
        p[off] = (uint8_t)(p[off] + 1);
        sink ^= p[off];
    }
    // Prevent the compiler from optimizing the loop away.
    if (sink == 0xFF) {
        fprintf(stderr, "sink=%u\n", (unsigned)sink);
    }
}

static void show_rounding_and_metadata(void) {
    printf("\n=== 1) Allocator rounding / usable size (metadata + alignment effects) ===\n");
    size_t tests[] = {1, 7, 8, 15, 16, 17, 31, 32, 33, 100, 1000, 100000};
    for (size_t i = 0; i < sizeof(tests) / sizeof(tests[0]); i++) {
        size_t n = tests[i];
        void* p = malloc(n);
        if (!p) {
            printf("malloc(%zu) failed\n", n);
            continue;
        }
#if defined(__GLIBC__)
        size_t u = malloc_usable_size(p);
        printf("malloc(%6zu) -> usable=%6zu (delta=%+6zd)\n",
               n, u, (ssize_t)u - (ssize_t)n);
#else
        printf("malloc(%6zu) -> usable=N/A (malloc_usable_size not available)\n", n);
#endif
        free(p);
    }
}

static void demo_heap_many_small_blocks(void) {
    printf("\n=== 2) Many \"small\" allocations (likely heap/brk): malloc vs touch vs free ===\n");
    // Each block is 64KB (often below glibc mmap_threshold). Many blocks aggregate to a lot.
    const size_t block_size = 64 * 1024;
    const size_t block_count = 1024;  // total ~64MB payload
    uint8_t** blocks = (uint8_t**)calloc(block_count, sizeof(uint8_t*));
    if (!blocks) {
        fprintf(stderr, "calloc blocks failed: %s\n", strerror(errno));
        return;
    }

    print_rss("Before allocating many blocks");

    // Allocate but do NOT touch.
    for (size_t i = 0; i < block_count; i++) {
        blocks[i] = (uint8_t*)malloc(block_size);
        if (!blocks[i]) {
            fprintf(stderr, "malloc block %zu failed\n", i);
            // free what we have and return
            for (size_t j = 0; j < i; j++) free(blocks[j]);
            free(blocks);
            return;
        }
    }
    print_rss("After malloc() many blocks (no touch)");

    // Touch one byte per page in each block to fault pages in.
    for (size_t i = 0; i < block_count; i++) {
        touch_pages(blocks[i], block_size);
    }
    print_rss("After touching pages (force RSS up)");

    // Free all blocks.
    for (size_t i = 0; i < block_count; i++) {
        free(blocks[i]);
    }
    print_rss("After free() many blocks (heap may keep RSS)");

#if defined(__GLIBC__)
    // malloc_trim can return free top-of-heap pages to OS (best-effort).
    int trimmed = malloc_trim(0);
    printf("malloc_trim(0) returned: %d\n", trimmed);
    print_rss("After malloc_trim(0) (best-effort RSS drop)");
#else
    printf("malloc_trim not available (non-glibc)\n");
#endif

    free(blocks);
}

static void demo_one_large_block_mmap_like(void) {
    printf("\n=== 3) One large allocation (often mmap): malloc vs touch vs free ===\n");
    // Large block: commonly served via mmap by glibc (threshold varies).
    const size_t big = (size_t)256 * 1024 * 1024; // 256MB

    print_rss("Before malloc() one big block");
    uint8_t* p = (uint8_t*)malloc(big);
    if (!p) {
        fprintf(stderr, "malloc(%zu) failed\n", big);
        return;
    }
    print_rss("After malloc() big block (no touch)");

    touch_pages(p, big);
    print_rss("After touching big block (RSS should jump)");

    free(p);
    print_rss("After free() big block (often drops quickly if mmap-backed)");
}

int main(void) {
    printf("Linux malloc/RSS demo\n");
    printf("Page size: %ld bytes\n", page_size_bytes());

#if defined(__GLIBC__)
    printf("Allocator: glibc (malloc_usable_size + malloc_trim available)\n");
#else
    printf("Allocator: unknown (glibc extensions not available)\n");
#endif

    show_rounding_and_metadata();
    demo_heap_many_small_blocks();
    demo_one_large_block_mmap_like();

    printf("\nDone.\n");
    return 0;
}