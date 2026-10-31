"""§4 LoRA 旁路 + §10 注入/可训键筛选。

前向/合并在此；旁路反向内联在 attention.attention_backward 的 wq/wv 段。
只在 stage 4/5 生效：inject 后 attention_forward 经 lora_forward 透传旁路
（主干无感），训练完 merge_lora 烘进 W、旁路随即消失。
"""

import numpy as np

from .config import Config
from .params import LORA_PROJECTIONS


def lora_keys(layer: str, name: str) -> tuple:
    return (f"{layer}_{name}.lora_A", f"{layer}_{name}.lora_B")


def lora_forward(params, cfg: Config, layer: str, name: str, x, base_out):
    """q = x@W + s*((x@A)@B)。返回 (总输出, 缓存或 None)。缓存供反向与校验。"""
    ka, kb = lora_keys(layer, name)
    if ka not in params:
        return base_out, None
    A, B = params[ka], params[kb]
    xa = x @ A  # (B,T,r) 降维
    side = xa @ B  # (B,T,d) 升维
    return base_out + cfg.lora_scale * side, (x, xa)


def merge_lora(params, cfg: Config, projections):
    """训练完把 s*(A@B) 烘进 W：推理零额外延迟（lesson08 的 merge OK）。"""
    for layer, name in projections:
        ka, kb = lora_keys(layer, name)
        params[f"{layer}_{name}"] += cfg.lora_scale * (params[ka] @ params[kb])
        del params[ka], params[kb]


def inject_lora(params, cfg: Config, rng: np.random.Generator):
    """A 随机、B 零初始化：B=0 ⇒ ΔW=0，起点与基座逐位一致；
    且 dL/dB ∝ (x@A)^T ≠ 0，第一步即可更新 B（A=B=0 会永久梯度死锁）。"""
    d, r = cfg.d_model, cfg.lora_r
    for layer, name in LORA_PROJECTIONS:
        ka, kb = lora_keys(layer, name)
        params[ka] = rng.normal(0, 0.02, size=(d, r))
        params[kb] = np.zeros((r, d))


def lora_trainable_keys(params) -> list:
    return [k for k in params if ".lora_" in k]
