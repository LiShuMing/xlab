---
chapter: 24
part: 第六篇 I/O与存储栈 —— 数据的完整通路
title: 网络栈精要
source_anchor:
  - net/core/skbuff.c
  - net/core/dev.c
  - net/ipv4/tcp_input.c
  - net/ipv4/tcp_output.c
  - net/ipv4/tcp.c
  - net/xdp/
  - net/bpf/
status: done
---

# 第24章 网络栈精要

## 写作目标

掌握Linux网络栈的核心机制，从sk_buff到TCP拥塞控制，理解XDP/eBPF加速和RDMA的定位。

## 章节大纲

### 24.1 sk_buff：数据包的内核表示

- **精读** `net/core/skbuff.c`：
  - `struct sk_buff`：数据包的通用抽象
  - 数据缓冲区的组织：线性区+分片区(frag_list)
  - skb的克隆与拷贝：零拷贝路径
  - skb的生命周期：分配→填充→发送/接收→释放

### 24.2 网络设备与NAPI

- **精读** `net/core/dev.c`：
  - `struct net_device`：网络设备抽象
  - NAPI(New API)：中断+轮询混合模型
    - 中断触发→关闭中断→轮询处理→重新开中断
    - budget控制轮询量
  - RSS(Receive Side Scaling)：多队列分发
  - GRO(Generic Receive Offload)/LRO

### 24.3 TCP/IP栈

- **精读** `net/ipv4/tcp_input.c`（7761行）：
  - 接收处理：从IP层到TCP层
  - 快速路径与慢速路径
  - SACK处理
- `net/ipv4/tcp_output.c`：
  - 发送处理：从TCP层到IP层
  - 拥塞窗口与发送窗口
- `net/ipv4/tcp.c`：
  - TCP连接管理
  - send/recv系统调用

### 24.4 拥塞控制

- TCP拥塞控制算法框架
- Cubic/BBR/DCTCP
- 拥塞状态的FSM：Open/Disorder/Recovery/Loss
- *数据库视角*：分布式数据库中TCP拥塞对RPC延迟的影响

### 24.5 XDP与eBPF加速

- XDP(eXpress Data Path)：最早的数据包处理点
  - XDP程序类型与返回值：PASS/DROP/TX/REDIRECT
  - `net/xdp/`：XDP核心
- eBPF网络程序：`net/bpf/`
  - tc(tc_eBPF)：流量控制
  - cgroup/bpf connect：连接级控制
- *数据库视角*：XDP在分布式数据库网络加速中的潜力

### 24.6 RDMA与零拷贝

- RDMA回顾（与第3章呼应）
- RDMA vs TCP：延迟与CPU占用对比
- *数据库视角*：RDMA在分布式数据库中的零拷贝RPC
  - PolarDB/Oracle RAC的RDMA使用
- *AI视角*：NCCL集合通信与RDMA——GPU训练的通信基础

## 关键源文件清单

| 文件 | 行数 | 关注点 |
|------|------|--------|
| `net/ipv4/tcp_input.c` | 7761 | TCP接收处理 |
| `net/core/dev.c` | ~4000 | 网络设备核心 |
| `net/core/skbuff.c` | ~4000 | sk_buff管理 |
| `net/ipv4/tcp_output.c` | ~4000 | TCP发送处理 |

## 跨章依赖

- 依赖第3章（RDMA硬件）：RDMA的网络层与硬件的对应
- 依赖第25章（eBPF）：XDP是eBPF在网络栈中的应用
