"""TinyGPT 门面 —— 把 (cfg, params) 收拢成对象，转发到各功能模块。

刻意只是转发、不新增任何数值逻辑：rng 仍由调用方持有并显式传入，
所以拆分前后的 rng 调用顺序、随机数消耗量与单文件版完全一致。

放在 api 而非 model：model 是最底层的组装层，inference/training 都依赖它；
门面同时依赖训练与推理，若写进 model 会形成循环导入。
"""

import numpy as np

from .config import Config
from .inference import (
    decode_step as _decode_step,
    generate as _generate,
    prefill as _prefill,
    verify_kv_equivalence as _verify_kv_equivalence,
)
from .lora import (
    inject_lora as _inject_lora,
    lora_trainable_keys as _lora_trainable_keys,
    merge_lora as _merge_lora,
)
from .model import backward as _backward, forward as _forward
from .params import LORA_PROJECTIONS, init_params
from .training import numerical_grad_check as _grad_check, train as _train


class TinyGPT:
    """一份 Config + 一份 params dict 的持有者，六个 stage 共用同一实例。

    参数不复制、不封装成 attribute：`model.params` 就是全流程唯一的模型状态，
    LoRA 注入往这个 dict 追加键、merge 原地改写 W，外部按原样访问。
    """

    def __init__(self, cfg: Config, params=None, rng=None):
        self.cfg = cfg
        if params is None:
            params = init_params(cfg, rng)
        self.params = params

    # ---- 形状与规模 ----
    @property
    def n_params(self) -> int:
        return sum(p.size for p in self.params.values())

    def base_params(self) -> dict:
        """剔除 .lora_* 键的主干视图：stage 4 用它证明 B=0 注入是逐位恒等。"""
        return {k: v for k, v in self.params.items() if ".lora_" not in k}

    # ---- 训练路径（§6 §8 §7）----
    def forward(self, idx: np.ndarray, targets=None):
        return _forward(self.params, self.cfg, idx, targets)

    def backward(self, cache, targets) -> dict:
        return _backward(self.cfg, self.params, cache, targets)

    def grad_check(self, data, rng, keys, **kwargs) -> float:
        return _grad_check(self.cfg, self.params, data, rng, keys, **kwargs)

    def train(self, data, rng, keys, **kwargs):
        return _train(self.params, self.cfg, data, rng, keys, **kwargs)

    # ---- 推理路径（§9）----
    def prefill(self, ids: np.ndarray):
        return _prefill(self.params, self.cfg, ids)

    def decode_step(self, tok: int, kv: dict, pos: int):
        return _decode_step(self.params, self.cfg, tok, kv, pos)

    def generate(self, tokenizer, prompt: str, n_new: int, **kwargs) -> str:
        return _generate(self.params, self.cfg, tokenizer, prompt, n_new, **kwargs)

    def verify_kv(self, text: str, tokenizer) -> float:
        return _verify_kv_equivalence(self.params, self.cfg, text, tokenizer)

    # ---- LoRA（§4 §10）----
    def inject_lora(self, rng):
        _inject_lora(self.params, self.cfg, rng)

    def lora_trainable_keys(self) -> list:
        return _lora_trainable_keys(self.params)

    def merge_lora(self, projections=LORA_PROJECTIONS):
        _merge_lora(self.params, self.cfg, projections)
