# 第13章 目标后端：体系结构适配实战

## 13.1 后端通用架构：每个Target的目录模板

### 13.1.1 ISelLowering / ISelDAGToDAG / InstrInfo / RegisterInfo / FrameLowering

每个LLVM目标后端遵循统一的目录结构，由以下核心组件构成：

```
llvm/lib/Target/X86/  (以X86为例)
├── X86.td                    : TableGen顶层描述
├── X86RegisterInfo.td/.cpp   : 寄存器定义与分配约束
├── X86InstrInfo.td/.cpp      : 指令定义、编码、语义
├── X86ISelLowering.cpp       : DAG lowering(最重要的文件!)
├── X86ISelDAGToDAG.cpp       : 指令选择(模式匹配)
├── X86FrameLowering.cpp      : 栈帧布局(prologue/epilogue)
├── X86CallingConv.td         : 调用约定
├── X86Subtarget.cpp          : 子目标特性(CPU/Feature检测)
├── X86TargetMachine.cpp      : 目标机器配置
├── X86TargetTransformInfo.cpp: TTI代价模型(7331行)
├── X86Schedule*.td           : 调度模型(10+代微架构)
└── MCTargetDesc/             : MC层(编码/反编码/目标文件)
```

### 13.1.2 Subtarget机制：同一ISA不同微架构的差异处理

```c++
// Subtarget通过Feature bit区分同一ISA的不同微架构
class X86Subtarget : public X86GenSubtargetInfo {
  // Feature bits (由.td文件自动生成)
  bool HasAVX;
  bool HasAVX2;
  bool HasAVX512F;
  bool HasSSE42;
  bool HasBMI;
  bool HasFMA;
  // ...

  // 调度模型选择
  const X86ProcFamilyEnum ProcFamily;
  // Intel: Nehalem → SandyBridge → Haswell → Broadwell → Skylake → IceLake → SapphireRapids
  // AMD:   K8 → Bulldozer → Zen → Zen2 → Zen3 → Zen4

  // 根据CPU名选择Feature和调度模型
  void ParseSubtargetFeatures(StringRef CPU, StringRef TuneCPU, StringRef FS);
};
```

**体系结构锚点**：同一份X86代码在Skylake和Zen3上的最优调度策略可能完全不同——执行端口数量、延迟、吞吐量都不同。Subtarget机制让编译器为每个微架构生成不同的代码。

---

## 13.2 X86后端：CISC的编译器工程

### 13.2.1 X86ISelLowering.cpp：最大文件的工程解读

**源码**：`llvm/lib/Target/X86/X86ISelLowering.cpp`（~63898行！LLVM最大的目标文件）

X86ISelLowering负责将目标无关的DAG操作降低(Lower)为X86特定的操作：

```
Lowering的核心任务:

1. 调用约定Lowering:
   C calling convention: 参数通过rdi, rsi, rdx, rcx, r8, r9传递(前6个整数参数)
   Fast calling convention: 通过ecx, edx传递(前2个)
   Vector calling convention: 通过xmm0-xmm5传递向量参数

2. 不支持操作的Lowering:
   rotl i32 → (shl + shr + or) (如果没有BMI2)
   popcnt i32 → 查表 + 位操作 (如果没有POPCNT指令)
   cttz i32 → bsf + cmov (如果没有TZCNT)

3. 向量操作Lowering:
   <4 x i32> add → vpadd (AVX2) 或 padd (SSE2)
   <16 x i32> add → vpadd (AVX-512) 或 split+2×vpadd (AVX2)
   scatter → AVX-512 vpscatterdd 或 逐元素store

4. 特殊寻址模式:
   GEP + 常量 → [base + disp] 寻址
   GEP + 变量 → [base + index*scale + disp] 寻址
   X86的复杂寻址模式是CISC架构的编译器优势
```

### 13.2.2 AVX/SSE/AVX-512向量化路径

```
向量化路径选择(由Subtarget Feature决定):

SSE2 (128-bit, 所有x86-64都有):
  <4 x i32> add → paddd xmm
  <2 x i64> add → paddq xmm
  <4 x float> add → addps xmm

AVX (256-bit, SandyBridge+):
  <8 x i32> add → vpaddd ymm
  <8 x float> add → vaddps ymm

AVX2 (256-bit整数, Haswell+):
  <8 x i32> add → vpaddd ymm (整数)
  <4 x i64> add → vpaddq ymm

AVX-512 (512-bit, Skylake-X+):
  <16 x i32> add → vpaddd zmm
  <16 x float> add → vaddps zmm
  + mask寄存器: 条件向量化 vmaskmov
  + scatter/gather: vpscatterdd/vpgatherdd
```

### 13.2.3 X86特有Pass

```
X86CmovConversionPass:
  将cmov(条件移动)转为分支(或反之)
  基于PGO: 热路径用cmov(无分支预测失误), 冷路径用分支

X86AvoidStoreForwardingBlocks:
  避免store→load的转发阻塞
  Intel CPU: store后的load如果跨缓存行, 可能阻塞40+周期
  解决: 在store和load之间插入其他指令或改用寄存器传递

X86DomainReassignment:
  将向量指令从一个域(整数/SSE/AVX)转到另一个域
  例: 将整数向量操作转为SSE浮点操作(如果浮点端口更空闲)
  需要插入domain转换指令(cvtdq2ps等), 代价需要评估

X86CallFrameOptimization:
  优化函数调用时的栈帧操作
  合并相邻的push, 用mov替换push+pop
```

---

## 13.3 AArch64后端：RISC与SVE

### 13.3.1 固定指令长度的简化效应

AArch64的指令固定4字节，这简化了后端的很多问题：

```
简化1: 无需变长指令编码
  X86: 指令1-15字节, 需要复杂的编码/解码
  AArch64: 指令固定4字节, 编码简单

简化2: 无需复杂的指令对齐
  X86: 指令可能跨缓存行 → 取指复杂
  AArch64: 指令自然对齐 → 取指简单

简化3: 简单的调用约定
  AArch64 AAPCS64: 参数通过x0-x7传递(前8个整数)
  浮点/向量: 通过v0-v7传递
  栈对齐: 16字节(比X86的16字节更严格)

简化4: 无复杂寻址模式
  AArch64: [base + offset] 或 [base + index<<shift]
  没有 X86 的 [base + index*scale + disp]
  → 编译器需要更多显式地址计算指令
```

### 13.3.2 SVE可伸缩向量的编译支持

```
AArch64 SVE向量化路径:
  <vscale x 4 x i32> add → add z0.s, z0.s, z1.s
  <vscale x 8 x i16> mul → mul z0.h, z0.h, z1.h
  <vscale x 2 x i64> fmla → fmla z0.d, z1.d, z2.d

SVE的独特功能:
  1. 谓词向量(Predicated vector):
     whilelo p0.s, x0, x1   ; 生成活跃元素掩码
     ld1w z0.s, p0/z, [x2]  ; 条件加载(只加载活跃元素)

  2. 横向归约:
     uaddv d0, p0, z0.s     ; 向量求和

  3. 负载均衡:
     同一代码在128-bit和2048-bit SVE上都能运行
     编译器不需要知道实际向量宽度
```

### 13.3.3 AArch64特有Pass

```
A57FPLoadBalancing:
  Cortex-A57有两个浮点/向量流水线, 但不对等
  将浮点指令分配到两个流水线以平衡负载
  通过改变指令的目标寄存器组实现

AArch64LoadStoreOptimizer:
  合并相邻的load/store对:
    ldr x0, [sp, #0]        → ldp x0, x1, [sp, #0]
    ldr x1, [sp, #8]           (一对load, 单条指令)
  合并str pair同理

AArch64ConditionOptimizer:
  优化条件码链:
    cmp → b.ne → cmp → b.eq
    → 合并为单个比较和条件分支
```

---

## 13.4 RISC-V后端：模块化ISA的编译策略

### 13.4.1 基础ISA + 扩展的组合式后端

```
RISC-V ISA模块化设计:
  RV64I     : 基础整数指令集(必须)
  M         : 乘法/除法扩展
  A         : 原子扩展
  F         : 单精度浮点
  D         : 双精度浮点
  C         : 压缩指令(16位编码)
  V         : 向量扩展(可伸缩向量!)
  Zicsr     : CSR指令
  Zifencei  : 指令缓存刷新
  Zbb       : 基本位操作
  Zbs       : 单位操作
  ...更多扩展

编译器适配:
  Subtarget Feature: +m, +a, +f, +d, +c, +v, +zbb, ...
  每个Feature启用/禁用一组指令和Lowering规则
  -march=rv64gc → RV64IMAFDC (通用组合)
  -march=rv64gv → RV64IV (向量+基础)
```

### 13.4.2 RISC-V V向量扩展的指令选择

```
RISC-V V扩展与SVE的对比:
  相似: 都是可伸缩向量(vl寄存器控制活跃元素数)
  不同: V扩展使用显式的vsetvli指令设置向量配置

  vsetvli t0, a0, e32, m1  ; 设置: 元素宽度32bit, LMUL=1
  vle32.v v0, (a1)          ; 加载向量
  vadd.vv v0, v0, v1        ; 向量加法
  vse32.v v0, (a2)          ; 存储向量

V扩展的编译挑战:
  1. 配置管理: vsetvli的开销需要最小化(批量设置)
  2. LMUL选择: 向量分组(多个寄存器组合为更宽的向量)
  3. 尾部处理: 剩余元素的处理方式(undisturbed/agnostic)
  4. 类型合法化: 不支持的操作需要扩展/拆分
```

---

## 13.5 调用约定：ABI的编译器实现

### 13.5.1 三大ABI对比

| 特性 | X86-64 System V | AArch64 AAPCS64 | RISC-V LP64D |
|------|----------------|-----------------|-------------|
| 整数参数 | rdi,rsi,rdx,rcx,r8,r9 | x0-x7 | a0-a7 |
| 浮点参数 | xmm0-xmm7 | v0-v7 | fa0-fa7 |
| 返回值 | rax,rdx | x0,x1 | a0,a1 |
| 栈对齐 | 16字节(调用前) | 16字节 | 16字节 |
| 栈帧指针 | rbp(可选) | x29(fp) | s0(fp) |
| 红区 | 128字节(叶子函数) | 无 | 无 |
| 向量传递 | xmm0-xmm7 | v0-v7 | v0-v7(V扩展) |
| callee-saved | rbx,r12-r15 | x19-x28 | s0-s11 |

### 13.5.2 CallingConv.td：调用约定的TableGen描述

```
// X86-64 System V调用约定(简化)
def CC_X86_64_C : CallingConv<[
  CCIfType<[i32], CCAssignToReg<[EDI, ESI, EDX, ECX, R8D, R9D]>>,
  CCIfType<[i64], CCAssignToReg<[RDI, RSI, RDX, RCX, R8, R9]>>,
  CCIfType<[f32], CCAssignToReg<[XMM0, XMM1, XMM2, XMM3, XMM4, XMM5, XMM6, XMM7]>>,
  CCIfType<[f64], CCAssignToReg<[XMM0, XMM1, XMM2, XMM3, XMM4, XMM5, XMM6, XMM7]>>,
  // 寄存器传完后, 按栈对齐传递
  CCAssignToStack<8, 8>
]>;

// 编译器自动生成调用序列:
// 1. 将参数放入指定寄存器
// 2. 调用call指令
// 3. 从rax/rdx取返回值
// 4. 恢复callee-saved寄存器
```

---

## 13.6 本章小结

本章从工程实战角度解析了三个目标后端：

1. **通用架构**：ISelLowering/InstrInfo/RegisterInfo/FrameLowering/Subtarget的模板，Subtarget机制处理同一ISA不同微架构的差异。
2. **X86后端**：CISC的编译器工程挑战——63898行的ISelLowering、AVX/SSE/AVX-512的向量化路径、X86特有Pass。
3. **AArch64后端**：RISC的简化效应——固定指令长度、简单的调用约定、SVE可伸缩向量支持。
4. **RISC-V后端**：模块化ISA的组合式后端——Feature bits启用/禁用扩展、V向量扩展的配置管理。
5. **调用约定**：三大ABI的对比和TableGen描述，CallingConv.td自动生成调用序列。

下一章进入第四篇——MLIR，多层IR的编译新范式。
