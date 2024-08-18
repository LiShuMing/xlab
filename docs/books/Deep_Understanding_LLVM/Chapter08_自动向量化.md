# 第8章 自动向量化：从标量到SIMD

## 8.1 LoopVectorize：合法性分析

### 8.1.1 LoopAccessInfo：依赖距离与运行时检查

**源码**：`llvm/lib/Transforms/Vectorize/LoopVectorize.cpp`（9569行）

LoopVectorize是LLVM性能优化最重要的Pass——它将标量循环自动转换为SIMD向量指令，带来4-16倍的性能提升。

向量化的前提是合法性：**循环迭代之间不能有数据依赖**（或依赖距离 ≥ 向量宽度）：

```
合法向量化(无依赖):
  for (i=0; i<n; i++)
    A[i] = B[i] + C[i];     // 每次迭代写不同的A[i], 读不同的B[i]/C[i]

不合法向量化(循环携带依赖):
  for (i=1; i<n; i++)
    A[i] = A[i-1] + 1;      // A[i]依赖A[i-1] → 必须顺序执行

条件合法(需要运行时检查):
  for (i=0; i<n; i++)
    A[i] = B[i] + C[i];     // 如果A和B/C可能重叠 → 需要运行时检查
```

LoopAccessInfo分析内存访问的依赖关系：

```
依赖分析:
1. 收集循环内所有内存访问(load/store)
2. 对每对内存访问检查别名:
   - 如果肯定不别名 → 无依赖
   - 如果可能别名 → 计算依赖距离
   - 如果依赖距离 ≥ 向量宽度 → 安全(不同迭代访问不同元素)
3. 对于不确定的情况:
   - 生成运行时检查(runtime check)
   - 如果检查通过, 执行向量化版本
   - 如果检查失败, 执行标量版本
```

运行时检查的生成：

```llvm
; 运行时检查的伪代码:
; if (A_end <= B_start || B_end <= A_start)  // A和B不重叠
;   goto vectorized_loop;
; else
;   goto scalar_loop;

; 实际IR:
entry:
  %check = or i1 %no_alias1, %no_alias2
  br i1 %check, label %vector.ph, label %scalar.ph

vector.ph:
  ; 向量化循环体

scalar.ph:
  ; 标量循环体
```

### 8.1.2 向量化代价模型(TTI接口)

代价模型决定向量化是否有收益：

```
代价计算:
  标量代价 = 每次迭代的指令数 × 迭代次数
  向量代价 = 向量指令数 × 迭代次数/向量宽度 + 运行时检查代价 + 向量前后缀代价

  如果 向量代价 < 标量代价 → 向量化

TTI(TargetTransformInfo)提供的代价接口:
  getVectorInstrCost(Instruction, VectorType)  → 单条向量指令的代价
  getMemoryOpCost(Opcode, Type, Alignment)     → 向量load/store的代价
  getArithmeticInstrCost(Opcode, Type)         → 向量算术的代价
  getShuffleCost(ShuffleKind, Type)            → 向量重排的代价

X86上的典型代价:
  add <4 x i32> → 1 (一条vpaddd)
  load <4 x i32> → 1 (一条vmovdqa, 对齐时)
  shuffle <4 x i32> → 1-3 (取决于shuffle模式)
```

**体系结构锚点**：向量化代价模型必须匹配硬件的SIMD单元。Intel Skylake的AVX2有两条128-bit FMA单元，每周期可以执行2条`vfmadd <4 x float>`指令，峰值8 FLOP/cycle。如果代价模型不考虑这个，可能会选择次优的向量宽度。

---

## 8.2 VPlan：向量化的内部IR

### 8.2.1 VPlan构建 → 变换 → 执行管线

VPlan是LoopVectorize的内部表示，将向量化决策与IR变换分离：

```
VPlan管线:
  1. 构建VPlan:
     - 分析循环结构, 收集内存访问
     - 决定向量宽度(VF)和展开因子(UF)
     - 构建VPInstruction和VPBasicBlock

  2. 变换VPlan:
     - 插入掩码(mask)用于条件执行
     - 插入向量前后缀(prologue/epilogue)
     - 插入运行时检查

  3. 执行VPlan:
     - 将VPlan转换为LLVM IR
     - 生成向量化的循环 + 标量余数循环
```

VPlan的内部表示：

```
VPInstruction (向量化指令)
├── VPWidenRecipe    : 标量指令 → 对应的向量指令
├── VPReplicateRecipe: 标量指令保持标量(无法向量化)
├── VPWidenCastRecipe: 类型转换的向量化
├── VPWidenSelectRecipe: select的向量化
├── VPInterleaveRecipe: 交错访问模式
└── VPReductionRecipe: 归约操作的向量化

VPBasicBlock (向量化基本块)
  包含VPInstruction的有序列表

VPlan (向量化计划)
  包含VPBasicBlock的控制流图 + 向量宽度/展开因子
```

---

## 8.3 SLPVectorizer：超字级并行

### 8.3.1 种子收集与指令聚类算法

**源码**：`llvm/lib/Transforms/Vectorize/SLPVectorizer.cpp`（30061行！LLVM最大的向量化文件）

SLP(Superword-Level Parallelism)向量化与LoopVectorize互补——它在非循环代码中寻找可以并行的独立操作：

```
SLP适用场景:
  // 独立但同构的操作 → 合并为向量操作
  x0 = a0 + b0;
  x1 = a1 + b1;
  x2 = a2 + b2;
  x3 = a3 + b3;
  →
  vx = <a0,a1,a2,a3> + <b0,b1,b2,b3>

算法:
1. 种子收集:
   - 从store指令出发(连续内存写入是最常见的SLP机会)
   - 从连续的GEP出发
   - 从同构的二元运算出发

2. 指令聚类:
   - 从种子开始, 沿def-use链收集同构指令
   - 构建"指令树": root = store, children = add, grandchildren = load
   - 树中同一层的指令合并为向量操作

3. 代价评估:
   - 对每个聚类计算向量化前后的代价差
   - 只保留有正收益的聚类
```

```
Before SLP:                          After SLP:
  %a0 = load float, ptr %p0           %v_a = load <4 x float>, ptr %p0
  %a1 = load float, ptr %p0+4         %v_b = load <4 x float>, ptr %q0
  %a2 = load float, ptr %p0+8         %v_r = fadd <4 x float> %v_a, %v_b
  %a3 = load float, ptr %p0+12        store <4 x float> %v_r, ptr %r0
  %b0 = load float, ptr %q0
  ...
  %r0 = fadd float %a0, %b0
  ...
  store float %r0, ptr %out0
  store float %r1, ptr %out0+4
  store float %r2, ptr %out0+8
  store float %r3, ptr %out0+12
```

---

## 8.4 后向量化优化：VectorCombine

**源码**：`llvm/lib/Transforms/Vectorize/VectorCombine.cpp`（5980行）

VectorCombine在向量化后进一步优化向量指令：

```
优化1: 向量操作标量化
  ; 向量宽度为1的无意义向量 → 标量
  %v = insertelement <1 x i32> undef, i32 %x, i32 0
  %r = extractelement <1 x i32> %v, i32 0
  → %r = %x

优化2: 向量load合并
  %v1 = load <2 x float>, ptr %p
  %v2 = load <2 x float>, ptr %p+8
  → %v = load <4 x float>, ptr %p  ; 合并为更宽的load

优化3: shuffle简化
  shufflevector <4 x i32> %v, <4 x i32> undef, <4 x i32> <0,1,2,3>
  → %v  ; identity shuffle消除

优化4: 向量比较优化
  %cmp = fcmp oeq <4 x float> %a, %b
  %ext = sext <4 x i1> %cmp to <4 x i32>
  → %cmp = fcmp oeq <4 x float> %a, %b  ; 某些架构直接产生i32结果
```

---

## 8.5 可伸缩向量：SVE/RISC-V V的编译器支持

### 8.5.1 ScalableVectorType与vscale机制

ARM SVE和RISC-V V扩展引入了可伸缩向量——向量宽度在编译期未知，在运行时确定：

```llvm
; 固定向量: 编译期确定宽度
%v = add <4 x i32> %a, %b        ; 128-bit (假设SSE)

; 可伸缩向量: 运行时确定宽度
%v = add <vscale x 4 x i32> %a, %b  ; vscale*128-bit

; vscale的语义:
; SVE-128: vscale=1 → <4 x i32>  (128-bit)
; SVE-256: vscale=2 → <8 x i32>  (256-bit)
; SVE-512: vscale=4 → <16 x i32> (512-bit)
; RISC-V V-128: vscale=1
; RISC-V V-256: vscale=2
```

### 8.5.2 从体系结构视角看：为什么硬件走向可伸缩向量

固定向量宽度的问题：
1. **SSE→AVX→AVX-512的迁移痛苦**：每次向量宽度翻倍，软件需要重写
2. **功耗问题**：AVX-512的全宽操作功耗巨大，Intel不得不引入AVX-512 downclocking
3. **面积效率**：不同应用需要不同的向量宽度，固定宽度浪费硅片面积

可伸缩向量的解决思路：
1. **一次编译，多宽度运行**：同一段代码在不同宽度的硬件上都能执行
2. **软件不需要知道硬件宽度**：vscale在运行时获取
3. **硬件可以自由选择最优宽度**：根据功耗/面积约束

LLVM的可伸缩向量支持：
- `ScalableVectorType`：类型系统支持
- `vscale`内联函数：获取运行时向量宽度
- 向量化Pass自动选择可伸缩向量宽度(当目标支持时)
- AArch64后端生成SVE指令
- RISC-V后端生成V扩展指令

---

## 8.6 本章小结

本章解析了自动向量化的四个层次：

1. **LoopVectorize**：合法性分析(依赖距离、运行时检查)、代价模型(TTI)、VPlan内部表示。
2. **SLPVectorizer**：超字级并行——在非循环代码中寻找同构操作合并为向量，30061行的代码反映了其复杂性。
3. **VectorCombine**：向量化后的进一步优化——标量化、合并、shuffle简化。
4. **可伸缩向量**：SVE/RISC-V V的编译支持，vscale机制让一次编译适配多种向量宽度。

下一章进入编译器分析算法——DominatorTree、ScalarEvolution、AliasAnalysis、MemorySSA——这些是优化决策的算力引擎。
