"""One sampling distribution for rollout and policy scoring: temperature only.

这个文件只有三件事：把 prompt 变成 token、自回归采样出 answer、对给定 answer 算 logprob。

关键约定：**采样和打分用同一个分布**（同一个 temperature、同一个 chat template）。
GRPO 的更新量正比于新旧策略的 logprob 比，两边口径不一致时比值就不是 1，
会把“分布差异”误当成“策略改进”。没有 top-k / top-p / repetition penalty，
就是为了让这个分布能被精确复现。
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass

import torch


@dataclass
class Sample:
    """一次生成的全部产物。

    token_ids       生成的 token（不含 prompt）
    log_probs       每个 token 在采样分布下的 log 概率，长度与 token_ids 相同
    finish_reason   "eos" 表示自然结束，"max_tokens" 就是被截断
    token_seconds   每个 token 生成完时的累计秒数，用于算吞吐
    """

    token_ids: list[int]
    log_probs: torch.Tensor
    finish_reason: str
    token_seconds: list[float]


def encode_prompt(tokenizer, prompt: str) -> list[int]:
    """套上对话模板再分词。

    ``apply_chat_template`` 会插入 Qwen 的特殊标记（user/assistant 分段、思考开关）。
    ``enable_thinking=False`` 关掉 Qwen3 的思考模式，否则模型会先输出一段推理再给答案，
    与「只输出一个表达式」的格式要求直接冲突。
    ``add_generation_prompt=True`` 补上「轮到 assistant 说话」的前缀，模型才知道该接着写。
    """
    encoded = tokenizer.apply_chat_template(
        [{"role": "user", "content": prompt}],
        tokenize=True,
        add_generation_prompt=True,
        enable_thinking=False,
        return_dict=False,
    )
    if isinstance(encoded, Mapping):
        encoded = encoded["input_ids"]
    if not isinstance(encoded, list) or not encoded or not all(type(t) is int for t in encoded):
        raise ValueError("Chat template must produce one nonempty list of token IDs")
    return encoded


def answer_text(tokenizer, tokens: list[int]) -> str:
    # Strip EOS only. Other special tokens remain visible to the format validator.
    # 只剥结束符、保留其余特殊 token：如果模型输出了不该出现的标记，
    # 要让验证器看到并报格式错误，而不是在解码阶段悄悄抹掉
    eos = tokenizer.eos_token_id
    return tokenizer.decode([token for token in tokens if token != eos], skip_special_tokens=False)


@torch.no_grad()
def generate(
    model,
    prompt: list[int],
    max_new_tokens: int,
    temperature: float,
    eos_id: int | None,
    use_cache: bool = True,
) -> Sample:
    """自回归采样：一次 prefill，然后每步只前向 1 个新 token。

    第一步把整个 prompt 送进模型（prefill），同时建立 KV cache；
    之后每步只送刚生成的那 1 个 token（decode），历史信息从 cache 里读。
    ``@torch.no_grad()`` 是因为采样只做推理，不建计算图；
    需要梯度的那条路径在下面的 ``response_log_probs`` 里。
    """
    if not prompt or max_new_tokens < 1 or temperature < 0:
        raise ValueError("Invalid generation arguments")
    was_training = model.training
    # 推理必须切 eval：否则 dropout / batchnorm 等训练态行为会让同 seed 不可复现
    model.eval()
    try:
        device = next(model.parameters()).device
        ids = torch.tensor([prompt], device=device, dtype=torch.long)
        # history 是完整序列（含 prompt），ids 是“下一步要送进模型的部分”
        history, cache = ids, None
        responses, log_probs, times = [], [], []
        started = time.perf_counter()
        reason = "max_tokens"
        for step in range(max_new_tokens):
            # 有 cache 时：第 0 步送 prompt 全部，第 1 步起只送 1 个 token
            inputs = ids if use_cache and step else history
            logits, cache = model(
                inputs, past_key_values=cache if use_cache else None, use_cache=use_cache
            )
            scores = logits[0, -1].float()  # 只看最后一个位置：它预测下一个 token
            # 温度缩放后再 log_softmax。temperature=0 时走下面的 argmax，这里的 1.0 只是防除零
            distribution = (scores / (temperature or 1.0)).log_softmax(-1)
            token = (
                scores.argmax() if temperature == 0 else torch.multinomial(distribution.exp(), 1)[0]
            )
            token_id = int(token.item())
            # 记下采样分布下的 logprob，GRPO 用它算重要性比值
            log_probs.append(distribution[token_id])
            responses.append(token_id)
            times.append(time.perf_counter() - started)
            if token_id == eos_id:
                reason = "eos"
                break
            ids = token.reshape(1, 1)
            history = torch.cat((history, ids), -1)
        return Sample(responses, torch.stack(log_probs).detach(), reason, times)
    finally:
        # 恢复调用前的 train/eval 状态，避免采样把训练循环的状态改掉
        model.train(was_training)


def response_log_probs(
    model, prompt: list[int], response: list[int], temperature: float
) -> torch.Tensor:
    """用 teacher forcing 一次前向，算出整段 response 在当前策略下的 logprob。

    这里允许模型“看到答案”：不是生成，而是**重新打分**。拼接 prompt+response 后
    一次前向拿到每个位置的 logits，再取出“实际下一个 token”对应的那一项。

    对齐关系（最容易写错的地方）：
        位置 i 的输出 logits 预测的是 ids[i+1]
        所以 logits 从 len(prompt)-1 开始，与 ids 从 len(prompt) 开始逐项对应

    除以 temperature 是为了与采样时的分布口径一致；不一致的话重要性比值不等于 1。
    返回的每项都带计算图，GRPO 要靠它回传梯度。
    """
    if not response or temperature <= 0:
        raise ValueError("Policy scoring requires response tokens and positive temperature")
    device = next(model.parameters()).device
    ids = torch.tensor([prompt + response], device=device, dtype=torch.long)
    logits, _ = model(ids[:, :-1])
    scores = logits[0, len(prompt) - 1 :].float() / temperature
    targets = ids[0, len(prompt) :]
    return scores.log_softmax(-1).gather(-1, targets[:, None]).squeeze(-1)


def sft_loss_sum(model, prompt: list[int], response: list[int]) -> tuple[torch.Tensor, int]:
    """Shift once and supervise answer/EOS tokens only; return sum for accumulation.

    监督信号只盖住 answer：prompt 位置的 logits 不产生 loss，否则模型会去学“复述题目”，
    而那不是我们想强化的能力。

    返回的是 token 级**求和**而不是平均：调用方把多个样本的 sum 加总后再除以总 target
    token 数，这样长答案与短答案在同一批里按 token 加权，而不是每个样本等权。
    第二个返回值就是这批的 target token 数，供外部做归一化。
    """
    device = next(model.parameters()).device
    ids = torch.tensor([prompt + response], device=device, dtype=torch.long)
    logits, _ = model(ids[:, :-1])
    # 与 response_log_probs 相同的偏移：第 len(prompt)-1 个位置预测 answer 的第一个 token
    answer_logits = logits[0, len(prompt) - 1 :]
    targets = ids[0, len(prompt) :]
    # FP32 计交叉熵：低精度下 log_softmax 的 exp/sum 容易累积误差
    return torch.nn.functional.cross_entropy(answer_logits.float(), targets, reduction="sum"), len(
        response
    )
