# 第32章 GPU/AI加速器的OS管理

> 源码锚点：`drivers/accel/drm_accel.c`、`drivers/accel/amdxdna/`、`mm/hmm.c`、`mm/migrate_device.c`、`kernel/cgroup/dmem.c`

GPU和AI加速器是AI工作负载的核心硬件——Linux通过DRM/accel驱动框架管理这些设备，通过HMM实现统一内存，通过dmem cgroup实现显存隔离。理解加速器的OS管理层，才能优化推理和训练的系统栈。

## 32.1 DRM/accel驱动框架

### DRM子系统

DRM(Direct Rendering Manager)最初为GPU图形驱动设计——管理显存、命令提交和显示输出：

- **GEM(Graphics Execution Manager)**：显存对象管理——分配、映射、共享GPU显存
- **TTM(Translation Table Manager)**：多显存区域管理——在VRAM和系统内存间迁移
- **命令提交**：用户态通过ioctl提交GPU命令——内核验证后写入命令缓冲区
- **fence**：GPU操作的同步机制——CPU等待GPU完成特定操作
- **DRM调度器**：`drivers/gpu/drm/scheduler/`——GPU命令队列调度，防止一个任务独占GPU

### accel子系统

`drivers/accel/`为AI加速器从DRM中独立出来——AI加速器不需要显示功能：

```c
// drivers/accel/drm_accel.c
// accel设备注册：
// 1. 复用DRM的核心基础设施(GEM/调度器/fence)
// 2. 不注册DRM的显示相关功能(输出/CRTC/encoder)
// 3. 独立的设备节点：/dev/accel/accelN
```

accel与DRM的关系：accel是DRM的"子集"——共享GEM对象和调度器，但不包含任何图形功能。这使得AI加速器驱动更简洁——无需实现无关的显示接口。

## 32.2 AMD XDNA NPU驱动

`drivers/accel/amdxdna/`是AMD NPU的内核驱动——展示了AI加速器驱动的典型架构：

### 计算上下文管理

`amdxdna_ctx.c`管理NPU的计算上下文——类似GPU的CUDA context：

```
创建上下文 → 分配NPU计算资源 → 加载模型 → 执行推理 → 销毁上下文
```

### 显存对象管理

`amdxdna_gem.c`基于GEM框架管理NPU的内存——分配device buffer、映射到用户地址空间、处理迁移。

### 邮箱通信

`amdxdna_mailbox.c`实现host→NPU的命令传递——通过PCIe的mailbox寄存器：

```
用户态提交推理请求 → 内核构造命令 → 写入mailbox → NPU固件读取并执行
→ NPU完成 → 中断通知 → 内核唤醒等待进程
```

### 资源求解器

`aie2_solver.c`是NPU的资源分配器——NPU有多个计算核心(AIE tile)，求解器根据模型需求分配最优的tile组合——类似调度器的资源分配。

## 32.3 其他AI加速器驱动

- **Habana Gaudi**(`drivers/accel/habanalabs/`)：训练专用加速器——多芯片互联、大规模并行训练
- **Intel NPU**(`drivers/accel/ivpu/`)：Intel的神经处理单元——集成在Meteor Lake等处理器中
- **Rocket NPU**(`drivers/accel/rocket/`)：RISC-V NPU——开源AI加速器参考实现

## 32.4 HMM与统一内存

### HMM(Heterogeneous Memory Management)

`mm/hmm.c`实现异构内存管理——CPU和设备共享统一的地址空间：

```
传统模型：CPU内存 ←拷贝→ 设备内存 (两套独立的地址空间)
HMM模型：  CPU和设备共享同一虚拟地址空间 → 页面在CPU和设备间按需迁移
```

### hmm_range_fault()

```c
// mm/hmm.c (简化)
// 设备访问虚拟地址时，HMM确保页面在设备端可访问：
// 1. 页面在CPU内存 → 迁移到设备内存 或 建立设备映射
// 2. 页面在设备内存 → 直接访问
// 3. 页面不存在 → 触发缺页处理
int hmm_range_fault(struct hmm_range *range)
{
    // 遍历地址范围，为每个页面建立设备端映射
    // 必要时迁移页面到设备内存
}
```

### 设备页面迁移

`mm/migrate_device.c`实现页面在CPU内存与设备内存间的迁移：

```c
// 迁移流程：
migrate_vma_setup()    // 收集待迁移页面
migrate_vma_pages()    // 执行迁移：分配设备页、拷贝数据、更新页表
migrate_vma_finalize() // 确认迁移：释放旧页面
```

设备页面迁移的挑战：迁移期间页面可能被CPU和设备同时访问——需要同步机制防止数据丢失。

> **AI视角**：统一内存对推理框架的简化。传统推理框架需要显式管理CPU↔GPU数据拷贝(cudaMemcpy等)。HMM统一内存让开发者使用统一地址——数据自动迁移到访问它的设备。PyTorch的统一内存(unified memory)模式基于此机制。

## 32.5 设备内存cgroup

### dmem控制器

`kernel/cgroup/dmem.c`实现设备内存的cgroup隔离——限制cgroup使用的GPU/NPU显存量：

```c
// dmem charge/uncharge机制：
// 分配GPU显存 → dmem_charge() → 检查cgroup限额
// 释放GPU显存 → dmem_uncharge() → 减少cgroup使用量
// 超过限额 → 分配失败(类似ENOMEM)
```

dmem与`mm/memcontrol.c`的类比：
- memcg限制CPU内存使用量
- dmem限制设备内存使用量
- 两者都支持层级结构——子cgroup的限额不超过父cgroup

> **AI视角**：多租户推理的显存隔离。云上推理服务需要隔离不同租户的GPU显存使用——防止一个大模型推理耗尽显存导致其他租户OOM。dmem cgroup实现了推理服务的显存隔离——每个cgroup分配固定的显存配额，超出配额的分配请求被拒绝。

---

本章建立了对GPU/AI加速器OS管理的完整认知：DRM/accel驱动框架管理加速器设备，GEM管理显存对象，HMM实现CPU与设备的统一内存，设备页面迁移支持数据在异构内存间移动，dmem cgroup实现多租户显存隔离。AI加速器的OS管理是AI系统栈的关键层——理解这一层才能优化推理的延迟和吞吐。
