---
chapter: 35
part: 第九篇 AI时代的OS与硬件适配
title: 计算适配的未来
source_anchor:
  - drivers/nvme/host/uring_cmd.c
  - io_uring/uring_cmd.c
  - drivers/accel/
  - drivers/cxl/
  - drivers/net/ethernet/
  - kernel/sched/ext.c
status: done
---

# 第35章 计算适配的未来

## 写作目标

展望计算适配的未来方向，从计算存储、DPU卸载到Agent编排，建立对未来趋势的系统性思考。

## 章节大纲

### 35.1 计算存储：下推到SSD

- Computational Storage：在SSD内部执行计算
- NVMe Computational Drive
- **精读** `drivers/nvme/host/uring_cmd.c`：
  - NVMe passthrough命令
  - **精读** `io_uring/uring_cmd.c`：
    - IORING_OP_URING_CMD：统一的异步命令提交接口
    - 计算存储命令通过io_uring提交
- *数据库视角*：谓词下推(Predicate Pushdown)到SSD
  - 在存储设备内部过滤数据，减少数据传输
- *AI视角*：向量检索下推到SSD——近存向量搜索

### 35.2 DPU/SmartNIC：卸载网络与存储

- DPU(Data Processing Unit)：可编程网络+存储卸载
- `drivers/net/ethernet/`：智能网卡的硬件卸载
  - TCP segmentation offload
  - checksum offload
  - VXLAN/Geneve封装卸载
- *数据库视角*：RDMA/RoCE卸载到DPU
  - 分布式事务的RPC加速
- *AI视角*：NCCL集合通信的DPU加速

### 35.3 io_uring作为统一异步接口

- io_uring的扩展性：
  - 从文件I/O到网络I/O到设备命令
  - uring_cmd作为万能异步命令接口
- *展望*：io_uring + 计算存储 + DPU的统一编程模型
  - 应用 → io_uring → 多种后端（本地SSD/DPU/远程存储）

### 35.4 可编程调度与Agent编排

- BPF可编程调度器：`kernel/sched/ext.c`
  - 自定义调度策略
  - *AI视角*：推理任务的定制调度
    - SLO感知调度
    - GPU时间片分配
- Agent编排的OS视角：
  - Agent ≈ 一组协作进程
  - 资源复用与隔离：cgroup的类比
  - 优先级与抢占：调度器的类比
  - 通信：io_uring msg_ring / BPF ringbuf的类比

### 35.5 展望：计算适配的三个方向

1. **近存计算**：计算靠近数据（CXL/计算存储/NPU）
2. **异步一切**：io_uring统一的异步编程模型
3. **安全内生**：机密计算 + Rust驱动 + BPF安全策略

## 关键源文件清单

| 文件 | 关注点 |
|------|--------|
| `io_uring/uring_cmd.c` | 统一异步命令 |
| `drivers/nvme/host/uring_cmd.c` | NVMe passthrough |
| `kernel/sched/ext.c` | BPF可编程调度 |

## 跨章依赖

- 综合全书知识
