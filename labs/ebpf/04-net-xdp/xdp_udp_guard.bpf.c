// Experiment 4B: XDP packet counter, per-source-IP rate limiter, and dropper.
// Designed to run in XDP generic (SKB) mode on virtual/cloud NICs and veth.

#include "vmlinux.h"
#include <bpf/bpf_endian.h>
#include <bpf/bpf_helpers.h>

char LICENSE[] SEC("license") = "Dual BSD/GPL";

#define ETH_P_IP 0x0800
#define IPPROTO_ICMP_NUM 1
#define IPPROTO_UDP_NUM 17

enum guard_mode {
  MODE_COUNT = 0,
  MODE_DROP_ALL = 1,
  MODE_RATELIMIT = 2,
};

const volatile unsigned int mode = MODE_COUNT;
const volatile unsigned short target_udp_port = 19999;
const volatile unsigned int match_icmp = 0;  // 0 = UDP target_udp_port, 1 = ICMP echo request
const volatile unsigned long long max_pps = 200;

struct ip_stat {
  u64 rx_pkts;
  u64 drop_pkts;
  u64 window_sec;
  u64 window_pkts;
};

struct {
  __uint(type, BPF_MAP_TYPE_HASH);
  __uint(max_entries, 1024);
  __type(key, u32);
  __type(value, struct ip_stat);
} ip_stats SEC(".maps");

// Global counters visible to userspace via skel->bss.
unsigned long long rx_matched = 0;
unsigned long long rx_passed = 0;
unsigned long long rx_dropped = 0;

SEC("xdp")
int xdp_udp_guard(struct xdp_md *ctx) {
  void *data = (void *)(long)ctx->data;
  void *data_end = (void *)(long)ctx->data_end;

  struct ethhdr *eth = data;
  if ((void *)(eth + 1) > data_end) {
    return XDP_PASS;
  }
  if (eth->h_proto != bpf_htons(ETH_P_IP)) {
    return XDP_PASS;
  }

  struct iphdr *ip = (void *)(eth + 1);
  if ((void *)(ip + 1) > data_end) {
    return XDP_PASS;
  }
  u32 ihl = (u32)ip->ihl * 4;
  if (ihl < sizeof(*ip)) {
    return XDP_PASS;
  }
  void *l4 = (void *)ip + ihl;

  bool matched = false;
  if (match_icmp) {
    if (ip->protocol == IPPROTO_ICMP_NUM) {
      struct icmphdr *icmp = l4;
      if ((void *)(icmp + 1) <= data_end && icmp->type == 8) {
        matched = true;
      }
    }
  } else {
    if (ip->protocol == IPPROTO_UDP_NUM) {
      struct udphdr *udp = l4;
      if ((void *)(udp + 1) <= data_end &&
          udp->dest == bpf_htons(target_udp_port)) {
        matched = true;
      }
    }
  }

  if (!matched) {
    return XDP_PASS;
  }

  __sync_fetch_and_add(&rx_matched, 1);

  u32 src_ip = ip->saddr;
  u64 now_sec = bpf_ktime_get_ns() / 1000000000ULL;
  struct ip_stat *st = bpf_map_lookup_elem(&ip_stats, &src_ip);
  if (!st) {
    struct ip_stat init = {
        .rx_pkts = 1,
        .drop_pkts = 0,
        .window_sec = now_sec,
        .window_pkts = 1,
    };
    if (mode == MODE_DROP_ALL) {
      init.drop_pkts = 1;
      bpf_map_update_elem(&ip_stats, &src_ip, &init, BPF_ANY);
      __sync_fetch_and_add(&rx_dropped, 1);
      return XDP_DROP;
    }
    bpf_map_update_elem(&ip_stats, &src_ip, &init, BPF_ANY);
    __sync_fetch_and_add(&rx_passed, 1);
    return XDP_PASS;
  }

  __sync_fetch_and_add(&st->rx_pkts, 1);

  if (mode == MODE_DROP_ALL) {
    __sync_fetch_and_add(&st->drop_pkts, 1);
    __sync_fetch_and_add(&rx_dropped, 1);
    return XDP_DROP;
  }

  if (mode == MODE_RATELIMIT) {
    if (st->window_sec != now_sec) {
      st->window_sec = now_sec;
      st->window_pkts = 1;
    } else {
      st->window_pkts += 1;
      if (st->window_pkts > max_pps) {
        __sync_fetch_and_add(&st->drop_pkts, 1);
        __sync_fetch_and_add(&rx_dropped, 1);
        return XDP_DROP;
      }
    }
  }

  __sync_fetch_and_add(&rx_passed, 1);
  return XDP_PASS;
}
