# Python / Rust 模型产物契约

状态：`tiny-decoder-v1` 设计草案，尚无导出器或读取器。本文件是两个项目唯一的跨语言契约；改动需要同步两端实现和对照样本。

## 目录与版本

```text
bundle/
├── manifest.json
├── config.json
├── model.safetensors
├── tokenizer.json
└── reference/
    ├── cases.json
    └── logits.safetensors
```

`manifest.json` 包含 `format_version: 1`、`architecture: tiny-decoder-v1`、导出代码 commit、权重 dtype、各文件 SHA-256 与参考样本生成设备。未知版本、缺失文件、哈希不匹配必须拒绝加载。

## 模型配置与计算

`config.json` 必填字段：`vocab_size`、`context_length`、`num_layers`、`hidden_size`、`num_heads`、`ffn_size`、`layer_norm_eps`。要求 hidden_size 可被 num_heads 整除，所有维度为正。

v1 固定如下语义：

1. token embedding 加 learned absolute position embedding。
2. 每层：`x = x + attention(layer_norm_1(x))`；`x = x + ffn(layer_norm_2(x))`。
3. attention 使用 QK 转置乘积除以 `sqrt(head_dim)`、因果遮罩和 softmax；允许关注当前位置，不允许未来位置。
4. FFN 为线性层 → 精确 GELU（erf 形式）→ 线性层。
5. 最终 LayerNorm → LM head，返回未经过 softmax 的 logits。
6. LayerNorm 沿 hidden 维，方差分母为 hidden_size，epsilon 位于平方根内。
7. 所有线性层无 bias；LayerNorm 有 scale/bias；无 dropout；embedding 与 LM head 不共享权重。

## 权重名称与布局

所有权重以 FP32 导出；线性权重布局统一为 `[out_features, in_features]`。

| 名称 | Shape |
| --- | --- |
| `token_embedding.weight` | `[vocab_size, hidden_size]` |
| `position_embedding.weight` | `[context_length, hidden_size]` |
| `blocks.{i}.ln1.weight/bias` | 每个 `[hidden_size]` |
| `blocks.{i}.attn.q_proj.weight` | `[hidden_size, hidden_size]` |
| `blocks.{i}.attn.k_proj.weight` | `[hidden_size, hidden_size]` |
| `blocks.{i}.attn.v_proj.weight` | `[hidden_size, hidden_size]` |
| `blocks.{i}.attn.out_proj.weight` | `[hidden_size, hidden_size]` |
| `blocks.{i}.ln2.weight/bias` | 每个 `[hidden_size]` |
| `blocks.{i}.ffn.up.weight` | `[ffn_size, hidden_size]` |
| `blocks.{i}.ffn.down.weight` | `[hidden_size, ffn_size]` |
| `final_norm.weight/bias` | 每个 `[hidden_size]` |
| `lm_head.weight` | `[vocab_size, hidden_size]` |

`weight/bias` 表示两个独立键，不是字面文件键。层索引从 0 开始。head 按 hidden 维连续切分；Q/K/V 计算布局为 `[batch, heads, time, head_dim]`。缺失、额外或 shape 不匹配的权重均返回加载错误。

## Tokenizer

v1 使用自定义 `utf8-byte-v1`，不是 Hugging Face tokenizer.json 格式：字节 0–255 映射到相同 token ID；BOS=256、EOS=257、PAD=258，vocab_size=259。JSON 必须明确记录格式名称与版本。

编码不默认添加特殊 token；调用方显式决定。空 prompt 的生成入口插入 BOS。特殊 token 不输出为文本；非法 ID 返回错误。先拼接所有输出字节再做 UTF-8 解码，文本展示可使用 replacement character；数值对照以 token ID 为准。训练与生成对 PAD/BOS 的处理需显式配置，不通过改变参考 logits 隐藏这些 token。

## 参考数据

`cases.json` 保存唯一 case ID、输入 token IDs、追加 token IDs、张量键和预先指定的 atol/rtol。`logits.safetensors` 保存：

- 每个 prompt 的完整 logits，shape `[1, prompt_length, vocab_size]`。
- 逐个消费追加 token 后的最后位置 logits，每步 shape `[1, vocab_size]`。

参考数据由 FP32 CPU 无缓存路径生成。Rust 无缓存、Rust 缓存、Python 缓存各自与参考比较；追加 token 固定，不依赖随机采样。用例覆盖单 token、多 token、中文 UTF-8 和上下文边界。检查 NaN/Inf，并报告最大绝对误差和超阈值数量。

CPU 首轮建议 atol=1e-5、rtol=1e-4，属于待实测阈值。若需调整，记录数值原因与设备，不为掩盖实现错误而放宽。MPS/Metal 单独定义验证配置。

## 所有权边界

Python 导出器负责生成 bundle；Rust 读取器负责校验并加载，不导入 Python 包。推理 bundle 不含优化器或训练随机数状态。两端通过固定小样本验证协议，不要求同时启动。
