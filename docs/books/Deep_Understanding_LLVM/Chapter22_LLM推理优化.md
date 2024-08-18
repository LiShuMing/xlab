# 第22章 LLM推理优化：编译器视角

## 22.1 LLM推理的计算特征

### 22.1.1 Transformer算子图：Attention / FFN / KV Cache

```
LLM推理的两个阶段:

Prefill阶段(首token):
  输入: 完整prompt (sequence_length个token)
  计算: 完整的self-attention (O(S²·d)计算)
  特征: 计算密集型(GEMM为主)
  → 类比: 数据库的批量加载

Decode阶段(后续token):
  输入: 1个新token
  计算: 增量attention (O(S·d)计算, S=当前序列长度)
  特征: 内存带宽密集型(读取KV Cache)
  → 类比: 数据库的逐行点查

核心算子:
  1. QKV Projection: [S,d] × [d,3d] → [S,3d]   (GEMM, prefill)
  2. Attention: Q×K^T → S×S → Softmax → ×V       (O(S²·d))
  3. Output Projection: [S,d] × [d,d] → [S,d]     (GEMM)
  4. FFN: [S,d] × [d,4d] → [S,4d] → ×[4d,d]     (2个GEMM)
  5. KV Cache: 读取历史K/V, 追加新K/V              (内存带宽瓶颈!)
```

### 22.1.2 内存带宽瓶颈 vs 计算瓶颈：roofline模型分析

```
Roofline模型:

  性能 = min(峰值算力, 带宽 × 算术强度)

  算术强度(Arithmetic Intensity) = FLOPs / Bytes_transferred

  A100 GPU参数:
    峰值算力: 312 TFLOPS (FP16/BF16)
    内存带宽: 2 TB/s
    转折点: 312/2 = 156 FLOPs/Byte

  LLM推理的算术强度:
    Prefill (S=2048):  GEMM算术强度 ≈ S×d/(2×d×4) ≈ 256 → 计算密集
    Decode  (S=2048):  GEMV算术强度 ≈ d/(2×d×4) ≈ 0.125 → 内存密集!
    KV Cache读取:      算术强度 ≈ 0 → 纯内存带宽瓶颈

  数据库类比:
    Prefill ≈ 全表扫描 → 计算密集(过滤/聚合)
    Decode  ≈ 索引查找 → IO密集(随机读)

  编译器优化策略:
    计算密集: 向量化、算子融合、并行化
    内存密集: 量化(减少传输数据)、KV Cache压缩、Flash Attention
```

---

## 22.2 LLM算子的编译优化

### 22.2.1 Flash Attention的编译器实现思路

```
Flash Attention: 分块计算Attention, 避免S×S中间矩阵

标准Attention:
  S = Q × K^T           → [S,S]矩阵 (S²内存!)
  P = Softmax(S)        → [S,S]矩阵
  O = P × V             → [S,d]矩阵

Flash Attention:
  将Q/K/V分成B_r×B_c的块:
  for each block Q_i:
    for each block K_j, V_j:
      S_ij = Q_i × K_j^T          → [B_r, B_c] (小矩阵!)
      P_ij = Softmax(S_ij)         → 在线softmax
      O_i += P_ij × V_j            → 累加输出

  内存: O(S×d)而非O(S²) → 序列长度无关的内存占用!
  编译器实现:
  - MLIR Linalg → tiling by B_r×B_c → vector dialect
  - online softmax需要自定义的linalg.generic
  - GPU shared memory用于缓存Q_i和K_j块
```

### 22.2.2 KV Cache的内存布局优化

```
KV Cache布局对比:

方案1: [layer, batch, head, seq_len, head_dim] (NHSD)
  问题: 不同seq_len导致内存碎片
  优点: 单个head的K/V连续存储

方案2: [layer, batch, seq_len, head, head_dim] (NSHD)
  优点: 同一位置的K/V连续 → 适合PagedAttention
  问题: 跨head的访问不连续

方案3: PagedAttention (vLLM)
  将KV Cache分为固定大小的页(如16个token)
  页表映射: virtual_token → physical_page
  类似操作系统虚拟内存!
  → 减少内存碎片, 支持跨请求共享

编译器视角:
  布局选择 = linalg.generic的indexing_maps
  从NHSD → NSHD: permutation操作(零拷贝需要stride调整)
  PagedAttention: 需要自定义indirection(gather/scatter)
```

### 22.2.3 GEMM/GEMV的自动向量化与tiling

```
Prefill的GEMV优化:
  实际上Decode阶段是GEMV(矩阵×向量), 不是GEMM(矩阵×矩阵)

  GEMV: y = A × x, A是[d,d], x是[d,1], y是[d,1]
  算术强度: 2d² / (d² + 2d)×4 ≈ 0.5 → 极度内存密集

  优化策略:
  1. 量化: FP16 → INT8 → 数据量减半, 带宽利用率翻倍
  2. 重量矩阵分块: 将A分成tile, 并行处理
  3. 向量化load: 一次加载多个元素(SIMD)
  4. Warp级并行: 32个线程协作计算一个输出元素

  MLIR实现:
  linalg.matmul → tile by [32, 32] → vector<4xf32> → GPU shared mem
```

---

## 22.3 动态shape与自适应编译

### 22.3.1 MLIR的动态shape支持

```
动态shape在MLIR中的表达:

tensor<?x?xf32>   → 两个维度都动态
tensor<?x4096xf32> → 只有batch维度动态

编译策略:
  1. 泛型kernel: 接受动态维度作为参数
     func.func @matmul(%A: tensor<?x?xf32>, %B: tensor<?x?xf32>)
     → 编译为接受shape参数的通用代码

  2. Shape特化: 对常见shape编译专用版本
     tensor<1x4096xf32> → decode阶段
     tensor<2048x4096xf32> → prefill阶段
     → JIT编译特化版本, 缓存

  3. 多版本dispatch: 运行时根据shape选择版本
     if (seq_len <= 512) kernel_small();
     else if (seq_len <= 2048) kernel_medium();
     else kernel_large();
```

### 22.3.2 Sequence length / Batch size变化的编译策略

```
LLM推理的shape变化:

  Sequence length: 1(prefill第1个) → 2 → 3 → ... → max_len
  Batch size: 1(单请求) → N(批处理, vLLM continuous batching)

  编译挑战:
  1. 每个不同的shape理论上需要不同的kernel
  2. 但编译一个kernel需要秒级
  3. 实际shape在编译期未知

  解法:
  1. Shape无关kernel: 用动态循环界限
  2. Shape bucket: 将shape分成几档, 每档编译一个版本
     bucket: [1-128], [129-512], [513-2048], [2049+]
  3. TorchDynamo的编译缓存:
     第一次遇到新shape → JIT编译 → 缓存
     后续相同shape → 命中缓存
  4. AOT + JIT混合:
     关键kernel(attention, FFN)提前编译多个版本
     特化kernel(特定shape)按需JIT编译
```

---

## 22.4 量化与混合精度

### 22.4.1 W8A8 / W4A16 / FP8量化的编译器路径

```
量化方案与编译器支持:

W8A8 (权重8bit, 激活8bit):
  权重: int8存储, 运行时dequantize为fp16
  激活: fp16计算, 输出quantize为int8
  编译器路径:
    linalg.matmul → quantized_matmul_i8
    → vpmaddubsw + vpmaddwd (X86 AVX-VNNI)
    → dp4a (NVIDIA INT8 Tensor Core)

W4A16 (权重4bit, 激活16bit):
  权重: int4存储, 运行时dequantize为fp16
  激活: fp16计算
  编译器路径:
    linalg.matmul → dequantize_i4_to_f16 → fp16_matmul
    → dequantize开销小(4bit→16bit查找表)
    → 适用于内存带宽瓶颈(Decode阶段)

FP8 (E4M3/E5M2格式):
  E4M3: 4位指数, 3位尾数 → 前向传播
  E5M2: 5位指数, 2位尾数 → 反向传播
  编译器路径:
    linalg.matmul → fp8_matmul (硬件原生支持)
    → H100: FP8 Tensor Core, 2倍FP16吞吐
    → MI300: FP8 XDL指令

MLIR量化流水线:
  1. 识别可量化的linalg.matmul/linalg.conv
  2. 插入quantize/dequantize节点
  3. 传播量化类型(Quant Dialect)
  4. 融合quantize到计算算子
  5. 选择目标特定的量化kernel
```

---

## 22.5 分布式推理的编译器支持

### 22.5.1 Tensor Parallelism / Pipeline Parallelism的IR表达

```
分布式推理策略:

1. Tensor Parallelism(TP):
   将权重矩阵按列/行分割到多个GPU
   每个GPU计算部分结果, 然后all-reduce

   linalg.matmul %A, %B → 分割B为B1, B2
   GPU0: C1 = A × B1
   GPU1: C2 = A × B2
   AllReduce: C = C1 + C2

2. Pipeline Parallelism(PP):
   将模型按层分割到多个GPU
   每个GPU计算若干层

   GPU0: Layer0-7
   GPU1: Layer8-15
   GPU2: Layer16-23
   GPU3: Layer24-31

MLIR表达:
  shard方言(实验性):
    %sharded = shard.tensor_shard %weight <@mesh, ["x", "y"]>
    %result = shard.sharded_matmul %sharded, %input

  mesh方言:
    mesh.mesh @cluster(dim_x = 2, dim_y = 4)
    → 定义2×4的GPU网格
```

---

## 22.6 主流LLM推理框架的编译器架构对比

```
| 框架 | 编译后端 | 量化 | JIT | 特点 |
|------|---------|------|-----|------|
| vLLM | PyTorch/ATen | AWQ/GPTQ | torch.compile | PagedAttention, continuous batching |
| TensorRT-LLM | TensorRT | FP8/INT8 | 离线编译 | NVIDIA优化, kernel auto-tuning |
| TGI | FlashAttention/vLLM | bitsandbytes | torch.compile | HuggingFace生态 |
| llama.cpp | GGML | Q4_0/Q8_0 | 无JIT | CPU推理, 纯C++ |
| IREE | MLIR | Quant Dialect | AOT+JIT | 端到端MLIR, 多硬件 |

编译器使用情况:
  vLLM: 使用torch.compile (PyTorch的JIT), 底层是Triton/openAI kernel
  TensorRT-LLM: NVIDIA的专用编译器, 高度优化的CUDA kernel
  llama.cpp: 无编译器, 手写优化kernel, GGML张量库
  IREE: 完全基于MLIR, linalg→vector→GPU流水线

共同趋势:
  1. 向MLIR迁移: 统一的中间表示
  2. JIT编译: 动态shape需要运行时代码生成
  3. 自动量化: 从手动kernel到编译器自动生成量化kernel
  4. 算子融合: Flash Attention等融合kernel的编译器自动发现
```

---

## 22.7 本章小结

本章从编译器视角全面分析了LLM推理优化：

1. **计算特征**——Prefill计算密集、Decode内存密集，roofline模型指导优化方向。
2. **算子优化**——Flash Attention的分块计算、KV Cache布局优化、GEMV的量化加速。
3. **动态shape**——MLIR的动态shape支持、shape bucket策略、AOT+JIT混合编译。
4. **量化**——W8A8/W4A16/FP8的编译器路径，MLIR Quant Dialect的量化流水线。
5. **分布式**——Tensor/Pipeline Parallelism的IR表达，shard/mesh方言。
6. **框架对比**——vLLM/TensorRT-LLM/llama.cpp/IREE的编译器架构差异。

下一章展望未来——Agent驱动的编译优化和AI原生编译器。
