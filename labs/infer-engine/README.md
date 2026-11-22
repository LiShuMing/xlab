# infer-engine — 从零实现的单机迷你推理引擎（mini-vLLM）

前置条件：Linux / WSL2 + NVIDIA CUDA GPU（测试可在 CPU/CUDA 运行，基准需 CUDA）、Python 3.11+、PyTorch CUDA。
本目录自包含，不依赖同仓库其他 lab 或外部下载；所有运行产物写入被忽略的 `.local/`。

## 覆盖机制（对应 Phase 2 M2.1–M2.4）

| 模块 | 源码 | 核心机制与教学点 |
| --- | --- | --- |
| **M2.1 Static vs Concat KV** | [model.py](src/infer_engine/model.py) | Qwen3 风格 GQA + RoPE + RMSNorm + SwiGLU；预分配定长 KV 槽位消除 `torch.cat` 重分配 |
| **M2.2 Paged KV & Block Manager** | [paged_kv.py](src/infer_engine/paged_kv.py) | 固定 `block_size` 物理页池、逻辑页表、引用计数、COW 保护、CPU Swap-Out/In 与严格块守恒不变量 |
| **M2.3 Continuous Batching & Chunked Prefill** | [scheduler.py](src/infer_engine/scheduler.py) | Waiting / Running / Swapped 三队列、`max_num_batched_tokens` 预算分块预填充、Recompute vs CPU Swap 抢占 |
| **M2.4 Radix Prefix Cache** | [prefix_cache.py](src/infer_engine/prefix_cache.py) | 按 block 哈希建前缀树，对比 LRU 与 LFU（频率感知）在共享 system prompt + 扫描污染负载下的命中率与 TTFT |
| **M2.4 Speculative Decoding** | [speculative.py](src/infer_engine/speculative.py) | 0.6B Draft + 4B Target 同驻 16 GB 显存，实现 Leviathan 无损拒绝采样并实测高/低接受率下的加速与退化 |

## 快速运行

```bash
cd labs/infer-engine

# 1. 全量正确性与不变量单测（7 条路径 100% token-level parity + 块守恒 + LFU/LRU + 拒绝采样无损性）
make test

# 2. 在 RTX 5070 Ti 上运行 M2.1–M2.4 全量基准测试
make bench

# 3. 生成离线 HTML 观测报告（.local/report.html）
make report
```
