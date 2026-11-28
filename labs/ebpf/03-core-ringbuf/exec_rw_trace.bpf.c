// Experiment 3: Modern libbpf + CO-RE + BPF RingBuffer tracer.
//
// Tracks two complementary views in one CO-RE BPF object:
//   1) Short-lived process lifecycle (sched_process_exec -> sched_process_exit)
//      streamed to userspace via BPF_MAP_TYPE_RINGBUF.
//   2) Target-PID read/write syscall latency & byte counts streamed via
//      RingBuffer plus in-kernel log2 latency histograms (per-op slots).

#include "vmlinux.h"
#include <bpf/bpf_core_read.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

#include "common.h"

char LICENSE[] SEC("license") = "Dual BSD/GPL";

const volatile unsigned int target_pid = 0;       // 0 = trace all PIDs for exec/exit; >0 also traces R/W for this PID
const volatile unsigned int trace_exec_exit = 1;  // 1 = stream exec/exit events

struct {
  __uint(type, BPF_MAP_TYPE_RINGBUF);
  __uint(max_entries, 256 * 1024);
} rb SEC(".maps");

struct {
  __uint(type, BPF_MAP_TYPE_HASH);
  __uint(max_entries, 8192);
  __type(key, u32);
  __type(value, u64);
} exec_start SEC(".maps");

struct rw_inflight {
  u64 ts_ns;
  u32 fd;
  u32 op;  // EVT_READ or EVT_WRITE
};

struct {
  __uint(type, BPF_MAP_TYPE_HASH);
  __uint(max_entries, 8192);
  __type(key, u32);
  __type(value, struct rw_inflight);
} rw_start SEC(".maps");

// Slots [0..31] = read latency log2(us), [32..63] = write latency log2(us).
struct {
  __uint(type, BPF_MAP_TYPE_ARRAY);
  __uint(max_entries, HIST_SLOTS * 2);
  __type(key, u32);
  __type(value, u64);
} rw_lat_hist SEC(".maps");

static __always_inline u32 log2_u64(u64 v) {
  u32 r = 0;
  // Bounded 6-step binary search (verifier-friendly, zero loop back-edges).
  if (v >= (1ULL << 32)) { v >>= 32; r += 32; }
  if (v >= (1ULL << 16)) { v >>= 16; r += 16; }
  if (v >= (1ULL << 8))  { v >>= 8;  r += 8;  }
  if (v >= (1ULL << 4))  { v >>= 4;  r += 4;  }
  if (v >= (1ULL << 2))  { v >>= 2;  r += 2;  }
  if (v >= (1ULL << 1))  { r += 1; }
  return r;
}

SEC("tp/sched/sched_process_exec")
int handle_exec(struct trace_event_raw_sched_process_exec *ctx) {
  if (!trace_exec_exit) return 0;

  u64 pid_tgid = bpf_get_current_pid_tgid();
  u32 pid = pid_tgid >> 32;
  u64 ts = bpf_ktime_get_ns();
  bpf_map_update_elem(&exec_start, &pid, &ts, BPF_ANY);

  struct rb_event *e = bpf_ringbuf_reserve(&rb, sizeof(*e), 0);
  if (!e) return 0;

  struct task_struct *task = (struct task_struct *)bpf_get_current_task();
  e->kind = EVT_EXEC;
  e->pid = pid;
  e->ppid = BPF_CORE_READ(task, real_parent, tgid);
  e->fd = 0;
  e->ret = 0;
  e->duration_ns = 0;
  bpf_get_current_comm(&e->comm, sizeof(e->comm));

  unsigned int fname_off = ctx->__data_loc_filename & 0xFFFF;
  bpf_probe_read_str(&e->filename, sizeof(e->filename), (void *)ctx + fname_off);

  bpf_ringbuf_submit(e, 0);
  return 0;
}

SEC("tp/sched/sched_process_exit")
int handle_exit(struct trace_event_raw_sched_process_template *ctx) {
  (void)ctx;
  if (!trace_exec_exit) return 0;

  u64 pid_tgid = bpf_get_current_pid_tgid();
  u32 pid = pid_tgid >> 32;
  u32 tid = (u32)pid_tgid;
  if (pid != tid) return 0;  // Only report process leader exit.

  u64 *start_ts = bpf_map_lookup_elem(&exec_start, &pid);
  if (!start_ts) return 0;  // Only report processes we observed exec'ing.

  u64 dur = bpf_ktime_get_ns() - *start_ts;
  bpf_map_delete_elem(&exec_start, &pid);

  struct rb_event *e = bpf_ringbuf_reserve(&rb, sizeof(*e), 0);
  if (!e) return 0;

  struct task_struct *task = (struct task_struct *)bpf_get_current_task();
  e->kind = EVT_EXIT;
  e->pid = pid;
  e->ppid = BPF_CORE_READ(task, real_parent, tgid);
  e->fd = 0;
  e->ret = BPF_CORE_READ(task, exit_code) >> 8;
  e->duration_ns = dur;
  bpf_get_current_comm(&e->comm, sizeof(e->comm));
  e->filename[0] = '\0';

  bpf_ringbuf_submit(e, 0);
  return 0;
}

static __always_inline int record_rw_enter(u32 fd, u32 op) {
  u64 pid_tgid = bpf_get_current_pid_tgid();
  u32 pid = pid_tgid >> 32;
  u32 tid = (u32)pid_tgid;
  if (target_pid == 0 || pid != target_pid) return 0;

  struct rw_inflight info = {
      .ts_ns = bpf_ktime_get_ns(),
      .fd = fd,
      .op = op,
  };
  bpf_map_update_elem(&rw_start, &tid, &info, BPF_ANY);
  return 0;
}

static __always_inline int record_rw_exit(long long ret) {
  u64 pid_tgid = bpf_get_current_pid_tgid();
  u32 pid = pid_tgid >> 32;
  u32 tid = (u32)pid_tgid;
  if (target_pid == 0 || pid != target_pid) return 0;

  struct rw_inflight *info = bpf_map_lookup_elem(&rw_start, &tid);
  if (!info) return 0;

  u64 dur_ns = bpf_ktime_get_ns() - info->ts_ns;
  u32 fd = info->fd;
  u32 op = info->op;
  bpf_map_delete_elem(&rw_start, &tid);

  u32 bucket = log2_u64(dur_ns / 1000);
  if (bucket >= HIST_SLOTS) bucket = HIST_SLOTS - 1;
  u32 slot = (op == EVT_WRITE ? HIST_SLOTS : 0) + bucket;
  u64 *cnt = bpf_map_lookup_elem(&rw_lat_hist, &slot);
  if (cnt) {
    __sync_fetch_and_add(cnt, 1);
  }

  struct rb_event *e = bpf_ringbuf_reserve(&rb, sizeof(*e), 0);
  if (!e) return 0;

  e->kind = op;
  e->pid = pid;
  e->ppid = 0;
  e->fd = fd;
  e->ret = ret;
  e->duration_ns = dur_ns;
  bpf_get_current_comm(&e->comm, sizeof(e->comm));
  e->filename[0] = '\0';

  bpf_ringbuf_submit(e, 0);
  return 0;
}

SEC("tp/syscalls/sys_enter_read")
int handle_enter_read(struct trace_event_raw_sys_enter *ctx) {
  return record_rw_enter((u32)ctx->args[0], EVT_READ);
}

SEC("tp/syscalls/sys_exit_read")
int handle_exit_read(struct trace_event_raw_sys_exit *ctx) {
  return record_rw_exit(ctx->ret);
}

SEC("tp/syscalls/sys_enter_write")
int handle_enter_write(struct trace_event_raw_sys_enter *ctx) {
  return record_rw_enter((u32)ctx->args[0], EVT_WRITE);
}

SEC("tp/syscalls/sys_exit_write")
int handle_exit_write(struct trace_event_raw_sys_exit *ctx) {
  return record_rw_exit(ctx->ret);
}
