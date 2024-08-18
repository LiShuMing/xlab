# 第17章 GPU异构编译：SIMT世界的编译器适配

## 17.1 GPU执行模型与编译差异

### 17.1.1 SIMT vs 标量：Warp/Wavefront执行模型

```
CPU执行模型: 标量(SISD/MIMD)
  每个核心独立执行自己的指令流
  分支独立执行, 无divergence问题

GPU执行模型: SIMT (Single Instruction Multiple Threads)
  32个线程(NVIDIA Warp) / 64个线程(AMD Wavefront) 锁步执行
  同一Warp内所有线程共享PC(程序计数器)
  分支divergence: 同一Warp内线程走不同路径 → 串行化执行

  if (threadIdx.x < 16) path_A();
  else path_B();

  Warp0: 前16线程走path_A, 后16线程走path_B
  → 实际执行: path_A(前16活跃,后16屏蔽) + path_B(后16活跃,前16屏蔽)
  → 分支开销翻倍!

编译器影响:
  1. 避免divergent分支 → 用select/cmov替代
  2. 对齐内存访问 → 合并为coalesced load/store
  3. 减少warp内寄存器差异 → 均衡寄存器使用
```

### 17.1.2 GPU内存层次

```
GPU内存层次(延迟从小到大):
  寄存器       : 1周期     每线程私有
  共享内存     : ~5周期    同一Block共享 (user-managed cache)
  L1缓存       : ~30周期   同一SM共享
  L2缓存       : ~100周期  全局共享
  全局内存     : ~400周期  全局共享 (最大带宽瓶颈!)
  本地内存     : ~400周期  每线程私有 (寄存器溢出 → 极慢!)

编译器关键优化:
  1. 寄存器分配优化: 减少溢出(本地内存)
  2. 共享内存利用: 将频繁访问的全局数据缓存到shared memory
  3. 内存合并: 连续线程访问连续地址 → 单次内存事务
  4. 数据预取: 隐藏内存延迟(compute和memory overlap)
```

### 17.1.3 地址空间(0-5)在LLVM IR中的表示

```llvm
; GPU地址空间在LLVM IR中用addrspace表示
; NVIDIA NVPTX:
addrspace(0) ; 通用地址空间(Flat)
addrspace(1) ; 全局内存(GPU DRAM)
addrspace(3) ; 共享内存(Shared Memory)
addrspace(4) ; 常量内存(Constant Memory)
addrspace(5) ; 本地内存(Local Memory, 寄存器溢出)

; AMD AMDGPU:
addrspace(0) ; 通用
addrspace(1) ; 全局
addrspace(2) ; 区域(Region)
addrspace(3) ; 共享(LDS)
addrspace(4) ; 常量
addrspace(5) ; 私有(本地)

; 编译器生成地址空间相关的指令:
%val = load i32, ptr addrspace(1) %global_ptr    ; 全局内存加载
%val = load i32, ptr addrspace(3) %shared_ptr    ; 共享内存加载
store i32 %val, ptr addrspace(3) %shared_ptr     ; 共享内存存储
```

---

## 17.2 NVPTX后端

### 17.2.1 CUDA C++ → Clang → LLVM IR → NVPTX → PTX → SASS

```
完整编译路径:
  CUDA C++ (.cu)
    │ clang -x cuda
    ▼
  LLVM IR (带addrspace标注)
    │ NVPTX后端
    ▼
  PTX (并行线程执行, 类似汇编的可读格式)
    │ ptxas (NVIDIA PTX汇编器)
    ▼
  SASS (实际GPU微码, 不可读)

NVPTX关键特性:
  - 基于LLVM的完整CUDA编译支持
  - 支持所有CUDA特性: warp shuffle, cooperative groups, 动态并行
  - 自动地址空间推断(AllocaHoisting)
  - NVVMReflect: 运行时参数优化
```

### 17.2.2 NVPTX特有优化

```
AllocaHoisting:
  将kernel内的alloca提升到全局地址空间
  → 避免栈溢出(GPU栈空间有限)

NVVMReflect:
  __nvvm_reflect("kernel") → 编译期常量折叠
  → 条件编译的GPU版本

ImageOptimizer:
  纹理内存访问优化
  → 利用GPU的纹理缓存

WarpShuffle优化:
  将共享内存通信转为warp shuffle
  → 更低延迟(不需要shared memory)
```

---

## 17.3 AMDGPU后端

### 17.3.1 HIP → Clang → LLVM IR → AMDGPU → GCN ISA → HSACO

```
完整编译路径:
  HIP C++ (.hip)
    │ clang -x hip
    ▼
  LLVM IR (带addrspace标注)
    │ AMDGPU后端
    ▼
  GCN ISA (AMD GPU指令集)
    │ AMD代码对象格式
    ▼
  HSACO (HSA Code Object)

AMDGPU关键特性:
  - 支持AMD CDNA/RDNA架构
  - Wavefront宽度: 64线程(NVIDIA Warp的2倍)
  - 无限队列(Infinite Queue): 更灵活的kernel调度
  - Coherent内存: L2缓存一致性
```

### 17.3.2 AMDGPU特有优化

```
PromoteAlloca:
  将private内存alloca提升到向量寄存器
  → 如果寄存器足够, 消除local memory访问
  → 类似SROA, 但针对GPU架构

AnnotateUniformValues:
  标注uniform值(所有线程相同的值)
  → uniform值可以用标量寄存器而非向量寄存器
  → 减少向量寄存器压力

ExecMasking:
  优化分支的执行掩码
  → 用s_and_saveexec_b64等指令高效管理活跃线程
  → 比NVIDIA的谓词执行更灵活
```

---

## 17.4 OpenMP Offload机制

### 17.4.1 offload/ 目录架构

```
offload/
├── src/          : OpenMP目标端运行时
│   ├── Offload.cpp       : offload入口
│   ├── Device.cpp        : 设备管理
│   └── Omnipt.cpp        : OMPT追踪
└── cmake/        : 构建配置

编译流程:
  #pragma omp target teams distribute parallel for
  for (int i = 0; i < N; i++)
    A[i] = B[i] + C[i];

  → 编译为:
    1. 主机代码: 调用libomptarget将kernel发送到GPU
    2. 设备代码: LLVM IR → NVPTX/AMDGPU → GPU kernel
    3. 运行时: 数据传输 + kernel启动 + 结果回收
```

---

## 17.5 GPU vs CPU优化策略差异总结

```
策略差异对比:

1. Branch Divergence处理:
   CPU: 分支预测 + 乱序执行 → 分支几乎无开销
   GPU: SIMT锁步 → divergent分支串行化
   编译器: GPU用select替代分支, CPU保持分支

2. Memory Coalescing感知:
   CPU: 缓存行自动预取 → 程序员无需关心
   GPU: 必须连续线程访问连续地址 → 否则多次内存事务
   编译器: GPU生成结构化访问模式, 重排线程ID

3. Shared Memory利用:
   CPU: L1/L2自动缓存 → 无需手动管理
   GPU: 共享内存需要显式管理 → 手动缓存热数据
   编译器: PromoteAlloca/AllocaHoisting优化

4. 寄存器压力:
   CPU: 16-31个GPR → 溢出到L1缓存(~30周期)
   GPU: 255个向量寄存器 → 溢出到本地内存(~400周期!)
   编译器: GPU的寄存器分配更关键, 溢出代价更高

5. 延迟隐藏:
   CPU: 乱序执行 + 预取
   GPU: 大量线程切换(零开销调度)
   编译器: GPU增加占用率(occupancy) → 减少每线程寄存器
```

---

## 17.6 本章小结

本章解析了GPU异构编译的核心问题：

1. **SIMT执行模型**——Warp/Wavefront锁步执行，分支divergence导致串行化，编译器需避免divergent分支。
2. **内存层次**——寄存器→共享内存→全局内存，编译器需优化内存合并和共享内存利用。
3. **NVPTX后端**——CUDA→LLVM IR→PTX→SASS，AllocaHoisting和NVVMReflect优化。
4. **AMDGPU后端**——HIP→LLVM IR→GCN ISA→HSACO，PromoteAlloca和ExecMasking优化。
5. **CPU vs GPU优化差异**——分支、内存合并、共享内存、寄存器压力、延迟隐藏的策略完全不同。

下一章进入JIT编译——从MCJIT到ORC JIT v2的演进，以及JIT在数据库和LLM中的应用。
