# 第16章 MLIR实战：AI编译器的完整路径

## 16.1 深度学习编译栈全景

### 16.1.1 PyTorch/TF → MLIR Dialect → LLVM IR → Machine Code

```
完整编译路径:

PyTorch模型
  │ torch.export() / torch.compile()
  ▼
Torch Dialect (torch-mlir项目)
  │ torch→linalg转换
  ▼
Linalg Dialect
  │ tiling → fusion → vectorization
  ▼
Vector Dialect + SCF Dialect
  │ bufferization
  ▼
MemRef Dialect + SCF Dialect
  │ convert-to-llvm
  ▼
LLVM IR Dialect
  │ translate-to-llvmir
  ▼
LLVM IR
  │ llc
  ▼
目标机器码 (CPU) 或 PTX/GCN (GPU)
```

### 16.1.2 IREE / Torch-MLIR / XLA的MLIR实践

```
IREE (Integrated Runtime Engine):
  Google主导的AI编译运行时
  路径: MLIR → HAL Dialect → VM Bytecode → 运行时执行
  特点: 端到端编译+运行时, 支持CPU/GPU

Torch-MLIR:
  PyTorch → MLIR的桥梁
  路径: PyTorch → Torch Dialect → TOSA/Linalg Dialect
  特点: 利用torch.export()的图捕获

XLA (Accelerated Linear Algebra):
  Google的AI编译器, 已迁移到MLIR
  路径: HLO Dialect → Linalg → GPU/NVVM
  特点: 稳定算子集(HLO), 丰富的优化Pass
```

---

## 16.2 从算子到硬件：Linalg到GPU的完整Lowering

### 16.2.1 matmul示例：Linalg → Tiling → Vector → GPU → PTX/GCN

```
完整变换链(以matmul为例):

步骤1: Linalg Matmul
  %C = linalg.matmul ins(%A, %B: tensor<1024x1024xf32>,
                                     tensor<1024x1024xf32>)
                     outs(%C: tensor<1024x1024xf32>) -> tensor<1024x1024xf32>

步骤2: Tiling (分成64×64的块)
  scf.forall (%i, %j) in (16, 16) {
    %Atile = tensor.extract_slice %A[%i*64, 0] [64, 1024] [1, 1]
    %Btile = tensor.extract_slice %B[0, %j*64] [1024, 64] [1, 1]
    %Ctile = tensor.extract_slice %C[%i*64, %j*64] [64, 64] [1, 1]
    %R = linalg.matmul ins(%Atile, %Btile) outs(%Ctile)
    tensor.insert_slice %R into %C[%i*64, %j*64] [64, 64] [1, 1]
  }

步骤3: Vectorization (将内层循环向量化)
  %Atile_v = vector.transfer_read %Atile[%k, 0], %cst : memref<64x1024xf32>, vector<64xf32>
  %Btile_v = vector.transfer_read %Btile[0, %j], %cst : memref<1024x64xf32>, vector<64xf32>
  %acc = vector.contract {indexing_maps = ...} %Atile_v, %Btile_v, %Ctile_v
       : vector<64xf32>, vector<64xf32> -> vector<64x64xf32>
  vector.transfer_write %acc, %Ctile : vector<64x64xf32>, memref<64x64xf32>

步骤4: Bufferization (tensor → memref)
  所有tensor操作变为memref操作, 值语义变为引用语义

步骤5: GPU Launch (将kernel发送到GPU)
  gpu.launch blocks(%bx, %by) in (%gx, %gy) threads(%tx, %ty) in (%bx, %by) {
    %Atile = memref.load %A_global[%bx*64+%tx, ...] : ...
    ... 向量化计算 ...
    memref.store %result, %C_global[...] : ...
  }

步骤6: Convert to NVVM/ROCDL
  gpu.launch → nvvm.ptxld / rocdl.ds_read
  → 最终生成PTX (NVIDIA) 或 GCN ISA (AMD)
```

---

## 16.3 稀疏张量编译(SparseTensor Dialect)

```
SparseTensor方言: 编译期感知稀疏性

%sparse = sparse_tensor.convert %dense : tensor<1024x1024xf32>
                                    to tensor<1024x1024xf32, #CSR>

#CSR = #sparse_tensor.encoding<{
  dimLevelType = ["dense", "compressed"],  // 第1维稠密, 第2维稀疏
  dimOrdering = affine_map<(i, j) -> (i, j)>,
  pointerBitWidth = 64,
  indexBitWidth = 64
}>

稀疏编译的优势:
  - 只计算非零元素 → 10-1000倍加速(取决于稀疏度)
  - 自动选择存储格式(CSR/CSC/COO/CSF/...)
  - 稀疏+稠密混合计算自动处理
  - 算子融合在稀疏表示上同样有效

Linalg + SparseTensor:
  linalg.matmul的稀疏版本自动生成
  → 只迭代非零元素, 跳过零值计算
  → 通过SparseTensor encoding驱动代码生成
```

---

## 16.4 量化编译(Quant Dialect)

```
Quant方言: 深度学习量化支持

量化类型:
  !quant.uniform<i8:f32, 0.0078125:127>   // uniform int8量化
  !quant.per_axis<i8:f32, {scales, zp}>    // per-channel量化

量化流程:
  1. 识别可量化的算子(matmul, conv)
  2. 插入量化/反量化节点
  3. 传播量化类型
  4. 融合量化节点到算子中

  原始:
    %0 = arith.mulf %a, %b : f32

  量化后:
    %qa = quant.qcast %a : f32 -> !quant.uniform<i8:f32, ...>
    %qb = quant.qcast %b : f32 -> !quant.uniform<i8:f32, ...>
    %qr = arith.muli %qa, %qb : i8  // 整数乘法!
    %r  = quant.dcast %qr : !quant.uniform<i8:f32, ...> -> f32

  融合后:
    %r = quant.fused_matmul_i8 %a, %b   // 单条量化matmul指令

W8A8/W4A16/FP8量化的编译器路径:
  W8A8: 权重8bit, 激活8bit → 最常见, LLM推理标准
  W4A16: 权重4bit, 激活16bit → 减少内存带宽(GPTQ/AWQ)
  FP8: E4M3/E5M2格式 → 硬件原生支持(H100/MI300)
```

---

## 16.5 本章小结

本章展示了MLIR在AI编译中的完整实战：

1. **深度学习编译栈**——从PyTorch/TF到机器码的完整路径，Torch-MLIR/IREE/XLA三大实践。
2. **Linalg到GPU的完整Lowering**——以matmul为例的6步变换链。
3. **稀疏张量编译**——SparseTensor Dialect的CSR/CSC自动生成，只计算非零元素。
4. **量化编译**——Quant Dialect的W8A8/W4A16/FP8支持，量化节点融合。

下一章进入第五篇——GPU异构编译，SIMT世界的编译器适配。
