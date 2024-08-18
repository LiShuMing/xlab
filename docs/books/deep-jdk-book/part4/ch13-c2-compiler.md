# 第 13 章 C2 编译器：服务端即时编译

> 源码路径：`src/hotspot/share/opto/`、`src/hotspot/share/ad/`、`src/hotspot/cpu/x86/`

C2（Server Compiler）是 HotSpot 的重型 JIT 编译器，代表了 JVM 优化的最高水平。它使用 Sea of Nodes 中间表示，执行激进的逃逸分析、循环优化、自动向量化和图着色寄存器分配。一个经过 C2 充分优化的方法，其性能可以接近甚至达到手写 C 代码的水平。本章深入 C2 的编译流水线。

---

## 13.1 `opto/` 目录全景与 C2 编译流水线

### 13.1.1 C2 目录结构

```
opto/
├── compile.cpp/hpp              # 编译会话
├── parse1.cpp / parse2.cpp / parse3.cpp  # 字节码解析
├── node.cpp/hpp                 # Node 基类
├── addnode.cpp/hpp              # 算术节点
├── connode.cpp/hpp              # 常量节点
├── memnode.cpp/hpp              # 内存节点
├── cfgnode.cpp/hpp              # 控制流节点
├── loopnode.cpp/hpp             # 循环节点
├── loopTransform.cpp            # 循环变换
├── loopUnswitch.cpp             # 循环开关
├── escape.cpp/hpp               # 逃逸分析
├── chaitin.cpp/hpp              # 图着色寄存器分配
├── superword.cpp/hpp            # 自动向量化
├── vectorIntrinsics.cpp         # 向量内联
├── idealKit.cpp/hpp             # Ideal Graph 辅助
├── idealGraphPrinter.cpp/hpp    # Ideal Graph 可视化
├── output.cpp/hpp               # 代码输出
├── matcher.cpp/hpp              # 指令选择
├── regalloc.cpp/hpp             # 寄存器分配
├── regmask.cpp/hpp              # 寄存器掩码
├── coalesce.cpp/hpp             # 寄存器合并
├── live.cpp/hpp                 # 活跃分析
├── block.cpp/hpp                # 基本块
├── mulnode.cpp/hpp              # 乘法节点
├── divnode.cpp/hpp              # 除法节点
├── callnode.cpp/hpp             # 调用节点
├── type.cpp/hpp                 # 类型系统
└── phaseX.cpp/hpp               # 编译阶段管理
```

### 13.1.2 C2 编译流水线

```
字节码 + MethodData（类型反馈）
  │
  ▼
┌───────────────────┐
│  Parse (parse123) │  字节码 → Ideal Graph（Sea of Nodes）
└───────────────────┘
  │
  ▼
┌───────────────────┐
│  Iterative GVN    │  全局值编号 + 死代码消除
└───────────────────┘
  │
  ▼
┌───────────────────┐
│  Escape Analysis  │  逃逸分析 → 标量替换 + 锁消除
└───────────────────┘
  │
  ▼
┌───────────────────┐
│  Loop Optimizer   │  循环展开、强度削减、循环开关、向量化
└───────────────────┘
  │
  ▼
┌───────────────────┐
│  Matcher          │  指令选择（AD 文件描述的 BURG 匹配）
└───────────────────┘
  │
  ▼
┌───────────────────┐
│  Register Alloc   │  图着色寄存器分配（Chaitin-Briggs）
└───────────────────┘
  │
  ▼
┌───────────────────┐
│  Code Emission    │  生成机器码 + oop_map + 异常表
└───────────────────┘
```

---

## 13.2 `parse1/2/3`：字节码解析与 Ideal Graph 构建

### 13.2.1 Sea of Nodes

C2 使用「Sea of Nodes」表示——所有操作（包括内存操作和控制流）都是图中的节点，没有基本块的概念（直到后期调度阶段）：

```cpp
// node.hpp
class Node {
    uint          _cnt;        // 输入边计数
    Node*         _in[1];      // 输入边数组（变长）
    Node_List     _out;        // 输出边列表
    int           _idx;        // 节点唯一 ID
    const Type*   _type;       // 类型信息
    uint          _opcode;     // 操作码
};
```

### 13.2.2 节点类型与图结构

```
控制流节点：        数据节点：          内存节点：
  Start               ConI(42)            MergeMem
  If                  AddI                LoadI
  Region              SubI                StoreI
  Proj               MulI                MemBar
  Return             CastII              LoadRange
  Rethrow            CmpI                LoadKlass
  CallJava           Phi                 StoreP
```

Sea of Nodes 的一个独特设计：**内存也是图中的节点**。每个内存操作通过内存边（memory edge）连接，形成内存状态链：

```
Start
  │
  ├── memory edge ──→ LoadI[field1] ──→ LoadI[field2] ──→ StoreI[field3] ──→ Return
  │                    ↑                   ↑                  ↑
  └── control edge ────┴───────────────────┴──────────────────┘
```

这种表示让 C2 可以精确推理内存依赖——如果两个内存操作没有依赖关系，就可以重排。

### 13.2.3 Parse 的过程

```cpp
// parse1.cpp
void Parse::do_parse() {
    // 遍历字节码，构建 Ideal Graph
    while (_bc >= 0) {
        switch (_bc) {
        case Bytecodes::_iadd: {
            Node* b = pop();
            Node* a = pop();
            push(_gvn.transform(new AddINode(a, b)));
            break;
        }
        case Bytecodes::_invokevirtual: {
            do_call();
            break;
        }
        // ...
        }
        next_bytecode();
    }
}
```

`_gvn.transform()` 在构建节点时就执行全局值编号——如果图中已存在等价节点，直接复用。

---

## 13.3 Node 体系（`node.hpp / addnode / memnode / connode` 等）

### 13.3.1 核心节点类型

**算术节点**（`addnode.hpp`）：

```cpp
class AddINode : public AddNode { /* int 加法 */ };
class AddLNode : public AddNode { /* long 加法 */ };
class AddFNode : public AddNode { /* float 加法 */ };
class AddDNode : public AddNode { /* double 加法 */ };
```

**内存节点**（`memnode.hpp`）：

```cpp
class LoadINode   : public LoadNode { /* 加载 int 字段 */ };
class StoreINode  : public StoreNode { /* 存储 int 字段 */ };
class LoadRangeNode : public LoadNode { /* 加载数组长度 */ };
class LoadKlassNode : public LoadNode { /* 加载类指针 */ };
```

**控制流节点**（`cfgnode.hpp`）：

```cpp
class IfNode     : public Node { /* 条件分支 */ };
class RegionNode : public Node { /* 控制流汇合 */ };
class PhiNode    : public Node { /* SSA φ 节点 */ };
class ProjNode   : public Node { /* 分支投影 */ };
```

### 13.3.2 节点的理想化（Ideal 化）

C2 的优化核心是「Ideal 化」——每个节点可以定义 `ideal()` 方法，返回优化后的等价子图：

```cpp
// addnode.cpp
Node* AddINode::ideal(PhaseIterGVN* phase) {
    // (x + 0) → x
    if (in(2)->is_Con() && in(2)->get_int() == 0) {
        return in(1);
    }
    // (x + c1) + c2 → x + (c1 + c2)
    if (in(1)->is_AddI() && in(1)->in(2)->is_Con()) {
        int c1 = in(1)->in(2)->get_int();
        int c2 = in(2)->get_int();
        return new AddINode(in(1)->in(1), phase->intcon(c1 + c2));
    }
    return nullptr;  // 无优化
}
```

`PhaseIterGVN` 反复调用每个节点的 `ideal()` 直到图不再变化——这是一个不动点迭代过程。

---

## 13.4 `loopnode / loopTransform / loopUnswitch`：循环优化全景

### 13.4.1 循环识别

C2 在 Ideal Graph 上识别自然循环：

```cpp
// loopnode.cpp
void PhaseIdealLoop::build_loop_tree() {
    // 1. 识别回边（back edge）：如果节点 N 的控制流到达了支配 N 的节点 H
    //    则 N → H 构成回边，H 是循环头
    // 2. 计算循环体：从回边到循环头的所有节点
    // 3. 构建循环嵌套树
}
```

### 13.4.2 循环优化列表

| 优化 | 实现 | 效果 |
|------|------|------|
| 循环展开（Loop Unrolling） | `loopTransform.cpp` | 减少循环控制开销 |
| 强度削减（Strength Reduction） | `loopTransform.cpp` | 乘法 → 加法 |
| 循环不变量外提（LICM） | `loopTransform.cpp` | 将不变计算移出循环 |
| 循环开关（Loop Unswitching） | `loopUnswitch.cpp` | 将循环内条件提到循环外 |
| 循环剥离（Loop Peeling） | `loopTransform.cpp` | 剥离首次迭代 |
| 部分冗余消除（PRE） | `loopTransform.cpp` | 消除部分冗余计算 |
| 内循环提取 | `loopTransform.cpp` | 嵌套循环优化 |

### 13.4.3 循环展开示例

```
原始循环：
  for (int i = 0; i < n; i++) {
      sum += arr[i];
  }

展开 4 倍后：
  for (int i = 0; i < n; i += 4) {
      sum += arr[i];
      sum += arr[i+1];
      sum += arr[i+2];
      sum += arr[i+3];
  }
  // 处理尾部剩余元素
```

循环展开减少了循环条件的判断次数和分支预测压力，同时为后续的指令调度和向量化创造了条件。

---

## 13.5 `escape.cpp`：逃逸分析与标量替换

### 13.5.1 逃逸分析

逃逸分析判断对象是否「逃逸」出方法或线程：

```
逃逸级别：
  NoEscape：     对象不逃逸，可标量替换
  ArgEscape：    对象作为参数传递，不逃逸到堆
  GlobalEscape： 对象逃逸到堆或静态字段
```

### 13.5.2 标量替换

如果对象不逃逸（`NoEscape`），C2 可以将对象分解为标量值：

```
原始代码：
  Point p = new Point(x, y);
  return p.x + p.y;

标量替换后：
  int p_x = x;    // 不分配 Point 对象
  int p_y = y;
  return p_x + p_y;
```

标量替换消除了堆分配和 GC 压力——对象的所有字段变为寄存器/栈变量。

### 13.5.3 锁消除

如果同步对象不逃逸出线程，`synchronized` 块可以消除：

```java
// 原始代码
synchronized (new Object()) {   // Object 不逃逸
    // ... 临界区 ...
}

// 锁消除后
{
    // ... 临界区 ...（无锁操作）
}
```

---

## 13.6 `chaitin.cpp`：图着色寄存器分配

### 13.6.1 Chaitin-Briggs 算法

C2 使用经典的 Chaitin-Briggs 图着色寄存器分配算法：

```
1. 构建干涉图（Interference Graph）
   如果两个虚拟寄存器在同一时刻活跃，则它们干涉

2. 简化（Simplify）
   找到度数 < K 的节点（K = 物理寄存器数量），压栈

3. 溢出（Spill）
   如果所有节点度数 >= K，选择一个节点标记为溢出

4. 选择（Select）
   从栈中弹出节点，为其分配颜色（物理寄存器）

5. 重写（Rewrite）
   为溢出节点插入加载/存储指令

6. 重复直到无需溢出
```

### 13.6.2 干涉图

```cpp
// chaitin.cpp
class PhaseChaitin {
    // 干涉矩阵：如果 _ifg[x][y] = true，则 x 和 y 干涉
    IndexSet* _ifg;

    // 活跃分析结果
    LRG_List _lrgs;   // Live Range 列表
};
```

### 13.6.3 寄存器合并（Coalescing）

C2 在图着色过程中执行寄存器合并——如果两个虚拟寄存器之间有复制关系（`move src → dst`）且不干涉，可以将它们分配到同一个物理寄存器，消除复制指令。

---

## 13.7 `superword / vectorIntrinsics`：自动向量化

### 13.7.1 Superword 自动向量化

C2 的 Superword 优化器检测循环中的标量操作，将它们打包为 SIMD 向量操作：

```
原始循环：
  for (int i = 0; i < n; i++) {
      c[i] = a[i] + b[i];  // 标量加法
  }

向量化后（AVX2，256 位 = 8 个 int）：
  for (int i = 0; i < n; i += 8) {
      vadd_8i(c+i, a+i, b+i);  // 一条 vpaddd 指令加 8 个 int
  }
```

Superword 的实现步骤：

1. **分析依赖**：识别循环中的独立操作链
2. **打包（Pack）**：将相邻的标量操作打包为向量操作
3. **调度（Schedule）**：安排向量操作的执行顺序
4. **生成代码**：使用 AD 文件中的向量指令描述生成机器码

### 13.7.2 Vector Intrinsics

对于 `java.util.Arrays` 中的常见操作和 Vector API 调用，C2 直接内联为向量指令：

```cpp
// vectorIntrinsics.cpp
// Arrays.equals(byte[], byte[]) → 向量化比较
// Arrays.fill(int[], int)       → 向量化填充
// Vector API binaryOp           → 对应的 SIMD 指令
```

---

## 13.8 `idealKit / idealGraphPrinter`：Ideal Graph 可视化与调试

### 13.8.1 Ideal Graph 可视化

C2 支持将编译过程的 Ideal Graph 导出为可视化格式：

```
启用方式：
-XX:+PrintIdealGraphLevel=1
-XX:PrintIdealGraphFile=output.xml

或使用 Ideal Graph Visualizer (IGV) 工具：
-XX:+PrintIdealGraph
```

IGV 可以显示每个编译阶段后的图状态，帮助理解优化过程。

### 13.8.2 IdealKit

`IdealKit` 是 C2 内部用于构建复杂 Ideal Graph 的辅助工具类，主要用于实现同步操作和内存屏障的图模式：

```cpp
// idealKit.cpp
// 提供 high-level 的图构建接口
// 例如：构建 if-then-else 模式
//   if_then(condition, prob, cnt)
//     then_body
//   else_
//     else_body
//   end_if
```

---

## 13.9 [专题] Vector API（`jdk.incubator.vector`）与 C2 向量化的协同

### 13.9.1 Vector API 的层次

```
Java 层：  FloatVector.fromArray(species, arr, offset)
           .add(otherVector)
           .intoArray(result, offset);

C2 内联：  识别 Vector API 调用 → 生成对应 SIMD 指令

关键：species 决定向量宽度
  FloatVector.SPECIES_64  → 2 floats  → SSE
  FloatVector.SPECIES_128 → 4 floats  → SSE/AVX
  FloatVector.SPECIES_256 → 8 floats  → AVX2
  FloatVector.SPECIES_512 → 16 floats → AVX-512
```

### 13.9.2 Vector API vs Superword

| 特性 | Vector API | Superword |
|------|-----------|-----------|
| 用户控制 | 显式指定向量操作 | 编译器自动检测 |
| 可靠性 | 确定性的向量化 | 依赖编译器分析 |
| 可移植性 | 跨架构自适应 | 跨架构自适应 |
| 调试难度 | 较低（用户代码明确） | 较高（隐式转换） |

---

## 13.10 [体系结构视角] SIMD 指令选择与 CPU 微架构的耦合

### 13.10.1 SIMD 指令集的演进

| 指令集 | 向量宽度 | 寄存器 | JDK 支持 |
|--------|---------|--------|---------|
| SSE2 | 128 位 | XMM0-15 | 基本向量化 |
| AVX | 256 位 | YMM0-15 | Superword + Vector API |
| AVX2 | 256 位 | YMM0-15 | 整数向量化 |
| AVX-512 | 512 位 | ZMM0-31 | JDK 27 完整支持 |
| NEON (AArch64) | 128 位 | V0-31 | 移动端向量化 |

### 13.10.2 AVX-512 的降频问题

AVX-512 指令的高功耗导致 Intel CPU 在使用 ZMM 寄存器时降低频率：

```
典型降频（Intel Sapphire Rapids）：
  不使用 AVX-512：  全核 3.5 GHz
  使用 AVX-512：   全核 2.8 GHz（降低 20%）

净效果取决于向量宽度 vs 频率降低的权衡：
  - 计算密集型：AVX-512 净收益 30-50%
  - 访存密集型：AVX-512 净收益可能为负
```

C2 在 AVX-512 的使用上较为谨慎——只有当收益明显时才使用 ZMM 寄存器。

### 13.10.3 向量化在 AI 推理中的价值

```
LLM 推理的向量操作：
1. Token Embedding 查找：gather 操作
2. 注意力分数计算：向量点积 + softmax
3. KV Cache 访问：连续内存读取

Java Vector API 实现：
FloatVector dot = FloatVector.zero(SPECIES_256);
for (int i = 0; i < len; i += SPECIES_256.length()) {
    FloatVector a = FloatVector.fromArray(SPECIES_256, arr1, i);
    FloatVector b = FloatVector.fromArray(SPECIES_256, arr2, i);
    dot = a.fma(b, dot);  // 融合乘加
}
```

---

## 小结

本章深入了 C2 编译器的核心机制：

1. **Sea of Nodes** 表示将控制流、数据流和内存依赖统一为图
2. **Ideal 化** 通过不动点迭代逐步优化图
3. **循环优化** 包括展开、强度削减、LICM、开关等
4. **逃逸分析** 实现标量替换和锁消除，消除堆分配
5. **图着色** 寄存器分配是 C2 高质量代码的关键
6. **自动向量化**（Superword）和 Vector API 提供 SIMD 计算能力
7. **AVX-512 的降频问题** 提醒我们：更宽的向量不一定更快

下一章将介绍 JVMCI——让外部编译器（如 Graal）接入 HotSpot 的接口。
