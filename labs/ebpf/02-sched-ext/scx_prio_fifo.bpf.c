// SPDX-License-Identifier: GPL-2.0
/*
 * Minimal Linux 7.0 sched_ext (scx) scheduler: Global FIFO + Priority DSQ.
 *
 * Policy:
 *   - DSQ_HIGH (id=1): priority FIFO queue for either a pinned target_tgid or
 *     short-burst tasks whose last on-CPU run was shorter than short_task_ns.
 *   - DSQ_NORMAL (id=2): default global FIFO queue for CPU-bound tasks.
 *   - Idle CPUs take the fast path (SCX_DSQ_LOCAL) in select_cpu().
 *   - dispatch() always drains DSQ_HIGH before DSQ_NORMAL.
 *   - Built-in kernel watchdog (timeout_ms = 5000) automatically unloads and
 *     reverts to EEVDF if the scheduler ever stalls.
 */

#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

char _license[] SEC("license") = "GPL";

#define DSQ_HIGH   1ULL
#define DSQ_NORMAL 2ULL

/* Kernel sched_ext kfuncs (Linux 7.0 BTF signatures). */
extern s32 scx_bpf_create_dsq(u64 dsq_id, s32 node) __ksym;
extern s32 scx_bpf_select_cpu_dfl(struct task_struct *p, s32 prev_cpu,
                                  u64 wake_flags, bool *is_idle) __ksym;
extern void scx_bpf_dsq_insert(struct task_struct *p, u64 dsq_id,
                               u64 slice, u64 enq_flags) __ksym;
extern bool scx_bpf_dsq_move_to_local(u64 dsq_id) __ksym;
extern void scx_bpf_kick_cpu(s32 cpu, u64 flags) __ksym;
extern u64 scx_bpf_now(void) __ksym;

/* Userspace-configurable knobs (set in skeleton rodata before load). */
const volatile unsigned int target_tgid = 0;
const volatile unsigned long long short_task_ns = 500000ULL;     /* 500 us */
const volatile unsigned long long high_slice_ns = 2000000ULL;    /* 2 ms */
const volatile unsigned long long normal_slice_ns = 20000000ULL; /* 20 ms */
const volatile unsigned int enable_preempt = 1;                  /* 0 = no SCX_KICK_PREEMPT */
const volatile unsigned int simulate_stall = 0;                  /* 1 = trigger watchdog test */

/* Live counters read by userspace loader. */
unsigned long long nr_local_dispatches = 0;
unsigned long long nr_high_enqueues = 0;
unsigned long long nr_normal_enqueues = 0;
unsigned long long nr_high_preempt_kicks = 0;
unsigned long long exit_kind = 0;
char exit_reason[64] = {};

struct task_ctx {
  u64 run_start_ns;
  u64 last_run_ns;
};

struct {
  __uint(type, BPF_MAP_TYPE_TASK_STORAGE);
  __uint(map_flags, BPF_F_NO_PREALLOC);
  __type(key, int);
  __type(value, struct task_ctx);
} task_ctx_map SEC(".maps");

static __always_inline bool is_high_prio(struct task_struct *p) {
  if (target_tgid != 0 && p->tgid == (s32)target_tgid) {
    return true;
  }
  if (short_task_ns > 0) {
    struct task_ctx *tctx = bpf_task_storage_get(&task_ctx_map, p, 0, 0);
    if (tctx && tctx->last_run_ns > 0 && tctx->last_run_ns < short_task_ns) {
      return true;
    }
  }
  return false;
}

SEC("struct_ops/prio_fifo_select_cpu")
s32 BPF_PROG(prio_fifo_select_cpu, struct task_struct *p, s32 prev_cpu,
             u64 wake_flags) {
  bool is_idle = false;
  s32 cpu = scx_bpf_select_cpu_dfl(p, prev_cpu, wake_flags, &is_idle);

  if (is_idle) {
    u64 slice = is_high_prio(p) ? high_slice_ns : normal_slice_ns;
    scx_bpf_dsq_insert(p, SCX_DSQ_LOCAL, slice, 0);
    __sync_fetch_and_add(&nr_local_dispatches, 1);
  }
  return cpu;
}

SEC("struct_ops/prio_fifo_enqueue")
void BPF_PROG(prio_fifo_enqueue, struct task_struct *p, u64 enq_flags) {
  if (is_high_prio(p)) {
    scx_bpf_dsq_insert(p, DSQ_HIGH, high_slice_ns, enq_flags);
    __sync_fetch_and_add(&nr_high_enqueues, 1);
    /* Preempt CPU 0 immediately when the explicitly prioritized TGID wakes up. */
    if (enable_preempt && target_tgid != 0 && p->tgid == (s32)target_tgid) {
      scx_bpf_kick_cpu(0, SCX_KICK_PREEMPT);
      __sync_fetch_and_add(&nr_high_preempt_kicks, 1);
    }
  } else {
    scx_bpf_dsq_insert(p, DSQ_NORMAL, normal_slice_ns, enq_flags);
    __sync_fetch_and_add(&nr_normal_enqueues, 1);
  }
}

SEC("struct_ops/prio_fifo_dispatch")
void BPF_PROG(prio_fifo_dispatch, s32 cpu, struct task_struct *prev) {
  (void)cpu;
  (void)prev;
  if (simulate_stall) {
    /* Deliberately withhold dispatch so SCX_WATCHDOG triggers automatic eject. */
    return;
  }
  if (scx_bpf_dsq_move_to_local(DSQ_HIGH)) {
    return;
  }
  scx_bpf_dsq_move_to_local(DSQ_NORMAL);
}

SEC("struct_ops/prio_fifo_running")
void BPF_PROG(prio_fifo_running, struct task_struct *p) {
  struct task_ctx *tctx = bpf_task_storage_get(&task_ctx_map, p, 0,
                                               BPF_LOCAL_STORAGE_GET_F_CREATE);
  if (tctx) {
    tctx->run_start_ns = scx_bpf_now();
  }
}

SEC("struct_ops/prio_fifo_stopping")
void BPF_PROG(prio_fifo_stopping, struct task_struct *p, bool runnable) {
  (void)runnable;
  struct task_ctx *tctx = bpf_task_storage_get(&task_ctx_map, p, 0, 0);
  if (tctx && tctx->run_start_ns > 0) {
    u64 now = scx_bpf_now();
    if (now > tctx->run_start_ns) {
      tctx->last_run_ns = now - tctx->run_start_ns;
    }
  }
}

SEC("struct_ops.s/prio_fifo_init")
s32 BPF_PROG(prio_fifo_init) {
  s32 ret = scx_bpf_create_dsq(DSQ_HIGH, -1);
  if (ret) {
    return ret;
  }
  return scx_bpf_create_dsq(DSQ_NORMAL, -1);
}

SEC("struct_ops/prio_fifo_exit")
void BPF_PROG(prio_fifo_exit, struct scx_exit_info *ei) {
  if (ei) {
    exit_kind = ei->kind;
    if (ei->reason) {
      bpf_probe_read_kernel_str(exit_reason, sizeof(exit_reason), ei->reason);
    }
  }
}

SEC(".struct_ops.link")
struct sched_ext_ops prio_fifo_ops = {
    .select_cpu = (void *)prio_fifo_select_cpu,
    .enqueue    = (void *)prio_fifo_enqueue,
    .dispatch   = (void *)prio_fifo_dispatch,
    .running    = (void *)prio_fifo_running,
    .stopping   = (void *)prio_fifo_stopping,
    .init       = (void *)prio_fifo_init,
    .exit       = (void *)prio_fifo_exit,
    .flags      = SCX_OPS_KEEP_BUILTIN_IDLE,
    .timeout_ms = 5000,
    .name       = "prio_fifo",
};
