# 第12章 指令调度与代码发射

## 12.1 调度问题：流水线冒险与指令级并行

### 12.1.1 数据冒险 / 结构冒险 / 控制冒险

指令调度的目标是重排指令以最大化流水线利用率，避免三种冒险：

```
1. 数据冒险(Data Hazard):
   RAW (Read After Write):  add %r1, %r2 → sub %r3, %r1  ; 等待add结果
   WAW (Write After Write): 两个写同一寄存器 → 需要保持写顺序
   WAR (Write After Read):  现代CPU通常无此问题(寄存器重命名)

2. 结构冒险(Structural Hazard):
   两条指令需要同一执行端口 → 需要间隔
   例: 两条imul都需要Port 1 → 第二条等1个周期

3. 控制冒险(Control Hazard):
   分支预测失误 → 流水线刷新, 损失15-20个周期
   解决: 分支预测 + 条件移动 + 调度冷热代码
```

### 12.1.2 ScheduleDAG / ScheduleDAGInstrs / ScheduleDAGSDNodes

LLVM的调度器基于DAG表示——每个MachineInstr是DAG的节点，边表示依赖关系：

```
ScheduleDAG: 调度DAG的基类
  - SUnit (Scheduling Unit): DAG的节点
    - 对应一条MachineInstr
    - 有入边(Preds)和出边(Succs)
    - 每条边标记依赖类型(Data/Control/Order)

ScheduleDAGInstrs: MachineInstr层面的调度DAG
  - 在寄存器分配后构建
  - 依赖边来自: 寄存器def-use、内存依赖、隐式依赖

ScheduleDAGSDNodes: SelectionDAG层面的调度DAG
  - 在指令选择时构建
  - 用于Pre-RA调度
```

---

## 12.2 调度算法

### 12.2.1 List Scheduling

**源码**：`llvm/lib/CodeGen/MachineScheduler.cpp`（5021行）

List Scheduling是最常用的调度算法——贪心地选择就绪指令中优先级最高的：

```
算法:
  1. 构建调度DAG
  2. 初始化: 所有没有前驱的指令标记为"就绪"
  3. 循环直到所有指令被调度:
     a. 从就绪队列中选择优先级最高的指令
     b. 发射该指令(放入调度序列)
     c. 更新后继指令的就绪状态
     d. 新的就绪指令加入就绪队列

优先级启发式:
  - 关键路径长度(Critical Path): 最长路径的指令优先
  - 延迟(Latency): 高延迟指令优先(让它们尽早开始)
  - 资源使用: 平衡执行端口的负载
  - 寄存器压力: 压力高时优先释放寄存器的指令

LLVM的混合调度器:
  - Pre-RA调度: 减少关键路径长度, 降低寄存器压力
  - Post-RA调度: 消除流水线停顿, 优化执行端口利用
```

### 12.2.2 Modulo Scheduling(软件流水)

**源码**：`llvm/lib/CodeGen/MachinePipeliner.cpp`（4394行）

软件流水是循环优化的一种——将循环的不同迭代的指令交错排列：

```
原始循环(每次迭代3条指令, 有数据依赖):
  I0: load  %r1, [%ptr]      ; 3周期延迟
  I1: add   %r2, %r1, 1      ; 等待I0完成
  I2: store [%ptr], %r2       ; 等待I1完成

  每次迭代需要3个周期(串行)

软件流水后:
  ; prologue
  I0: load  %r1, [%ptr]       ; 迭代1的load
  ; kernel
  I0': load  %r1', [%ptr+4]   ; 迭代2的load
  I1:  add   %r2, %r1, 1      ; 迭代1的add (r1已就绪)
  I0'':load  %r1'', [%ptr+8]  ; 迭代3的load
  I1': add   %r2', %r1', 1    ; 迭代2的add
  I2:  store [%ptr], %r2      ; 迭代1的store
  ; epilogue
  I1'': add   %r2'', %r1'', 1
  I2':  store [%ptr+4], %r2'
  I2'': store [%ptr+8], %r2''

  kernel每周期发射1条指令 → 吞吐量3倍提升!
```

软件流水在DSP和VLIW架构上特别重要——这些架构有大量并行执行单元，软件流水可以充分利用它们。

---

## 12.3 机器模型(SchedMachineModel)

### 12.3.1 延迟/吞吐量/执行端口的TableGen描述

调度模型在.td文件中描述，TableGen生成C++代码：

```
// X86 Skylake调度模型(简化)
def SkylakeServerModel : SchedMachineModel {
  let IssueWidth = 6;        // 每周期发射6条指令
  let MicroOpBufferSize = 224; // 224项重排序缓冲区
  let LoadLatency = 4;        // L1缓存命中: 4周期
  let HighLatency = 20;       // 高延迟操作(如除法): 20周期
}

// 执行端口
def SKXPort0  : ProcResource<2>;  // ALU, 向量ALU
def SKXPort1  : ProcResource<2>;  // ALU, 向量ALU
def SKXPort5  : ProcResource<2>;  // 向量shuffle
def SKXPort6  : ProcResource<1>;  // 分支
def SKXPort23 : ProcResource<2>;  // load地址生成
def SKXPort4  : ProcResource<1>;  // store数据

// 指令调度信息
def : WriteRes<WriteALU, [SKXPort0, SKXPort1]> { let Latency = 1; }
def : WriteRes<WriteIMul, [SKXPort1]> { let Latency = 3; }
def : WriteRes<WriteDiv, [SKXPort0, SKXPort1]> { let Latency = 20; }
def : WriteRes<WriteVecALU, [SKXPort0, SKXPort1]> { let Latency = 4; }
```

### 12.3.2 从体系结构视角看：为什么调度模型要匹配微架构

调度模型必须与实际微架构匹配，否则调度结果可能是次优的：

```
Skylake端口分配:
  add rax, rbx  → Port 0 或 Port 1 (1周期)
  imul rax, rbx → Port 1 (3周期)
  div rax       → Port 0+1 (20+周期)
  jmp target    → Port 6 (1周期)

如果调度模型不准确:
  例: 模型认为add和imul可以用同一端口
  → 调度器可能连续发射两条imul
  → 但Skylake只有1个imul端口 → 第二条imul必须等待
  → 实际性能比模型预测差

  例: 模型认为load延迟是3周期(实际4周期)
  → 调度器在3周期后就发射依赖load的指令
  → 实际需要等待4周期 → 流水线停顿1周期
```

**体系结构锚点**：Intel从Nehalem到Sapphire Rapids的每代微架构都有不同的调度模型。LLVM的`llvm/lib/Target/X86/MCTargetDesc/X86Schedule*.td`文件覆盖了10+代X86微架构。这是编译器与硬件协同设计的典型——微架构改变，调度模型必须同步更新。

---

## 12.4 代码发射

### 12.4.1 MC层：MCAsmBackend / MCCodeEmitter / MCObjectWriter

```
MachineInstr → MC层 → 目标文件

流程:
  MachineInstr (后端的机器指令表示)
    │
    ▼ AsmPrinter (5364行)
  MCInst (MC层的机器指令, 更底层)
    │
    ├── MCCodeEmitter: MCInst → 二进制编码
    │   例: ADD32rr → 0x01 0xC8 (x86-64编码)
    │
    ├── MCAsmBackend: 处理fixup和重定位
    │   例: call @printf → 占位符, 链接时填充地址
    │
    └── MCObjectWriter: 写入目标文件(ELF/Mach-O/COFF)
        ELF: .text段(代码) + .data段(数据) + .symtab(符号表) + .rela(重定位)
```

### 12.4.2 AsmPrinter：MachineInstr → 汇编文本

AsmPrinter将MachineInstr转换为可读的汇编文本：

```
MachineInst:
  %rax = ADD64rr %rax, %rbx, implicit-def %eflags

汇编输出:
  addq %rbx, %rax

MachineInst:
  MOV64mr %stack.0, 1, %noreg, 0, %noreg, %rax

汇编输出:
  movq %rax, -8(%rsp)    ; 存入栈帧
```

### 12.4.3 ELF/Mach-O/WASM目标文件格式

```
ELF (Linux):
  .text     : 代码段
  .data     : 已初始化数据段
  .bss      : 未初始化数据段
  .rodata   : 只读数据段
  .symtab   : 符号表
  .strtab   : 字符串表
  .rela.text: 代码段重定位表
  .eh_frame : 异常处理信息(DWARF)

Mach-O (macOS):
  __TEXT    : 代码和只读数据
  __DATA    : 可写数据
  __LINKEDIT: 符号表和重定位

WASM (WebAssembly):
  Code section   : 函数体
  Memory section : 线性内存
  Table section  : 间接函数表
  Global section : 全局变量
```

---

## 12.5 本章小结

本章解析了指令调度和代码发射：

1. **调度问题**：三种冒险(数据/结构/控制)、调度DAG的构建、依赖边类型。
2. **调度算法**：List Scheduling(默认)、软件流水(循环优化)。
3. **机器模型**：TableGen描述延迟/吞吐量/端口，调度模型必须匹配微架构。
4. **代码发射**：MC层的编码/重定位/目标文件生成，AsmPrinter的MachineInstr→汇编转换。

下一章进入目标后端——X86/AArch64/RISC-V的具体适配，以及调用约定的实现。
