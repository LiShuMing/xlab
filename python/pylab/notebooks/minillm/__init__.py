"""minillm — 原单文件 minillm.py 的模块化拆分（行为与 rng 调用顺序保持逐位一致）。

模块地图（括号内为原单文件的小节编号）：

    config.py     (§0)  超参数 Config：d_head / attn_scale / lora_scale 派生属性
    tokenizer.py  (§1)  语料常量 + 字符级 CharTokenizer
    params.py     (§2)  init_params：全流程唯一一份 params dict 在此诞生
    ops.py        (§3)  RMSNorm / GELU 的 forward/backward 原语
    lora.py       (§4 §10) LoRA 旁路前向、合并、注入与可训键筛选
    attention.py  (§5)  split/merge heads + 因果自注意力 fwd/bwd
    model.py      (§6)  整体 forward/backward（残差 + 逐层倒放）
    optim.py      (§7)  Adam + 全局范数梯度裁剪
    training.py   (§8)  sample_batch / 数值梯度校验 / train 循环
    inference.py  (§9)  prefill + decode_step + 采样 + KV 等价性校验
    api.py               TinyGPT 门面：把 cfg + params 收拢为对象
    app.py        (§11) 六 stage 主流程 main()

入口：
    python3 minillm.py      # 仓库内薄入口，行为等同拆分前
    python3 -m minillm      # 在 notebooks 目录下等价
"""

from .app import main
from .config import Config
from .tokenizer import LORA_TEXT, PRETRAIN_LINES, PRETRAIN_TEXT, CharTokenizer
from .params import LORA_PROJECTIONS, init_params
from .ops import gelu_backward, gelu_forward, rmsnorm_backward, rmsnorm_forward
from .lora import (
    inject_lora,
    lora_forward,
    lora_keys,
    lora_trainable_keys,
    merge_lora,
)
from .attention import attention_backward, attention_forward, merge_heads, split_heads
from .api import TinyGPT
from .model import backward, forward
from .optim import Adam, clip_grad_global
from .training import numerical_grad_check, sample_batch, train
from .inference import (
    decode_step,
    generate,
    prefill,
    sample_token,
    verify_kv_equivalence,
)

__all__ = [
    "Adam",
    "CharTokenizer",
    "Config",
    "LORA_PROJECTIONS",
    "LORA_TEXT",
    "PRETRAIN_LINES",
    "PRETRAIN_TEXT",
    "attention_backward",
    "attention_forward",
    "backward",
    "clip_grad_global",
    "decode_step",
    "forward",
    "gelu_backward",
    "gelu_forward",
    "generate",
    "init_params",
    "inject_lora",
    "lora_forward",
    "lora_keys",
    "lora_trainable_keys",
    "main",
    "merge_heads",
    "merge_lora",
    "numerical_grad_check",
    "prefill",
    "rmsnorm_backward",
    "rmsnorm_forward",
    "sample_batch",
    "sample_token",
    "split_heads",
    "TinyGPT",
    "train",
    "verify_kv_equivalence",
]
