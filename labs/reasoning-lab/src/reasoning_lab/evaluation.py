"""Fixed-seed task evaluation, clustered paired comparisons, and cost accounting.

评测与比较是两件不同的事，这里各占一半：

    evaluate  在固定 seed 下让模型做一遍题，把每个样本的判定写成 responses.jsonl
    compare   两份评测结果做配对比较，输出 delta、95% 区间和 accept/reject

评测只回答“这次跑了多少分”，compare 才回答“这次改动是否真的变好”。
单看前者会被题目难度和环境噪声干扰，所以接受与否只看后者。
"""

from __future__ import annotations

import json
import random
import time
from collections import Counter, defaultdict
from pathlib import Path

from .data import read_jsonl, write_json, write_jsonl
from .generation import answer_text, encode_prompt, generate
from .logging import get_logger
from .runtime import seed_all, synchronize
from .tasks import digest, verify

log = get_logger("eval")


def summarize(records: list[dict], expected: int) -> dict:
    """把逐样本记录聚合成一份报告。

    两个主指标容易混：
        single_success_rate  pass@1，正确样本数 / 总样本数（题库数 x 每题候选数）
        any_success_rate    pass@k，至少有一个候选正确的“题数” / 题数
    前者量能力，后者量“多试几次能不能对”，后者不被训练直接优化。
    """
    grouped = defaultdict(list)
    for row in records:
        grouped[row["task_id"]].append(row)
    correct = sum(row["correct"] for row in records)
    layers = defaultdict(list)
    for row in records:
        layers[row["difficulty"]].append(row)
    return {
        "complete": len(records) == expected,
        "expected_samples": expected,
        "samples": len(records),
        "questions": len(grouped),
        "single_success_rate": correct / len(records) if records else None,
        "any_success_rate": sum(any(r["correct"] for r in rows) for rows in grouped.values())
        / len(grouped)
        if grouped
        else None,
        "failure_reasons": dict(Counter(row["reason"] for row in records if not row["correct"])),
        "truncated_samples": sum(row["finish_reason"] == "max_tokens" for row in records),
        "prompt_tokens": sum(row["prompt_tokens"] for row in records),
        "generated_tokens": sum(row["generated_tokens"] for row in records),
        "seconds": sum(row["seconds"] for row in records),
        "by_difficulty": {
            key: {"samples": len(rows), "success_rate": sum(r["correct"] for r in rows) / len(rows)}
            for key, rows in layers.items()
        },
    }


def evaluate(
    model,
    tokenizer,
    tasks: list[dict],
    cfg,
    directory: Path,
    deadline: float | None = None,
    samples: int | None = None,
) -> dict:
    from .runs import restore_rng, rng_state

    directory.mkdir(parents=True, exist_ok=False)
    device = str(next(model.parameters()).device)
    # 评测前拍一份 RNG 快照，结束后恢复：采样会消耗随机数，
    # 不恢复的话“评测”会改变训练中后续 step 的随机序列
    before_rng = rng_state(device)
    records = []
    sample_count = samples or cfg.samples
    # About ten progress lines keep a long evaluation observable; short checks stay quiet.
    progress_every = len(tasks) // 10
    log.info(
        "evaluating %d questions x %d candidates into %s",
        len(tasks),
        sample_count,
        directory,
    )
    try:
        for index, task in enumerate(tasks, start=1):
            prompt = encode_prompt(tokenizer, task["prompt"])
            # 题太长就直接报错，而不是跳过：跳过会让分母变化，成功率失去定义
            if len(prompt) + cfg.max_new_tokens > cfg.max_length:
                raise ValueError(f"Evaluation question exceeds token budget: {task['task_id']}")
            for candidate in range(sample_count):
                if deadline is not None and time.monotonic() >= deadline:
                    break
                # seed 只由“哪道题 + 第几个候选”决定，与模型无关：
                # 同一题同一候选换模型时，输出差异只来自权重。
                # candidate 乘一个大素数，避免不同候选抽到同一串随机数
                seed = (int(task["task_id"][:8], 16) + cfg.seed + candidate * 1000003) % 2**31
                seed_all(seed)
                # 计时前先同步：GPU/MPS 是异步的，不同步会把“排队时间”漏掉
                synchronize(device)
                started = time.perf_counter()
                sample = generate(
                    model, prompt, cfg.max_new_tokens, cfg.temperature, tokenizer.eos_token_id
                )
                synchronize(device)
                seconds = time.perf_counter() - started
                text = answer_text(tokenizer, sample.token_ids)
                verdict = verify(task, text)
                records.append(
                    {
                        "task_id": task["task_id"],
                        "task": task["task"],
                        "difficulty": task["difficulty"],
                        "prompt": task["prompt"],
                        "output": text,
                        "token_ids": sample.token_ids,
                        "seed": seed,
                        "candidate": candidate,
                        "seconds": seconds,
                        "prompt_tokens": len(prompt),
                        "generated_tokens": len(sample.token_ids),
                        "finish_reason": sample.finish_reason,
                        **verdict.to_dict(),
                    }
                )
            # 每 10% 题打一行进度：长评测能看到进展，短检查（少于 10 题）保持安静
            if progress_every and index % progress_every == 0:
                log.info(
                    "progress %d/%d questions, %d/%d samples correct",
                    index,
                    len(tasks),
                    sum(row["correct"] for row in records),
                    len(records),
                )
            if deadline is not None and time.monotonic() >= deadline:
                log.warning("deadline reached after %d/%d questions", index, len(tasks))
                break
    finally:
        restore_rng(before_rng, device)
        write_jsonl(directory / "responses.jsonl", records)
    report = summarize(records, len(tasks) * sample_count)
    report["protocol"] = {
        "backend": "pytorch",
        "dtype": cfg.dtype,
        "temperature": cfg.temperature,
        "max_new_tokens": cfg.max_new_tokens,
        "max_length": cfg.max_length,
        "samples_per_question": sample_count,
        "thinking": False,
        "top_p": 1.0,
        "seed": cfg.seed,
        # task_hash 把整个题集打成指纹：改题、改顺序、改 --limit 都会变，
        # 于是 compare 会拒绝拿不同题集的两份结果做比较
        "task_hash": digest(tasks),
        "rule_version": "1",
        "split": cfg.split,
    }
    write_json(directory / "summary.json", report)
    log.info(
        "evaluation %s complete=%s single=%s any=%s truncated=%d failures=%s",
        directory,
        report["complete"],
        report["single_success_rate"],
        report["any_success_rate"],
        report["truncated_samples"],
        report["failure_reasons"],
    )
    print(json.dumps({"evaluation": str(directory), **report}, ensure_ascii=False), flush=True)
    return report


def compare(left: Path, right: Path, output: Path, repeats: int = 2000) -> dict:
    """配对比较：同一题、同一候选 seed 上算左右两边的差值，再做 bootstrap。

    为什么必须配对：题目难度差异远大于训练带来的改进（难题两遍都错、易题两遍都对）。
    直接比两个总成功率，等于把题目难度当成噪声；配对后只看“同一题是否翻转”，
    难度项被消掉，同样的题量能得到更窄的区间。

    代价是两份结果必须同协议：题集、采样参数、dtype 全部一致，否则拒绝比较。
    """
    a = json.loads((left / "summary.json").read_text())
    b = json.loads((right / "summary.json").read_text())
    if not all({"backend", "dtype"} <= report.get("protocol", {}).keys() for report in [a, b]):
        raise ValueError("Legacy evaluation lacks backend/precision identity; rerun it")
    if not a["complete"] or not b["complete"] or a["protocol"] != b["protocol"]:
        raise ValueError("Compare requires complete evaluations with identical protocols")
    groups = []
    for path in [left, right]:
        grouped = defaultdict(dict)
        for row in read_jsonl(path / "responses.jsonl"):
            # 对齐键用 (candidate, seed) 而不是行号：行号在不同 run 里没意义，
            # seed 才是“这里是同一道题的第几次采样”的真正身份
            key = (row["candidate"], row["seed"])
            if key in grouped[row["task_id"]]:
                raise ValueError("Duplicate question/candidate")
            grouped[row["task_id"]][key] = int(row["correct"])
        groups.append(grouped)
    if groups[0].keys() != groups[1].keys():
        raise ValueError("Question sets differ")
    differences = []
    for key, old in groups[0].items():
        new = groups[1][key]
        if old.keys() != new.keys():
            raise ValueError("Candidate seeds differ")
        # 先在一道题内部对候选求平均，再拿题与题做统计：
        # 同一题的 4 个候选高度相关，当成 4 个独立样本会把区间压得过窄
        differences.append(sum(new[k] - old[k] for k in old) / len(old))
    if not differences:
        raise ValueError("No paired questions")
    rng = random.Random(0)
    # bootstrap：对“题目”做有放回重采样，每次算一个平均差，得到经验分布后取 2.5/97.5 分位
    bootstrap = sorted(
        sum(rng.choices(differences, k=len(differences))) / len(differences) for _ in range(repeats)
    )
    delta = sum(differences) / len(differences)
    lower, upper = bootstrap[int(repeats * 0.025)], bootstrap[int(repeats * 0.975)]
    # 三态判据：既要区间下界大于 0（方向确定），又要 delta 达到事先声明的 3 个点，
    # 防止“统计上显著但幅度不值钱”的改动被判为收益
    decision = (
        "accept"
        if delta >= 0.03 and lower > 0
        else ("reject" if upper < 0 else "insufficient_evidence")
    )
    report = {
        "questions": len(differences),
        "delta": delta,
        "paired_95_ci": [lower, upper],
        "bootstrap_repeats": repeats,
        "decision": decision,
        "left_seconds": a["seconds"],
        "right_seconds": b["seconds"],
        "left_generated_tokens": a["generated_tokens"],
        "right_generated_tokens": b["generated_tokens"],
        # 诚实标注边界：dev 既是训练时的选模集，也是这里的比较集，
        # 所以这是“同一种子下的选模证据”，不等于独立复现
        "limitation": "Dev selection evidence, not an independent training-seed replication.",
    }
    write_json(output, report)
    log.info(
        "compare questions=%d delta=%+.4f ci=[%+.4f, %+.4f] decision=%s",
        report["questions"],
        delta,
        lower,
        upper,
        decision,
    )
    return report
