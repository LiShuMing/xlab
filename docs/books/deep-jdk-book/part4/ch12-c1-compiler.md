# 第 12 章 C1 编译器：客户端即时编译

> 源码路径：`src/hotspot/share/c1/`、`src/hotspot/cpu/x86/c1_*`

C1（Client Compiler）是 HotSpot 的轻量级 JIT 编译器，设计目标是快速编译和合理的代码质量。在分层编译中，C1 负责层级 1-3 的编译，为热点方法提供比解释器快 5-10 倍的执行速度，同时为 C2 争取编译时间。本章从 C1 的编译流水线入手，逐步剖析其 HIR、LIR、优化和寄存器分配。

---

## 12.1 `c1/` 目录全景与编译流水线

### 12.1.1 C1 目录结构

```
c1/
├── c1_Compilation.cpp/hpp        # 编译会话管理
├── c1_Compiler.cpp/hpp           # 编译器入口
├── c1_GraphBuilder.cpp/hpp       # 字节码 → HIR 构建
├── c1_Instruction.cpp/hpp        # HIR 指令定义
├── c1_Optimizer.cpp/hpp          # 优化器
├── c1_ValueMap.cpp/hpp           # 值编号
├── c1_ValueStack.cpp/hpp         # 值栈（模拟操作数栈）
├── c1_LIRGenerator.cpp/hpp       # HIR → LIR
├── c1_LIR.cpp/hpp                # LIR 定义
├── c1_LinearScan.cpp/hpp         # 线性扫描寄存器分配
├── c1_CodeStubs.cpp/hpp          # 代码桩
├── c1_FrameMap.cpp/hpp           # 栈帧映射
├── c1_Runtime1.cpp/hpp           # 运行时辅助
└── c1_RangeCheckElimination.cpp  # 范围检查消除
```

### 12.1.2 C1 编译流水线

```
字节码
  │
  ▼
┌──────────────────┐
│  GraphBuilder    │  字节码 → HIR（高级中间表示）
└──────────────────┘
  │
  ▼
┌──────────────────┐
│  Optimizer       │  值编号、常量折叠、全局值编号
└──────────────────┘
  │
  ▼
┌──────────────────┐
│  LIRGenerator    │  HIR → LIR（低级中间表示）
└──────────────────┘
  │
  ▼
┌──────────────────┐
│  LinearScan      │  线性扫描寄存器分配
└──────────────────┘
  │
  ▼
┌──────────────────┐
│  Code Emission   │  LIR → 机器码
└──────────────────┘
```

---

## 12.2 `c1_GraphBuilder`：字节码到 HIR 的构建

### 12.2.1 HIR（High-level Intermediate Representation）

C1 的 HIR 是一种基于 SSA（Static Single Assignment）的图结构：

```cpp
// c1_Instruction.hpp
class Instruction: public CompilationResourceObj {
    int         _id;            // 指令 ID
    ValueType*  _type;          // 类型
    Instruction* _next;         // 指令链
    Instruction* _prev;
    int         _use_count;     // 使用计数
    bool        _can_trap;      // 是否可能抛异常
};

// HIR 指令类型
class Invoke;          // 方法调用
class ArithmeticOp;    // 算术运算
class IfOp;            // 条件判断
class StoreField;      // 字段存储
class LoadField;       // 字段加载
class NewInstance;     // 新建对象
class NewArray;        // 新建数组
class ExceptionObject; // 异常对象
```

### 12.2.2 GraphBuilder 的字节码遍历

`GraphBuilder` 逐条遍历字节码，构建 HIR：

```cpp
// c1_GraphBuilder.cpp（简化）
void GraphBuilder::iterate_bytecodes_for_block(BlockBegin* block) {
    while (!_method_data->is_within_block()) {
        switch (cur_bc()) {
        case Bytecodes::_iadd:
            // 从值栈弹出两个操作数，创建 ArithmeticOp
            { Value y = ipop(); Value x = ipop();
              push(append(new ArithmeticOp(Bytecodes::_iadd, x, y, false))); }
            break;
        case Bytecodes::_iload:
            { int index = get_index(); push(load_local(intType, index)); }
            break;
        case Bytecodes::_invokevirtual:
            { invoke(); }
            break;
        // ...
        }
    }
}
```

`GraphBuilder` 维护一个 `ValueStack`（模拟字节码操作数栈），HIR 指令的操作数从 `ValueStack` 弹出，结果压回 `ValueStack`。

### 12.2.3 控制流图的构建

对于分支和循环，`GraphBuilder` 构建 `BlockBegin / BlockEnd` 结构：

```
HIR 控制流图：
BlockBegin [0]
  ├── iadd
  ├── if_icmplt → BlockBegin [1]  (true)
  └── goto → BlockBegin [2]       (false)

BlockBegin [1]
  ├── ...
  └── goto → BlockBegin [3]

BlockBegin [2]
  ├── ...
  └── goto → BlockBegin [3]

BlockBegin [3]
  └── return
```

异常处理通过 `ExceptionHandler` 节点表示，每个可能抛异常的指令都关联了异常处理器块。

---

## 12.3 `c1_Instruction`：HIR 指令体系

### 12.3.1 指令分类

| 类别 | 指令 | 说明 |
|------|------|------|
| 常量 | `Constant` | 整数、浮点、null、对象 |
| 算术 | `ArithmeticOp` | 加减乘除、移位、位运算 |
| 转换 | `ConvertOp` | int↔long、int↔float 等 |
| 比较 | `CompareOp` | 整数/浮点比较 |
| 条件 | `IfOp` | 三元条件表达式 |
| 加载 | `LoadLocal / LoadField / LoadIndexed` | 局部变量/字段/数组 |
| 存储 | `StoreLocal / StoreField / StoreIndexed` | 对应的存储操作 |
| 调用 | `Invoke` | virtual/static/special/interface/dynamic |
| 对象 | `NewInstance / NewArray / NewMultiArray` | 对象/数组分配 |
| 类型 | `CheckCast / InstanceOf` | 类型检查 |
| 监视器 | `MonitorEnter / MonitorExit` | 同步操作 |
| 基块 | `BlockBegin / BlockEnd / If / Goto` | 控制流 |

### 12.3.2 Invoke 指令与内联

`Invoke` 是 HIR 中最复杂的指令，因为它涉及内联决策：

```cpp
// c1_GraphBuilder.cpp
void GraphBuilder::invoke(Bytecodes::Code code) {
    // 1. 解析方法引用
    Method* target = method_resolve(...);

    // 2. 内联决策
    if (should_inline(target)) {
        // 内联：将目标方法的字节码也遍历，合并到当前 HIR
        inline_target(target);
    } else {
        // 不内联：生成 Invoke 指令
        append(new Invoke(code, target, args));
    }
}
```

C1 的内联策略比 C2 保守——主要内联小方法（getter/setter）和编译器已知的目标（static/final 方法）。

---

## 12.4 `c1_Optimizer`：值编号、常量折叠、全局值编号

### 12.4.1 局部值编号（Local Value Numbering）

C1 在 `GraphBuilder` 阶段就执行局部值编号：

```cpp
// c1_ValueMap.cpp
class ValueMap {
    // 哈希表：值 → 已有的指令
    ValueMapEntry* _entries[default_size];

    // 查找等价值
    Value find_insert(Value x) {
        int hash = x->hash();
        ValueMapEntry* entry = _entries[hash % size];
        while (entry) {
            if (entry->value()->is_equal(x)) {
                return entry->value();  // 找到等价值，返回已有指令
            }
            entry = entry->next();
        }
        // 未找到，插入
        insert(hash, x);
        return x;
    }
};
```

示例：

```
原始代码：
  a = x + y
  b = x + y     // 与 a 完全相同
  c = a + b

值编号后：
  a = x + y
  b = a          // 复用 a 的结果
  c = a + a      // 替换 b → a
```

### 12.4.2 常量折叠

在值编号过程中，如果操作数是常量，直接计算结果：

```cpp
// c1_GraphBuilder.cpp
Value x = ipop();
Value y = ipop();
if (x->is_constant() && y->is_constant()) {
    int result = x->as_constant()->as_int() + y->as_constant()->as_int();
    push(new Constant(intType, result));  // 编译期计算
} else {
    push(new ArithmeticOp(Bytecodes::_iadd, x, y, false));
}
```

### 12.4.3 全局值编号（GVN）

C1 的 GVN 在 `Optimizer` 阶段执行，跨基本块进行值编号。它使用 `ValueMap` 的快照在每个基本块入口处恢复已知值，实现跨块的冗余消除。

GVN 的效果受限于 C1 的方法大小限制——C1 的编译上限比 C2 小，因此 GVN 的跨块优化范围有限。

---

## 12.5 `c1_LIRGenerator`：HIR 到 LIR 的 lowering

### 12.5.1 LIR（Low-level Intermediate Representation）

LIR 是 C1 的低级中间表示，更接近机器码：

```cpp
// c1_LIR.hpp
class LIR_Op {
    // LIR 操作基类
};

class LIR_Op1: public LIR_Op {
    // 一元操作：移动、转换、返回
    LIR_Opr _opr;     // 操作数
};

class LIR_Op2: public LIR_Op {
    // 二元操作：算术、逻辑、比较
    LIR_Opr _opr1;    // 操作数 1
    LIR_Opr _opr2;    // 操作数 2
    LIR_Opr _result;  // 结果
};
```

### 12.5.2 Lowering 过程

HIR 到 LIR 的 lowering 将高级操作逐步降低为具体的机器操作：

```
HIR:  x + y (ArithmeticOp)
  │
  ▼ lowering
LIR:  mov rax, [rbp + offset_x]     // 加载 x
      add rax, [rbp + offset_y]     // 加载 y 并加
      mov [rbp + offset_result], rax // 存储结果
```

### 12.5.3 LIR 操作数

```cpp
// c1_LIR.hpp
class LIR_Opr {
    // 操作数类型
    enum OprType {
        unknown_type,    // 未确定
        int_type,        // 整数
        long_type,       // 长整数
        float_type,      // 浮点
        double_type,     // 双精度
        object_type,     // 对象引用
        address_type,    // 地址
    };

    // 操作数位置
    // - 寄存器：rax, rbx, ...
    // - 栈槽：[rbp - 16], ...
    // - 常量：42, 3.14, null
};
```

---

## 12.6 `c1_LinearScan`：线性扫描寄存器分配

### 12.6.1 线性扫描算法

C1 使用线性扫描（Linear Scan）寄存器分配，而非 C2 的图着色算法。线性扫描更简单、编译更快，但分配质量略低：

```
1. 计算每个虚拟寄存器的生命周期区间（Live Interval）
   v1: [0, 5]     // 从指令 0 活跃到指令 5
   v2: [2, 8]
   v3: [4, 10]
   v4: [6, 12]

2. 按起始位置排序，线性扫描
   扫描位置 0：分配 v1 → rax
   扫描位置 2：分配 v2 → rbx
   扫描位置 4：v1 还活跃，分配 v3 → rcx
   扫描位置 5：v1 结束，释放 rax
   扫描位置 6：分配 v4 → rax（复用）

3. 当寄存器不够时，溢出（Spill）到栈
```

### 12.6.2 生命周期区间

```cpp
// c1_LinearScan.hpp
class Interval {
    int           _reg_num;       // 虚拟寄存器号
    LIR_Opr       _assigned_reg;  // 分配的物理寄存器
    List<Range*>  _ranges;        // 生命周期范围列表
    int           _spill_slot;    // 溢出槽位
};

class Range {
    int _from;    // 起始位置
    int _to;      // 结束位置
};
```

### 12.6.3 溢出策略

当没有空闲寄存器时，线性扫描需要选择一个活跃区间溢出到栈。选择策略：

1. **最少使用（Least Frequently Used）**：溢出使用次数最少的区间
2. **最远下次使用（Furthest Next Use）**：溢出下次使用最远的区间
3. **优先溢出较长的区间**：短区间可能在溢出前就结束

C1 使用一种基于优先级的策略——调用点和分支目标处的区间优先保留在寄存器中。

---

## 12.7 `c1_RangeCheckElimination`：范围检查消除

### 12.7.1 数组边界检查的消除

Java 的数组访问要求边界检查（`0 <= index < length`），但很多情况下检查是冗余的：

```java
for (int i = 0; i < arr.length; i++) {
    arr[i] = i;  // 边界检查冗余——循环条件已保证 i < arr.length
}
```

C1 的范围检查消除分析循环的条件，如果可以证明索引在合法范围内，就消除边界检查：

```cpp
// c1_RangeCheckElimination.cpp
// 分析循环变量与数组长度的关系
// 如果 index >= lower_bound && index < upper_bound，且 upper_bound <= array.length
// 则消除边界检查
```

C1 的范围检查消除比 C2 简单——它只处理基本的循环模式，不进行复杂的约束传播。

---

## 12.8 [体系结构视角] C1 生成的代码质量与流水线效率

### 12.8.1 C1 vs C2 代码质量对比

```
典型方法（循环累加）：

解释器：~10ns/iter
C1 代码：
  mov rax, [rbp + offset_sum]     // 从栈加载 sum
  add rax, [rbx + rdi*4 + 16]    // 加载数组元素并加
  mov [rbp + offset_sum], rax     // 存储回栈
  ~3ns/iter

C2 代码：
  add r8d, dword [rbx + rdi*4 + 16]  // 寄存器中的 sum
  ~1ns/iter
```

C1 代码比 C2 慢的主要原因：
1. **寄存器分配差**：线性扫描比图着色效果差，更多变量溢出到栈
2. **无循环优化**：不进行循环展开、强度削减
3. **无逃逸分析**：无法消除堆分配和锁
4. **无向量化**：不生成 SIMD 指令

### 12.8.2 C1 的编译速度优势

```
编译一个典型方法：
C1：~5-20ms
C2：~50-500ms

编译速度差距：10-25 倍
```

C1 的快速编译使分层编译成为可能——热点方法先用 C1 编译快速获得性能提升，等真正极热时再用 C2 重编译获得最高性能。

### 12.8.3 C1 在分层编译中的角色

```
方法调用次数：
  0 ──── 解释执行
  │
  Tier 3 阈值（~2500次）──── C1 编译（带 Profiling）
  │                            - 收集类型反馈
  │                            - 收集分支频率
  │
  Tier 4 阈值（~15000次）─── C2 编译
                               - 使用 C1 收集的 Profiling 数据
                               - 最高优化级别
```

C1 Tier 3 编译的代码携带性能采集指令，为 C2 提供精确的类型和分支信息——这是分层编译的核心价值。

---

## 小结

本章剖析了 C1 编译器的完整流水线：

1. **GraphBuilder** 将字节码构建为 SSA 形式的 HIR
2. **Optimizer** 执行值编号和常量折叠，消除冗余计算
3. **LIRGenerator** 将 HIR 降低为接近机器的 LIR
4. **LinearScan** 使用线性扫描算法分配寄存器，快速但质量有限
5. **RangeCheckElimination** 消除冗余的数组边界检查
6. **分层编译中**，C1 是 C2 的「侦察兵」，快速编译并提供 Profiling 数据

下一章将深入 C2——HotSpot 最强大的 JIT 编译器。
