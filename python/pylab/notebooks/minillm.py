"""minillm.py — 薄入口：实现已按功能拆分到 minillm/ 包，此处只保留运行入口。

拆分前是单文件 727 行；拆分后每个模块只负责一件事，阅读顺序建议：

    minillm/config.py      §0  超参数（形状的唯一权威源）
    minillm/tokenizer.py   §1  语料 + 字符级 tokenizer
    minillm/params.py      §2  init_params：唯一一份 params dict 在此诞生
    minillm/ops.py         §3  RMSNorm / GELU 的 fwd+bwd 原语
    minillm/attention.py   §5  split/merge heads + 因果自注意力
    minillm/lora.py        §4 §10 LoRA 旁路、注入、合并、可训键
    minillm/model.py       §6  整体 forward/backward（残差 + 逐层倒放）
    minillm/optim.py       §7  Adam + 全局范数梯度裁剪
    minillm/training.py    §8  采样、数值梯度校验、训练循环
    minillm/inference.py   §9  prefill / decode_step / 采样 / KV 等价性
    minillm/api.py             TinyGPT 门面（cfg + params 收拢为对象）
    minillm/app.py         §11 六 stage 主流程 main()

六个 stage（梯度校验 → 预训练 → 贪心生成 → KV 等价 → LoRA 注入 →
LoRA 微调 + merge）全部由断言守门，运行 `python3 minillm.py` 即完成自验证；
CPU（Apple Silicon）全程约 30 秒。包内任一模块也可单独 import 做实验。
"""

from minillm.app import main

if __name__ == "__main__":
    main()
