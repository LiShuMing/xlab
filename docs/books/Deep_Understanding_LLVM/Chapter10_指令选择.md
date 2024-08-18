# 第10章 指令选择：从IR到机器指令的桥梁

## 10.1 SelectionDAG：DAG-based指令选择

### 10.1.1 SDNode / SDValue / ISD opcodes层次体系

SelectionDAG是LLVM后端的核心数据结构——它将LLVM IR转换为有向无环图(DAG)，然后在DAG上进行合法化、优化和指令选择：

```
SDNode: DAG的节点(表示一个操作)
  - Opcode: ISD::ADD, ISD::LOAD, ISD::BRCOND...
  - Operands: SDValue列表(输入边)
  - Values: 多个输出值(SDValue)

SDValue: DAG的边(指向SDNode的某个输出)
  - SDNode*: 目标节点
  - unsigned ResNo: 输出编号(多输出节点的第几个结果)

ISD opcodes (与LLVM IR操作码不同!):
  ISD::ADD    → 整数加法(目标无关)
  ISD::LOAD   → 内存加载
  ISD::STORE  → 内存存储
  ISD::BRCOND → 条件分支
  ISD::TokenFactor → 多个副作用的汇合点
  ... + 目标特定opcodes (X86ISD::CMOV, AArch64ISD::CSEL...)
```

### 10.1.2 SelectionDAGBuilder.cpp：IR→DAG构建

**源码**：`llvm/lib/CodeGen/SelectionDAG/SelectionDAGBuilder.cpp`（13083行）

SelectionDAGBuilder逐条遍历IR指令，为每条指令创建对应的SDNode：

```
构建过程:
  IR: add i32 %a, %b
  → DAG: (add:i32 SDValue(%a), SDValue(%b))

  IR: load i32, ptr %p
  → DAG: (load:i32 (EntryToken), SDValue(%p))

  IR: br i1 %cond, label %true, label %false
  → DAG: (brcond (SDValue(%cond)), BasicBlockSDNode(%true))
         (br BasicBlockSDNode(%false))

  IR: ret i32 %val
  → DAG: (ret SDValue(%val))
```

**关键设计——TokenFactor和内存序**：
DAG中的内存操作通过Token链保持顺序——load/store按序排列，优化器不能跨越Token链重排内存操作（除非别名分析证明安全）。

### 10.1.3 Legalize → Combine → Select 三阶段

```
IR → DAG构建 → 合法化 → 组合优化 → 指令选择 → MachineInstr

阶段1: 合法化(Legalize)
  源码: LegalizeDAG.cpp (6571行) + LegalizeTypes.cpp (1053行)
  将目标不支持的操作/类型转为支持的形式:
  - 类型合法化: i64 → 2×i32 (32位目标)
  - 操作合法化: i32 rotl → (shl + shr + or) (如果不支持旋转)
  - 合法化动作: Legal/Promote/Expand/Custom/LibCall

阶段2: DAG组合优化(DAGCombiner)
  源码: DAGCombiner.cpp (31296行! LLVM最大单文件)
  对DAG进行窥孔优化——类似InstCombine但在DAG层面:
  - (add x, 0) → x
  - (mul x, 1) → x
  - (load (add base, offset)) → 目标特定的寻址模式
  - (sext (sext x)) → (sext x)
  - 更复杂的: (add (mul a, b), c) → fma (如果目标支持)

阶段3: 指令选择(Instruction Selection)
  源码: 各目标的*ISelDAGToDAG.cpp
  将DAG模式匹配为目标指令:
  - TableGen生成的模式匹配表
  - 回溯搜索匹配最优模式
  - 未匹配的DAG节点用默认规则处理
```

### 10.1.4 DAGCombiner：LLVM最大文件的窥孔优化

31296行的DAGCombiner是后端的"InstCombine"——它在DAG层面做大量优化：

```
关键优化:

1. 寻址模式优化:
   (add base, (shl idx, 2)) → 目标寻址模式[base + idx*4]
   X86: 可以用一条lea指令完成

2. FMA形成:
   (fadd (fmul a, b), c) → (fma a, b c)
   如果目标支持FMA(如Haswell的vfmadd)

3. 向量操作优化:
   (build_vector x, x, x, x) → (splat_vector x)
   (vector_shuffle v, v, mask) → 简化shuffle

4. 内存操作合并:
   (load i32 ptr+0) + (load i32 ptr+4) → (load i64 ptr)
   (store i32 val, ptr+0) + (store i32 val2, ptr+4) → (store i64, ptr)
```

---

## 10.2 GlobalISel：新一代指令选择框架

### 10.2.1 四阶段流水线

GlobalISel是LLVM的新一代指令选择框架，采用与SelectionDAG不同的方法：

```
SelectionDAG: IR → DAG → Legalize → Combine → Select → MachineInstr
GlobalISel:   IR → G_MIR → Legalize → RegBank → Select → MachineInstr

阶段1: IRTranslator (源码: 4417行)
  LLVM IR → 通用机器IR(G_MIR)
  使用G_*通用操作码:
    G_ADD, G_SUB, G_MUL  → 通用算术
    G_LOAD, G_STORE      → 通用内存操作
    G_ICMP, G_FCMP       → 通用比较
    G_BR, G_COND_BR      → 通用控制流
    G_GEP                → 通用地址计算

阶段2: Legalizer (源码: 391行)
  将不合法的G_*操作转为合法的G_*操作
  合法化动作: Legal/Lower/FewerElements/MoreElements/Custom

阶段3: RegBankSelect (源码: 1120行)
  为G_MIR操作数选择寄存器组(GPR/FPR/VR)
  代价驱动的选择:
    G_FADD → FPR(浮点寄存器组)
    G_ADD  → GPR(通用寄存器组)

阶段4: InstructionSelect (源码: 385行)
  G_MIR → 目标特定的MachineInstr
  使用TableGen生成的选择表
```

### 10.2.2 G_*通用操作码设计哲学

```
G_* vs ISD opcodes:
  ISD: 目标无关但有隐含类型约束(如ISD::ADD要求整数)
  G_*: 完全目标无关, 类型通过操作数传递

  G_ADD %0:i32, %1:i32    → 32位加法
  G_ADD %0:i64, %1:i64    → 64位加法
  G_ADD %0:v4i32, %1:v4i32 → 向量加法
  (同一条G_ADD, 不同类型 → 不同目标指令)

优势:
  - 统一表示: 所有类型用同一个操作码
  - 简化合法化: 只需处理类型差异
  - 更好的可测试性: 可以在G_MIR层面独立测试
```

### 10.2.3 GISel vs SelectionDAG对比

| 维度 | SelectionDAG | GlobalISel |
|------|-------------|------------|
| 内存开销 | 高(每个操作创建SDNode) | 低(直接操作MachineInstr) |
| 编译速度 | 慢(DAG构建+销毁) | 快(直接翻译) |
| 优化能力 | 强(DAGCombiner 31K行) | 弱(CombinerHelper较小) |
| 代码质量 | 高(成熟) | 中(AArch64已追平,O0默认用GISel) |
| 可调试性 | 差(DAG难以可视化) | 好(G_MIR可打印) |
| 当前状态 | 默认(大多数目标) | AArch64 O0默认,其他目标部分 |

---

## 10.3 TableGen：指令描述的DSL

### 10.3.1 .td文件语法

TableGen是LLVM的元编程系统——用声明式DSL描述指令、寄存器、调度模型，自动生成C++代码：

```
// 指令定义示例 (X86)
let Constraints = "$src1 = $dst" in
def ADD32rr : I<0x01, MRMDestReg, (outs GR32:$dst), (ins GR32:$src1, GR32:$src2),
                "add{l}\t{$src2, $dst|$dst, $src2}",
                [(set GR32:$dst, (add GR32:$src1, GR32:$src2))]>;

// 解读:
// I<0x01, ...>           → 操作码0x01
// (outs GR32:$dst)       → 输出: 32位通用寄存器
// (ins GR32:$src1, GR32:$src2) → 输入: 两个32位通用寄存器
// "add{l}\t..."          → 汇编语法
// [(set GR32:$dst, ...)] → 模式匹配: (add i32:$src1, i32:$src2) → ADD32rr

// 寄存器定义
def RAX : X86Reg<"rax", 0>;
def RCX : X86Reg<"rcx", 1>;
def GR64 : RegisterClass<"X86", [i64], 64, (add RAX, RCX, RDX, RBX, ...)>;

// 调度模型
def : SchedWriteRes<[X86Port0, X86Port1]> { let Latency = 3; let NumMicroOps = 2; }
```

### 10.3.2 模式匹配与代码生成

TableGen最重要的功能是从模式匹配规则生成指令选择代码：

```
// 模式匹配规则
def : Pat<(add GR32:$src1, GR32:$src2), (ADD32rr GR32:$src1, GR32:$src2)>;
def : Pat<(add GR32:$src, i32immSExt8:$imm), (ADD32ri8 GR32:$src, $imm)>;

// 自动生成的匹配代码(简化版):
if (N->getOpcode() == ISD::ADD) {
  if (isType(N, MVT::i32)) {
    if (N->getOperand(1)->isConstant() && fitsInInt8(N->getOperand(1)))
      return SelectADD32ri8(N);  // 立即数加法
    else
      return SelectADD32rr(N);   // 寄存器加法
  }
}
```

**工程价值**：TableGen让后端工程师用声明式方式描述指令，而非手写C++选择代码。这大幅减少了后端的开发量——一个新后端可能只需要几千行.td文件，而非几万行C++代码。

---

## 10.4 本章小结

本章解析了指令选择的两种框架：

1. **SelectionDAG**：IR→DAG→Legalize→Combine→Select的三阶段流水线，DAGCombiner(31296行)是LLVM最大的单文件。
2. **GlobalISel**：IR→G_MIR→Legalize→RegBank→Select的四阶段流水线，G_*通用操作码简化了指令选择。
3. **TableGen**：声明式DSL描述指令/寄存器/模式，自动生成C++代码，大幅减少后端开发量。

下一章进入寄存器分配——从虚拟寄存器到物理寄存器的NP完全问题。
