# 第9章 关键分析算法：优化决策的算力引擎

## 9.1 DominatorTree：Lengauer-Tarjan与增量更新

### 9.1.1 半支配者与迭代支配者计算

**源码**：`llvm/include/llvm/Support/GenericDomTreeConstruction.h` + `llvm/lib/Analysis/DomTreeUpdater.cpp`

DominatorTree是编译器最基础的分析数据结构——它回答"基本块A是否支配基本块B"（从入口到B的所有路径是否都经过A）：

```
支配树示例:
entry
  ├── A (支配A和A的后代)
  │   ├── B
  │   │   └── D
  │   └── C
  │       ├── E
  │       └── F
  └── G

支配关系:
  entry支配所有块
  A支配B,C,D,E,F
  B支配D
  C支配E,F

立即支配者(idom):
  idom(A) = entry
  idom(B) = A
  idom(D) = B
  idom(C) = A
  idom(E) = C
```

LLVM使用Lengauer-Tarjan算法构建支配树，时间复杂度O(E·α(E,N))（近似线性）：

```
算法步骤:
1. DFS编号: 从entry深度优先遍历, 为每个节点分配DFS序号
2. 计算半支配者(sdom): sdom(n) = 从n沿DFS树向上, 能到达的DFS序号最小的节点
3. 计算立即支配者(idom):
   - 如果sdom(n) = sdom(sdom(n))，则idom(n) = sdom(n)
   - 否则idom(n) = idom(sdom(n))
```

### 9.1.2 增量更新：插入/删除边后的高效维护

DomTreeUpdater支持在IR变换后增量更新支配树，而非完全重建：

```
支持的操作:
  insertEdge(BB_from, BB_to)  : 添加一条CFG边
  deleteEdge(BB_from, BB_to)  : 删除一条CFG边
  applyUpdates(ArrayRef<Update>): 批量应用更新

增量更新算法:
  插入边: 可能扩展某些节点的支配者集合
  删除边: 可能缩小某些节点的支配者集合
  批量更新: 先收集所有变更, 一次性重新计算受影响的部分

性能:
  完全重建: O(N) (N = 基本块数)
  增量更新: 通常O(log N), 最坏O(N) (但实际中增量更新远快于重建)
```

**优化Pass大量使用支配树**：LICM(判断循环不变量是否支配退出)、JumpThreading(判断条件传播的合法性)、SimplifyCFG(判断块是否不可达)。

---

## 9.2 ScalarEvolution：循环变量的符号计算

### 9.2.1 SCEV表达式层次

**源码**：`llvm/lib/Analysis/ScalarEvolution.cpp`（16336行！LLVM最大的分析文件）

SCEV(Scalar Evolution)是LLVM最强大的循环分析工具——它能符号化地计算循环变量在每次迭代中的值：

```
SCEV表达式层次:

SCEV (抽象基类)
├── SCEVConstant      : 常量 → SCEV for 42
├── SCEVUnknown       : 不可分析的值 → SCEV for %x (来自循环外)
├── SCEVAddRecExpr    : 递归加法(核心!) → {start, +, step}<loop>
│     {0, +, 1}<loop>  → 第i次迭代值为i
│     {5, +, 3}<loop>  → 第i次迭代值为5+3i
│     {0, +, 1, +, 2}<loop>  → 第i次迭代值为i² (二阶递归)
│
├── SCEVAddExpr       : 加法 → SCEV for A + B
├── SCEVMulExpr       : 乘法 → SCEV for A * B
├── SCEVUDivExpr      : 无符号除法
├── SCEVZeroExtendExpr: 零扩展
├── SCEVSignExtendExpr: 符号扩展
├── SCEVTruncateExpr  : 截断
├── SCEVPtrToIntExpr  : 指针转整数
└── SCEVMinMaxExpr    : min/max → SCEV for umin(A, B)
```

### 9.2.2 闭式表达式构造：从指令到SCEV的推导链

```
源代码:
  for (int i = 0; i < n; i++)
    arr[i*3 + 2] = 0;

IR:
  %i = phi i32 [0, %entry], [%i.next, %loop]
  %mul = mul i32 %i, 3
  %add = add i32 %mul, 2
  %idx = sext i32 %add to i64
  %ptr = getelementptr i32, ptr %arr, i64 %idx
  store i32 0, ptr %ptr

SCEV推导:
  %i   → {0, +, 1}<loop>
  %mul → {0, +, 3}<loop>
  %add → {2, +, 3}<loop>
  %idx → {2, +, 3}<loop>  (sext后)
  %ptr → {arr+8, +, 12}<loop>  (字节偏移)

  闭式: 第i次迭代, 偏移 = arr + 8 + 12*i
```

**SCEV的关键性质——唯一化**：相同语义的SCEV表达式只有一个实例，指针比较即可判断等价。这使得SCEV的等价性检查是O(1)。

### 9.2.3 SCEV在LSR/LoopVectorize中的关键应用

**LSR中的应用**（第5.7.4节）：
```
SCEV提供循环变量的闭式表达式 → LSR据此选择最优的地址计算方案
原始: arr[i*3+2] 每次需要mul+add+sext+GEP
LSR后: 用一个指针p从&arr[2]开始，每次加3 → 只需add+GEP
```

**LoopVectorize中的应用**：
```
SCEV判断循环迭代次数 → 决定向量化是否安全
SCEV计算依赖距离 → 判断是否有循环携带依赖
SCEV推导运行时检查条件 → 生成别名检查代码
```

---

## 9.3 别名分析(AliasAnalysis)：多策略融合

### 9.3.1 多策略融合架构

**源码**：`llvm/lib/Analysis/AliasAnalysis.cpp`（978行）+ `llvm/lib/Analysis/BasicAliasAnalysis.cpp`（2079行）

别名分析回答"两个指针是否可能指向同一内存位置"——这是几乎所有内存相关优化的前提：

```
AAResults: 别名分析的统一接口
├── BasicAA       : 基于指针算术的分析(最常用, 最快)
│   - 同一alloca的不同偏移 → NoAlias
│   - 指针+常量偏移 vs 指针 → NoAlias (如果偏移足够大)
│
├── GlobalsAA     : 全局变量间的别名分析
│   - 不同的全局变量 → NoAlias
│
├── SCEVAA        : 基于SCEV的循环别名分析
│   - {base+0,+,4} vs {base+1,+,4} → NoAlias (偏移不同)
│
├── TBAA          : 基于类型的别名分析(Type-Based AA)
│   - int* vs float* → NoAlias (严格别名规则)
│   - 依赖前端生成的!tbaa元数据
│
├── ScopedNoAliasAA: 基于作用域的别名分析
│   - !noalias元数据指定的无别名作用域
│
└── CFL-Steens/CFL-Andersen : 基于CFL的别名分析
    - 更精确但更慢的分析(已逐步弃用)
```

### 9.3.2 AAResults::alias()的分发逻辑

```c++
// 简化的分发逻辑:
AliasResult AAResults::alias(const MemoryLocation &LocA,
                              const MemoryLocation &LocB) {
  // 按优先级查询各分析:
  for (auto &AA : AAs) {
    AliasResult Result = AA.alias(LocA, LocB);
    if (Result != MayAlias)  // 如果任何分析给出确定答案
      return Result;          // 立即返回
  }
  return MayAlias;  // 所有分析都不确定, 返回"可能别名"
}

// 结果类型:
// NoAlias   : 肯定不别名 → 最大优化空间
// MayAlias  : 可能别名   → 保守处理
// MustAlias : 肯定别名   → 可以合并访问
// PartialAlias: 部分重叠 → 少见但可能
```

**数据库类比**：别名分析 ≈ 数据依赖分析——判断两个操作是否访问同一数据。在数据库中，这决定了两个事务是否可以并行执行；在编译器中，这决定了两个内存操作是否可以重排。

---

## 9.4 MemorySSA：内存的SSA形式

### 9.4.1 MemoryDef / MemoryUse / MemoryPhi

**源码**：`llvm/lib/Analysis/MemorySSA.cpp`（2667行）

MemorySSA将内存操作建模为SSA形式，让内存依赖关系像值的def-use链一样显式：

```
原始IR:                           MemorySSA:
entry:                           entry:
  store i32 0, ptr %p              1 = MemoryDef(liveOnEntry)  ; store
  store i32 1, ptr %q              2 = MemoryDef(1)            ; store
  br i1 %c, label %A, label %B

A:                               A:
  %x = load i32, ptr %p            3 = MemoryUse(1)  ; 读1定义的值
  store i32 2, ptr %r              4 = MemoryDef(2)  ; 不影响%p/%q
  br label %JOIN

B:                               B:
  store i32 3, ptr %p              5 = MemoryDef(1)  ; 覆盖1
  br label %JOIN

JOIN:                            JOIN:
  %y = load i32, ptr %p            6 = MemoryPhi(A:4, B:5)  ; 汇合
  ret void                         7 = MemoryUse(6)  ; 读6定义的值
```

MemorySSA的三种节点：
- **MemoryDef**：定义(写入)内存，指向可能被覆盖的前一个定义
- **MemoryUse**：使用(读取)内存，指向被读取的定义
- **MemoryPhi**：控制流汇合处的内存状态合并

### 9.4.2 Walker优化查询：clobber查找算法

MemorySSA的核心查询是"这个load读到的最新clobber(写)是什么"：

```
Walker查找算法:
  从MemoryUse出发, 沿def链向上查找
  使用别名分析跳过不相关的MemoryDef

示例:
  7 = MemoryUse(6)  ; load ptr %p
  → Walker从6出发查找%p的clobber
  6 = MemoryPhi(A:4, B:5)
  → 4 = MemoryDef(2): store ptr %r, 不别名%p → 跳过
  → 5 = MemoryDef(1): store ptr %p, 别名%p → 找到!
  → 在B路径上, %p的最新clobber是5(store i32 3)
  → 在A路径上, 需要继续向上找, 最终是1(store i32 0)

优化: Walker缓存结果, 避免重复查找
```

### 9.4.3 MemorySSA在LICM/DSE中的使用

```
LICM: 使用MemorySSA判断循环内是否有写可能影响load
  %x = load i32, ptr %p   (在循环内)
  → 查询MemorySSA: 循环内是否有%p的clobber?
  → 如果没有 → 可以安全外提

DSE(Dead Store Elimination): 使用MemorySSA判断store是否被后续store覆盖
  store i32 0, ptr %p     (1 = MemoryDef)
  store i32 1, ptr %p     (2 = MemoryDef, 覆盖1)
  → MemorySSA显示1被2覆盖 → 删除1
```

---

## 9.5 代价模型：TargetTransformInfo / TargetLibraryInfo

### 9.5.1 TTI：连接优化器与后端的桥梁

**源码**：`llvm/lib/Analysis/TargetTransformInfo.cpp`（1621行）+ `llvm/lib/Target/X86/X86TargetTransformInfo.cpp`（7331行）

TTI是优化器查询目标架构特性的统一接口：

```c++
class TargetTransformInfo {
  // 指令代价查询
  InstructionCost getArithmeticInstrCost(Opcode, Type);
  InstructionCost getMemoryOpCost(Opcode, Type, Alignment);
  InstructionCost getVectorInstrCost(Opcode, Type, Index);

  // 向量化相关
  unsigned getRegisterBitWidth(bool Vector);  // 寄存器宽度
  unsigned getMaxInterleaveFactor(unsigned VF);  // 最大交错因子
  bool prefersVectorWidth(unsigned Width);  // 偏好的向量宽度

  // 微架构相关
  bool isLegalAddressingMode(Type, GlobalValue*, int, unsigned);
  bool isLegalMaskedStore(Type);  // AVX-512 mask store?
  bool hasBranchDivergence();  // GPU?

  // 缓存相关
  unsigned getCacheLineSize();
  unsigned getPrefetchDistance();
};
```

### 9.5.2 X86 TTI深度解析

X86的TTI实现(7331行)反映了X86微架构的复杂性：

```
X86代价模型的特殊考虑:

1. 向量化代价:
   SSE: <4 x i32> add → 1 cycle (128-bit)
   AVX: <8 x i32> add → 1 cycle (256-bit)
   AVX-512: <16 x i32> add → 1 cycle (512-bit)
   但: AVX-512可能导致降频(降频惩罚!)

2. 降频惩罚(AVX-512 downclocking):
   Skylake-X: 使用AVX-512 → CPU降频到1.4GHz
   代价模型必须考虑: 更宽的向量但更低的频率 → 是否有净收益?

3. 指令代价:
   idiv i32: 15-40 cycles (非常慢!)
   imul i32: 3 cycles
   vpermilps: 1 cycle (AVX shuffle)
   vgather: ~20 cycles (AVX-512 gather)

4. 地址模式:
   [base+index*scale+disp]: X86原生支持 → GEP代价低
   但RISC架构不支持 → 需要额外指令计算地址
```

**体系结构锚点**：X86 TTI的7331行代码几乎是一部"X86微架构对编译器的影响"的百科全书。每一条代价规则背后都有对应的微架构特性——例如AVX-512降频是因为512-bit执行单元功耗巨大，CPU必须降低频率以控制散热。

---

## 9.6 本章小结

本章解析了5组关键分析算法：

1. **DominatorTree**：Lengauer-Tarjan构建 + 增量更新，是控制流分析的基础。
2. **ScalarEvolution**：16336行的符号计算引擎，SCEVAddRecExpr的递归加法表达式是循环分析的核心工具。
3. **AliasAnalysis**：多策略融合——BasicAA/TBAA/SCEVAA各有所长，AAResults统一分派。
4. **MemorySSA**：内存的SSA形式，让内存依赖像值的def-use链一样显式，Walker优化查询。
5. **代价模型**：TTI连接优化器与后端，X86 TTI的7331行反映了微架构的复杂性。

下一章进入后端的核心——指令选择，从IR到机器指令的桥梁。
