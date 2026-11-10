"""Strict, fully materialized experiment configuration.

一份配置 = 一次可复现运行的全部输入。所有字段都有默认值，yaml 只写与默认值
不同的部分，加载后立刻 validate()：非法组合在开机前失败，而不是训练到一半
才被发现。

字段按用途分四组：

    身份与路径   stage/task/model/data/output/device/dtype/split
    模型结构     rank/alpha/attention/gradient_checkpointing/max_length
    生成协议     max_new_tokens/temperature/samples
    优化与预算   steps/max_seconds/learning_rate/.../group_size/kl_beta/clip_eps

字段集合是封闭的（load 里 cls(**value) 会拒绝未知键），所以这里出现什么，
protocol 哈希就覆盖什么；想加一个只给日志看的字段，不能往 Config 里塞。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import yaml


@dataclass
class Config:
    # ---- 身份与路径 ----
    # stage 决定 train() 走哪条路：eval 只评测、sft 用参考答案监督、
    # grpo 用程序化奖励做强化学习、bench 只测吞吐
    stage: str = "eval"
    # task 同时决定题目空间和判卷器：三个任务各有自己的 make_task/verify
    task: str = "countdown"
    model: str = ".local/models/qwen3-0.6b"
    data: str = ".local/data/countdown-v1"
    output: str = ".local/runs"
    device: str = "auto"
    # float32 是默认：0.6B 在 CPU/MPS 上 bf16 收益有限，
    # 而 FP32 让“训练前后是否真的变了”这种比较不会淹没在舍入误差里
    dtype: str = "float32"
    # seed 同时决定题目抽样、采样的随机数和评测里每题的候选 seed
    seed: int = 42

    # ---- LoRA 结构 ----
    # 旁路的秩：A 是 [rank, in]，B 是 [out, rank]，
    # 可训练参数约 rank*(in+out)，比全参微调小几个数量级
    rank: int = 16
    # 缩放分子：delta = (alpha/rank) * B(Ax)。alpha 与 rank 同步放大时，
    # 改 rank 不必重新调学习率
    alpha: float = 16.0
    # sdpa 走 PyTorch 融合内核（快）；eager 是手写 softmax（慢，但能逐项对账）
    attention: str = "sdpa"
    # 用时间换显存：不存中间激活，反向时重算。
    # 与 KV cache 互斥，因为 cache 存的正是被省掉的那部分张量
    gradient_checkpointing: bool = False
    # prompt + 生成的总长度上限，必须严格大于 max_new_tokens
    max_length: int = 256

    # ---- 生成协议 ----
    # 生成长度上限，同时也是截断判据：finish_reason == "max_tokens"
    max_new_tokens: int = 64
    # 采样温度：0 等价贪心（GRPO 禁止，因为组内候选会完全相同）；
    # 越大分布越平，多样性上升、正确率通常下降
    temperature: float = 0.7
    # 评测时每题生成几个候选，pass@k 的 k 就来自这里
    samples: int = 4

    # ---- 训练预算 ----
    # 优化器更新次数，不是样本数；一个 step 可能跨 accumulation 个微批
    steps: int = 200
    # 墙钟上限：超时就在下个检查点安全退出，避免任务无限延长
    max_seconds: float = 7200
    learning_rate: float = 1e-4
    # LoRA 可训练参数很少，正则化收益低，默认不做权重衰减
    weight_decay: float = 0.0
    # AdamW 一阶/二阶动量的衰减系数
    betas: tuple = (0.9, 0.999)
    # 二阶矩的数值稳定项，防止除零
    eps: float = 1e-8
    # 梯度累积：攒 accumulation 个微批再 step，等价于放大 batch 而不涨显存
    accumulation: int = 1
    # 梯度裁剪：把参数梯度整体 L2 范数压到这个值以内
    max_grad_norm: float = 1.0
    eval_every: int = 50
    save_every: int = 50

    # ---- GRPO 三件套 ----
    # 每题采几个候选组成 group，advantage 在组内标准化
    group_size: int = 4
    # KL 惩罚系数：约束当前策略不要偏离参考策略（SFT 后的初始 adapter）太远
    kl_beta: float = 0.02
    # PPO 截断：ratio 偏离 1 超过 ±clip_eps 的样本不再贡献梯度，防止单步更新过猛
    clip_eps: float = 0.2
    # 一致性门禁：采样时记的 logprob 与事后重算的 logprob 之差超过此值，
    # 说明温度/精度/位置对齐出了问题，直接中止而不是带着错误继续训练
    max_logprob_gap: float = 0.05
    # 软显存上限（GiB）：超过就打告警，并据此判断是否降级
    memory_soft_limit_gib: float = 10

    # ---- 数据与续训 ----
    # 训练只允许 dev/dev-quick：test/OOD 一旦参与选模就不再是独立审计集
    split: str = "dev"
    # 只取前 N 题做冒烟。它会改变 task_hash，
    # 所以 --limit 的结果不能与全量结果做 compare
    limit: int | None = None
    # adapter：只加载 LoRA 权重做 warm start，模型身份与 rank/alpha 必须一致
    adapter: str | None = None
    # resume：真续训，额外恢复 optimizer/RNG/step/cursor，协议必须完全一致
    resume: str | None = None
    # 实验卡：先写假设和改动，再看数字，避免事后编故事
    hypothesis: str = "Establish a reproducible baseline."
    change: str = "none"

    def validate(self) -> Config:
        """把非法组合挡在开机前。每条检查都对应一个会静默出错的真实场景。"""
        if self.stage not in {"eval", "sft", "grpo", "bench"}:
            raise ValueError("Unknown stage")
        if self.dtype not in {"float32", "bfloat16"} or self.attention not in {"eager", "sdpa"}:
            raise ValueError("Unsupported dtype or attention")
        if self.task not in {"countdown", "maze", "sql"}:
            raise ValueError("Unknown task")
        # 生成预算必须给 prompt 留空间，否则每条样本写两三个 token 就被截断
        if self.max_new_tokens < 1 or self.max_length <= self.max_new_tokens:
            raise ValueError("max_length must exceed max_new_tokens")
        # 这些值会被当作除数、步长或循环边界，<=0 会变成静默空转或除零
        if (
            min(
                self.steps,
                self.samples,
                self.accumulation,
                self.eval_every,
                self.save_every,
                self.rank,
            )
            < 1
            or self.max_seconds <= 0
        ):
            raise ValueError("Budgets and intervals must be positive")
        if self.temperature < 0 or self.group_size < 2 or self.learning_rate <= 0:
            raise ValueError("Invalid temperature, group_size or learning rate")
        # GRPO 两个硬约束：温度必须为正（否则组内候选全相同，advantage 恒为 0），
        # 累积必须为 1（否则同组候选会被拆进不同微批，组内比较失去意义）
        if self.stage == "grpo" and (self.temperature <= 0 or self.accumulation != 1):
            raise ValueError("GRPO requires positive temperature and accumulation=1")
        # 选模只能用 dev：test/OOD 必须留作冻结审计，参与选模就不再独立
        if self.stage in {"sft", "grpo"} and self.split not in {"dev", "dev-quick"}:
            raise ValueError("Training may only use dev/dev-quick for checkpoint selection")
        # 两种语义不能混：resume 恢复优化器与随机数，adapter 只替换权重
        if self.resume and self.adapter:
            raise ValueError("Choose full resume or adapter warm start")
        if self.limit is not None and self.limit < 1:
            raise ValueError("limit must be positive")
        if not 0 <= self.clip_eps < 1 or self.kl_beta < 0 or self.weight_decay < 0:
            raise ValueError("Invalid optimizer/GRPO coefficients")
        if self.max_grad_norm <= 0 or self.memory_soft_limit_gib <= 0 or self.alpha <= 0:
            raise ValueError("Gradient, memory and alpha limits must be positive")
        if self.max_logprob_gap <= 0:
            raise ValueError("max_logprob_gap must be positive")
        if len(self.betas) != 2 or not all(0 <= value < 1 for value in self.betas) or self.eps <= 0:
            raise ValueError("Invalid AdamW betas/eps")
        return self

    @classmethod
    def load(cls, path: Path, overrides: dict | None = None) -> Config:
        """yaml 打底、命令行覆盖，再统一校验。

        cls(**value) 只接受已声明的字段：写错键名直接 TypeError，
        不会出现“存了一个没人读的配置”。字段集合封闭，protocol 哈希才可信。
        """
        value = yaml.safe_load(path.read_text()) or {}
        if not isinstance(value, dict):
            raise ValueError("Config must be a mapping")
        value.update(overrides or {})
        return cls(**value).validate()

    def to_dict(self) -> dict:
        """扁平快照。protocol_identity 拿它算训练协议哈希，所以不能塞临时字段。"""
        return asdict(self)
