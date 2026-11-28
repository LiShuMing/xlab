// Verifier Case 2 (BAD): Loop with dynamic, verifier-unbounded upper limit.
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
int bad_unbounded_loop(void *ctx) {
  (void)ctx;
  u32 key = 0;
  u64 *limit = bpf_map_lookup_elem(&cfg_map, &key);
  if (!limit) return 0;

  u64 acc = 0;
  // BUG: *limit is an arbitrary u64 from a map; verifier cannot prove termination.
  #pragma clang loop unroll(disable)
  for (u64 i = 0; i < *limit; ++i) {
    acc += bpf_get_prandom_u32();
  }
  *limit = acc;
  return 0;
}
