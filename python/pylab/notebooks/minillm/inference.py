"""§9 KV cache 推理：prefill + decode + 采样 —— 推理三段式：prefill 整段并行
→ decode 每 token 只算增量 → sample 温度/top-k；stage 2/3/5 的 generate 与
verify 全走这条路径。

注意：decode_step 不走 model.forward，而是把单步前向手工展开（Tq=1 时因果性
由"cache 只存历史"在结构上保证，无需掩码），因此也不产生训练用 cache。
"""

import numpy as np

from .attention import merge_heads, split_heads
from .config import Config
from .lora import lora_forward
from .model import forward
from .ops import gelu_forward, rmsnorm_forward


def prefill(params, cfg: Config, ids: np.ndarray):
    """整段 prompt 一次算完，返回最后位置 logits 与每层 KV cache。"""
    logits, _, cache = forward(params, cfg, ids)
    kv = {i: (cache[f"l{i}"]["attn"]["kh"], cache[f"l{i}"]["attn"]["vh"])
          for i in range(cfg.n_layers)}
    return logits[0, -1], kv


def decode_step(params, cfg: Config, tok: int, kv: dict, pos: int):
    """单 token 增量 decode：只算当前 q，K/V 追加 cache。返回最后位置 logits。"""
    d, H, dh = cfg.d_model, cfg.n_heads, cfg.d_head
    x = params["emb"][tok][None, None, :] + params["pos"][pos:pos + 1][None, :, :]
    for i in range(cfg.n_layers):
        pre = f"l{i}"
        normed1, _ = rmsnorm_forward(x, params[f"{pre}_ln1_g"])
        q = normed1 @ params[f"{pre}_wq"]
        k = normed1 @ params[f"{pre}_wk"]
        v = normed1 @ params[f"{pre}_wv"]
        q, _ = lora_forward(params, cfg, pre, "wq", normed1, q)
        v, _ = lora_forward(params, cfg, pre, "wv", normed1, v)
        qh = split_heads(q, 1, 1, H, dh)
        kh = split_heads(k, 1, 1, H, dh)
        vh = split_heads(v, 1, 1, H, dh)
        # 追加 cache（demo 用 concat，O(T) 拷贝；真实系统预分配/paged cache）
        K = np.concatenate([kv[i][0], kh], axis=2)  # (1,H,Tk,dh)
        V = np.concatenate([kv[i][1], vh], axis=2)
        kv[i] = (K, V)
        # Tq=1、Tk>1：因果性由 cache 只存历史在结构上保证，无需掩码
        scores = np.matmul(qh, np.swapaxes(K, -1, -2)) * cfg.attn_scale
        p_attn = np.exp(scores - scores.max(axis=-1, keepdims=True))
        p_attn /= p_attn.sum(axis=-1, keepdims=True)
        oh = np.matmul(p_attn, V)
        merged = merge_heads(oh, 1, 1, d)
        x = x + merged @ params[f"{pre}_wo"]

        normed2, _ = rmsnorm_forward(x, params[f"{pre}_ln2_g"])
        h1, _ = gelu_forward(normed2 @ params[f"{pre}_w1"])
        x = x + h1 @ params[f"{pre}_w2"]

    normed_f, _ = rmsnorm_forward(x, params["lnf_g"])
    logits = normed_f @ params["wout"]
    return logits[0, 0], kv


def sample_token(logits: np.ndarray, temperature: float, top_k: int,
                 rng: np.random.Generator) -> int:
    z = logits.astype(np.float64) / temperature
    if top_k and top_k < z.size:
        keep = np.argpartition(z, -top_k)[-top_k:]
        mask = np.full(z.size, -np.inf)
        mask[keep] = z[keep]
        z = mask
    e = np.exp(z - z.max())
    p = e / e.sum()
    return int(rng.choice(z.size, p=p))


def generate(params, cfg: Config, tokenizer, prompt: str, n_new: int,
             temperature: float = 0.8, top_k: int = 5, rng=None) -> str:
    """自回归生成：prefill 一次吃进整段 prompt，之后每步只喂最后一个 token。

    返回 prompt + n_new 个新字符；总长受 block_size 约束（位置编码表行数）。
    top_k=1 即贪心解码，stage 2/5 的行为对比依赖它的确定性。
    """
    rng = rng or np.random.default_rng(0)
    ids = tokenizer.encode(prompt).tolist()
    # 三段式：prefill 并行算完 prompt → 采样首个新 token → 循环 decode
    logits, kv = prefill(params, cfg, np.array([ids]))
    nxt = sample_token(logits, temperature, top_k, rng)  # 首个新 token 来自 prefill 末位 logits
    ids.append(nxt)
    for _ in range(n_new - 1):
        # pos = len(ids)-1 是刚采样 token 的绝对位置（位置编码与 cache 写入都用它）
        logits, kv = decode_step(params, cfg, ids[-1], kv, len(ids) - 1)
        ids.append(sample_token(logits, temperature, top_k, rng))
    return tokenizer.decode(ids)


def verify_kv_equivalence(params, cfg: Config, text: str, tokenizer) -> float:
    """decode 路径逐步 logits vs 整段重算：数学等价，浮点上应 ulp 级一致。"""
    ids = tokenizer.encode(text)
    split = cfg.block_size // 2
    prefix = np.array([ids[:split]])
    logits, kv = prefill(params, cfg, prefix)
    worst = float(np.abs(
        forward(params, cfg, prefix)[0][0, -1] - logits).max())
    for t in range(split, len(ids)):
        logits, kv = decode_step(params, cfg, ids[t], kv, t)
        full = forward(params, cfg, np.array([ids[:t + 1]]))[0][0, -1]
        worst = max(worst, float(np.abs(full - logits).max()))
    return worst
