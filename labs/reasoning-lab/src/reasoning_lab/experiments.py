"""Numerical checks and fixed-workload inference measurements."""

from __future__ import annotations

import gc
import statistics
import time
from dataclasses import asdict
from pathlib import Path

import torch

from .data import write_json
from .generation import encode_prompt, generate
from .logging import get_logger
from .model import ModelConfig, Qwen3, load_model
from .runtime import memory_snapshot, seed_all

log = get_logger("bench")


class ByteTokenizer:
    """离线冒烟用字节分词器，绝不用于预训练权重。

    vocab_size=259 = 256 个字节 + 3 个特殊位。token = byte+3，
    把 0/1/2 留给特殊符，避免真实字节与 pad/eos 撞号。
    """

    eos_token_id = 2
    pad_token_id = 0

    def encode(self, text, add_special_tokens=False):
        return [byte + 3 for byte in text.encode()]

    def decode(self, ids, skip_special_tokens=False):
        return bytes(token - 3 for token in ids if token >= 3).decode(errors="replace")

    def apply_chat_template(self, messages, **_kwargs):
        return self.encode("User: " + messages[-1]["content"] + "\nAssistant: ")


def tiny_model(device: str = "cpu", seed: int = 42) -> Qwen3:
    """几十 KB 的同构 Qwen3 模型，用来验证管线能否走通。

    参数刻意自洽：4 个查询头 x head_dim 8 = hidden 32，KV 头取一半，
    这样下面的 numerical_checks 能真正跑到 GQA 的 repeat_kv 分支。
    rank=alpha=4 使 LoRA 缩放为 1，冒烟时不引入额外变量。
    """
    seed_all(seed)
    cfg = ModelConfig(
        vocab_size=259,
        hidden_size=32,
        intermediate_size=64,
        num_hidden_layers=2,
        num_attention_heads=4,
        num_key_value_heads=2,
        head_dim=8,
    )
    return Qwen3(cfg, rank=4, alpha=4).to(device)


@torch.no_grad()
def numerical_checks(model, ids: torch.Tensor, mask: torch.Tensor, tolerance=1e-4) -> dict:
    """三组对账，全部只比有效 token 位置。

    1. 逐 token 带 cache 前向 vs 一次性全量前向：验证 KV cache 拼接
    2. eager vs sdpa：验证融合内核与手写 attention 等价
    3. 单条去 padding vs batch 里带 padding：验证 padding 不污染结果

    padding 位置的 logits 没有语义，所以只在 valid 掩码内取最大误差；
    否则一个无意义的值就能让检查假失败。
    """
    model.eval()
    original = model.attention_impl
    model.attention_impl = "eager"
    full, _ = model(ids, attention_mask=mask)
    cache, pieces = None, []
    for index in range(ids.shape[1]):
        logits, cache = model(
            ids[:, index : index + 1],
            attention_mask=mask[:, : index + 1],
            past_key_values=cache,
            use_cache=True,
        )
        pieces.append(logits)
    cached = torch.cat(pieces, 1)
    model.attention_impl = "sdpa"
    sdpa, _ = model(ids, attention_mask=mask)
    model.attention_impl = original
    valid = mask.bool().unsqueeze(-1).expand_as(full)
    cache_gap = (cached.float() - full.float()).abs()[valid].max().item()
    sdpa_gap = (sdpa.float() - full.float()).abs()[valid].max().item()
    pad_gap = 0.0
    for row in range(ids.shape[0]):
        individual, _ = model(ids[row : row + 1, mask[row].bool()])
        batched = sdpa[row, mask[row].bool()]
        pad_gap = max(pad_gap, (individual.float()[0] - batched.float()).abs().max().item())
    return {
        "cached_full_max_abs": cache_gap,
        "eager_sdpa_max_abs": sdpa_gap,
        "single_padded_max_abs": pad_gap,
        "tolerance": tolerance,
        "passed": max(cache_gap, sdpa_gap, pad_gap) < tolerance,
    }


def hf_reference(model_path: Path, output: Path) -> None:
    """独立进程入口：存完参考 logits 就退出，不与自写模型共存。

    输入故意带一行左 padding（[0,0,21,22]），后面的 position_ids 用 cumsum-1
    并对 0 位置 clamp，覆盖“左 padding 下位置要连续”这个易错点。
    """
    from transformers import AutoModelForCausalLM

    seed_all(42)
    ids = torch.tensor([[10, 11, 12, 13], [0, 0, 21, 22]])
    mask = torch.tensor([[1, 1, 1, 1], [0, 0, 1, 1]])
    position_ids = (mask.cumsum(-1) - 1).clamp_min(0)
    hf = AutoModelForCausalLM.from_pretrained(
        model_path, dtype=torch.float32, attn_implementation="eager"
    ).eval()
    with torch.no_grad():
        logits = hf(input_ids=ids, attention_mask=mask, position_ids=position_ids).logits
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"input_ids": ids, "mask": mask, "logits": logits}, output)


def parity(model_path: Path, reference_path: Path, output: Path, device: str) -> dict:
    """自写实现与 HF 的逐位置对账。

    FP32 下两者的累加顺序不同，结果不会逐位相等，所以外部容差取 1e-3
    （比 numerical_checks 的 1e-4 宽），同时要求三组内部对账全过。
    """
    reference = torch.load(reference_path, weights_only=True)
    model, info = load_model(model_path, device, torch.float32)
    model.eval()
    model.attention_impl = "eager"
    ids, mask = reference["input_ids"].to(device), reference["mask"].to(device)
    with torch.no_grad():
        logits, _ = model(ids, attention_mask=mask)
    valid = mask.cpu().bool().unsqueeze(-1).expand_as(reference["logits"])
    error = (logits.cpu().float() - reference["logits"]).abs()[valid]
    report = numerical_checks(model, ids, mask, tolerance=1e-3)
    report.update(
        hf_max_abs=error.max().item(),
        hf_mean_abs=error.mean().item(),
        model=info,
        reference_dtype="float32",
        device=device,
    )
    report["passed"] = report["passed"] and report["hf_max_abs"] < 1e-3
    write_json(output, report)
    return report


def benchmark(model, tokenizer, tasks, cfg, run, monitor) -> dict:
    """固定工作量的吞吐测试：三档对比 eager 无 cache / eager 有 cache / sdpa 有 cache。

    - 固定 max_new_tokens 并忽略 EOS：这是系统测试而非质量测试，
      每次生成长度相同，tokens/s 才有可比性
    - 每种配置先跑一次短预热，排除首轮编译与内存分配开销
    - TTFT 是首 token 时间（prefill 成本），ITL 是相邻 token 间隔中位数（decode 成本）
    """
    prompt = encode_prompt(tokenizer, tasks[0]["prompt"])
    if len(prompt) + cfg.max_new_tokens > cfg.max_length:
        raise ValueError("Benchmark prompt exceeds token budget")
    rows = []
    original = model.attention_impl
    deadline = time.monotonic() + cfg.max_seconds
    for attention, use_cache in [("eager", False), ("eager", True), ("sdpa", True)]:
        model.attention_impl = attention
        generate(model, prompt, 2, 0, None, use_cache)
        for repeat in range(3):
            if time.monotonic() >= deadline:
                break
            metrics = {}
            # Ignore EOS for fixed work. This is a systems benchmark, not a quality score.
            with monitor.phase("generate", metrics):
                sample = generate(model, prompt, cfg.max_new_tokens, 0, None, use_cache)
            intervals = [b - a for a, b in zip(sample.token_seconds, sample.token_seconds[1:])]
            row = {
                "attention": attention,
                "use_cache": use_cache,
                "repeat": repeat,
                "prompt_tokens": len(prompt),
                "generated_tokens": len(sample.token_ids),
                "output_tokens_per_second": len(sample.token_ids) / metrics["generate_seconds"],
                "ttft_seconds": sample.token_seconds[0],
                "itl_median_seconds": statistics.median(intervals) if intervals else None,
                "token_ids": sample.token_ids,
                **metrics,
                "memory": memory_snapshot(run.device),
            }
            rows.append(row)
            run.log("metrics", row)
            log.info(
                "%s cache=%s repeat=%d %.1f tokens/s ttft=%.3fs",
                attention,
                use_cache,
                repeat,
                row["output_tokens_per_second"],
                row["ttft_seconds"],
            )
    model.attention_impl = original
    report = {
        "runs": rows,
        "fixed_length": True,
        "includes_loading": False,
        "synchronized_stage_wall_time": True,
        "observed_memory_high_water": monitor.high_water,
    }
    write_json(run.path / "benchmark.json", report)
    return report


def smoke(output: Path, device: str) -> dict:
    """离线冒烟：随机小模型 + 8 道题，SFT 3 步、GRPO 2 步，验证整条管线。

    它证明代码路径跑通、数值不炸，不证明预训练模型的任务质量；
    summary 里把这条 limitation 写死，避免被当成实验结论引用。
    """
    from .config import Config
    from .data import generate_dataset, load_dataset
    from .runs import Run
    from .runtime import Monitor
    from .tasks import digest
    from .training import train

    output.mkdir(parents=True, exist_ok=False)
    manifest = generate_dataset(
        output / "data", "countdown", 42, {"train": 8, "dev": 2, "test": 2, "ood": 2}
    )
    model = tiny_model(device)
    model_id = {"hash": digest([asdict(model.config), 42]), "random_tiny_model": True}
    checks = numerical_checks(
        model,
        torch.tensor([[5, 6, 7], [0, 8, 9]], device=device),
        torch.tensor([[1, 1, 1], [0, 1, 1]], device=device),
    )
    if not checks["passed"]:
        raise RuntimeError(f"Tiny-model numerical checks failed: {checks}")
    reports = {}
    for stage, steps, lr in [("sft", 3, 1e-3), ("grpo", 2, 1e-4)]:
        cfg = Config(
            stage=stage,
            output=str(output / "runs"),
            steps=steps,
            device=device,
            max_length=512,
            max_new_tokens=8,
            samples=1,
            eval_every=steps,
            save_every=steps,
            rank=4,
            alpha=4,
            max_seconds=180,
            learning_rate=lr,
        )
        run = Run(cfg, device, model_id, manifest)
        run.announce()
        with Monitor(run.path / "system.jsonl", device) as monitor:
            reports[stage] = train(
                model,
                ByteTokenizer(),
                load_dataset(output / "data", "train"),
                load_dataset(output / "data", "dev"),
                cfg,
                run,
                monitor,
                time.monotonic(),
            )
    report = {
        "passed": True,
        "numerical_checks": checks,
        "stages": reports,
        "limitation": "Random tiny model: validates plumbing, not pretrained task quality.",
    }
    write_json(output / "summary.json", report)
    del model
    gc.collect()
    return report
