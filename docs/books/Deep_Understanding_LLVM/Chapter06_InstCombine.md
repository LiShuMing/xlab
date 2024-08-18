# 第6章 InstCombine：系统化的窥孔优化工程

## 6.1 Worklist驱动架构

### 6.1.1 InstructionCombining.cpp主循环

**源码**：`llvm/lib/Transforms/InstCombine/InstructionCombining.cpp`（6351行）

InstCombine是LLVM中代码量最大的单功能优化Pass，总计36179行，分布在8个文件中。它采用worklist驱动架构，反复对指令应用代数化简规则直到收敛：

```c++
// 核心循环(简化版):
bool InstCombinerImpl::run(Function &F) {
  while (Worklist !empty()) {
    Instruction *I = Worklist.pop_back_val();
    if (I->isSafeToRemove()) continue;  // 已被删除

    // 对当前指令尝试所有化简规则
    if (Instruction *NewI = tryCombineInstruction(I)) {
      // 化简成功:
      // 1. 将新指令的操作数加入Worklist(可能产生新的化简机会)
      addUsersToWorklist(*NewI);
      // 2. 删除旧指令
      replaceInstUsesWith(*I, *NewI);
      // 3. 将被替换的指令的操作数也加入Worklist
      addUsersToWorklist(*I);
    }
  }
}
```

**Worklist管理策略**：

```
初始Worklist: 函数中所有指令的逆序(后定义先处理)
迭代:
  1. 弹出一条指令
  2. 尝试化简
  3. 如果成功, 将受影响的指令加入Worklist
  4. 重复直到Worklist为空

终止保证:
  - 每次化简严格减小指令的"复杂度"(操作数数量或嵌套深度)
  - 复杂度有下界, 所以必然终止
```

### 6.1.2 Visitor模式与分发

InstCombine使用C++的visitor模式为每类指令分发到对应的化简函数：

```c++
// 分发逻辑:
Instruction *tryCombineInstruction(Instruction &I) {
  switch (I.getOpcode()) {
  case Instruction::Add:
  case Instruction::Sub:   return visitAddSub(I);    // AddSub.cpp
  case Instruction::Mul:
  case Instruction::SDiv:
  case Instruction::UDiv:
  case Instruction::SRem:
  case Instruction::URem:  return visitMulDivRem(I); // MulDivRem.cpp
  case Instruction::And:
  case Instruction::Or:
  case Instruction::Xor:   return visitAndOrXor(I);  // AndOrXor.cpp
  case Instruction::Shl:
  case Instruction::LShr:
  case Instruction::AShr:  return visitShifts(I);    // Shifts.cpp
  case Instruction::Trunc:
  case Instruction::ZExt:
  case Instruction::SExt:  return visitCast(I);      // Casts.cpp
  case Instruction::ICmp:  return visitICmp(I);      // Compares.cpp
  case Instruction::FCmp:  return visitFCmp(I);
  case Instruction::PHI:   return visitPHI(I);
  case Instruction::Select:return visitSelect(I);
  // ...
  }
}
```

---

## 6.2 代数简化规则全景

### 6.2.1 AddSub规则

**源码**：`InstCombineAddSub.cpp`（3370行）

```
规则示例:

; 恒等变换
x + 0 → x
x - 0 → x
x - x → 0

; 结合律/交换律
(x + C1) + C2 → x + (C1+C2)    ; 常量合并
(x + C1) - C2 → x + (C1-C2)

; 分配律驱动的化简
(x + y) - y → x
(x - y) + y → x

; 溢出语义
(add nsw x, C1) + C2 → (add nsw x, C1+C2)  ; 仅当C1+C2不溢出
```

### 6.2.2 AndOrXor规则

**源码**：`InstCombineAndOrXor.cpp`（5666行，最大的规则文件）

```
规则示例:

; 幂等律
x & x → x
x | x → x

; 常量折叠
x & -1 → x
x | 0 → x
x & 0 → 0
x | -1 → -1

; De Morgan律
~(x | y) → ~x & ~y
~(x & y) → ~x | ~y

; 位操作优化
(x & C1) | (x & C2) → x & (C1|C2)     ; 位掩码合并
(x | C1) & (x | C2) → x | (C1&C2)

; 与比较的交互
(x & 1) != 0 → (x & 1) == 1 → x <s 0 (如果x是i1)
(x & C) == C → (x | ~C) == -1 → popcount(x & C) == popcount(C)

; 最重要的一组: 从位操作推导比较
icmp eq (x & C), 0 → !ctpop(x & C)  ; 如果C只有1位设置
icmp eq (x & C), C → ctpop(x & C) == ctpop(C)
```

### 6.2.3 MulDivRem规则

**源码**：`InstCombineMulDivRem.cpp`（2586行）

```
规则示例:

; 恒等变换
x * 1 → x
x * 0 → 0
x * -1 → -x

; 2的幂次乘法 → 移位
x * 8 → x << 3

; 除法优化
x / 1 → x
x / x → 1 (x != 0)
0 / x → 0

; 2的幂次除法 → 移位(无符号)
x u/ 8 → x >> 3

; 除以常量 → 乘以magic number + 移位
; 这是最复杂的规则之一:
; x / 3 → mul(x, 0x55555556) >> 32  (i32, 无符号)
; 原理: 利用乘法逆元在有限域中的等价性
```

**体系结构锚点**："除以常量变乘法"规则之所以重要，是因为整数除法在x86上需要15-40个周期(idiv)，而乘法只需要3个周期(imul)。这个变换在现代CPU上带来5-10倍的性能提升。

### 6.2.4 Shifts规则

**源码**：`InstCombineShifts.cpp`（1853行）

```
规则示例:

; 移位量为0或超宽
x << 0 → x
x << 32 → 0 (i32)  ; 移位量>=位宽, 结果为0

; 移位的移位
(x << C1) << C2 → x << (C1+C2)  ; 仅当C1+C2 < 位宽
(x >> C1) >> C2 → x >> (C1+C2)

; 与位操作的交互
(x << C) >> C → x & (-1 >> C)    ; 逻辑右移, 掩码高位
(x << C) a>> C → x               ; 算术右移恢复符号位(当C <= 符号位位置)

; 乘法与移位的互换
x * (1 << C) → x << C
(x << C) + (x << (C+1)) → x * 3 << C  ; 乘法合并
```

---

## 6.3 类型cast优化：InstCombineCasts

**源码**：`InstCombineCasts.cpp`（3366行）

Cast指令的类型转换是冗余的高发区：

```
规则1: 消除冗余cast链
  (sext (zext x)) → (zext x)     ; zext已经零扩展, sext无额外效果
  (trunc (zext x)) → (zext x)    ; 如果源类型和目标类型相同
  (zext (trunc x)) → (and x, mask) ; 只保留低位

规则2: cast与运算的互换
  (sext (add x, y)) → (add (sext x), (sext y))
  ; 将sext推入运算内部, 可能暴露进一步的化简

规则3: 比较中的cast优化
  (icmp eq (zext x), 0) → (icmp eq x, 0)
  ; 零扩展不改变零值判断

规则4: bitcast的消除
  bitcast <4 x i32> %v to <2 x i64>  ; 如果后面立即bitcast回来
  → 直接使用原始向量
```

**数据库类比**：Cast优化类似于类型强转消除——如果SQL中将INT转为BIGINT再转回INT，优化器应该识别并消除这些冗余转换。

---

## 6.4 比较指令优化：InstCombineCompares

**源码**：`InstCombineCompares.cpp`（9238行，InstCombine最大的子文件）

比较指令是优化的富矿——它们连接了算术运算和控制流：

```
规则1: 范围推导
  (icmp ule x, C) where C = 2^n-1 → (icmp ult x, 2^n)
  ; 无符号比较可以利用2的幂次边界化简

规则2: 比较与位操作
  (icmp eq (x & C), C) → (icmp eq (x | ~C), -1)
  ; 检查特定位是否全部设置

规则3: 符号/零扩展后的比较
  (icmp slt (sext x), 0) → (icmp slt x, 0)
  ; 符号扩展后与0比较, 等价于原值与0比较

规则4: 比较与Select
  select (icmp eq x, 0), 0, y → select (icmp ne x, 0), y, 0
  ; 翻转条件和值, 可能暴露进一步的化简

规则5: 浮点比较
  (fcmp oeq x, x) → (fcmp ord x, x)  ; 有序等于自身 → 有序检查(NaN检测)
  (fcmp uno x, 0.0) → (fcmp uno x, x) ; 无序比较与0无关, 改为与自身比较
```

**最重要的一组规则——从算术推导比较结果**：

```
; 加法溢出检测
(icmp ult (add nsw x, y), x) → false   ; nsw保证不溢出, 永远为假
(icmp ugt (add nuw x, y), x) → (icmp ne y, 0)  ; nuw保证不溢出

; 乘法结果判断
(icmp eq (mul x, y), 0) → (icmp eq (x | y), 0)  ; 乘积为0 ↔ 至少一个为0
```

---

## 6.5 Demanded Bits分析

**源码**：`InstCombineSimplifyDemanded.cpp`（3749行）

Demanded Bits是InstCombine最强大的分析工具之一——它从指令的使用者反向传播"需要哪些位"的信息，将不需要的位计算消除：

```
核心概念:
  "demanded bits" = 使用者真正需要的位集合

  例如: %x = add i32 %a, %b
        %y = shr i32 %x, 16      ; 只使用%x的高16位
        → %x的add中, 低16位的结果不重要
        → 如果%a和%b的高16位可以独立计算, 可以简化

算法:
  1. 从每条指令的使用者出发, 收集该指令哪些位被"需求"
  2. 反向传播: 如果I的第k位不被需求, 尝试简化I
  3. 简化方式:
     - 将不被需求的操作数位清零
     - 将不被需求的操作替换为0
     - 消除只为不被需求位服务的计算

示例:
  %x = add i32 %a, %b
  %y = and i32 %x, 0xFF00        ; 只使用第8-15位
  → %x的add只需要第8-15位(和可能的进位)
  → 如果%a和%b的低8位都是0, add可以简化
```

---

## 6.6 工程启示：如何将规则引擎做得可扩展

### 6.6.1 InstCombine的架构教训

InstCombine的36000+行代码展示了一个大型规则引擎的工程挑战：

**优势**：
- 规则之间通过Worklist自动产生交互——一条规则化简后，新的匹配机会自然浮现
- 终止性由复杂度度量保证——每步化简严格减小复杂度
- 递归收敛——反复应用直到无新变化（不动点）

**问题**：
- 规则之间可能相互触发导致振荡——需要careful ordering
- 规则的优先级对结果影响巨大——但缺乏系统性的优先级设计
- 测试困难——规则的组合爆炸使得完整测试不可能
- 编译时间长——InstCombine是O2编译时间的主要贡献者之一

### 6.6.2 与数据库表达式简化的对比

| 维度 | InstCombine | 数据库表达式简化 |
|------|------------|---------------|
| 规则数量 | 数百条 | 数十条 |
| 交互方式 | Worklist自动传播 | 显式调用链 |
| 终止保证 | 复杂度递减 | 规则优先级 |
| 可扩展性 | 新增规则即可 | 需要插入调用点 |

**数据库类比**：数据库的表达式简化（如`1=1 → TRUE`, `x=x → TRUE`, `NOT(NOT(x)) → x`）与InstCombine面对的是同一类问题。InstCombine的Worklist模式可以启发数据库优化器：当一条规则触发后，自动重新评估受影响的表达式，而非依赖人工安排的规则调用顺序。

---

## 6.7 本章小结

本章深入了InstCombine的内部：

1. **Worklist驱动架构**——从后向前处理指令，化简后自动将受影响指令加入Worklist，实现规则间的隐式交互。
2. **四大类代数规则**——AddSub(3370行)、AndOrXor(5666行)、MulDivRem(2586行)、Shifts(1853行)覆盖了整数运算的核心化简。
3. **Cast和Compare优化**——类型转换的冗余消除和比较指令的范围推导。
4. **Demanded Bits**——从使用点反向传播位需求，消除不需要的位计算。
5. **工程启示**——大型规则引擎的架构挑战：振荡、优先级、编译时间。

下一章跨越函数边界——过程间优化(IPO)，理解内联、属性推断、去虚化等跨函数优化如何工作。
