# 第24章 网络栈精要

> 源码锚点：`net/core/skbuff.c`、`net/core/dev.c`、`net/ipv4/tcp_input.c`、`net/ipv4/tcp_output.c`、`net/xdp/`

Linux网络栈是内核最复杂的子系统之一——从网卡中断到TCP连接管理，从sk_buff数据包抽象到拥塞控制算法，每一层都有精心设计的优化。本章聚焦网络栈的核心机制，理解数据包从网卡到用户态的完整路径。

## 24.1 sk_buff：数据包的内核表示

### struct sk_buff

sk_buff(skb)是网络数据包的通用抽象——贯穿整个网络栈：

```c
// sk_buff的关键字段：
struct sk_buff {
    struct sk_buff  *next, *prev;        // 链表
    struct net_device *dev;               // 接收/发送设备
    char            cb[48];               // 控制块(各层私有数据)
    unsigned int    len;                  // 数据总长度(含分片)
    unsigned int    data_len;             // 分片数据长度
    sk_buff_data_t  transport_header;     // 传输层头偏移
    sk_buff_data_t  network_header;       // 网络层头偏移
    sk_buff_data_t  mac_header;           // MAC头偏移
    // ...
};
```

### 数据缓冲区的组织

skb的数据分两部分：
- **线性区(head room + data + tail room)**：存储各层协议头和部分数据
- **分片区(frag_list / skb_shared_info.frags)**：大块数据通过页面引用，零拷贝

```
┌─────────────────────────────────────┐
│ headroom | [MAC][IP][TCP] | payload │ ← 线性区
└─────────────────────────────────────┘
                              │
                    ┌─────────┴──────────┐
                    │ page frag 0        │ ← 分片区
                    │ page frag 1        │
                    │ ...                │
                    └────────────────────┘
```

各层协议处理时，只需移动指针——push MAC头时前移mac_header，不需要拷贝数据。这是网络栈零拷贝的基础。

### skb的克隆与拷贝

- **克隆(clone)**：共享数据缓冲区，独立元数据——tcpdump等只需要读包头的场景
- **拷贝(copy)**：完全独立的新skb——需要修改数据的场景

克隆只复制skb结构(约300字节)，不复制数据——大幅减少内存分配和数据拷贝。

## 24.2 网络设备与NAPI

### NAPI：中断+轮询混合模型

传统中断模式：每个包一次中断——高速网络下中断风暴导致CPU过载。NAPI(New API)解决此问题：

```
1. 第一个包到达 → 硬中断 → 关闭该队列的硬中断
2. 调度NAPI poll → 在软中断中轮询处理队列中的包
3. 处理完(budget耗尽或队列空) → 重新开硬中断
4. 下一个包到达 → 回到步骤1
```

NAPI的budget控制每次轮询处理的包数——防止软中断独占CPU。默认budget为64个包。

### RSS(Receive Side Scaling)

现代网卡多队列——每个队列独立中断，可绑定到不同CPU。RSS(Receive Side Scaling)在硬件层面将包分发到不同队列——基于五元组(源IP/目的IP/源端口/目的端口/协议)的哈希。

RSS与第18章的中断亲和性配合——队列N的中断绑定到CPU N，实现网络接收的并行处理。

### GRO(Generic Receive Offload)

GRO在软件层面合并接收到的包——将同一流(TCP五元组相同)的连续小包合并为大包，减少协议栈处理次数。

## 24.3 TCP/IP栈

### 接收路径

```
网卡 → DMA到内存 → 硬中断 → NAPI poll
  → netif_receive_skb() → 进入协议栈
  → ip_rcv() → IP层处理
  → tcp_v4_rcv() → TCP层处理
  → 放入socket接收队列
  → 唤醒等待的进程(recv/epoll)
```

### TCP快速路径与慢速路径

`tcp_input.c`(7761行)是TCP最复杂的部分——区分快速路径和慢速路径：

- **快速路径**：预期内的数据包(序列号正确、无特殊标志)——少量检查后直接处理
- **慢速路径**：非预期包(乱序、重复ACK、窗口探测等)——完整的状态检查

90%以上的包走快速路径——内核优化快速路径的每一条指令。

### SACK处理

SACK(Selective Acknowledgment)允许接收方告知发送方哪些数据已收到——发送方只重传丢失的段。`tcp_sacktag_walk()`处理SACK块——标记已接收的段，计算重传队列中需要重传的段。

### 发送路径

```
send()/sendmsg() → tcp_sendmsg()
  → 数据拷贝到skb → 放入发送队列
  → tcp_push() → 触发发送
  → ip_queue_xmit() → IP层
  → dev_queue_xmit() → 网卡驱动
```

发送窗口和拥塞窗口控制发送速率——取两者较小值。`tcp_output.c`负责构建TCP段、管理重传定时器。

## 24.4 拥塞控制

### TCP拥塞控制算法框架

Linux将拥塞控制算法抽象为`struct tcp_congestion_ops`——可插拔的算法框架：

```c
struct tcp_congestion_ops {
    void (*cong_avoid)(struct sock *sk, u32 ack, u32 acked);  // 拥塞避免
    u32  (*ssthresh)(struct sock *sk);                         // 慢启动阈值
    void (*set_state)(struct sock *sk, u8 new_state);          // 状态切换
    // ...
};
```

### 拥塞状态FSM

TCP拥塞控制的状态机：

- **Open**：正常状态，拥塞避免算法控制窗口增长
- **Disorder**：收到重复ACK，标记报文段但未进入恢复
- **Recovery**：快速重传/快速恢复，降低拥塞窗口
- **Loss**：超时，慢启动重新探测

### Cubic/BBR/DCTCP

- **Cubic**(默认)：基于丢包的拥塞控制——丢包时降低窗口，否则按立方函数增长。在长肥网络(LFN)上性能不佳
- **BBR**(Bottleneck Bandwidth and RTT)：基于带宽和RTT的模型——不依赖丢包信号，周期性测量带宽和RTT，选择发送速率。在高速长距离网络上显著优于Cubic
- **DCTCP**(Data Center TCP)：数据中心专用——利用ECN(Explicit Congestion Notification)信号，快速响应轻微拥塞，低延迟

> **数据库视角**：分布式数据库中TCP拥塞对RPC延迟的影响。数据库节点间的RPC通常在数据中心内——低延迟、高带宽。Cubic在数据中心内的RTT波动会导致不必要的窗口缩减。DCTCP或BBR更适合——DCTCP利用ECN信号快速调整，BBR基于带宽模型避免丢包触发的窗口缩减。PolarDB和TiDB在高并发RPC场景下受益于BBR——减少P99延迟。

## 24.5 XDP与eBPF加速

### XDP(eXpress Data Path)

XDP是网络栈最早的数据包处理点——在skb分配之前，直接在网卡驱动的RX环形缓冲区上操作：

```
传统路径：网卡 → skb分配 → 协议栈 → socket → 用户态
XDP路径：  网卡 → XDP程序 → 决策(PASS/DROP/TX/REDIRECT)
```

XDP程序的返回值：
- **XDP_PASS**：继续正常协议栈处理
- **XDP_DROP**：直接丢弃——最快的DDoS防护
- **XDP_TX**：从同一网卡发回——负载均衡器的快速响应
- **XDP_REDIRECT**：重定向到另一个接口/CPU

XDP在skb分配之前执行——避免了skb分配和协议栈处理的开销。适合L3/L4负载均衡(如Cilium)、DDoS防护、流量采样等。

### eBPF网络程序

- **tc eBPF**：在流量控制(tc)层挂载eBPF程序——可以对skb进行修改、重定向、丢弃
- **cgroup/bpf connect**：在connect/accept时执行eBPF程序——实现连接级策略

> **数据库视角**：XDP在分布式数据库网络加速中的潜力。分布式数据库的心跳和节点发现消息高频且小——通过XDP在内核态直接处理，不经过完整协议栈，降低延迟。Cilium的eBPF网络策略也适用于数据库节点间的网络隔离。

## 24.6 RDMA与零拷贝

### RDMA vs TCP

| 特性 | TCP | RDMA |
|------|-----|------|
| 数据拷贝 | 2次(内核→用户) | 0次(RDMA直接到用户缓冲区) |
| CPU参与 | 协议栈处理+拷贝 | 仅设置RDMA工作请求 |
| 延迟 | ~50-100μs(数据中心) | ~2-5μs(RoCEv2) |
| 带宽利用率 | ~80-90%(协议开销) | ~95%+ |

### RDMA在分布式数据库中的应用

PolarDB/Oracle RAC使用RDMA实现节点间的共享存储访问——RDMA远程读写共享内存，延迟仅微秒级，无需CPU参与。这是共享存储架构的关键——存储节点和计算节点间的高速互连。

> **AI视角**：NCCL集合通信与RDMA——GPU训练的通信基础。NCCL(NVIDIA Collective Communications Library)使用RDMA实现GPU间的集合通信(all-reduce/all-gather/broadcast)。RDMA的零拷贝和低延迟使得GPU间的大规模参数同步成为可能——没有RDMA，千卡训练的通信开销将成为瓶颈。

---

本章建立了对Linux网络栈的核心认知：sk_buff是数据包的通用抽象，NAPI解决高速网络的中断风暴，TCP快速/慢速路径优化常见场景，可插拔拥塞控制框架支持Cubic/BBR/DCTCP，XDP在最早点处理数据包，RDMA提供零拷贝低延迟通信。网络栈是分布式系统和AI训练的基础设施——理解其机制才能优化通信延迟和吞吐。
