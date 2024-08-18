# 第3章 存储与I/O硬件通路

> 源码锚点：`drivers/nvme/host/pci.c`、`drivers/nvme/host/core.c`、`drivers/nvme/host/nvme.h`、`drivers/dma/dmaengine.c`、`drivers/infiniband/`

存储设备的延迟跨越了六个数量级——从DRAM的100纳秒到HDD的10毫秒。这个鸿沟不仅决定了I/O性能，更深刻地塑造了操作系统的I/O栈设计。本章聚焦NVMe、DMA、RDMA三大硬件通路，它们是第六篇I/O栈的硬件前置。

## 3.1 存储设备的延迟谱系

| 存储介质 | 随机读延迟 | 顺序带宽 | 每GB成本 |
|---------|-----------|---------|---------|
| DRAM | ~100 ns | ~50 GB/s | ¥20/GB |
| NVM(Optane) | ~1-10 μs | ~10 GB/s | ¥50/GB |
| NVMe SSD | ~10-100 μs | ~7 GB/s | ¥3/GB |
| SATA SSD | ~100 μs | ~0.5 GB/s | ¥2/GB |
| HDD | ~5-10 ms | ~0.2 GB/s | ¥0.1/GB |

关键观察：

1. **DRAM到HDD跨越5个数量级**。软件必须用不同策略应对：DRAM用精细的缓存行管理，SSD用异步I/O避免阻塞，HDD用电梯算法减少寻道。
2. **NVM的定位尴尬**：比DRAM慢10-100倍，比SSD贵10倍。Intel已停产Optane，但CXL内存扩展可能在某种意义上延续NVM的定位。
3. **NVMe SSD是当前数据库的主力**：延迟在10-100微秒范围，足够快以至于传统中断驱动的I/O模型成为瓶颈——这是io_uring出现的硬件背景。

延迟鸿沟的根本约束：**软件层能做的优化，上限是硬件延迟**。一个fsync必须等到数据持久化到存储介质，无论软件怎么优化，都不可能低于介质的写入延迟。理解硬件延迟，就理解了软件优化的天花板。

## 3.2 NVMe：从寄存器到驱动

### NVMe规范核心：SQ/CQ双队列

NVMe协议的核心设计是**多对提交/完成队列**：

```
主机内存                              NVMe控制器
┌──────────────┐                     ┌──────────┐
│ SQ 0 (Admin) │─── 门铃 ───────────►│          │
│ SQ 1 (I/O)   │─── 门铃 ───────────►│  处理器  │
│ SQ 2 (I/O)   │─── 门铃 ───────────►│          │
│ ...          │                     │          │
│ CQ 0 (Admin) │◄── 门铃 ────────────│          │
│ CQ 1 (I/O)   │◄── 门铃 ────────────│          │
│ CQ 2 (I/O)   │◄── 门铃 ────────────│          │
└──────────────┘                     └──────────┘
```

- **提交队列(SQ, Submission Queue)**：主机写入命令的环形缓冲区，位于主机内存
- **完成队列(CQ, Completion Queue)**：控制器写入完成状态的环形缓冲区，位于主机内存
- **门铃寄存器(DB, Doorbell Register)**：位于控制器寄存器空间，主机写DB通知控制器"有新命令"，控制器写DB通知主机"有新完成"

多队列是NVMe相对AHCI的革命性改进：AHCI只有1个命令队列(深度32)，NVMe支持65535个I/O队列(每队列深度65536)。多队列天然映射到多核——每个CPU核心可以操作自己的SQ/CQ对，无需全局锁。

### 门铃寄存器与队列管理

提交命令的流程：
1. 主机将NVMe命令写入SQ的下一个槽位
2. 更新SQ的tail指针
3. 写SQ的门铃寄存器(DB)——一次MMIO写操作，通知控制器
4. 控制器从SQ取命令执行
5. 控制器将完成条目写入CQ
6. 控制器写CQ的门铃寄存器或触发MSI-X中断
7. 主机读取CQ条目，更新CQ的head指针
8. 写CQ的门铃寄存器，通知控制器"CQ空间已释放"

CQ使用**相位位(Phase Bit)**机制检测新完成：每个CQ条目的最低位是相位位，新完成条目的相位位与上次不同。这样主机无需单独跟踪CQ的head/tail，只需比较相位位即可判断是否有新完成。

### PRP/SGL：数据缓冲区描述

NVMe命令需要告诉控制器数据缓冲区的位置：

- **PRP(Physical Region Page)**：简单的页对齐地址列表，每个PRP指向一个4KB页。命令中有PRP1和PRP2，超过2个页时通过PRP链表间接引用。PRP简单但不灵活——缓冲区必须页对齐。
- **SGL(Scatter-Gather List)**：更灵活的散列表，支持任意长度的段和嵌套。NVMe 1.1+支持。SGL更适合大块I/O和分散的缓冲区。

### 精读 drivers/nvme/host/pci.c

NVMe的Linux PCI驱动是硬件协议的忠实映射。核心数据结构`struct nvme_queue`精确对应SQ/CQ：

```c
// drivers/nvme/host/pci.c
struct nvme_queue {
    struct nvme_dev *dev;
    spinlock_t sq_lock;                    // SQ的并发保护
    void *sq_cmds;                         // SQ命令缓冲区(主机内存)
    spinlock_t cq_poll_lock ____cacheline_aligned_in_smp;  // CQ轮询锁(独立缓存行!)
    struct nvme_completion *cqes;          // CQ完成条目(主机内存)
    dma_addr_t sq_dma_addr;               // SQ的DMA地址(控制器可见)
    dma_addr_t cq_dma_addr;               // CQ的DMA地址
    u32 __iomem *q_db;                    // 门铃寄存器(MMIO地址)
    u32 q_depth;                          // 队列深度
    u16 cq_vector;                        // MSI-X向量号
    u16 sq_tail;                          // SQ尾指针(主机维护)
    u16 last_sq_tail;                     // 上次敲铃时的tail
    u16 cq_head;                          // CQ头指针(主机维护)
    u16 qid;                              // 队列ID
    u8 cq_phase;                          // CQ相位位
    ...
};
```

注意`cq_poll_lock`使用了`____cacheline_aligned_in_smp`——将锁放到独立缓存行，避免与`sq_lock`的伪共享。这是内核对硬件数据结构的精细优化。

**请求提交路径**——`nvme_queue_rq()`：

```c
static blk_status_t nvme_queue_rq(struct blk_mq_hw_ctx *hctx,
                                  const struct blk_mq_queue_data *bd)
{
    struct nvme_queue *nvmeq = hctx->driver_data;
    struct request *req = bd->rq;

    if (unlikely(!test_bit(NVMEQ_ENABLED, &nvmeq->flags)))
        return BLK_STS_IOERR;                         // 队列已禁用
    if (unlikely(!nvme_check_ready(&dev->ctrl, req, true)))
        return nvme_fail_nonready_command(&dev->ctrl, req);  // 控制器未就绪

    ret = nvme_prep_rq(req);                          // 准备请求(详见下文)
    if (unlikely(ret))
        return ret;

    spin_lock(&nvmeq->sq_lock);
    nvme_sq_copy_cmd(nvmeq, &iod->cmd);               // 复制命令到SQ
    nvme_write_sq_db(nvmeq, bd->last);                // 敲门铃
    spin_unlock(&nvmeq->sq_lock);
    return BLK_STS_OK;
}
```

`nvme_prep_rq()`是提交前的准备，包含三个关键步骤：

```c
static blk_status_t nvme_prep_rq(struct request *req)
{
    ret = nvme_setup_cmd(req->q->queuedata, req);    // 1. 构造NVMe命令
    if (ret) return ret;

    if (blk_rq_nr_phys_segments(req)) {
        ret = nvme_map_data(req);                     // 2. DMA映射数据缓冲区
        if (ret) goto out_free_cmd;
    }

    if (blk_integrity_rq(req)) {
        ret = nvme_map_metadata(req);                 // 3. DMA映射元数据
        if (ret) goto out_unmap_data;
    }

    nvme_start_request(req);                          // 启动超时计时器
    return BLK_STS_OK;
}
```

`nvme_map_data()`处理DMA映射——将物理上不连续的页面映射为控制器可访问的DMA地址，并构造PRP或SGL描述符：

```c
static blk_status_t nvme_map_data(struct request *req)
{
    // 单段请求的快速路径——直接用PRP，无需SGL
    if (blk_rq_nr_phys_segments(req) == 1) {
        ret = nvme_pci_setup_data_simple(req, use_sgl);
        if (ret != BLK_STS_AGAIN)
            return ret;
    }

    // 多段请求的通用路径
    if (!blk_rq_dma_map_iter_start(req, dev->dev, &iod->dma_state, &iter))
        return iter.status;                            // DMA映射失败

    // 根据设备能力和请求大小选择PRP或SGL
    if (use_sgl == SGL_FORCED ||
        (use_sgl == SGL_SUPPORTED && avg_seg_size >= sgl_threshold))
        return nvme_pci_setup_data_sgl(req, &iter);
    return nvme_pci_setup_data_prp(req, &iter);
}
```

**命令复制与门铃**——`nvme_sq_copy_cmd()`和`nvme_write_sq_db()`：

```c
static inline void nvme_sq_copy_cmd(struct nvme_queue *nvmeq,
                                    struct nvme_command *cmd)
{
    // 将64字节的NVMe命令复制到SQ的下一个槽位
    memcpy(nvmeq->sq_cmds + (nvmeq->sq_tail << nvmeq->sqes),
           absolute_pointer(cmd), sizeof(*cmd));
    if (++nvmeq->sq_tail == nvmeq->q_depth)
        nvmeq->sq_tail = 0;                          // 环形回绕
}

static inline void nvme_write_sq_db(struct nvme_queue *nvmeq, bool write_sq)
{
    if (!write_sq) {                                  // 批量提交优化
        u16 next_tail = nvmeq->sq_tail + 1;
        if (next_tail == nvmeq->q_depth) next_tail = 0;
        if (next_tail != nvmeq->last_sq_tail)
            return;                                   // 队列未满，延迟敲门铃
    }
    // 写门铃寄存器——一次MMIO写，通知控制器
    if (nvme_dbbuf_update_and_check_event(nvmeq->sq_tail, ...))
        writel(nvmeq->sq_tail, nvmeq->q_db);
    nvmeq->last_sq_tail = nvmeq->sq_tail;
}
```

注意`nvme_write_sq_db`的批量优化：如果`write_sq`为false且下一个tail不等于`last_sq_tail`，则跳过门铃写入。这意味着多个命令可以批量提交——复制到SQ后只在最后一个命令时敲一次门铃，减少MMIO写次数。

**完成路径**——中断处理与CQ轮询：

```c
static irqreturn_t nvme_irq(int irq, void *data)
{
    struct nvme_queue *nvmeq = data;
    DEFINE_IO_COMP_BATCH(iob);

    if (nvme_poll_cq(nvmeq, &iob)) {                 // 轮询CQ
        if (!rq_list_empty(&iob.req_list))
            nvme_pci_complete_batch(&iob);            // 批量完成
        return IRQ_HANDLED;
    }
    return IRQ_NONE;
}

static inline bool nvme_poll_cq(struct nvme_queue *nvmeq,
                                struct io_comp_batch *iob)
{
    bool found = false;
    while (nvme_cqe_pending(nvmeq)) {                 // 检查相位位
        found = true;
        dma_rmb();                                    // 读内存屏障
        nvme_handle_cqe(nvmeq, iob, nvmeq->cq_head); // 处理单个CQE
        nvme_update_cq_head(nvmeq);                   // 推进head
    }
    if (found)
        nvme_ring_cq_doorbell(nvmeq);                // 敲CQ门铃
    return found;
}
```

完成路径的核心：`nvme_cqe_pending()`检查CQ条目的相位位是否翻转——这是无锁检测新完成的关键。`dma_rmb()`确保相位位的读取在CQE其余字段的读取之前完成（load-load控制依赖）。

`nvme_handle_cqe()`将CQE映射回原始请求，并尝试批量完成——如果连续多个请求成功完成，可以一次调用`nvme_pci_complete_batch()`而非逐个调用`nvme_pci_complete_rq()`，减少锁操作和调度开销。

```c
static void nvme_pci_complete_rq(struct request *req)
{
    nvme_pci_unmap_rq(req);    // 解除DMA映射
    nvme_complete_rq(req);     // 通知块层完成
}
```

### NVMe over Fabrics

NVMe协议不限于PCIe总线——NVMe-oF将NVMe命令封装到网络协议中传输：

- **FC-NVMe**：`drivers/nvme/host/fc.c`——光纤通道传输
- **TCP**：`drivers/nvme/host/tcp.c`——标准TCP传输，无需专用硬件
- **RDMA**：`drivers/nvme/host/rdma.c`——RoCE/InfiniBand传输，最低延迟

NVMe-oF使得远程存储设备可以像本地NVMe SSD一样使用——相同的命令集、相同的驱动接口。这对分布式存储系统（如Ceph、SPDK target）至关重要。

> **数据库视角**：WAL写路径为何要绕过I/O调度器。NVMe SSD的延迟约10-20微秒，但Linux I/O调度器的决策延迟可能达到数百微秒——在设备层面，调度反而增加了延迟。`none`调度器(无调度)配合O_DIRECT，让WAL写入直接从应用层到达NVMe驱动，跳过合并、排序等调度决策。这对于延迟敏感的WAL fsync路径尤其重要——每次fsync的延迟直接决定事务提交的吞吐。第21章会深入分析块层的调度器选择。

## 3.3 DMA：异步数据搬运

### DMA控制器与总线Mastering

CPU直接搬运数据太慢了——每次搬运都要经过寄存器，对于大量数据传输效率极低。DMA(Direct Memory Access)让设备直接读写内存，CPU只需设置传输参数，然后去做别的事，传输完成后设备发出中断通知CPU。

DMA的前提是设备必须是**总线主控(Bus Master)**——能够主动发起总线事务。现代PCIe设备都支持总线主控。

### 流式DMA映射 vs 一致性DMA映射

Linux内核提供两种DMA映射方式：

**流式DMA映射(Streaming DMA Mapping)**：临时映射，用于单次I/O操作。流程：
1. `dma_map_single()`或`dma_map_sg()`——将缓冲区映射为DMA地址
2. 执行DMA传输
3. `dma_unmap_single()`或`dma_unmap_sg()`——解除映射

流式映射需要处理Cache一致性——CPU Cache中的数据可能比内存新。映射时需要**刷出(Clean)**写缓冲区（确保DMA读到最新数据），解除映射时需要**无效化(Invalidate)**（确保CPU读DMA写入的新数据）。

**一致性DMA映射(Coherent DMA Mapping)**：长期映射，驱动生命周期内有效。流程：
1. `dma_alloc_coherent()`——分配并映射，返回CPU虚拟地址和DMA地址
2. 随时可用，无需显式同步
3. `dma_free_coherent()`——释放

一致性映射的缓冲区位于**不可缓存(Uncacheable)**或**写合并(Write-Combine)**的内存区域，CPU和DMA看到的数据始终一致。代价是CPU访问速度较慢——没有Cache加速。

NVMe驱动中，SQ和CQ使用一致性DMA映射（`dma_alloc_coherent`），因为它们需要CPU和控制器同时访问；而I/O数据缓冲区使用流式DMA映射（`dma_map_sg`），因为数据只需要单向传输。

### DMA引擎抽象

`drivers/dma/dmaengine.c`提供了硬件无关的DMA引擎框架：

```
应用层:  dma_request_channel() → dmaengine_prep_*() → dmaengine_submit() → dma_async_issue_pending()
框架层:  dmaengine.c — 统一接口、通道管理
驱动层:  各硬件DMA驱动(ioat, dw, pl330, ...)
硬件层:  DMA控制器
```

核心接口：
- `dma_request_channel()`：申请DMA通道
- `dmaengine_prep_memcpy()`/`dmaengine_prep_slave_sg()`：准备传输描述符
- `dmaengine_submit()`：提交描述符到通道
- `dma_async_issue_pending()`：触发传输开始
- 完成回调：传输完成后执行的函数

### DMA地址与IOMMU

DMA地址是设备看到的"物理地址"。在没有IOMMU的系统上，DMA地址就是物理地址。但在有IOMMU的系统上，DMA地址经过IOMMU翻译：

```
设备发出的DMA地址 → IOMMU翻译 → 物理地址
```

IOMMU的作用：
1. **地址翻译**：设备使用连续的DMA地址访问分散的物理页面——类似CPU的虚拟内存
2. **隔离**：限制设备只能访问被授权的内存区域，防止恶意或buggy的DMA操作破坏内核
3. **地址映射**：32位设备可以访问64位地址空间的内存

IOMMU对性能的影响：每次DMA访问增加一次地址翻译（类似TLB），IOMMU有自己的IOTLB缓存翻译结果。NVMe驱动中的`nvme_map_data()`最终调用的`dma_map_sg()`会通过IOMMU建立映射。

## 3.4 RDMA：零拷贝网络传输

### RDMA原理：内核旁路

传统网络栈的数据路径：

```
应用缓冲区 → 内核socket缓冲区 → 网卡驱动 → 网卡 → 网络 → 网卡 → 网卡驱动 → 内核socket缓冲区 → 应用缓冲区
```

两次数据拷贝(应用↔内核)，两次上下文切换(用户态↔内核态)。

RDMA(Remote Direct Memory Access)的关键优化：

```
应用缓冲区 ──────────── DMA ────────────→ 网卡 → 网络 → 网卡 ──────────── DMA ────────────→ 应用缓冲区
   (远端CPU不参与)          (本地CPU不参与)
```

1. **内核旁路**：数据不经过内核协议栈，应用直接与网卡交互
2. **零拷贝**：数据从应用缓冲区直接DMA到网卡，无中间拷贝
3. **远端CPU不参与**：远端网卡的DMA引擎直接写入应用缓冲区，远端CPU无需处理中断、拷贝数据

### InfiniBand与RoCE协议

RDMA最初运行在InfiniBand专有网络上，后来出现了RoCE(RDMA over Converged Ethernet)，允许在标准以太网上运行RDMA：

- **InfiniBand**：专用互连，最高HDR 200 Gb/s，亚微秒延迟。需要专用交换机和网卡。
- **RoCE v1**：RDMA over Ethernet，仅在同一二层网络内工作
- **RoCE v2**：RDMA over UDP/IP，可路由，部署更灵活。需要无损以太网(PFC/ECN)。

两者共享相同的Verbs API，应用代码无需区分。

### InfiniBand核心概念

`drivers/infiniband/`实现了Linux的RDMA栈，核心概念：

**Protection Domain (PD)**：资源隔离的基本单位。每个PD内的资源(MR/QP/SRQ)只能互相引用，不同PD间隔离。

**Memory Region (MR)**：注册给网卡的内存区域。应用必须先注册MR，网卡才能访问该内存。注册过程：
1. 锁定物理页面（防止被换出）
2. 建立网卡可见的虚拟地址→物理地址映射（类似IOMMU页表）
3. 返回lkey(本地访问密钥)和rkey(远程访问密钥)

**Queue Pair (QP)**：通信端点，由发送队列(SQ)和接收队列(RQ)组成。两个QP建立连接后，可以互相发送数据。QP的状态机：Reset → Init → RTR(Ready to Receive) → RTS(Ready to Send)。

**Completion Queue (CQ)**：工作完成通知队列。SQ/RQ的操作完成后，完成条目被放入CQ，应用通过轮询CQ获取完成状态。

```
发送端应用                              接收端应用
    │                                       │
    ├── Post Send (SQ) ──►                  │
    │   DMA→网卡→网络──►网卡→DMA──┤
    │                                       ├── CQ通知接收完成
    │   ◄── CQ通知发送完成                   │
    │                                       │
```

### Linux RDMA栈结构

`drivers/infiniband/`的目录组织：

```
infiniband/
├── core/          # 核心框架
│   ├── device.c   # 设备注册与管理
│   ├── cma.c      # 连接管理器(CM)
│   ├── mr_pool.c  # MR池化管理
│   ├── cq.c       # CQ核心
│   ├── cm.c       # 通信管理
│   ├── uverbs_*.c # 用户态Verbs接口
│   └── ...
├── hw/            # 硬件驱动
│   ├── mthca/     # Mellanox ConnectX
│   ├── mlx4/      # Mellanox ConnectX-3
│   ├── mlx5/      # Mellanox ConnectX-4/5/6
│   ├── hfi1/      # Intel Omni-Path
│   └── ...
├── sw/            # 软件实现
│   └── rxe/       # RXe: 软件RDMA over UDP
└── ulp/           # 上层协议
    ├── srpt/      # SCSI RDMA Protocol (SRP Target)
    ├── isert/     # iSER (iSCSI Extensions for RDMA)
    └── ...
```

用户态应用通过`/dev/infiniband/uverbsN`字符设备与内核RDMA栈交互——`uverbs`(用户态Verbs)接口允许应用直接操作QP/MR/CQ，数据路径完全不经过内核。

> **数据库视角**：RDMA在分布式数据库中的应用。Paxos/Raft共识协议需要多数派确认，每次确认涉及网络往返。RDMA的亚微秒延迟和零拷贝特性使Paxos日志复制延迟从TCP的约100微秒降到约10微秒。Oracle RAC使用RDMA进行缓存融合(Cache Fusion)，PolarDB使用RDMA加速分布式查询的RPC。但RDMA的编程模型复杂——MR注册/注销、QP连接管理、错误恢复都是挑战。

> **AI视角**：NCCL集合通信与RDMA。多GPU训练中，AllReduce操作是瓶颈。NCCL(NVIDIA Collective Communications Library)使用RDMA/RoCE在GPU间直接传输数据，绕过CPU。GPU → NVLink → 本地网卡 → RDMA → 远端网卡 → NVLink → 远端GPU，全程无CPU参与。RDMA的低延迟和高带宽使大规模训练的通信效率成为可能。

---

本章建立了对存储I/O硬件通路的认知：NVMe的多队列模型是blk-mq的硬件镜像，DMA映射是设备访问内存的桥梁，RDMA的内核旁路是高性能网络的基础。第21章将看到blk-mq如何将block层的request映射到NVMe的SQ/CQ，第23章将看到io_uring如何将NVMe的异步模型暴露给应用层，第24章将对比RDMA与传统网络栈的架构差异。理解硬件通路，才能理解软件I/O栈的设计动机。
