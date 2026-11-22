---
created: 2026-11-21
topics: [llm, inference, gpu, cuda, triton, scheduling, roofline]
projects: [labs/gpu-kernel, labs/infer-engine, labs/llm-observability, labs/raylab, labs/k8s-lab]
stage: active
---

# 单卡 GPU 推理与四层 GPU 调度实验设计

> **定位**：基于当前单卡 **RTX 5070 Ti（16 GB GDDR7, Blackwell `sm_120`）** 硬件约束与 `xlab` 既有实验资产，设计一套可持续演进的「LLM 推理执行 + GPU 调度」实验体系，明确分层边界、核心约束、选型决策、正确性验证不变量与分阶段里程碑。
>
> **分工**：本篇收纳跨 lab 的总体约束、设计取舍与实验契约；基础概念总览见 [LLM 推理优化](llm-inference-optimization.md)，多租户 AI 平台题解见 [多租户 AI 平台](ai-platform-design.md)，长期个人进度跟踪见 [AI 学习计划](../notes/ai-learning-plan.md)。

---

## 一、核心结论与决策树

### 1.1 三个先决结论

1. **单卡 16 GB + 高带宽已覆盖 85% 的核心问题**：实测 RTX 5070 Ti 显存带宽约 **725.8 GB/s**、BF16 算力约 **91.4 TFLOPS**（算术强度拐点 **≈ 126 FLOPs/Byte**）。在 **0.6B–8B** 模型规模下，Roofline 瓶颈、算子融合、CUDA Graph、Paged KV Cache、Continuous Batching、Chunked Prefill、Prefix Cache、Speculative Decoding 与单卡 MPS 共享干扰全部可以**真机实测**，无需依赖大集群。
2. **多卡与集群调度靠「真实控制面代码 + 确定性仿真」闭环**：单卡没有 NVLink、多机 RDMA 与硬件 MIG，不强行用单卡数字外推多卡通信；而是把集群调度算法（Bin-packing、拓扑感知、Gang Scheduling、PD 分离与 KV-Aware 路由）直接写进 [labs/k8s-lab/](../../labs/k8s-lab/README.md) 与确定性轨迹重放器，攒够 2–3 个明确假设后再按小时租多卡集中校准。
3. **复用数据库内核的心智模型，不做黑盒调参**：推理引擎本质上是「GPU 时代的查询执行引擎 + Buffer Pool + Workload Manager」。每个实验必须先算理论物理上限，再做最小实现与量化对照，最后以可复现测试和离线报告收口。

### 1.2 硬件约束与实测基线（2026-11-21 实测）

| 维度 | 实测规格 / 数值 | 设计约束与物理直觉 |
| --- | --- | --- |
| GPU | NVIDIA GeForce RTX 5070 Ti (`sm_120`, 70 SMs, **15.92 GiB** 可用 GDDR7) | 单卡适合 0.6B–4B BF16 或 4B–8B INT4/FP8；支持 0.6B + 4B 双模型同驻（投机解码） |
| 实测算力 | BF16 GEMM (`4096³`): **~91.4 TFLOPS** (`1.50 ms`) | Prefill 与大 batch（并发 token > ~128）进入 compute-bound |
| 实测带宽 | 256 MB 显存拷贝: **~725.8 GB/s** | 4B BF16（权重 ~8 GB）batch=1 decode 理论物理上限 ≈ **90 tok/s**（INT4 ≈ **360 tok/s**） |
| 实测 Roofline 拐点 | `91.4 TFLOPS / 725.8 GB/s ≈ 126 FLOPs/Byte` | 任何小于 ~128 并发 token 的 BF16 decode 优先优化访存与 launch 开销，而非堆算力 |
| 宿主环境 | WSL2 (`6.6.87`), Ryzen AI 9 HX 370 (12C/24T, AVX-512), **15 GiB RAM** | CPU KV Swap 与大模型加载受 15 GiB 宿主内存约束；不可假设无限 host memory |
| 工具链 | CUDA 13.3 (`nvcc 13.3.73`, `compute-sanitizer`), PyTorch `2.10.0+cu128`, Triton `3.6.0` (`sm_120` 已实测通过), `uv` | `nsys` / `ncu` 尚未安装完整套件，且 WSL2 下 `ncu` 硬件计数器受限；日常以 `torch.cuda.Event` + PyTorch Profiler (Chrome Trace) + 补装 `nsys` 为主 |

### 1.3 问题定位与实验选型决策树

```text
你要解决什么问题？
├─ 单算子/单步延迟远低于硬件理论上限（带宽利用率低、小 batch ITL 高）
│   ├─ 算术强度 < 126 FLOPs/B（RMSNorm/RoPE/Softmax/小 batch GEMV）
│   │   └─ 查访存次数与 kernel 融合 + 权重位宽 → 主线 A（labs/gpu-kernel/）
│   ├─ GPU 活跃占比低、Timeline 出现大量空泡（bubble）
│   │   └─ 查 Python/CPU launch 开销 → CUDA Graphs / 异步提交 → 主线 A & 主线 B
│   └─ 算术强度 > 126 FLOPs/B（长 prompt prefill / 大 batch）
│       └─ 查 FlashAttention tiling、Tensor Core 利用率 → 主线 A
│
├─ 单卡并发吞吐上不去 / 显存早早 OOM / 尾延迟（TTFT 或 P99 ITL）失控
│   ├─ 显存碎片高、并发数受限于最大序列长度预留
│   │   └─ Paged KV Cache + Block Manager → 主线 B（labs/infer-engine/）
│   ├─ 长 prompt 涌入阻塞正在 decode 的请求
│   │   └─ Continuous Batching + Chunked Prefill + Preemption → 主线 B
│   ├─ 多轮对话 / 共享 system prompt 重复计算 prefill
│   │   └─ Prefix Caching（Radix Tree + 淘汰策略对照）→ 主线 B（借鉴 labs/cache/）
│   ├─ 已知需要对齐生产基线、定位全链路（API→Scheduler→GPU）耗时
│   │   └─ Linux/NVML 可观测性 + vLLM/SGLang 对照压测 → 主线 C（labs/llm-observability/）
│   └─ batch=1 仍想突破显存带宽上限
│       └─ Speculative Decoding（0.6B Draft + 4B Target）→ 主线 B
│
└─ 多任务/多租户共享 GPU、资源碎片、多卡死锁或集群路由
    ├─ 单卡多进程并发共享与尾延迟干扰（noisy neighbor）
    │   └─ CUDA Stream 优先级 + NVIDIA MPS 实测 → 主线 D1 & labs/raylab/
    └─ 多卡拓扑、碎片整理、分布式作业死锁、PD 分离路由
        └─ Bin-packing / Gang Scheduling / KV-Aware Routing → 主线 D4（labs/k8s-lab/）
```

### 1.4 与数据库内核机制的概念对位

| 数据库内核机制 | 推理执行 / GPU 调度对应物 | 核心共性约束 |
| --- | --- | --- |
| Buffer Pool + Page Table | Paged KV Cache + Block Manager | 固定大小页块消除外部碎片；引用计数实现 COW 共享 |
| Buffer / Plan Cache 淘汰（LRU/W-TinyLFU/ARC） | Prefix Cache / RadixAttention 淘汰 | 扫描污染防护、热点保留与元数据维护开销权衡 |
| 向量化算子融合（减少中间物化） | Triton / CUDA Kernel Fusion + FlashAttention | 把多次全局内存（HBM/GDDR）读写压缩到片上 SRAM |
| Pipeline / Morsel 驱动执行 | Continuous Batching + Chunked Prefill | 细粒度切分长任务，避免队头阻塞（head-of-line blocking） |
| Workload Management / Admission Control | Token Budget、SLO 准入控制、Preemption | 在吞吐最大化与尾延迟（TTFT / P99 ITL）之间显式取舍 |
| 分布式查询资源预留 / 死锁避免 | Gang Scheduling（Coscheduling） | 多卡作业的原子资源分配，防止部分占位互等死锁 |

---

## 二、四条实验主线设计与验证边界

所有新建或扩展实验必须遵守 [labs/README.md](../../labs/README.md) 的隔离原则：每个 lab 自包含、独立 `.venv`、不跨 lab 相对路径引用、每次运行输出可复现报告到 `.local/`。

### 主线 A：`labs/gpu-kernel/` — 硬件 Roofline、CUDA/Triton 算子与执行模型

**解决的问题**：建立单卡硬件性能上限直觉，掌握 memory-bound 算子融合、Attention 分块、低比特反量化权衡与 CUDA Graph 延迟隐藏。

| 阶段 | 实验内容 | 关键代价与权衡（时间 / 显存 / 精度） | 适用与不适用边界 |
| --- | --- | --- | --- |
| A1 | **Roofline 标定**：扫 `(M, N, K)` 与 FP32/BF16/FP8 GEMM、显存读写拷贝 | 运行 < 1 分钟；显存 < 2 GB；无精度损失 | 反映单卡稳态上限；不代表 PCIe/多卡通信上限 |
| A2 | **Memory-bound 融合**：Triton + CUDA C++ 实现 Vector Add、Fused RMSNorm、Fused RoPE、Online Softmax | 把多 pass 读写降为单 pass，带宽利用率逼近 725 GB/s；FP32 累加保证数值稳定 | 仅对访存主导算子收益大；小张量下 launch 开销占比会掩盖带宽收益 |
| A3 | **Decode GEMV & 量化**：BF16 vs Weight-Only INT8/INT4（分 group scale） | 显存与权重读取减半至 1/4；需权衡反量化指令开销与精度漂移（per-channel / per-group） | 低 batch 带宽收益显著；大 batch compute-bound 时反量化开销可能使 INT4 慢于 BF16/FP8 |
| A4 | **Attention 演进**：Naive Attention → FlashAttention（Tiling + Online Softmax）→ PagedAttention Kernel | 显存从 $O(N^2)$ 降为 $O(N)$；Paged 版本引入 block table 间接寻址开销 | 单卡实测只覆盖单头/GQA 局部执行，不覆盖 Ring Attention 跨卡通信 |
| A5 | **CUDA Streams & CUDA Graphs**：对比 eager launch vs CUDA Graph capture 在小 batch decode 的延迟 | 消除每步大量小 kernel 的 CPU dispatch 延迟；Graph 需固定输入 shape（常用 bucket padding） | 动态变长输入需多图分桶（bucketing），会增加显存常驻与冷启动 capture 成本 |

**正确性与性能验证方式**：
- **数值对拍**：所有自定义 Triton/CUDA kernel 必须与 PyTorch FP32 参考实现逐元素对比（BF16 校验 `atol/rtol` + 最大绝对误差 + cosine similarity），并覆盖非 2 次幂长度、尾部 mask、极值输入（测试 softmax 防溢出）。
- **内存安全**：CUDA C++ kernel 通过 `compute-sanitizer --tool memcheck` 与 `racecheck` 零报错。
- **计时纪律**：必须先预热，再用 `torch.cuda.Event(enable_timing=True)` 记录纯 GPU 时间，另行记录墙钟时间以暴露 CPU launch 开销；禁止未 `synchronize()` 直接读墙钟。

**典型错误与反例**：
- *反例 1*：不预热 cuBLAS/Triton 编译缓存直接计时，把 30 ms 冷初始化误判成 0.6 TFLOPS。
- *反例 2*：只测 `batch=1` 的 INT4 加速就宣称“INT4 永远更快”，忽略 `batch=64+` 反量化指令打满 ALU 的性能反转。

---

### 主线 B：`labs/infer-engine/` — 从零实现的单机迷你推理引擎（mini-vLLM）

**解决的问题**：打通「请求入队 → 批调度 → 页式 KV 显存管理 → 前向计算 → 采样 → 抢占/前缀复用」全链路，避免停留在调用现成引擎的 API 层。优先复用 [labs/reasoning-lab/](../../labs/reasoning-lab/README.md) 已验证的手写 Qwen3 权重加载思路，但面向 **CUDA + 并发服务** 独立实现。

| 阶段 | 实验内容 | 关键代价与权衡 | 适用与不适用边界 |
| --- | --- | --- | --- |
| B1 | **Static KV Cache 基线**：预分配 `[num_layers, 2, max_batch, num_kv_heads, max_len, head_dim]`，对比 concat KV | 消除每步 `torch.cat` 拷贝与显存分配器抖动；缺点是按 `max_len` 预留导致严重内部碎片 | 仅适合单请求或定长离线批；在线变长服务浪费 > 60% KV 显存 |
| B2 | **Paged KV + Block Manager**：固定 block size（如 16 tokens）、逻辑页表、物理块空闲链表、引用计数与 COW | 把碎片压到单请求最后一个未满 block（< 4%）；增加页表维护与 kernel 间接寻址复杂度 | 单机显存内闭环；不涉及跨机 KV 传输 |
| B3 | **Continuous Batching + Chunked Prefill + Preemption**：Waiting/Running/Swapped 三队列、`max_num_batched_tokens` 预算、Recompute vs CPU Swap | 显著提高吞吐并平滑 P99 ITL；Chunked Prefill 会略微拉长超长 prompt 的 TTFT；CPU Swap 受 WSL2 15 GiB RAM 与 PCIe 带宽限制 | 抢占阈值过紧会导致抖动（thrashing），需实测不同到达率下的拐点 |
| B4 | **Prefix Caching（Radix Tree）**：按 token block 哈希建前缀树，直接迁移 [labs/cache/](../../labs/cache/README.md) 的 LRU / W-TinyLFU / ARC 策略对比淘汰效果 | 共享 system prompt / 多轮对话下 TTFT 大幅下降；需额外树索引内存与哈希校验成本 | 一次性无复用请求（one-hit wonder）下收益为零，甚至增加元数据开销 |
| B5 | **Speculative Decoding**：Qwen3-0.6B（Draft）+ Qwen3-4B（Target）同驻 16 GB 显存，对比代码/数学/自由文本负载 | 低 batch 下通过把多次串行 decode 转为一次并行 verify 突破带宽墙；接受率低时反而因草稿开销变慢 | 仅在 memory-bound（低并发）区间显著加速；高并发已 compute-bound 时收益消失 |

**正确性与性能验证方式**：
- **Token-level Parity（对拍）**：固定 greedy decoding（`temperature=0`），Static KV、Paged KV、Continuous Batching（混排不同长度请求）、Chunked Prefill、Prefix Cache 命中路径的输出 token 序列必须与 HuggingFace / 单条 eager 参考实现 **100% 逐 token 一致**。
- **资源不变量**：每轮调度后断言 `allocated_blocks + free_blocks == total_blocks`、`refcount >= 0`、请求结束后所有 block 归零释放（允许 prefix cache 常驻块位于可回收集合）。
- **投机解码分布无损检验**：验证拒绝采样实现满足目标分布不变性（统计验证 + 边界概率单测）。

**典型错误与反例**：
- *反例 1*：只看总输出 `tokens/s` 不看 **Goodput**（同时满足 TTFT 与 TPOT SLO 的有效吞吐），把严重超时的请求也算进高吞吐。
- *反例 2*：Continuous Batching 混跑时未正确处理不同序列的 position_ids / causal mask，导致生成结果看似通顺但 logits 已偏移。

---

### 主线 C：生产引擎对照与 Linux/CUDA 可观测性（扩展既有 Lab）

**解决的问题**：用同一套监控与压测框架，把自研 `infer-engine` 与生产级 **vLLM / SGLang** 拉到同一标尺下对比，补齐 [labs/llm-observability/](../../labs/llm-observability/README.md) 在 Linux + NVIDIA GPU 侧的平台缺口。

| 扩展目标 | 具体改动 | 关键边界声明 |
| --- | --- | --- |
| [labs/llm-observability/](../../labs/llm-observability/README.md) | 1) 为 host exporter 增加 Linux + `pynvml` 采集（SM 利用率、显存使用、功耗、温度）<br>2) 独立 `uv` 环境跑 CUDA vLLM/SGLang，打通 `/metrics` + OTel 请求链路 + Jaeger UI | host span 与中间件计时**不冒充**纯 GPU kernel 时间；kernel 细分依赖 PyTorch Profiler / `nsys` |
| [labs/llm/bench/](../../labs/llm/bench/README.md) | 新增在线并发负载压测器（泊松到达率 $\lambda$、固定随机种子、混合长短 prompt 分布），输出 TTFT / TPOT / ITL P50/P95/P99 与 Goodput 曲线 | 固定模型、上下文长度、采样参数与预热策略；分开记录冷启动与稳态数据 |

---

### 主线 D：四层 GPU 调度（单卡实测 + 扩展 `raylab` 与 `k8s-lab`）

把“GPU 调度”拆成四个正交层次，避免把驱动共享、引擎排程、Ray 资源记账和 K8s 集群调度混为一谈：

| 调度层次 | 载体 | 核心实验内容 | 权衡与边界 |
| --- | --- | --- | --- |
| **D1 硬件 / 驱动层** | `labs/gpu-kernel/` 或 `labs/infer-engine/` 配套脚本 | 1) CUDA Stream 优先级抢占行为实测<br>2) 开启/关闭 **NVIDIA MPS**（`cuda-mps-control`）双进程并发，测总吞吐提升与高优进程 P99 尾延迟劣化（noisy neighbor） | RTX 5070 Ti **不支持硬件 MIG**；MPS 仅共享计算与部分显存配额，不提供故障隔离与带宽硬隔离 |
| **D2 单机引擎层** | `labs/infer-engine/`（与主线 B3 合并） | Prefill-first vs Decode-first vs Chunked Prefill；基于队列深度与剩余 KV 块的 SLO 准入控制 | 过度保守的准入控制降低利用率；过度激进触发频繁抢占与尾延迟雪崩 |
| **D3 Ray 分布式运行时层** | 扩展 [labs/raylab/](../../labs/raylab/README.md) | 1) 将 `02_logical_gpu` 升级为真实 RTX 5070 Ti 的 fractional GPU（`num_gpus=0.5`）实测，验证**逻辑配额 ≠ 显存硬隔离**及 OOM 触发条件<br>2) 增加 Ray Serve 动态批处理、反压与副本扩缩容延迟实验 | 单机单卡只能验证逻辑记账与同卡争用；跨节点弹性扩容仍以 `06_autoscaler` 状态机仿真为主 |
| **D4 K8s 集群调度层** | 扩展 [labs/k8s-lab/](../../labs/k8s-lab/README.md) | 补齐 `internal/scheduler`（纯 Go，零外部依赖）：<br>1) **多卡节点与拓扑建模**：卡数、显存、NVLink/PCIe 拓扑、碎片指标<br>2) **Filter / Score 插件**：Bin-packing（减少整卡碎片）vs Spread、拓扑亲和<br>3) **Gang Scheduling（Coscheduling）**：PodGroup 原子预留，复现部分占位死锁并验证回滚/排队解法<br>4) **PD 分离 + KV-Cache-Aware Routing 模拟器**：沿用 `labs/cache/` 的确定性轨迹重放，对比 Round-Robin、Least-Loaded、Prefix-Aware 路由 | 纯进程内仿真，不声称代表真实网络延迟或真实 kubelet 设备插件（DRA/Device Plugin）开销；重点验证算法正确性、公平性、碎片率与并发竞态 |

**调度层正确性验证不变量（D4 `k8s-lab`）**：
- `go test -race ./...` 零竞态；
- **容量守恒**：任意时刻每个节点已绑定 GPU 总量 ≤ 节点容量，同一物理 GPU ID 不被互斥作业重复分配；
- **Gang 原子性**：任一 PodGroup 要么全部 Pod 拿到同一批预留资源进入调度，要么零占用（回滚并退回队列），在双大作业交替到达的对抗用例下不发生永久死锁；
- **碎片率确定性回归**：固定随机种子轨迹下，验证 Bin-packing 相对 Spread 对大卡（如 8 卡）作业接纳率的提升。

---

## 三、单卡边界与多卡验证策略（诚实声明）

| 问题域 | 本机 RTX 5070 Ti 能否直接实测 | 不能实测时的补齐手段 |
| --- | --- | --- |
| Roofline、算子融合、量化交叉点、Flash/PagedAttention、CUDA Graph | **能**（真机） | — |
| Paged KV、Continuous Batching、Chunked Prefill、Prefix Cache、Speculative Decoding | **能**（0.6B–8B 模型真机） | — |
| 单卡多进程并发干扰（NVIDIA MPS）、Ray fractional GPU 显存争用 | **能**（真机） | — |
| 硬件 MIG 强隔离 | **不能**（消费级 GPU 无 MIG） | 文档对照数据中心卡（A100/H100/B200）架构差异，不伪造实测数据 |
| 多卡 TP/PP/EP、NVLink vs PCIe AllReduce、跨机 PD 分离 KV 传输 | **不能**（单卡） | 1) 用 $\alpha\text{-}\beta$ 通信模型 + `k8s-lab` 调度/路由仿真推演<br>2) 积累 2–3 个明确待测假设后，按小时租 4×/8× GPU 实例集中做一次校准实验并归档 |

---

## 四、可持续推进节奏与里程碑

遵循 **每 1–2 周一个小闭环** 的工作流：

> **提出量化假设 → 写最小可运行实验（`labs/`）→ 对拍验证 + Profile 采数 → 沉淀反直觉结论并勾选里程碑（`docs/`）**

### Phase 1：硬件标定与算子直觉（预计 2 周）
- [x] **M1.1** 建立 [labs/gpu-kernel/](../../labs/gpu-kernel/README.md)，产出 RTX 5070 Ti 实测 Roofline 脚本与离线报告（steady-state VRAM 带宽 **792.7 GB/s**、BF16 GEMM **90.35 TFLOPS** / FFN **97.49 TFLOPS**、BF16 拐点 **114.0 FLOPs/Byte**，详见 [RESULTS.md](../../labs/gpu-kernel/RESULTS.md)）
- [x] **M1.2** 用 Triton + CUDA C++ 实现并对照 Fused RMSNorm / Online Softmax（通过 FP32/BF16 对拍与 `compute-sanitizer` memcheck/racecheck 0 errors；RMSNorm 达 **761.9 GB/s / 9.59×**，Triton Softmax 达 **766.1 GB/s / 9.89×**）
- [x] **M1.3** 固化 PyTorch Profiler Chrome Trace 流水线与 CUDA Graph 基准（`cuda_graph/bench_cuda_graph.py`），实测 24 层 decode 将 289 次 host launch 压至 1 次 `cudaGraphLaunch`，`qwen_0.6b_like B=1` 墙钟耗时 `14.05 ms → 1.60 ms`（**8.76×**），`qwen_4b_like B=1` `15.86 ms → 5.49 ms`（**2.89×**），全部 M1.1–M1.3 数据已聚合进统一离线交互报告（`make -C labs/gpu-kernel report`）

### Phase 2：单机迷你推理引擎闭环（预计 3–4 周）
- [x] **M2.1** 建立 [labs/infer-engine/](../../labs/infer-engine/README.md)，跑通 Qwen3 架构 Static KV vs Concat KV（7 条路径 100% FP32 token parity）
- [x] **M2.2** 实现 Paged KV Cache + Block Manager，实测并发上限提升 **4.75×**（8 → 38）、碎片率 **89.0% → 1.74%**，并通过全步块守恒不变量测试
- [x] **M2.3** 实现 Continuous Batching + Chunked Prefill + Preemption（Recompute `4620 ms` vs CPU Swap `4645 ms` 实测对照，记录 WSL2 Eager launch 税对分块的影响，详见 [RESULTS.md](../../labs/infer-engine/RESULTS.md)）
- [x] **M2.4** 实现 Radix Tree Prefix Caching（扫描污染下 LFU 命中率 **68.6%** vs LRU **58.1%**）与 0.6B+4B Speculative Decoding（12,000 次拒绝采样无损检验通过，并实测验证同等深度 Eager Draft 的 launch-bound 退化边界）

### Phase 3：生产引擎对照与 Linux/CUDA 可观测性（预计 2 周）
- [x] **M3.1** 扩展 [labs/llm-observability/](../../labs/llm-observability/README.md) 支持 Linux + NVIDIA GPU 指标（`exporter.py` 新增 `parse_nvidia_smi` 与 Linux `nvidia_smi` 探针，已在 RTX 5070 Ti 实测采样且 18/18 单测通过；*注：当前离线环境未装 vLLM/SGLang，待有网环境独立 `uv` 安装后对接*）
- [x] **M3.2** 扩展 [labs/llm/bench/](../../labs/llm/bench/README.md) 新增泊松到达在线负载压测器 `poisson_load.py`（支持 OpenAI SSE 与可插拔异步后端，输出 TTFT/TPOT/ITL P50/P95/P99 与双 SLO Goodput，3/3 单测通过）

### Phase 4：四层 GPU 调度闭环（预计 3 周）
- [x] **M4.1** 完成单卡共享与干扰实测（`labs/gpu-kernel/scheduling/bench_stream_contention.py`：CUDA Stream Priority 及双进程 Noisy Neighbor 实测 P99 尾延迟劣化 **2.30×**、`1.39 → 3.19 ms`，后台同时跑出 `59.4 TFLOPS`；*注：当前默认 pyenv 未装 `ray`，`raylab` 实卡运行待安装 Ray 后补测*）
- [x] **M4.2** 给 [labs/k8s-lab/](../../labs/k8s-lab/README.md) 新增纯 Go 零依赖 `internal/scheduler`（`apis.Node` 多卡拓扑、Bin-packing 0% 碎片 vs Spread 100% 碎片、NVLink 同岛亲和、原子 Gang Scheduling 防交替死锁回归与 `-race` 验证全绿）
- [x] **M4.3** 在 `labs/k8s-lab/internal/routing` 实现确定性轨迹重放模拟器，对照 RoundRobin / LeastLoaded / PrefixAware / PDDisaggregated（实测 PD 分离将 Decode P99 ITL 从 `55.0 ms` 压低至 **`15.0 ms`**，PrefixAware/PD 命中率提升至 `82.0%–83.7%`）

---

## 关联文档与代码入口

- 概念总览：[LLM 推理优化](llm-inference-optimization.md)
- 平台级架构题：[多租户 AI 平台](ai-platform-design.md)
- 数据库执行对位：[向量化执行](vectorized-execution.md)
- 面试题与能力地图：[learn-llm.md](../notes/learn-llm.md)
- 既有相关 Lab：[labs/llm/](../../labs/llm/README.md)、[labs/reasoning-lab/](../../labs/reasoning-lab/README.md)、[labs/llm-observability/](../../labs/llm-observability/README.md)、[labs/cache/](../../labs/cache/README.md)、[labs/raylab/](../../labs/raylab/README.md)、[labs/k8s-lab/](../../labs/k8s-lab/README.md)
