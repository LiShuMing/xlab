# eBPF 实验台实测结果

测试环境（`dev2`，脱敏记录）：
- **内核与架构**：Linux `7.0.0-38-generic` (`x86_64`, `PREEMPT_DYNAMIC`)，2 vCPU / 1.7 GiB RAM，根分区 `ext4`（`/var/tmp` 位于块设备，非 `tmpfs`）
- **eBPF 工具链**：`bpftrace v0.25.0`、`clang 21.1.8`、`bpftool v7.7.0`、`libbpf 1.7`
- **内核能力**：`/sys/kernel/btf/vmlinux` 就绪，`/sys/kernel/sched_ext` 已开启
- **跨机对端**：`dev1`（Linux `6.8.0-106-generic`，跨机 RTT ~35.4 ms）

---

## 实验 1：`bpftrace` 对照观测

### 1A. Page Cache 命中与预读行为（16 MiB 文件，4,096 × 4 KiB `pread`）

通过 `tracepoint:filemap:mm_filemap_add_to_page_cache` 与 `tracepoint:block:block_rq_issue/complete` 实时统计：

| 模式 | 耗时 (ms) | 吞吐 (MiB/s) | Page Cache 插入次数 | 块 I/O 请求数 | 块层读取总量 | 典型 Folio Order / 请求粒度 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `warm`（热缓存） | **9.70** | **1649.0** | `0` | `0` | `0 B` | 全部命中内存，无块 I/O |
| `fadv_will`（`WILLNEED` 预取） | **42.06** | **380.4** | `24` | `11` | `8.0 MiB`（前段预读已入缓存） | 大 folio（order 2~8+），I/O 合并为 512 KiB~2 MiB |
| `seq`（冷顺序读） | **51.17** | **312.7** | `30` | `20` | `16.0 MiB` | 大 folio（order 2~8+），14 次 `[1M, 2M)` 合并读 |
| `rand`（冷随机读，默认预读） | **1531.00** | **10.5** | `3,960` | `2,813` | `14.7 MiB` | order 0 为主，但默认预读仍触发 8~128 KiB 放大请求 |
| `fadv_rand`（`POSIX_FADV_RANDOM`） | **1856.00** | **8.6** | `2,530` | `2,530` | `9.9 MiB` | **100% order 0 + 100% 4 KiB 请求**，零预读浪费 |

**关键结论**：
1. `seq` / `fadv_will` 在 Linux 7.0 下通过大 folio（order 最高达 8+）把 4,096 次 4 KiB 读合并为仅 **11~20 次** 1~2 MiB 块请求，吞吐比随机读高 **36~44 倍**。
2. `fadv_rand` 彻底关闭预读后，块层读放大消失（读总量从 `14.7 MiB` 降至精确命中独立页的 `9.9 MiB`，请求大小全部落在 `[4K, 8K)`）。
3. 工程细节：若测试文件建在 `tmpfs`（如 `/tmp`），`drop_caches` 不会驱逐页面且不触发 `block_rq_*`，必须落在真实块设备文件系统（`/var/tmp`）。

### 1B. Futex 锁竞争「两段延迟」拆解（4 线程争抢单把 `pthread_mutex`，2 vCPU）

将一次 `FUTEX_WAIT` 拆解为：
- **Stage 1（等持锁者释放）**：`sys_enter_futex` → `sched:sched_wakeup`
- **Stage 2（唤醒后 runqueue 排队上 CPU）**：`sched:sched_wakeup` → `sched:sched_switch(next_pid)`

| 负载配置 (`hold_us / work_us`) | `FUTEX_WAIT` 次数 | Stage 1 累计 (us) | Stage 2 累计 (us) | 总等待累计 (us) | **Stage 2 占比** | 现象特征 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `200 us / 10 us`（锁内重、锁外轻） | `2,624` | `2,564,751` | `81,336` | `2,653,469` | **3.1%** | 锁外几乎不占 CPU，唤醒后 `[2, 4) us` 立刻上核 |
| `200 us / 400 us`（锁外 CPU 密集） | `1,574` | `1,508,032` | `641,722` | `2,153,767` | **29.8%** | Stage 2 呈现明显**双峰**：一半 `[2, 4) us`，另一半在 2 核 runqueue 积压 `[256, 2000) us` |

两段之和与实测 `sys_enter_futex → sys_exit_futex` 总耗时吻合度超过 **99.7%**，直接区分了「真锁竞争」与「CPU 过载导致的唤醒排队」。

---

## 实验 2：Linux 7.0 手写极简 `sched_ext` 调度器

在 2 vCPU 机器上同时跑 **4 个吃满 CPU 的竞争进程（`hog`）** + **1 个周期性低延迟探针进程（`probe`，每 15 ms 唤醒做固定短计算，采样 150 次）**，切换三种调度器对比：

| 调度器模式 | `sched_ext` 状态 | 唤醒延迟 p50 (us) | 唤醒延迟 p95 (us) | **唤醒延迟 p99 (us)** | 总响应 p99 (us) | 调度计数 / 备注 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| **1) 默认 Linux 7.0 EEVDF** | `disabled` | `88` | `2,368` | **`3,377`** | `3,502` | 基线公平调度 |
| **2) `sched_ext` 全局 FIFO**（`--short-us 0`，20 ms slice） | `enabled (prio_fifo)` | `26,865` | `39,893` | **`41,774`** | `41,984` | `normal=2782`，探针被迫排在两个 20 ms CPU hog 之后 |
| **3) `sched_ext` 优先 DSQ + 抢占 Kick**（`--pid` + `--short-us 500`） | `enabled (prio_fifo)` | `207` | **`593`** | **`858`** | **`984`** | `high=1692 / normal=406 / preempt_kicks=151`；卸载后 `exit_kind=64` 无缝回退 EEVDF |

**关键结论**：
- 相比全局 FIFO，优先 DSQ + `SCX_KICK_PREEMPT` 将探针 p99 唤醒延迟从 **`41.8 ms`** 压低至 **`0.86 ms`**（**48.7× 降低**）；
- 即使对比默认 Linux 7.0 EEVDF，在 200% CPU 过载下依然把 p99 唤醒延迟从 **`3.38 ms`** 压低至 **`0.86 ms`**（**3.9× 降低**），实现亚毫秒级响应。

---

## 实验 3：`libbpf + CO-RE + RingBuffer` 与 BPF Verifier 画廊

### 3A. CO-RE + RingBuffer 实时追踪（`exec_rw_trace`）

完整走通 `clang -target bpf` → `bpftool gen skeleton` → `BPF_MAP_TYPE_RINGBUF` 用户态消费闭环：
- 捕获短命进程生命周期：`[EXEC] /bin/true` → `[EXIT] code=0 life_ms=1.683`、`[EXEC] /bin/echo` → `[EXIT] code=0 life_ms=7.616`；
- 过滤目标 PID 的 `read` / `write` 系统调用，同时经 RingBuffer 流式输出单次事件（`lat_us=3.40 ~ 29.11`）并在内核 Map 中聚合 log2 延迟直方图（`[2, 3] us: 8`、`[4, 7] us: 2`、`[8, 15] us: 1`、`[16, 31] us: 1`）。

### 3B. BPF Verifier 三个经典拒绝与修复对照

| 案例 | 故意制造的缺陷 | Linux 7.0 Verifier 实测拒绝日志关键行 | 修复方式 | 修复后结果 |
| --- | --- | --- | --- | --- |
| Case 1 (`case1_null_deref`) | `BPF_MAP_TYPE_HASH` 查找结果未判空直接解引用 | `R0 invalid mem access 'map_value_or_null'` (`-EACCES`) | 增加 `if (!val) return 0;` | `VERIFIER ACCEPTED` |
| Case 2 (`case2_unbounded_loop`) | 循环上界来自运行时 map 值，Verifier 无法证明终止 | `BPF program is too large. Processed 1000001 insn` (`-E2BIG`, `14290` states) | 固定编译期上限 `32` 并加 `if (i >= n) break;` | `VERIFIER ACCEPTED` |
| Case 3 (`case3_pkt_oob`) | XDP 直接读 `eth->h_proto` 未检查 `data_end` | `invalid access to packet, off=12 size=2, R1(id=0,off=12,r=0)` / `R1 offset is outside of the packet` (`-EACCES`) | 读取前增加 `if ((void *)(eth + 1) > data_end) return XDP_PASS;` | `VERIFIER ACCEPTED` |

---

## 实验 4：网络数据面观测（TCP `netem`）与 XDP 拦截

### 4A. TCP 拥塞与重传观测（`tcp:tcp_probe` + `tcp:tcp_retransmit_skb`）

| 场景 | 吞吐 (MB/s) | 平均 SRTT (us) | `snd_cwnd` 范围 | `tcp_retransmit_skb` 重传次数 | 采样数 |
| --- | ---: | ---: | --- | ---: | ---: |
| 隔离 `veth` 基线（无损伤） | **826.79** | `55` | `10 ~ 226` | `0` | `4,325` |
| 隔离 `veth` + `tc netem delay 20ms 5ms loss 1%` | **0.34** | `19,581`（100% 落在 `[16K, 32K) us`） | `1 ~ 10`（拥塞窗口被 1% 丢包持续打压） | **`54`** | `1,620` |
| 真实跨机 WAN `eth0`（TCP 22 数据流） | — | `34,225`（~34.2 ms，与 `ping` 35.4 ms 吻合） | `8 ~ 10` | `1` | `556` |

### 4B. XDP（Generic / SKB 模式）协议栈入口前拦截对照

在 `veth_ebpf_srv` 上挂载 70 行 `xdp_udp_guard`（1,000 个 UDP 包 @ 1,000 pps，限速阈值 `200 pps`）：

| 模式 | 客户端发出 | XDP `matched` | XDP `passed` | XDP `dropped` | 用户态 `udp_server` 实收 | 验证结论 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `count`（纯计数） | `1,000` | `1,000` | `1,000` | `0` | **`1,000`** | 零丢包全量通过 |
| `ratelimit`（按源 IP 限速 200 pps） | `1,000` | `1,000` | `215` | `785` | **`215`** | 超限包在协议栈前被精确丢弃，与用户态实收 1:1 吻合 |
| `drop`（全量 `XDP_DROP`） | `1,000` | `1,000` | `0` | `1,000` | **`0`** | 100% 协议栈前拦截 |

### 4C. `dev1 → dev2` 真实云主机 `eth0` 跨机 XDP 验证（仅匹配 ICMP Echo，不碰 SSH）

| `dev2` `eth0` XDP 模式 | `dev1` `ping -c 5` 结果 | `dev2` XDP 统计 (`matched / passed / dropped`) |
| --- | --- | --- |
| `count` | `5 transmitted, 5 received, 0% loss`（RTT avg `35.43 ms`） | `5 / 5 / 0` |
| `drop` | **`5 transmitted, 0 received, 100% packet loss`** | **`5 / 0 / 5`** |
