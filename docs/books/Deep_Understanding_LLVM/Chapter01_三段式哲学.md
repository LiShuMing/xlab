# 第1章 编译器的三段式哲学：从查询引擎到LLVM

## 1.1 三段式编译 vs 数据库查询处理：一个工程师的直觉映射

如果你曾深入数据库查询引擎的内部，理解优化器如何将一条SQL从逻辑计划变换为物理执行计划，那么你已经掌握了理解LLVM最核心的直觉——**三段式架构**。

### 1.1.1 两种系统的同构性

编译器和查询引擎看似属于不同领域，但其核心抽象惊人地相似：

```
┌─────────────────────────────────────────────────────────────────────┐
│                    编译器 Pipeline                                   │
│                                                                     │
│  源代码 → [前端] → LLVM IR → [优化器] → 优化后IR → [后端] → 机器码  │
│           Clang       ↑       Pass序列        ↑       CodeGen      │
│                    IR是枢纽              IR仍是枢纽                  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    查询引擎 Pipeline                                 │
│                                                                     │
│  SQL → [Parser] → 逻辑计划 → [优化器] → 物理计划 → [执行器] → 结果  │
│         Lexer/AST    ↑        Rule/Cost      ↑       Volcano/      │
│                      逻辑计划是枢纽      物理计划是枢纽  Vectorized  │
└─────────────────────────────────────────────────────────────────────┘
```

关键对应关系：

| 数据库概念 | 编译器概念 | 共同的本质 |
|-----------|-----------|-----------|
| SQL Parser → AST | Clang Lexer/Parser → AST | 语法分析，消除表面语法差异 |
| 逻辑查询计划(Logical Plan) | LLVM IR(未优化) | 与平台无关的中间表示 |
| 优化器规则(Rule) | 优化Pass | 等价变换，保持语义 |
| 代价模型(Cost Model) | TargetTransformInfo | 平台感知的决策依据 |
| 物理查询计划(Physical Plan) | MachineInstr | 平台相关的执行表示 |
| 执行引擎(Executor) | CPU/GPU硬件 | 实际执行计算 |

**最核心的同构在于中间表示**。正如逻辑计划将SQL的语法多样性统一为关系代数操作，LLVM IR将C/C++/Rust/Fortran等语言的语义多样性统一为类型化SSA指令。这种统一不是偶然——它是一种工程哲学：**在IR层面建立最大的优化空间**。

### 1.1.2 SSA与关系代数的深层联系

SSA(Static Single Assignment)是LLVM IR的基础约束：每个变量只被赋值一次。这条约束看似简单，却与关系代数有深层的同构性：

- **def-use chain ≈ 数据血缘(Lineage)**：在SSA中，每个值的定义和使用形成一条显式链，就像数据库中每行数据的溯源路径。`Value.h`中的`Use`链表精确记录了"谁消费了我"。

- **PHI节点 ≈ Union合并**：当控制流汇合时，PHI节点选择来自不同路径的值，类似于UNION将多个子查询结果合并。两者的本质都是：在汇合点消除歧义。

- **Pass不变量 ≈ 查询等价性**：每个优化Pass必须保证变换前后程序语义不变，正如每个查询改写规则必须保证结果集不变。`Verifier.cpp`(8425行)就是LLVM的"语义等价性守卫者"。

### 1.1.3 Pass Pipeline ≈ 优化器规则引擎

数据库优化器面临一个经典问题：规则的执行顺序影响结果质量。编译器同样如此——Pass的编排顺序直接决定了优化效果：

```
数据库优化器:                          LLVM优化器:
┌──────────────┐                    ┌──────────────────┐
│ Rule 1: 谓词下推 │                  │ Pass 1: SROA      │
│ Rule 2: 列裁剪   │                  │ Pass 2: EarlyCSE  │
│ Rule 3: Join重排 │                  │ Pass 3: LICM      │
│ Rule 4: 算子融合 │                  │ Pass 4: InstCombine│
│ ...            │                    │ ...              │
└──────────────┘                    └──────────────────┘
   顺序敏感! 顺序敏感!
```

LLVM通过`PassBuilderPipelines.cpp`(2507行)精确编排O0-Oz每个优化级别的Pass序列，这与Cascades/Volcano优化器通过规则优先级和搜索策略编排变换顺序是同一类问题。我们在第4章会深入解析这个编排逻辑。

---

## 1.2 LLVM项目全景：源码目录结构与组件关系

### 1.2.1 顶层项目一览

LLVM项目是一个庞大的monorepo，包含20+个子项目，各自承担编译工具链的不同角色：

```
llvm-project/
│
├── llvm/                  # LLVM核心——编译器基础设施
│   ├── lib/IR/           # IR核心实现(Value/Instruction/Function/Module)
│   ├── lib/Transforms/   # IR优化Pass(Scalar/IPO/Vectorize/InstCombine)
│   ├── lib/CodeGen/      # 后端代码生成(SelectionDAG/GlobalISel/RegAlloc/Sched)
│   ├── lib/Target/       # 30+架构后端(X86/AArch64/RISC-V/NVPTX/AMDGPU...)
│   ├── lib/MC/           # 机器码层(汇编/反汇编/目标文件)
│   ├── lib/Analysis/     # 分析Pass(AliasAnalysis/SCEV/MemorySSA/DominatorTree)
│   ├── lib/Passes/       # Pass管理器与流水线定义
│   ├── lib/LTO/          # 链接时优化
│   ├── lib/ExecutionEngine/  # JIT编译(ORC JIT)
│   ├── lib/ProfileData/  # PGO/MemProf/SampleProf
│   ├── lib/Bitcode/      # IR位码读写
│   ├── lib/Linker/       # IR链接器
│   └── tools/            # 命令行工具(opt/llc/lli/llvm-ar/llvm-mc...)
│
├── clang/                 # C/C++/Obj-C前端
│   ├── lib/Lex/          # 词法分析
│   ├── lib/Parse/        # 语法分析
│   ├── lib/Sema/         # 语义分析
│   ├── lib/AST/          # 抽象语法树
│   ├── lib/CodeGen/      # AST → LLVM IR生成(关键桥梁!)
│   ├── lib/Driver/       # 编译驱动(命令行→编译动作)
│   └── lib/Frontend/     # 前端基础设施
│
├── mlir/                  # 多层中间表示框架
│   ├── lib/IR/           # MLIR核心(Operation/Dialect/Region/Block)
│   ├── lib/Dialect/      # 40+方言(Arith/Func/Linalg/Affine/GPU/SPIRV...)
│   ├── lib/Conversion/   # 84个方言间转换Pass
│   ├── lib/Transforms/   # 通用变换(Canonicalize/CSE/Inliner/SCCP)
│   └── lib/Target/       # MLIR→LLVM/GPU/SPIRV目标
│
├── lld/                   # 链接器(ELF/Mach-O/COFF/WASM)
├── lldb/                  # 调试器
├── flang/                 # Fortran前端
├── compiler-rt/           # 运行时库( sanitizer / profiling / builtins)
├── libcxx/                # C++标准库实现
├── libcxxabi/             # C++ ABI库
├── libunwind/             # 异常处理与栈展开
├── openmp/                # OpenMP运行时
├── offload/               # OpenMP目标端offload运行时(GPU offload)
├── polly/                 # 多面体优化框架
├── bolt/                  # 二进制优化与链接时工具
├── libc/                  # LLVM实现的C标准库
└── pyproject.toml         # Python绑定配置
```

### 1.2.2 组件间的数据流

这些子项目并非孤立存在，它们通过LLVM IR和相关的数据格式紧密连接：

```
                          ┌─────────────┐
                          │  C/C++ 源码  │
                          │  Fortran    │
                          │  Rust/...   │
                          └──────┬──────┘
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
                    ▼            ▼            ▼
               ┌─────────┐ ┌─────────┐ ┌──────────┐
               │  Clang  │ │  Flang  │ │  Rustc   │
               │ (C/C++) │ │ (Fortran)│ │ (Rust)   │
               └────┬────┘ └────┬────┘ └────┬─────┘
                    │            │            │
                    └────────────┼────────────┘
                                 │
                          LLVM IR (.ll / .bc)
                          ★ 全局枢纽 ★
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
                    ▼            ▼            ▼
              ┌──────────┐ ┌──────────┐ ┌──────────────┐
              │   opt    │ │   llc    │ │  MLIR → LLVM │
              │ (优化器)  │ │ (后端)   │ │  (AI编译路径) │
              └────┬─────┘ └────┬─────┘ └──────┬───────┘
                   │            │               │
                   ▼            ▼               ▼
           优化后的IR     目标文件(.o)     目标文件(.o)
                   │            │               │
                   └────────────┼───────────────┘
                                │
                                ▼
                          ┌──────────┐
                          │   lld    │
                          │ (链接器)  │
                          └────┬─────┘
                               │
                               ▼
                          可执行文件 / 库
```

**LLVM IR是整个生态的通用语言**——就像数据库中的逻辑查询计划是优化器和执行器之间的契约。任何能产生LLVM IR的前端都可以利用LLVM的全部优化和代码生成能力；任何能消费LLVM IR的后端都可以支持任意前端语言。这就是三段式架构的威力：**解耦带来组合爆炸式的扩展能力**。

### 1.2.3 源码规模感知

在深入源码之前，先建立对代码规模的感觉——这有助于判断阅读的优先级：

| 组件 | 关键文件 | 代码行数 | 阅读优先级 |
|------|---------|---------|-----------|
| IR核心 | `llvm/lib/IR/` 全部 | ~18,000+ | 最高 |
| 指令定义 | `llvm/include/llvm/IR/Instruction.def` | 257 | 最高(必读!) |
| IR验证 | `llvm/lib/IR/Verifier.cpp` | 8,425 | 高 |
| Clang CodeGen | `clang/lib/CodeGen/CGExpr.cpp` | 7,427 | 中 |
| Clang CodeGen | `clang/lib/CodeGen/CGCall.cpp` | 6,503 | 中 |
| 优化流水线 | `llvm/lib/Passes/PassBuilderPipelines.cpp` | 2,507 | 高 |
| SelectionDAG构建 | `llvm/lib/CodeGen/SelectionDAG/SelectionDAGBuilder.cpp` | 13,083 | 中(第10章) |
| DAG组合器 | `llvm/lib/CodeGen/SelectionDAG/DAGCombiner.cpp` | 31,296 | 参考(最大!) |
| 汇编打印 | `llvm/lib/CodeGen/AsmPrinter/AsmPrinter.cpp` | 5,364 | 低 |
| X86 Lowering | `llvm/lib/Target/X86/X86ISelLowering.cpp` | 63,898 | 参考(第13章) |

**阅读策略**：先读`.def`文件(分类学)，再读`.h`文件(接口契约)，最后读`.cpp`文件(算法实现)。这就像数据库中先理解系统表(catalog)，再理解查询接口，最后深入执行引擎。

---

## 1.3 从一行C代码到可执行文件：完整编译流程追踪

理解LLVM最好的方式是追踪一个具体的程序从源码到机器码的完整旅程。我们选择一个经典的循环求和函数，逐步观察它在编译管线中的形态变化。

### 1.3.1 源码起点

```c
// sum_array.c
int sum_array(int* arr, int n) {
    int sum = 0;
    for (int i = 0; i < n; ++i) {
        sum += arr[i];
    }
    return sum;
}
```

### 1.3.2 阶段1：前端——C代码到LLVM IR

**源码入口**: `clang/lib/CodeGen/CodeGenFunction.cpp`

Clang前端的处理分为四个子阶段：

```
源码 ──→ 词法分析(Lex) ──→ Token流
  Token流 ──→ 语法分析(Parse) ──→ AST
  AST ──→ 语义分析(Sema) ──→ 类型检查后的AST
  AST ──→ 代码生成(CodeGen) ──→ LLVM IR
```

**关键源码文件**：

| 文件 | 行数 | 职责 |
|------|------|------|
| `clang/lib/Lex/Lexer.cpp` | 词法分析 | 字符流→Token |
| `clang/lib/Parse/Parser.cpp` | 语法分析 | Token→AST |
| `clang/lib/Sema/Sema.cpp` | 语义分析 | 类型检查/名称查找 |
| `clang/lib/CodeGen/CGExpr.cpp` | 7,427行 | 表达式→IR指令 |
| `clang/lib/CodeGen/CGStmt.cpp` | 3,414行 | 语句→IR基本块 |
| `clang/lib/CodeGen/CGCall.cpp` | 6,503行 | 函数调用→IR call指令+ABI |
| `clang/lib/CodeGen/CGClass.cpp` | C++类→IR | this指针/vtable |

CodeGen阶段是前端最关键的部分——它是AST到IR的翻译层，也是C++语义与LLVM IR语义之间的桥梁。例如，`arr[i]`在AST中是一个数组下标表达式，CGExpr会将其翻译为：

```llvm
%idxprom = sext i32 %i to i64           ; 符号扩展索引
%arrayidx = getelementptr inbounds i32, ptr %arr, i64 %idxprom  ; 计算地址
%val = load i32, ptr %arrayidx, align 4 ; 加载值
```

这三条IR指令精确对应了C语义：数组下标计算 → 地址计算 → 内存加载。

**O0下的LLVM IR**（`clang -S -emit-llvm -O0 sum_array.c`）：

```llvm
define i32 @sum_array(ptr %arr, i32 %n) {
entry:
  %sum = alloca i32, align 4          ; 栈上分配sum
  %i = alloca i32, align 4            ; 栈上分配i
  store i32 0, ptr %sum, align 4      ; sum = 0
  store i32 0, ptr %i, align 4        ; i = 0
  br label %for.cond

for.cond:
  %0 = load i32, ptr %i, align 4
  %cmp = icmp slt i32 %0, %n
  br i1 %cmp, label %for.body, label %for.end

for.body:
  %1 = load i32, ptr %i, align 4
  %idxprom = sext i32 %1 to i64
  %arrayidx = getelementptr inbounds i32, ptr %arr, i64 %idxprom
  %2 = load i32, ptr %arrayidx, align 4
  %3 = load i32, ptr %sum, align 4
  %add = add nsw i32 %3, %2
  store i32 %add, ptr %sum, align 4
  br label %for.inc

for.inc:
  %4 = load i32, ptr %i, align 4
  %inc = add nsw i32 %4, 1
  store i32 %inc, ptr %i, align 4
  br label %for.cond

for.end:
  %5 = load i32, ptr %sum, align 4
  ret i32 %5
}
```

注意O0 IR的特征：每个局部变量都通过`alloca`分配在栈上，通过`load`/`store`访问——这是未经过SSA提升的"原始"形态，与C语言的内存模型直接对应。数据库工程师可以将其类比为：未经优化的逻辑计划，每个子查询都物化为临时表。

### 1.3.3 阶段2：中端优化——IR到优化后IR

**源码入口**: `llvm/lib/Passes/PassBuilderPipelines.cpp`

这是LLVM优化器的核心编排文件，2507行代码定义了O0到Oz每个级别的Pass序列。O2级别对这个函数施加的关键变换有：

```
O0 IR
  │
  ├── SROA (Scalar Replacement of Aggregates)
  │     alloca + load/store → SSA寄存器
  │     消除sum和i的栈分配，直接用SSA值
  │     ★ 类比: 消除临时表，直接流水线传递
  │
  ├── SimplifyCFG (Control Flow Graph Simplification)
  │     合并基本块、删除空块
  │     ★ 类比: 消除无用的Union/Project节点
  │
  ├── LICM (Loop Invariant Code Motion)
  │     循环不变量外提(本例中无，但循环外常有)
  │     ★ 类比: 谓词下推/不变子表达式提取
  │
  ├── IndVarSimplify (Induction Variable Simplification)
  │     归纳变量规范化，消除冗余的i计算
  │     ★ 类比: 循环变量规范化
  │
  ├── LoopUnroll (如果展开有利)
  │     循环展开，减少分支开销
  │     ★ 类比: 子查询展开
  │
  └── GVN (Global Value Numbering)
        消除冗余计算
        ★ 类比: 公共子表达式消除
```

**O2下的LLVM IR**（`clang -S -emit-llvm -O2 sum_array.c`）：

```llvm
define i32 @sum_array(ptr nocapture noundef readonly %arr, i32 noundef %n) local_unnamed_addr #0 {
entry:
  %cmp6 = icmp sgt i32 %n, 0
  br i1 %cmp6, label %for.body.preheader, label %for.end

for.body.preheader:                               ; preds = %entry
  %wide.trip.count = zext i32 %n to i64
  br label %for.body

for.body:                                         ; preds = %for.body, %for.body.preheader
  %indvars.iv = phi i64 [ 0, %for.body.preheader ], [ %indvars.iv.next, %for.body ]
  %sum.07 = phi i32 [ 0, %for.body.preheader ], [ %add, %for.body ]
  %arrayidx = getelementptr inbounds i32, ptr %arr, i64 %indvars.iv
  %0 = load i32, ptr %arrayidx, align 4
  %add = add nsw i32 %0, %sum.07
  %indvars.iv.next = add nuw nsw i64 %indvars.iv, 1
  %exitcond.not = icmp eq i64 %indvars.iv.next, %wide.trip.count
  br i1 %exitcond.not, label %for.end, label %for.body

for.end:                                          ; preds = %for.body, %entry
  %sum.0.lcssa = phi i32 [ 0, %entry ], [ %add, %for.body ]
  ret i32 %sum.0.lcssa
}
```

对比O0和O2，关键变化：

1. **alloca/store/load全部消失**——SROA将栈变量提升为SSA值，循环变量通过PHI节点传递
2. **循环变量从i32升级为i64**——IndVarSimplify规范归纳变量，减少循环内的sext
3. **函数属性增加**——`nocapture noundef readonly`是Attribute inference的结果
4. **基本块结构简化**——SimplifyCFG合并了for.inc块

### 1.3.4 阶段3：后端代码生成——IR到机器码

**源码入口**: `llvm/lib/CodeGen/SelectionDAG/SelectionDAGISel.cpp`

后端将优化后的IR转换为目标架构的机器码，这个过程分为多个子阶段：

```
优化后LLVM IR
  │
  ├── 1. SelectionDAG构建
  │     源码: llvm/lib/CodeGen/SelectionDAG/SelectionDAGBuilder.cpp (13,083行)
  │     IR指令 → SDNode DAG (与目标无关的DAG表示)
  │
  ├── 2. 类型合法化 (LegalizeTypes)
  │     源码: llvm/lib/CodeGen/SelectionDAG/LegalizeTypes.cpp
  │     将目标不支持的数据类型转为支持的类型
  │     例: i64 → 两个i32 (32位目标)
  │
  ├── 3. 操作合法化 (LegalizeDAG)
  │     源码: llvm/lib/CodeGen/SelectionDAG/LegalizeDAG.cpp (6,571行)
  │     将目标不支持的操作展开为支持的操作序列
  │
  ├── 4. DAG优化 (DAGCombiner)
  │     源码: llvm/lib/CodeGen/SelectionDAG/DAGCombiner.cpp (31,296行!)
  │     对DAG进行窥孔优化，LLVM最大的单文件
  │
  ├── 5. 指令选择 (Instruction Selection)
  │     源码: llvm/lib/Target/X86/X86ISelDAGToDAG.cpp
  │     DAG模式匹配 → 目标指令(MachineInstr)
  │
  ├── 6. 寄存器分配 (Register Allocation)
  │     源码: llvm/lib/CodeGen/RegAllocGreedy.cpp (2,995行)
  │     虚拟寄存器 → 物理寄存器 + spill/reload
  │
  ├── 7. 指令调度 (Instruction Scheduling)
  │     源码: llvm/lib/CodeGen/MachineScheduler.cpp
  │     重排指令以优化流水线利用率
  │
  └── 8. 代码发射 (Code Emission)
        源码: llvm/lib/CodeGen/AsmPrinter/ + llvm/lib/MC/
        MachineInstr → 汇编文本 / 机器码字节 → ELF目标文件
```

**X86-64汇编输出**（`clang -O2 -S sum_array.c`）：

```asm
sum_array:
    test    edi, edi              # 检查n是否<=0
    jle     .LBB0_3               # 如果是，跳到返回0
    xor     eax, eax              # sum = 0 (xor比mov 0短)
    xor     ecx, ecx              # i = 0
.LBB0_2:                          # 循环体
    add     eax, dword ptr [rdi + 4*rcx]  # sum += arr[i]
    inc     ecx                   # i++
    cmp     ecx, edi              # 比较i和n
    jl      .LBB0_2               # 如果i<n，继续
.LBB0_3:
    ret                           # 返回eax(sum)
```

### 1.3.5 阶段4：汇编与链接——目标文件到可执行文件

**源码入口**: `llvm/lib/MC/` (Machine Code层) + `lld/` (链接器)

MC层将汇编文本或MachineInstr编码为二进制机器码，写入ELF/Mach-O/COFF目标文件。lld链接器将多个目标文件和库合并为最终可执行文件。

```
MachineInstr
  │
  ├── MCCodeEmitter:  指令 → 二进制编码
  │     例: add eax, [rdi+4*rcx] → 03 04 8F (X86-64编码)
  │
  ├── MCAsmBackend:   处理重定位、fixup
  │
  ├── MCObjectWriter: 写入目标文件(ELF/Mach-O/COFF)
  │
  └── lld:            链接多个.o + 库 → 可执行文件
       lld/ELF/       Linux ELF链接器
       lld/MachO/     macOS Mach-O链接器
       lld/COFF/      Windows COFF链接器
```

### 1.3.6 完整流程一览：从宏观到微观

将上述所有阶段合并，我们得到一个完整的编译流程全景图：

```
sum_array.c
    │
    │ [Clang 前端]
    │  Lexer → Parser → Sema → CodeGen
    │  源码: clang/lib/Lex/ → Parse/ → Sema/ → CodeGen/
    │
    ▼
sum_array.ll (O0, 未优化IR)
    │  特征: alloca + load/store, 冗余基本块
    │
    │ [LLVM 优化器 - opt]
    │  Pass序列: SROA → SimplifyCFG → EarlyCSE → LICM →
    │            IndVarSimplify → GVN → InstCombine → ...
    │  源码: llvm/lib/Passes/PassBuilderPipelines.cpp
    │  编排: PassBuilder → Module → CGSCC → Function → Loop 层次
    │
    ▼
sum_array.ll (O2, 优化后IR)
    │  特征: 纯SSA, PHI传递循环变量, 函数属性标注
    │
    │ [LLVM 后端 - llc]
    │  SelectionDAG构建 → 类型合法化 → 操作合法化 →
    │  DAG优化 → 指令选择 → 寄存器分配 → 指令调度 → 代码发射
    │  源码: llvm/lib/CodeGen/ (SelectionDAG/ + GlobalISel/ + RegAlloc/ + ...)
    │
    ▼
sum_array.s (X86-64汇编)
    │
    │ [MC层 + 汇编器]
    │  汇编 → 重定位 → 机器码 → ELF目标文件
    │  源码: llvm/lib/MC/
    │
    ▼
sum_array.o (ELF目标文件)
    │
    │ [链接器 - lld]
    │  符号解析 → 重定位 → 生成可执行文件
    │  源码: lld/ELF/
    │
    ▼
a.out (可执行文件)
```

---

## 1.4 透视Instruction.def：69条指令的分类学

在1.3节我们看到LLVM IR在编译流程中扮演核心角色，但IR到底由什么构成？答案在`llvm/include/llvm/IR/Instruction.def`中——这个257行的文件定义了LLVM IR的**全部**指令集。

### 1.4.1 X-macro技巧

`Instruction.def`使用了一种称为X-macro的C预编程技巧。它不定义任何代码，只定义宏调用——具体的代码生成由include它的文件决定：

```c
// Instruction.def 的核心模式:
HANDLE_TERM_INST  ( 3, CondBr, CondBrInst)    // 条件分支
HANDLE_BINARY_INST(14, Add  , BinaryOperator)  // 整数加法
HANDLE_MEMORY_INST(35, GetElementPtr, GetElementPtrInst)  // 地址计算
HANDLE_CAST_INST  (39, Trunc, TruncInst)       // 整数截断
HANDLE_OTHER_INST (55, ICmp , ICmpInst)        // 整数比较
```

每个条目包含三个字段：**操作码编号**、**助记符**、**C++类名**。不同的消费者通过定义不同的宏来获取不同视角：

- `llvm/IR/Instruction.h`定义`HANDLE_INST`为枚举生成，得到`enum OpCode { Ret=1, ..., Freeze=69 }`
- `llvm/IR/Instructions.h`定义各类HANDLE宏为前向声明，得到所有指令类的声明
- `Instruction::classof()`使用操作码范围进行类型检查

**这种技巧的工程价值**：在257行中维护69条指令的完整定义，任何新增指令只需修改一处，所有消费方自动同步。这就像数据库中用系统表(catalog)维护元数据——单一真相来源(Single Source of Truth)。

### 1.4.2 七大指令分类

`Instruction.def`将69条指令分为7个类别，每个类别有连续的操作码范围：

```
┌─────────────────────────────────────────────────────────────────┐
│  Terminator Instructions (操作码 1-12)                          │
│  控制流终结者——每个基本块必须且只能以一条终结指令结尾              │
│                                                                  │
│  Ret(1)          返回                                            │
│  UncondBr(2)     无条件跳转                                      │
│  CondBr(3)       条件跳转                                        │
│  Switch(4)       switch多路分支                                  │
│  IndirectBr(5)   间接跳转(跳转地址在寄存器中)                    │
│  Invoke(6)       带异常处理的调用                                │
│  Resume(7)       异常恢复                                        │
│  Unreachable(8)  不可达标记                                      │
│  CleanupRet(9)   异常清理返回                                    │
│  CatchRet(10)    异常捕获返回                                    │
│  CatchSwitch(11) 异常捕获switch                                  │
│  CallBr(12)      可跳转的调用(GCC asm goto)                      │
├─────────────────────────────────────────────────────────────────┤
│  Unary Instructions (操作码 13)                                  │
│  一元运算——目前只有一条                                          │
│                                                                  │
│  FNeg(13)        浮点取反                                        │
│  注: 整数取反用 Sub 0, x 或 XOR x, -1 表示                      │
├─────────────────────────────────────────────────────────────────┤
│  Binary Instructions (操作码 14-31)                              │
│  二元运算——算术 + 逻辑 + 移位                                    │
│                                                                  │
│  算术: Add(14) FAdd(15) Sub(16) FSub(17)                        │
│        Mul(18) FMul(19) UDiv(20) SDiv(21) FDiv(22)             │
│        URem(23) SRem(24) FRem(25)                               │
│  移位: Shl(26) LShr(27) AShr(28)                                │
│  逻辑: And(29) Or(30) Xor(31)                                   │
├─────────────────────────────────────────────────────────────────┤
│  Memory Instructions (操作码 32-38)                              │
│  内存操作——LLVM与硬件的接口                                      │
│                                                                  │
│  Alloca(32)        栈分配                                        │
│  Load(33)          内存读取                                      │
│  Store(34)         内存写入                                      │
│  GetElementPtr(35) 地址计算(GEP) ★最重要的内存指令★              │
│  Fence(36)         内存屏障                                      │
│  AtomicCmpXchg(37) 原子比较交换                                  │
│  AtomicRMW(38)     原子读-改-写                                  │
├─────────────────────────────────────────────────────────────────┤
│  Cast Instructions (操作码 39-52)                                │
│  类型转换——连接不同类型世界的桥梁                                │
│                                                                  │
│  Trunc(39)       整数截断(大→小)                                │
│  ZExt(40)        零扩展(小→大, 无符号)                          │
│  SExt(41)        符号扩展(小→大, 有符号)                        │
│  FPToUI(42)      浮点→无符号整数                                │
│  FPToSI(43)      浮点→有符号整数                                │
│  UIToFP(44)      无符号整数→浮点                                │
│  SIToFP(45)      有符号整数→浮点                                │
│  FPTrunc(46)     浮点截断(大→小)                                │
│  FPExt(47)       浮点扩展(小→大)                                │
│  PtrToInt(48)    指针→整数                                      │
│  PtrToAddr(49)   指针→地址(新增!)                               │
│  IntToPtr(50)    整数→指针                                      │
│  BitCast(51)     位模式重解释                                    │
│  AddrSpaceCast(52) 地址空间转换(GPU编译关键!)                   │
├─────────────────────────────────────────────────────────────────┤
│  FuncletPad Instructions (操作码 53-54)                          │
│  异常处理辅助                                                    │
│                                                                  │
│  CleanupPad(53)  清理区域入口                                    │
│  CatchPad(54)    捕获区域入口                                    │
├─────────────────────────────────────────────────────────────────┤
│  Other Instructions (操作码 55-69)                               │
│  其他——最多样化的一类                                            │
│                                                                  │
│  ICmp(55)           整数比较                                     │
│  FCmp(56)           浮点比较                                     │
│  PHI(57)            SSA合并节点 ★SSA的标志★                     │
│  Call(58)           函数调用                                     │
│  Select(59)         条件选择(类似三目运算符)                     │
│  UserOp1(60)/2(61)  内部使用                                    │
│  VAArg(62)          可变参数访问                                 │
│  ExtractElement(63) 从向量提取元素                               │
│  InsertElement(64)  向向量插入元素                               │
│  ShuffleVector(65)  向量重排                                    │
│  ExtractValue(66)   从聚合体提取字段                            │
│  InsertValue(67)    向聚合体插入字段                            │
│  LandingPad(68)     异常处理着陆垫                              │
│  Freeze(69)         冻结undef/poison为具体值                    │
└─────────────────────────────────────────────────────────────────┘
```

### 1.4.3 从分类学看设计哲学

从这个分类可以提炼出LLVM IR的几个核心设计决策：

**1. 极简指令集 + 无限内联函数**

69条指令看似很少，但LLVM通过内联函数(intrinsics)机制将大量复杂操作编码为`call @llvm.*`形式，如`llvm.memcpy`、`llvm.expect`、`llvm.sadd.with.overflow`等。内联函数定义在`llvm/include/llvm/IR/Intrinsics.td`(目标无关)和`llvm/include/llvm/IR/IntrinsicsX86.td`等(目标相关)中。这种设计使得核心指令集保持精简，同时通过intrinsic扩展无限表达能力。

**类比**：SQL中核心只有SELECT/FROM/WHERE/GROUP BY/HAVING/ORDER BY，但通过窗口函数、CTE、JSON函数等扩展无限表达能力。

**2. GEP是一条指令，不是语法糖**

GetElementPtr(GEP)是LLVM最独特的指令之一。它纯粹做地址计算而不访问内存，这让优化器可以在完全不考虑内存别名的情况下对GEP进行代数变换。这个设计直接体现了**将副作用与纯计算分离**的哲学。

**类比**：这就像数据库将逻辑计划节点与物理访问路径分离——LogicalJoin只描述"要连接"，物理算子(HashJoin/NestedLoop)才涉及实际IO。

**3. PHI是一等公民**

在许多编译器中，PHI节点是事后补丁。但在LLVM中，PHI是操作码57的一等指令，必须在基本块头部，直接参与def-use链。这让SSA成为IR的一等属性而非可选优化。

**4. 顺序有意义：Cast指令的编号编码了化简规则**

注释中明确写道："The order matters here because CastInst::isEliminableCastPair encodes a table based on this ordering." Cast指令的编号不是随意的——它编码了化简规则表的索引，使得O(1)判断两个连续cast是否可以合并。这种将语义编码到表示中的做法在编译器设计中反复出现。

---

## 1.5 编译流程的可观测性：工具链实战

理解理论框架后，掌握工具链是深入源码的前提。LLVM提供了强大的可观测性工具，让我们能像数据库的EXPLAIN一样逐阶段查看编译过程。

### 1.5.1 核心工具速查

```bash
# 1. 前端：C/C++ → LLVM IR
clang -S -emit-llvm -O0 sum_array.c -o sum_array_O0.ll   # 未优化IR
clang -S -emit-llvm -O2 sum_array.c -o sum_array_O2.ll   # 优化后IR

# 2. 优化器：IR → 优化IR
opt -S -O2 sum_array_O0.ll -o sum_array_opt.ll           # 完整O2优化
opt -S -passes=sroa,simplifycfg sum_array_O0.ll -o out.ll # 指定Pass

# 3. 后端：IR → 汇编
llc sum_array_O2.ll -o sum_array.s                        # 默认目标
llc -march=x86-64 sum_array_O2.ll -o sum_array_x86.s     # 指定X86
llc -march=aarch64 sum_array_O2.ll -o sum_array_arm.s    # 指定ARM

# 4. 位码与文本互转
llvm-as sum_array.ll -o sum_array.bc    # 文本 → 位码
llvm-dis sum_array.bc -o sum_array.ll   # 位码 → 文本

# 5. 查看编译阶段
clang -ccc-print-phases sum_array.c     # 显示完整阶段列表
```

### 1.5.2 Pass级可观测性——编译器的EXPLAIN

这是最强大的调试功能，类似于数据库的EXPLAIN ANALYZE：

```bash
# 查看每个Pass执行后的IR变化
opt -S -O2 -mllvm -print-after-all sum_array_O0.ll 2>pass_log.txt

# 只看特定Pass的效果
opt -S -passes=sroa -mllvm -print-after=sroa sum_array_O0.ll

# 查看特定Pass的调试信息(需要debug构建)
opt -S -O2 -debug-only=licm sum_array_O0.ll 2>licm_debug.txt

# 查看Pass统计信息
opt -S -O2 -stats sum_array_O0.ll 2>&1 | grep "licm"

# 生成优化报告(YAML格式，可用opt-viewer可视化)
clang -O2 -fsave-optimization-record sum_array.c
```

### 1.5.3 后端可观测性

```bash
# 查看指令选择过程
llc -debug-only=isel sum_array_O2.ll 2>isel_debug.txt

# 查看寄存器分配过程
llc -debug-only=regalloc sum_array_O2.ll 2>regalloc_debug.txt

# 查看指令调度
llc -debug-only=pre-RA-sched sum_array_O2.ll 2>sched_debug.txt

# 查看完整后端流水线
llc -print-after-all sum_array_O2.ll 2>backend_log.txt

# 机器码性能分析
llvm-mca -mcpu=skylake sum_array.s
```

### 1.5.4 一个完整的观测实验

让我们用工具链完整观测`sum_array`的优化过程：

```bash
# 步骤1: 生成O0 IR
clang -S -emit-llvm -O0 sum_array.c -o sum_array_O0.ll

# 步骤2: 逐Pass观察SROA的效果
opt -S -passes=sroa sum_array_O0.ll -o after_sroa.ll
# 对比: alloca/store/load 全部消失!

# 步骤3: 逐Pass观察完整O2的效果
opt -S -O2 -mllvm -print-after-all sum_array_O0.ll 2>full_pipeline.txt
# 在full_pipeline.txt中搜索每个Pass名，观察IR的渐变

# 步骤4: 生成最终汇编
llc -march=x86-64 after_O2.ll -o sum_array.s

# 步骤5: 机器码性能分析
llvm-mca -mcpu=skylake sum_array.s
# 输出: 吞吐量、延迟、端口压力分析
```

这个实验建立了贯穿本书的方法论：**用工具链观测 → 用源码解释 → 用体系结构理解**。每一章我们都会用这种方式深入特定子系统。

---

## 1.6 本章小结

本章建立了三个核心认知框架：

1. **编译器 ≈ 查询引擎**：三段式架构、SSA与关系代数、Pass Pipeline与Rule Engine——两个系统的核心抽象高度同构，理解一个就能加速理解另一个。

2. **LLVM IR是全局枢纽**：69条指令(定义在`Instruction.def`中)构成了前端的输出语言、优化器的操作对象、后端的输入格式。掌握IR就掌握了LLVM的DNA。

3. **完整编译流程是一条可观测的管线**：从C代码到机器码，每一步都有对应的源码文件和观测工具。`-print-after-all`和`-debug-only`是编译器的EXPLAIN。

下一章我们将深入IR的内部——Value/User/Instruction的内存布局、类型系统的设计、def-use链的工程实现——从"IR是什么"进入"IR怎么工作"。
