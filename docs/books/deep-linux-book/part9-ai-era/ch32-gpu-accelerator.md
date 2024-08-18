---
chapter: 32
part: 第九篇 AI时代的OS与硬件适配
title: GPU/AI加速器的OS管理
source_anchor:
  - drivers/gpu/drm/
  - drivers/accel/drm_accel.c
  - drivers/accel/amdxdna/
  - drivers/accel/habanalabs/
  - drivers/accel/rocket/
  - mm/hmm.c
  - mm/migrate_device.c
  - kernel/cgroup/dmem.c
status: done
---

# 第32章 GPU/AI加速器的OS管理

## 写作目标

深入理解GPU/AI加速器在Linux中的驱动模型与资源管理，掌握显存管理、统一内存与算力隔离机制。

## 章节大纲

### 32.1 DRM/accel驱动框架

- DRM子系统：`drivers/gpu/drm/`
  - GEM(Graphics Execution Manager)：显存对象
  - TTM(Translation Table Manager)：显存区域
  - 命令提交与fence
  - DRM调度器：`drivers/gpu/drm/scheduler/`
- accel子系统：`drivers/accel/`
  - **精读** `drivers/accel/drm_accel.c`：
    - 与DRM的复用关系
    - 为何从DRM分离——AI加速器不需要显示功能
    - 注册与发现机制

### 32.2 AMD XDNA NPU驱动精读

- **精读** `drivers/accel/amdxdna/`：
  - `amdxdna_ctx.c`：计算上下文管理
    - 上下文创建/销毁/调度
  - `amdxdna_gem.c`：显存对象管理
    - GEM对象在NPU上的映射
  - `amdxdna_mailbox.c`：邮箱通信
    - host→NPU的命令传递
  - `aie2_pci.c`：PCI设备管理
  - `aie2_solver.c`：资源求解器
    - 计算资源的分配优化
  - `aie2_pm.c`/`aie2_smu.c`：电源与时钟管理
  - NPU各代差异：`npu1_regs.c`/`npu4_regs.c`/`npu5_regs.c`/`npu6_regs.c`
  - IOMMU：`amdxdna_iommu.c`

### 32.3 其他AI加速器驱动

- Habana Gaudi：`drivers/accel/habanalabs/`
  - `common/`：通用基础设施
  - `gaudi/`/`gaudi2/`：各代驱动
  - 计算引擎与同步机制
- Intel NPU：`drivers/accel/ivpu/`
- Rocket NPU：`drivers/accel/rocket/`
  - `rocket_core.c`：核心管理
  - `rocket_gem.c`：显存管理

### 32.4 HMM与统一内存

- **精读** `mm/hmm.c`：Heterogeneous Memory Management
  - 设备透明的内存迁移
  - CPU页表与设备页表的同步
  - `hmm_range_fault()`：设备触发缺页
- **精读** `mm/migrate_device.c`：
  - 页面在CPU内存与设备内存间的迁移
  - `migrate_vma_setup()`/`migrate_vma_pages()`/`migrate_vma_finalize()`
- *AI视角*：统一内存对推理框架的简化——无需显式拷贝

### 32.5 设备内存cgroup

- **精读** `kernel/cgroup/dmem.c`：
  - 设备内存(GPU/NPU显存)的cgroup隔离
  - charge/uncharge机制
  - 与`mm/memcontrol.c`的类比
- *AI视角*：多租户推理的显存隔离——关键能力与实现挑战

## 关键源文件清单

| 文件/目录 | 关注点 |
|-----------|--------|
| `drivers/accel/drm_accel.c` | 加速器框架 |
| `drivers/accel/amdxdna/` | AMD XDNA NPU |
| `mm/hmm.c` | 异构内存管理 |
| `mm/migrate_device.c` | 设备页面迁移 |
| `kernel/cgroup/dmem.c` | 设备内存cgroup |

## 跨章依赖

- 依赖第4章（互连与加速器）：硬件架构基础
- 依赖第8章（cgroup）：dmem控制器与cgroup框架的关系
