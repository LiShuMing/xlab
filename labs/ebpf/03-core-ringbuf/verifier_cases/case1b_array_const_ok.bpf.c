// Verifier Case 1b (LINUX 7.0 STATIC NON-NULL PROOF):
// Unlike BPF_MAP_TYPE_HASH, BPF_MAP_TYPE_ARRAY preallocates all slots.
// When the key is a compile-time constant within max_entries, modern Linux
// verifiers statically prove the returned pointer is non-null (PTR_TO_MAP_VALUE)
// and accept direct dereference without a NULL check.
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>

char LICENSE[] SEC("license") = "GPL";

struct {
  __uint(type, BPF_MAP_TYPE_ARRAY);
  __uint(max_entries, 1);
  __type(key, u32);
  __type(value, u64);
} arr_map SEC(".maps");

SEC("tracepoint/syscalls/sys_enter_getpid")
int array_const_key_ok(void *ctx) {
  (void)ctx;
  u32 key = 0;
  u64 *val = bpf_map_lookup_elem(&arr_map, &key);
  *val += 1;
  return 0;
}
