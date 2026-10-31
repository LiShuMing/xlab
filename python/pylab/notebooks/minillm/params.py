"""§2 参数初始化 —— 全流程唯一一份 params dict 在此诞生，六个 stage
都在它上面原地演进（训练改权重、LoRA 加键、merge 改写 W）。
"""

import numpy as np

from .config import Config

LORA_PROJECTIONS = [(f"l{i}", name) for i in range(2) for name in ("wq", "wv")]


def init_params(cfg: Config, rng: np.random.Generator) -> dict:
    """全部参数收进一个 dict，键名即参数名；float64 全程以支撑数值梯度校验。"""
    p: dict = {}
    d, V, T = cfg.d_model, cfg.vocab_size, cfg.block_size
    std = 0.02
    p["emb"] = rng.normal(0, std, size=(V, d))
    p["pos"] = rng.normal(0, std, size=(T, d))
    for i in range(cfg.n_layers):
        pre = f"l{i}"
        p[f"{pre}_ln1_g"] = np.ones(d)
        p[f"{pre}_ln2_g"] = np.ones(d)
        for name in ("wq", "wk", "wv", "wo"):
            p[f"{pre}_{name}"] = rng.normal(0, std, size=(d, d))
        p[f"{pre}_w1"] = rng.normal(0, std, size=(d, cfg.ffn_mult * d))
        p[f"{pre}_w2"] = rng.normal(0, std, size=(cfg.ffn_mult * d, d))
    p["lnf_g"] = np.ones(d)
    p["wout"] = rng.normal(0, std, size=(d, V))
    return p
