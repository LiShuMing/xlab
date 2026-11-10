# 验证记录

日期：2026-11-08。机器：Apple M4 Pro，24GB 统一内存，macOS 15.5 arm64。
Python 3.11.15，torch 2.15.0，transformers 5.22.2；精确依赖见 `uv.lock`。

## 已执行

- CPU 单元检查：33 项通过，覆盖解析器、分数、重复数字、split、权重加载、HF 对照、
  SFT 标签/冻结/累积/checkpointing、GRPO 优势/梯度、恢复、配对比较、trace 与报告转义。
- MPS doctor：FP32 与 BF16 的小张量 forward/backward/AdamW 检查均通过，未启用 CPU fallback。
- CPU 与 MPS 随机小模型：cached/full、padding、eager/SDPA 通过；SFT 三更新、GRPO 两更新。
- 小模型 GRPO 初始 ratio=1，所有组奖励为零时任务梯度为零。
- CPU checkpoint：optimizer、RNG 恢复后下一次更新与连续训练精确一致。
- 凑数正式快照：1000 train / 200 dev / 400 test / 200 OOD，语义主键跨 split 不重叠。

## 官方 Qwen3-0.6B 检查

固定 revision：`c1899de289a04d12100db370d81485cdf75e47ca`。

- HF CPU FP32 参考与手写模型 MPS FP32：最大 logits 差 `9.73e-5`，平均 `9.75e-6`。
- cached/full 最大差 0；eager/SDPA 和单条/左 padding 最大差约 `1.24e-5`。
- 基础参数 596,049,920；rank16 adapter 10,092,544；共享 embedding 检查通过。
- MPS FP32 与 BF16 均执行了三个真实 SFT 更新，梯度有限，基础参数无梯度。
- 修正后 MPS FP32 GRPO 执行两次更新，更新前 ratio=1、初始 KL=0；
  第二组奖励为 `[0, 1, 1, 0]`，梯度范数约 2.97，rollout/full 最大 logprob 差约 `2.41e-5`。
- 正式 dev-quick 50 题、每题一候选、temperature=0.7、最多 64 输出 token：
  成功率 0/50，50 条均为表达式解析失败，12 条截断。输出普遍附解释或 Markdown。
  这一结果用于定位协议学习问题，不是完整 dev/test/OOD 成绩。
- 推理 benchmark 完成 eager 无 cache、eager cache、SDPA cache 各三轮，固定 32 输出 token；
  九次 token IDs 一致。系统有显著换页与背景负载，因此不把测得吞吐当作稳态性能承诺。

## 实测发现及处理

本机 torch 2.15.0 的 BF16/MPS 在 no_grad 与 grad-enabled full forward 之间存在差异，
一次固定回答的最大 logprob 差约 0.333。早期 BF16 GRPO 因此出现 ratio 偏移与伪 KL，
对应 run 已标为 invalidated，不能用于选模。

当前旧策略与参考评分改用 grad-enabled 后立即 detach，与 live policy 路径一致。
rollout/full logprob gap 超过 0.05 或更新前 current/old 差超过 1e-4 即拒绝更新。
默认 GRPO 保持 FP32；没有把 BF16 小张量探针或 SFT 可用解释成 BF16 GRPO 可用。

真实小集的三步 SFT/两步 GRPO 仅有两道开发题，不提供训练收益的统计证据。
随机小模型检查不证明预训练模型有任务能力；没有宣称 200/100 更新正式候选已完成。

## 复核命令

```bash
bash lab.sh test
python3 ../../tools/test_lab_isolation.py
uv run --locked python scripts/validate_real.py
```

最后一条在隔离小快照中检查 Base → SFT → 完整恢复 → GRPO → 配对比较。
运行后 `.local/acceptance/<时间戳>/summary.json` 记录各 run 与验收状态。
本次真实 MPS 全链路验收已通过，记录目录为 `.local/acceptance/20261108-211331-826706/`：
Base、三步 SFT、完整恢复到第四步、两步 GRPO、两组严格同协议配对比较和 HTML 报告均完成。
仓库独立性守卫通过三项检查；该守卫是仓库维护检查，不是本项目运行依赖。

原始本机产物均位于忽略的 `.local/`，文档不含机器标识符或进程清单。
本记录不是整个 xlab 的构建认证。
