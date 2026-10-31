"""minillm_v2.py — minillm（v1）的组件现代化版本。

把 v1（minillm.py）的六个组件逐项替换为现代 LLM（Llama/Qwen 系）的标准
配置，全部反向传播仍然手写：

    组件         v1（minillm.py）          v2（本文件）
    位置编码     可学习位置表 (T, d)        RoPE 旋转位置编码（无参数、相对位置）
    FFN          GELU MLP（4d，2 矩阵）     SwiGLU（8/3 d，gate/up/down 三矩阵）
    attention    MHA                        GQA 分组查询注意力（KV 头减半 → cache 减半）
    优化器       Adam + 线性 warmup         AdamW 解耦权重衰减 + cosine 退火
    KV cache     concat 追加，每步 O(T)     预分配定长 buffer，decode 每步 O(1) 原地写
    推理部署     无                         INT8 per-channel 权重量化（weight-only）

  Stage 0   梯度数值校验（RoPE/SwiGLU/GQA 路径全覆盖，中心差分 vs 解析梯度）
  Stage 0b  RoPE 相对位置性质：<R_m q, R_n k> 只依赖 m-n
  Stage 1   预训练（AdamW + warmup + cosine 退火）
  Stage 2   贪心生成
  Stage 3   预分配 KV cache 等价性验证 + 内存占用（对比 MHA）
  Stage 4   INT8 量化：logits 偏差 + 生成一致性 + 内存对比
  Stage 5   LoRA 注入/微调/合并（cpu → gpu 行为转变，与 v1 同款 demo）

张量约定与 v1 相同：行向量风格 (B, T, d)，线性层 y = x @ W；attention
内部 (B, H, T, dh)。GQA 的 K/V 是 (B, n_kv, T, dh)，按 group repeat 成
(B, H, T, dh) 再参与打分（HF Llama repeat_kv 的 repeat_interleave 语义）。

运行: python3 minillm_v2.py   （Apple Silicon CPU 上全程约 15 秒）
"""

from dataclasses import dataclass

import numpy as np

# ---------------------------------------------------------------------------
# 0. 超参数
# ---------------------------------------------------------------------------


@dataclass
class Config:
    vocab_size: int
    d_model: int = 64
    n_heads: int = 4          # query 头数
    n_kv_heads: int = 2       # GQA：KV 头数（必须整除 n_heads）
    n_layers: int = 2
    block_size: int = 32
    ffn_mult: float = 8.0 / 3.0   # SwiGLU 惯例宽度；d_ff 向上取到 16 的倍数
    rope_theta: float = 10000.0
    lora_r: int = 4
    lora_alpha: float = 8.0
    weight_decay: float = 0.01
    warmup_steps: int = 40
    final_lr_scale: float = 0.1   # cosine 终点 lr = base_lr * scale

    @property
    def d_head(self) -> int:
        return self.d_model // self.n_heads

    @property
    def d_kv(self) -> int:
        return self.n_kv_heads * self.d_head

    @property
    def d_ff(self) -> int:
        unit = 16
        return int(round(self.ffn_mult * self.d_model / unit)) * unit

    @property
    def attn_scale(self) -> float:
        return 1.0 / np.sqrt(self.d_head)

    @property
    def lora_scale(self) -> float:
        # alpha/r 把秩 r 与更新幅度解耦：调 r 不必重调学习率
        return self.lora_alpha / self.lora_r


# ---------------------------------------------------------------------------
# 1. 语料与字符级 tokenizer（与 v1 一致，便于对比行为）
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 2. 参数初始化（无位置表；K/V 投影只有 n_kv 头宽）
# ---------------------------------------------------------------------------


def init_params(cfg: Config, rng: np.random.Generator) -> dict:
    """全部参数收进一个 dict，键名即参数名；float64 全程以支撑数值梯度校验。"""
    p: dict = {}
    d, std = cfg.d_model, 0.02
    p["emb"] = rng.normal(0, std, size=(cfg.vocab_size, d))
    for i in range(cfg.n_layers):
        pre = f"l{i}"
        p[f"{pre}_ln1_g"] = np.ones(d)
        p[f"{pre}_ln2_g"] = np.ones(d)
        p[f"{pre}_wq"] = rng.normal(0, std, size=(d, d))
        p[f"{pre}_wk"] = rng.normal(0, std, size=(d, cfg.d_kv))
        p[f"{pre}_wv"] = rng.normal(0, std, size=(d, cfg.d_kv))
        p[f"{pre}_wo"] = rng.normal(0, std, size=(d, d))
        p[f"{pre}_w1"] = rng.normal(0, std, size=(d, cfg.d_ff))   # SwiGLU gate
        p[f"{pre}_w3"] = rng.normal(0, std, size=(d, cfg.d_ff))   # SwiGLU up
        p[f"{pre}_w2"] = rng.normal(0, std, size=(cfg.d_ff, d))   # SwiGLU down
    p["lnf_g"] = np.ones(d)
    p["wout"] = rng.normal(0, std, size=(d, cfg.vocab_size))
    return p


# ---------------------------------------------------------------------------
# 3. 前向/反向原语：RMSNorm、sigmoid
# ---------------------------------------------------------------------------


def rmsnorm_forward(x: np.ndarray, g: np.ndarray):
    """y = x / sqrt(mean(x^2) + eps) * g，逐最后一个维度。"""
    inv = 1.0 / np.sqrt(np.mean(x * x, axis=-1, keepdims=True) + 1e-5)
    return x * inv * g, inv


def rmsnorm_backward(dy, x, g, inv):
    """返回 (dx, dg)。dx_i = inv*dxhat_i - inv^3/d * x_i * Σ_j dxhat_j x_j。"""
    d = x.shape[-1]
    dxhat = dy * g
    dg = (dy * x * inv).sum(axis=(0, 1))
    dx = inv * dxhat - (inv**3 / d) * x * (dxhat * x).sum(axis=-1, keepdims=True)
    return dx, dg


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


# ---------------------------------------------------------------------------
# 4. RoPE 旋转位置编码（无参数；施加在 attention 内部的 q/k 上）
# ---------------------------------------------------------------------------


def rope_tables(positions: np.ndarray, half: int, theta: float):
    """cos/sin 表 (len(positions), half)。频率按 theta^(2i/dh) 几何递减，
    低频维度转得慢 → 编码远距离相对位置，高频维度编码局部顺序。"""
    inv_freq = theta ** (-np.arange(half, dtype=np.float64) / half)
    ang = np.asarray(positions, dtype=np.float64)[:, None] * inv_freq
    return np.cos(ang), np.sin(ang)


def rope_forward(x, cos, sin):
    """把 (B,H,T,dh) 按位置旋转：前 half 维与后 half 维两两配对，
    每对是一个二维平面旋转角 m*inv_freq 的旋转。"""
    half = x.shape[-1] // 2
    x1, x2 = x[..., :half], x[..., half:]
    return np.concatenate([x1 * cos - x2 * sin, x1 * sin + x2 * cos], axis=-1)


def rope_backward(dy, cos, sin):
    """RoPE 是逐 2 维平面的正交旋转，反向 = 用 -角度再旋转一次（转置）。"""
    half = dy.shape[-1] // 2
    d1, d2 = dy[..., :half], dy[..., half:]
    return np.concatenate([d1 * cos + d2 * sin, -d1 * sin + d2 * cos], axis=-1)


def check_rope_relative_property(cfg: Config, rng: np.random.Generator) -> float:
    """核心性质：<R_m q, R_n k> 只依赖 m-n（attention 打分天然只看相对位置），
    与绝对位置无关——这是 RoPE 替换可学习位置表的根本原因。"""
    dh = cfg.d_head
    q = rng.normal(size=dh)
    k = rng.normal(size=dh)

    def rot(v: np.ndarray, m: int) -> np.ndarray:
        cos, sin = rope_tables(np.array([m]), dh // 2, cfg.rope_theta)
        return rope_forward(v[None, None, None, :], cos, sin)[0, 0, 0]

    worst = 0.0
    for m, n, shift in ((3, 7, 5), (0, 11, 4), (13, 6, 9), (2, 2, 17)):
        base = float(rot(q, m) @ rot(k, n))
        moved = float(rot(q, m + shift) @ rot(k, n + shift))
        worst = max(worst, abs(base - moved))
    return worst


# ---------------------------------------------------------------------------
# 5. SwiGLU FFN：h = silu(x@w1) * (x@w3)，y = h@w2
# ---------------------------------------------------------------------------


def swiglu_forward(x, w1, w2, w3):
    """silu(z) = z * sigmoid(z)；gate 支路控制 up 支路每个维度的通断。"""
    a = x @ w1            # gate 支路预激活
    sg = sigmoid(a)
    s = a * sg            # silu
    b = x @ w3            # up 支路
    h = s * b
    return h @ w2, (x, a, sg, b, h)


def swiglu_backward(cfg: Config, params, layer: str, grads: dict, dy, cache):
    """返回对 FFN 输入（RMSNorm 输出）的梯度 dnormed2。"""
    x, a, sg, b, h = cache
    s = a * sg  # silu 输出：cache 未直接存，逐元素乘重算即可
    d = cfg.d_model
    N = x.shape[0] * x.shape[1]
    xf = x.reshape(N, d)
    dyf = dy.reshape(N, d)

    dh = dy @ params[f"{layer}_w2"].T
    grads[f"{layer}_w2"] += h.reshape(N, -1).T @ dyf
    ds = dh * b                                   # ∂h/∂s = b
    db = dh * s                                   # ∂h/∂b = s
    dsilu = sg * (1.0 + a * (1.0 - sg))           # silu'(a) = sg * (1 + a(1-sg))
    da = ds * dsilu
    grads[f"{layer}_w1"] += xf.T @ da.reshape(N, -1)
    grads[f"{layer}_w3"] += xf.T @ db.reshape(N, -1)
    return da @ params[f"{layer}_w1"].T + db @ params[f"{layer}_w3"].T


# ---------------------------------------------------------------------------
# 6. LoRA 旁路（旁路反向内联在 attention_backward 的 wq/wv 处）
# ---------------------------------------------------------------------------


def lora_keys(layer: str, name: str) -> tuple:
    return (f"{layer}_{name}.lora_A", f"{layer}_{name}.lora_B")


def lora_forward(params, cfg: Config, layer: str, name: str, x, base_out):
    """out = x@W + s*((x@A)@B)。返回 (总输出, 缓存或 None)。缓存供反向与校验。"""
    ka, kb = lora_keys(layer, name)
    if ka not in params:
        return base_out, None
    A, B = params[ka], params[kb]
    xa = x @ A            # (B,T,r) 降维
    side = xa @ B         # (B,T,d_out) 升维（wq 为 d，wv 为 n_kv*dh）
    return base_out + cfg.lora_scale * side, (x, xa)


def merge_lora(params, cfg: Config, projections):
    """训练完把 s*(A@B) 烘进 W：推理零额外延迟。"""
    for layer, name in projections:
        ka, kb = lora_keys(layer, name)
        params[f"{layer}_{name}"] += cfg.lora_scale * (params[ka] @ params[kb])
        del params[ka], params[kb]


# ---------------------------------------------------------------------------
# 7. GQA attention（含 RoPE；batch 版，(B,H,T,dh) 布局）
# ---------------------------------------------------------------------------


def split_heads(x, B, T, H, dh):
    return x.reshape(B, T, H, dh).transpose(0, 2, 1, 3)  # (B,H,T,dh)


def merge_heads(x, B, T, d):
    return x.transpose(0, 2, 1, 3).reshape(B, T, d)


def attention_forward(cfg: Config, params, layer: str, x, cos, sin):
    """训练态因果 GQA 自注意力 + RoPE。x: (B,T,d) 已 RMSNorm。返回 (out, cache)。"""
    B, T, d = x.shape
    H, KH, dh, s = cfg.n_heads, cfg.n_kv_heads, cfg.d_head, cfg.attn_scale
    g = H // KH

    q = x @ params[f"{layer}_wq"]
    q, lq = lora_forward(params, cfg, layer, "wq", x, q)
    k = x @ params[f"{layer}_wk"]          # (B,T,KH*dh)
    v = x @ params[f"{layer}_wv"]
    v, lv = lora_forward(params, cfg, layer, "wv", x, v)

    qh = rope_forward(split_heads(q, B, T, H, dh), cos, sin)    # (B,H,T,dh)
    kh = rope_forward(split_heads(k, B, T, KH, dh), cos, sin)   # (B,KH,T,dh)
    vh = split_heads(v, B, T, KH, dh)

    # GQA：每 1 个 KV 头服务 g 个连续 query 头（repeat_interleave 语义）
    kh_f = np.repeat(kh, g, axis=1)        # (B,H,T,dh)
    vh_f = np.repeat(vh, g, axis=1)

    scores = np.matmul(qh, np.swapaxes(kh_f, -1, -2)) * s   # (B,H,T,T)
    mask = np.triu(np.ones((T, T), dtype=bool), k=1)         # 严格上三角：只看过去
    scores = np.where(mask, -1e9, scores)
    p_attn = np.exp(scores - scores.max(axis=-1, keepdims=True))
    p_attn /= p_attn.sum(axis=-1, keepdims=True)
    oh = np.matmul(p_attn, vh_f)                             # (B,H,T,dh)
    merged = merge_heads(oh, B, T, d)
    out = merged @ params[f"{layer}_wo"]
    cache = dict(x=x, qh=qh, kh=kh, vh=vh, p_attn=p_attn, merged=merged,
                 cos=cos, sin=sin, lora_wq=lq, lora_wv=lv)
    return out, cache


def attention_backward(cfg: Config, params, grads, layer: str, dout, cache):
    """返回对 attention 输入（RMSNorm 输出）的梯度 dnormed。"""
    B, T, d = cache["x"].shape
    H, KH, dh, s = cfg.n_heads, cfg.n_kv_heads, cfg.d_head, cfg.attn_scale
    g = H // KH
    x = cache["x"]
    xf = x.reshape(B * T, d)
    cos, sin = cache["cos"], cache["sin"]

    dmerged = dout @ params[f"{layer}_wo"].T
    grads[f"{layer}_wo"] += cache["merged"].reshape(B * T, d).T @ dout.reshape(B * T, d)

    doh = split_heads(dmerged, B, T, H, dh)                  # (B,H,T,dh)
    kh_f = np.repeat(cache["kh"], g, axis=1)
    vh_f = np.repeat(cache["vh"], g, axis=1)
    dp_attn = np.matmul(doh, np.swapaxes(vh_f, -1, -2))
    dv_f = np.matmul(np.swapaxes(cache["p_attn"], -1, -2), doh)   # (B,H,T,dh)
    # softmax 反向：mask 格子 p=0，梯度自然为 0
    dps = cache["p_attn"] * (dp_attn - (dp_attn * cache["p_attn"]).sum(-1, keepdims=True))
    dqh_rot = np.matmul(dps, kh_f) * s        # 旋转后坐标系下的 dq
    dkh_f_rot = np.matmul(np.swapaxes(dps, -1, -2), cache["qh"]) * s  # 注意：用旋转后的 q，非 doh

    # RoPE 反向 = 反向旋转；K/V 头先按 group 求和折回 n_kv，再反向旋转
    # （rope_backward 线性，与求和可交换：rope_bwd(Σ·) = Σ rope_bwd(·)）
    dqh = rope_backward(dqh_rot, cos, sin)
    dkh_rot = dkh_f_rot.reshape(B, KH, g, T, dh).sum(axis=2)
    dkh = rope_backward(dkh_rot, cos, sin)
    dv = dv_f.reshape(B, KH, g, T, dh).sum(axis=2)

    dq = merge_heads(dqh, B, T, d)
    dk = merge_heads(dkh, B, T, cfg.d_kv)
    dv = merge_heads(dv, B, T, cfg.d_kv)

    dnormed = np.zeros_like(x)
    # 主路投影：∂q/∂Wq = x 与 LoRA 无关，梯度恒为 x^T @ dq
    grads[f"{layer}_wq"] += xf.T @ dq.reshape(B * T, d)
    dnormed += dq @ params[f"{layer}_wq"].T
    grads[f"{layer}_wk"] += xf.T @ dk.reshape(B * T, cfg.d_kv)
    dnormed += dk @ params[f"{layer}_wk"].T
    grads[f"{layer}_wv"] += xf.T @ dv.reshape(B * T, cfg.d_kv)
    dnormed += dv @ params[f"{layer}_wv"].T

    # LoRA 旁路：dside = s*dout；dA = x^T(dside B^T)，dB = (xA)^T dside
    for name, dout_pv, lc in (("wq", dq, cache["lora_wq"]), ("wv", dv, cache["lora_wv"])):
        if lc is None:
            continue
        xa = lc[1]  # (B,T,r) 前向缓存的降维结果
        ka, kb = lora_keys(layer, name)
        A_mat, B_mat = params[ka], params[kb]
        dside = (cfg.lora_scale * dout_pv).reshape(B * T, -1)
        dxa = dside @ B_mat.T                                  # (B*T, r)
        grads[ka] += xf.T @ dxa                                # (d,r)
        grads[kb] += xa.reshape(B * T, -1).T @ dside           # (r,d_out)
        dnormed += dxa.reshape(B, T, -1) @ A_mat.T             # (B,T,d)
    return dnormed


# ---------------------------------------------------------------------------
# 8. 完整前向/反向
# ---------------------------------------------------------------------------


def forward(params, cfg: Config, idx: np.ndarray, targets=None):
    """idx (B,T) int → logits (B,T,V)。给 targets 时同时返回平均 CE loss。"""
    B, T = idx.shape
    d = cfg.d_model
    cache: dict = {"idx": idx}
    x = params["emb"][idx]  # RoPE 无参数且按位置旋转，不再加可学习位置表
    cos, sin = rope_tables(np.arange(T), cfg.d_head // 2, cfg.rope_theta)

    for i in range(cfg.n_layers):
        pre = f"l{i}"
        x_in = x
        normed1, inv1 = rmsnorm_forward(x, params[f"{pre}_ln1_g"])
        attn_out, attn_cache = attention_forward(cfg, params, pre, normed1, cos, sin)
        x = x_in + attn_out  # 残差 1
        x_mid = x
        normed2, inv2 = rmsnorm_forward(x, params[f"{pre}_ln2_g"])
        ffn_out, ffn_cache = swiglu_forward(
            normed2, params[f"{pre}_w1"], params[f"{pre}_w2"], params[f"{pre}_w3"])
        x = x_mid + ffn_out  # 残差 2
        cache[f"l{i}"] = dict(x_in=x_in, inv1=inv1, attn=attn_cache,
                              x_mid=x_mid, inv2=inv2, normed2=normed2,
                              ffn=ffn_cache)

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
    """从 CE loss 反传到全部参数。返回 grads（与 params 同键，累加语义）。"""
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

        # --- FFN: x = x_mid + swiglu(normed2) ---
        dh2 = dx  # 残差直通
        dnormed2 = swiglu_backward(cfg, params, pre, grads, dx, c["ffn"])
        dx_mid, dg2 = rmsnorm_backward(dnormed2, c["x_mid"],
                                       params[f"{pre}_ln2_g"], c["inv2"])
        grads[f"{pre}_ln2_g"] += dg2
        dh2 = dh2 + dx_mid

        # --- attention: x = x_in + attn(ln1(x_in)) ---
        dnormed1 = attention_backward(cfg, params, grads, pre, dh2, c["attn"])
        dx_in, dg1 = rmsnorm_backward(dnormed1, c["x_in"],
                                      params[f"{pre}_ln1_g"], c["inv1"])
        grads[f"{pre}_ln1_g"] += dg1
        dx = dh2 + dx_in

    # 4) embedding：scatter-add（同一 token 多次出现梯度累加）
    np.add.at(grads["emb"], idx, dx)
    return grads


# ---------------------------------------------------------------------------
# 9. AdamW、cosine 调度与梯度裁剪
# ---------------------------------------------------------------------------

# 这些后缀的 2-D 矩阵做解耦 weight decay；embedding / norm 增益 / LoRA 不衰减
DECAY_SUFFIXES = ("wq", "wk", "wv", "wo", "w1", "w2", "w3", "wout")


def decay_keys_of(params) -> set:
    return {k for k in params if k.split("_")[-1] in DECAY_SUFFIXES}


class AdamW:
    """Adam + 解耦权重衰减（AdamW）：衰减项不进动量，直接缩参数。"""

    def __init__(self, keys, wd_keys=frozenset(), weight_decay: float = 0.01,
                 beta1: float = 0.9, beta2: float = 0.999, eps: float = 1e-8):
        self.keys = list(keys)
        self.wd_keys = set(wd_keys)
        self.wd = weight_decay
        self.b1, self.b2, self.eps = beta1, beta2, eps
        self.m: dict = {}
        self.v: dict = {}
        self.t = 0

    def step(self, params, grads, lr: float):
        self.t += 1
        bc1 = 1.0 - self.b1**self.t
        bc2 = 1.0 - self.b2**self.t
        for k in self.keys:
            if k not in self.m:
                self.m[k] = np.zeros_like(params[k])
                self.v[k] = np.zeros_like(params[k])
            g = grads[k]
            self.m[k] = self.b1 * self.m[k] + (1 - self.b1) * g
            self.v[k] = self.b2 * self.v[k] + (1 - self.b2) * g * g
            m_hat = self.m[k] / bc1
            v_hat = self.v[k] / bc2
            params[k] -= lr * m_hat / (np.sqrt(v_hat) + self.eps)
            if k in self.wd_keys:
                params[k] -= lr * self.wd * params[k]


def cosine_lr(step: int, total: int, base_lr: float, warmup: int,
              final_scale: float) -> float:
    """线性 warmup → cosine 退火到 base_lr * final_scale。"""
    if step <= warmup:
        return base_lr * step / max(1, warmup)
    prog = min(1.0, (step - warmup) / max(1, total - warmup))
    return base_lr * (final_scale + (1.0 - final_scale) * 0.5 * (1.0 + np.cos(np.pi * prog)))


def clip_grad_global(grads, keys, max_norm: float):
    total = np.sqrt(sum(float(np.sum(grads[k] ** 2)) for k in keys))
    if total > max_norm:
        scale = max_norm / (total + 1e-12)
        for k in keys:
            grads[k] *= scale
    return total


# ---------------------------------------------------------------------------
# 10. 数据采样、数值梯度校验与训练
# ---------------------------------------------------------------------------


def sample_batch(data: np.ndarray, block: int, batch: int, rng):
    ix = rng.integers(0, len(data) - block - 1, size=batch)
    x = np.stack([data[i:i + block] for i in ix])
    y = np.stack([data[i + 1:i + block + 1] for i in ix])
    return x, y


def numerical_grad_check(cfg: Config, params, data: np.ndarray, rng,
                         keys, n_checks: int = 4, eps: float = 1e-5):
    """中心差分 vs 解析梯度；float64 下相对误差应 < 1e-5。"""
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
          lr: float, batch: int, log_every: int, tag: str,
          wd_keys=frozenset(), schedule: str = "cosine"):
    """keys 决定训练哪些参数：预训练为全部参数，LoRA 阶段只有 A/B（主干冻结）。"""
    opt = AdamW(keys, wd_keys=wd_keys, weight_decay=cfg.weight_decay)
    for step in range(1, steps + 1):
        xb, yb = sample_batch(data, cfg.block_size, batch, rng)
        _, loss, cache = forward(params, cfg, xb, yb)
        grads = backward(cfg, params, cache, yb)
        clip_grad_global(grads, keys, 1.0)
        if schedule == "cosine":
            lr_eff = cosine_lr(step, steps, lr, cfg.warmup_steps, cfg.final_lr_scale)
        else:  # LoRA 微调：常数学习率 + 短 warmup（小秩旁路不需要退火）
            lr_eff = lr * min(1.0, step / 20.0)
        opt.step(params, grads, lr_eff)
        if step == 1 or step % log_every == 0:
            print(f"  [{tag}] step {step:4d}  loss {loss:.4f}  "
                  f"ppl {np.exp(loss):7.2f}  lr {lr_eff:.2e}")
    return params


# ---------------------------------------------------------------------------
# 11. 预分配 KV cache 推理：prefill + decode + 采样
# ---------------------------------------------------------------------------


class KVCache:
    """预分配定长 KV 缓冲 (n_layers, n_kv, block, dh)。

    decode 每步在 pos 处 O(1) 原地写入；v1 用 concat 追加，每步都要 O(T)
    拷贝整段历史。GQA 下 KV 头数是 H/2，cache 内存相对 MHA 直接减半——
    这正是 GQA 服务于推理吞吐的核心收益（真实引擎如 vLLM 进一步分页化）。
    """

    def __init__(self, cfg: Config):
        shape = (cfg.n_layers, cfg.n_kv_heads, cfg.block_size, cfg.d_head)
        self.k = np.zeros(shape)
        self.v = np.zeros(shape)

    @property
    def nbytes(self) -> int:
        return self.k.nbytes + self.v.nbytes


def prefill(params, cfg: Config, ids: np.ndarray):
    """整段 prompt 一次算完，返回最后位置 logits 与预分配 cache（已填充）。"""
    ids = np.atleast_2d(np.asarray(ids))  # 兼容 1D 序列与 (1,T) 批量两种入参
    logits, _, cache = forward(params, cfg, ids)
    T = ids.shape[1]
    kv = KVCache(cfg)
    for i in range(cfg.n_layers):
        attn = cache[f"l{i}"]["attn"]
        kv.k[i, :, :T] = attn["kh"][0]   # 已旋转的 K（post-RoPE、pre-repeat）
        kv.v[i, :, :T] = attn["vh"][0]
    return logits[0, -1], kv


def decode_step(params, cfg: Config, tok: int, kv: KVCache, pos: int):
    """单 token 增量 decode：只算当前 q，K/V 原地写入预分配 buffer。
    Tq=1、Tk>1：因果性由 cache 只存历史在结构上保证，无需掩码。"""
    d, H, KH, dh, s = cfg.d_model, cfg.n_heads, cfg.n_kv_heads, cfg.d_head, cfg.attn_scale
    g = H // KH
    x = params["emb"][tok][None, None, :]  # (1,1,d)
    cos, sin = rope_tables(np.array([pos]), dh // 2, cfg.rope_theta)
    for i in range(cfg.n_layers):
        pre = f"l{i}"
        normed1, _ = rmsnorm_forward(x, params[f"{pre}_ln1_g"])
        q = normed1 @ params[f"{pre}_wq"]
        q, _ = lora_forward(params, cfg, pre, "wq", normed1, q)
        k = normed1 @ params[f"{pre}_wk"]
        v = normed1 @ params[f"{pre}_wv"]
        v, _ = lora_forward(params, cfg, pre, "wv", normed1, v)
        qh = rope_forward(split_heads(q, 1, 1, H, dh), cos, sin)
        kh = rope_forward(split_heads(k, 1, 1, KH, dh), cos, sin)
        vh = split_heads(v, 1, 1, KH, dh)
        kv.k[i, :, pos:pos + 1] = kh[0]   # O(1) 原地写：(KH,1,dh)
        kv.v[i, :, pos:pos + 1] = vh[0]
        K = kv.k[i, :, :pos + 1][None]          # (1,KH,Tk,dh)
        V = kv.v[i, :, :pos + 1][None]
        kh_f = np.repeat(K, g, axis=1)
        vh_f = np.repeat(V, g, axis=1)
        scores = np.matmul(qh, np.swapaxes(kh_f, -1, -2)) * s   # (1,H,1,Tk)
        p_attn = np.exp(scores - scores.max(axis=-1, keepdims=True))
        p_attn /= p_attn.sum(axis=-1, keepdims=True)
        oh = np.matmul(p_attn, vh_f)
        x = x + merge_heads(oh, 1, 1, d) @ params[f"{pre}_wo"]

        normed2, _ = rmsnorm_forward(x, params[f"{pre}_ln2_g"])
        ffn_out, _ = swiglu_forward(normed2, params[f"{pre}_w1"],
                                    params[f"{pre}_w2"], params[f"{pre}_w3"])
        x = x + ffn_out

    normed_f, _ = rmsnorm_forward(x, params["lnf_g"])
    return (normed_f @ params["wout"])[0, 0], kv


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
    rng = rng or np.random.default_rng(0)
    ids = tokenizer.encode(prompt).tolist()
    logits, kv = prefill(params, cfg, np.array(ids))
    nxt = sample_token(logits, temperature, top_k, rng)
    ids.append(nxt)
    for _ in range(n_new - 1):
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
        logits, kv = decode_step(params, cfg, int(ids[t]), kv, t)
        full = forward(params, cfg, np.array([ids[:t + 1]]))[0][0, -1]
        worst = max(worst, float(np.abs(full - logits).max()))
    return worst


# ---------------------------------------------------------------------------
# 12. INT8 per-channel 权重量化（weight-only）
# ---------------------------------------------------------------------------

QUANT_KEYS = ("wq", "wk", "wv", "wo", "w1", "w2", "w3")  # 线性层；wout 单独加


def quantize_int8(W: np.ndarray):
    """per-output-channel 对称量化：W (in, out) 的每列独立 scale = max|W[:,j]|/127。
    dequant 误差每元素 ≤ scale/2，即相对幅度 ~0.4%。"""
    scale = np.abs(W).max(axis=0) / 127.0
    scale = np.where(scale == 0.0, 1.0, scale)
    q = np.clip(np.round(W / scale), -127, 127).astype(np.int8)
    return q, scale


def dequantize_int8(q: np.ndarray, scale: np.ndarray) -> np.ndarray:
    return q.astype(np.float64) * scale


def quantized_params(params, cfg: Config) -> dict:
    """把全部线性层权重换成 int8 → 反量化值的参数副本（weight-only int8 的
    模拟：真实引擎存 int8，计算时反量化或走 int8 GEMM）。"""
    qp = dict(params)
    keys = [f"l{i}_{n}" for i in range(cfg.n_layers) for n in QUANT_KEYS]
    keys.append("wout")
    for k in keys:
        q, s = quantize_int8(params[k])
        qp[k] = dequantize_int8(q, s)
    return qp


def quant_memory_report(params, cfg: Config) -> tuple:
    """返回 (fp 总字节, int8 方案总字节, 量化键列表)。"""
    keys = [f"l{i}_{n}" for i in range(cfg.n_layers) for n in QUANT_KEYS] + ["wout"]
    fp_total = sum(p.nbytes for p in params.values())
    quant_elems = sum(params[k].size for k in keys)
    scale_bytes = sum(params[k].shape[-1] * 8 for k in keys)
    keep_fp = fp_total - sum(params[k].nbytes for k in keys)
    return fp_total, keep_fp + quant_elems + scale_bytes, keys


# ---------------------------------------------------------------------------
# 13. LoRA 注入
# ---------------------------------------------------------------------------


def inject_lora(params, cfg: Config, rng: np.random.Generator, projections):
    """A 随机、B 零初始化：B=0 ⇒ ΔW=0，起点与基座逐位一致；
    且 dL/dB ∝ (x@A)^T ≠ 0，第一步即可更新 B（A=B=0 会永久梯度死锁）。"""
    for layer, name in projections:
        d_out = cfg.d_model if name == "wq" else cfg.d_kv
        ka, kb = lora_keys(layer, name)
        params[ka] = rng.normal(0, 0.02, size=(cfg.d_model, cfg.lora_r))
        params[kb] = np.zeros((cfg.lora_r, d_out))


def lora_trainable_keys(params) -> list:
    return [k for k in params if ".lora_" in k]


# ---------------------------------------------------------------------------
# 14. 主流程
# ---------------------------------------------------------------------------


def main():
    import time

    t0 = time.time()
    # Apple Accelerate BLAS 在部分 float64 GEMM 上会误置 FP 异常 flag
    # （numpy 2.4.4 已知现象），数值结果正确——由 stage 0 梯度校验与各
    # 阶段断言兜底验证，故此处仅静默 FP 警告。
    np.seterr(divide="ignore", invalid="ignore", over="ignore")

    rng = np.random.default_rng(0)
    tokenizer = CharTokenizer(PRETRAIN_TEXT + "\n" + LORA_TEXT)
    cfg = Config(vocab_size=tokenizer.vocab_size)
    data_pre = tokenizer.encode(PRETRAIN_TEXT)
    data_lora = tokenizer.encode(LORA_TEXT)
    projections = [(f"l{i}", n) for i in range(cfg.n_layers) for n in ("wq", "wv")]

    print(f"vocab={cfg.vocab_size} d={cfg.d_model} q_heads={cfg.n_heads} "
          f"kv_heads={cfg.n_kv_heads} (GQA {cfg.n_heads // cfg.n_kv_heads}:1) "
          f"layers={cfg.n_layers} block={cfg.block_size} "
          f"d_ff={cfg.d_ff} (SwiGLU) rope_theta={cfg.rope_theta:g} "
          f"corpus={len(data_pre)}+{len(data_lora)} chars")

    # ---- Stage 0: 数值梯度校验（RoPE/SwiGLU/GQA 全路径）----
    params = init_params(cfg, rng)
    worst = numerical_grad_check(cfg, params, data_pre, rng,
                                 keys=["emb", "l0_wq", "l0_wk", "l0_wv",
                                       "l1_w1", "l1_w2", "l1_w3", "lnf_g", "wout"])
    print(f"[stage 0] grad check OK: worst rel err = {worst:.2e}")

    # ---- Stage 0b: RoPE 相对位置性质 ----
    viol = check_rope_relative_property(cfg, rng)
    assert viol < 1e-10, f"RoPE relative-position property violated: {viol:.2e}"
    print(f"[stage 0b] RoPE relative-position property OK: max violation = {viol:.2e}")

    # ---- Stage 1: 预训练（AdamW + warmup + cosine 退火）----
    print("[stage 1] pretraining ...")
    train(params, cfg, data_pre, rng, keys=list(params.keys()),
          steps=400, lr=3e-3, batch=16, log_every=80, tag="pretrain",
          wd_keys=decay_keys_of(params), schedule="cosine")
    n_params = sum(p.size for p in params.values())
    print(f"[stage 1] done, {n_params} params (float64, no pos table)")

    # ---- Stage 2: 预训练模型贪心生成 ----
    # 生成长度受 context window 约束：prompt(12) + n_new ≤ block_size(32)
    prompt = "llm runs on "
    n_gen = cfg.block_size - len(prompt) - 1
    gen_kw = dict(temperature=0.5, top_k=1)  # 贪心解码：行为对比需确定性
    print(f"[stage 2] generate | prompt={prompt!r} n_new={n_gen}")
    out_base = generate(params, cfg, tokenizer, prompt, n_gen, rng=rng, **gen_kw)
    print(f"  -> {out_base!r}")

    # ---- Stage 3: 预分配 KV cache 等价性 + 内存 ----
    worst_kv = verify_kv_equivalence(params, cfg, PRETRAIN_LINES[2], tokenizer)
    assert worst_kv < 1e-9, f"kv cache mismatch: {worst_kv:.2e}"
    kv0 = KVCache(cfg)
    mha_bytes = kv0.nbytes * (cfg.n_heads // cfg.n_kv_heads)
    print(f"[stage 3] KV cache equivalence OK: max|full - decode| = {worst_kv:.2e}")
    print(f"[stage 3] preallocated cache = {kv0.nbytes} B "
          f"(MHA would be {mha_bytes} B, GQA saves "
          f"{1 - kv0.nbytes / mha_bytes:.0%})")

    # ---- Stage 4: INT8 weight-only 量化 ----
    qp = quantized_params(params, cfg)
    probe = np.array([tokenizer.encode(prompt + "cpu.")])
    logits_fp = forward(params, cfg, probe)[0]
    logits_q = forward(qp, cfg, probe)[0]
    diff = float(np.abs(logits_fp - logits_q).max())
    assert diff < 1.0, f"int8 logit drift too large: {diff:.3f}"
    out_q = generate(qp, cfg, tokenizer, prompt, n_gen, rng=rng, **gen_kw)
    fp_total, int8_total, _ = quant_memory_report(params, cfg)
    print(f"[stage 4] INT8 quantization: max|Δlogit| = {diff:.2e} "
          f"(rel {diff / max(1e-9, float(np.abs(logits_fp).max())):.1e})")
    print(f"[stage 4] greedy generation fp64 vs int8: "
          f"{'一致' if out_q == out_base else '分歧'} -> {out_q!r}")
    print(f"[stage 4] memory: {fp_total / 1024:.1f} KB (fp64) -> "
          f"{int8_total / 1024:.1f} KB, {fp_total / int8_total:.1f}x")

    # ---- Stage 5: LoRA 注入（B=0 ⇒ 输出逐位不变）----
    inject_lora(params, cfg, rng, projections)
    diff_init = float(np.abs(
        forward(params, cfg, probe)[0] - forward(
            {k: v for k, v in params.items() if ".lora_" not in k},
            cfg, probe)[0]).max())
    assert diff_init == 0.0, f"LoRA init should be exact identity, got {diff_init:.2e}"
    print(f"[stage 5] LoRA injected; init identity OK: max|diff| = {diff_init:.1f}")

    # 给 B 一点更新再校验 LoRA 梯度：绕开 A=B=0 死锁点，检验的是有效状态
    for (layer, name) in projections:
        ka, kb = lora_keys(layer, name)
        params[kb] += rng.normal(0, 0.02, size=params[kb].shape)
    worst_lora = numerical_grad_check(cfg, params, data_lora, rng,
                                      keys=lora_trainable_keys(params))
    print(f"[stage 5] LoRA grad check OK: worst rel err = {worst_lora:.2e}")

    # ---- Stage 5: LoRA 微调（冻结主干，只训 A/B）+ 合并 + 行为转变 ----
    print("[stage 5] LoRA finetuning on 'gpu' corpus (base frozen) ...")
    base_backup = {k: params[k].copy() for k in params if ".lora_" not in k}
    train(params, cfg, data_lora, rng, keys=lora_trainable_keys(params),
          steps=1200, lr=3e-3, batch=16, log_every=300, tag="lora",
          wd_keys=frozenset(), schedule="constant")
    drifted = max(float(np.abs(params[k] - base_backup[k]).max())
                  for k in base_backup)
    print(f"[stage 5] base drift = {drifted:.2e} (0.0 = frozen as expected)")

    out_lora = generate(params, cfg, tokenizer, prompt, n_gen, rng=rng, **gen_kw)
    print(f"[stage 5] generate after LoRA | prompt={prompt!r}")
    print(f"  -> {out_lora!r}")

    # 合并等价性：分路前向 vs 烘进 W 的前向，实数上同函数，浮点上 ulp 级一致
    logits_split = forward(params, cfg, probe)[0]
    merge_lora(params, cfg, projections)
    logits_merged = forward(params, cfg, probe)[0]
    diff_merge = float(np.abs(logits_split - logits_merged).max())
    assert diff_merge < 1e-9, f"merge mismatch: {diff_merge:.2e}"
    print(f"[stage 5] merge equivalence OK: max|split - merged| = {diff_merge:.2e}")

    out_merged = generate(params, cfg, tokenizer, prompt, n_gen, rng=rng, **gen_kw)
    print(f"[stage 5] generate after merge | prompt={prompt!r}")
    print(f"  -> {out_merged!r}")

    print(f"[done] all stages passed in {time.time() - t0:.1f}s.")


if __name__ == "__main__":
    main()
