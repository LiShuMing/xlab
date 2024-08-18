# 第35章 计算适配的未来

> 源码锚点：`io_uring/uring_cmd.c`、`drivers/nvme/host/uring_cmd.c`、`drivers/accel/`、`drivers/cxl/`、`kernel/sched/ext.c`

从计算存储到DPU卸载，从io_uring统一异步接口到BPF可编程调度，计算适配正在走向三个方向：近存计算、异步一切、安全内生。这些趋势将重塑操作系统与硬件的边界，也将重塑AI与数据库的系统栈。

## 35.1 计算存储：下推到SSD

### Computational Storage

计算存储(Computational Storage)将计算能力嵌入SSD——在存储设备内部执行数据处理，减少数据传输：

```
传统路径：SSD → 读取数据 → 传输到主机 → 主机处理 → 结果
计算存储：  SSD → 内部处理 → 仅返回结果 → 主机

节省的带宽 = 原始数据量 - 结果数据量
```

### NVMe uring_cmd

`drivers/nvme/host/uring_cmd.c`和`io_uring/uring_cmd.c`实现NVMe passthrough命令——通过io_uring异步提交NVMe命令：

```c
// 用户态提交计算存储命令
struct io_uring_sqe sqe = {
    .opcode = IORING_OP_URING_CMD,
    .cmd_op = NVME_URING_CMD_IO,
    // NVMe命令：读取+过滤+返回结果
};
io_uring_submit(&ring);
// 异步完成：CQE返回结果
```

uring_cmd的统一接口——任何设备的自定义命令都可以通过io_uring异步提交，无需专用系统调用。

> **数据库视角**：谓词下推(Predicate Pushdown)到SSD。数据库查询的WHERE子句可以下推到SSD——SSD内部过滤不满足条件的行，只返回匹配行。减少90%+的数据传输量。Oracle的Exadata Smart Scan就是此思路的工程实践。

> **AI视角**：向量检索下推到SSD——近存向量搜索。RAG(检索增强生成)需要在向量数据库中搜索相关文档——将向量索引和搜索算法嵌入SSD，在存储设备内部完成搜索，只返回Top-K结果。减少99%的数据传输量。

## 35.2 DPU/SmartNIC：卸载网络与存储

### DPU(Data Processing Unit)

DPU是可编程的网络+存储卸载设备——将主机CPU从网络和存储处理中解放出来：

```
传统：主机CPU处理网络协议栈 + 存储协议 + 安全加密
DPU： DPU处理网络协议栈 + 存储协议 + 安全加密 → 主机CPU专注业务逻辑
```

### 硬件卸载

`drivers/net/ethernet/`中的智能网卡驱动实现各种硬件卸载：

- **TCP Segmentation Offload(TSO)**：主机发送大段数据，网卡分片为TCP段——减少CPU开销
- **Checksum Offload**：网卡计算TCP/UDP/IP校验和——零CPU开销
- **VXLAN/Geneve封装卸载**：网卡执行隧道封装/解封——Overlay网络的硬件加速
- **RDMA/RoCE**：网卡实现RDMA协议——零拷贝、低延迟通信

> **数据库视角**：RDMA/RoCE卸载到DPU。分布式数据库的节点间RPC走RDMA——DPU处理RDMA协议，CPU不参与数据搬运。PolarDB和Oracle RAC已使用RDMA——DPU可以进一步卸载连接管理和流量控制。

> **AI视角**：NCCL集合通信的DPU加速。GPU训练的All-Reduce通信通过NCCL——DPU可以实现集合通信的硬件加速，减少GPU间通信的CPU开销和延迟。NVIDIA的BlueField DPU已支持NCCL的offload。

## 35.3 io_uring作为统一异步接口

### io_uring的扩展性

io_uring从文件I/O起步，已扩展为统一的异步编程接口：

```
文件I/O → READ/WRITE
网络I/O → SEND/RECV/ACCEPT/CONNECT
定时器  → TIMEOUT
信号    → SIGNAL_WAIT
futex   → FUTEX_WAIT/WAKE
设备命令 → URING_CMD
epoll   → EPOLL_WAIT
```

io_uring的核心优势——**统一的异步编程模型**：所有操作使用相同的SQ/CQ机制，相同的提交/完成语义。

### io_uring + 计算存储 + DPU的统一编程模型

展望未来——应用通过io_uring与多种后端交互：

```
应用 → io_uring SQE → 内核
  → IORING_OP_READ → 本地SSD读取
  → IORING_OP_URING_CMD → 计算存储命令(NVMe过滤)
  → IORING_OP_SEND → DPU网络发送
  → IORING_OP_READ → CXL远端内存读取
```

应用不关心后端是什么——统一提交、统一完成、统一超时和取消。io_uring成为操作系统的"异步系统调用总线"。

## 35.4 可编程调度与Agent编排

### BPF可编程调度器

`kernel/sched/ext.c`实现BPF可编程调度器——允许用BPF程序自定义调度策略：

```c
// sched_ext BPF程序示例：
// SLO感知调度：推理请求优先于批处理任务
SEC("sched/select_cpu")
int select_cpu(struct task_struct *p) {
    if (is_inference_task(p))
        return select_idle_cpu(p, SCHED_INFER_NODE);
    else
        return select_idle_cpu(p, SCHED_BATCH_NODE);
}
```

BPF调度器的优势——运行时可替换调度策略，无需重启内核。适用于：
- **SLO感知调度**：推理请求优先，批处理任务使用剩余资源
- **GPU时间片分配**：多租户推理的公平GPU时间分配
- **Cache感知调度**：优先调度数据在cache中的任务

### Agent编排的OS视角

AI Agent是多个协作进程的集合——编排Agent的挑战与OS调度异曲同工：

| OS机制 | Agent编排 |
|--------|----------|
| cgroup资源隔离 | Agent资源配额 |
| 调度器优先级 | Agent优先级 |
| 抢占 | Agent任务抢占 |
| 进程间通信 | Agent间通信 |
| 内存限制 | Agent上下文窗口限制 |

io_uring的`msg_ring`操作(跨ring通信)可用于Agent间的异步消息传递——BPF ringbuf用于Agent状态的实时监控。

## 35.5 展望：计算适配的三个方向

### 1. 近存计算

计算靠近数据——减少数据搬运的延迟和带宽消耗：

- **CXL内存池**：多主机共享远端内存——推理引擎的KV Cache池化
- **计算存储**：SSD内部执行过滤和搜索——数据库谓词下推、AI向量检索
- **NPU近存推理**：NPU直接访问CXL内存——无需将数据搬入HBM

近存计算的核心洞察：**数据不动，计算动**——在数据所在地执行计算，比将数据搬到计算单元更高效。

### 2. 异步一切

io_uring统一的异步编程模型——从文件I/O到网络到设备命令，一切异步：

- **消除系统调用开销**：共享内存环替代syscall
- **批量操作**：一次提交多个请求，减少切换开销
- **SQPOLL消除提交延迟**：内核线程自动轮询提交
- **uring_cmd统一设备命令**：任何设备的自定义命令通过统一接口

异步一切的核心洞察：**同步是延迟的来源**——将所有操作异步化，让CPU永远有工作可做。

### 3. 安全内生

安全不是附加功能——而是系统设计的内生属性：

- **机密计算(SEV-SNP/TDX)**：硬件级的数据加密保护
- **Rust内核驱动**：编译时内存安全保证
- **BPF LSM安全策略**：运行时可定制的安全规则
- **dmem cgroup显存隔离**：多租户资源隔离

安全内生的核心洞察：**安全不是补丁，是架构**——从设计之初将安全作为核心约束，而非事后添加。

---

全书从x86硬件架构出发，经过启动过程、内存管理、同步并发、中断时间信号、I/O存储栈、可观测性安全、数据库对话，最终到达AI时代的OS演进。35章的内容建立了一条完整的认知链路：**从硬件原理到内核实现，从内核机制到应用优化，从当前系统到未来方向**。理解操作系统，就是理解计算适配的艺术——在硬件的约束下，为应用提供最高效、最安全、最可观测的服务。计算适配的未来，将继续沿着近存计算、异步一切、安全内生三个方向演进——而Linux内核，将继续是这场演进的核心舞台。
