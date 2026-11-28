// Verifier Case 1 (FIXED): Check HASH map lookup pointer before dereferencing.
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>

char LICENSE[] SEC("license") = "GPL";

struct {
  __uint(type, BPF_MAP_TYPE_HASH);
  __uint(max_entries, 64);
  __type(key, u32);
  __type(value, u64);
} cnt_map SEC(".maps");

SEC("tracepoint/syscalls/sys_enter_getpid")
int fixed_null_deref(void *ctx) {
  (void)ctx;
  u32 key = (u32)(bpf_get_current_pid_tgid() >> 32);
  u64 *val = bpf_map_lookup_elem(&cnt_map, &key);
  if (!val) return 0;
  *val += 1;
  return 0;
}
