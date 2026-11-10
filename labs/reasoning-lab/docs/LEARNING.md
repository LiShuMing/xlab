# 从一轮实验学会一个机制

每次先写预测，再运行并解释证据。按完成标准前进，不按预设天数承诺分数。

| 阶段 | 阅读 | 实验 | 学会的判断 |
| --- | --- | --- | --- |
| 0 | `tasks.py` | 改一个合法表达式为重复数字、除零或非法操作 | 程序奖励是否与任务定义一致 |
| 1 | `model.py` Attention、RMSNorm | tiny parity；官方模型 parity | head_dim、RoPE、GQA、padding、KV 的关系 |
| 2 | `generation.py` | 固定 token 历史比较 cached/full；固定长度 bench | 采样差异与数值差异如何区分 |
| 3 | LoRALinear、sft_loss_sum | 3 次更新；观察 B 梯度与冻结参数 | 低秩更新、标签移位、prompt masking |
| 4 | SFT 训练循环 | 相同起点比较单批与 token 归一化累积 | optimizer update 与样本/token 数的区别 |
| 5 | normalized_advantages、grpo_loss | 同分组、混合奖励组、固定参考 | 奖励、优势、ratio、KL 各自的作用 |
| 6 | runs.py | 中断恢复与连续训练短对照 | adapter warm start 与完整 resume 的区别 |
| 7 | evaluation.py | 同题配对、四候选成本、失败分类 | 采样预算收益与参数学习收益的区别 |
| 8 | runtime.py、report.py | 正常阶段计时与详细观察对照 | 同步、观测扰动、内存重叠与换页 |

## 首批实验卡

1. R0：FP32 与 BF16 哪些算子可用？官方模型数值检查是否通过？
2. R1：L1/L2 单次和四候选分别能解多少？有无格式失败或预算截断？
3. R2：最多 200 个 SFT 更新，是否改善开发集格式与成功率？
4. R3：从 R2 固定起点做短 GRPO，混合奖励组比例是否提供学习信号？
5. R4：按 train/dev 最大错误类别只修正一种数据因素。
6. R5：优胜方案增加训练 seed，冻结后审计 test/OOD。
7. R6：固定候选权重，比较 KV/attention 的时间与质量。

每张卡包含：假设、唯一改动、起点 hash、数据版本、预算、可观察证据、结果、
接受/拒绝/证据不足、下一轮问题。运行目录的 `decision.md` 是起始模板。

## 常见失败如何推进

- 全部 GRPO 候选失败：先降课程或补合法 SFT，不把增加 group 当作免费信号。
- 训练 loss 降而开发分数不动：看格式、数字使用、算术错误和数据覆盖率。
- 开发分数突增：先检查 split、prompt 与程序验证器，再解释学习收益。
- 第一步 LoRA A 梯度为零：B 初始为零时正常；至少应有 B 梯度。
- MPS 训练突然变慢：先检查本轮 pageout/swap 增量与阶段耗时。
- resume 被拒绝：先检查源码/依赖/数据/协议是否改变；需要新实验时明确 warm start。
- 置信区间跨零：记录证据不足；评测 bootstrap 不能替代独立训练 seed。
