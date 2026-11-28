// Experiment 1B: 4-thread pthread_mutex contention workload for dissecting
// futex wait latency into:
//   Stage 1 (lock-holder wait): sys_enter_futex(WAIT) -> sched_wakeup
//   Stage 2 (runqueue delay):   sched_wakeup          -> sched_switch(in)

#define _GNU_SOURCE
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

static pthread_mutex_t g_lock = PTHREAD_MUTEX_INITIALIZER;
static uint64_t g_shared_counter = 0;

struct worker_cfg {
  int id;
  int iters;
  int hold_us;
  int work_us;
};

static uint64_t now_ns(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

static void busy_spin_us(int us) {
  if (us <= 0) return;
  uint64_t deadline = now_ns() + (uint64_t)us * 1000ULL;
  volatile uint64_t x = 0;
  while (now_ns() < deadline) {
    x += 1;
  }
}

static void *worker_fn(void *arg) {
  struct worker_cfg *cfg = (struct worker_cfg *)arg;
  for (int i = 0; i < cfg->iters; ++i) {
    pthread_mutex_lock(&g_lock);
    busy_spin_us(cfg->hold_us);
    g_shared_counter++;
    pthread_mutex_unlock(&g_lock);
    // Optional outside-lock CPU burn to keep runqueue busy so stage 2 shows up clearly.
    busy_spin_us(cfg->work_us);
  }
  return NULL;
}

int main(int argc, char **argv) {
  int nthreads = argc > 1 ? atoi(argv[1]) : 4;
  int iters = argc > 2 ? atoi(argv[2]) : 1500;
  int hold_us = argc > 3 ? atoi(argv[3]) : 200;
  int work_us = argc > 4 ? atoi(argv[4]) : 50;

  if (nthreads < 1 || nthreads > 32) {
    fprintf(stderr, "nthreads must be in [1, 32]\n");
    return 1;
  }

  pthread_t *threads = calloc((size_t)nthreads, sizeof(*threads));
  struct worker_cfg *cfgs = calloc((size_t)nthreads, sizeof(*cfgs));
  if (!threads || !cfgs) {
    return 1;
  }

  uint64_t t0 = now_ns();
  for (int i = 0; i < nthreads; ++i) {
    cfgs[i].id = i;
    cfgs[i].iters = iters;
    cfgs[i].hold_us = hold_us;
    cfgs[i].work_us = work_us;
    pthread_create(&threads[i], NULL, worker_fn, &cfgs[i]);
  }
  for (int i = 0; i < nthreads; ++i) {
    pthread_join(threads[i], NULL);
  }
  uint64_t t1 = now_ns();

  printf("futex_bench threads=%d iters=%d hold_us=%d work_us=%d total_ops=%llu elapsed_ms=%.1f\n",
         nthreads, iters, hold_us, work_us,
         (unsigned long long)g_shared_counter, (double)(t1 - t0) / 1e6);

  free(threads);
  free(cfgs);
  return 0;
}
