// Userspace loader & BPF RingBuffer consumer for exec_rw_trace.

#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "common.h"
#include "exec_rw_trace.skel.h"

static volatile sig_atomic_t g_stop = 0;
static uint64_t g_evt_counts[5] = {0};
static int g_max_print = 25;
static int g_printed = 0;

static void on_sig(int sig) {
  (void)sig;
  g_stop = 1;
}

static int handle_rb_event(void *ctx, void *data, size_t data_sz) {
  (void)ctx;
  if (data_sz < sizeof(struct rb_event)) return 0;
  const struct rb_event *e = (const struct rb_event *)data;
  if (e->kind <= 4) g_evt_counts[e->kind]++;

  if (g_printed < g_max_print) {
    if (e->kind == EVT_EXEC) {
      printf("[EXEC ] pid=%-6u ppid=%-6u comm=%-15s file=%s\n",
             e->pid, e->ppid, e->comm, e->filename);
    } else if (e->kind == EVT_EXIT) {
      printf("[EXIT ] pid=%-6u ppid=%-6u comm=%-15s code=%-3lld life_ms=%.3f\n",
             e->pid, e->ppid, e->comm, e->ret, (double)e->duration_ns / 1e6);
    } else if (e->kind == EVT_READ) {
      printf("[READ ] pid=%-6u comm=%-15s fd=%-3u bytes=%-6lld lat_us=%.2f\n",
             e->pid, e->comm, e->fd, e->ret, (double)e->duration_ns / 1e3);
    } else if (e->kind == EVT_WRITE) {
      printf("[WRITE] pid=%-6u comm=%-15s fd=%-3u bytes=%-6lld lat_us=%.2f\n",
             e->pid, e->comm, e->fd, e->ret, (double)e->duration_ns / 1e3);
    }
    g_printed++;
  }
  return 0;
}

static void print_hist(int map_fd, const char *title, uint32_t base_slot) {
  uint64_t vals[HIST_SLOTS] = {0};
  uint64_t total = 0;
  for (uint32_t i = 0; i < HIST_SLOTS; ++i) {
    uint32_t key = base_slot + i;
    if (bpf_map_lookup_elem(map_fd, &key, &vals[i]) == 0) {
      total += vals[i];
    }
  }
  if (total == 0) return;
  printf("\n--- %s (total=%llu) ---\n", title, (unsigned long long)total);
  for (uint32_t i = 0; i < HIST_SLOTS; ++i) {
    if (vals[i] == 0) continue;
    uint64_t lo = i == 0 ? 0 : (1ULL << i);
    uint64_t hi = (1ULL << (i + 1)) - 1;
    printf("  [%6llu, %6llu] us : %llu\n",
           (unsigned long long)lo, (unsigned long long)hi,
           (unsigned long long)vals[i]);
  }
}

int main(int argc, char **argv) {
  uint32_t target_pid = 0;
  uint32_t trace_exec_exit = 1;
  int duration_sec = 0;

  for (int i = 1; i < argc; ++i) {
    if (strcmp(argv[i], "--pid") == 0 && i + 1 < argc) {
      target_pid = (uint32_t)strtoul(argv[++i], NULL, 10);
    } else if (strcmp(argv[i], "--no-exec") == 0) {
      trace_exec_exit = 0;
    } else if (strcmp(argv[i], "--duration") == 0 && i + 1 < argc) {
      duration_sec = atoi(argv[++i]);
    } else if (strcmp(argv[i], "--max-print") == 0 && i + 1 < argc) {
      g_max_print = atoi(argv[++i]);
    }
  }

  signal(SIGINT, on_sig);
  signal(SIGTERM, on_sig);

  struct exec_rw_trace_bpf *skel = exec_rw_trace_bpf__open();
  if (!skel) {
    fprintf(stderr, "Failed to open skeleton\n");
    return 1;
  }
  skel->rodata->target_pid = target_pid;
  skel->rodata->trace_exec_exit = trace_exec_exit;

  if (exec_rw_trace_bpf__load(skel)) {
    fprintf(stderr, "Failed to load BPF program\n");
    exec_rw_trace_bpf__destroy(skel);
    return 1;
  }
  if (exec_rw_trace_bpf__attach(skel)) {
    fprintf(stderr, "Failed to attach BPF program\n");
    exec_rw_trace_bpf__destroy(skel);
    return 1;
  }

  struct ring_buffer *rb =
      ring_buffer__new(bpf_map__fd(skel->maps.rb), handle_rb_event, NULL, NULL);
  if (!rb) {
    fprintf(stderr, "Failed to create ring buffer\n");
    exec_rw_trace_bpf__destroy(skel);
    return 1;
  }

  printf("RingBuffer tracer active (target_pid=%u trace_exec_exit=%u)...\n",
         target_pid, trace_exec_exit);
  fflush(stdout);

  int ticks = 0;
  while (!g_stop) {
    int err = ring_buffer__poll(rb, 100);
    if (err == -EINTR) break;
    if (err < 0) {
      fprintf(stderr, "ring_buffer__poll error: %d\n", err);
      break;
    }
    ticks++;
    if (duration_sec > 0 && ticks >= duration_sec * 10) {
      break;
    }
  }

  printf(
      "\nSummary: exec=%llu exit=%llu read=%llu write=%llu (printed first %d)\n",
      (unsigned long long)g_evt_counts[EVT_EXEC],
      (unsigned long long)g_evt_counts[EVT_EXIT],
      (unsigned long long)g_evt_counts[EVT_READ],
      (unsigned long long)g_evt_counts[EVT_WRITE], g_printed);

  int hist_fd = bpf_map__fd(skel->maps.rw_lat_hist);
  print_hist(hist_fd, "READ latency histogram", 0);
  print_hist(hist_fd, "WRITE latency histogram", HIST_SLOTS);

  ring_buffer__free(rb);
  exec_rw_trace_bpf__destroy(skel);
  return 0;
}
