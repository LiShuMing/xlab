"""§0 超参数 —— 形状的唯一权威源，派生量全部以属性给出。

四条硬约束（详见项目记忆）：d_model % n_heads == 0；vocab_size 由语料决定；
attn_scale 跟随收缩维 d_head 而非模型宽；block_size 即 context window 上限。
"""

from dataclasses import dataclass

import numpy as np


@dataclass
class Config:
    vocab_size: int
    d_model: int = 64
    n_heads: int = 4
    n_layers: int = 2
    block_size: int = 32
    ffn_mult: int = 4
    lora_r: int = 4
    lora_alpha: float = 8.0

    @property
    def d_head(self) -> int:
        return self.d_model // self.n_heads

    @property
    def attn_scale(self) -> float:
        return 1.0 / np.sqrt(self.d_head)

    @property
    def lora_scale(self) -> float:
        # alpha/r 把秩 r 与更新幅度解耦：调 r 不必重调学习率
        return self.lora_alpha / self.lora_r
