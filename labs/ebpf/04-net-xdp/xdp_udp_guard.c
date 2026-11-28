// Userspace loader for xdp_udp_guard (XDP generic/SKB mode).

#include <arpa/inet.h>
#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <linux/if_link.h>
#include <net/if.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "xdp_udp_guard.skel.h"

struct ip_stat {
  uint64_t rx_pkts;
  uint64_t drop_pkts;
  uint64_t window_sec;
  uint64_t window_pkts;
};

static volatile sig_atomic_t g_stop = 0;

static void on_sig(int sig) {
  (void)sig;
  g_stop = 1;
}

int main(int argc, char **argv) {
  const char *iface = "eth0";
  uint32_t mode = 0;  // 0=count, 1=drop, 2=ratelimit
  uint16_t port = 19999;
  uint32_t match_icmp = 0;
  uint64_t max_pps = 200;
  int duration_sec = 0;

  for (int i = 1; i < argc; ++i) {
    if (strcmp(argv[i], "--iface") == 0 && i + 1 < argc) {
      iface = argv[++i];
    } else if (strcmp(argv[i], "--mode") == 0 && i + 1 < argc) {
      const char *m = argv[++i];
      if (strcmp(m, "count") == 0) mode = 0;
      else if (strcmp(m, "drop") == 0) mode = 1;
      else if (strcmp(m, "ratelimit") == 0) mode = 2;
      else {
        fprintf(stderr, "Unknown mode: %s (use count|drop|ratelimit)\n", m);
        return 1;
      }
    } else if (strcmp(argv[i], "--port") == 0 && i + 1 < argc) {
      port = (uint16_t)strtoul(argv[++i], NULL, 10);
    } else if (strcmp(argv[i], "--icmp") == 0) {
      match_icmp = 1;
    } else if (strcmp(argv[i], "--max-pps") == 0 && i + 1 < argc) {
      max_pps = (uint64_t)strtoull(argv[++i], NULL, 10);
    } else if (strcmp(argv[i], "--duration") == 0 && i + 1 < argc) {
      duration_sec = atoi(argv[++i]);
    }
  }

  unsigned int ifindex = if_nametoindex(iface);
  if (ifindex == 0) {
    fprintf(stderr, "Invalid interface %s: %s\n", iface, strerror(errno));
    return 1;
  }

  signal(SIGINT, on_sig);
  signal(SIGTERM, on_sig);

  struct xdp_udp_guard_bpf *skel = xdp_udp_guard_bpf__open();
  if (!skel) {
    fprintf(stderr, "Failed to open XDP skeleton\n");
    return 1;
  }
  skel->rodata->mode = mode;
  skel->rodata->target_udp_port = port;
  skel->rodata->match_icmp = match_icmp;
  skel->rodata->max_pps = max_pps;

  if (xdp_udp_guard_bpf__load(skel)) {
    fprintf(stderr, "Failed to load XDP program\n");
    xdp_udp_guard_bpf__destroy(skel);
    return 1;
  }

  int prog_fd = bpf_program__fd(skel->progs.xdp_udp_guard);
  int err = bpf_xdp_attach((int)ifindex, prog_fd, XDP_FLAGS_SKB_MODE, NULL);
  if (err) {
    fprintf(stderr, "bpf_xdp_attach(%s, SKB_MODE) failed: %d (%s)\n",
            iface, err, strerror(-err));
    xdp_udp_guard_bpf__destroy(skel);
    return 1;
  }

  const char *mode_name = mode == 0 ? "count" : (mode == 1 ? "drop" : "ratelimit");
  printf("XDP attached on %s (SKB mode) proto=%s port=%u mode=%s max_pps=%llu\n",
         iface, match_icmp ? "ICMP-echo" : "UDP", port, mode_name,
         (unsigned long long)max_pps);
  fflush(stdout);

  int elapsed = 0;
  while (!g_stop) {
    sleep(1);
    elapsed++;
    if (duration_sec > 0 && elapsed >= duration_sec) {
      break;
    }
  }

  printf("XDP totals: matched=%llu passed=%llu dropped=%llu\n",
         (unsigned long long)skel->bss->rx_matched,
         (unsigned long long)skel->bss->rx_passed,
         (unsigned long long)skel->bss->rx_dropped);

  int map_fd = bpf_map__fd(skel->maps.ip_stats);
  uint32_t key = 0, next_key = 0;
  int has_prev = 0;
  while (bpf_map_get_next_key(map_fd, has_prev ? &key : NULL, &next_key) == 0) {
    struct ip_stat st = {0};
    if (bpf_map_lookup_elem(map_fd, &next_key, &st) == 0) {
      struct in_addr addr = {.s_addr = next_key};
      char ipbuf[INET_ADDRSTRLEN];
      inet_ntop(AF_INET, &addr, ipbuf, sizeof(ipbuf));
      printf("  per-src-ip: rx=%llu drop=%llu\n",
             (unsigned long long)st.rx_pkts,
             (unsigned long long)st.drop_pkts);
    }
    key = next_key;
    has_prev = 1;
  }

  bpf_xdp_detach((int)ifindex, XDP_FLAGS_SKB_MODE, NULL);
  xdp_udp_guard_bpf__destroy(skel);
  return 0;
}
