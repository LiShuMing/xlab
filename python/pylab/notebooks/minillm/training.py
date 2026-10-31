"""§8 数据采样、数值梯度校验与训练 —— sample_batch 是训练/校验唯一取数口；
numerical_grad_check 被 stage 0（主干）与 stage 4（LoRA）复用；train 被
stage 1（全参数）与 stage 5（仅 A/B）复用。
"""

import numpy as np

from .config import Config
from .model import backward, forward
from .optim import Adam, clip_grad_global


def sample_batch(data: np.ndarray, block: int, batch: int, rng):
    ix = rng.integers(0, len(data) - block - 1, size=batch)
    x = np.stack([data[i:i + block] for i in ix])
    y = np.stack([data[i + 1:i + block + 1] for i in ix])
    return x, y


def numerical_grad_check(cfg: Config, params, data: np.ndarray, rng,
                         keys, n_checks: int = 4, eps: float = 1e-5):
    """中心差分 vs 解析梯度；float64 下相对误差应 < 1e-5。
    stage 0 传主干关键键、stage 4 传 LoRA 全部键——同一守门员，只换 keys。"""
    xb, yb = sample_batch(data, cfg.block_size, 2, rng)
    _, loss0, cache = forward(params, cfg, xb, yb)
    grads = backward(cfg, params, cache, yb)
    worst, worst_key = 0.0, ""
    for key in keys:
        flat = params[key].ravel()  # C 连续时是视图，原地改可扰动参数
        gflat = grads[key].ravel()
        for _ in range(n_checks):
            i = int(rng.integers(flat.size))
            orig = flat[i]
            flat[i] = orig + eps
            lp = forward(params, cfg, xb, yb)[1]
            flat[i] = orig - eps
            lm = forward(params, cfg, xb, yb)[1]
            flat[i] = orig  # 复原
            num = (lp - lm) / (2 * eps)
            ana = gflat[i]
            rel = abs(num - ana) / max(1e-8, abs(num) + abs(ana))
            if rel > worst:
                worst, worst_key = rel, key
    assert worst < 1e-5, f"grad check failed: rel={worst:.2e} at {worst_key}"
    return worst


def train(params, cfg: Config, data: np.ndarray, rng, keys, steps: int,
          lr: float, batch: int, log_every: int, tag: str):
    """keys 决定训练哪些参数：预训练为全部参数，LoRA 阶段只有 A/B（主干冻结）。

    单步节拍：sample_batch 取数 → forward 出 loss → backward 出 grads →
    全局范数裁剪 → 线性 warmup 学习率 → Adam 只 step keys 里的键。
    stage 1 与 stage 5 复用本函数，唯一区别就是 keys 传什么。
    """
    opt = Adam(keys)
    # 以上节拍循环 steps 轮，loss 经 log_every 抽样打印
    for step in range(1, steps + 1):
        xb, yb = sample_batch(data, cfg.block_size, batch, rng)
        _, loss, cache = forward(params, cfg, xb, yb)
        grads = backward(cfg, params, cache, yb)
        clip_grad_global(grads, keys, 1.0)
        lr_eff = lr * min(1.0, step / 20.0)  # 线性 warmup
        opt.step(params, grads, lr_eff)
        if step == 1 or step % log_every == 0:
            print(f"  [{tag}] step {step:4d}  loss {loss:.4f}  ppl {np.exp(loss):7.2f}")
    return params
