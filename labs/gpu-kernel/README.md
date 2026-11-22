# gpu-kernel — 单卡 Roofline、CUDA/Triton 融合算子与执行模型实验

前置条件：Linux / WSL2 + NVIDIA CUDA GPU、CUDA Toolkit（`nvcc`、`compute-sanitizer`）、Python 3.11+、PyTorch CUDA、Triton。
本目录自包含，不依赖仓库其他语言目录或外部 checkout；所有运行产物、报告与 Triton 缓存写入被忽略的 `.local/` 与 `fused_ops/bin/`。

## 目录结构

```text
labs/gpu-kernel/
├── Makefile                  # 统一调度入口（roofline / kernels / test / sanitize / clean）
├── common/timing.py          # CUDA Event 计时、L2 flush、环境探测与报告工具
├── roofline/
│   └── bench_roofline.py     # M1.1 显存带宽阶梯 + GEMM Roofline 扫参 + 离线 HTML/SVG 报告
├── fused_ops/
│   ├── Makefile              # nvcc 编译与 compute-sanitizer 验证
│   ├── kernels.cu            # M1.2 手写 CUDA C++ Fused RMSNorm + Online Softmax
│   ├── triton_ops.py         # M1.2 手写 Triton Fused RMSNorm + Softmax
│   └── bench_fused_ops.py    # PyTorch Eager / Built-in / Triton / CUDA C++ 对拍与带宽基准
├── cuda_graph/
│   └── bench_cuda_graph.py   # M1.3 CUDA Graph vs Eager launch 开销扫参 + PyTorch Profiler Chrome Trace
├── tools/
│   └── build_report.py       # 聚合最新 roofline + fused_ops + cuda_graph 数据生成统一离线交互报告
└── RESULTS.md                # 本机实测数据、Roofline 结论与证据边界
```

## 快速运行

```bash
cd labs/gpu-kernel

# 1. M1.1: 显存带宽阶梯 + GEMM Roofline 标定（输出 .local/runs/.../report.html）
make roofline

# 2. M1.2: 构建 CUDA C++ kernel 并运行四方对比（Eager / Built-in / Triton / CUDA C++）
make kernels

# 3. M1.3: CUDA Graph 消除小 batch launch 空泡 + 导出 Chrome Trace（可用 Perfetto / chrome://tracing 打开）
make cuda-graph

# 4. 聚合全部实测数据生成统一可观测性与学习交互报告（.local/report.html）
make report

# 5. 全量数值对拍单测（CUDA C++ + Triton + CUDA Graph 多输入对拍）
make test

# 6. CUDA 内存安全与竞态检查（compute-sanitizer memcheck + racecheck）
make sanitize
```

## 验证纪律与证据边界

1. **防 L2 缓存假带宽**：显存受限基准在相邻迭代之间执行 64 MB L2 flush，避免把 L2 命中带宽误报成 steady-state VRAM 带宽（`roofline` 中 ≤ 32 MB 刻意不 flush 以显式展示 L2→VRAM 的阶梯）。
2. **纯 GPU 计时与数值对拍**：所有计时均先预热再使用 `torch.cuda.Event` / `cudaEventElapsedTime`；所有自定义 kernel 必须先通过 FP32 参考实现数值对拍，再参与性能对比。
3. **单卡边界**：实测结果反映单张本地 GPU（如 RTX 5070 Ti, `sm_120`）的算力、显存带宽与核函数调度特征，不能直接外推多卡 NVLink/NCCL 通信或数据中心卡（MIG/HBM3e）行为。
