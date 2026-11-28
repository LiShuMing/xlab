/*
 * Userspace loader for the minimal sched_ext scheduler (scx_prio_fifo).
 *
 * Usage:
 *   sudo ./bin/scx_prio_fifo [--pid TGID] [--short-us US] [--duration SEC]
 */

#include <bpf/libbpf.h>
#include <errno.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "scx_prio_fifo.skel.h"

static volatile sig_atomic_t g_stop = 0;

static void OnSignal(int sig) {
  (void)sig;
  g_stop = 1;
}

static int LibbpfPrintFn(enum libbpf_print_level level, const char *fmt,
                         va_list args) {
  if (level == LIBBPF_DEBUG) {
    return 0;
  }
  return vfprintf(stderr, fmt, args);
}

static void PrintUsage(const char *prog) {
  fprintf(stderr,
          "Usage: %s [--pid TGID] [--short-us US] [--no-preempt] [--stall-test] [--duration SEC]\n"
          "  --pid TGID      Prioritize all threads of TGID in DSQ_HIGH (default: 0)\n"
          "  --short-us US   Auto-prioritize tasks with last_run < US (default: 500)\n"
          "  --no-preempt    Keep DSQ_HIGH priority but disable SCX_KICK_PREEMPT\n"
          "  --stall-test    Withhold dispatch with timeout_ms=2000 to verify SCX watchdog\n"
          "  --duration SEC  Auto-exit after SEC seconds (0 = until Ctrl-C)\n",
          prog);
}

int main(int argc, char **argv) {
  uint32_t target_pid = 0;
  uint64_t short_us = 500;
  uint32_t enable_preempt = 1;
  uint32_t simulate_stall = 0;
  int duration_sec = 0;

  for (int i = 1; i < argc; ++i) {
    if (strcmp(argv[i], "--pid") == 0 && i + 1 < argc) {
      target_pid = (uint32_t)strtoul(argv[++i], NULL, 10);
    } else if (strcmp(argv[i], "--short-us") == 0 && i + 1 < argc) {
      short_us = strtoull(argv[++i], NULL, 10);
    } else if (strcmp(argv[i], "--no-preempt") == 0) {
      enable_preempt = 0;
    } else if (strcmp(argv[i], "--stall-test") == 0) {
      simulate_stall = 1;
    } else if (strcmp(argv[i], "--duration") == 0 && i + 1 < argc) {
      duration_sec = atoi(argv[++i]);
    } else {
      PrintUsage(argv[0]);
      return 1;
    }
  }

  libbpf_set_print(LibbpfPrintFn);
  signal(SIGINT, OnSignal);
  signal(SIGTERM, OnSignal);

  struct scx_prio_fifo_bpf *skel = scx_prio_fifo_bpf__open();
  if (!skel) {
    fprintf(stderr, "Failed to open BPF skeleton\n");
    return 1;
  }

  skel->rodata->target_tgid = target_pid;
  skel->rodata->short_task_ns = short_us * 1000ULL;
  skel->rodata->enable_preempt = enable_preempt;
  skel->rodata->simulate_stall = simulate_stall;
  if (simulate_stall) {
    skel->struct_ops.prio_fifo_ops->timeout_ms = 2000;
  }

  int err = scx_prio_fifo_bpf__load(skel);
  if (err) {
    fprintf(stderr, "Failed to load BPF skeleton: %d (%s)\n", err, strerror(-err));
    scx_prio_fifo_bpf__destroy(skel);
    return 1;
  }

  struct bpf_link *link = bpf_map__attach_struct_ops(skel->maps.prio_fifo_ops);
  if (!link) {
    err = -errno;
    fprintf(stderr, "Failed to attach sched_ext struct_ops: %d (%s)\n", err,
            strerror(-err));
    scx_prio_fifo_bpf__destroy(skel);
    return 1;
  }

  printf("scx_prio_fifo attached! target_tgid=%u short_task_us=%llu preempt=%u stall_test=%u\n",
         target_pid, (unsigned long long)short_us, enable_preempt, simulate_stall);
  fflush(stdout);

  int elapsed = 0;
  while (!g_stop && skel->bss->exit_kind == 0) {
    sleep(1);
    elapsed++;
    printf("t=%2ds  local=%-8llu high=%-8llu normal=%-8llu preempt_kicks=%llu\n",
           elapsed,
           (unsigned long long)skel->bss->nr_local_dispatches,
           (unsigned long long)skel->bss->nr_high_enqueues,
           (unsigned long long)skel->bss->nr_normal_enqueues,
           (unsigned long long)skel->bss->nr_high_preempt_kicks);
    fflush(stdout);
    if (duration_sec > 0 && elapsed >= duration_sec) {
      break;
    }
  }

  bpf_link__destroy(link);
  printf("scx_prio_fifo detached (exit_kind=%llu reason=\"%s\"). Reverted to default scheduler.\n",
         (unsigned long long)skel->bss->exit_kind, skel->bss->exit_reason);
  scx_prio_fifo_bpf__destroy(skel);
  return 0;
}
