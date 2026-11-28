// Verifier Case 2 (FIXED): Clamp loop bound so the verifier can prove termination.
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>

char LICENSE[] SEC("license") = "GPL";

struct {
  __uint(type, BPF_MAP_TYPE_ARRAY);
  __uint(max_entries, 1);
  __type(key, u32);
  __type(value, u64);
} cfg_map SEC(".maps");

SEC("tracepoint/syscalls/sys_enter_getpid")
int fixed_bounded_loop(void *ctx) {
  (void)ctx;
  u32 key = 0;
  u64 *limit = bpf_map_lookup_elem(&cfg_map, &key);
  if (!limit) return 0;

  u64 n = *limit;
  if (n > 32) n = 32;  // Provable upper bound for verifier.

  u64 acc = 0;
  #pragma clang loop unroll(disable)
  for (u64 i = 0; i < 32; ++i) {
    if (i >= n) break;
    acc += bpf_get_prandom_u32();
  }
  *limit = acc;
  return 0;
}
