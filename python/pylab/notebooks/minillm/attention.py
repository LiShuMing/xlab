"""§5 attention（batch 版，(B,H,T,dh) 布局）。

训练态经 attention_forward/attention_backward 成对使用；推理态不经过这里，
inference.decode_step 手工展开单步（Tq=1 时无需掩码）。
"""

import numpy as np

from .config import Config
from .lora import lora_forward, lora_keys


def split_heads(x, B, T, H, dh):
    return x.reshape(B, T, H, dh).transpose(0, 2, 1, 3)  # (B,H,T,dh)


def merge_heads(x, B, T, d):
    return x.transpose(0, 2, 1, 3).reshape(B, T, d)


def attention_forward(cfg: Config, params, layer: str, x):
    """训练态因果自注意力。x: (B,T,d) 已 RMSNorm。返回 (out, cache)。"""
    B, T, d = x.shape
    H, dh, s = cfg.n_heads, cfg.d_head, cfg.attn_scale
    q = x @ params[f"{layer}_wq"]
    k = x @ params[f"{layer}_wk"]
    v = x @ params[f"{layer}_wv"]
    q, lq = lora_forward(params, cfg, layer, "wq", x, q)
    v, lv = lora_forward(params, cfg, layer, "wv", x, v)

    qh, kh, vh = (split_heads(t, B, T, H, dh) for t in (q, k, v))
    scores = np.matmul(qh, np.swapaxes(kh, -1, -2)) * s  # (B,H,T,T)
    mask = np.triu(np.ones((T, T), dtype=bool), k=1)  # 严格上三角：只看过去
    scores = np.where(mask, -1e9, scores)
    p_attn = np.exp(scores - scores.max(axis=-1, keepdims=True))
    p_attn /= p_attn.sum(axis=-1, keepdims=True)
    oh = np.matmul(p_attn, vh)  # (B,H,T,dh)
    merged = merge_heads(oh, B, T, d)
    out = merged @ params[f"{layer}_wo"]
    cache = dict(x=x, qh=qh, kh=kh, vh=vh, p_attn=p_attn, merged=merged,
                 lora_wq=lq, lora_wv=lv)
    return out, cache


def attention_backward(cfg: Config, params, grads, layer: str, dout, cache):
    """返回对 attention 输入（RMSNorm 输出）的梯度 dnormed。"""
    B, T, d = cache["x"].shape
    H, dh, s = cfg.n_heads, cfg.d_head, cfg.attn_scale
    x = cache["x"]
    xf = x.reshape(B * T, d)

    dmerged = dout @ params[f"{layer}_wo"].T
    grads[f"{layer}_wo"] += cache["merged"].reshape(B * T, d).T @ dout.reshape(B * T, d)

    doh = split_heads(dmerged, B, T, H, dh)  # (B,H,T,dh)
    dp_attn = np.matmul(doh, np.swapaxes(cache["vh"], -1, -2))
    dvh = np.matmul(np.swapaxes(cache["p_attn"], -1, -2), doh)
    # softmax 反向：mask 格子 p=0，梯度自然为 0
    dps = cache["p_attn"] * (dp_attn - (dp_attn * cache["p_attn"]).sum(-1, keepdims=True))
    dqh = np.matmul(dps, cache["kh"]) * s
    dkh = np.matmul(np.swapaxes(dps, -1, -2), cache["qh"]) * s

    dq = merge_heads(dqh, B, T, d)
    dk = merge_heads(dkh, B, T, d)
    dv = merge_heads(dvh, B, T, d)

    dnormed = np.zeros_like(x)
    # 主路投影：∂q/∂Wq = x 与 LoRA 无关，梯度恒为 x^T @ dq
    grads[f"{layer}_wq"] += xf.T @ dq.reshape(B * T, d)
    dnormed += dq @ params[f"{layer}_wq"].T
    grads[f"{layer}_wk"] += xf.T @ dk.reshape(B * T, d)
    dnormed += dk @ params[f"{layer}_wk"].T
    grads[f"{layer}_wv"] += xf.T @ dv.reshape(B * T, d)
    dnormed += dv @ params[f"{layer}_wv"].T

    # LoRA 旁路：dside = s*dout；dA = x^T(dside B^T)，dB = (xA)^T dside
    for name, dout_pv, lc in (("wq", dq, cache["lora_wq"]), ("wv", dv, cache["lora_wv"])):
        if lc is None:
            continue
        xa = lc[1]  # (B,T,r) 前向缓存的降维结果
        ka, kb = lora_keys(layer, name)
        A_mat, B_mat = params[ka], params[kb]
        ds = (cfg.lora_scale * dout_pv).reshape(B * T, d)  # (B*T, d)
        dxa = ds @ B_mat.T                                  # (B*T, r)
        grads[ka] += xf.T @ dxa                             # (d,r)
        grads[kb] += xa.reshape(B * T, -1).T @ ds           # (r,d)
        dnormed += dxa.reshape(B, T, -1) @ A_mat.T          # (B,T,d)
    return dnormed
