# RTX 5070 Ti 实测结果与分析（Phase 2：M2.1–M2.4）

测试日期：2026-11-21
硬件环境：NVIDIA GeForce RTX 5070 Ti（`sm_120`，15.92 GiB GDDR7），WSL2 (`6.6.87`)
软件环境：PyTorch `2.10.0+cu128`，离线 Qwen3 架构维度模型（GQA + RoPE + RMSNorm + SwiGLU）
离线报告：[report.html](.local/report.html)（由 `make report` 生成）

---

## 一、正确性与不变量验证（5/5 全通过）

- **7 条执行路径 100% Token-Level Parity**（FP32 精确对拍）：No-Cache Eager == Concat KV == Static KV == Paged KV + Continuous Batching == 非对齐 Chunked Prefill (`budget=17`) == Recompute/Swap 抢占 == Radix Prefix Cache 命中路径。
- **物理块守恒不变量**：每步断言 `used + free == num_blocks`、`refcount >= 0`，全部请求结束后无泄漏。
- **投机解码无损性**：12,000 次拒绝采样统计验证，输出分布与目标分布最大全变差误差 `< 0.02`。

---

## 二、真机实测结果与关键反直觉发现

### M2.1 Static KV vs Concat KV（0.6B 架构 BF16，Prompt=256, Gen=128）
- `concat`：Median ITL `35.95 ms`（26.4 tok/s）；`static`：Median ITL `45.78 ms`（21.0 tok/s）。
- **结论**：在 WSL2 Python Eager 模式下，24 层每步 ~35–45 ms 的宿主发核税完全掩盖了短上下文下 `torch.cat` 的显存拷贝差；Static KV 的核心工程价值在于**消除长上下文 $O(L^2)$ 拷贝**，以及作为 **CUDA Graph 捕获的前提（地址静态不可变）**。

### M2.2 Static KV vs Paged KV 显存碎片（固定 8192 token 预算，max_len=1024，block_size=16）
- **Static KV**：仅能并发 **8 条**请求，内部碎片浪费高达 **89.0%**；
- **Paged KV**：并发飙升至 **38 条**（**4.75× 并发增益**），内部碎片骤降至 **1.74%**。

### M2.3 Continuous Batching：Chunked Prefill 与抢占（Recompute vs CPU Swap）
- **Chunked Prefill**（6 条 Decode + 2 条 384-token 长 Prefill）：在无 CUDA Graph 的 Eager 实现下，切分 chunk 增加了总迭代步数（20 → 23 步），在 WSL2 高每步发核税下反而推高长 Prefill TTFT（`109.8 ms → 1525.0 ms`）且未压低 P99 ITL（`181.2 → 208.9 ms`）——直观暴露 **Chunked Prefill 收益的前提是单步 launch 成本远低于长 Prefill 计算时间（即长上下文 ≥ 2K–8K 且配合 CUDA Graph / 高效 C++ 调度器）**。
- **Preemption（24 块紧张池）**：Recompute（3 次抢占，重算 359 tokens，总耗时 `4620.4 ms`）与 CPU Swap（4 次抢占，PCIe Swap-out `76.51 ms` + Swap-in `26.64 ms`，总耗时 `4645.1 ms`）几乎持平——验证了为什么 vLLM 对中短序列默认采用 **Recompute** 而非 CPU Swap。

### M2.4 Radix Prefix Cache（LRU vs LFU）与 Speculative Decoding（0.6B + 4B）
- **Radix Prefix Cache（热点 system prompt + 一次性扫描污染）**：
  - 无缓存：命中率 `0.0%`（0 tokens）；
  - **Radix LRU**：受扫描污染，命中率 `58.1%`（976 tokens，29 次淘汰）；
  - **Radix LFU（频率感知）**：保护热点前缀，命中率提升至 **`68.6%`**（1152 tokens，仅 18 次淘汰）。
- **Speculative Decoding（0.6B 584 MB Draft + 4B 3170 MB Target 同驻 16 GB 显存，$\gamma=4$）**：
  - Target-Only 基线：`2238.2 ms`（48 次 Target forward）；
  - 未对齐 0% 接受率 Draft：`11372.1 ms`（**0.20× 严重退化**）；
  - 模拟 75% 对齐（实测 BF16 下 33.3% 接受，Target 调用从 48 次降至 22 次）：`4564.6 ms`（**0.49×**）。
  - **极重要系统教训（串联 M1.3 与 M2.4）**：在 WSL2 Python Eager 模式下，24 层 0.6B Draft 每步也要付 ~45 ms 发核税（几乎和 24 层 4B Target 一样贵！），4 次 Draft 发核本身就花了 ~180 ms。因此投机解码想要真正跑出正加速，必须满足 $\gamma T_{\text{draft}} + T_{\text{verify}} < (1 + \mathbb{E}[\text{accept}]) T_{\text{target}}$——工程上必须结合 **CUDA Graph** 与 **极浅草稿头（如 EAGLE / Medusa / 4 层 Draft）**，而非直接用同等深度的 Eager 模型。
