# 独立本机持续实验设计

## 目标与边界

把 Qwen3、LoRA、SFT、GRPO、程序验证与系统测量放在一个可读、可独立安装的实验室。
首个正式任务为凑数游戏；迷宫和微型 SQL 复用相同任务字典与 run 协议。
首期目标是能反复提出、执行、审查实验，不承诺开放域能力提升。

主要后端为 PyTorch CPU/MPS，默认 0.6B、短序列、串行小组采样。
模型原始结构为 28 层、hidden=1024、Q/KV heads=16/8、head_dim=128、共享 embedding。
不能把 head_dim 推导为 hidden_size / Q heads；KV 开销也不随参数量同比缩小。

## 执行链与代码

| 步骤 | 实现 | 关键不变量 |
| --- | --- | --- |
| 数据 | `tasks.py`、`data.py` | 精确 solver/verifier；语义主键去重；split hash |
| 加载 | `model.py:load_model` | 单文件/分片；基础权重完整；拒绝量化；绑定 embedding |
| 数值检查 | `experiments.py` | HF 独立参考进程；cached/full；左 padding；SDPA/eager |
| 生成 | `generation.py` | thinking 关闭；温度采样；EOS 是动作；完整输出可审查 |
| SFT | `training.py` | prompt 无监督；answer/EOS 监督；按 token 累积；冻结基础模型 |
| GRPO | `training.py` | 0/1 奖励；组内标准化；相同采样/评分分布；固定起点 KL 参考 |
| 候选 | `evaluation.py` | 固定预算与种子；按题目聚类配对；不完整结果拒绝比较 |
| 恢复 | `runs.py` | optimizer/RNG/游标/参考锚点/身份均保存，完整更新边界 |
| 测量 | `runtime.py`、`report.py` | 阶段同步；采样内存；swap 增量；离线 HTML/trace |

模型采用 HF 基础张量名称，LoRA A/B 直接附在线性层上。
不保留原项目的 no-e mask、外部 judge、CUDA/Liger 依赖或固定 1.7B tokenizer。
训练 forward 不保存 KV；gradient checkpointing 与推理缓存明确互斥。

## 实验协议

每个 run 保存完整配置，而非只保存覆盖参数。源码 hash 覆盖包内所有 Python 模块，
依赖由 lock hash 标识，模型及 tokenizer 按文件 SHA-256 标识；Git commit/diff 只作附加信息。
机器身份和原始遥测均保留在忽略的 `.local/`，不放进公开文档。

默认 SFT 200 更新、GRPO 100 更新，各最多两小时，加载与评测计入预算。
每次只改变一个主要变量：数据课程、学习率、rank、长度、缓存或 attention 实现。
先单 seed 检查可行性，仅对有希望的方案重复第二、第三个训练 seed。

dev-quick 用于中途选择 checkpoint，dev-full 用于候选比较。
test/OOD 在阶段协议冻结后审计；程序无法阻止人反复调试测试集，研究者必须维持此边界。
消融从同一已接受权重分叉；连续课程才顺序延续权重。
比较报告的 accept 是初始开发门槛，不能自动覆盖“上一轮模型”。

## 资源预算

24GB 是 CPU/GPU/系统共享内存。0.6B BF16 基础参数约 1.11GiB，
全七类投影 rank16 adapter 为 10,092,544 个参数；AdamW、梯度及临时激活额外占用。
词表 151936，训练 logits 与 log_softmax 可能比 KV 更显眼。

首先分别测加载、生成、SFT forward/backward、GRPO rollout、old/reference、policy update。
预热后的稳定窗口才用于估算正式轮次成本；初次编译、换页和加载不能混作稳态吞吐。
当前 driver 采样软限制为 min(10GiB, 0.9×recommended)，不是分配器硬上限。
默认关闭自动 CPU fallback。OOM 退出该进程，缩小配置后新开 run。
操作边界检查预算会产生一个操作级别的超额，不承诺抢占式硬截止。

## 当前刻意保留的研究项

- KV concat 与预分配、长度分桶、并行组 rollout 的独立性能消融。
- BF16 对概率分布与边界题的影响；FP32 对照阈值不能直接套给 BF16。
- 本机 BF16/MPS 的 no_grad 与可求导评分存在实测差异。旧策略与参考评分使用同一
  grad-enabled 路径后立即 detach；rollout/评分 gap 默认上限 0.05，超出即拒绝更新。
  首轮 GRPO 使用 FP32；不能因为 BF16 SFT 可用就宣称 BF16 GRPO 已通过。
- 多轮迷宫 episode、SQL JOIN 与多表语义，需扩展任务协议。
- 训练后权重合并、MLX 转换和重新量化；不属于首期训练闭环的依赖。
- 不创建定时任务、无限实验搜索、后台服务或自动删除历史产物。
