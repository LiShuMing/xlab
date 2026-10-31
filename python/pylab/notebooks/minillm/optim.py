"""§7 Adam 优化器与梯度裁剪 —— keys 白名单即参数冻结机制：stage 1 传全部
键、stage 5 只传 A/B 键，主干梯度就算算出来也不会被 step。
"""

import numpy as np


class Adam:
    def __init__(self, keys, beta1=0.9, beta2=0.999, eps=1e-8):
        self.keys = list(keys)
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
            self.m[k] = self.b1 * self.m[k] + (1 - self.b1) * grads[k]
            self.v[k] = self.b2 * self.v[k] + (1 - self.b2) * grads[k] ** 2
            m_hat = self.m[k] / bc1
            v_hat = self.v[k] / bc2
            params[k] -= lr * m_hat / (np.sqrt(v_hat) + self.eps)


def clip_grad_global(grads, keys, max_norm: float):
    total = np.sqrt(sum(float(np.sum(grads[k] ** 2)) for k in keys))
    if total > max_norm:
        scale = max_norm / (total + 1e-12)
        for k in keys:
            grads[k] *= scale
    return total
