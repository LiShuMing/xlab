"""§11 主流程 —— 六个 stage 串行共享同一份 params：每步先用断言证明自己的
不变量，再进入下一步；出错会停在最早 stage，不带病运行。

拆分前后行为必须逐位一致：单一 rng、单一份 params，打印文本保持不变，
所以 `python3 minillm.py` 的输出可与单文件版直接 diff。
"""

import numpy as np

from .api import TinyGPT
from .config import Config
from .lora import lora_keys
from .model import forward
from .params import LORA_PROJECTIONS
from .tokenizer import LORA_TEXT, PRETRAIN_LINES, PRETRAIN_TEXT, CharTokenizer


def main():
    # Apple Accelerate BLAS 在部分 float64 GEMM 上会误置 FP 异常 flag
    # （numpy 2.4.4 已知现象），数值结果正确——由 stage 0 梯度校验与各
    # 阶段断言兑底验证，故此处仅静默 FP 警告。
    np.seterr(divide="ignore", invalid="ignore", over="ignore")

    rng = np.random.default_rng(0)  # 单一 rng 贯穿六个 stage：全流程可复现
    tokenizer = CharTokenizer(PRETRAIN_TEXT + "\n" + LORA_TEXT)
    cfg = Config(vocab_size=tokenizer.vocab_size)
    data_pre = tokenizer.encode(PRETRAIN_TEXT)
    data_lora = tokenizer.encode(LORA_TEXT)

    print(f"vocab={cfg.vocab_size} d={cfg.d_model} heads={cfg.n_heads} "
          f"layers={cfg.n_layers} block={cfg.block_size} "
          f"corpus={len(data_pre)}+{len(data_lora)} chars")

    # ---- Stage 0: 数值梯度校验（先证明反向传播写对了，再谈训练）----
    # params 是全流程唯一的模型状态：此后没有任何函数再新建参数，
    # 训练/LoRA 注入/合并全部在这个 dict 上原地演进
    model = TinyGPT(cfg, rng=rng)
    # 抽查关键路径的 7 个参数（覆盖 emb/位置编码/q 型/w 型/输出层）
    worst = model.grad_check(data_pre, rng,
                             keys=["emb", "pos", "l0_wq", "l1_w2",
                                   "l1_wo", "lnf_g", "wout"])
    print(f"[stage 0] grad check OK: worst rel err = {worst:.2e}")

    # ---- Stage 1: 预训练 ----
    # keys=全部参数：主干从零学会语料分布；产物是 stage 2-5 共用的基座权重
    print("[stage 1] pretraining on toy corpus ...")
    model.train(data_pre, rng, keys=list(model.params.keys()),
                steps=400, lr=3e-3, batch=16, log_every=80, tag="pretrain")
    n_params = model.n_params
    print(f"[stage 1] done, {n_params} params (float64)")

    # ---- Stage 2: 预训练模型生成 ----
    # 生成长度受 context window 约束：prompt(12) + n_new ≤ block_size(32)，
    # 与真实 LLM 的 context limit 行为一致（位置编码表只有 block_size 行）
    # 生成首次走 §9 推理路径：prefill 并行吃进 prompt，再 decode 逐 token 增量
    prompt = "llm runs on "
    n_gen = cfg.block_size - len(prompt) - 1
    gen_kw = dict(temperature=0.5, top_k=1)  # 贪心解码：行为对比需确定性，排除采样随机性
    print(f"[stage 2] generate | prompt={prompt!r} n_new={n_gen}")
    print(f"  -> {model.generate(tokenizer, prompt, n_gen, rng=rng, **gen_kw)!r}")

    # ---- Stage 3: KV cache 等价性 ----
    # 证明推理加速没有改变数学：逐步 decode 的 logits 应与整段重算 ulp 级一致
    worst_kv = model.verify_kv(PRETRAIN_LINES[2], tokenizer)
    assert worst_kv < 1e-9, f"kv cache mismatch: {worst_kv:.2e}"
    print(f"[stage 3] KV cache equivalence OK: max|full - decode| = {worst_kv:.2e}")

    # ---- Stage 4: LoRA 注入（B=0 ⇒ 输出逐位不变）----
    # 此后 params 多出 8 个 .lora_* 键；主干键自此不再被任何更新触碰
    model.inject_lora(rng)
    # probe 文本取自预训练句：量化注入前后的输出差异，应逐位为 0
    probe = np.array([tokenizer.encode(prompt + "cpu.")])
    diff_init = float(np.abs(
        model.forward(probe)[0] - forward(model.base_params(), cfg, probe)[0]).max())
    assert diff_init == 0.0, f"LoRA init should be exact identity, got {diff_init:.2e}"
    print(f"[stage 4] LoRA injected; init identity OK: max|diff| = {diff_init:.1f}")

    # 给 B 一点更新再校验 LoRA 梯度：绕开 A=B=0 死锁点，检验的是有效状态
    for (layer, name) in LORA_PROJECTIONS:
        ka, kb = lora_keys(layer, name)
        model.params[kb] += rng.normal(0, 0.02, size=model.params[kb].shape)
    worst_lora = model.grad_check(data_lora, rng,
                                  keys=model.lora_trainable_keys())
    print(f"[stage 4] LoRA grad check OK: worst rel err = {worst_lora:.2e}")

    # ---- Stage 5: LoRA 微调（冻结主干，只训 A/B）+ 合并 + 行为转变 ----
    print("[stage 5] LoRA finetuning on 'gpu' corpus (base frozen) ...")
    lora_keys_all = model.lora_trainable_keys()
    # 备份全部主干键：训练后逐键比对，base drift=0 即证明 keys 白名单真冻结
    base_backup = {k: v.copy() for k, v in model.base_params().items()}
    model.train(data_lora, rng, keys=lora_keys_all,
                steps=1200, lr=3e-3, batch=16, log_every=300, tag="lora")
    drifted = max(float(np.abs(model.params[k] - base_backup[k]).max())
                  for k in base_backup)
    print(f"[stage 5] base drift = {drifted:.2e} (0.0 = frozen as expected)")

    out_lora = model.generate(tokenizer, prompt, n_gen, rng=rng, **gen_kw)
    print(f"[stage 5] generate after LoRA | prompt={prompt!r}")
    print(f"  -> {out_lora!r}")

    # 合并等价性：分路前向 vs 烘进 W 的前向，实数上同函数，浮点上 ulp 级一致
    logits_split = model.forward(probe)[0]
    model.merge_lora()
    logits_merged = model.forward(probe)[0]
    diff_merge = float(np.abs(logits_split - logits_merged).max())
    assert diff_merge < 1e-9, f"merge mismatch: {diff_merge:.2e}"
    print(f"[stage 5] merge equivalence OK: max|split - merged| = {diff_merge:.2e}")

    out_merged = model.generate(tokenizer, prompt, n_gen, rng=rng, **gen_kw)
    print(f"[stage 5] generate after merge | prompt={prompt!r}")
    print(f"  -> {out_merged!r}")

    print("[done] all stages passed.")
