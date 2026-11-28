# 04 — 网络数据面实验：TCP `tc netem` 观测与 XDP（SKB 模式）拦截

## 前置条件

- Linux 5.8+，`bpftrace`、`clang`、`bpftool`、`libbpf-dev`、`iproute2`（`ip` / `tc`）、`python3`、`sudo`

## 实验内容

### 4A. TCP 观测（`tcp_trace.bt` + `tc netem`）
- 挂接 `tracepoint:tcp:tcp_probe` 与 `tracepoint:tcp:tcp_retransmit_skb`，统计每条流的 SRTT（μs）、`snd_cwnd` 分布与重传次数。
- 默认脚本在独立 `veth` + `netns` 中对照「无损伤链路」与「`tc netem delay 20ms 5ms loss 1%`」，不干扰宿主 SSH 连接；也可对 `eth0` 指定端口（如 `22`）观测真实跨机 TCP 流。

### 4B. XDP 改包/拦截（`xdp_udp_guard`）
- 约 110 行 XDP 程序，使用 `XDP_FLAGS_SKB_MODE`（generic 模式，兼容云主机虚拟网卡与 `veth`）。
- 支持三种模式：
  - `count`：按目标 UDP 端口（或 `--icmp` 匹配 ICMP Echo）统计全局与按源 IP 包数并 `XDP_PASS`。
  - `ratelimit`：按源 IP 固定 1 秒窗口限速（`--max-pps`），超限包在协议栈入口前直接 `XDP_DROP`。
  - `drop`：匹配报文全部 `XDP_DROP`，对比应用层 socket 实收包数验证协议栈入口前拦截效果。

## 构建与运行

```sh
make all
./run_net_lab.sh
```
