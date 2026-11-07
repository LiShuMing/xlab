# LLM Lab Architecture

状态：v0.1 已实现 CPU/MPS 训练、恢复和无缓存生成。KV Cache、跨语言导出仍为设计。当前运行配置为 2 层、64 维、context 64，4 层/128 维作为后续配置建议。

## 目标与边界

实现可读、可验证的小型 decoder-only 语言模型，建立训练到推理的完整计算基线。第一版只做字节 tokenizer、bigram 和 Tiny Transformer；不包含分布式训练、RL、RAG、聊天 UI 或生产服务。

## 数据流

```text
文本 → 数据划分 → tokenizer → token batches → model → loss → optimizer
                                             ↓
                                  checkpoint / evaluation
                                             ↓
prompt → tokenizer → prefill → decode → sampling → output tokens
```

数据集先按文档划分训练/验证集，再生成窗口，避免重叠窗口跨集合泄漏。训练目标为右移一位的 next-token prediction；padding 不参与 loss。

## 模块职责

| 模块 | 职责 |
| --- | --- |
| `tokenizer.py` | UTF-8 字节与特殊 token 编码；不隐式插入 BOS/EOS |
| `data.py` | 文档划分、窗口构造、batch 与数据校验值 |
| `model.py` | Bigram 与 Tiny Transformer，显式因果遮罩 |
| `train.py` | 优化器、训练步、验证、随机数状态与恢复 |
| `checkpoint.py` | 已实现原子本地检查点；推理产物导出待实现 |
| `generate.py` | 已实现无缓存生成、EOS、长度与上下文容量结束 |
| `kv_cache.py`（规划） | 每层 K/V、有效长度、容量检查 |
| `train.py:evaluate` | 已实现固定验证集、按非 PAD token 加权的 loss；perplexity 后续增加 |
| `cli.py` | 配置解析与命令入口，不包含计算逻辑 |

先实现具体函数和类，存在第二种实现后再决定是否抽象。

## 第一版 Transformer

- 初始建议：4 层，hidden size 128，4 个 attention heads，FFN size 512，context 128。
- Pre-LayerNorm；学习式绝对位置编码；GELU FFN；最终 LayerNorm。
- Q/K/V 和输出投影使用显式权重；第一版关闭 dropout，不共享 embedding 与 LM head 权重。
- FP32 CPU 是数值参考，MPS 是可选执行设备；不可用时显式报告，不静默改变性能实验设备。
- 初始 batch size 8，按内存与耗时实测调整。这些数值是起步配置，不是性能承诺。

## 训练与推理状态

训练检查点保存模型、优化器、训练步、配置、数据版本和相关随机数状态。只加载可信的本地训练检查点。跨语言推理产物使用 safetensors，不要求 Rust 读取 Python pickle。

Prefill 建立每层缓存并输出预测下一个 token 的 logits。Decode 消费新 token，以缓存有效长度作为位置偏移，写入新 K/V 后输出下一步 logits。上下文溢出先返回明确错误，不隐式截断或滚动缓存。

## 验证策略

- tokenizer 字节往返、特殊 token 和非法 ID。
- 修改未来 token 不影响此前位置 logits。
- 小型合成数据可过拟合；独立验证集与 bigram 对照。
- 检查点重载前后 logits 一致；CPU 下恢复下一训练步与连续运行对照。
- 缓存/无缓存逐步 logits 一致，覆盖多种 prompt 长度及容量边界。
- Python/Rust 比较 token ID、张量 shape、完整 FP32 logits 和误差报告。

误差阈值必须在实验前固定。不同设备不要求 bitwise 相同；采样文本相同不能替代数值验证。

## 实验记录

记录代码 commit、依赖版本、配置、数据哈希、设备、dtype、随机种子、预热次数、重复次数和原始测量。GPU 计时需在测量边界同步，分别报告 prefill、decode、端到端时间；不把 Mac 数值外推为 CUDA 性能。

产物格式以 [artifact-contract.md](docs/artifact-contract.md) 为准。

## v0.1 实现细节

内置 synthetic-v1 含 64 个不同英文合成文档；固定种子分配训练/验证文档，窗口不跨文档。PAD 忽略损失；无 dropout，AdamW 与梯度裁剪。CPU batch generator、CPU Torch RNG、优化器和训练步写入检查点，恢复要求模型、数据、batch size 和学习率一致。没有 CUDA 或分布式后端。训练计时包含 Python 调度和定期 loss 读取，且同步 MPS；当前是单次链路验收，不是严谨的跨设备性能基准。
