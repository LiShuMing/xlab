# RTX 5070 Ti 实测结果与分析（Phase 1：M1.1 + M1.2 + M1.3）

测试日期：2026-11-21
硬件环境：NVIDIA GeForce RTX 5070 Ti（Blackwell `sm_120`，70 SMs，15.92 GiB GDDR7），WSL2 (`6.6.87`)
软件环境：CUDA Toolkit `13.3` (`nvcc 13.3.73`, `compute-sanitizer`)，PyTorch `2.10.0+cu128`，Triton `3.6.0`
计时口径：每次基准先预热，再使用 `torch.cuda.Event` / `cudaEventElapsedTime` 取中位数；显存受限测试与 GEMM 均在相邻迭代间做 64 MB L2 flush。

---

## 一、M1.1 显存带宽阶梯与 GEMM Roofline

### 1.1 带宽阶梯（L2 缓存 → Steady-State GDDR7）

| 算子 | 单张量大小 | Median (ms) | 有效带宽 (GB/s) | 物理现象 |
| --- | ---: | ---: | ---: | --- |
| `triad` | 8 MB | 0.0226 | **1115.5** | 命中 L2 缓存，突破显存带宽上限 |
| `copy` | 32 MB | 0.0745 | 900.8 | L2 与 VRAM 过渡区 |
| `copy` | 64 MB（L2 flush） | 0.1765 | 760.3 | 进入 steady-state GDDR7 |
| `copy` | 256 MB（L2 flush） | 0.6973 | 769.9 | steady-state 拷贝带宽 |
| `triad` | 256 MB（L2 flush） | 1.0159 | **792.7** | **实测峰值显存带宽**（约 88% GDDR7 理论带宽） |

### 1.2 GEMM 扫参（Decode → Prefill 迁移）

| 精度 / 形状 | `M×K×N` | 算术强度 (FLOPs/B) | Median (ms) | 实测 TFLOPS | 有效带宽 (GB/s) | 瓶颈区间 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `bf16` | `1×4096×4096` | 1.00 | 0.0847 | 0.40 | 396.5 | memory-bound |
| `bf16` | `4×4096×4096` | 3.99 | 0.0557 | 2.41 | 603.6 | memory-bound |
| `bf16` | `16×4096×4096` | 15.88 | 0.0578 | 9.29 | 585.0 | memory-bound |
| `bf16` | `32×4096×4096` | 31.51 | 0.0597 | 17.99 | 570.9 | memory-bound |
| `bf16` | `64×4096×4096` | 62.06 | **0.1303** | **16.48** | 265.5 | memory-bound（反直觉退化） |
| `bf16` | `128×4096×4096` | 120.47 | 0.1158 | 37.10 | 307.9 | compute-bound |
| `bf16` | `256×4096×4096` | 227.56 | 0.1048 | 81.95 | 360.1 | compute-bound |
| `bf16` | `4096×4096×4096` | 1365.33 | 1.5211 | **90.35** | 66.2 | compute-bound |
| `fp16` | `4096×4096×4096` | 1365.33 | 1.4163 | **97.04** | 71.1 | compute-bound |
| `fp32_tf32` | `4096×4096×4096` | 682.67 | 3.0204 | 45.50 | 66.7 | compute-bound |
| `fp32_ieee` | `4096×4096×4096` | 682.67 | 4.1955 | 32.76 | 48.0 | compute-bound |
| `bf16_ffn` | `8×4096×14336` | 7.98 | 0.1637 | 5.74 | **719.0** | memory-bound（91% 峰值带宽） |
| `bf16_ffn` | `2048×4096×14336` | 1246.61 | 2.4671 | **97.49** | 78.2 | compute-bound |

**核心结论**：
1. **实测 Roofline 拐点**：以 `792.7 GB/s` 和 `90.35 TFLOPS`（`4096³` BF16）计算，BF16 拐点约为 **114.0 FLOPs/Byte**（按 FFN 峰值 97.5 TFLOPS 约 123 FLOPs/Byte）。
2. **Continuous Batching 的物理依据**：`bf16 M=4 → 32` 时，耗时几乎不变（`0.0557 → 0.0597 ms`），而算力吞吐线性放大 **7.5 倍**（`2.41 → 17.99 TFLOPS`）。
3. **反直觉现象 #1（`bf16 M=64` 性能凹陷）**：`bf16 64×4096×4096` 耗时 `0.1303 ms`，反而慢于 `M=32`（`0.0597 ms`）和 `M=256`（`0.1048 ms`），而同形状 `fp16` 只需 `0.0596 ms`。这是 cuBLASLt 在 `sm_120` 上针对特定 `(M, N, K, dtype)` 的 tile/split-K 启发式选型退化——说明推理引擎做 batch padding/bucketing 时必须实测各档位延迟，不可默认耗时随 batch 单调递增。

---

## 二、M1.2 融合算子四方对照（BF16）

### 2.1 正确性与内存安全验证

- CUDA C++ (`fused_ops/kernels.cu`)：覆盖 `cols = 127, 256, 513, 1024, 3584, 4096, 8192`，FP32 RMSNorm 最大误差 `≤ 3.58e-7`，BF16 RMSNorm `≤ 1.33e-2`，BF16 Online Softmax `≤ 2.35e-3`。
- `compute-sanitizer --tool memcheck`：**0 errors**；`compute-sanitizer --tool racecheck`：**0 hazards (0 errors, 0 warnings)**。
- Triton 3.6 (`fused_ops/triton_ops.py`)：FP32 & BF16 全尺寸（含非 2 次幂与 `±50` 极值）对拍全部通过。

### 2.2 有效带宽与加速比（相对 792.7 GB/s 实测峰值）

| 算子 | 形状 (BF16) | `pytorch_eager` | `pytorch_builtin` | `triton_fused` | `cuda_cpp` | 峰值带宽占比（最优实现） |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| **RMSNorm** | `4096×2048` | 113.2 GB/s (1.00×) | **719.8 GB/s (6.36×)** | 296.2 GB/s (2.62×) | 714.4 GB/s (6.31×) | 90.8% (`builtin`/`cuda_cpp`) |
| **RMSNorm** | `4096×4096` | 79.4 GB/s (1.00×) | 714.4 GB/s (8.99×) | 612.4 GB/s (7.71×) | **761.9 GB/s (9.59×)** | **96.1%** (`cuda_cpp`) |
| **RMSNorm** | `4096×8192` | 79.1 GB/s (1.00×) | 713.0 GB/s (9.02×) | **753.9 GB/s (9.53×)** | 749.6 GB/s (9.48×) | **95.1%** (`triton_fused`) |
| **Softmax** | `4096×2048` | 119.7 GB/s (1.00×) | **510.8 GB/s (4.27×)** | 364.3 GB/s (3.04×) | 479.7 GB/s (4.01×) | 64.4% (`builtin`) |
| **Softmax** | `4096×4096` | 77.5 GB/s (1.00×) | 478.9 GB/s (6.18×) | **766.1 GB/s (9.89×)** | 497.1 GB/s (6.42×) | **96.6%** (`triton_fused`) |
| **Softmax** | `4096×8192` | 73.3 GB/s (1.00×) | 567.7 GB/s (7.75×) | **751.3 GB/s (10.25×)** | 578.3 GB/s (7.89×) | **94.8%** (`triton_fused`) |

**关键工程洞察**：
1. **融合消除中间物化直接带来 9×–10× 提速**：未融合 `pytorch_eager` 仅跑出 ~73–80 GB/s（约 10% 带宽），原因在于每次算子边界都把整张 FP32 中间张量写回再读出显存；融合后直接打到 **750–766 GB/s（~96% 实测显存峰值）**。
2. **反直觉现象 #2（为什么 Triton Softmax 在 4096/8192 比手写 CUDA Online Softmax 快 1.54×）**：
   - 本版 `cuda_cpp` 的 `OnlineSoftmaxBf16Kernel` 虽然用 Milakov-Gimelshein 状态合并省去了传统 3-pass 的第 2 趟，但写回归一化结果时仍需对 `row_x` 做**第 2 次全局显存读取**，且未向量化（标量 `bfloat16` 加载）；
   - `triton_fused` 将整行 4096/8192 个元素一次性载入寄存器/片上缓存，完成 `max` / `exp` / `sum` / 除法后直接写回，**真正做到 1 读 1 写**，因而跑出 **766.1 GB/s**（同时超越 PyTorch 内置 `torch.softmax` 1.60×）。
3. **小列宽 (`4096×2048`) 的 occupancy 权衡**：`triton_fused` 在 `2048` 列下 `num_warps=4` 反而偏慢（296/364 GB/s），而 `cuda_cpp` 向量化 `bfloat162` RMSNorm 仍保持 `714.4 GB/s`——后续可加入 Triton `@triton.autotune`（扫 `num_warps`）与 CUDA register-cached / `float4` vectorized softmax 做进一步对照。

---

## 三、M1.3 CUDA Graph 消除 Launch 空泡与 Chrome Trace

实验脚本：`cuda_graph/bench_cuda_graph.py`（24 层 BF16 解码块 + 静态 KV Cache 256 tokens，每步共 289 个 CUDA kernel；先通过 3 组不同输入的多输入数值对拍验证，排除静态缓冲区陈旧输出 bug）。

### 3.1 端到端单步墙钟耗时（Eager vs CUDA Graph vs 理论显存底线）

| 模型规模 | Batch `B` | 权重大小 | Eager (ms) | CUDA Graph (ms) | 加速比 | 消除 Launch 开销 | 理论显存底线 (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `qwen_0.6b_like` | 1 | 528 MB | 14.046 | **1.604** | **8.76×** | 12.442 ms | 0.730 |
| `qwen_0.6b_like` | 4 | 528 MB | 13.102 | **2.032** | **6.45×** | 11.069 ms | 0.826 |
| `qwen_0.6b_like` | 16 | 528 MB | 13.813 | **2.497** | **5.53×** | 11.315 ms | 1.207 |
| `qwen_0.6b_like` | 64 | 528 MB | 14.522 | **4.476** | **3.24×** | 10.047 ms | 2.730 |
| `qwen_4b_like` | 1 | 3030 MB | 15.863 | **5.485** | **2.89×** | 10.378 ms | 4.088 |
| `qwen_4b_like` | 8 | 3030 MB | 16.588 | **6.257** | **2.65×** | 10.331 ms | 4.643 |
| `qwen_4b_like` | 32 | 3030 MB | 15.743 | **9.179** | **1.72×** | 6.564 ms | 6.548 |
| `qwen_4b_like` | 64 | 3030 MB | 24.716 | **14.300** | **1.73×** | 10.416 ms | 9.088 |

### 3.2 PyTorch Profiler Chrome Trace 与核心洞察

- **Host Launch 次数骤降 289×**：Chrome Trace（`trace_eager.json` 与 `trace_cudagraph.json`）证实两者在 GPU 上执行完全相同的 **289 个 kernel**，但 Host 侧发核次数从 **289 次 `cudaLaunchKernel`** 降至 **1 次 `cudaGraphLaunch`**。
- **反直觉现象 #3（恒定的 ~10–12 ms 宿主空泡与 WSL2 放大效应）**：
  - 无论模型是 528 MB 还是 3030 MB、Batch 是 1 还是 64，Eager 相比 Graph 多花的几乎都是恒定的 **~10–12 ms**（`~36 µs × 289`），因为 WSL2 下每次 CUDA 发核需经过 Python + PyTorch dispatcher + Windows WDDM/DXG 半虚拟化层；
  - 对小模型/小 batch（`0.6B B=1`），这 12.4 ms 空泡直接吃掉 **88.6%** 的单步时间，开启 CUDA Graph 后直接拿到 **8.76×** 加速；对 4B 模型 `B=1` 仍带来 **2.89×** 加速并逼近理论显存底线的 **74.5%**。
- **Profiler 观测者效应**：开启 `torch.profiler(CPU+CUDA)` 会对 289 个 Eager CPU op 附加 ~30× 埋点耗时（墙钟膨胀至 ~460 ms），因此耗时对比必须以无 profiler 干扰的纯净计时为准，Profiler 仅用于结构核查（kernel 数、launch 数、timeline 空泡形态）。
