// Controlled CPU-contention latency benchmark for sched_ext vs EEVDF.
//
// Modes:
//   hog   [seconds]         - saturates 1 CPU core with tight arithmetic work
//   probe [samples] [ms]    - wakes up every `ms` milliseconds, runs a short
//                             fixed compute burst (~500 us), and reports
//                             wakeup-delay & completion-latency p50/p95/p99.

#define _GNU_SOURCE
#include <math.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t g_hog_stop = 0;

static void on_hog_term(int sig) {
  (void)sig;
  g_hog_stop = 1;
}

static uint64_t now_ns(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

static int cmp_u64(const void *a, const void *b) {
  uint64_t x = *(const uint64_t *)a;
  uint64_t y = *(const uint64_t *)b;
  return (x > y) - (x < y);
}

static uint64_t percentile(const uint64_t *sorted, size_t n, double p) {
  if (n == 0) return 0;
  size_t idx = (size_t)((p / 100.0) * (double)(n - 1));
  if (idx >= n) idx = n - 1;
  return sorted[idx];
}

static int run_hog(int seconds) {
  signal(SIGTERM, on_hog_term);
  signal(SIGINT, on_hog_term);
  uint64_t t0 = now_ns();
  uint64_t end = t0 + (uint64_t)seconds * 1000000000ULL;
  volatile uint64_t acc = 1;
  uint64_t iters = 0;
  while (!g_hog_stop && now_ns() < end) {
    for (int i = 0; i < 4096; ++i) {
      acc = acc * 6364136223846793005ULL + 1442695040888963407ULL;
    }
    iters++;
  }
  double elapsed_s = (double)(now_ns() - t0) / 1e9;
  if (elapsed_s < 1e-6) elapsed_s = 1e-6;
  printf("hog pid=%d iters=%llu elapsed_s=%.3f iters_per_s=%.1f\n",
         getpid(), (unsigned long long)iters, elapsed_s,
         (double)iters / elapsed_s);
  return 0;
}

static int run_probe(int samples, int period_ms, int work_loops) {
  uint64_t *wake_us = calloc((size_t)samples, sizeof(uint64_t));
  uint64_t *exec_us = calloc((size_t)samples, sizeof(uint64_t));
  if (!wake_us || !exec_us) return 1;

  // Print PID immediately so orchestrator can pass it to --prio-pid if desired.
  printf("PROBE_PID=%d\n", getpid());
  fflush(stdout);

  // Brief startup pause so scheduler can attach after reading PROBE_PID.
  struct timespec init_ts = {.tv_sec = 0, .tv_nsec = 400000000};
  nanosleep(&init_ts, NULL);

  volatile uint64_t acc = 1;
  for (int i = 0; i < samples; ++i) {
    uint64_t target = now_ns() + (uint64_t)period_ms * 1000000ULL;
    struct timespec sleep_ts = {.tv_sec = period_ms / 1000,
                                .tv_nsec = (period_ms % 1000) * 1000000L};
    nanosleep(&sleep_ts, NULL);
    uint64_t woke = now_ns();
    uint64_t overshoot_ns = woke > target ? (woke - target) : 0;

    for (int k = 0; k < work_loops; ++k) {
      acc = acc * 2862933555777941757ULL + 3037000493ULL;
    }
    uint64_t done = now_ns();

    wake_us[i] = overshoot_ns / 1000;
    exec_us[i] = (done - target) / 1000;
  }

  qsort(wake_us, (size_t)samples, sizeof(uint64_t), cmp_u64);
  qsort(exec_us, (size_t)samples, sizeof(uint64_t), cmp_u64);

  printf(
      "probe samples=%d wake_delay_us(p50=%llu p95=%llu p99=%llu max=%llu) "
      "total_resp_us(p50=%llu p95=%llu p99=%llu max=%llu)\n",
      samples,
      (unsigned long long)percentile(wake_us, (size_t)samples, 50),
      (unsigned long long)percentile(wake_us, (size_t)samples, 95),
      (unsigned long long)percentile(wake_us, (size_t)samples, 99),
      (unsigned long long)wake_us[samples - 1],
      (unsigned long long)percentile(exec_us, (size_t)samples, 50),
      (unsigned long long)percentile(exec_us, (size_t)samples, 95),
      (unsigned long long)percentile(exec_us, (size_t)samples, 99),
      (unsigned long long)exec_us[samples - 1]);

  free(wake_us);
  free(exec_us);
  return 0;
}

int main(int argc, char **argv) {
  if (argc < 2) {
    fprintf(stderr, "Usage: %s hog [sec] | probe [samples] [period_ms] [work_loops]\n",
            argv[0]);
    return 1;
  }
  if (strcmp(argv[1], "hog") == 0) {
    int sec = argc > 2 ? atoi(argv[2]) : 5;
    return run_hog(sec);
  }
  if (strcmp(argv[1], "probe") == 0) {
    int samples = argc > 2 ? atoi(argv[2]) : 150;
    int period_ms = argc > 3 ? atoi(argv[3]) : 15;
    int work_loops = argc > 4 ? atoi(argv[4]) : 50000;
    return run_probe(samples, period_ms, work_loops);
  }
  fprintf(stderr, "Unknown mode: %s\n", argv[1]);
  return 1;
}
