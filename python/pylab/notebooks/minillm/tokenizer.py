"""§1 语料与字符级 tokenizer —— 流程最上游：文本 → id 序列。

训练侧供 training.sample_batch 切样本，推理侧供 inference.generate /
inference.verify_kv_equivalence 编解码。
"""

import numpy as np

# 预训练语料：短句重复，结构强，小模型几百步即可学会续写。
PRETRAIN_LINES = [
    "llm runs on cpu with fp64 numpy.",
    "llm runs on cpu for tiny demos.",
    "kv cache speeds up token decode.",
    "lora adds a low rank side path.",
]
PRETRAIN_TEXT = "\n".join(PRETRAIN_LINES * 24)

# LoRA 微调语料：教模型"改口"——同一个 prompt 前缀，答案从 cpu 换成 gpu。
LORA_TEXT = "\n".join(["llm runs on gpu with fast kernels."] * 48)


class CharTokenizer:
    """字符级 tokenizer：语料内所有唯一字符构成词表。"""

    def __init__(self, text: str):
        chars = sorted(set(text))
        self.stoi = {c: i for i, c in enumerate(chars)}
        self.itos = {i: c for i, c in enumerate(chars)}
        self.vocab_size = len(chars)

    def encode(self, text: str) -> np.ndarray:
        return np.array([self.stoi[c] for c in text], dtype=np.int64)

    def decode(self, ids) -> str:
        return "".join(self.itos[int(i)] for i in ids)
