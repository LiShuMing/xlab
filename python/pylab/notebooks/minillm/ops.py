"""§3 前向/反向原语：RMSNorm、GELU —— 被 attention 与 model 组装。

每个原语成对提供 forward（缓存反向所需中间量）与 backward。
"""

import numpy as np


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


_GELU_C = np.sqrt(2.0 / np.pi)
_GELU_A = 0.044715


def gelu_forward(x):
    """tanh 近似 GELU: 0.5x(1 + tanh(c(x + a x^3)))。"""
    t = np.tanh(_GELU_C * (x + _GELU_A * x**3))
    return 0.5 * x * (1.0 + t), t


def gelu_backward(dy, x, t):
    dtanh = 1.0 - t * t
    dgelu = 0.5 * (1.0 + t) + 0.5 * x * dtanh * _GELU_C * (1.0 + 3.0 * _GELU_A * x * x)
    return dy * dgelu
