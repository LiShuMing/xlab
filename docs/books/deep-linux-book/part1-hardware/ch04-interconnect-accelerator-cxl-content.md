# 第4章 互连、加速器与CXL

> 源码锚点：`drivers/cxl/`、`drivers/gpu/drm/`、`drivers/accel/drm_accel.c`、`drivers/accel/amdxdna/`、`drivers/accel/habanalabs/`、`drivers/accel/rocket/`

CPU不再是唯一的计算引擎。GPU、NPU、DSA等加速器已经成为计算架构的一等公民，而连接它们的互连总线决定了数据搬运的效率。本章聚焦PCIe/CXL互连和加速器驱动框架，这是第九篇AI适配的硬件基础。

## 4.1 PCIe拓扑与带宽模型

### PCIe层次结构

PCIe(Peripheral Component Interconnect Express)是当前最主流的I/O互连总线，采用点对点串行传输：

```
CPU ─── Root Complex ─── Switch ──┬── Endpoint (NVMe SSD)
         (RC)           │         ├── Endpoint (GPU)
                        │         └── Endpoint (NIC)
                        │
                        └── Switch ──┬── Endpoint (NPU)
                                    └── Endpoint (CXL内存)
```

- **Root Complex (RC)**：CPU侧的PCIe控制器，是PCIe树的根
- **Switch**：PCIe交换机，扩展端口数量，转发TLP包
- **Endpoint**：终端设备，NVMe/GPU/NIC等

### 带宽计算

PCIe采用全双工传输，每个方向独立。带宽由代数(Generation)和通道数(Lane)决定：

| 代数 | 编码 | 每通道带宽(单向) | x16总带宽(双向) |
|------|------|----------------|----------------|
| Gen3 | 128b/130b | ~985 MB/s | ~31.5 GB/s |
| Gen4 | 128b/130b | ~1.97 GB/s | ~63 GB/s |
| Gen5 | 128b/130b | ~3.94 GB/s | ~126 GB/s |
| Gen6 | 64b/66b(PAM4) | ~7.56 GB/s | ~242 GB/s |

注意编码开销：Gen3/4/5使用128b/130b编码（每128比特数据加2比特开销，约1.5%），Gen6改用PAM4调制和更高效的64b/66b编码。

实际有效带宽低于理论值——TLP包头、DLLP确认、流量控制开销大约占10-20%。一个Gen5 x16 NVMe SSD的理论带宽约14 GB/s，实际约12-13 GB/s。

### TLP与DLLP

PCIe的事务层协议：

- **TLP(Transaction Layer Packet)**：承载数据的事务包，包含包头(Header)、数据载荷(Data Payload)、摘要(ECRC)。TLP类型包括Memory Read/Write、Completion、Configuration Read/Write等。
- **DLLP(Data Link Layer Packet)**：链路层确认包，用于TLP的可靠传输。ACK/NACK机制保证TLP不丢失、不乱序。

### ASPM(Active State Power Management)

PCIe链路的动态功耗管理：

- **L0s**：链路空闲时快速进入低功耗状态，恢复延迟~100ns
- **L1**：更深度的低功耗状态，恢复延迟~1-10μs
- **L1.2**：最深度低功耗，关闭链路收发器，恢复延迟~数十μs

ASPM对延迟敏感的场景（如NVMe I/O）有影响——链路从L1恢复的延迟可能占总I/O延迟的显著比例。Linux的`pcie_aspm=performance`内核参数可以禁用ASPM，牺牲功耗换延迟。

## 4.2 CXL：缓存一致性互连

### CXL的三个协议层

CXL(Compute Express Link)建立在PCIe物理层之上，新增了三个协议：

| 协议 | 全称 | 功能 | 类比 |
|------|------|------|------|
| CXL.io | I/O协议 | 设备发现、配置、中断 | 标准PCIe |
| CXL.cache | 缓存协议 | 设备缓存主机内存 | 设备的CPU Cache |
| CXL.mem | 内存协议 | 主机访问设备内存 | 设备的内存条 |

CXL.cache和CXL.mem是CXL相对PCIe的关键扩展——它们提供了**缓存一致性**的内存访问，这是PCIe不具备的。

### Type 1/2/3设备

CXL定义了三种设备类型，对应不同的协议组合：

| 类型 | 支持协议 | 典型设备 | 缓存方向 |
|------|---------|---------|---------|
| Type 1 | CXL.io + CXL.cache | 智能网卡(DPU) | 设备缓存主机内存 |
| Type 2 | CXL.io + CXL.cache + CXL.mem | GPU/加速器 | 双向：设备缓存主机内存，主机访问设备内存 |
| Type 3 | CXL.io + CXL.mem | CXL内存扩展 | 主机访问设备内存 |

**Type 3是最简单的**——CXL内存扩展设备，本质上是一块通过CXL连接的DRAM，主机通过CXL.mem协议直接访问，像访问本地内存一样。这就是CXL内存池化的基础。

**Type 2最有野心**——GPU既缓存主机内存(CXL.cache)，又暴露自己的显存给主机(CXL.mem)，CPU和GPU共享一致的内存视图。这消除了传统的PCIe DMA拷贝模型——CPU和GPU可以直接操作同一块内存。

### 精读 drivers/cxl/

Linux CXL子系统在`drivers/cxl/`下，目录结构清晰：

```
drivers/cxl/
├── core/        # CXL核心库(被其他模块链接)
│   ├── port.c   # 端口/交换机核心
│   ├── memdev.c # 内存设备核心
│   ├── region.c # 区域(Region)管理
│   ├── pmu.c    # 性能监控
│   └── ...
├── mem.c        # CXL内存设备PCI驱动
├── pmem.c       # CXL持久内存驱动
├── port.c       # CXL端口PCI驱动
├── pci.c        # CXL PCI通用功能
├── acpi.c       # ACPI表解析
└── security.c   # 安全特性
```

**`drivers/cxl/mem.c`**——CXL内存设备驱动：

```c
// drivers/cxl/mem.c
/**
 * DOC: cxl mem
 *
 * CXL memory endpoint devices and switches are CXL capable devices that are
 * participating in CXL.mem protocol. Their functionality builds on top of the
 * CXL.io protocol that allows enumerating and configuring components via
 * standard PCI mechanisms.
 *
 * The cxl_mem driver owns kicking off the enumeration of this CXL.mem
 * capability. With the detection of a CXL capable endpoint, the driver will
 * walk up to find the platform specific port it is connected to, and determine
 * if there are intervening switches in the path.
 */
```

`cxl_mem`驱动的核心职责：
1. 发现CXL内存端点设备
2. 向上遍历找到连接的CXL端口和交换机
3. 将设备注册为CXL端点端口
4. 管理设备的DPA(Device Physical Address)空间
5. 通过邮箱命令(Mailbox Commands)配置设备

**CXL核心的Region管理**——`drivers/cxl/core/`中的region.c负责将多个CXL内存设备的地址空间组合为系统可用的内存区域：

```c
// drivers/cxl/core/core.h
struct cxl_region_context {
    struct cxl_endpoint_decoder *cxled;
    struct range hpa_range;             // 主机物理地址范围
    int interleave_ways;               // 交错路数
    int interleave_granularity;        // 交错粒度
};
```

CXL支持**交错(Interleave)**——多个CXL内存设备的地址空间交错编址，类似RAID0的条带化。这既增加了带宽（多设备并行服务），又提供了跨设备的地址连续性。

CXL的RAS(Reliability, Availability, Serviceability)特性也由核心层管理——`cxl_handle_ras()`处理RAS错误，`cxl_get_poison_by_endpoint()`查询毒化页面。

### CXL与内存池化

CXL的Type 3设备可以实现**内存池化**——多个主机共享同一个CXL内存设备。这在数据库和AI推理场景中有巨大潜力：

- **数据库**：多个数据库实例共享CXL内存池作为扩展Buffer Pool
- **AI推理**：多个GPU共享CXL内存池存放模型参数和KV Cache

当前Linux CXL驱动主要支持单主机的内存扩展（CXL内存作为系统内存的一部分），多主机共享的池化模式尚在早期阶段。

> **AI视角**：CXL共享内存池化推理架构展望。当前推理的瓶颈是GPU显存容量——70B模型需要140GB+显存，单卡放不下。CXL内存池化可以让多GPU共享主机侧的大容量CXL内存，KV Cache按需从CXL内存换入GPU HBM。结合CXL.cache，GPU可以缓存CXL内存中的热数据，减少换入次数。第33章会深入讨论CXL与异构内存管理。

## 4.3 GPU与DRM子系统

### GPU架构概览

GPU的执行模型是SIMT(Single Instruction, Multiple Threads)——一条指令驱动多个线程同时执行，不同线程操作不同数据。这与CPU的SISD/SIMD模型有本质区别：

| 特征 | CPU | GPU |
|------|-----|-----|
| 执行模型 | SISD/SIMD | SIMT |
| 核心数 | 8-128 | 数千-数万 |
| 单线程性能 | 极高 | 较低 |
| 内存带宽 | ~50 GB/s | ~2 TB/s (HBM) |
| 内存容量 | 数百GB | 16-192 GB |
| 延迟优化 | 深流水线、大Cache | 高吞吐、高并行 |

GPU的显存层级：

```
GPU Core → L1 (64 KB/SM) → L2 (数MB) → HBM (16-192 GB) → PCIe → 主机内存
```

HBM(High Bandwidth Memory)是GPU的高带宽显存，通过3D堆叠实现约2 TB/s的带宽——比DDR5高约30倍。但容量有限，这是推理场景的核心约束。

### DRM框架

DRM(Direct Rendering Manager)是Linux的GPU/显示子系统框架，位于`drivers/gpu/drm/`：

核心抽象：

- **GEM(Graphics Execution Manager)**：显存对象管理。每个GEM对象代表一块显存，提供`drm_gem_object`抽象。GEM处理显存分配、映射、共享。
- **TTM(Translation Table Manager)**：更通用的显存区域管理，支持在系统内存、VRAM、AGP等不同内存类型之间迁移。AMD GPU驱动使用TTM。
- **fence机制**：GPU命令的完成通知。CPU提交命令后获得一个`dma_fence`对象，可以等待GPU完成或注册回调。这是CPU/GPU异步协作的基础。
- **DRM调度器**：`drivers/gpu/drm/scheduler/`——GPU命令的调度队列，管理命令的提交、依赖、超时。

用户态通过`/dev/dri/cardN`或`/dev/dri/renderN`字符设备与DRM交互——前者用于显示，后者用于纯计算(GPU compute)。

### AMD GPU驱动

AMD的GPU驱动(`drivers/gpu/drm/amd/`)是Linux中最完整的开源GPU驱动：

- `amdgpu/`：显示和计算驱动，处理显存管理、命令提交、显示输出
- `amdkfd/`：HSA(Heterogeneous System Architecture)计算驱动，提供用户态计算队列

KFD(Kernel Fusion Driver)特别值得注意——它允许用户态应用直接提交计算命令到GPU，无需经过内核态的命令缓冲，这是AMD ROCm计算平台的基础。

## 4.4 AI加速器驱动框架

### accel子系统：从DRM中分离

Linux 7.0引入了`drivers/accel/`子系统，专门管理AI加速器。它复用DRM的基础设施（GEM、fence、调度器），但作为独立子系统存在。

**精读 `drivers/accel/drm_accel.c`**——加速器框架核心：

```c
// drivers/accel/drm_accel.c
// Copyright 2022 HabanaLabs, Ltd.

static const struct class accel_class = {
    .name = "accel",
    .devnode = accel_devnode,           // 设备节点: /dev/accel/accelN
};

int accel_open(struct inode *inode, struct file *filp)
{
    // 与DRM相同的打开流程
    minor = drm_minor_acquire(&accel_minors_xa, iminor(inode));
    ...
    retcode = drm_open_helper(filp, minor);
    ...
}
```

为什么从DRM分离？原因有三：

1. **语义不同**：DRM面向图形渲染，有display/crtc/encoder等概念；加速器只做计算，不需要这些
2. **设备节点隔离**：加速器使用`/dev/accel/accelN`而非`/dev/dri/`，权限和容器隔离更清晰
3. **独立的设备类**：`accel_class`允许udev规则和容器运行时单独管理加速器设备

accel框架复用了DRM的**大量基础设施**：GEM显存管理、`dma_fence`完成通知、GPU调度器、ioctl框架。这意味着加速器驱动无需重新发明轮子，只需实现硬件特定的部分。

### 精读 drivers/accel/amdxdna/：AMD XDNA NPU驱动

AMD XDNA NPU是AMD的AI加速器系列（NPU1/4/5/6），驱动在`drivers/accel/amdxdna/`下。这是Linux中首个主流NPU加速器驱动，值得精读。

**驱动结构**：

```
amdxdna/
├── amdxdna_ctx.c       # 计算上下文管理
├── amdxdna_ctx.h       # 上下文头文件
├── amdxdna_gem.c       # GEM显存对象
├── amdxdna_gem.h       # GEM头文件
├── amdxdna_mailbox.c   # 邮箱通信(host↔NPU)
├── amdxdna_mailbox_helper.c
├── amdxdna_pci_drv.c   # PCI驱动框架
├── amdxdna_pm.c        # 电源管理
├── amdxdna_iommu.c     # IOMMU集成
├── aie2_pci.c          # AIE2 NPU PCI设备管理
├── aie2_solver.c       # 资源求解器
├── aie2_message.c      # AIE2消息处理
├── aie2_pm.c           # AIE2电源管理
├── aie2_smu.c          # SMU(系统管理单元)
├── npu1_regs.c         # NPU1寄存器定义
├── npu4_regs.c         # NPU4寄存器定义
├── npu5_regs.c         # NPU5寄存器定义
├── npu6_regs.c         # NPU6寄存器定义
└── TODO                # 待办事项
```

**计算上下文**——`amdxdna_ctx.c`：

```c
// drivers/accel/amdxdna/amdxdna_ctx.c
struct amdxdna_fence {
    struct dma_fence base;       // 复用DRM的fence机制
    spinlock_t lock;
    struct amdxdna_hwctx *hwctx; // 所属硬件上下文
};
```

上下文(hwctx)是NPU计算的基本调度单元——每个用户进程创建自己的hwctx，NPU硬件在多个hwctx之间切换执行。fence机制与DRM完全一致——CPU提交命令获得fence，可以等待NPU完成或注册回调。

**邮箱通信**——`amdxdna_mailbox.c`：

主机与NPU之间的命令传递通过邮箱(Mailbox)机制——主机将命令写入共享内存中的邮箱队列，NPU固件从队列取命令执行。这是host↔加速器通信的标准模式。

**资源求解器**——`aie2_solver.c`：

NPU的AIE(Array of AI Engines)是二维的处理器阵列，需要按列分配给不同的上下文。`aie2_solver`负责在多个上下文之间划分AIE列资源——这是一个类似伙伴系统的资源分配问题，需要考虑列的连续性和碎片化。

**各代NPU的寄存器定义**——`npu{1,4,5,6}_regs.c`：

NPU的硬件寄存器布局在不同代之间有差异，驱动通过分离的寄存器定义文件支持多代硬件。这是硬件驱动常见的演进模式。

### 其他AI加速器驱动

- **Habana Gaudi**：`drivers/accel/habanalabs/`——Intel的AI训练加速器，支持GAUDI/GAUDI2/GAUDI3。Gaudi的驱动更成熟，包含完整的命令提交、内存管理、调试接口。
- **Intel NPU**：`drivers/accel/ivpu/`——Intel的神经处理单元，集成在Meteor Lake等SoC中。
- **Rocket NPU**：`drivers/accel/rocket/`——新兴的AI加速器驱动，结构简洁：
  ```c
  // drivers/accel/rocket/
  rocket_core.c     // 核心管理
  rocket_device.c   // 设备管理
  rocket_drv.c      // 驱动框架
  rocket_gem.c      // GEM显存管理
  ```

### 加速器驱动的通用模式

通过对比这些驱动，可以总结出AI加速器驱动的通用架构：

```
用户态应用 (PyTorch/TensorFlow)
    │ ioctl / mmap
    ▼
accel框架 (drm_accel.c + DRM基础设施)
    │ GEM / fence / scheduler
    ▼
加速器驱动 (amdxdna / habanalabs / ivpu / rocket)
    │ 上下文管理 / 命令提交 / 邮箱通信
    ▼
加速器硬件 (NPU / DSA / Gaudi)
```

关键抽象：
1. **GEM对象**：显存/设备内存的统一表示，支持mmap到用户态
2. **dma_fence**：命令完成的异步通知机制
3. **GPU调度器**：命令队列管理、依赖追踪、超时处理
4. **上下文**：隔离不同用户/进程的计算资源

> **AI视角**：加速器驱动模型如何影响推理框架。推理框架(如vLLM、TensorRT-LLM)通过用户态驱动库(如AMD ROCm、Intel Level Zero)与加速器交互。驱动模型的每个设计决策都向上传递：GEM对象的mmap决定了推理框架如何管理显存；fence机制决定了异步执行模型；上下文隔离决定了多租户推理的安全性。理解驱动层，才能理解推理框架的内存管理为何如此设计——第32章将深入分析。

---

本章建立了对互连与加速器架构的认知：PCIe/CXL决定了数据搬运的带宽和延迟，DRM/accel框架决定了加速器的编程模型。CXL的缓存一致性互连是未来异构计算的关键基础设施，accel子系统是AI加速器驱动的新标准。第九篇将从这些硬件基础出发，讨论GPU/NPU的OS管理、CXL异构内存和面向AI工作负载的OS演进。
