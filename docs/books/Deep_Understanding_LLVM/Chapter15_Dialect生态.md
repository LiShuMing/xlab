# 第15章 Dialect生态：从高层语义到低层代码

## 15.1 核心Dialect详解

### 15.1.1 Arith / Func / SCF / CF：基础设施方言

```
Arith方言: 基础算术运算
  arith.addi %a, %b : i32         ; 整数加法
  arith.addf %a, %b : f32         ; 浮点加法
  arith.muli, arith.mulf           ; 乘法
  arith.cmpi eq, %a, %b : i1      ; 整数比较
  arith.cmpf oeq, %a, %b : i1     ; 浮点比较
  arith.select %cond, %a, %b : i32 ; 条件选择
  arith.extsi %a : i32 to i64     ; 符号扩展
  arith.trunci %a : i64 to i32    ; 截断

  定位: 类似LLVM IR的Binary/Compare/Cast指令
  特点: 纯计算, 无副作用, 最容易优化的方言

Func方言: 函数定义和调用
  func.func @main(%arg0: i32) -> i32 {
    %result = func.call @helper(%arg0) : (i32) -> i32
    func.return %result : i32
  }

  定位: 类似LLVM IR的Function + Call指令
  特点: 支持嵌套函数、函数属性

SCF方言: 结构化控制流(Structured Control Flow)
  scf.for %i = %lb to %ub step %step {
    ...循环体...
  }

  scf.if %cond {
    ...then分支...
  } else {
    ...else分支...
  }

  scf.while(%arg = %init) : (i32) -> (i32) {
    %cond = arith.cmpi slt, %arg, %n : i1
    scf.condition(%cond) %arg : i32
  } do {
  ^bb0(%arg: i32):
    %next = arith.addi %arg, %c1 : i32
    scf.yield %next : i32
  }

  定位: 结构化控制流(无goto!), 比CF更容易分析和变换
  特点: 循环/条件有明确的Region结构, 适合多面体分析

CF方言: 非结构化控制流(Control Flow)
  cf.br ^bb1                       ; 无条件跳转
  cf.cond_br %cond, ^bb1(%val), ^bb2 ; 条件跳转
  cf.switch %val, ^default, [0, ^bb0], [1, ^bb1]

  定位: 类似LLVM IR的br/condbr, 非结构化
  特点: Lowering的最终形态(从SCF→CF→LLVM)
```

### 15.1.2 MemRef / Tensor：内存与张量

```
MemRef方言: 物理内存操作
  %buf = memref.alloc() : memref<128x256xf32>   ; 堆分配
  %val = memref.load %buf[%i, %j] : f32         ; 读取
  memref.store %val, %buf[%i, %j] : f32         ; 写入
  %view = memref.subview %buf[0, 0][64, 128][256, 1]  ; 子视图
  memref.dealloc %buf : memref<128x256xf32>      ; 释放

  MemRef类型: memref<shape, element_type, layout, address_space>
  memref<128x256xf32, strided<[256, 1], offset: 0>>
  → 128行×256列, 行主序, 步长[256, 1], 偏移0

  定位: 类似LLVM IR的alloca+load+store+GEP
  特点: 有显式的布局信息, 支持子视图和视图变换

Tensor方言: 抽象张量操作
  %0 = tensor.empty() : tensor<128x256xf32>     ; 空张量
  %1 = tensor.insert %val into %0[%i, %j]       ; 插入元素
  %2 = tensor.extract %1[%i, %j] : f32          ; 提取元素
  %3 = tensor.insert_slice %slice into %2[0, 0] ; 插入切片

  定位: bufferization前的抽象操作
  特点: 值语义(不可变), 每次操作产生新张量
```

### 15.1.3 Linalg：结构化线性代数

**源码**：`mlir/lib/Dialect/Linalg/IR/LinalgOps.cpp`（6741行）

Linalg是MLIR最重要的AI编译方言——它以结构化方式表达线性代数运算：

```
Linalg核心操作:

linalg.matmul:
  %C = linalg.matmul ins(%A, %B: tensor<128x256xf32>, tensor<256x512xf32>)
                       outs(%C: tensor<128x512xf32>) -> tensor<128x512xf32>
  → 语义: C += A × B (矩阵乘法)

linalg.conv_2d:
  %Y = linalg.conv_2d ins(%Input, %Filter: ...)
                      outs(%Output: ...) -> tensor<...>
  → 语义: 2D卷积

linalg.generic: 通用结构化运算
  %R = linalg.generic {
    indexing_maps = [affine_map<(i, j) -> (i, j)>,    // 输入A的索引
                     affine_map<(i, j) -> (j, k)>,    // 输入B的索引
                     affine_map<(i, j) -> (i, k)>],   // 输出C的索引
    iterator_types = ["parallel", "parallel", "reduction"]
  } ins(%A, %B) outs(%C) {
  ^bb0(%a: f32, %b: f32, %c: f32):
    %0 = arith.mulf %a, %b : f32
    %1 = arith.addf %c, %0 : f32
    linalg.yield %1 : f32
  } -> tensor<128x512xf32>
  → 这就是linalg.matmul的通用形式!

Linalg的设计哲学:
  1. 结构化: 循环嵌套是隐式的(通过iterator_types表达)
  2. 索引映射: 仿射映射表达输入输出的索引关系
  3. 体区域(Region): 操作的计算逻辑用嵌套Region表达
  4. 渐进式Lowering: linalg → loops → affine → scf → cf → llvm
```

### 15.1.4 Affine：仿射循环(多面体优化)

**源码**：`mlir/lib/Dialect/Affine/IR/AffineOps.cpp`（5696行）

Affine方言表达仿射循环嵌套，支持多面体变换：

```
affine.for %i = 0 to 128 {
  affine.for %j = 0 to 256 {
    %a = affine.load %A[%i, %j] : memref<128x256xf32>
    %b = affine.load %B[%j] : memref<256xf32>
    %0 = arith.mulf %a, %b : f32
    affine.store %0, %C[%i, %j] : memref<128x256xf32>
  }
}

多面体变换:
  Loop tiling: 将大循环分成小块(适配缓存)
  Loop fusion: 合并相邻循环(减少内存访问)
  Loop interchange: 交换循环顺序(改善局部性)
  Loop parallelization: 标识可并行的循环

  这些变换在仿射表示上可以精确计算依赖距离,
  保证变换的正确性 → 这就是多面体优化的威力
```

### 15.1.5 GPU / SPIRV / NVVM / ROCDL：异构计算

```
GPU方言: 设备无关的GPU编程
  gpu.launch blocks(%bx, %by, %bz) in (%gsx, %gsy, %gsz)
             threads(%tx, %ty, %tz) in (%bsx, %bsy, %bsz) {
    %tid = gpu.thread_id  x
    %bid = gpu.block_id   x
    ...kernel代码...
    gpu.terminator
  }

  → Lowering到:
    NVVM方言 (NVIDIA) → PTX
    ROCDL方言 (AMD)   → GCN

SPIRV方言: Vulkan/OpenCL计算
  标准化的GPU中间表示
  跨平台: NVIDIA/AMD/Intel GPU都支持

NVVM方言: NVIDIA GPU特定
  直接映射到PTX指令
  包含NVVM intrinsics

ROCDL方言: AMD GPU特定
  直接映射到GCN ISA
  包含AMD特有操作
```

---

## 15.2 Pattern Rewriting：模式重写引擎

### 15.2.1 RewritePattern / PatternRewriter / benefit排序

```
模式重写是MLIR变换的核心机制:

1. 定义Pattern:
   struct MatmulToLoops : public OpRewritePattern<linalg::MatmulOp> {
     LogicalResult matchAndRewrite(linalg::MatmulOp op,
                                    PatternRewriter &rewriter) override {
       // 将linalg.matmul替换为嵌套scf.for + arith.mulf/addf
       ...
     }
   };

2. 注册Pattern:
   RewritePatternSet patterns(context);
   patterns.add<MatmulToLoops>(context);

3. 应用Pattern:
   applyPatternsAndFoldGreedily(op, std::move(patterns));

Pattern选择策略:
  - benefit排序: 每个Pattern有一个benefit值(0-65535)
  - 高benefit的Pattern优先匹配
  - 相同benefit的Pattern按注册顺序匹配
  - Pattern成功匹配后, 重新评估所有受影响的Op

终止条件:
  - 没有Pattern可以匹配 → 固定点
  - 达到最大迭代次数 → 强制终止
```

### 15.2.2 Declarative Rewrites与PDLL

```
声明式重写规则(在.td文件中定义):

def MatmulToLoops : Pat<
  (Linalg_MatmulOp $A, $B, $C),       // 匹配模式
  (SCF_ForOp ...)>;                     // 替换模式

PDLL (Pattern Definition Language):
  更强大的声明式重写语言:
  Rewrite matmul_to_loops(op: linalg.MatmulOp) {
    // 类型安全的模式匹配
    let A = op.inputs()[0];
    let B = op.inputs()[1];
    // 生成嵌套循环
    replace op with scf.for ...;
  }
```

---

## 15.3 Dialect Conversion：方言间的渐进式降低

### 15.3.1 ConversionTarget / TypeConverter / applyFullConversion

```
Dialect Conversion框架:

1. ConversionTarget: 定义目标方言的合法性
   ConversionTarget target(*context);
   target.addLegalDialect<SCFDialect>();       // SCF方言合法
   target.addLegalDialect<ArithDialect>();      // Arith方言合法
   target.addIllegalDialect<LinalgDialect>();   // Linalg方言不合法 → 必须转换!
   target.addDynamicallyLegalOp<scf::ForOp>(   // 动态合法性判断
     [](scf::ForOp op) { return isLegalFor(op); });

2. TypeConverter: 类型转换规则
   TypeConverter converter;
   converter.addConversion([](TensorType type) {      // tensor → memref
     return MemRefType::get(type.getShape(), type.getElementType());
   });
   converter.addConversion([](IndexType type) {       // index → i64
     return IntegerType::get(type.getContext(), 64);
   });

3. 应用转换:
   applyFullConversion(op, target, patterns);   // 全量转换(所有非法Op必须转换)
   applyPartialConversion(op, target, patterns); // 部分转换(允许残留)
```

### 15.3.2 84个转换Pass的组织逻辑

```
mlir/lib/Conversion/目录:
  ArithToLLVM/     : Arith → LLVM IR
  SCFToOpenMP/     : SCF → OpenMP
  SCFToControlFlow/: SCF → CF (非结构化控制流)
  LinalgToLoops/   : Linalg → SCF循环
  LinalgToStandard/: Linalg → 标准操作
  VectorToLLVM/    : Vector → LLVM IR向量
  VectorToGPU/     : Vector → GPU
  GPUToNVVM/       : GPU → NVVM
  GPUToROCDL/      : GPU → ROCDL
  GPUToSPIRV/      : GPU → SPIRV
  TensorToLinalg/  : Tensor → Linalg
  MemRefToLLVM/    : MemRef → LLVM IR
  AffineToStandard/: Affine → SCF
  FuncToLLVM/      : Func → LLVM IR
  ...更多

典型Lowering路径:
  Linalg → SCF → CF → LLVM
  Linalg → Affine → SCF → CF → LLVM
  Linalg → Vector → LLVM
  GPU → NVVM/ROCDL/SPIRV
```

---

## 15.4 Linalg优化流水线：Tiling → Fusion → Vectorization → Bufferization

### 15.4.1 数据库执行计划优化的类比

```
Linalg优化流水线 ≈ 数据库查询优化:

1. Tiling ≈ 分区裁剪(Partition Pruning):
   linalg.matmul on tensor<1024x1024xf32>
   → tile to 4x4 blocks of tensor<256x256xf32>
   → 目的: 适配缓存大小(类似分区适配存储块)

2. Fusion ≈ 算子融合(Operator Fusion):
   matmul → relu → batch_norm
   → 融合为单个kernel, 避免中间结果写回内存
   → 类比: 多个SQL子查询合并为单个查询

3. Vectorization ≈ 向量化执行(Vectorized Execution):
   标量循环 → SIMD向量指令
   → 类比: 行式执行 → 向量化batch执行

4. Bufferization ≈ 物理化(Materialization):
   tensor → memref (从值语义到引用语义)
   → 类比: 逻辑计划 → 物理计划
   → 决定哪些中间结果物化到内存, 哪些in-place计算
```

### 15.4.2 Transform Dialect：声明式转换策略

```
Transform方言: 用MLIR自身描述MLIR变换

module attributes {transform.with_named_sequence} {
  transform.named_sequence @__transform_main(%arg: !transform.any_op) {
    // 1. 获取所有matmul操作
    %matmuls = transform.structured.match ops{["linalg.matmul"]} in %arg

    // 2. 对matmul进行tiling
    %tiled, %loops = transform.structured.tile_using_forall %matmuls
                       tile_sizes [64, 64]

    // 3. 对tiling后的结果进行向量化
    %vectorized = transform.structured.vectorize %tiled

    // 4. bufferization
    %bufferized = transform.bufferization.one_shot_bufferize %vectorized

    transform.yield
  }
}

价值:
  - 优化策略可编程(不再硬编码在C++中)
  - 策略可序列化和复用
  - 类似于数据库的Hint机制(用户指导优化器)
```

---

## 15.5 本章小结

本章解析了MLIR的Dialect生态和变换机制：

1. **核心Dialect**——Arith/Func/SCF/CF(基础设施)、MemRef/Tensor(内存与张量)、Linalg(AI编译核心)、Affine(多面体优化)、GPU/SPIRV(异构计算)。
2. **Pattern Rewriting**——声明式模式匹配和重写，benefit排序保证确定性。
3. **Dialect Conversion**——ConversionTarget/TypeConverter框架，84个转换Pass的渐进式Lowering。
4. **Linalg优化流水线**——Tiling→Fusion→Vectorization→Bufferization，与数据库查询优化的深刻类比。

下一章进入MLIR在AI编译中的实战——从PyTorch到GPU的完整路径。
