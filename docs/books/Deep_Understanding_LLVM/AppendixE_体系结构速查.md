# 附录E 体系结构速查(面向编译器工程师)

## X86-64 / AArch64 / RISC-V 关键特性对比

| 特性 | X86-64 | AArch64 | RISC-V |
|------|--------|---------|--------|
| ISA类型 | CISC(变长1-15B) | RISC(固定4B) | RISC(固定4B, C扩展16B) |
| 通用寄存器 | 16 (rax-r15) | 31 (x0-x30) | 31 (x1-x31) |
| 浮点/向量寄存器 | 16/32 XMM/YMM/ZMM | 32 V(neon/sve) | 32 V(向量扩展) |
| 虚拟地址宽度 | 48/57位 | 48/52位 | 39/48/57位 |
| 大端/小端 | 小端 | 可配置(默认小端) | 小端 |
| 原子支持 | CMPXCHG16B | LDXR/STXR | LR/SC |
| 分支预测 | 复杂(2级TAGE) | 简单(2级) | 简单(BHT+BTB) |

## 缓存层次

| 层级 | Intel Skylake | AMD Zen3 | ARM Cortex-A78 |
|------|-------------|---------|---------------|
| L1 I-Cache | 32KB, 8路, 4周期 | 32KB, 8路, 4周期 | 64KB, 4路, 3周期 |
| L1 D-Cache | 32KB, 8路, 4周期 | 32KB, 8路, 4周期 | 64KB, 4路, 4周期 |
| L2 Cache | 1MB(每核), 12周期 | 512KB(每核), 12周期 | 256KB(每核), 9周期 |
| L3 Cache | 共享(~1.375MB/核) | 共享(32MB/CCX) | 共享(可配置) |
| 缓存行大小 | 64B | 64B | 64B |

## TLB

| 特性 | X86-64 | AArch64 | RISC-V |
|------|--------|---------|--------|
| L1 ITLB | 64项 | 48项 | 实现定义 |
| L1 DTLB | 64项 | 48项 | 实现定义 |
| L2 STLB | 1536项 | 1024项 | 实现定义 |
| 页大小 | 4KB/2MB/1GB | 4KB/16KB/64KB | 4KB/2MB/1GB |

## 分支预测器

| 特性 | Intel Skylake | AMD Zen3 | ARM Cortex-A78 |
|------|-------------|---------|---------------|
| 类型 | TAGE-SC-L | Perceptron | 2-level |
| 预测失误惩罚 | ~19周期 | ~19周期 | ~8周期 |
| BTB大小 | ~4K项 | ~4K项 | ~1K项 |
| RAS深度 | ~64 | ~32 | ~8 |

## 执行端口

### Intel Skylake-SP

```
Port 0: ALU, 向量ALU, 乘法, 除法
Port 1: ALU, 向量ALU, 乘法
Port 2: Load地址生成
Port 3: Load地址生成
Port 4: Store数据
Port 5: ALU, 向量shuffle
Port 6: ALU, 分支
Port 7: Store地址生成
```

### AMD Zen3

```
ALU0: ALU, 乘法, 分支
ALU1: ALU, 乘法
ALU2: ALU, 除法
AGU0: Load/Store地址
AGU1: Load/Store地址
AGU2: Load/Store地址
FP0: FPU, 向量
FP1: FPU, 向量
FP2: FPU, 向量
FP3: FPU, 向量
```

## SIMD指令集演进

### X86

```
SSE (1999):   128-bit, 4×f32, 2×f64
SSE2 (2001):  128-bit, 整数SIMD
SSE3 (2004):  水平加/减
SSSE3 (2006): 字节shuffle, 符号运算
SSE4.1 (2007): blend, dot product, rounding
SSE4.2 (2008): 字符串比较, CRC32
AVX (2011):   256-bit, 3操作数(VEX编码)
AVX2 (2013):  256-bit整数SIMD, gather
AVX-512F (2015): 512-bit, mask寄存器
AVX-512BW/DQ/VL: 字节/字/双字/可变宽度
AVX-512VNNI: INT8推理(bfloat16→int8)
AVX-512BF16: BF16推理(Hopper/SapphireRapids)

编译器标识:
  -mattr=+sse4.2,+avx,+avx2,+avx512f,+avx512bw,+avx512vnni,+avx512bf16
```

### ARM

```
NEON (2011):  128-bit, 4×f32, 2×f64 (AArch64标配)
SVE (2016):   可伸缩向量(128-2048bit), 谓词执行
SVE2 (2020):  SVE + 更多整数操作
SME (2022):   可伸缩矩阵扩展(外积引擎)

编译器标识:
  -mattr=+neon,+sve,+sve2,+sme
```

### RISC-V

```
V (2021): 可伸缩向量扩展(128-4096bit), vl控制
Zvfh: 半精度浮点向量
Zvk*: 向量密码学扩展

编译器标识:
  -mattr=+v,+zvfh
```

## 编译器对体系结构特性的利用

| 硬件特性 | 编译器利用 |
|---------|----------|
| SIMD寄存器 | LoopVectorize / SLPVectorizer |
| 乘法指令 | InstCombine: ×2^n → <<n |
| FMA单元 | DAGCombiner: (a×b)+c → fma |
| 复杂寻址模式 | X86ISelLowering: [base+idx*scale+disp] |
| 条件移动 | BranchProbability → cmov vs branch |
| 缓存行 | LoopDataPrefetch / 对齐 |
| 分支预测 | MachineBlockPlacement / 热路径fall-through |
| 执行端口 | SchedMachineModel / 端口压力调度 |
| 原子指令 | AtomicExpandPass / fence插入 |
| 量化单元 | VNNI/DP4A指令生成(INT8推理) |
