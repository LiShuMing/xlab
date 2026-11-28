# eBPF 实验台：观测、调度器、CO-RE 工程闭环与网络数据面

面向 **Linux 6.12+ / 7.0（BTF + `sched_ext` 就绪）** 的四组自包含 eBPF 实验，覆盖从 30 行 `bpftrace` 观测、手写内核调度器、`libbpf + CO-RE + RingBuffer` 与 Verifier 对抗，到 `tc netem` + XDP 网络数据面拦截的完整路径。

## 前置环境

- **OS / 内核**：Linux x86_64/arm64，`CONFIG_DEBUG_INFO_BTF=y`（存在 `/sys/kernel/btf/vmlinux`）；实验 2 需要启用 `CONFIG_SCHED_CLASS_EXT=y`（存在 `/sys/kernel/sched_ext`）。
- **工具链**：`bpftrace`、`clang`、`llvm`、`bpftool`、`libbpf-dev`、`libelf-dev`、`zlib1g-dev`、`gcc`、`make`、`iproute2`（`ip` / `tc`）、`python3`。
- **权限**：加载 BPF 程序、`sched_ext`、XDP 与 `drop_caches` 需要 `sudo`（root / `CAP_BPF` + `CAP_PERFMON` + `CAP_NET_ADMIN`）。
- **实测基线**：Ubuntu Linux `7.0.0-38-generic`（2 vCPU / 1.7 GiB，ext4 块存储），`bpftrace v0.25.0`、`clang 21.1.8`、`bpftool v7.7.0`、`libbpf 1.7`。详细实测数据见 [RESULTS.md](RESULTS.md)，原理深度拆解与 15 分钟技术分享讲稿见 [DEEP_DIVE.md](DEEP_DIVE.md)。

Ubuntu 快速安装依赖：

```bash
sudo apt-get update && sudo apt-get install -y \
  bpftrace clang llvm libbpf-dev libelf-dev zlib1g-dev pkg-config iproute2 gcc make
```

## 目录结构

| 实验目录 | 主题 | 核心技术点 | 一键运行 |
| --- | --- | --- | --- |
| [`01-bpftrace/`](01-bpftrace/) | Page Cache 预读与 Futex 两段锁延迟拆解 | `filemap` + `block_rq_*`、`futex` + `sched_wakeup` + `sched_switch` | `make run-01` |
| [`02-sched-ext/`](02-sched-ext/) | Linux 7.0 极简 `sched_ext` 调度器 | 双 DSQ（`DSQ_HIGH` / `DSQ_NORMAL`）、`BPF_MAP_TYPE_TASK_STORAGE` 短任务识别、`SCX_KICK_PREEMPT` 抢占、watchdog 安全回退 | `make run-02` |
| [`03-core-ringbuf/`](03-core-ringbuf/) | `libbpf + CO-RE + RingBuffer` 与 Verifier 画廊 | `clang -target bpf` → `bpftool gen skeleton` → `BPF_MAP_TYPE_RINGBUF`；3 个经典 Verifier 拒绝案例与修复对照 | `make run-03` |
| [`04-net-xdp/`](04-net-xdp/) | TCP 拥塞观测与 XDP 协议栈前拦截 | `tcp:tcp_probe` / `tcp_retransmit_skb` + `tc netem`（20ms 抖动 + 1% 丢包）；XDP SKB 模式计数 / 按源 IP 限速 / `XDP_DROP` | `make run-04` |

## 快速开始

```bash
cd labs/ebpf
make vmlinux   # 从 /sys/kernel/btf/vmlinux 导出 common/vmlinux.h
make all       # 编译 01~04 全部用户态与 BPF 目标
make run-01    # 实验 1：Page Cache & Futex 两段延迟
make run-02    # 实验 2：EEVDF vs sched_ext FIFO vs Priority DSQ
make run-03    # 实验 3：CO-RE RingBuffer + 3 个 Verifier 拒绝/修复对照
make run-04    # 实验 4：TCP netem 观测 + XDP UDP 计数/限速/丢包
```

### 跨机联动（`dev1` → `dev2` 真实 `eth0` 验证）

在云主机安全组仅放行 SSH (22) 和 ICMP 的环境下，实验 4 支持两种互补验证：

1. **隔离 `veth` + `netns` 全功能验证**（`make run-04`）：不干扰 SSH 连接，完整运行 `tc netem delay 20ms 5ms loss 1%` 与 UDP `19999` 端口的 XDP `count` / `ratelimit` / `drop`。
2. **真实跨机 `eth0` 联动**（不碰 TCP 22，确保 SSH 绝对安全）：
   - **TCP 观测**：在 `dev2` 上运行 `sudo bpftrace -q --no-warnings 04-net-xdp/tcp_trace.bt 22`，从 `dev1` 向 `dev2` 发起 `ssh` 数据流传输，实时观测真实跨机 WAN 链路的 SRTT 与 `snd_cwnd`。
   - **XDP 真实网卡拦截**：在 `dev2` 上运行 `sudo 04-net-xdp/bin/xdp_udp_guard --iface eth0 --icmp --mode drop --duration 5`，从 `dev1` 执行 `ping -c 5 <dev2>`，可亲眼看到 `dev1` 100% 丢包而 `dev2` 的 XDP 计数器在协议栈入口前精确记录并丢弃了每一个 ICMP Echo 包。

## 实验要点与工程细节

1. **Page Cache 实验必须在真实块设备文件系统上进行**：现代 Ubuntu 默认把 `/tmp` 挂载为 `tmpfs`（内存盘），`drop_caches` 不会驱逐 `tmpfs`，也不会触发 `block:block_rq_issue`。实验 1 默认使用 `/var/tmp`（ext4）。
2. **`sched_ext` 命名与安全边界**：
   - `BPF_PROG(name, ...)` 宏会隐式注入参数 `unsigned long long *ctx`，因此函数体内不要定义名为 `ctx` 的局部变量。
   - `.rodata` / `.bss` 供 `bpftool gen skeleton` 暴露给用户态的全局变量应使用标准 C 类型（如 `unsigned int` / `unsigned long long`），避免用户态头文件缺少内核 `u32`/`u64` typedef。
   - `timeout_ms = 5000` 启用内核 watchdog，即使调度器卡死也会自动卸载回退 EEVDF。
3. **Linux 7.0 Verifier 的真实行为差异**：
   - 对 `BPF_MAP_TYPE_ARRAY` 使用编译期常量且在界内的 key 时，现代 Verifier 能静态证明返回值非空；而 `BPF_MAP_TYPE_HASH` 仍返回 `map_value_or_null`，缺判空必然被拒绝。
   - 动态循环上界（来自 map 值）会触发 `infinite loop` / 指令数超限；固定编译期上限加 `if (i >= n) break` 即可通过验证。
   - XDP 包指针访问前必须先做 `(void *)(hdr + 1) > data_end` 边界检查。

---

## 可联动的开源 eBPF 项目参考

按本实验台的四个方向以及**数据库内核 / 系统基础设施 / 可观测性**延伸场景整理，方便后续直接源码对照或二次开发：

### 1. 调度器与 `sched_ext` 生态（对应实验 2）

| 项目 | 语言 / 技术栈 | 亮点与联动方式 |
| --- | --- | --- |
| [sched-ext/scx](https://github.com/sched-ext/scx) | C (BPF) + Rust (用户态) | 官方 `sched_ext` 调度器集合：`scx_simple`（最小参考）、`scx_bpfland`（交互式优先 vtime 调度）、`scx_lavd`（延迟临界性感知）、`scx_rusty`（多域负载均衡）。可直接对照 `02-sched-ext/scx_prio_fifo.bpf.c` 演进为 vtime / NUMA / 数据库 OLTP+OLAP 混合负载隔离调度器。 |
| [scx_loader](https://github.com/sched-ext/scx/tree/main/rust/scx_loader) | Rust + D-Bus | 动态热切换不同 `sched_ext` 调度器的守护进程，适合在实验机上自动化做多调度器基准矩阵。 |

### 2. eBPF 工程脚手架与多语言框架（对应实验 3）

| 项目 | 语言 | 亮点与联动方式 |
| --- | --- | --- |
| [libbpf/libbpf-bootstrap](https://github.com/libbpf/libbpf-bootstrap) | C / Rust | 现代 CO-RE + skeleton + RingBuffer 的官方标准模板（`bootstrap`、`minimal`、`uprobe`、`lsm`），非常适合作为 C 侧工程对照。 |
| [aya-rs/aya](https://github.com/aya-rs/aya) | **纯 Rust**（内核态 + 用户态） | 不依赖 `clang`/`libbpf` C 生态，直接用 Rust 写 eBPF 程序与异步 Tokio 用户态；与本仓库 Rust 栈和 `kernel-lens` 天然契合，可把 `03-core-ringbuf` 移植为纯 Rust eBPF 探针。 |
| [cilium/ebpf](https://github.com/cilium/ebpf) | **纯 Go** | Go 生态事实标准（`bpf2go` 代码生成），适合集成到 `k8s-lab` 或云原生控制面 Agent 中。 |
| [eunomia-bpf/bpf-developer-tutorial](https://github.com/eunomia-bpf/bpf-developer-tutorial) | C / Rust / Go | 40+ 渐进式实战教程，涵盖 CO-RE、LSM、uprobe、sched_ext、TCP/XDP 与性能分析。 |

### 3. 可观测性、Profiling 与零侵入追踪（对应实验 1 & 3）

| 项目 | 定位 | 亮点与联动方式 |
| --- | --- | --- |
| [iovisor/bpftrace](https://github.com/iovisor/bpftrace) & [iovisor/bcc (`libbpf-tools`)](https://github.com/iovisor/bcc/tree/master/libbpf-tools) | 动态追踪 & 生产级工具集 | `cachestat`、`biolatency`、`runqlat`、`futexctn`、`ext4slower`、`tcpretrans` 等经典工具的 C/CO-RE 生产实现，可直接与实验 1/4 脚本逐行对拍。 |
| [open-telemetry/opentelemetry-ebpf-profiler](https://github.com/open-telemetry/opentelemetry-ebpf-profiler) / [parca-dev/parca-agent](https://github.com/parca-dev/parca-agent) | 全系统持续性能剖析 | 基于 eBPF 的低开销跨语言（C/C++/Rust/Go/Python/JVM）栈展开与火焰图采集，无需 frame pointer 即可用 DWARF/eh_frame 展开。 |
| [grafana/beyla](https://github.com/grafana/beyla) | 零侵入应用/协议可观测性 | 用 eBPF 自动识别 HTTP/gRPC/SQL/Redis 流量并吐出 OpenTelemetry Traces 与 Prometheus 指标，可联动数据库或推理服务的链路观测。 |
| [coroot/coroot-node-agent](https://github.com/coroot/coroot-node-agent) | 节点级全栈 eBPF 监控 | 用极轻量 eBPF 采集 TCP RTT、重传、连接拓扑、DNS、TLS/DB 协议延迟与日志，代码精炼易读。 |

### 4. 网络数据面、XDP 与安全（对应实验 4）

| 项目 | 定位 | 亮点与联动方式 |
| --- | --- | --- |
| [xdp-project/xdp-tutorial](https://github.com/xdp-project/xdp-tutorial) | XDP 官方教程 | 从 `XDP_DROP`、包解析、包改写、`XDP_REDIRECT` 到 `AF_XDP` 零拷贝用户态收包的完整递进实验。 |
| [facebookincubator/katran](https://github.com/facebookincubator/katran) | XDP L4 负载均衡器 | Meta 开源的高性能 XDP 负载均衡器，展示了 Maglev 一致性哈希、IPIP 封装与 BPF map 在超高 PPS 数据面中的工程实践。 |
| [cilium/cilium](https://github.com/cilium/cilium) & [cilium/tetragon](https://github.com/cilium/tetragon) | 云原生网络 & 运行时安全 | Cilium 的 `sockops` / `tc` / XDP 绕过内核协议栈加速（Socket-level LB）；Tetragon 的内核态实时安全策略与文件/进程/网络执行拦截。 |
| [mozillazg/ptcpdump](https://github.com/mozillazg/ptcpdump) | 进程感知 `tcpdump` | 用 eBPF 把数据包与进程 PID / comm / 容器元数据关联起来，排查跨机网络问题比传统 `tcpdump` 高效得多。 |

### 5. 数据库内核工程师最值得联动的三个切入点

1. **存储引擎 Page Cache & 块层剖析**：将实验 1 的 `filemap` + `block_rq_*` 挂到 DuckDB / RocksDB / SlateDB 本地缓存或 PostgreSQL 顺序扫描 vs 点查，验证预读放大与大 folio 合并。
2. **混合负载（OLTP 点查 vs OLAP 扫描）CPU 隔离**：将实验 2 的 `sched_ext` 双 DSQ 扩展为基于 cgroup 或短任务特征的动态调度策略，把后台 Compaction / 全表扫描线程压到低优 DSQ，保护前台短查询的 p99 延迟。
3. **无侵入 SQL / RPC 线协议延迟观测**：结合实验 3（RingBuffer）与实验 4（网络 hook / `uprobe` / `sockops`），参考 `grafana/beyla` 思路，在不改数据库源码的前提下追踪查询端到端网络 + 锁 + I/O 延迟分解。
