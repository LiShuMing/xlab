# 第5章 标量优化：逐指令的变换艺术

## 5.1 死代码消除三兄弟：DCE / ADCE / BDCE

### 5.1.1 DCE：平凡死代码消除

**源码**：`llvm/lib/Transforms/Scalar/DCE.cpp`（147行）

DCE是最简单的死代码消除——删除没有副作用的死指令（没有use的指令）：

```c++
// 核心算法(极简):
bool DCE::runOnFunction(Function &F) {
  SmallVector<Instruction*> DeadInsts;
  for (Instruction &I : instructions(F))
    if (I.isSafeToRemove() && I.use_empty())
      DeadInsts.push_back(&I);

  while (!DeadInsts.empty()) {
    Instruction *I = DeadInsts.pop_back_val();
    for (auto &Op : I->operands())
      if (auto *OpI = dyn_cast<Instruction>(Op))
        if (OpI->use_empty() && OpI->isSafeToRemove())
          DeadInsts.push_back(OpI);
    I->eraseFromParent();
  }
}
```

**局限**：只能消除"没有使用者"的指令，不能消除"使用者也是死代码"的传递性死代码。

### 5.1.2 ADCE：激进死代码消除

**源码**：`llvm/lib/Transforms/Scalar/ADCE.cpp`（648行）

ADCE从控制流图出发，标记所有"活的"指令，然后删除所有"死的"指令：

```
算法:
1. 标记所有有副作用(store, call, terminate等)的指令为"活"
2. 反向传播: 如果指令的操作数是"活"的, 则标记该操作数为"活"
3. 删除所有未被标记为"活"的指令

Before ADCE:                  After ADCE:
  %x = add i32 %a, %b          (deleted)
  %y = mul i32 %x, 2           (deleted)
  store i32 %a, ptr %p         store i32 %a, ptr %p
  ret void                      ret void
```

**数据库类比**：DCE像删除"没有引用的临时表"，ADCE像基于数据血缘(lineage)的传递性删除——从最终输出反向追踪，只保留有贡献的节点。

### 5.1.3 BDCE：位追踪死代码消除

**源码**：`llvm/lib/Transforms/Scalar/BDCE.cpp`（210行）

BDCE在ADCE基础上增加了位级精度——追踪每个值的哪些位是"活的"：

```
Before BDCE:                         After BDCE:
  %x = add i32 %a, %b                  (deleted — %x的高位无人使用)
  %y = shl i32 %x, 16                  (deleted)
  %z = and i32 %y, 0xFFFF0000          (deleted)
  %w = lshr i32 %z, 16                 %w = and i32 %a, 0xFFFF  ; 直接取低16位
  ret i32 %w                            ret i32 %w
```

BDCE通过Demanded Bits分析（参见6.5节）从使用点反向传播"需要的位"，将不需要的位对应的计算消除。

---

## 5.2 公共子表达式消除：EarlyCSE / GVN / NewGVN

### 5.2.1 EarlyCSE：简单值编号的快速路径

**源码**：`llvm/lib/Transforms/Scalar/EarlyCSE.cpp`（1948行）

EarlyCSE对每个基本块内的指令做简单的值编号——如果两条指令的操作码、操作数和标志完全相同，则第二条可以使用第一条的结果：

```
Before EarlyCSE:                      After EarlyCSE:
  %a = load i32, ptr %p                %a = load i32, ptr %p
  %b = add i32 %a, 1                   %b = add i32 %a, 1
  %c = load i32, ptr %p                ; eliminated → use %a
  %d = add i32 %c, 1                   ; eliminated → use %b
```

**关键设计**：
- **不做跨块分析**：只在本块内消除冗余，速度快
- **处理内存操作**：使用MemorySSA判断两个load是否可能读到不同值
- **处理常量折叠**：`add i32 1, 2`直接折叠为`3`

### 5.2.2 GVN：全局值编号 + 部分冗余消除(PRE)

**源码**：`llvm/lib/Transforms/Scalar/GVN.cpp`（3398行）

GVN比EarlyCSE强大得多——它跨越基本块消除冗余计算，并做部分冗余消除(Partial Redundancy Elimination)：

```
GVN的核心概念——值编号(Value Number):
  相同值编号的指令计算相同的值
  编号规则: hash(Opcode + 操作数值编号 + 标志)

Before GVN:                          After GVN:
entry:                               entry:
  %a = load i32, ptr %p                %a = load i32, ptr %p
  br i1 %cond, label %A, label %B      br i1 %cond, label %A, label %B
A:                                   A:
  %b = load i32, ptr %p  ; 冗余!       ; eliminated → 使用%a (通过PHI)
  br label %JOIN                        br label %JOIN
B:                                   B:
  %c = load i32, ptr %p  ; 冗余!       ; eliminated → 使用%a
  br label %JOIN                        br label %JOIN
JOIN:                                JOIN:
  %r = phi i32 [%b, %A], [%c, %B]      %r = phi i32 [%a, %A], [%a, %B]
                                        ; → 简化为直接使用%a
```

**PRE(Partial Redundancy Elimination)**：将部分冗余（在某些路径上冗余但不是所有路径）变为完全冗余：

```
Before PRE:                          After PRE:
entry:                               entry:
  %a = add i32 %x, %y                 %a = add i32 %x, %y
  br i1 %cond, label %A, label %B      br i1 %cond, label %A, label %B
A:                                   A:
  br label %JOIN                        br label %JOIN
B:                                   B:
  %b = add i32 %x, %y  ; 冗余(但A路径没有)   ; eliminated → 使用%a (插入PHI)
  br label %JOIN                        br label %JOIN
JOIN:                                JOIN:
                                      %r = phi i32 [%a, %A], [%a, %B]
```

**数据库类比**：值编号 ≈ hash distinct——相同输入的子查询只需执行一次。PRE ≈ 谓词下推——将计算移到最早需要的位置，避免在不需要的路径上执行。

### 5.2.3 NewGVN：另一种算法实现

**源码**：`llvm/lib/Transforms/Scalar/NewGVN.cpp`（4292行）

NewGVN是对GVN算法的重写，使用不同的值编号策略：
- 基于SSA的值编号而非传统RPO遍历
- 更好地处理内存操作和PHI节点
- 更精确的冗余检测

目前NewGVN尚未替代GVN作为默认Pass，但代表了GVN算法的演进方向。

---

## 5.3 循环不变量外提(LICM)

### 5.3.1 不变性判定

**源码**：`llvm/lib/Transforms/Scalar/LICM.cpp`（3072行）

LICM将循环内的不变计算移到循环外：

```
不变性判定条件(全部满足):
1. 指令的定义点在循环外(操作数在循环外定义)   ← def-use链判定
2. 指令没有副作用(pure计算)                   ← isSafeToSpeculativelyExecute
3. 指令支配循环的所有退出点(保证外提后仍会执行) ← DominatorTree判定
4. 对于内存操作: 循环内没有可能别名的写         ← AliasAnalysis + MemorySSA判定
```

```
Before LICM:                          After LICM:
for.body:                            entry:
  %x = load i32, ptr %p  ; %p不被修改    %x = load i32, ptr %p  ; 外提!
  %y = mul i32 %x, 4     ; %x不变       %y = mul i32 %x, 4     ; 外提!
  store i32 %y, ptr %q   ; 循环内store   br label %for.body
  br label %for.body
                                      for.body:
                                        store i32 %y, ptr %q  ; 直接使用外提值
                                        br label %for.body
```

### 5.3.2 安全性检查：别名、异常、循环副作用

LICM的安全检查是编译器安全性保障的典型例子：

```c++
// 源码追踪: LICM.cpp canHoistOrSinkInst()

bool canHoistOrSinkInst(Instruction &I) {
  // 1. 检查指令是否可以安全执行(无异常/无副作用)
  if (!isSafeToSpeculativelyExecute(&I))
    return false;

  // 2. 检查操作数是否在循环外定义
  for (Value *Op : I.operands())
    if (Instruction *OpI = dyn_cast<Instruction>(Op))
      if (Loop->contains(OpI))
        return false;  // 操作数在循环内定义

  // 3. 对于load: 检查循环内是否有写可能别名
  if (auto *LI = dyn_cast<LoadInst>(&I)) {
    if (!Loop->isLoopInvariant(LI->getPointerOperand()))
      return false;
    // 使用AliasAnalysis检查循环内的store
    // 使用MemorySSA加速查询
  }
}
```

**体系结构锚点**：LICM外提load的最直接收益是**减少缓存压力**——循环内重复的load会导致缓存行被反复访问，外提后只访问一次。对于L1缓存4周期延迟、主存100+周期的现代CPU，这可能带来10-100倍的性能差异。

---

## 5.4 聚合体标量替换(SROA)

### 5.4.1 Alloca切片分析：partition算法

**源码**：`llvm/lib/Transforms/Scalar/SROA.cpp`（6148行）

SROA是LLVM最重要的优化之一——它将栈上的聚合体(alloca)拆分为标量，消除所有的内存操作：

```
Before SROA:                          After SROA:
entry:                               entry:
  %s = alloca {i32, float}             ; alloca被消除
  %f1 = getelementptr {i32, float},     ; GEP被消除
        ptr %s, i32 0, i32 0
  store i32 42, ptr %f1                %field0 = i32 42      ; 直接用SSA值
  %f2 = getelementptr {i32, float},     ; GEP被消除
        ptr %s, i32 0, i32 1
  store float 3.14, ptr %f2            %field1 = float 3.14  ; 直接用SSA值
  %l1 = load i32, ptr %f1              ; eliminated → 直接用%field0
  %l2 = load float, ptr %f2            ; eliminated → 直接用%field1
  ret i32 %l1                           ret i32 %field0
```

**核心算法——Alloca切片(Partition)**：

```
对每个alloca:
1. 收集所有使用该alloca的指令(load/store/memcpy/GEP)
2. 根据访问的偏移和大小, 将alloca分割为不重叠的"切片"
3. 每个切片变成一个独立的SSA值
4. 消除原alloca和相关的内存操作

示例: alloca [10 x i32], 被以下方式访问:
  store i32 %a, ptr %p+0   → 切片0: [0, 4) → i32
  store i32 %b, ptr %p+4   → 切片1: [4, 8) → i32
  load i64, ptr %p+0       → 切片2: [0, 8) → i64 (跨越切片0和1!)
  memcpy %p+8, %src, 32    → 切片3: [8, 40) → [8 x i32]

当切片有重叠时, SROA会尝试拆分或合并切片, 无法处理的情况保留alloca
```

### 5.4.2 promoteMemToReg：Briggs-Cooper算法

当SROA成功将alloca的每个切片简化为单一类型后，`promoteMemToReg`将剩余的简单alloca提升为SSA寄存器：

```
算法(基于Briggs-Cooper的迭代支配者算法):
1. 对每个简单alloca:
   - 收集所有store和load
   - 在支配者树的前驱节点插入PHI
   - 用PHI和SSA值替换所有load
   - 删除所有store和alloca
```

**数据库类比**：SROA ≈ 消除临时表——将中间结果直接流水线传递，避免写入磁盘再读回。这是查询优化和编译器优化最直接的对应。

---

## 5.5 稀疏条件常量传播(SCCP)

### 5.5.1 ValueLatticeElement格结构与状态转移

**源码**：`llvm/lib/Transforms/Scalar/SCCP.cpp`（140行主文件）+ `llvm/lib/Analysis/SparsePropagation.h`

SCCP使用格(Lattice)来跟踪每个值的可能状态：

```
ValueLatticeElement格:

              ⊤ (unknown/overdefined — 可能是任何值)
             / | \
    constant  constant  ...
    (i32 42)  (i32 0)   (具体的常量值)
             \ | /
              ⊥ (undefined — 尚未计算/不可达)

状态转移规则:
  ⊥ + 任何输入 → ⊥        (还没计算出来)
  ⊤ + 任何输入 → ⊤        (已经overdefined, 不再精确)
  constant + constant → constant (如果能计算) 或 ⊤ (如果不确定)

  关键: ⊥ → constant → ⊤ 是单向的(格的单调性)
        一旦变成⊤就不可能回到constant
```

### 5.5.2 SparseSolver工作表算法

```
SCCP算法:
1. 初始化: 所有值为⊥, 函数参数为⊤
2. 工作表: 加入入口基本块
3. 循环直到工作表为空:
   a. 取出一个基本块
   b. 对每条指令:
      - 根据操作数的格值计算结果的格值
      - 如果结果格值变化(↑), 将使用该结果的所有指令加入工作表
   c. 对条件分支:
      - 如果条件是constant(true/false), 只将可达的后继加入工作表
      - 如果条件是⊤, 将所有后继加入工作表
4. 优化:
   - 格值为constant的值 → 替换为常量
   - 不可达的基本块 → 删除
```

**SCCP的威力**——条件常量传播：

```
Before SCCP:                           After SCCP:
define i32 @test(i1 %cond) {           define i32 @test(i1 %cond) {
  br i1 %cond, label %A, label %B       br i1 %cond, label %A, label %B
A:                                     A:
  %x = add i32 1, 2      ; → 3           ret i32 3           ; 常量折叠
  ret i32 %x
B:                                     B:
  %y = add i32 10, 20     ; → 30         ret i32 30          ; 常量折叠
  ret i32 %y
}

; 如果%cond已知为true:
define i32 @test() {                   define i32 @test() {
  br i1 true, label %A, label %B         ret i32 3           ; 死代码B被消除!
A:
  ret i32 3
B:                                       ; B块被删除(不可达)
  ret i32 30
}
```

---

## 5.6 CFG化简：SimplifyCFG / JumpThreading / CorrelatedValuePropagation

### 5.6.1 SimplifyCFG

**源码**：`llvm/lib/Transforms/Utils/SimplifyCFG.cpp`（8993行）

SimplifyCFG是一组CFG变换规则的集合：

```
规则1: 合并只有一个前驱的基本块
  BB1 → BB2 (BB2只有BB1一个前驱) → 合并为一个块

规则2: 删除不可达基本块
  没有前驱且不是入口块 → 删除

规则3: 消除空基本块
  BB1: br label %BB2 (BB1只有一条br) → 将BB1的前驱直接指向BB2

规则4: Switch优化
  switch i32 1, label %default [i32 1, label %A] → br label %A

规则5: 三角分支消除
  br i1 %c, label %A, label %B    →   select i1 %c, %a, %b
  A: %r = phi [%a, %entry]            (如果%a和%b是简单值)
  B: %r = phi [%b, %entry]
```

### 5.6.2 JumpThreading：条件传播驱动的路径复制

**源码**：`llvm/lib/Transforms/Scalar/JumpThreading.cpp`（3259行）

JumpThreading通过复制基本块来简化控制流：

```
Before JumpThreading:                  After JumpThreading:
entry:                                entry:
  %cmp = icmp eq i32 %x, 0             %cmp = icmp eq i32 %x, 0
  br i1 %cmp, label %A, label %B       br i1 %cmp, label %A, label %B_copy
A:                                    A:
  store i32 1, ptr %p                  store i32 1, ptr %p
  br label %JOIN                       br label %JOIN
B:                                    B_copy:  ; 复制, 已知%cmp=false
  store i32 0, ptr %p                  store i32 0, ptr %p
  %cmp2 = icmp eq i32 %x, 0           ; → 已知false, 可以消除
  br i1 %cmp2, label %C, label %JOIN   br label %JOIN  ; 直接跳到JOIN
```

**数据库类比**：JumpThreading ≈ 谓词下推——将已知的过滤条件推到更早的位置，减少后续需要处理的路径。

### 5.6.3 CorrelatedValuePropagation

与JumpThreading配合使用，通过LazyValueInfo分析已知值的范围和等式关系，传播条件信息消除冗余比较。

---

## 5.7 循环优化族：Rotation / Unroll / IndVarSimplify / LSR

### 5.7.1 LoopRotation：guard + latch旋转

**源码**：`llvm/lib/Transforms/Scalar/LoopRotation.cpp`（107行主文件，核心在Utils/LoopRotationUtils.cpp）

LoopRotation将while循环转换为do-while + guard形式：

```
Before Rotation:                       After Rotation:
entry:                                entry:
  br label %loop                        %guard = icmp slt i32 0, %n
loop:                                   br i1 %guard, label %loop, label %exit
  %i = phi i32 [0, %entry],           loop:
            [%i.next, %loop]             %i = phi i32 [0, %guard],
  %cond = icmp slt i32 %i, %n                        [%i.next, %loop]
  br i1 %cond, label %loop, label %exit  ...循环体...
  %i.next = add i32 %i, 1               %i.next = add i32 %i, 1
                                         %cond = icmp slt i32 %i.next, %n
                                         br i1 %cond, label %loop, label %exit
                                       exit:
```

**收益**：保证循环体至少执行一次才检查条件，为后续的LoopUnroll和LICM创造更好的条件——循环内的代码可以安全地假设第一次迭代已经发生。

### 5.7.2 LoopUnroll：代价模型与展开因子选择

**源码**：`llvm/lib/Transforms/Scalar/LoopUnrollPass.cpp`（1800行）

LoopUnroll复制循环体多次，减少循环控制开销和增加指令级并行：

```
Before Unroll(2):                      After Unroll(2):
for (int i = 0; i < n; i++)           for (int i = 0; i < n; i += 2) {
  sum += arr[i];                         sum += arr[i];
                                         sum += arr[i+1];
                                       }
; 或者完全展开(n已知且小):
for (int i = 0; i < 4; i++)           sum += arr[0];
  sum += arr[i];                       sum += arr[1];
                                       sum += arr[2];
                                       sum += arr[3];
```

**展开因子选择**的代价模型：
1. 循环体大小 × 展开因子 ≤ 阈值(默认O2: 150条指令)
2. 展开后是否有新的优化机会(如向量化)
3. PGO信息：热循环展开更激进
4. 寄存器压力：展开后寄存器溢出则不值得

### 5.7.3 IndVarSimplify：归纳变量规范化

**源码**：`llvm/lib/Transforms/Scalar/IndVarSimplify.cpp`（2237行）

IndVarSimplify将循环的归纳变量规范化为最简形式：

```
Before:                              After:
for (int i = 0; i < n; i++)          for (long iv = 0; iv < (long)n; iv++) {
  sum += arr[i * 4 + base];            sum += arr[iv * 4 + base];  // 更宽的类型
                                      }
; 或进一步: SCEV推导出arr[i*4+base]是线性递增
for (long iv = 0; iv < (long)n; iv++)
  sum += *ptr++;   // GEP变成简单的指针递增
```

### 5.7.4 LSR(Loop Strength Reduction)：SCEV驱动的地址计算优化

**源码**：`llvm/lib/Transforms/Scalar/LoopStrengthReduce.cpp`（7163行！LLVM最大的标量优化Pass）

LSR是LLVM最复杂的标量优化之一，利用SCEV分析将昂贵的地址计算替换为廉价的递增操作：

```
Before LSR:                          After LSR:
for (long i = 0; i < n; i++) {       for (long i = 0; i < n; i++) {
  int val = arr[i*3 + 2];              int val = *p;      ; 简单load
  sum += val;                           sum += val;
}                                       p += 3;           ; 简单加法, 替代乘法
                                      }
; 其中 p 初始化为 &arr[2], 每次迭代加3

; 原始: 每次迭代计算 i*3+2 (乘法+加法+GEP)
; 优化后: 每次迭代只做 p+=3 (一次加法) + 简单load
```

LSR的决策极其复杂，需要考虑：
- 寄存器压力（每种公式方案需要多少个IV）
- 代码大小（不同退出路径的最终值计算）
- 目标架构的寻址模式（X86支持[base+index*scale+disp]，ARM只支持[base+offset]）

**体系结构锚点**：LSR的存在正是因为CPU的地址计算单元支持特定的寻址模式。X86的复杂寻址模式让LSR在某些情况下保留乘法（因为CPU可以一条指令完成），而RISC架构则倾向于消除乘法。

---

## 5.8 本章小结

本章解析了7组标量优化Pass：

1. **DCE/ADCE/BDCE**：从平凡到位追踪的三级死代码消除，精度递增
2. **EarlyCSE/GVN/NewGVN**：从块内到全局的公共子表达式消除，GVN的PRE是跨路径优化的经典
3. **LICM**：循环不变量外提，别名分析和支配树是安全性的保障
4. **SROA**：聚合体标量替换，是O0 IR到O2 IR最关键的变换，消除alloca + load/store
5. **SCCP**：基于格的稀疏条件常量传播，能同时做常量折叠和死代码消除
6. **SimplifyCFG/JumpThreading**：CFG化简和路径复制，简化控制流
7. **循环优化族**：Rotation/Unroll/IndVar/LSR，从循环结构优化到地址计算强度削减

下一章聚焦InstCombine——LLVM最大的窥孔优化引擎，36000+行的规则系统。
