"""§6 完整前向/反向 —— 模型数据流的聚合点：

    forward:  emb+pos → n×{RMSNorm → attention → 残差 → RMSNorm → GELU FFN → 残差}
              → RMSNorm → wout → (CE loss)
    backward: 上式的严格倒放，CE 起步、embedding/位置编码收尾

本模块只做"组装"：所有数学原语在 ops.py / attention.py，这里负责残差接线、
cache 的组织方式与逐层倒放顺序。
"""

import numpy as np

from .attention import attention_backward, attention_forward
from .config import Config
from .ops import gelu_backward, gelu_forward, rmsnorm_backward, rmsnorm_forward


def forward(params, cfg: Config, idx: np.ndarray, targets=None):
    """idx (B,T) int → logits (B,T,V)。给 targets 时同时返回平均 CE loss。

    全流程唯一的前向入口：stage 0/1/4/5 的校验与训练、stage 2/3 的 prefill
    都调这里。targets=None 时跳过 softmax/loss（纯推理），但每层 cache 照
    常填充——prefill 靠它提取各层 KV 送去 inference 的 KV cache。
    """
    B, T = idx.shape
    d = cfg.d_model
    cache: dict = {"idx": idx}
    x = params["emb"][idx] + params["pos"][:T]  # (B,T,d)

    for i in range(cfg.n_layers):
        pre = f"l{i}"
        x_in = x
        normed1, inv1 = rmsnorm_forward(x, params[f"{pre}_ln1_g"])
        attn_out, attn_cache = attention_forward(cfg, params, pre, normed1)
        x = x_in + attn_out  # 残差 1
        x_mid = x
        normed2, inv2 = rmsnorm_forward(x, params[f"{pre}_ln2_g"])
        z1 = normed2 @ params[f"{pre}_w1"]  # gelu 的输入（反向需要）
        h1, t = gelu_forward(z1)  # (B,T,4d)
        ffn_out = h1 @ params[f"{pre}_w2"]
        x = x_mid + ffn_out  # 残差 2
        cache[f"l{i}"] = dict(x_in=x_in, inv1=inv1, attn=attn_cache,
                              x_mid=x_mid, inv2=inv2, normed2=normed2,
                              z1=z1, h1=h1, t=t)

    x_last = x
    normed_f, invf = rmsnorm_forward(x, params["lnf_g"])
    logits = normed_f @ params["wout"]  # (B,T,V)

    loss, probs = None, None
    if targets is not None:
        N, V = B * T, cfg.vocab_size
        z = logits.reshape(N, V)
        e = np.exp(z - z.max(axis=-1, keepdims=True))
        probs = e / e.sum(axis=-1, keepdims=True)
        picked = np.clip(probs[np.arange(N), targets.reshape(-1)], 1e-30, None)
        loss = float(-np.mean(np.log(picked)))
        cache["probs"] = probs
    cache.update(x_last=x_last, invf=invf, normed_f=normed_f)
    return logits, loss, cache


def backward(cfg: Config, params, cache, targets) -> dict:
    """从 CE loss 反传到全部参数。返回 grads（与 params 同键，累加语义）。

    执行顺序严格镜像 forward 的倒放：CE → wout → lnf →
    各层{FFN → RMSNorm → attention → RMSNorm} → embedding/位置编码。
    grads 与 params 同构；optim 的优化器按 keys 白名单挑键更新——冻结机制
    依赖这份同构：不可训键的梯度照样算，只是不被 step。
    """
    idx = cache["idx"]
    B, T = idx.shape
    d, V = cfg.d_model, cfg.vocab_size
    N = B * T
    grads = {k: np.zeros_like(v) for k, v in params.items()}

    # 1) CE: dz = (softmax - onehot) / N
    dz = cache["probs"].copy()
    dz[np.arange(N), targets.reshape(-1)] -= 1.0
    dz /= N  # (N,V)

    # 2) 输出投影 + final RMSNorm
    nf = cache["normed_f"].reshape(N, d)
    grads["wout"] += nf.T @ dz
    dnf = (dz @ params["wout"].T).reshape(B, T, d)
    dx, dg = rmsnorm_backward(dnf, cache["x_last"], params["lnf_g"], cache["invf"])
    grads["lnf_g"] += dg

    # 3) 倒序过各层
    for i in reversed(range(cfg.n_layers)):
        pre = f"l{i}"
        c = cache[f"l{i}"]

        # --- FFN: x = x_mid + gelu(normed2@w1)@w2 ---
        dh3 = dx  # 残差直通
        dact = dx @ params[f"{pre}_w2"].T
        grads[f"{pre}_w2"] += c["h1"].reshape(N, -1).T @ dx.reshape(N, d)
        dh1 = gelu_backward(dact, c["z1"], c["t"])  # 注意传 gelu 的输入 z1，非输出 h1
        grads[f"{pre}_w1"] += c["normed2"].reshape(N, d).T @ dh1.reshape(N, -1)
        dnormed2 = dh1 @ params[f"{pre}_w1"].T
        dx_mid, dg2 = rmsnorm_backward(dnormed2, c["x_mid"], params[f"{pre}_ln2_g"], c["inv2"])
        grads[f"{pre}_ln2_g"] += dg2
        dh2 = dh3 + dx_mid

        # --- attention: x = x_in + attn(ln1(x_in)) ---
        dnormed1 = attention_backward(cfg, params, grads, pre, dh2, c["attn"])
        dx_in, dg1 = rmsnorm_backward(dnormed1, c["x_in"], params[f"{pre}_ln1_g"], c["inv1"])
        grads[f"{pre}_ln1_g"] += dg1
        dx = dh2 + dx_in

    # 4) embedding：scatter-add（同一 token 多次出现梯度累加）；
    #    位置编码每个位置对 batch 共享，梯度先沿 batch 维求和
    np.add.at(grads["emb"], idx, dx)
    grads["pos"] += dx.sum(axis=0)
    return grads
