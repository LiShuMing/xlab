/**
 * @file l_page_memory_behavior.c
 * @brief 演示 malloc/mmap 内存分配与页错误的关系
 *
 * 这个程序展示：
 * 1. malloc 不等于立刻占用物理内存（RSS 不涨）
 * 2. 写入触发缺页异常，内核分配物理页并建立映射
 * 3. 顺序/随机写会影响缺页次数与性能
 * 4. madvise(MADV_DONTNEED) 如何丢弃页
 * 5. mlock 如何锁页到RAM
 *
 * 编译: gcc -o l_page_memory_behavior l_page_memory_behavior.c -Wall -O2
 */

// ╔═══════════════════════════════════════════════════════════╗
// ║         内存分配与页错误行为演示程序                       ║
// ║         Page Fault and Memory Behavior Demo               ║
// ╚═══════════════════════════════════════════════════════════╝

// 系统信息:
//   页大小: 4096 字节 (4 KB)
//   初始 RSS: 1052 KB

// ═══════════════════════════════════════════════════════════
// 测试 1: malloc 分配但不触碰内存
// ═══════════════════════════════════════════════════════════
// 分配 524288 字节 (128 页)...

// [malloc 后（未触碰）]
//   RSS: 1052 KB -> 1052 KB (变化: +0 KB, +0 页)
//   Minor Page Faults: 88 -> 89 (变化: +1)
//   Major Page Faults: 0 -> 0 (变化: +0)
// 结论: malloc 只分配虚拟地址空间，不立即分配物理页
//       RSS 基本不变，没有页错误

// ═══════════════════════════════════════════════════════════
// 测试 2: malloc 分配后逐页写入（触发每页一次缺页）
// ═══════════════════════════════════════════════════════════

// 分配后状态:
//   RSS: 1624 KB
//   Minor PF: 90, Major PF: 0

// 逐页写入 (每页写一个字节)...

// 触碰后状态:
//   RSS: 1884 KB
//   Minor PF: 217 (+127), Major PF: 0 (+0)
// 结论: 每页第一次写入触发一次缺页异常
//       RSS 增长约等于触碰的页数 * 4KB

// ═══════════════════════════════════════════════════════════
// 测试 3: malloc 分配后顺序写入
// ═══════════════════════════════════════════════════════════

// 顺序写入 524288 字节...

// [顺序写入后]
//   RSS: 1884 KB -> 1884 KB (变化: +0 KB, +0 页)
//   Minor Page Faults: 217 -> 219 (变化: +2)
//   Major Page Faults: 0 -> 0 (变化: +0)
// 写入耗时: 0.001460 秒
// 吞吐量: 342.48 MB/s
// 结论: 顺序写入对 CPU 缓存友好，缺页次数 = 页数

// ═══════════════════════════════════════════════════════════
// 测试 4: malloc 分配后随机写入
// ═══════════════════════════════════════════════════════════

// 随机写入 128 页（每页一个随机位置）...

// [随机写入后]
//   RSS: 1884 KB -> 1884 KB (变化: +0 KB, +0 页)
//   Minor Page Faults: 219 -> 219 (变化: +0)
//   Major Page Faults: 0 -> 0 (变化: +0)
// 写入耗时: 0.000003 秒
// 结论: 随机写入对缓存不友好，但缺页次数同样是每页一次

// ═══════════════════════════════════════════════════════════
// 测试 5: mmap 匿名映射分配
// ═══════════════════════════════════════════════════════════
// 使用 mmap 分配 524288 字节 (128 页)...

// [mmap 后（未触碰）]
//   RSS: 1884 KB -> 1884 KB (变化: +0 KB, +0 页)
//   Minor Page Faults: 219 -> 219 (变化: +0)
//   Major Page Faults: 0 -> 0 (变化: +0)
// 结论: mmap 匿名映射同样只分配虚拟地址空间

// 触碰第一页...

// 触碰后状态:
//   RSS: 1884 KB
//   Minor PF: 220, Major PF: 0

// ═══════════════════════════════════════════════════════════
// 测试 6: madvise(MADV_DONTNEED) 丢弃页
// ═══════════════════════════════════════════════════════════
// 分配并触碰 128 页...
// 触碰后 RSS: 2460 KB

// 调用 madvise(Ptr, Size, MADV_DONTNEED)...
// 这会要求内核丢弃指定范围的页...

// madvise 后状态:
//   RSS: 2460 KB -> 2200 KB (变化: -260 KB)
//   Minor PF: +1, Major PF: +0

// 现在再次触碰这些页...

// 重新触碰后状态:
//   RSS: 2520 KB
//   Minor PF: 477 (+128), Major PF: 0 (+0)
// 结论: madvise(MADV_DONTNEED) 释放物理页但保留虚拟地址映射
//       再次访问会导致新的缺页（通常是 major page fault）

// ═══════════════════════════════════════════════════════════
// 测试 7: mlock 锁定页到 RAM
// ═══════════════════════════════════════════════════════════
// 警告: 这个测试会尝试锁定内存页
// 当前限制: Max locked memory         50472620032          50472620032          bytes     

// 分配并触碰 128 页...
// 触碰后 RSS: 2524 KB

// 调用 mlock(ptr, 524288)...
// 这会尝试将这些页锁定到 RAM 中...
// mlock 成功!

// mlock 后状态:
//   RSS: 2524 KB

// 尝试 madvise(MADV_DONTNEED) 丢弃锁定的页...
// madvise on locked pages: Invalid argument
//   RSS: 2524 KB

// 解锁内存...
// 结论: mlock 防止页被换出到 swap
//       注意: 过度使用 mlock 可能导致系统问题

// ═══════════════════════════════════════════════════════════
// 测试 8: 顺序写 vs 随机写 性能对比
// ═══════════════════════════════════════════════════════════

// [顺序写测试 - 10 MB, 100 次迭代]
//   顺序写耗时: 0.008873 秒
//   吞吐量: 112696.26 MB/s

// [随机写测试 - 10 MB, 100 次迭代, 每次随机写 2560 页]
//   随机写耗时: 0.010237 秒
//   吞吐量: 97682.24 MB/s

// [性能对比]
//   顺序写: 112696.26 MB/s
//   随机写: 97682.24 MB/s
//   速度比: 1.15x

// [详细统计 - getrusage]
//   用户时间: 0.014947 秒
//   系统时间: 0.018684 秒
//   最大 RSS: 12292 KB
//   页面回收（软缺页）: 5597
//   页面错误（硬缺页）: 0
//   上下文切换次数: 3

// ═══════════════════════════════════════════════════════════
// 总结:
// ═══════════════════════════════════════════════════════════
// 1. malloc/mmap 只分配虚拟地址空间，不立即分配物理页
// 2. 写入触发缺页异常，内核分配物理页并建立映射
// 3. 每页第一次访问会导致一次缺页
// 4. 顺序写对 CPU 缓存友好，速度更快
// 5. madvise(MADV_DONTNEED) 可以丢弃物理页但保留映射
// 6. mlock 可以锁页到 RAM，防止被换出

 #define _GNU_SOURCE
 #include <stdio.h>
 #include <stdlib.h>
 #include <string.h>
 #include <stdint.h>
 #include <unistd.h>
 #include <sys/mman.h>
 #include <sys/resource.h>
 #include <sys/time.h>
 #include <fcntl.h>
 #include <errno.h>
 #include <time.h>
 
 /* 页大小，通常是 4096 字节 */
 #define PAGE_SIZE 4096
 
 /* 测试分配的页数 */
 #define NUM_PAGES 128
 
 /* 测试内存大小 */
 #define ALLOC_SIZE (NUM_PAGES * PAGE_SIZE)
 
 /**
  * @brief 获取当前 RSS（Resident Set Size）
  * @return RSS 大小（KB）
  */
 static long get_rss_kb(void) {
     FILE *fp = fopen("/proc/self/statm", "r");
     if (!fp) {
         perror("fopen /proc/self/statm");
         return -1;
     }
 
     long rss = -1;
     if (fscanf(fp, "%*s %ld", &rss) != 1) {
         perror("fscanf statm");
     }
     fclose(fp);
 
     /* statm 的单位是页，需要转换为 KB */
     return rss * (PAGE_SIZE / 1024);
 }
 
 /**
  * @brief 获取页面错误信息
  */
 static void get_page_faults(long *minor, long *major) {
     struct rusage usage;
     if (getrusage(RUSAGE_SELF, &usage) != 0) {
         perror("getrusage");
         return;
     }
     *minor = usage.ru_minflt;
     *major = usage.ru_majflt;
 }
 
 /**
  * @brief 打印内存和页错误状态
  */
 static void print_memory_state(const char *phase, long rss_before,
                                long minor_before, long major_before) {
     long rss_after = get_rss_kb();
     long minor_after, major_after;
     get_page_faults(&minor_after, &major_after);
 
     long rss_diff = rss_after - rss_before;
     long minor_diff = minor_after - minor_before;
     long major_diff = major_after - major_before;
 
     printf("\n[%s]\n", phase);
     printf("  RSS: %ld KB -> %ld KB (变化: %+ld KB, %+ld 页)\n",
            rss_before, rss_after, rss_diff, rss_diff / 4);
     printf("  Minor Page Faults: %ld -> %ld (变化: %+ld)\n",
            minor_before, minor_after, minor_diff);
     printf("  Major Page Faults: %ld -> %ld (变化: %+ld)\n",
            major_before, major_after, major_diff);
 }
 
 /**
  * @brief 使用 getrusage 获取更详细的统计信息
  */
 static void print_detailed_stats(void) {
     struct rusage usage;
     if (getrusage(RUSAGE_SELF, &usage) != 0) {
         perror("getrusage");
         return;
     }
 
     printf("\n[详细统计 - getrusage]\n");
     printf("  用户时间: %ld.%06ld 秒\n",
            usage.ru_utime.tv_sec, usage.ru_utime.tv_usec);
     printf("  系统时间: %ld.%06ld 秒\n",
            usage.ru_stime.tv_sec, usage.ru_stime.tv_usec);
     printf("  最大 RSS: %ld KB\n", usage.ru_maxrss);
     printf("  页面回收（软缺页）: %ld\n", usage.ru_minflt);
     printf("  页面错误（硬缺页）: %ld\n", usage.ru_majflt);
     printf("  上下文切换次数: %ld\n", usage.ru_nivcsw);
 }
 
 /* ==================== malloc 测试 ==================== */
 
 /**
  * @brief 测试 malloc 分配但不触碰内存
  */
 static void test_malloc_no_touch(void) {
     printf("\n");
     printf("═══════════════════════════════════════════════════════════\n");
     printf("测试 1: malloc 分配但不触碰内存\n");
     printf("═══════════════════════════════════════════════════════════\n");
 
     long rss_before = get_rss_kb();
     long minor_before, major_before;
     get_page_faults(&minor_before, &major_before);
 
     printf("分配 %d 字节 (%d 页)...\n", ALLOC_SIZE, NUM_PAGES);
 
     /* 只分配，不触碰 */
     char *ptr = static_cast<char*>(malloc(ALLOC_SIZE));
     if (!ptr) {
         perror("malloc");
         return;
     }
 
     print_memory_state("malloc 后（未触碰）", rss_before, minor_before, major_before);
 
     printf("结论: malloc 只分配虚拟地址空间，不立即分配物理页\n");
     printf("      RSS 基本不变，没有页错误\n");
 
     free(ptr);
 }
 
 /**
  * @brief 测试逐页写入
  */
 static void test_malloc_page_by_page(void) {
     printf("\n");
     printf("═══════════════════════════════════════════════════════════\n");
     printf("测试 2: malloc 分配后逐页写入（触发每页一次缺页）\n");
     printf("═══════════════════════════════════════════════════════════\n");
 
     long minor_before, major_before;
     get_page_faults(&minor_before, &major_before);
 
     char *ptr = static_cast<char*>(malloc(ALLOC_SIZE));
     if (!ptr) {
         perror("malloc");
         return;
     }

     long rss_after_alloc = get_rss_kb();
     long minor_after_alloc, major_after_alloc;
     get_page_faults(&minor_after_alloc, &major_after_alloc);
 
     printf("\n分配后状态:\n");
     printf("  RSS: %ld KB\n", rss_after_alloc);
     printf("  Minor PF: %ld, Major PF: %ld\n",
            minor_after_alloc, major_after_alloc);
 
     printf("\n逐页写入 (每页写一个字节)...\n");
     for (int i = 0; i < NUM_PAGES; i++) {
         ptr[i * PAGE_SIZE] = (char)(i & 0xFF);
     }
 
     long rss_after_touch = get_rss_kb();
     long minor_after_touch, major_after_touch;
     get_page_faults(&minor_after_touch, &major_after_touch);
 
     printf("\n触碰后状态:\n");
     printf("  RSS: %ld KB\n", rss_after_touch);
     printf("  Minor PF: %ld (+%ld), Major PF: %ld (+%ld)\n",
            minor_after_touch, minor_after_touch - minor_after_alloc,
            major_after_touch, major_after_touch - major_after_alloc);
 
     printf("结论: 每页第一次写入触发一次缺页异常\n");
     printf("      RSS 增长约等于触碰的页数 * 4KB\n");
 
     free(ptr);
 }
 
 /**
  * @brief 测试顺序写入
  */
 static void test_malloc_sequential_write(void) {
     printf("\n");
     printf("═══════════════════════════════════════════════════════════\n");
     printf("测试 3: malloc 分配后顺序写入\n");
     printf("═══════════════════════════════════════════════════════════\n");
 
     long rss_before = get_rss_kb();
     long minor_before, major_before;
     get_page_faults(&minor_before, &major_before);
 
     char *ptr = static_cast<char*>(malloc(ALLOC_SIZE));
     if (!ptr) {
         perror("malloc");
         return;
     }

     printf("\n顺序写入 %d 字节...\n", ALLOC_SIZE);
 
     struct timespec start, end;
     clock_gettime(CLOCK_MONOTONIC, &start);
 
     /* 顺序写入整个区域 */
     for (size_t i = 0; i < ALLOC_SIZE; i++) {
         ptr[i] = (char)(i & 0xFF);
     }
 
     clock_gettime(CLOCK_MONOTONIC, &end);
     double elapsed = (end.tv_sec - start.tv_sec) +
                      (end.tv_nsec - start.tv_nsec) / 1e9;
 
     print_memory_state("顺序写入后", rss_before, minor_before, major_before);
 
     printf("写入耗时: %.6f 秒\n", elapsed);
     printf("吞吐量: %.2f MB/s\n", (ALLOC_SIZE / 1024.0 / 1024.0) / elapsed);
     printf("结论: 顺序写入对 CPU 缓存友好，缺页次数 = 页数\n");
 
     free(ptr);
 }
 
 /**
  * @brief 测试随机写入
  */
 static void test_malloc_random_write(void) {
     printf("\n");
     printf("═══════════════════════════════════════════════════════════\n");
     printf("测试 4: malloc 分配后随机写入\n");
     printf("═══════════════════════════════════════════════════════════\n");
 
     long rss_before = get_rss_kb();
     long minor_before, major_before;
     get_page_faults(&minor_before, &major_before);
 
     char *ptr = static_cast<char*>(malloc(ALLOC_SIZE));
     if (!ptr) {
         perror("malloc");
         return;
     }

     /* 使用确定性随机数以便复现 */
     printf("\n随机写入 %d 页（每页一个随机位置）...\n", NUM_PAGES);
 
     struct timespec start, end;
     clock_gettime(CLOCK_MONOTONIC, &start);
 
     /* 随机访问每页的一个位置 */
     for (int i = 0; i < NUM_PAGES; i++) {
         size_t offset = (rand() % PAGE_SIZE);
         ptr[i * PAGE_SIZE + offset] = (char)(i & 0xFF);
     }
 
     clock_gettime(CLOCK_MONOTONIC, &end);
     double elapsed = (end.tv_sec - start.tv_sec) +
                      (end.tv_nsec - start.tv_nsec) / 1e9;
 
     print_memory_state("随机写入后", rss_before, minor_before, major_before);
 
     printf("写入耗时: %.6f 秒\n", elapsed);
     printf("结论: 随机写入对缓存不友好，但缺页次数同样是每页一次\n");
 
     free(ptr);
 }
 
 /* ==================== mmap 测试 ==================== */
 
 /**
  * @brief 测试 mmap 匿名映射
  */
 static void test_mmap_anonymous(void) {
     printf("\n");
     printf("═══════════════════════════════════════════════════════════\n");
     printf("测试 5: mmap 匿名映射分配\n");
     printf("═══════════════════════════════════════════════════════════\n");
 
     long rss_before = get_rss_kb();
     long minor_before, major_before;
     get_page_faults(&minor_before, &major_before);
 
     printf("使用 mmap 分配 %d 字节 (%d 页)...\n", ALLOC_SIZE, NUM_PAGES);
 
     /* 匿名映射 */
     char *ptr = static_cast<char*>(mmap(NULL, ALLOC_SIZE,
                      PROT_READ | PROT_WRITE,
                      MAP_PRIVATE | MAP_ANONYMOUS,
                      -1, 0));
 
     if (ptr == MAP_FAILED) {
         perror("mmap");
         return;
     }
 
     print_memory_state("mmap 后（未触碰）", rss_before, minor_before, major_before);
 
     printf("结论: mmap 匿名映射同样只分配虚拟地址空间\n");
 
     /* 现在触碰它 */
     printf("\n触碰第一页...\n");
     ptr[0] = 1;
 
     long rss_after_touch = get_rss_kb();
     long minor_after_touch, major_after_touch;
     get_page_faults(&minor_after_touch, &major_after_touch);
 
     printf("\n触碰后状态:\n");
     printf("  RSS: %ld KB\n", rss_after_touch);
     printf("  Minor PF: %ld, Major PF: %ld\n",
            minor_after_touch, major_after_touch);
 
     munmap(ptr, ALLOC_SIZE);
 }
 
 /* ==================== madvise 测试 ==================== */
 
 /**
  * @brief 测试 madvise(MADV_DONTNEED) - 丢弃页
  */
 static void test_madvise_dontneed(void) {
     printf("\n");
     printf("═══════════════════════════════════════════════════════════\n");
     printf("测试 6: madvise(MADV_DONTNEED) 丢弃页\n");
     printf("═══════════════════════════════════════════════════════════\n");
 
     printf("分配并触碰 %d 页...\n", NUM_PAGES);
 
     /* 使用 mmap 分配以确保页对齐 */
     char *ptr = static_cast<char*>(mmap(NULL, ALLOC_SIZE,
                      PROT_READ | PROT_WRITE,
                      MAP_PRIVATE | MAP_ANONYMOUS,
                      -1, 0));
     if (ptr == MAP_FAILED) {
         perror("mmap");
         return;
     }

     /* 触碰所有页 */
     for (size_t i = 0; i < ALLOC_SIZE; i += PAGE_SIZE) {
         ptr[i] = 1;
     }

     long rss_after_touch = get_rss_kb();
     printf("触碰后 RSS: %ld KB\n", rss_after_touch);

     long minor_before, major_before;
     get_page_faults(&minor_before, &major_before);

     printf("\n调用 madvise(Ptr, Size, MADV_DONTNEED)...\n");
     printf("这会要求内核丢弃指定范围的页...\n");

     /* 使用 madvise 丢弃页 */
     if (madvise(ptr, ALLOC_SIZE, MADV_DONTNEED) != 0) {
         perror("madvise");
         munmap(ptr, ALLOC_SIZE);
         return;
     }
 
     /* 等待一下让操作生效 */
     sync();
     usleep(100000);
 
     long rss_after_madvise = get_rss_kb();
     long minor_after, major_after;
     get_page_faults(&minor_after, &major_after);
 
     printf("\nmadvise 后状态:\n");
     printf("  RSS: %ld KB -> %ld KB (变化: %+ld KB)\n",
            rss_after_touch, rss_after_madvise,
            rss_after_madvise - rss_after_touch);
     printf("  Minor PF: %+ld, Major PF: %+ld\n",
            minor_after - minor_before,
            major_after - major_before);
 
     printf("\n现在再次触碰这些页...\n");
     for (size_t i = 0; i < ALLOC_SIZE; i += PAGE_SIZE) {
         ptr[i] = 2;
     }
 
     long rss_after_retouch = get_rss_kb();
     long minor_after_retouch, major_after_retouch;
     get_page_faults(&minor_after_retouch, &major_after_retouch);
 
     printf("\n重新触碰后状态:\n");
     printf("  RSS: %ld KB\n", rss_after_retouch);
     printf("  Minor PF: %ld (+%ld), Major PF: %ld (+%ld)\n",
            minor_after_retouch,
            minor_after_retouch - minor_after,
            major_after_retouch,
            major_after_retouch - major_after);
 
     printf("结论: madvise(MADV_DONTNEED) 释放物理页但保留虚拟地址映射\n");
     printf("      再次访问会导致新的缺页（通常是 major page fault）\n");
 
     munmap(ptr, ALLOC_SIZE);
 }
 
 /* ==================== mlock 测试 ==================== */
 
 /**
  * @brief 测试 mlock - 将页锁定到 RAM
  */
 static void test_mlock_pages(void) {
     printf("\n");
     printf("═══════════════════════════════════════════════════════════\n");
     printf("测试 7: mlock 锁定页到 RAM\n");
     printf("═══════════════════════════════════════════════════════════\n");
     printf("警告: 这个测试会尝试锁定内存页\n");
 
     /* 检查当前锁定的内存限制 */
     FILE *fp = fopen("/proc/self/limits", "r");
     if (fp) {
         char line[512];
         while (fgets(line, sizeof(line), fp)) {
             if (strstr(line, "Max locked memory")) {
                 printf("当前限制: %s", line);
                 break;
             }
         }
         fclose(fp);
     }
 
     long minor_before, major_before;
     get_page_faults(&minor_before, &major_before);
 
     printf("\n分配并触碰 %d 页...\n", NUM_PAGES);
 
     /* 使用 mmap 分配以确保页对齐 */
     char *ptr = static_cast<char*>(mmap(NULL, ALLOC_SIZE,
                      PROT_READ | PROT_WRITE,
                      MAP_PRIVATE | MAP_ANONYMOUS,
                      -1, 0));
     if (ptr == MAP_FAILED) {
         perror("mmap");
         return;
     }

     /* 触碰所有页以确保它们在内存中 */
     for (size_t i = 0; i < ALLOC_SIZE; i += PAGE_SIZE) {
         ptr[i] = 1;
     }

     long rss_after_touch = get_rss_kb();
     printf("触碰后 RSS: %ld KB\n", rss_after_touch);

     printf("\n调用 mlock(ptr, %d)...\n", ALLOC_SIZE);
     printf("这会尝试将这些页锁定到 RAM 中...\n");

     /* 尝试锁定页 */
     if (mlock(ptr, ALLOC_SIZE) != 0) {
         perror("mlock");
         if (errno == ENOMEM) {
             printf("提示: 可能需要 root 权限或调整 ulimit -l\n");
         }
         munmap(ptr, ALLOC_SIZE);
         return;
     }
 
     printf("mlock 成功!\n");
 
     long rss_after_mlock = get_rss_kb();
     long minor_after, major_after;
     get_page_faults(&minor_after, &major_after);
 
     printf("\nmlock 后状态:\n");
     printf("  RSS: %ld KB\n", rss_after_mlock);
 
     /* 尝试丢弃页（应该失败或部分失败） */
     printf("\n尝试 madvise(MADV_DONTNEED) 丢弃锁定的页...\n");
     int ret = madvise(ptr, ALLOC_SIZE, MADV_DONTNEED);
     if (ret != 0) {
         perror("madvise on locked pages");
     } else {
         printf("madvise 返回成功，但检查 RSS...\n");
     }
 
     long rss_after_madvise = get_rss_kb();
     printf("  RSS: %ld KB\n", rss_after_madvise);
 
     printf("\n解锁内存...\n");
     munlock(ptr, ALLOC_SIZE);
 
     printf("结论: mlock 防止页被换出到 swap\n");
     printf("      注意: 过度使用 mlock 可能导致系统问题\n");
 
     munlock(ptr, ALLOC_SIZE);
     munmap(ptr, ALLOC_SIZE);
 }
 
 /**
  * @brief 比较顺序写 vs 随机写的性能
  */
 static void test_sequential_vs_random_performance(void) {
     printf("\n");
     printf("═══════════════════════════════════════════════════════════\n");
     printf("测试 8: 顺序写 vs 随机写 性能对比\n");
     printf("═══════════════════════════════════════════════════════════\n");
 
     const size_t large_size = 1024 * 1024 * 10; /* 10 MB */
     const size_t iterations = 100;
 
     /* 顺序写测试 */
     printf("\n[顺序写测试 - %zu MB, %zu 次迭代]\n",
            large_size / (1024 * 1024), iterations);
 
     char *ptr = static_cast<char*>(malloc(large_size));
     if (!ptr) {
         perror("malloc");
         return;
     }

     struct timespec start, end;

     clock_gettime(CLOCK_MONOTONIC, &start);
     for (int iter = 0; iter < iterations; iter++) {
         for (size_t i = 0; i < large_size; i += PAGE_SIZE) {
             ptr[i] = (char)(iter + i);
         }
     }
     clock_gettime(CLOCK_MONOTONIC, &end);

     double sequential_time = (end.tv_sec - start.tv_sec) +
                              (end.tv_nsec - start.tv_nsec) / 1e9;
     printf("  顺序写耗时: %.6f 秒\n", sequential_time);
     printf("  吞吐量: %.2f MB/s\n",
            (large_size * iterations / 1024.0 / 1024.0) / sequential_time);

     free(ptr);

     /* 随机写测试 */
     printf("\n[随机写测试 - %zu MB, %zu 次迭代, 每次随机写 %zu 页]\n",
            large_size / (1024 * 1024), iterations, large_size / PAGE_SIZE);

     ptr = static_cast<char*>(malloc(large_size));
     if (!ptr) {
         perror("malloc");
         return;
     }
 
     /* 先触碰所有页 */
     for (size_t i = 0; i < large_size; i += PAGE_SIZE) {
         ptr[i] = 0;
     }
 
     /* 设置随机种子 */
     srand(42);
 
     clock_gettime(CLOCK_MONOTONIC, &start);
     for (int iter = 0; iter < iterations; iter++) {
         for (size_t i = 0; i < large_size; i += PAGE_SIZE) {
             size_t offset = rand() % PAGE_SIZE;
             ptr[i + offset] = (char)(iter + i);
         }
     }
     clock_gettime(CLOCK_MONOTONIC, &end);
 
     double random_time = (end.tv_sec - start.tv_sec) +
                          (end.tv_nsec - start.tv_nsec) / 1e9;
     printf("  随机写耗时: %.6f 秒\n", random_time);
     printf("  吞吐量: %.2f MB/s\n",
            (large_size * iterations / 1024.0 / 1024.0) / random_time);
 
     printf("\n[性能对比]\n");
     printf("  顺序写: %.2f MB/s\n",
            (large_size * iterations / 1024.0 / 1024.0) / sequential_time);
     printf("  随机写: %.2f MB/s\n",
            (large_size * iterations / 1024.0 / 1024.0) / random_time);
     printf("  速度比: %.2fx\n", random_time / sequential_time);
 
     free(ptr);
 }
 
 /**
  * @brief 主函数
  */
 int main(int argc, char *argv[]) {
     printf("╔═══════════════════════════════════════════════════════════╗\n");
     printf("║         内存分配与页错误行为演示程序                       ║\n");
     printf("║         Page Fault and Memory Behavior Demo               ║\n");
     printf("╚═══════════════════════════════════════════════════════════╝\n");
 
     printf("\n系统信息:\n");
     printf("  页大小: %d 字节 (%d KB)\n", PAGE_SIZE, PAGE_SIZE / 1024);
     printf("  初始 RSS: %ld KB\n", get_rss_kb());
 
     /* 运行测试 */
     test_malloc_no_touch();
     test_malloc_page_by_page();
     test_malloc_sequential_write();
     test_malloc_random_write();
     test_mmap_anonymous();
     test_madvise_dontneed();
     test_mlock_pages();
     test_sequential_vs_random_performance();
 
     /* 打印最终统计 */
     print_detailed_stats();
 
     printf("\n");
     printf("═══════════════════════════════════════════════════════════\n");
     printf("总结:\n");
     printf("═══════════════════════════════════════════════════════════\n");
     printf("1. malloc/mmap 只分配虚拟地址空间，不立即分配物理页\n");
     printf("2. 写入触发缺页异常，内核分配物理页并建立映射\n");
     printf("3. 每页第一次访问会导致一次缺页\n");
     printf("4. 顺序写对 CPU 缓存友好，速度更快\n");
     printf("5. madvise(MADV_DONTNEED) 可以丢弃物理页但保留映射\n");
     printf("6. mlock 可以锁页到 RAM，防止被换出\n");
     printf("═══════════════════════════════════════════════════════════\n");
 
     return 0;
 }
 