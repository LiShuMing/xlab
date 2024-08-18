# 第31章 LLM推理的系统视角

> 源码锚点：`mm/vmscan.c`、`mm/page_table_check.c`、`mm/ksm.c`、`kernel/sched/fair.c`

LLM推理是当前最重要的计算工作负载之一——它对内存带宽、显存容量和调度策略提出了前所未有的要求。从操作系统原理出发审视LLM推理，会发现推理引擎的许多设计与OS的经典机制异曲同工。

## 31.1 推理阶段的访存瓶颈

### 自回归生成的访存模式

LLM推理分两个阶段：

- **Prefill阶段**：并行处理输入token——计算密集(算力bound)，GPU利用率高
- **Decode阶段**：逐token自回归生成——每一步需读取全部模型权重，但只产生一个token的输出——访存密集(带宽bound)

Decode阶段的瓶颈：生成一个token需读取全部模型参数(如70B模型需140GB)，但只产生几个字节的输出。这本质上是**带宽bound**——GPU的算力远未饱和。

### Memory Wall

模型参数量增长速度远超内存带宽增长——2018年的BERT有3.4亿参数，2024年的Llama-3有700亿参数，但HBM带宽只增长了约3倍。这就是Memory Wall。

> **OS映射**：与Page Cache的命中率问题本质相同——工作集(模型参数)远大于缓存容量(GPU HBM)，每次访问都miss。OS解决此问题的方法是分层(DRAM+SSD)，LLM推理也需要分层(HBM+DDR+SSD)。

## 31.2 KV Cache管理

### KV Cache的本质

KV Cache是每个请求的注意力缓存——存储Transformer每层的Key和Value矩阵，避免重复计算：

```
KV Cache大小 = 2 × layers × heads × dim × seq_len × sizeof(float16)
Llama-3 70B: 2 × 80 × 64 × 128 × seq_len × 2 ≈ 2MB per token
```

多请求并发的KV Cache随batch size线性增长——80GB HBM只能支持约40K token的KV Cache。

### PagedAttention：分页显存管理

vLLM的PagedAttention将KV Cache分为固定大小的Block——与OS的分页系统异曲同工：

| OS分页 | PagedAttention |
|--------|---------------|
| Page(4KB) | KV Block(如16 token) |
| Page Table | Block Table |
| 虚拟地址连续 | 逻辑序列连续 |
| 物理页不连续 | 物理Block不连续 |
| 外部碎片消除 | 外部碎片消除 |

传统KV Cache为每个请求预分配最大长度的连续显存——大量浪费(实际序列通常远短于最大长度)。PagedAttention按需分配Block——类似OS的按需分页，只为实际使用的序列长度分配物理页。

`mm/page_table_check.c`的页表检查机制提供了启发——OS通过检查确保页表映射的物理页不被重复使用。PagedAttention的Block Table也需要类似的一致性检查——防止同一Block被分配给两个请求。

### KV Cache换出

当GPU HBM不足时，将部分KV Cache换出到CPU内存——GPU显存的swap：

| OS swap | KV Cache swap |
|---------|--------------|
| DRAM → SSD | HBM → DDR |
| 换入时缺页中断 | 换入时PCIe传输 |
| 换出选择LRU | 换出选择最久未访问的请求 |

换出的代价：PCIe带宽约64GB/s——远低于HBM的3TB/s。换出过多会严重增加延迟。

### 前缀缓存(Prefix Caching)

多个请求共享相同的系统提示(system prompt)——这些提示的KV Block可以复用：

| OS KSM | 前缀缓存 |
|--------|---------|
| 相同页面合并 | 相同前缀KV Block共享 |
| COW保护 | 引用计数保护 |
| `mm/ksm.c` | PagedAttention Block复用 |

`mm/ksm.c`通过内容哈希找到相同页面并合并——前缀缓存通过前缀哈希找到相同前缀并共享Block。

## 31.3 连续批处理(Continuous Batching)

### 从静态到连续

传统静态批处理：一组请求同时开始、同时结束——短请求被长请求拖慢。

连续批处理(Continuous Batching)：每个decode iteration可以加入新请求、移出已完成的请求——类似OS的调度：

| OS调度 | 连续批处理 |
|--------|-----------|
| 进程 | 请求 |
| 时间片 | decode iteration |
| 进程完成退出 | 请求完成移出batch |
| 新进程加入 | 新请求加入batch |
| CFS公平调度 | SLO感知调度 |

### CFS类比

`kernel/sched/fair.c`的CFS调度器为每个进程维护虚拟运行时间——调度vruntime最小的进程。连续批处理可以类似地维护每个请求的"等待时间"——优先调度等待最久的请求，确保公平性。

Orca调度器的思路：优先调度KV Cache未换出的请求——避免换出/换入的延迟开销。类似CFS的cache-aware调度——优先调度数据在cache中的进程。

## 31.4 推理引擎的内存管理

### KV Cache回收策略

当KV Cache占用接近显存上限时，需要选择哪些请求的KV Cache回收：

- **LRU**：回收最久未访问的KV Block——类似`mm/vmscan.c`的LRU回收
- **热度感知**：保留最近生成的token的KV Block——这些token可能被后续attention引用
- **工作集估计**：`mm/workingset.c`的refault距离概念——预测哪些KV Block被回收后最可能再次需要

### vLLM的PagedAttention实现

vLLM维护一个Block分配器——空闲Block池+已分配Block的引用计数：

```
Block分配：从空闲池取Block → 加入请求的Block Table
Block释放：请求完成 → Block引用计数减1 → 计数为0 → 归还空闲池
Block共享：前缀缓存 → 引用计数 > 1 → 不能释放
```

这与OS的页面分配器(`mm/page_alloc.c`)和页表管理的逻辑完全一致。

## 31.5 Speculative Decoding的系统视角

Speculative Decoding用小模型猜测多个token，大模型并行验证：

```
小模型猜测：token1, token2, token3, token4
大模型验证：✓, ✓, ✓, ✗ → 接受前3个，从第4个重新生成
```

> **OS映射**：与CPU分支预测的类比——CPU的分支预测器猜测分支方向，猜测正确则流水线满载，猜测错误则清空流水线重新执行。Speculative Decoding是"语言模型的分支预测"——猜测正确则加速生成，猜测错误则回退重试。

---

本章建立了LLM推理与OS机制的映射：Memory Wall与Page Cache命中率问题同构，PagedAttention是OS分页的GPU显存版本，连续批处理是CFS调度的推理版本，KV Cache回收是页面回收的推理版本。OS的智慧不仅适用于通用计算——在AI推理中同样适用，因为问题的本质相同：在有限资源下高效服务多个并发请求。
