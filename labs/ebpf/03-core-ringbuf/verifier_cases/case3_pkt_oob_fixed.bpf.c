// Verifier Case 3 (FIXED): Check packet bounds against data_end before reading.
#include "vmlinux.h"
#include <bpf/bpf_endian.h>
#include <bpf/bpf_helpers.h>

char LICENSE[] SEC("license") = "GPL";

SEC("xdp")
int fixed_pkt_oob(struct xdp_md *ctx) {
  void *data = (void *)(long)ctx->data;
  void *data_end = (void *)(long)ctx->data_end;
  struct ethhdr *eth = data;
  if ((void *)(eth + 1) > data_end) {
    return XDP_PASS;
  }
  if (eth->h_proto == bpf_htons(0x0800)) {
    return XDP_PASS;
  }
  return XDP_PASS;
}
