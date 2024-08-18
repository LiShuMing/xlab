# 第14章 MLIR核心：可扩展编译基础设施

## 14.1 为什么需要MLIR？——LLVM IR的局限与突破

### 14.1.1 单层IR的表达力瓶颈

LLVM IR虽然强大，但存在根本性的表达力瓶颈：

```
LLVM IR的局限:

1. 抽象层次单一:
   LLVM IR接近汇编 → 无法表达高层语义(循环嵌套、张量运算)
   例: linalg.matmul在LLVM IR中变成3层嵌套循环+load/store → 语义丢失

2. 类型系统不足:
   LLVM IR只有基础类型+向量 → 无法表达tensor/memref/sparse
   例: tensor<1024x1024xf32>在LLVM IR中只是指针+元数据

3. 无领域抽象:
   AI编译需要算子融合、tiling、bufferization
   硬件综合需要时序、面积、功耗约束
   HPC需要多面体优化(仿射变换)
   → 这些抽象无法在LLVM IR层面表达

4. 转换路径不灵活:
   LLVM IR → MachineInstr 是固定的单一路径
   没有中间的"方言转换"机制
```

### 14.1.2 AI编译、硬件综合、HPC的差异化需求

```
不同领域需要的IR抽象:

AI编译:
  tensor → linalg → scf → affine → vector → llvm
  需要: 自动微分、算子融合、动态shape、量化

硬件综合(CIRCT):
  hw → comb → seq → fsm → llvm
  需要: 时序约束、时钟域、面积优化

HPC:
  affine → scf → llvm
  需要: 多面体变换、循环变换、数据布局优化

MLIR的解法:
  统一基础设施 + 可扩展方言(Dialect)
  不同领域定义自己的方言，通过方言转换互操作
```

---

## 14.2 核心数据结构：Operation / Dialect / Region / Block

### 14.2.1 Operation：MLIR的基本单元

**源码**：`mlir/lib/IR/Operation.cpp`（1435行）

Operation是MLIR的核心抽象——一切皆Operation：

```
Operation的内存布局:
┌─────────────────────────────────────────┐
│ Operation (固定部分, ~64字节)            │
│ ├── name: OperationName (Dialect+"."+Op) │
│ ├── operands: Value[] (输入)             │
│ ├── results: Value[] (输出)              │
│ ├── successors: Block*[] (后继块)       │
│ ├── regions: Region[] (嵌套区域)         │
│ ├── attributes: DictionaryAttr           │
│ ├── location: Location (源码位置)        │
│ └── block: Block* (所属基本块)           │
└─────────────────────────────────────────┘

示例: linalg.matmul
%result = linalg.matmul ins(%A, %B: tensor<128x256xf32>, tensor<256x512xf32>)
                        outs(%C: tensor<128x512xf32>) -> tensor<128x512xf32>

Operation {
  name: "linalg.matmul"
  operands: [%A, %B, %C]
  results: [%result]
  regions: [] (有些linalg op有region定义body)
  attributes: {}
}
```

与LLVM IR Instruction的关键区别：
- Operation可以有**多个结果**(Instruction只有一个Value)
- Operation可以有**嵌套Region**(Instruction是扁平的)
- Operation可以有**任意属性**(Instruction的属性是固定的)
- Operation的名称由**Dialect命名空间限定**

### 14.2.2 Dialect：可扩展命名空间

**源码**：`mlir/lib/IR/Dialect.cpp`（331行）

Dialect是Operation的类型命名空间，提供扩展机制：

```
Dialect注册:
  MLIRContext::getOrLoadDialect<arith::ArithDialect>()
  → 注册 "arith" 方言及其所有Operation/Type/Attribute

Dialect内容:
  arith: addf, mulf, addi, muli, cmpf, cmpi, select, ...
  func: func.func, func.call, func.return
  scf: scf.for, scf.if, scf.while, scf.yield
  linalg: linalg.matmul, linalg.conv, linalg.generic, ...
  affine: affine.for, affine.if, affine.load, affine.store
  gpu: gpu.launch, gpu.thread_id, gpu.barrier
  vector: vector.contract, vector.transfer_read/write
  memref: memref.alloc, memref.load, memref.store
  tensor: tensor.extract, tensor.insert, tensor.empty

扩展新Dialect:
  1. 定义.td文件(ODS: Operation Definition Specification)
  2. TableGen生成C++类
  3. 实现verify/fold/canonicalize方法
  4. 注册到MLIRContext
```

### 14.2.3 Region & Block：嵌套IR结构

**源码**：`mlir/lib/IR/Region.cpp`（299行）

Region是MLIR与LLVM IR最本质的区别——Operation可以包含嵌套的IR区域：

```
LLVM IR: 扁平结构
  define @foo {
    ...  ← 所有指令在同一层
  }

MLIR: 嵌套结构
  func.func @foo() {
    scf.for %i = 0 to %n {        ← Region 1: for循环体
      %val = arith.mulf %a, %b
      scf.if %cond {              ← Region 2: if的then分支
        ...
      } else {                    ← Region 3: if的else分支
        ...
      }
    }
  }

Region的结构:
  Region
  └── Block[] (基本块列表)
        ├── BlockArgument[] (块参数 ≈ PHI节点)
        └── Operation[] (操作列表)
            └── Region[] (可能嵌套更多Region!)

语义:
  Region定义了一个局部的SSA计算
  Block之间的控制流通过succ_operands传递值
  嵌套的Region可以引用外层的值(通过Value的use)
```

### 14.2.4 与LLVM IR Value/Instruction的对比映射

| MLIR概念 | LLVM IR对应 | 关键差异 |
|---------|------------|---------|
| Operation | Instruction | 多结果、可嵌套Region、有属性 |
| Value | Value | MLIR Value可以是OpResult或BlockArgument |
| Block | BasicBlock | Block可以有参数(BlockArgument) |
| Region | 无对应 | MLIR独有——嵌套IR结构 |
| Dialect | 无对应 | MLIR独有——可扩展命名空间 |
| Attribute | Metadata | MLIR Attribute是一等公民，类型化 |
| Type | Type | MLIR有tensor/memref等富类型 |

---

## 14.3 类型系统：从简单到富类型

### 14.3.1 tensor / memref / vector三种张量类型的语义差异

**源码**：`mlir/lib/IR/BuiltinTypes.cpp`（987行）

```
三种内存/计算类型:

tensor<128x256xf32>:
  - 语义: 抽象的数学张量, 无物理存储
  - 用途: 算子融合的输入/输出, bufferization前
  - 特点: 只读语义, 不可原地修改
  - 类比: 数据库中的逻辑表(只有schema, 没有物理存储)

memref<128x256xf32>:
  - 语义: 物理内存引用, 有具体存储布局
  - 用途: bufferization后的缓冲区, 可读写
  - 特点: 有stride/offset/alignment信息
  - 类比: 数据库中的物理表(有存储格式、索引、分区)

vector<4xf32>:
  - 语义: SIMD向量寄存器
  - 用途: 向量化后的计算
  - 特点: 固定宽度, 直接映射到硬件SIMD
  - 类比: 数据库中的向量化执行(batch of values)

三者的转换关系:
  tensor → (bufferization) → memref
  tensor → (vectorize) → vector
  memref → (vectorize) → vector
```

### 14.3.2 ShapedType层次与动态形状支持

```
ShapedType (有形状的类型)
├── TensorType
│   ├── RankedTensorType: tensor<128x256xf32>  (静态形状)
│   └── UnrankedTensorType: tensor<*xf32>      (动态形状)
│
├── MemRefType
│   ├── MemRefType: memref<128x256xf32, strided<[256, 1]>>
│   └── UnrankedMemRefType: memref<*xf32>
│
└── VectorType
    ├── VectorType: vector<4xf32>               (固定宽度)
    └── ScalableVectorType: vector<[4]xf32>     (可伸缩)

动态形状:
  tensor<?x?xf32>  → 第1和第2维度在运行时确定
  tensor<?x256xf32> → 只有第1维度是动态的

  编译期: 不知道具体大小, 但知道类型和秩
  运行时: 通过shape操作获取维度值

  这是AI编译的核心挑战——LLM的sequence length就是动态维度!
```

---

## 14.4 Attribute与Properties

### 14.4.1 编译期元数据的表达与传递

MLIR的Attribute系统比LLVM的Metadata更强大——Attribute是一等公民，有类型，可以参与模式匹配：

```
Attribute层次:
  Attribute (基类)
  ├── IntegerAttr: 42 : i32
  ├── FloatAttr: 3.14 : f32
  ├── StringAttr: "hello"
  ├── ArrayAttr: [1, 2, 3]
  ├── DictionaryAttr: {key = "value"}
  ├── TypeAttr: i32
  ├── SymbolRefAttr: @foo
  ├── DenseElementsAttr: dense<1.0> : tensor<4xf32>  (张量常量!)
  └── 自定义Attribute (由Dialect定义)

Operation的Attribute:
  %0 = arith.addi %a, %b {overflow = "nsw"} : i32
                                    ↑ Attribute

  linalg.matmul {lowering_config = ...}  ← 附加优化配置
  gpu.launch {block_size = [32, 1, 1]}   ← 附加GPU配置

Properties (新机制, 替代部分Attribute):
  更严格的类型约束
  更高效的内存布局
  不参与DictionaryAttr的遍历
```

---

## 14.5 本章小结

本章建立了MLIR核心的核心理解：

1. **为什么需要MLIR**——LLVM IR的抽象层次单一，无法满足AI编译、硬件综合、HPC的差异化需求。
2. **Operation/Dialect/Region/Block**——Operation是一等公民，Dialect是可扩展命名空间，Region实现嵌套IR结构。
3. **类型系统**——tensor(抽象张量)/memref(物理内存)/vector(SIMD寄存器)三种语义，ShapedType支持动态形状。
4. **Attribute与Properties**——编译期元数据的一等表达，支持类型化和模式匹配。

下一章深入Dialect生态——从核心方言到Linalg优化流水线。
