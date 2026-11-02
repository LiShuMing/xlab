from: https://github.com/liaokongVFX/LangChain-Chinese-Getting-Started-Guide

你是一个LLM AI大厂或者创业公司的AI技术工程师负责人，帮我梳理和准备AI 推理工程师 (Inference Engineer) 核心面试题，能够达到顶尖LLM大厂的工程师水平，并思考输出面试技巧；这个方向的本质，是在 GPU 上做极端的性能压榨。很多挑战与构建高性能分布式存储或计算引擎极为相似。


你是一个LLM AI大厂或者创业公司的AI技术工程师负责人，帮我梳理和准备AI Agent 工程师核心面试题
这个方向的本质，是构建一个高容错的状态机。用不确定的 AI 大脑，驱动确定的 API 和业务流。
## AI Infra
### Concepts
- vLLM
- PagedAttention
- 如何实现3D并行：
    - Tensor Parallelism
    - Pipeline Parlallelism
    - Sequence Pallelism

### Topic
#### GPU 内存管理
Q1：KV Cache 的内存是如何组织的？为什么会产生碎片？vLLM 的 PagedAttention 解决了什么问题？
Q2：一个 7B 模型（FP16）部署在单卡 80GB A100 上，KV Cache 最多能撑多长的上下文？请估算。

好的，这是一份系统性的 AI 推理工程师核心面试题梳理。我会把它组织成几个核心模块，每个模块配上典型题目和考察意图。以下按模块逐一展开。

---

## 模块一：GPU 内存管理

这是推理工程的第一道门。面试官要确认你真的理解显存是怎么用掉的，以及为什么 KV Cache 是核心瓶颈。

**典型题目：**

**Q1：KV Cache 的内存是如何组织的？为什么会产生碎片？vLLM 的 PagedAttention 解决了什么问题？**

考察意图：很多人知道 KV Cache 的存在，但不清楚它在显存里是连续 tensor 还是分散块，也不理解为什么序列长度不确定会导致预分配浪费。PagedAttention 类比操作系统虚拟内存分页，将 KV Cache 分成固定大小的 block，按需分配，从而把碎片率从 ~60% 降到 <4%。

**Q2：一个 7B 模型（FP16）部署在单卡 80GB A100 上，KV Cache 最多能撑多长的上下文？请估算。**

考察意图：考工程直觉。参数占用约 14GB，KV Cache = `2 × num_layers × num_heads × head_dim × seq_len × batch_size × 2 bytes`。对于 LLaMA-2-7B，每个 token 的 KV Cache 约 0.5MB（32层 × 2 × 32头 × 128维 × 2字节），剩余 ~66GB 能支撑约 130K token（batch=1），实际还要留给激活值和系统开销。

**Q3：Prefix Caching（Prompt Caching）的核心机制是什么？为什么能加速 TTFT？**

考察意图：系统提示（system prompt）在多轮对话中完全相同，如果每次都重算其 KV Cache 是浪费。通过哈希 prefix 并复用 block，可以把首 token 延迟从 O(n) 降到 O(1)。

---

## 模块二：并行策略与分布式推理

和分布式存储引擎相似，核心问题是：如何在多卡/多机上切割计算，同时最小化通信开销。

**Q4：Tensor Parallelism、Pipeline Parallelism、Sequence Parallelism 三者的切割粒度和通信模式分别是什么？各自的适用场景？**

这是高频题，要能画出数据流：

- **TP**：在 Attention 和 MLP 的权重矩阵上切列/行，每层都有 AllReduce，延迟敏感，适合单机多卡
- **PP**：按层切，micro-batch 流水线，气泡（bubble）是瓶颈，适合多机
- **SP**（Sequence Parallelism）：在序列维度切，配合 Ring Attention，适合超长上下文

**Q5：AllReduce 在推理 vs 训练中的性能特征有何不同？为什么 NVLink 带宽比 PCIe 对 TP 至关重要？**

**Q6：为什么大模型推理通常是 memory-bound 而不是 compute-bound？如何用 Arithmetic Intensity（AI 值）来分析？**

考察意图：这是所有性能优化的根基。矩阵向量乘（decode 阶段 batch=1）的 AI 极低（~1 FLOP/byte），远低于 A100 的 Roofline 拐点（约 200），所以受制于 HBM 带宽而非 CUDA Core。

---

## 模块三：调度与吞吐优化

这模块最像传统分布式系统面试，考察对请求排队、资源分配、SLO 保障的理解。

**Q7：Continuous Batching 相比 Static Batching 解决了什么问题？为什么能显著提升 GPU 利用率？**

核心在于：Static Batching 要等最长序列生成完才能释放槽位，导致短序列浪费等待。Continuous Batching 在 token 粒度上做 preemption 和 join，序列完成即释放，新请求即插即用。

**Q8：如何在延迟（TTFT/TBT）和吞吐（tokens/s）之间做 trade-off？如果 SLO 要求 P99 TTFT < 500ms，你的调度策略是什么？**

**Q9：Speculative Decoding 的原理是什么？draft model 和 target model 的分工如何？什么时候会退化？**

考察意图：用小模型快速生成 k 个候选 token，大模型并行验证，验证通过则 accept，否则从拒绝位置重采样。当 draft 和 target 的分布差距大时，接受率下降，反而比不用 spec decoding 更慢。

---

## 模块四：量化与模型压缩

**Q10：INT8、INT4、FP8 量化的精度损失来源分别在哪里？Weight-only 量化和 Weight+Activation 量化有什么根本区别？**

**Q11：GPTQ 和 AWQ 的核心思路各是什么？为什么 AWQ 在保留显著权重方面更有效？**

**Q12：量化后的模型在 decode 阶段是否一定更快？什么情况下 INT4 反而比 FP16 慢？**

考察意图：量化减少了 weight load 的带宽（memory-bound 下有效），但如果 dequantize 的 kernel overhead 大于节省的带宽，反而更慢。必须结合 batch size 和 GPU 架构分析。

---

## 模块五：CUDA 算子与内核优化

**Q13：FlashAttention 的核心优化是什么？为什么它能把 Attention 的内存复杂度从 O(n²) 降到 O(n)？**

关键词：tiling（分块计算）、online softmax（避免存储完整 attention score 矩阵）、融合 Q/K/V matmul + softmax + output 为单个 kernel，减少 HBM 读写次数。

**Q14：Kernel Fusion 的原理是什么？哪些算子适合 fuse，哪些不适合？**

**Q15：写一个 CUDA kernel 实现向量点积，并分析如何优化 warp 内的 reduce。**

---

## 模块六：系统设计

**Q16：设计一个支持 100 个不同 LoRA adapter 的推理服务，要求低延迟热切换，GPU 显存预算有限，你的方案？**

考察意图：S-LoRA 的核心问题——把 base model 常驻显存，adapter 按需换入，利用 unified paging 管理 adapter 权重，批内不同请求可以复用 base model 权重并行推理。

**Q17：一个 70B 模型要服务 1000 QPS，你如何做容量规划？需要多少 H100？**

**Q18：推理服务的监控指标你会关注哪些？TTFT、TBT、ITL、QPS、GPU Utilization 各自反映什么问题？**

---

## 加分：边界题（高级岗）

- MoE 模型推理中 expert routing 导致的 load imbalance 如何解决？
- 为什么 prefill 和 decode 阶段的性能特征完全不同，有些系统要把它们拆到不同的 worker 上（disaggregated prefill）？
- Ring Attention 如何扩展 context length 到单卡无法容纳的长度？通信隐藏的策略是什么？

---

**备考建议**：代码侧重 CUDA/Triton kernel 写法和 profiling（`ncu`、`nsys`）；系统侧重 vLLM、TensorRT-LLM 源码中的调度器和内存管理模块；理论侧重 Roofline 模型和通信分析（α-β 模型）。

对，这个方向的本质，确实可以理解为：

**在 GPU + 通信 + 内存带宽 + 调度约束下，做一套“极致压榨硬件”的在线执行系统。**

它和高性能分布式存储/计算引擎非常像，区别只是：

* 你过去压榨的是 CPU / Cache / NUMA / 磁盘 / 网络；
* Inference Engineer 压榨的是 **HBM / SM / Tensor Core / PCIe / NVLink / NCCL / KV Cache / 连续批处理**。

所以如果你要准备 **AI 推理工程师（Inference Engineer）核心面试题**，不要把它当成“模型岗”，而要把它当成：

**GPU 时代的 query engine / execution engine / serving system 工程师。**

下面我按“真正核心”的方式帮你整理。

---

# 一、面试官真正想考什么

这个岗位通常考 5 类能力：

## 1. 对推理系统全链路的理解

不是只会说 Transformer，而是要能说清：

* 请求进入服务后经历什么
* token 是怎么一步步生成的
* prefill 和 decode 有什么本质差异
* 吞吐、延迟、成本之间如何 tradeoff

## 2. 对 GPU 性能瓶颈的理解

核心不是“会用 CUDA API”，而是：

* 算力瓶颈还是带宽瓶颈
* 为什么 decode 往往 memory-bound
* 为什么 batch 变大不一定更快
* 为什么 kernel fusion 能提速

## 3. 对并发调度和系统设计的理解

这部分最像数据库：

* continuous batching
* request scheduling
* admission control
* memory management
* cache reuse
* fragmentation control

## 4. 分布式推理能力

模型大了以后，必考：

* tensor parallel
* pipeline parallel
* expert parallel
* data parallel in serving
* NCCL 通信瓶颈
* 跨机推理延迟

## 5. 工程落地与优化方法论

不是玄学调参，而是：

* profiling
* benchmark
* roofline 思维
* 定位瓶颈
* 设计实验
* 做取舍

---

# 二、最核心面试题清单

下面这些题，几乎就是这个方向的“主干”。

---

## A. 基础原理题：必须能讲透

### 1）LLM 推理的完整流程是什么？

你需要讲到：

* tokenizer
* embedding lookup
* Transformer block
* self-attention
* MLP
* logits
* sampling
* 生成下一个 token
* 循环迭代直到结束

进一步要讲：

* **prefill**：处理整段 prompt，计算所有历史 token 的 KV
* **decode**：每次只生成一个新 token，复用已有 KV cache

这是最重要的第一题。

---

### 2）prefill 和 decode 的区别是什么？为什么它们的优化方式不同？

标准回答要点：

* prefill 输入序列长、并行度高，通常更偏 **compute-bound**
* decode 每步只生成一个 token，但要读取大量历史 KV cache，通常更偏 **memory-bound**
* prefill 更适合大矩阵乘、提高 tensor core 利用率
* decode 更依赖 cache layout、memory access、batching、paged attention

这是高频题。

---

### 3）为什么 LLM 推理通常比训练更难做系统优化？

可以答：

* 训练是规则的大 batch dense compute，吞吐优先
* 推理请求长度不一、到达时间随机，在线服务更复杂
* 推理需要同时兼顾 TTFT、TPOT、吞吐、尾延迟、成本
* decode 是典型小步迭代、memory-bound，更难把 GPU 喂饱
* 还要处理 KV cache、动态 batching、取消请求、early stop、采样差异

---

### 4）Transformer 推理里最耗时/最耗资源的部分是什么？

分场景答：

* prefill 常常主要耗在 attention + GEMM/MLP
* decode 阶段往往 attention 的 **KV 读取** 非常贵
* 大模型场景中，**权重加载带宽、KV cache 占用、通信** 都可能成为主瓶颈

优秀回答不是说“attention 最贵”，而是说：
**不同阶段、不同 batch、不同并行策略下，瓶颈不同。**

---

## B. GPU / CUDA / 性能工程题：这是区分度最高的部分

### 5）GPU 上 kernel 性能受哪些关键因素影响？

你要讲：

* occupancy
* memory coalescing
* shared memory 使用
* register pressure
* warp divergence
* kernel launch overhead
* global memory vs shared memory vs register
* compute-bound vs memory-bound

---

### 6）怎么判断一个推理 kernel 是 compute-bound 还是 memory-bound？

应答要点：

* 看算术强度（FLOPs / bytes）
* 结合 roofline model
* 用 profiler 看 SM 利用率、memory throughput、tensor core utilization
* 若带宽接近上限但算力低，多半是 memory-bound
* 若 tensor core 很忙但带宽未满，可能 compute-bound

---

### 7）为什么 decode 阶段往往是 memory-bound？

要点：

* 每生成一个 token，都要访问所有历史 token 的 KV
* 计算量相对不大，但内存读写很多
* batch 小、矩阵形状不规则，tensor core 利用率不高
* 请求长度差异大，导致访存和调度都不够规整

---

### 8）什么是 kernel fusion？为什么它重要？

要点：

* 把多个小 kernel 合并成一个大 kernel
* 减少 kernel launch overhead
* 减少中间结果写回 global memory
* 提高 locality
* 提升吞吐和降低延迟

可以举例：

* bias + activation
* layernorm + residual
* attention 中的若干步骤融合

---

### 9）FlashAttention 为什么快？

这是必考高频题。

核心点：

* 不是减少理论 FLOPs，而是优化 **IO**
* 避免显式 materialize 巨大的 attention matrix
* 利用 tiling，把计算放在 SRAM/shared memory 中完成
* 降低 HBM 访问次数
* 提升带宽效率

如果面试官继续追问：

* 在线 softmax 怎么做
* 为什么数值稳定
* 对长序列为何收益大

---

### 10）什么是 Tensor Core？如何让 GEMM 跑得更快？

要点：

* Tensor Core 是 GPU 上专门做矩阵乘加的硬件单元
* 高吞吐依赖合适的数据类型和 tile shape
* 需要良好的矩阵布局、对齐、batch size、kernel 实现
* 实际中常靠 cuBLAS / CUTLASS / TensorRT-LLM / Triton 等实现高性能

---

## C. KV Cache / Memory 管理题：特别像数据库 buffer manager

### 11）什么是 KV Cache？为什么它重要？

标准回答：

* self-attention 中历史 token 的 K/V 可以复用
* decode 时不必每次重算历史 token 的 K/V
* 大幅降低重复计算
* 但会带来巨大的显存占用和管理复杂度

---

### 12）KV Cache 的大小大致怎么估算？

需要能给出近似公式：

对于某层：

* K 和 V 各一份
* 大小约为
  `2 × batch × seq_len × num_kv_heads × head_dim × dtype_size`

全模型再乘以层数。

优秀候选人会补一句：

* MQA / GQA 可以显著减少 KV cache 占用

---

### 13）PagedAttention 的核心思想是什么？解决了什么问题？

高频题。

要点：

* 不把每个请求的 KV cache 放成一个连续大块
* 而是分页管理，像虚拟内存一样分 block/page
* 解决外部碎片问题
* 提高显存利用率
* 支持动态增长和共享 prefix

这题和数据库页式存储、buffer pool、slab allocator 的类比很好讲。

---

### 14）KV Cache 会带来哪些工程问题？

要点：

* 显存占用大
* 长请求拖垮系统
* 碎片化
* prefix sharing 管理复杂
* 请求取消/结束后的回收
* 跨 batch 重排带来的索引复杂度
* 多 GPU 分片时 cache 路由问题

---

### 15）如何减少 KV Cache 的内存占用？

常见答案：

* MQA / GQA
* 量化 KV cache（INT8 / FP8 等）
* 限制最大上下文长度
* prompt caching / prefix sharing
* 及时回收 finished requests
* 分层 offload（GPU -> CPU）
* sliding window attention

---

## D. Serving / 调度题：最像 query scheduler

### 16）什么是 continuous batching？为什么比 static batching 更适合 LLM serving？

这题几乎必考。

要点：

* static batching 需要等一批请求凑齐再一起执行
* LLM 请求长度不一，静态批处理浪费严重
* continuous batching 允许请求动态加入/退出 batch
* 能提高 GPU 利用率和整体吞吐
* 但实现复杂，涉及调度、重排、KV 管理、采样差异

---

### 17）TTFT、TPOT、吞吐量分别是什么？三者如何 tradeoff？

你必须会：

* **TTFT**: time to first token
* **TPOT**: time per output token / inter-token latency
* **Throughput**: tokens/s 或 requests/s

tradeoff：

* 更大 batch 通常提升吞吐，但会恶化 TTFT
* aggressive packing 可能提升 GPU 利用率，但尾延迟变差
* 调度策略要按场景平衡交互性和成本

---

### 18）如果系统目标是降低 TTFT，你会怎么做？

可答：

* 提高 prefill 优先级
* 做 prompt cache / prefix cache
* 减少排队时间
* 使用更快 tokenizer / 更少前处理
* 将长短请求分队列
* 控制 batch 大小避免 prefill 被 decode 拖住
* 模型编译优化、warmup、减少 cold start

---

### 19）如果目标是提升吞吐，你会怎么做？

要点：

* 提高 batch 利用率
* continuous batching
* 优化 decode kernel
* 提升 KV cache 命中与复用
* 减少内存碎片
* 使用量化
* 张量并行/多实例部署
* 更激进的 admission control

---

### 20）长请求和短请求混跑会有什么问题？怎么解决？

像数据库里大查询和短查询混跑一样：

* head-of-line blocking
* TTFT 恶化
* 显存被长上下文请求占满
* 尾延迟变差

解决：

* 按 prompt 长度/生成长度分类队列
* reservation / quota
* prefill-decode 分离
* SRPT-like / priority scheduling
* 对超长请求限流或单独池化

---

## E. 分布式推理题：大模型必考

### 21）Tensor Parallel、Pipeline Parallel、Data Parallel 分别是什么？推理场景怎么选？

要点：

* **TP**：单层算子在多个 GPU 上切分，适合单卡放不下或追求层内并行
* **PP**：按层切分到不同 GPU，形成流水线
* **DP**：多份完整模型副本，各自处理不同请求

推理中：

* 小模型常用 DP + batch serving
* 大模型单卡放不下时常用 TP
* 超大模型可能 TP + PP + EP 混合

---

### 22）为什么 Tensor Parallel 会带来通信开销？

因为一层的计算被拆到多个 GPU：

* 中间激活需要 all-reduce / all-gather / reduce-scatter
* 通信和计算的 overlap 很关键
* GPU 间带宽和拓扑决定效果

---

### 23）NVLink、PCIe、InfiniBand 对推理有什么影响？

要点：

* GPU 间通信速度直接决定 TP/EP 效率
* 单机 NVLink 通常远快于 PCIe
* 跨机依赖 InfiniBand / RoCE
* 通信慢时，多卡并行反而可能不划算

---

### 24）什么情况下多 GPU 反而比单 GPU 更慢？

很好的区分题。

答案：

* 模型其实单卡能放下
* batch 太小，通信占比过高
* TP 切分过细
* 跨机延迟高
* kernel shape 变差
* pipeline bubble 明显
* 调度不合理导致 GPU 空转

---

### 25）MoE 模型推理的主要挑战是什么？

要点：

* token routing
* expert load imbalance
* all-to-all 通信
* expert cache locality
* batch 被打散
* 热 expert 过载
* 尾延迟变差

---

## F. 量化 / 模型压缩题：工业界非常常见

### 26）为什么量化能提升推理性能？

要点：

* 降低权重和激活占用
* 降低内存带宽压力
* 提高 cache / HBM 利用率
* 某些硬件上低精度算子吞吐更高

但要补充：

* 并非所有场景都线性加速
* 有时瓶颈在调度或 KV 访问，不在权重计算

---

### 27）INT8、FP8、INT4 的 tradeoff 是什么？

可答：

* 精度 vs 吞吐 vs 工程复杂度
* INT4 压缩更强，但可能带来更复杂 dequant 开销和精度损失
* FP8 常在硬件支持较好时更平衡
* 量化收益依赖 kernel、模型结构、硬件代际

---

### 28）量化后为什么不一定更快？

高质量回答要点：

* dequantization 开销
* kernel 未充分优化
* 小 batch 下 launch/调度占主导
* attention/KV cache 仍是瓶颈
* 通信瓶颈未变
* 某些层必须保持高精度

---

## G. 系统设计题：高级岗重点

### 29）设计一个高性能 LLM Serving 系统

面试官通常想听到这些模块：

* API gateway
* scheduler
* tokenizer / preprocessor
* model workers
* KV cache manager
* batch manager
* sampling module
* metrics / tracing
* autoscaling
* admission control
* model registry / rollout

如果你能再讲：

* prefix cache
* prefill / decode disaggregation
* multi-tenant isolation
* GPU memory defragmentation
* request cancellation
* backpressure
  就很强了。

---

### 30）如何定位线上推理服务变慢的问题？

很像查数据库 query latency。

思路：

* 看是 TTFT 变慢还是 TPOT 变慢
* 看 queueing time、prefill time、decode time
* 看 GPU utilization、memory bandwidth、NCCL 时间
* 看 batch 大小变化、请求长度分布变化
* 看是否 cache miss、碎片加重、长请求涌入
* 看模型是否换版本、sampling 参数是否变化

---

### 31）如何做推理系统 benchmark？

你要强调：

* 真实 workload 很重要
* 输入长度分布、输出长度分布、到达分布不能只看平均值
* 要区分 offline throughput benchmark 和 online latency benchmark
* 看 P50/P95/P99
* 看 tokens/s、TTFT、TPOT、cost/token
* 关注 warmup 和 steady state

---

### 32）如何做多租户隔离？

要点：

* quota / admission control
* per-tenant concurrency limits
* request priority
* memory reservation
* noisy neighbor control
* separate pools / virtual queues
* fairness vs utilization tradeoff

这题和数据库 resource group 很像。

---

# 三、最适合你的“类比讲法”

你如果去面试，完全可以把自己的数据库背景转成优势。

## 1）把 KV cache 类比成 buffer pool / page cache

* 关注容量
* 碎片
* 回收
* locality
* 复用
* prefix sharing 类似公共页复用

## 2）把 continuous batching 类比成 query scheduler

* 不同请求长度像不同 query cost
* 长短任务混跑导致 HOL blocking
* 需要 fair scheduling / priority / admission control

## 3）把 decode 优化类比成 vectorized engine 的热点内核优化

* 少分支
* 少访存
* 更好 locality
* fusion
* 减少 materialization

## 4）把 TP/PP/EP 类比成分布式执行 plan

* 本地算子快不代表全局快
* 通信代价决定并行收益
* operator placement 非常关键

这会让你和普通“只会背 LLM 八股”的候选人拉开很大差距。

---

# 四、面试官最喜欢追问的深水区

这些题很能拉开层次。

## 1）为什么 vLLM/PagedAttention 有价值？

因为真实 serving 不是理想固定 batch，而是动态请求流；核心问题不是单次 GEMM 快，而是 **如何在动态 workload 下维持高 GPU 利用率和高显存利用率**。

## 2）为什么很多推理系统优化最后都落到 memory 上？

因为 decode 阶段常常不是算不动，而是 **搬不动**。

## 3）为什么在线 serving 比离线 benchmark 难？

因为线上有：

* request arrival randomness
* variable sequence length
* cancellation
* SLO
* multi-tenancy
* tail latency
* fragmentation
* admission control

## 4）为什么“更大的 batch”不是银弹？

因为：

* TTFT 变差
* 尾延迟上升
* 显存压力上升
* 调度复杂度增加
* 请求异质性更强时 padding / idle 更严重

---

# 五、你可以重点准备的高质量回答模板

下面给你几个可以直接说出口的模板。

## 模板 1：怎么理解 Inference Engineer

> 我理解 Inference Engineer 本质上不是模型训练岗，而是面向在线请求的高性能执行系统工程师。核心目标是在 GPU、显存、通信和延迟约束下，把模型推理做成一个高吞吐、低延迟、可扩展、可观测的 serving system。它和高性能数据库执行引擎非常像，只是执行对象从 SQL operator 变成了 attention、MLP、sampling 和 KV cache management。

## 模板 2：为什么 decode 难优化

> Decode 的难点在于每一步只生成一个 token，算子规模小，但要访问大量历史 KV cache，所以它常常不是 compute-bound，而是 memory-bound。与此同时，请求长度又高度动态，导致 batch 形状不断变化，这让 GPU 很难始终保持高利用率。因此 decode 优化通常同时涉及 kernel、memory layout、continuous batching 和 cache 管理，而不是单点优化。

## 模板 3：如何看 serving 的核心指标

> 我会把指标拆成 TTFT、TPOT、throughput 和 cost/token。TTFT 反映首 token 响应，TPOT 反映交互流畅性，throughput 决定资源利用率，cost/token 决定商业可行性。实际系统优化本质上是在这几个指标之间找 Pareto frontier，而不是单纯追求某一个数字最大化。

---

# 六、如果要准备面试，建议按这个顺序学

## 第一层：必须会

* Transformer 推理流程
* prefill vs decode
* KV cache
* continuous batching
* TP/PP/DP
* TTFT / TPOT / throughput

## 第二层：高频进阶

* FlashAttention
* PagedAttention
* quantization
* NCCL / NVLink / PCIe
* roofline / memory-bound / compute-bound
* profiling 方法

## 第三层：拉开差距

* CUDA kernel 基础
* Triton / CUTLASS
* MoE serving
* prefix caching
* prefill-decode disaggregation
* 多租户调度与 admission control

---

# 七、如果把这套题变成“核心面试题大纲”

我建议你记成这 10 个母题：

1. LLM 推理流程与 prefill/decode 区别
2. 为什么 decode 往往 memory-bound
3. KV cache 的作用、开销与管理
4. continuous batching 的原理与收益
5. FlashAttention / PagedAttention 的核心思想
6. GPU kernel 性能瓶颈与 roofline 分析
7. TTFT / TPOT / throughput 的权衡
8. TP/PP/DP/EP 的适用场景与通信代价
9. 量化为什么有效、为什么有时无效
10. 如何设计和调优一个生产级推理系统

这 10 个题答透了，已经非常够打。

---

# 八、给你的判断

这个方向和你过去做的高性能数据系统，**不是转行，而是迁移战场**。

你过去练的是：

* execution engine
* scheduler
* memory manager
* distributed runtime
* profiling & optimization

而 Inference Engineer 的核心，恰好也是这些，只是名字换了：

* execution engine -> inference runtime
* scheduler -> batch/request scheduler
* buffer/cache -> KV cache manager
* exchange/network -> NCCL / all-reduce / all-to-all
* operator optimization -> attention / GEMM / fusion kernel

所以你是很适合切入这个方向的，而且你的优势不是“懂模型原理更多”，而是**更懂把一个复杂执行系统做实**。

你要的话，我下一步可以直接继续给你整理一版：

**《AI 推理工程师核心面试题 50 题 + 参考答案（偏系统/性能/分布式视角）》**。

## AI Agent
- LangChain
- LlamalIndex
- 向量数据库
- RAG
