# 第2章 LLVM IR：类型化SSA的精妙设计

## 2.1 为什么是SSA？——从理论到工程实现

### 2.1.1 SSA的理论优势

SSA(Static Single Assignment)的核心约束极其简单：**每个变量只被赋值一次**。这条约束带来的收益却极其深远：

1. **唯一的定义点**：每个值只有一个def，优化器无需追踪多个赋值之间的数据流
2. **显式的数据依赖**：def-use链直接编码了值的传播路径，无需额外分析
3. **简化的常量传播**：因为每个值只有一个定义，常量传播可以在O(1)确定值的来源
4. **自然的PHI合并**：控制流汇合处的值选择通过PHI节点显式表达，而非隐式覆盖

用数据库的类比：SSA就像是一个每行只能写入一次的表——你永远不需要判断"这行数据是哪个事务最后修改的"，因为只有一次写入。这让数据血缘(lineage)追踪从O(n)变为O(1)。

### 2.1.2 Value→User→Instruction：def-use链的内存布局

LLVM SSA的核心数据结构是`Value`/`User`/`Use`三层体系，定义在三个头文件中：

```
                    Value.h (1078行)
                    ┌─────────────────────────────────┐
                    │  Value                           │
                    │  - SubclassID: 子类型标识          │
                    │  - VTy: Type*                     │
                    │  - UseList: Use* (使用链表头)      │
                    │  - Name: ValueName*               │
                    │                                  │
                    │  核心方法:                         │
                    │  - use_begin()/use_end()          │
                    │  - replaceAllUsesWith()           │
                    │  - users()                        │
                    └────────────┬────────────────────┘
                                 │ 继承
                    ┌────────────┴────────────────────┐
                    │                                  │
              User.h (364行)                    其他子类
         ┌──────────────────────┐            Argument
         │  User : Value         │            BasicBlock
         │  - OperandList: Use*  │            Function
         │  - NumOperands        │            GlobalVariable
         │                      │            Constant
         │  核心方法:            │
         │  - getOperand(i)      │
         │  - setOperand(i, V)   │
         │  - operands()         │
         └──────────┬───────────┘
                    │ 继承
         ┌──────────┴───────────┐
         │  Instruction : User   │
         │  - 基本块指针          │
         │  - 操作码              │
         │  - 调试信息            │
         │  - 内存操作标记        │
         └──────────────────────┘
```

关键在于`Use`类(`Use.h`, 126行)——它是Value和User之间的双向链接：

```
         Value                    Use                     User
    ┌──────────────┐      ┌────────────────┐      ┌──────────────┐
    │ UseList ──────┼──→   │ Val: Value*    │      │ OperandList  │
    │              │      │ Next: Use* ─────────→ │   Use[]      │
    │              │  ←───│ Prev: Use**    │      │              │
    │              │      │ Parent: User*  │──→   │              │
    └──────────────┘      └────────────────┘      └──────────────┘

    Value的UseList: 穿链表，所有使用该Value的Use通过Next/Prev串联
    User的OperandList: 连续数组，Use对象紧挨User对象存储(内联)或悬挂在外(外挂)
```

**这个设计的精妙之处**：

1. **从Value出发**：遍历`UseList`链表可以找到所有使用该Value的User（def→use方向）
2. **从User出发**：遍历`OperandList`数组可以找到该User使用的所有Value（use→def方向）
3. **O(1)替换**：`replaceAllUsesWith(NewValue)`只需修改Use的Val指针并调整链表，无需遍历指令
4. **缓存友好**：Use数组与User对象连续存储（内联模式），提高内存局部性

源码追踪：`Value::replaceAllUsesWith()`定义在`llvm/lib/IR/Value.cpp`(1342行)中，核心逻辑是遍历UseList，将每个Use的Val从旧Value改为新Value，同时维护双向链表。

### 2.1.3 Instruction.def：X-macro指令表的工程智慧

在第1章我们看到了`Instruction.def`的七大分类。这里深入其工程机制：

```c
// llvm/include/llvm/IR/Instruction.def 核心宏模式

// Terminator类指令
#ifndef HANDLE_TERM_INST
#define HANDLE_TERM_INST(NUM, OPC, CLASS) HANDLE_INST(NUM, OPC, CLASS)
#endif
HANDLE_TERM_INST( 1, Ret,       ReturnInst)
HANDLE_TERM_INST( 3, CondBr,    CondBrInst)
...

// Binary类指令
#ifndef HANDLE_BINARY_INST
#define HANDLE_BINARY_INST(NUM, OPC, CLASS) HANDLE_INST(NUM, OPC, CLASS)
#endif
HANDLE_BINARY_INST(14, Add,      BinaryOperator)
HANDLE_BINARY_INST(18, Mul,      BinaryOperator)
...
```

消费者通过定义自己的宏来"消费"这个定义表：

| 消费者文件 | 定义的宏 | 效果 |
|-----------|---------|------|
| `Instruction.h` | `HANDLE_INST` → 枚举生成 | `enum OpCode { Ret=1, Add=14, ... }` |
| `Instructions.h` | 各HANDLE宏 → 前向声明 | 所有指令类的声明 |
| `Instruction.cpp` | `HANDLE_INST` → `classof()` | `isa<AddInst>(V)` 类型检查 |

**工程启示**：X-macro是一种无依赖的代码生成技术——不需要TableGen这样的外部工具，仅用C预处理器就能在257行中维护69条指令的完整定义。这比数据库的DDL+触发器方案更轻量，但达到了同样的"单一真相来源"效果。

---

## 2.2 类型系统：从typed pointer到opaque pointer的演进

### 2.2.1 Type继承体系

LLVM的类型系统定义在`Type.h`(563行)和`DerivedTypes.h`(920行)中，采用值类型(非继承)设计——所有类型共享`Type`类的内存布局，通过`TypeID`枚举区分子类型：

```
Type (563行, 不可变、唯一化)
├── TypeID枚举:
│   HalfTyID(0)      ── 16位浮点(bf16/fp16)
│   BFloatTyID(1)    ── 16位浮点(7位尾数)
│   FloatTyID(2)     ── 32位浮点(fp32)
│   DoubleTyID(3)    ── 64位浮点(fp64)
│   X86_FP80TyID(4)  ── 80位浮点(x87)
│   FP128TyID(5)     ── 128位浮点(112位尾数)
│   PPC_FP128TyID(6) ── 128位浮点(PowerPC双double)
│   VoidTyID(7)      ── void
│   LabelTyID(8)     ── 基本块标签
│   MetadataTyID(9)  ── 元数据
│   X86_AMXTyID(10)  ── AMX向量(X86)
│   TokenTyID(11)    ── 词法token
│   IntegerTyID(12)  ── 任意位宽整数
│   ByteTyID(13)     ── 字节类型
│   FunctionTyID(14) ── 函数类型
│   PointerTyID(15)  ── 指针(opaque pointer!)
│   StructTyID(16)   ── 结构体
│   ArrayTyID(17)    ── 数组
│   FixedVectorTyID(18)   ── 固定宽度向量
│   ScalableVectorTyID(19)── 可伸缩向量(SVE/RISC-V V)
│   TypedPointerTyID(20)  ── 类型化指针(仅GPU目标)
│   TargetExtTyID(21)     ── 目标扩展类型
```

**设计决策：不可变+唯一化**。`Type`对象一旦创建就永不修改，且相同类型只有一个实例——比较两个类型是否相同只需指针比较(`T1 == T2`)，无需递归比较结构。这与数据库中的interning技术异曲同工：将频繁比较的值唯一化，用指针比较替代值比较。

### 2.2.2 IntegerType：任意位宽的工程实现

```c
// llvm/include/llvm/IR/DerivedTypes.h
class IntegerType : public Type {
  // 位宽存储在Type::SubclassData中(24位，最大2^23=8388608)
  unsigned getBitWidth() const { return getSubclassData(); }

  // 范围约束
  enum {
    MIN_INT_BITS = 1,
    MAX_INT_BITS = (1<<23)  // 8388608
  };

  // 唯一化工厂方法
  static IntegerType *get(LLVMContext &C, unsigned NumBits);
};
```

LLVM支持从i1到i8388608的任意位宽整数。这意味着：
- `i1`：布尔值（条件码、标记位）
- `i8/i16/i32/i64`：标准整数
- `i24`：某些DSP的寻址宽度
- `i128/i256`：大整数（加密算法、任意精度运算）

位宽存储在`SubclassData`字段中（24位），而非单独的成员变量——这是一种零额外内存开销的设计。

### 2.2.3 FunctionType / StructType / VectorType

**FunctionType**：函数签名 = 返回类型 + 参数类型列表 + 可变参数标记

```c
class FunctionType : public Type {
  bool isVarArg;           // 是否可变参数(如printf)
  Type *ReturnType;        // 返回类型
  unsigned NumContainedTys; // 参数数量
  Type *ContainedTys;      // 参数类型数组(紧随对象分配)
};
```

**StructType**：结构体 = 有序类型列表 + 命名 + 字面量标记

```c
class StructType : public Type {
  // 两种形态:
  // 1. 命名结构体: %struct.Point = type { i32, i32 }
  // 2. 字面结构体: type { i32, i32 }  (匿名, 每次创建相同)
  bool isLiteral;
  bool isPacked;  // 紧凑排列(<{...}>), 无对齐填充
};
```

**VectorType**：两种向量

```c
// 固定宽度向量: <4 x i32>  →  128-bit SIMD
class FixedVectorType : public VectorType { ... };

// 可伸缩向量: <vscale x 4 x i32>  →  SVE/RISC-V V
// vscale在运行时确定, 编译期只知道"是4的倍数"
class ScalableVectorType : public VectorType { ... };
```

可伸缩向量是LLVM对ARM SVE和RISC-V V扩展的支持。`vscale`是一个运行时常量，表示向量寄存器的实际宽度与最小宽度的比值。例如在SVE-256上，`<vscale x 4 x i32>`实际为`<8 x i32>`（vscale=2）。

### 2.2.4 指针类型革命：为什么LLVM走向opaque pointer

LLVM 15-17完成了一次重大迁移：从typed pointer到opaque pointer。

**旧世界(typed pointer)**：
```llvm
i32*        ; 指向i32的指针
i32**       ; 指向i32指针的指针
void()*     ; 函数指针
```

**新世界(opaque pointer)**：
```llvm
ptr         ; 统一的指针类型，不携带所指类型信息
```

这个迁移的原因深植于编译器工程实践：

1. **类型不一致问题**：同一个地址在不同上下文中可能被`load`为不同类型，typed pointer要求插入`bitcast`，产生了大量冗余指令
2. **优化阻碍**：`bitcast i32* %p to float*`创造了额外的use和def，干扰别名分析和常量传播
3. **前端负担**：Clang必须精确推断每个指针的类型，但在C/C++的隐式转换面前这往往不必要

迁移后，指针类型信息转移到`load`/`store`/`getelementptr`指令的操作数中：
```llvm
; 旧: bitcast + typed load
%p2 = bitcast i32* %p to float*
%v = load float, float* %p2

; 新: 直接用ptr
%v = load float, ptr %p
```

**体系结构视角**：硬件根本不区分"指向i32的指针"和"指向float的指针"——地址就是地址，类型信息只在load/store时才需要。opaque pointer让IR更忠实地反映了硬件语义。

---

## 2.3 常量与元数据：编译期信息的载体

### 2.3.1 Constant层次

常量是编译期已知的值，它们不是指令（不产生运行时计算），但可以是指令的操作数。定义在`Constants.h`(1690行)中：

```
Constant : User (常量也是Value的User!)
├── ConstantData : Constant
│   ├── ConstantInt       ── 整数常量: i32 42, i1 true
│   ├── ConstantByte      ── 字节常量
│   ├── ConstantFP        ── 浮点常量: float 3.14
│   ├── ConstantAggregateZero ── 零初始化: zeroinitializer
│   ├── ConstantPointerNull   ── 空指针: null
│   └── ConstantTokenNone     ── token none
│
├── ConstantAggregate : Constant
│   ├── ConstantArray     ── 数组常量: [i32 1, i32 2, i32 3]
│   ├── ConstantStruct    ── 结构体常量: {i32 1, float 2.0}
│   └── ConstantVector    ── 向量常量: <i32 1, i32 2, i32 3, i32 4>
│
├── ConstantExpr : Constant  ── 常量表达式(编译期计算!)
│   └── GEP/bitcast/icmp等操作的编译期版本
│
├── UndefValue : ConstantData ── 未定义值: 每次读取可能不同
│   └── PoisonValue : UndefValue ── 毒值: 使用它导致UB
│
├── BlockAddress : Constant   ── 基本块地址(用于indirectbr)
├── DSOLocalEquivalent : Constant
├── NoCFIValue : Constant
└── ConstantPtrAuth : Constant ── 指针认证(ARM PAC)
```

**关键设计**：

- **ConstantInt是唯一化的**：相同位宽和值的整数只有一个`ConstantInt`实例，通过`ConstantInt::get(Context, APInt)`获取
- **ConstantExpr是编译期计算**：`gep (ptr @global, i64 4)`在编译期就能计算出地址偏移，不需要运行时指令
- **UndefValue vs PoisonValue**：
  - `undef`：每次读取可以返回任意值（可能每次不同）——优化器可以自由选择任何值
  - `poison`：使用它(如作为除数、分支条件)导致未定义行为——比undef更严格的语义

```
; undef的语义:
%x = add i32 %y, undef    ; → 可以替换为任何i32值，优化器可以选择最简形式

; poison的语义:
%div = udiv i32 %x, poison ; → UB! 因为poison被"使用"了
%store = store i32 poison, ptr %p ; → OK! store不"使用"存储的值
```

### 2.3.2 Metadata体系

元数据为IR附加额外的语义信息，不影响程序执行语义，但指导优化和调试。定义在`Metadata.h`(1869行)和`Metadata.def`中：

```
Metadata (抽象基类)
├── MDString : Metadata      ── 字符串元数据
├── MDNode : Metadata        ── 元数据节点(元组)
│   └── MDTuple : MDNode     ── 有序元数据列表
│       ├── !tbaa = !{!0, !1, i64 0}      ── 类型别名分析
│       ├── !prof = !{!"function_entry_count", i64 1000} ── PGO信息
│       ├── !noalias = !{!0}               ── 无别名作用域
│       └── !range = !{i64 0, i64 100}     ── 值范围
│
├── ValueAsMetadata : Metadata ── 将Value包装为Metadata
└── DI-* : DebugInfo元数据(定义在DebugInfoMetadata.h)
    ├── DICompileUnit     ── 编译单元
    ├── DISubprogram      ── 子程序(函数)
    ├── DILocalVariable   ── 局部变量
    ├── DIExpression      ── DWARF表达式
    ├── DILocation        ── 源码位置(行/列/文件)
    └── DIBasicType       ── 基本类型描述
```

元数据通过`!name`语法附加到指令和函数上：

```llvm
define i32 @sum_array(ptr %arr, i32 %n) !prof !1 {
  %v = load i32, ptr %arr, !tbaa !2, !range !3
  ...
}

!1 = !{!"function_entry_count", i64 1000}  ; PGO: 函数调用1000次
!2 = !{!4, !5, i64 0}                       ; TBAA: int类型的加载
!3 = !{i64 0, i64 100}                       ; 值范围: [0, 100)
!4 = !{!"int", !5}
!5 = !{!"omnipotent char"}
```

**数据库类比**：元数据就像数据库中的统计信息(pg_stats)——不影响查询结果，但深刻影响优化器的决策。TBAA告诉优化器"这两个内存访问不会别名"，就像统计信息告诉优化器"这个列的选择度是0.01"。

### 2.3.3 DebugInfo：从源码到IR的映射

DebugInfo是LLVM与调试器(如lldb/gdb)之间的契约，基于DWARF标准：

```
源码: int sum = 0;   行5, 列7
  │
  ▼ CodeGen生成
IR:  %sum = alloca i32, !dbg !10
     call void @llvm.dbg.value(metadata i32 0, metadata !11, metadata !DIExpression()), !dbg !10
  │
  ▼ DebugInfo元数据
!10 = !DILocation(line: 5, column: 7, scope: !12)
!11 = !DILocalVariable(name: "sum", scope: !12, type: !13)
!12 = !DISubprogram(name: "sum_array", ...)
!13 = !DIBasicType(name: "int", size: 32, encoding: DW_ATE_signed)
```

源码入口：`clang/lib/CodeGen/CGDebugInfo.cpp`生成DebugInfo元数据，`llvm/lib/CodeGen/AsmPrinter/DwarfCompileUnit.cpp`将DebugInfo转为DWARF段。

---

## 2.4 Module-Function-BasicBlock-Instruction：四层IR容器

### 2.4.1 Module的全局视野

`Module`(定义在`Module.h`, 1089行)是IR的最外层容器，持有：

```
Module (一个编译单元)
├── Function列表        ── 所有函数定义和声明
├── GlobalVariable列表  ── 全局变量
├── GlobalAlias列表     ── 全局别名
├── GlobalIFunc列表     ── 间接函数
├── DataLayout          ── 目标机数据布局 ★
├── TargetTriple        ── 目标三元组(如x86_64-unknown-linux-gnu)
├── ModuleFlagsMetadata ── 模块级元数据(如!llvm.ident)
└── LLVMContext         ── 所属上下文
```

**DataLayout：体系结构的信息注入点**

`DataLayout`(定义在`DataLayout.h`, 839行)是编译器理解目标硬件的关键接口：

```c
class DataLayout {
  // 典型的X86-64布局字符串:
  // "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-f80:128-n8:16:32:64-S128"

  unsigned AllocaAddrSpace;     // alloca的地址空间
  unsigned ProgramAddrSpace;    // 程序地址空间
  SmallVector<PointerLayout> Pointers; // 各地址空间的指针大小和对齐
  unsigned StackNaturalAlign;   // 栈自然对齐
  // ... 类型大小/对齐查询接口
};
```

DataLayout直接影响优化决策：
- 指针大小(4 vs 8字节)影响GEP计算和内联成本
- 类型对齐影响memcpy/memset的选择
- 大端/小端影响常量折叠

**类比**：DataLayout就像数据库的统计信息系统表——优化器必须查询它才能做出正确决策，否则只能保守假设。

### 2.4.2 Function：IR的核心单元

`Function`(定义在`Function.h`, 1090行)既是Module的子容器，也是GlobalValue：

```
Function : GlobalValue : Constant : User : Value
├── Argument列表       ── 函数参数(也是Value的子类)
├── BasicBlock列表     ── 基本块(指令的有序列表)
├── 函数属性           ── readonly, norecurse, willreturn等
├── 调用约定           ── C calling convention, fastcc等
├── GC策略             ── 垃圾回收策略名
└── 个人编号(PersonalityFn) ── 异常处理函数
```

Function继承链的意义：**函数本身是一个值**——可以被存储、作为参数传递、被调用。这反映了函数式编程的核心思想：函数是一等公民。

### 2.4.3 BasicBlock：指令的容器与控制流节点

`BasicBlock`(定义在`BasicBlock.h`, 794行)是一段顺序执行的指令序列，以一条终结指令(Terminator)结尾：

```
BasicBlock : Value (基本块也是值——可作为switch/indirectbr的目标)
├── InstList: 指令双向链表
│   ├── 普通指令(0..N-2)
│   └── 终结指令(N-1): 必须是Ret/Br/Invoke/...之一
│
├── 前驱块(predecessors): 通过其他块的Terminator推导
└── 后继块(successors): 通过Terminator的操作数获取
```

**关键不变量**(由Verifier强制检查)：
1. 基本块最后一条指令必须是Terminator
2. PHI节点必须出现在基本块头部(在所有非PHI指令之前)
3. 基本块不能为空(至少包含一条Terminator)

### 2.4.4 LLVMContext：IR世界的上下文

`LLVMContext`(定义在`LLVMContext.h`, 385行)是IR对象的内存管理器和唯一化工厂：

```c
class LLVMContext {
  // 核心职责:
  // 1. Type唯一化: IntegerType::get(Ctx, 32) 总返回同一指针
  // 2. Constant唯一化: ConstantInt::get(Ctx, APInt(32, 42)) 同理
  // 3. MDNode唯一化/回收
  // 4. 线程安全: 每个线程应该有自己的Context(多线程编译)
};
```

**工程实践**：通常一个编译进程使用一个LLVMContext，但多线程编译时每个线程需要独立的Context，因为Type/Constant的唯一化表不是线程安全的。

---

## 2.5 IR构建与验证

### 2.5.1 IRBuilder + ConstantFolder + InstSimplifyFolder

`IRBuilder`(定义在`IRBuilder.h`, 2902行)是构建IR的主要工具：

```c++
// IRBuilder的分层设计
IRBuilderBase (114行基类)
├── 插入点管理: InsertPt, SetInsertPoint()
├── 基础创建: CreateAdd, CreateSub, CreateMul, ...
├── 内存操作: CreateAlloca, CreateLoad, CreateStore, ...
├── 控制流: CreateBr, CreateCondBr, CreateRet, ...
├── 类型创建: getInt32, getFloat, getPtrTy, ...
└── 常量折叠: Folder对象

IRBuilder<Folder> : IRBuilderBase
├── IRBuilder<ConstantFolder>    ── 默认: 仅折叠常量
├── IRBuilder<InstSimplifyFolder> ── 进阶: 调用InstSimplify化简
└── 自定义Folder                  ── 可扩展
```

使用示例：

```c++
IRBuilder<> Builder(BB);  // 在基本块BB的末尾插入

// 创建常量折叠后的指令
Value *Sum = Builder.CreateAdd(LHS, RHS, "sum");
// 如果LHS和RHS都是常量, CreateAdd直接返回ConstantInt而不创建指令!

// 创建GEP
Value *ElemPtr = Builder.CreateGEP(ArrayTy, BasePtr, {Idx0, Idx1}, "elem");

// 创建条件分支
Builder.CreateCondBr(Cond, TrueBB, FalseBB);
```

### 2.5.2 Verifier：8425行的IR不变量守卫者

`Verifier`(定义在`llvm/lib/IR/Verifier.cpp`, 8425行)是LLVM的"类型检查器"，确保IR满足所有不变量：

```c++
// Verifier的核心检查类别:
class Verifier : public InstVisitor<Verifier> {
  // 模块级检查
  void verify(const Module &M);       // 全局变量、函数声明一致性
  // 函数级检查
  void verify(const Function &F);     // 参数类型、属性一致性
  // 指令级检查
  void visitAdd(BinaryOperator &B);   // 操作数类型匹配
  void visitLoad(LoadInst &LI);       // 指针类型、对齐合法
  void visitPHI(PHINode &PN);         // 值数量=前驱数量
  void visitCall(CallInst &CI);       // 参数类型=函数签名
  // ... 为每类指令定义专门的visit方法
};
```

**关键不变量举例**：

1. **PHI节点**：`PHINode::getNumIncomingValues() == BB->getNumPredecessors()`
2. **内存指令**：`LoadInst`的操作数必须是指针类型，`StoreInst`的值类型必须匹配指针所指类型
3. **终结指令**：每个基本块必须且只能以一条终结指令结尾
4. **类型一致性**：`add i32 %a, %b`的操作数类型必须完全一致
5. **引用完整性**：指令只能引用同一函数中的值或全局值

### 2.5.3 PatternMatch：模式匹配DSL

`PatternMatch`(定义在`PatternMatch.h`, 3404行)提供了一套声明式的模式匹配语法，是优化Pass的核心工具：

```c++
// 传统写法:
if (auto *BO = dyn_cast<BinaryOperator>(V))
  if (BO->getOpcode() == Instruction::Add)
    if (auto *C = dyn_cast<ConstantInt>(BO->getOperand(1)))
      if (C->isZero())
        return BO->getOperand(0);  // x + 0 → x

// PatternMatch写法:
Value *X;
if (match(V, m_Add(m_Value(X), m_Zero())))  // 一行搞定!
  return X;
```

常用模式：

```c++
// 算术模式
m_Add(m_Value(X), m_Zero())        // X + 0
m_Mul(m_Value(X), m_One())         // X * 1
m_Sub(m_Value(X), m_Deferred(X))   // X - X

// 比较模式
m_ICmp(ICmpInst::ICMP_EQ, m_Value(X), m_Zero())  // X == 0

// 内存模式
m_Load(m_Value(X))                 // load X
m_Store(m_Value(X), m_Specific(Y)) // store X, Y

// 组合模式
m_Or(m_And(m_Value(A), m_Value(B)),   // (A & B) | (C & D)
     m_And(m_Value(C), m_Value(D)))

// 递归模式
m_Not(m_Value(X))  // ~X, 展开为 m_Xor(m_Value(X), m_AllOnes())
```

**数据库类比**：PatternMatch就像SQL中的模式匹配——`LIKE`和正则表达式让你描述"什么样的字符串"，PatternMatch让你描述"什么样的指令序列"。两者都是声明式的：你指定模式，引擎负责匹配。

---

## 2.6 本章小结

本章深入了LLVM IR的内部设计，建立了五个核心认知：

1. **Value/User/Use三元组**是def-use链的工程实现——双向链表+连续数组的组合，O(1)遍历和替换，是LLVM优化器高效运作的基石。

2. **类型系统的不可变+唯一化设计**——指针比较替代值比较，零额外内存的位宽编码，opaque pointer简化了类型不一致问题。

3. **常量和元数据**是编译期信息的载体——Constant层次编码了编译期已知值，Metadata体系附加了优化提示和调试信息，DebugInfo建立了源码到IR的映射。

4. **Module/Function/BasicBlock/Instruction四层容器**构成了IR的拓扑——Module提供全局视野，Function是核心单元，BasicBlock是控制流节点，Instruction是原子操作。DataLayout是体系结构信息注入优化器的关键接口。

5. **IRBuilder和PatternMatch**是构建和匹配IR的双面工具——IRBuilder负责创建(带常量折叠)，PatternMatch负责查询(声明式模式)，Verifier负责验证(8425行不变量检查)。

下一章我们将看到IR的三种物理表示——内存对象拓扑、文本汇编(.ll)、和紧凑位码(.bc)——以及如何用工具链在它们之间转换。
