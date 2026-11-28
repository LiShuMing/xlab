/*
 * Workload for comparing default EEVDF vs scx_prio_fifo on a 2-core host:
 *   - mode "hog":   runs N busy-loop CPU hogs that saturate all cores.
 *   - mode "probe": wakes up every period_ms (default 10 ms), measures wakeup
 *                   jitter (actual_wake - expected_wake) + short burst latency,
 *                   and prints p50 / p95 / p99 / max in microseconds.
 *
 * Typical experiment:
 *   1. Start 4 CPU hogs (2x oversubscription on 2 CPUs):
 *        ./bin/cpu_hog_bench hog 4 8 &
 *   2. Run probe under EEVDF:
 *        ./bin/cpu_hog_bench probe 300 10
 *   3. Attach scx_prio_fifo (either auto short-task mode or --pid <probe_pid>)
 *      and re-run probe under identical 4-hog saturation.
 */

#define _GNU_SOURCE
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static volatile int g_hog_stop = 0;

static uint64_t NowNs(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

static int CmpU64(const void *a, const void *b) {
  uint64_t va = *(const uint64_t *)a;
  uint64_t vb = *(const uint64_t *)b;
  return (va > vb) - (va < vb);
}

static void *HogThread(void *arg) {
  uint64_t *iters = (uint64_t *)arg;
  volatile uint64_t acc = 1;
  uint64_t count = 0;
  while (!g_hog_stop) {
    for (int i = 0; i < 10000; ++i) {
      acc = acc * 6364136223846793005ULL + 1442695040888963407ULL;
    }
    count++;
  }
  *iters = count;
  (void)acc;
  return NULL;
}

static int RunHogs(int nthreads, int duration_sec) {
  if (nthreads < 1 || nthreads > 32) {
    fprintf(stderr, "invalid hog threads: %d\n", nthreads);
    return 1;
  }
  pthread_t tids[32];
  uint64_t iters[32] = {0};

  for (int i = 0; i < nthreads; ++i) {
    if (pthread_create(&tids[i], NULL, HogThread, &iters[i]) != 0) {
      perror("pthread_create");
      return 1;
    }
  }
  sleep((unsigned int)duration_sec);
  g_hog_stop = 1;

  uint64_t total = 0;
  for (int i = 0; i < nthreads; ++i) {
    pthread_join(tids[i], NULL);
    total += iters[i];
  }
  printf("hog_done threads=%d duration_s=%d total_work_units=%llu\n",
         nthreads, duration_sec, (unsigned long long)total);
  return 0;
}

static int RunProbe(int samples, int period_ms) {
  if (samples < 10 || samples > 100000) {
    fprintf(stderr, "invalid samples: %d\n", samples);
    return 1;
  }
  uint64_t *jitter_us = calloc((size_t)samples, sizeof(uint64_t));
  if (!jitter_us) {
    perror("calloc");
    return 1;
  }

  printf("probe_pid=%d samples=%d period_ms=%d\n", getpid(), samples, period_ms);
  fflush(stdout);

  struct timespec target;
  clock_gettime(CLOCK_MONOTONIC, &target);
  uint64_t period_ns = (uint64_t)period_ms * 1000000ULL;

  for (int i = 0; i < samples; ++i) {
    uint64_t next_ns = (uint64_t)target.tv_sec * 1000000000ULL +
                       (uint64_t)target.tv_nsec + period_ns;
    target.tv_sec = (time_t)(next_ns / 1000000000ULL);
    target.tv_nsec = (long)(next_ns % 1000000000ULL);

    clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &target, NULL);
    uint64_t woke_ns = NowNs();
    uint64_t lat_ns = woke_ns > next_ns ? (woke_ns - next_ns) : 0;
    jitter_us[i] = lat_ns / 1000ULL;

    /* Small burst (~30-80 us) so this task stays classified as a short task. */
    volatile uint64_t x = 7;
    for (int k = 0; k < 2000; ++k) {
      x = x * 1103515245ULL + 12345ULL;
    }
    (void)x;
  }

  qsort(jitter_us, (size_t)samples, sizeof(uint64_t), CmpU64);
  uint64_t p50 = jitter_us[samples / 2];
  uint64_t p95 = jitter_us[(samples * 95) / 100];
  uint64_t p99 = jitter_us[(samples * 99) / 100];
  uint64_t pmax = jitter_us[samples - 1];
  uint64_t sum = 0;
  for (int i = 0; i < samples; ++i) {
    sum += jitter_us[i];
  }
  printf("wakeup_jitter_us: avg=%.1f p50=%llu p95=%llu p99=%llu max=%llu\n",
         (double)sum / (double)samples,
         (unsigned long long)p50,
         (unsigned long long)p95,
         (unsigned long long)p99,
         (unsigned long long)pmax);

  free(jitter_us);
  return 0;
}

int main(int argc, char **argv) {
  if (argc < 2) {
    fprintf(stderr,
            "Usage:\n"
            "  %s hog [nthreads=4] [duration_s=8]\n"
            "  %s probe [samples=300] [period_ms=10]\n",
            argv[0], argv[0]);
    return 1;
  }
  if (strcmp(argv[1], "hog") == 0) {
    int nthreads = argc > 2 ? atoi(argv[2]) : 4;
    int duration = argc > 3 ? atoi(argv[3]) : 8;
    return RunHogs(nthreads, duration);
  }
  if (strcmp(argv[1], "probe") == 0) {
    int samples = argc > 2 ? atoi(argv[2]) : 300;
    int period_ms = argc > 3 ? atoi(argv[3]) : 10;
    return RunProbe(samples, period_ms);
  }
  fprintf(stderr, "unknown mode: %s\n", argv[1]);
  return 1;
}
