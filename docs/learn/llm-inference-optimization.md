---
created: 2026-03-27
topics: [llm, inference, performance]
projects: []
review: 2026-03-30
stage: active
---

# LLM Inference Optimization

## Overview

Optimizing LLM inference involves balancing throughput, latency, and cost. Key challenges arise from the autoregressive nature of generation.

**Core Problem:** Each token depends on previous tokens → sequential generation.

**Optimization Goals:**
- Reduce time-to-first-token (TTFT)
- Reduce time-per-output-token (TPOT)
- Increase throughput (tokens/sec)
- Reduce memory usage

## Key Concepts

### 1. KV Cache

**Problem:** Attention computation is O(n²) and recomputes for each token.

**Solution:** Cache Key and Value tensors from previous tokens.

```
Without cache: O(n²) per token
With cache: O(n) per token (only new token)

Memory: 2 × num_layers × num_heads × head_dim × seq_len × batch_size × bytes
       = 2 × 32 × 8 × 128 × 4096 × 1 × 2 = 1GB for 4K context
```

**Optimizations:**
- PagedAttention (vLLM): Block-based allocation, reduce fragmentation
- Multi-query attention (MQA): Share K/V across heads
- Grouped-query attention (GQA): Middle ground

### 2. Batching Strategies

| Strategy | Description | Best For |
|----------|-------------|----------|
| Static batching | Fixed batch size | Uniform workloads |
| Dynamic batching | Add requests when possible | Variable load |
| Continuous batching | Add/remove during generation | Max throughput |
| In-flight batching | NVIDIA TensorRT-LLM | GPU utilization |

**Continuous Batching (Orca/vLLM):**
```
Time →
Req1: [=======]
Req2:  [===]
Req3:    [========]
Req4:       [====]

Requests join/leave as they complete, not at batch boundaries
```

### 3. Quantization

| Method | Bits | Accuracy Loss | Speedup |
|--------|------|---------------|---------|
| FP16 | 16 | Baseline | 1x |
| INT8 | 8 | Minimal | 1.5-2x |
| INT4 (GPTQ) | 4 | Small | 2-3x |
| AWQ | 4 | Small | 2-3x |
| GGUF | 4-8 | Small-medium | 2-4x |

**Trade-offs:**
- Lower bits = faster, less memory
- But: activation quantization harder than weight quantization
- AWQ/GPTQ protect "salient" weights

### 4. Speculative Decoding

**Idea:** Use small draft model to predict tokens, verify with large model.

```
Draft model (fast): predicts tokens 1,2,3,4,5
Target model: verifies all in parallel
Accept: 1,2,3  Reject: 4,5
Continue from 4

Speedup: 2-3x depending on acceptance rate
```

**Variants:**
- Medusa: Multiple draft heads
- Lookahead decoding: N-gram based
- EAGLE: Enhanced with attention

## System Implementations

### vLLM

**Key Innovation:** PagedAttention

```python
# Block-based KV cache management
# Like OS virtual memory: allocate blocks as needed
# Reduces fragmentation, enables sharing

from vllm import LLM

llm = LLM(model="meta-llama/Llama-2-7b")
output = llm.generate("Hello, world!")
```

**Features:**
- Continuous batching
- PagedAttention
- Tensor parallelism
- Pipeline parallelism

### TensorRT-LLM (NVIDIA)

**Optimizations:**
- Kernel fusion
- FP8 support (Hopper)
- In-flight batching
- Speculative decoding

### llama.cpp

**Focus:** Edge/CPU inference

**Features:**
- GGUF format
- Multiple backends (CUDA, Metal, Vulkan)
- Quantization focus
- Cross-platform

## Performance Analysis

### Metrics

| Metric | Definition | Target |
|--------|-----------|--------|
| TTFT | Time to first token | < 100ms |
| TPOT | Time per output token | < 50ms |
| Throughput | tokens/sec | Maximize |
| Latency | End-to-end time | Minimize |

### Bottlenecks

**Prefill Phase (first token):**
- Compute-bound: Attention O(n²)
- Optimize: FlashAttention, fused kernels

**Decode Phase (subsequent tokens):**
- Memory-bound: KV cache bandwidth
- Optimize: Quantization, better caching

## My Learning Path

### Phase 1: Understanding ✅
- [x] KV cache concept
- [x] Batching strategies
- [x] Quantization basics

### Phase 2: Hands-on 🔄
- [ ] Run vLLM locally
- [ ] Benchmark different batch sizes
- [ ] Compare FP16 vs INT8

### Phase 3: Deep Dive 🔴
- [ ] Read vLLM PagedAttention paper
- [ ] Understand CUDA kernels
- [ ] Implement simple optimizations

## Connections

### Related Topics
- [Transformer Architecture](./transformer.md)
- [GPU Programming](./gpu-programming.md)
- [Performance Benchmarking](./benchmarking.md)

### Projects
- Could optimize py-radar's LLM calls
- Future: Build simple inference server

### Readings
- [vLLM Paper](../read/papers/vllm-pagedattention.md)
- [FlashAttention](../read/papers/flashattention.md)
- [Continuous Batching](../read/papers/continuous-batching.md)

## Resources

### Papers
- Efficient Memory Management for Large Language Model Serving with PagedAttention
- FlashAttention: Fast and Memory-Efficient Exact Attention
- Speculative Decoding: Leveraging Speculative Execution for Accelerating LLM Inference

### Code
- [vLLM](https://github.com/vllm-project/vllm)
- [TensorRT-LLM](https://github.com/NVIDIA/TensorRT-LLM)
- [llama.cpp](https://github.com/ggerganov/llama.cpp)

## Review Log
- 2026-03-27: Created from AI learning plan
