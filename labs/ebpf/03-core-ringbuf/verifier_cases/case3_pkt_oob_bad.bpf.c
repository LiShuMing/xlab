// Verifier Case 3 (BAD): Reading XDP packet bytes without checking data_end.
#include "vmlinux.h"
#include <bpf/bpf_endian.h>
#include <bpf/bpf_helpers.h>

char LICENSE[] SEC("license") = "GPL";

SEC("xdp")
int bad_pkt_oob(struct xdp_md *ctx) {
  struct ethhdr *eth = (void *)(long)ctx->data;
  // BUG: Missing `if ((void *)(eth + 1) > (void *)(long)ctx->data_end) return XDP_PASS;`
  if (eth->h_proto == bpf_htons(0x0800)) {
    return XDP_DROP;
  }
  return XDP_PASS;
}
