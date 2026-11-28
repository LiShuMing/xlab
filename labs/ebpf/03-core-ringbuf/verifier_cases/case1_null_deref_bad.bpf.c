// Verifier Case 1 (BAD): Dereferencing HASH map lookup without NULL check.
// Note: Unlike BPF_MAP_TYPE_ARRAY with constant in-bounds key (which modern
// kernels may know is non-null), BPF_MAP_TYPE_HASH lookups can always miss and
// return NULL, so the verifier strictly requires a NULL check.
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
int bad_null_deref(void *ctx) {
  (void)ctx;
  u32 key = (u32)(bpf_get_current_pid_tgid() >> 32);
  u64 *val = bpf_map_lookup_elem(&cnt_map, &key);
  // BUG: Missing `if (!val) return 0;` -> verifier rejects map_value_or_null!
  *val += 1;
  return 0;
}
