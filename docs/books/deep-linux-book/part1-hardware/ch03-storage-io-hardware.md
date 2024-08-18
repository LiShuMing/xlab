---
chapter: 3
part: 第一篇 硬件与架构 —— 计算的物理边界
title: 存储与I/O硬件通路
source_anchor:
  - drivers/nvme/host/pci.c
  - drivers/nvme/host/core.c
  - drivers/nvme/host/nvme.h
  - drivers/dma/dmaengine.c
  - drivers/infiniband/
status: done
---

# 第3章 存储与I/O硬件通路

## 写作目标

理解数据在存储硬件与主机之间的传输路径，掌握NVMe/DMA/RDMA三大I/O通路的硬件原理，这是第六篇I/O栈的硬件前置。

## 章节大纲

### 3.1 存储设备的延迟谱系

- DRAM: ~100ns
- NVM(如Intel Optane): ~微秒级
- NVMe SSD: ~10-100微秒
- SATA SSD: ~100微秒
- HDD: ~毫秒级
- 延迟鸿沟与软件设计的根本约束

### 3.2 NVMe：从寄存器到驱动

- NVMe规范核心：Submission Queue / Completion Queue
- 门铃寄存器(DB)与队列管理
- PRP/SGL：数据缓冲区描述
- **精读** `drivers/nvme/host/pci.c`：
  - `nvme_queue_rq()`：请求提交路径
  - `nvme_pci_complete_rq()`：完成路径
  - 中断处理与MSI-X多队列
- NVMe over Fabrics：`drivers/nvme/host/fc.c`、`drivers/nvme/host/tcp.c`、`drivers/nvme/host/rdma.c`
- *数据库视角*：WAL写路径为何要绕过I/O调度器——直接NVMe提交的延迟优势

### 3.3 DMA：异步数据搬运

- DMA控制器与总线 mastering
- DMA引擎抽象：`drivers/dma/dmaengine.c`
- 流式DMA映射 vs 一致性DMA映射
- DMA地址与IOMMU
- *源码精读*：一个DMA传输的请求→映射→提交→回调全流程

### 3.4 RDMA：零拷贝网络传输

- RDMA原理：内核旁路与远程直接内存访问
- InfiniBand与RoCE协议
- `drivers/infiniband/` 目录结构：core/hw/sw/ulp
- Protection Domain、Memory Region、Queue Pair
- *数据库视角*：RDMA在分布式数据库中的应用——Paxos/RPC的零拷贝
- *AI视角*：NCCL集合通信与RDMA

## 关键源文件清单

| 文件 | 行数 | 关注点 |
|------|------|--------|
| `drivers/nvme/host/pci.c` | ~3500 | NVMe PCI驱动核心 |
| `drivers/nvme/host/core.c` | ~4500 | NVMe核心抽象 |
| `drivers/dma/dmaengine.c` | ~2000 | DMA引擎框架 |
| `drivers/infiniband/core/` | — | RDMA核心层 |

## 跨章依赖

- 本章是第21章（通用块层）的前置：NVMe多队列与blk-mq的对应关系
- 本章是第24章（网络栈）的前置：RDMA与传统网络栈的对比
