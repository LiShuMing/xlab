# LLM Runtime

用于学习 LLM 推理执行、KV Cache 和请求调度的 Rust 实验项目。

**当前状态：仅目录与设计文档，尚无 Cargo crate、模型后端或可运行服务。**

## 项目目标

- 先用确定性 MockBackend 验证请求状态和资源生命周期。
- 接入 Candle CPU 后端，验证真实模型数值，再尝试 Metal。
- 从单请求和连续缓存逐步演进到批处理、分块缓存实验。
- 通过固定工作负载解释吞吐、延迟、缓存利用率的变化。

## 与 Python 项目的关系

[LLM Lab](../../../python/projects/llm-lab/README.md) 提供易读的计算参考，以及可选的模型权重和参考 logits。Rust 编译、启动和模拟实验不依赖 Python 环境；两边不通过 FFI 调用。

模型格式统一参考 Python 项目中的 [模型产物契约](../../../python/projects/llm-lab/docs/artifact-contract.md)。不要在 Rust 目录维护第二份格式定义。

## 目录

```text
llm-runtime/
├── README.md
├── ARCHITECTURE.md
├── AGENTS.md
├── TASKS.md
├── CHANGELOG.md
├── src/             # 预留：engine、scheduler、backend、cache
├── tests/           # 预留：生命周期、数值与资源测试
├── benches/         # 预留：调度和缓存基准
├── configs/         # 预留：模拟与真实后端配置
├── experiments/     # 固定请求轨迹与实验结论
└── docs/            # 设计决策记录
```

## 阶段

1. MockBackend + 单线程 Engine + FIFO。
2. Candle CPU + 单请求 prefill/decode + 连续 KV Cache。
3. 模型产物与 Python 参考对齐，Metal 可选验证。
4. 真正批量执行与连续 batching。
5. 分块缓存与前缀共享实验。

设计见 [ARCHITECTURE.md](ARCHITECTURE.md)，验收标准见 [TASKS.md](TASKS.md)。

## 环境与运行

计划使用 Rust 2021 和 Cargo，Candle 版本与 feature 在实现阶段验证后固定。当前不提供 cargo run/test 命令，因为尚无 Cargo.toml。

2026-09-19 本机检查记录：M4，10 核 GPU，16 GB 统一内存，支持 Metal。尚未验证 Rust 工具链和 Candle Metal；本机不是 CUDA 实验环境。

## 参考

- [Candle](https://github.com/huggingface/candle)：Rust 张量与模型后端。
- [nano-vLLM](https://github.com/GeeeekExplorer/nano-vllm)：推理运行时源码参考，不能假设其 CUDA 路径可在 Metal 原样运行。
- [llama2.c](https://github.com/karpathy/llama2.c)：底层推理计算参考。

## 非目标

第一版不做训练框架、分布式推理、CUDA kernel、HTTP 服务或生产部署。上游源码参考不等于本项目已经支持其全部能力。
