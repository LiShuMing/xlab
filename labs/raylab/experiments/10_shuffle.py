"""Ray Data 的五条 shuffle 路径：算子名、分区数、task 粒度与倾斜在数据上长什么样。"""
import re

import numpy as np
import ray
import ray.data
from ray.data._internal.util import explain_plan

from common import RUN_DIR, run, session

STATS_LINE = re.compile(
    r"^Operator (\d+) (.+?): "
    r"(?:(?P<tasks>\d+) tasks executed, (?P<blocks>\d+) blocks produced |executed )"
    r"in (?P<seconds>[\d.]+)s$"
)
OP_LINE = re.compile(r"^([A-Z]\w*)\[(.*)\]$")


def parse_plans(text):
    sections, current = {}, None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--------") and stripped.endswith("--------"):
            current = stripped.strip("- ").strip()
            sections[current] = []
        elif current and stripped:
            sections[current].append(re.sub(r"^\+- ", "", stripped))
    return sections


def optimized_plan_lines(ds):
    plans = parse_plans(explain_plan(ds._logical_plan))
    return plans["Physical Plan (Optimized)"], plans


def operator_types(lines):
    return [match.group(1) for line in lines if (match := OP_LINE.match(line))]


def operator_names(lines):
    """算子类型 + 括号内的参数，便于看清 num_partitions 从哪来。"""
    return [line for line in lines if OP_LINE.match(line)]


def parse_stats(text):
    rows = []
    for line in text.splitlines():
        match = STATS_LINE.match(line.strip())
        if match:
            rows.append({
                "operator": match.group(2),
                "tasks": int(match.group("tasks")) if match.group("tasks") else None,
                "seconds": float(match.group("seconds")),
            })
    return rows


def with_group(ds):
    """给每行加一列 group，避开 add_column 在 arrow-backed pandas 上的取模限制。"""
    return ds.map_batches(
        lambda batch: {"id": batch["id"], "group": batch["id"] % 8},
        batch_size=32, batch_format="numpy",
    )


def block_row_counts(ds):
    """一块一行：把每个 block 的行数变成一行输出，用来量分区大小。"""
    counts = ds.map_batches(
        lambda batch: {"rows": np.array([len(batch["id"])], dtype=np.int64)},
        batch_size=None, batch_format="numpy",
    ).take_all()
    return [int(row["rows"]) for row in counts]


def section_shuffle_paths():
    """五条路径分别落到哪个物理算子。"""
    cases = {
        "repartition_by_key": lambda: with_group(
            ray.data.range(128, override_num_blocks=8)
        ).repartition(4, keys=["group"]),
        "repartition_no_key": lambda: ray.data.range(
            128, override_num_blocks=8
        ).repartition(4),
        "groupby_count": lambda: with_group(
            ray.data.range(128, override_num_blocks=8)
        ).groupby("group").count(),
        "sort": lambda: ray.data.range(128, override_num_blocks=8).sort("id"),
        "random_shuffle": lambda: ray.data.range(
            128, override_num_blocks=8
        ).random_shuffle(),
    }
    report = {}
    for label, build in cases.items():
        ds = build()
        lines, _ = optimized_plan_lines(ds)
        names = operator_names(lines)
        materialized = ds.materialize()
        stats = materialized.stats()
        (RUN_DIR / f"plan_{label}.txt").write_text(
            explain_plan(build()._logical_plan) + "\n" + stats
        )
        report[label] = {
            "operators": names,
            "operator_types": operator_types(lines),
            "elapsed_s": max(
                (row["seconds"] for row in parse_stats(stats)), default=None
            ),
            "output_blocks": materialized.num_blocks(),
        }

    # 按 key 的重分区、groupby 走 hash 家族；无 key 重分区、sort、随机打散走 AllToAll。
    assert any(
        "HashShuffleOperator" in name
        for name in report["repartition_by_key"]["operator_types"]
    ), report["repartition_by_key"]
    assert any(
        "HashAggregateOperator" in name
        for name in report["groupby_count"]["operator_types"]
    ), report["groupby_count"]
    for label in ("repartition_no_key", "sort", "random_shuffle"):
        assert any(
            "AllToAllOperator" in name
            for name in report[label]["operator_types"]
        ), (label, report[label])
    # 按 key 重分区的分区数写在算子名里，可直接读出。
    assert "num_partitions=4" in report["repartition_by_key"]["operators"][0], (
        report["repartition_by_key"]["operators"]
    )
    return report


def section_partition_arity():
    """分区数由 num_partitions 决定，与输入块数无关 —— 这是 stage 边界的语义。"""
    report = {}
    for num_blocks, partitions in ((8, 3), (16, 3), (16, 2)):
        ds = with_group(
            ray.data.range(256, override_num_blocks=num_blocks)
        ).repartition(partitions, keys=["group"])
        lines, _ = optimized_plan_lines(ds)
        materialized = ds.materialize()
        stats = materialized.stats()
        (RUN_DIR / f"stats_arity_{num_blocks}_{partitions}.txt").write_text(stats)
        rows = {row["operator"]: row for row in parse_stats(stats)}
        read = next(v for k, v in rows.items() if k.startswith("ReadRange"))
        report[f"blocks_{num_blocks}_partitions_{partitions}"] = {
            "read_tasks": read["tasks"],
            "output_blocks": materialized.num_blocks(),
            "count": materialized.count(),
        }
        assert read["tasks"] == num_blocks, (read, num_blocks)
        # 上游 task 数变了，输出块数却只由 num_partitions 封顶：空分区不产出数据块，
        # 所以是“≤”。这是 shuffle 作为 stage 边界的核心语义。
        assert 1 <= materialized.num_blocks() <= partitions, (
            materialized.num_blocks(), partitions
        )
        assert materialized.count() == 256
    return report


def section_skew():
    """热 key 在 hash 分区下只能变成一个热分区，加分区数也拆不开。"""
    total, hot = 512, 480

    def build(partitions):
        def add_group(batch):
            ids = batch["id"]
            # id < hot 的行全部落到 group 0，其余行均分到 group 1..3。
            group = np.where(ids < hot, 0, 1 + (ids % 3))
            return {"id": ids, "group": group}

        return ray.data.range(total, override_num_blocks=8).map_batches(
            add_group, batch_size=64, batch_format="numpy",
        ).repartition(partitions, keys=["group"])

    report = {}
    for partitions in (4, 8):
        ds = build(partitions)
        materialized = ds.materialize()
        (RUN_DIR / f"stats_skew_{partitions}.txt").write_text(materialized.stats())
        sizes = sorted(block_row_counts(materialized), reverse=True)
        assert sum(sizes) == total, (sum(sizes), total)
        # 空分区不产出数据块，所以非空块数只会小于等于分区数。
        assert 1 <= len(sizes) <= partitions, (len(sizes), partitions)
        report[f"partitions_{partitions}"] = {
            "block_rows_desc": sizes,
            "max_share": round(sizes[0] / total, 3),
        }
        # 同一个 key 只能落到一个分区，所以 480 行热键必然堆在同一个块里。
        # 这条与分区数无关，是 hash shuffle 无法自动治倾斜的直接证据。
        assert sizes[0] >= hot, (sizes, hot)
    return report


def section_hash_vs_all_to_all_cost():
    """同样的重分区，按 key 走 hash 家族要额外起聚合器 Actor。"""
    report = {}
    for label, ds in (
        ("hash_by_key", with_group(ray.data.range(64, override_num_blocks=8))
         .repartition(4, keys=["group"])),
        ("all_to_all_no_key", ray.data.range(64, override_num_blocks=8)
         .repartition(4)),
        ("sort", ray.data.range(64, override_num_blocks=8).sort("id")),
    ):
        lines, _ = optimized_plan_lines(ds)
        materialized = ds.materialize()
        stats = materialized.stats()
        (RUN_DIR / f"stats_cost_{label}.txt").write_text(stats)
        rows = parse_stats(stats)
        shuffle_row = rows[-1] if rows else None
        report[label] = {
            "operators": operator_names(lines),
            "shuffle_seconds": shuffle_row["seconds"] if shuffle_row else None,
            "output_blocks": materialized.num_blocks(),
        }
    # 只报告耗时不加断言：小数据下耗时几乎全由 Actor 启动构成，机器不同会漂移。
    return report


def experiment():
    with session():
        paths = section_shuffle_paths()
        arity = section_partition_arity()
        skew = section_skew()
        cost = section_hash_vs_all_to_all_cost()
        import json
        print(json.dumps({
            "paths": paths, "arity": arity, "skew": skew, "cost": cost,
        }, ensure_ascii=False, indent=2), flush=True)
        return {
            "scope": (
                "真实 CPU Ray Data shuffle 计划与执行；单机 4 CPU、内存数据源、64~512 行。"
                "不测跨节点网络搬运，也不与真实 SQL 引擎的 shuffle 做基准对比。"
            ),
            "hash_paths": {
                "by_key": paths["repartition_by_key"]["operators"],
                "groupby": paths["groupby_count"]["operators"],
            },
            "all_to_all_paths": {
                label: paths[label]["operators"]
                for label in ("repartition_no_key", "sort", "random_shuffle")
            },
            "partition_arity": arity,
            "skew_max_share": {
                key: value["max_share"] for key, value in skew.items()
            },
            "shuffle_seconds_tiny_data": {
                key: value["shuffle_seconds"] for key, value in cost.items()
            },
            "artifacts": str(RUN_DIR),
            "note": (
                "小数据下 hash shuffle 的秒数主要是聚合器 Actor 启动开销，不能当作 shuffle 吞吐指标；"
                "倾斜结论依赖 group 列是分组键，若分组键是 id 本身则不会倾斜。"
                "分区数与输入块数解耦这一点，是本实验唯一带断言的 stage 边界证据。"
            ),
        }


if __name__ == "__main__":
    run(experiment)
