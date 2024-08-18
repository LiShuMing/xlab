---
chapter: 4
part: 第一篇 硬件与架构 —— 计算的物理边界
title: 互连、加速器与CXL
source_anchor:
  - drivers/cxl/
  - drivers/gpu/drm/
  - drivers/accel/drm_accel.c
  - drivers/accel/amdxdna/
  - drivers/accel/habanalabs/
  - drivers/accel/rocket/
  - drivers/accel/ivpu/
status: done
---

# 第4章 互连、加速器与CXL

## 写作目标

理解现代计算中互连总线与加速器的硬件架构，掌握CXL缓存一致性互连和Linux加速器驱动框架，为第九篇AI适配建立硬件基础。

## 章节大纲

### 4.1 PCIe拓扑与带宽模型

- PCIe层次结构：Root Complex → Switch → Endpoint
- Gen3/Gen4/Gen5带宽：x1/x4/x8/x16通道数
- TLP(Transaction Layer Packet)与DLLP
- ASPM(Active State Power Management)
- 带宽计算：编码开销与有效吞吐

### 4.2 CXL：缓存一致性互连

- CXL三个协议层：CXL.io / CXL.cache / CXL.mem
- Type 1/2/3设备的语义差异
- **精读** `drivers/cxl/`：
  - `drivers/cxl/core/`：CXL核心抽象
  - `drivers/cxl/mem.c`：CXL内存设备驱动
  - `drivers/cxl/pmem.c`：CXL持久内存
  - `drivers/cxl/port.c`：CXL端口/交换机
  - `drivers/cxl/pmu.h`：CXL性能监控
- CXL与内存池化：共享内存的未来
- *AI视角*：CXL共享内存池化推理架构展望——多GPU共享主机内存池

### 4.3 GPU与DRM子系统

- GPU架构概览：SIMT执行模型与显存层级
- DRM(Direct Rendering Manager)框架：`drivers/gpu/drm/`
  - GEM(Graphics Execution Manager)：显存对象管理
  - TTM(Translation Table Manager)：显存区域管理
  - 命令提交与 fence 机制
- AMD GPU驱动：`drivers/gpu/drm/amd/amdgpu/`
  - KFD(Kernel Fusion Driver)：`drivers/gpu/drm/amd/amdkfd/`——HSA计算
- NVIDIA Nouveau驱动：`drivers/gpu/drm/nouveau/`

### 4.4 AI加速器驱动框架

- `drivers/accel/`：独立的加速器子系统
  - `drivers/accel/drm_accel.c`：通用基础设施——为何从DRM中分离
  - 与DRM的复用关系：GEM/fence/内存管理
- **精读** `drivers/accel/amdxdna/`：
  - `amdxdna_ctx.c`：计算上下文管理
  - `amdxdna_gem.c`：显存对象管理
  - `amdxdna_mailbox.c`：邮箱通信机制
  - `aie2_pci.c`：NPU PCI设备管理
  - `aie2_solver.c`：资源求解器
  - NPU各代(NPU1/4/5/6)的寄存器定义
- Habana Gaudi：`drivers/accel/habanalabs/`——GAUDI/GAUDI2/GAUDI3
- Intel NPU：`drivers/accel/ivpu/`
- Rocket NPU：`drivers/accel/rocket/`
- *AI视角*：加速器驱动模型如何影响推理框架的内存管理

## 关键源文件清单

| 文件/目录 | 行数 | 关注点 |
|-----------|------|--------|
| `drivers/cxl/` | — | CXL驱动全家桶 |
| `drivers/accel/drm_accel.c` | ~200 | 加速器框架核心 |
| `drivers/accel/amdxdna/` | — | AMD XDNA NPU驱动 |
| `drivers/accel/habanalabs/` | — | Habana Gaudi驱动 |
| `drivers/accel/rocket/` | ~10文件 | Rocket NPU驱动 |
| `drivers/gpu/drm/amd/amdgpu/` | — | AMD GPU驱动 |

## 跨章依赖

- 本章是第32章（GPU/AI加速器OS管理）的前置
- 本章是第33章（CXL与异构内存）的前置
