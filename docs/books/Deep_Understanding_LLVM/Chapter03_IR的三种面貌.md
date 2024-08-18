# 第3章 IR的三种面貌：内存、文本与位码

## 3.1 内存表示：C++对象的拓扑

### 3.1.1 Value对象的内存布局

在运行时，LLVM IR以C++对象图的形式存在于内存中。理解这个图的拓扑结构，是理解LLVM性能特征和设计约束的基础。

```
                    ┌─────────────────────────────────────┐
                    │           Module                     │
                    │  Function* ───→ Function[]            │
                    │  GlobalVariable* ───→ GV[]           │
                    │  DataLayout                         │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │          Function                    │
                    │  Argument[] ──→ Argument : Value     │
                    │  BasicBlock[] ──→ BasicBlock[]       │
                    │  属性: readonly, norecurse...        │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │         BasicBlock                   │
                    │  Instruction[] (双向链表)             │
                    │  ┌──────┐ ┌──────┐ ┌──────┐        │
                    │  │ PHI  │→│ Add  │→│ Ret  │        │
                    │  └──┬───┘ └──┬───┘ └──────┘        │
                    └─────┼────────┼─────────────────────┘
                          │        │
                    Value/Use系统:
                    ┌─────▼────────▼─────────────────────┐
                    │  Value ←── Use ←── User(Instruction)│
                    │  UseList链表穿起所有使用者            │
                    │  OperandList数组持有所有操作数        │
                    └─────────────────────────────────────┘
```

**对象大小估算**（64位系统）：

| 对象 | 大小估算 | 说明 |
|------|---------|------|
| Value | 32字节 | VTable + SubclassID + Type* + UseList + Name |
| Use | 32字节 | Val + Next + Prev + Parent |
| Instruction(1操作数) | 56字节 | Value基类 + User基类 + 操作码 + 基本块指针 |
| BasicBlock | 48字节 | Value基类 + 指令链表头尾 |
| Function | 120+字节 | GlobalValue基类 + 参数列表 + 基本块列表 + 属性 |

**关键源码文件**：

| 文件 | 行数 | 职责 |
|------|------|------|
| `llvm/lib/IR/Value.cpp` | 1,342 | Value核心：replaceAllUsesWith, dump |
| `llvm/lib/IR/Instruction.cpp` | 1,444 | Instruction：eraseFromParent, moveBefore |
| `llvm/lib/IR/Function.cpp` | 1,250 | Function：删除基本块、参数管理 |
| `llvm/lib/IR/Type.cpp` | 1,151 | Type工厂方法与唯一化 |

### 3.1.2 内存中的IR遍历模式

LLVM提供了丰富的迭代器接口，让遍历IR的各个层次变得简洁：

```c++
// 遍历模块中的所有函数
for (Function &F : M) { ... }

// 遍历函数中的所有基本块
for (BasicBlock &BB : F) { ... }

// 遍历基本块中的所有指令
for (Instruction &I : BB) { ... }

// 遍历指令的所有操作数
for (Value *Op : I.operands()) { ... }

// 遍历值的所有使用者
for (User *U : Val.users()) { ... }

// 深度优先遍历函数的控制流图
for (dom_iterator DI = df_begin(&F.getEntryBlock()); DI != df_end(); ) { ... }
```

这些遍历接口的设计遵循STL迭代器规范，使得C++标准库算法可以直接应用于IR。

---

## 3.2 文本表示(.ll)：人类可读的汇编

### 3.2.1 AsmWriter：IR的序列化逻辑

`AsmWriter`(定义在`llvm/lib/IR/AsmWriter.cpp`, 5533行)负责将内存中的IR对象图序列化为人类可读的.ll格式。核心流程：

```
Module::print()
  → AsmWriter::printModule()
    → 打印目标三元组和DataLayout
    → 打印全局变量和别名
    → 打印函数定义
      → AsmWriter::printFunction()
        → 打印函数头(define + 属性 + 类型)
        → 打印基本块
          → 打印标签(非entry块)
          → 打印指令(逐条)
            → 打印操作码
            → 打印操作数
            → 打印元数据附件
    → 打印元数据定义
    → 打印命名值表
```

### 3.2.2 .ll语法完整手册

.ll文件的语法遵循固定的层次结构：

```llvm
; === 模块级 ===
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-f80:128-n8:16:32:64-S128"
target triple = "x86_64-unknown-linux-gnu"

; === 全局变量 ===
@g_count = dso_local global i32 0, align 4          ; 初始化
@.str = private unnamed_addr constant [13 x i8] c"hello world\0A\00"  ; 字符串常量
@extern_var = external global i32                     ; 外部声明

; === 函数声明 ===
declare i32 @printf(ptr, ...)                         ; 可变参数函数

; === 函数定义 ===
define dso_local i32 @add(i32 noundef %a, i32 noundef %b) #0 {
entry:
  %result = add nsw i32 %a, %b
  ret i32 %result
}

; === 类型定义 ===
%struct.Point = type { i32, i32 }

; === 属性组 ===
attributes #0 = { noinline optnone }

; === 元数据 ===
!llvm.module.flags = !{!0}
!0 = !{i32 1, !"wchar_size", i32 4}
```

**指令语法详览**：

```llvm
; 二元运算
%r = add nsw i32 %a, %b        ; 带No Signed Wrap标记
%r = add nuw i32 %a, %b        ; 带No Unsigned Wrap标记
%r = fadd fast float %a, %b    ; 带fast-math标志

; 内存操作
%p = alloca i32, align 4                    ; 栈分配
%v = load i32, ptr %p, align 4              ; 加载
store i32 %v, ptr %p, align 4               ; 存储
%e = getelementptr inbounds i32, ptr %arr, i64 %idx  ; 地址计算

; 控制流
br label %target                             ; 无条件跳转
br i1 %cond, label %true, label %false       ; 条件跳转
ret i32 %result                              ; 返回
switch i32 %val, label %default [i32 1, label %case1]

; 函数调用
%r = call i32 @func(i32 %arg)
%r = call fastcc i32 @func(i32 %arg)        ; fast calling convention
%r = tail call i32 @func(i32 %arg)           ; 尾调用
%r = musttail call i32 @func(i32 %arg)       ; 必须尾调用

; PHI节点
%val = phi i32 [ 0, %entry ], [ %new, %loop ]

; 比较与选择
%cmp = icmp eq i32 %a, %b                    ; 整数比较
%fcmp oeq float %a, %b                       ; 浮点比较(ordered eq)
%r = select i1 %cond, i32 %a, i32 %b         ; 条件选择

; 向量操作
%e = extractelement <4 x i32> %vec, i32 %idx
%v = insertelement <4 x i32> %vec, i32 %val, i32 %idx
%s = shufflevector <4 x i32> %v1, <4 x i32> %v2, <4 x i32> <i32 0, i32 4, i32 2, i32 6>

; 类型转换
%ext = sext i32 %val to i64                  ; 符号扩展
%trunc = trunc i64 %val to i32               ; 截断
%bc = bitcast <4 x i32> %vec to <2 x i64>    ; 位重解释
%asc = addrspacecast ptr %p to ptr addrspace(1)  ; 地址空间转换

; 原子操作
%old = atomicrmw add ptr %p, i32 %val seq_cst          ; 原子读-改-写
%cmp = cmpxchg ptr %p, i32 %expected, i32 %new seq_cst seq_cst  ; 原子比较交换
fence acquire                                          ; 内存屏障
```

### 3.2.3 GEP指令的深入理解

GEP(GetElementPtr)是LLVM最独特也最常被误解的指令。它**只做地址计算，不访问内存**：

```llvm
; 结构体字段地址计算
%struct = alloca %struct.Point
%y_ptr = getelementptr inbounds %struct.Point, ptr %struct, i32 0, i32 1
;          索引0: 结构体本身(只有1个)  索引1: 第二个字段(y)
; 结果: %struct + offsetof(Point, y)

; 数组元素地址计算
%elem = getelementptr inbounds i32, ptr %arr, i64 %idx
; 结果: %arr + %idx * sizeof(i32)

; 多维数组
%elem = getelementptr inbounds [10 x [20 x i32]], ptr %mat, i64 %i, i64 %j
; 结果: %mat + (%i * 20 + %j) * sizeof(i32)

; GEP的类型规则:
; - 第一个索引: 指针解引用(从指针变为所指类型)
; - 后续索引: 沿类型结构导航(数组下标或结构体字段)
; - 每一步索引都会根据类型自动计算字节偏移
```

**为什么GEP是一条独立指令？** 因为将地址计算与内存访问分离，使得优化器可以对地址进行代数变换而不必担心内存语义。例如：

```llvm
; 优化前:
%p1 = getelementptr i32, ptr %base, i64 4
%p2 = getelementptr i32, ptr %base, i64 4
%v1 = load i32, ptr %p1
%v2 = load i32, ptr %p2

; 优化后(GEP CSE):
%p1 = getelementptr i32, ptr %base, i64 4
%v1 = load i32, ptr %p1
%v2 = load i32, ptr %p1    ; 复用%p1
```

如果地址计算与加载是一条指令，这种CSE优化就无法进行——因为加载有副作用，不能随意消除。

---

## 3.3 位码表示(.bc)：紧凑的二进制格式

### 3.3.1 位码格式设计

位码(.bc)是LLVM IR的紧凑二进制序列化格式，定义在`llvm/Bitcode/`目录中：

| 文件 | 行数 | 职责 |
|------|------|------|
| `llvm/lib/Bitcode/Writer/BitcodeWriter.cpp` | 5,967 | IR→位码编码 |
| `llvm/lib/Bitcode/Reader/BitcodeReader.cpp` | 8,981 | 位码→IR解码 |

位码格式的核心设计决策：

1. **位级编码**：不按字节对齐，每个字段使用最小位数。例如操作码Add只需6位(69条指令<64不够，<128够用)
2. **变长整数**：使用VBR(Variable Bit Rate)编码，小数值用更少的位
3. **Abbreviation机制**：允许定义缩写规则，为高频出现的记录定义更紧凑的编码
4. **块嵌套**：支持MODULE/BLOCK/FUNCTION等嵌套块结构
5. **向前兼容**：新版本可以添加新字段，旧版本可以跳过不认识的字段

```
位码文件结构:
┌──────────────────────────────┐
│ Magic Number: 'BC' + 0xC0DE  │  4字节
├──────────────────────────────┤
│ MODULE Block                  │
│ ├── IDENTIFICATION Block     │  版本信息
│ ├── BLOCK Block              │  函数/全局变量
│ │   ├── TYPE Block           │  类型表
│ │   ├── VSTOFFSET Record     │  值符号表偏移
│ │   ├── GLOBALVAR Records    │  全局变量
│ │   ├── FUNCTION Records     │  函数声明
│ │   └── ...                  │
│ ├── FUNCTION Block           │  函数体
│ │   ├── CONSTANTS Block      │  常量表
│ │   ├── FUNCTION Block       │  指令编码
│ │   └── VALUE_SYMTAB Block   │  值名称表
│ ├── METADATA Block           │  元数据
│ └── STRTAB Block             │  字符串表
└──────────────────────────────┘
```

### 3.3.2 位码与版本兼容性

LLVM位码格式有版本号，通常每个LLVM大版本更新一次。关键原则：

- **同一主版本内**：位码向后兼容，LLVM 17.x可以读取17.0生成的位码
- **跨主版本**：不保证兼容，LLVM 18可能无法读取LLVM 16的位码
- **LTO场景**：因为位码兼容性限制，不同版本的LLVM编译的.o文件可能无法链接

这就是为什么`clang -flto`要求所有编译单元使用相同版本的LLVM。

---

## 3.4 实战工具链

### 3.4.1 opt：IR优化器的100种用法

`opt`是LLVM最强大的IR操作工具，本质上是Pass Manager的命令行入口：

```bash
# 运行完整优化流水线
opt -S -O2 input.ll -o output.ll

# 运行指定Pass
opt -S -passes=sroa input.ll -o output.ll

# 运行多个Pass(按顺序)
opt -S -passes='sroa,instcombine,simplifycfg' input.ll -o output.ll

# 运行分析Pass并打印结果
opt -passes='print<domtree>' input.ll -disable-output 2>domtree.txt
opt -passes='print<loops>' input.ll -disable-output 2>loops.txt
opt -passes='print<scalar-evolution>' input.ll -disable-output 2>scev.txt

# 查看Pass执行效果
opt -S -O2 -print-after-all input.ll 2>pipeline.txt
opt -S -O2 -print-before=licm -print-after=licm input.ll

# 调试特定Pass(需要assertion构建)
opt -S -O2 -debug-only=licm input.ll 2>licm_debug.txt

# 统计信息
opt -S -O2 -stats input.ll 2>&1 | grep -E "^[0-9]+"

# 验证IR合法性(每个Pass后自动验证)
opt -S -O2 -verify-each input.ll
```

**New Pass Manager的`-passes=`语法**：

```
-passes='pass1,pass2,pass3'            # 顺序执行
-passes='pass1(pass2,pass3)'           # pass1内部嵌套pass2,pass3
-passes='repeat<3>(pass1,pass2)'       # 重复3次
-passes='cgscc(inline)'               # CGSCC层内联
-passes='function(loop(licm))'         # Function层中的Loop层LICM
-passes='module(sroa,function(instcombine))'  # 混合层次
```

### 3.4.2 llc：后端代码生成

```bash
# 生成汇编
llc input.ll -o output.s

# 指定目标架构
llc -march=x86-64 input.ll -o x86.s
llc -march=aarch64 input.ll -o arm.s
llc -march=riscv64 input.ll -o riscv.s
llc -march=nvptx64 input.ll -o ptx.s  # GPU!

# 指定CPU微架构(影响调度模型和指令选择)
llc -mcpu=skylake input.ll -o x86.s
llc -mcpu=cortex-a78 input.ll -o arm.s

# 指定属性
llc -mattr=+avx2 input.ll -o x86_avx2.s
llc -mattr=+sve input.ll -o arm_sve.s
llc -mattr=+v input.ll -o riscv_v.s

# 后端调试
llc -debug-only=isel input.ll 2>isel.txt       # 指令选择
llc -debug-only=regalloc input.ll 2>regalloc.txt  # 寄存器分配
llc -print-after-all input.ll 2>backend.txt     # 所有后端Pass
```

### 3.4.3 llvm-dis / llvm-as：格式互转

```bash
# .bc → .ll (反序列化位码为文本)
llvm-dis input.bc -o output.ll
llvm-dis input.bc   # 自动生成input.ll

# .ll → .bc (序列化文本为位码)
llvm-as input.ll -o output.bc

# 查看位码信息
llvm-bcanalyzer input.bc    # 分析位码结构
```

### 3.4.4 -print-after-all / -debug-only：Pass级可观测性

这是LLVM最强大的调试功能，让我们逐Pass观察IR变换：

**-print-after-all**：在每个Pass执行后打印完整的IR快照

```bash
opt -S -O2 -print-after-all input.ll 2>pipeline.txt
# pipeline.txt 内容示例:
# *** IR Dump After SROAPass ***
# define i32 @foo(...) { ... }
#
# *** IR Dump After InstCombinePass ***
# define i32 @foo(...) { ... }  (看到SROA效果后的进一步化简)
```

**-debug-only**：打印特定Pass的内部调试信息（需要LLVM以`-DLLVM_ENABLE_ASSERTIONS=ON`构建）

```bash
opt -S -O2 -debug-only=licm input.ll 2>licm_debug.txt
# licm_debug.txt 内容示例:
# LICM: Hoisting: %val = load i32, ptr %p
# LICM: Loop invariant: %val is defined outside the loop
# LICM: Safety check: no writes to %p inside the loop
```

**-stats**：打印Pass执行统计

```bash
opt -S -O2 -stats input.ll 2>&1
# 输出:
# ===-------------------------------------------------------------------------===
#                          ... Statistics Collected ...
# ===-------------------------------------------------------------------------===
# 3 instcombine  - Number of insts combined
# 2 licm         - Number of instructions hoisted
# 5 sroa         - Number of allocas promoted
# 1 gvn          - Number of loads eliminated
```

### 3.4.5 一个完整的调试工作流

假设我们想理解LICM对某个循环做了什么：

```bash
# 步骤1: 生成O0 IR
clang -S -emit-llvm -O0 loop.c -o loop_O0.ll

# 步骤2: 先运行SROA提升alloca
opt -S -passes=sroa loop_O0.ll -o loop_sroa.ll

# 步骤3: 单独运行LICM并观察效果
opt -S -passes=licm loop_sroa.ll -o loop_licm.ll
diff loop_sroa.ll loop_licm.ll

# 步骤4: 获取LICM的详细调试信息
opt -S -passes=licm -debug-only=licm loop_sroa.ll 2>licm_debug.txt

# 步骤5: 对比完整O2效果
opt -S -O2 loop_O0.ll -o loop_O2.ll
diff loop_licm.ll loop_O2.ll  # 看LICM之外还有哪些变换
```

---

## 3.5 本章小结

本章展示了LLVM IR的三种物理面貌：

1. **内存表示**：以Value/User/Use为核心的对象图，通过迭代器提供高效的遍历接口，是优化器直接操作的形态。

2. **文本表示(.ll)**：人类可读的汇编格式，由AsmWriter序列化，涵盖完整的指令语法——从二元运算到原子操作，从PHI节点到GEP地址计算。

3. **位码表示(.bc)**：位级编码的紧凑二进制格式，由BitcodeWriter/Reader处理，使用VBR和Abbreviation实现高压缩率，但有版本兼容性限制。

4. **工具链**是连接三种表示的桥梁：`opt`操作IR、`llc`生成机器码、`llvm-dis/llvm-as`互转格式、`-print-after-all/-debug-only`提供Pass级可观测性。

下一章我们进入LLVM优化器的核心框架——Pass基础设施，理解优化是如何被编排和执行的。
