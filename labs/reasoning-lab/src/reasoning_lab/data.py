"""Immutable dataset snapshots with semantic split disjointness.

数据集只生成一次、写盘、之后只读。理由是可复现：训练、评测、比较都引用同一份 jsonl，
不能“今天重跑一次数据生成”就把昨天实验的题换掉。

两个不变量：
    语义去重   以 task_id（题目内容的哈希）去重，而不是比文本；同一道题不会同时出现在 train 与 dev
    内容校验   manifest 存每个 split 的行数与哈希，加载时复核；手改任何一行 jsonl 都会失败
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from .tasks import RULE_VERSION, digest, make_task


def write_json(path: Path, value: object) -> None:
    # ensure_ascii=False 让中文保持可读；allow_nan=False 是故意的：
    # NaN/Infinity 不是合法 JSON，宁可在写入时报错，也不要产出别的语言读不了的文件
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n" for row in records)
    )


def generate_dataset(
    output: Path, task: str, seed: int, counts: dict[str, int], difficulty: str = "L2"
) -> dict:
    """生成四个 split（train/dev/test/ood）加一个 dev-quick 子集。

    counts 由调用方给出，例如 {"train": 1000, "dev": 200, "test": 400, "ood": 200}。
    返回的 manifest 会被写进 manifest.json，并在训练与评测时被再次校验。
    """
    # 目录已存在就拒绝：快照不可变，覆盖会让旧实验的题集无法恢复
    if output.exists():
        raise FileExistsError(f"Dataset snapshots are immutable; choose a new path: {output}")
    if any(n < 1 for n in counts.values()):
        raise ValueError("Every split needs at least one question")
    rng = random.Random(seed)
    seen, splits = set(), {}
    for split, count in counts.items():
        rows = []
        # 尝试次数设上限而不是 while True：题目空间太小的时候要显式失败，
        # 否则脚本会在这里无限转圈
        for attempt in range(max(10000, count * 500)):
            if len(rows) == count:
                break
            # L2 is the first curriculum. L1's finite space must not be inflated.
            level = (
                "L1"
                if task == "countdown" and difficulty == "L2" and len(rows) < count // 10
                else difficulty
            )
            item = make_task(task, rng, level, ood=split == "ood")
            # task_id 是题目内容的哈希：同一道题（即使换个顺序生成）也不会重复入集，
            # 而且跨 split 共用一个 seen 集合，保证 train 与 dev 不重叠
            if item["task_id"] in seen:
                continue
            seen.add(item["task_id"])
            rows.append(item)
        if len(rows) != count:
            raise ValueError(
                f"Insufficient distinct {task} questions for {split}: {len(rows)}/{count}"
            )
        splits[split] = rows
    output.mkdir(parents=True)
    manifest = {
        "schema": 1,
        "task": task,
        "seed": seed,
        "rule_version": RULE_VERSION,
        "curriculum": difficulty,
        "splits": {
            name: {"count": len(rows), "hash": digest(rows)} for name, rows in splits.items()
        },
    }
    for name, rows in splits.items():
        write_jsonl(output / f"{name}.jsonl", rows)
    # dev-quick 就是 dev 的前 50 题，单独落一份只是为了让选择集有稳定名字；
    # 它不参与 hash 校验的独立性，仍然是 dev 的子集
    write_jsonl(output / "dev-quick.jsonl", splits["dev"][:50])
    manifest["splits"]["dev-quick"] = {
        "count": len(splits["dev"][:50]),
        "hash": digest(splits["dev"][:50]),
    }
    write_json(output / "manifest.json", manifest)
    return manifest


def load_dataset(path: Path, split: str) -> list[dict]:
    """读一个 split，并复核它没有被改过。

    两道校验缺一不可：
        rule_version  判卷规则变了，旧数据的 answer 与标签可能不再成立
        hash          行数或内容变了一点，之前的评测结果就不能再拿来做比较
    """
    manifest = json.loads((path / "manifest.json").read_text())
    if manifest["rule_version"] != RULE_VERSION:
        raise ValueError("Verifier/data rule version mismatch")
    rows = read_jsonl(path / f"{split}.jsonl")
    expected = manifest["splits"][split]
    if len(rows) != expected["count"] or digest(rows) != expected["hash"]:
        raise ValueError(f"Dataset checksum mismatch: {split}")
    return rows
