"""Ray 把一串 UDF 变成算子图：读四段计划、找融合边界、量算子级并行度与流水线重叠。"""
import re
import time

import numpy as np
import ray
import ray.data
from ray.data._internal.util import explain_plan

from common import RUN_DIR, run, session

# 两种 stats 行格式：
#   Operator 1 ReadRange: 8 tasks executed, 8 blocks produced in 0.94s
#   Operator 2 Shuffle(key_columns=('id',)): executed in 4.1s
STATS_LINE = re.compile(
    r"^Operator (\d+) (.+?): "
    r"(?:(?P<tasks>\d+) tasks executed, (?P<blocks>\d+) blocks produced |executed )"
    r"in (?P<seconds>[\d.]+)s$"
)
OP_LINE = re.compile(r"^([A-Z]\w*)\[(.*)\]$")


def parse_plans(text):
    """把 explain_plan 的输出切成四段，每段返回去掉树形前缀的行。"""
    sections, current = {}, None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--------") and stripped.endswith("--------"):
            current = stripped.strip("- ").strip()
            sections[current] = []
        elif current and stripped:
            sections[current].append(re.sub(r"^\+- ", "", stripped))
    return sections


def operator_types(section):
    """抽取某一段里的物理算子类型（保持自顶向下顺序）。"""
    names = []
    for line in section:
        match = OP_LINE.match(line)
        if match:
            names.append(match.group(1))
    return names


def parse_stats(text):
    """解析每个算子的 task 数、block 数与耗时。"""
    rows = []
    for line in text.splitlines():
        match = STATS_LINE.match(line.strip())
        if match:
            rows.append({
                "operator": match.group(2),
                "tasks": int(match.group("tasks")) if match.group("tasks") else None,
                "blocks": int(match.group("blocks")) if match.group("blocks") else None,
                "seconds": float(match.group("seconds")),
            })
    return rows


def section_four_stage_plan():
    """一个 filter + map 的链，在四段计划里分别长什么样。"""
    ds = ray.data.range(256, override_num_blocks=8).filter(
        lambda row: row["id"] % 2 == 0
    ).map(lambda row: {"id": row["id"] * 3, "parity": "even"})

    text = explain_plan(ds._logical_plan)
    (RUN_DIR / "plans_four_stage.txt").write_text(text)
    plans = parse_plans(text)
    assert set(plans) == {
        "Logical Plan", "Logical Plan (Optimized)",
        "Physical Plan", "Physical Plan (Optimized)",
    }, sorted(plans)

    logical = operator_types(plans["Logical Plan"])
    physical = operator_types(plans["Physical Plan"])
    optimized = operator_types(plans["Physical Plan (Optimized)"])

    materialized = ds.materialize()
    (RUN_DIR / "stats_four_stage.txt").write_text(materialized.stats())

    # 逻辑层 3 个算子（读 / 过滤 / 投影），未优化的物理层也是 3 个 map 算子。
    assert len(logical) == 3 and len(physical) == 4, (logical, physical)
    # 优化后 3 个 map 被融合成 1 个：融合写在物理计划里，不是运行期内联。
    assert len(optimized) == 2, optimized
    fused_name = [
        line for line in plans["Physical Plan (Optimized)"]
        if OP_LINE.match(line) and line.startswith("TaskPoolMapOperator")
    ][0]
    assert fused_name.count("->") == 2, fused_name
    return {
        "logical_ops": logical,
        "physical_ops": physical,
        "optimized_ops": optimized,
        "fused_operator": fused_name,
        "rows_out": materialized.count(),
    }


def section_fusion_boundary():
    """中间插一个按 key 的重分区，融合必须在此断开。"""
    ds = ray.data.range(256, override_num_blocks=8).map(
        lambda row: {"id": row["id"], "group": row["id"] % 4}
    ).repartition(4, keys=["group"]).map(
        lambda row: {"id": row["id"], "bucket": row["id"] % 2}
    )
    text = explain_plan(ds._logical_plan)
    (RUN_DIR / "plans_fusion_boundary.txt").write_text(text)
    plans = parse_plans(text)
    optimized = operator_types(plans["Physical Plan (Optimized)"])
    # 融合后应保留 3 个算子：融合的 map 组 -> HashShuffle -> 下游 map
    assert len(optimized) == 4, optimized
    assert "HashShuffleOperator" in optimized, optimized
    # shuffle 必须是中间那个，前后各有一个 map 算子组
    shuffle_index = optimized.index("HashShuffleOperator")
    assert 0 < shuffle_index < len(optimized) - 1, optimized
    materialized = ds.materialize()
    (RUN_DIR / "stats_fusion_boundary.txt").write_text(materialized.stats())
    optimized_lines = plans["Physical Plan (Optimized)"]
    shuffle_line = next(
        line for line in optimized_lines if line.startswith("HashShuffleOperator")
    )
    return {
        "optimized_ops": optimized,
        "shuffle_operator": shuffle_line,
        "blocks_after_shuffle": materialized.num_blocks(),
    }


def section_operator_level_parallelism():
    """并行度是算子级的：重分区后下游 task 数跟着分区数变，不跟上游块数走。"""
    observations = {}
    for num_blocks, partitions in ((8, 2), (8, 4)):
        ds = ray.data.range(256, override_num_blocks=num_blocks).repartition(
            partitions
        ).map_batches(lambda batch: {"id": batch["id"] + 1}, batch_size=None)
        materialized = ds.materialize()
        stats = materialized.stats()
        (RUN_DIR / f"stats_parallelism_{num_blocks}_{partitions}.txt").write_text(stats)
        rows = {row["operator"]: row for row in parse_stats(stats)}
        read = next(v for k, v in rows.items() if k.startswith("ReadRange"))
        downstream = next(
            v for k, v in rows.items() if k.startswith("MapBatches")
        )
        assert read["tasks"] == num_blocks, (read, num_blocks)
        assert downstream["tasks"] == partitions, (downstream, partitions)
        observations[f"blocks_{num_blocks}_partitions_{partitions}"] = {
            "read_tasks": read["tasks"], "downstream_tasks": downstream["tasks"],
        }
    return observations


def section_taskpool_vs_actorpool():
    """同一个 UDF，写成函数还是类，决定物理算子和状态语义。"""
    import os

    class Stateful:
        def __init__(self):
            self.calls = 0

        def __call__(self, batch):
            self.calls += 1
            n = len(batch["id"])
            return {
                "id": batch["id"],
                "pid": np.full(n, os.getpid()),
                "counter": np.full(n, self.calls),
            }

    def stateless(batch):
        """函数没有实例状态，每次调用看到的计数永远是 1。"""
        n = len(batch["id"])
        return {
            "id": batch["id"],
            "pid": np.full(n, os.getpid()),
            "counter": np.ones(n, dtype=int),
        }

    results = {}
    for label, udf, compute in (
        ("task_pool", stateless, ray.data.TaskPoolStrategy()),
        ("actor_pool", Stateful, ray.data.ActorPoolStrategy(size=2)),
    ):
        ds = ray.data.range(256, override_num_blocks=4).map_batches(
            udf, batch_size=8, batch_format="numpy", num_cpus=1,
            udf_modifying_row_count=False, compute=compute,
        )
        # 必须先取计划：materialize() 之后逻辑计划会塌缩成 InputData。
        plans = parse_plans(explain_plan(ds._logical_plan))
        types = operator_types(plans["Physical Plan (Optimized)"])
        materialized = ds.materialize()
        stats = materialized.stats()
        (RUN_DIR / f"stats_{label}.txt").write_text(stats)

        rows = materialized.take_all()
        per_pid = {}
        for row in rows:
            per_pid[row["pid"]] = per_pid.get(row["pid"], 0) + 1
        results[label] = {
            "operator_types": types,
            "processes": len(per_pid),
            # 行数 / batch_size = 该进程承接的批次数。
            "max_batches_per_process": max(per_pid.values()) // 8,
            "max_counter": max(row["counter"] for row in rows),
        }

    # 函数走 TaskPool，类走 ActorPool —— 这是 MapOperator.create 的分流结果。
    assert any("TaskPoolMapOperator" in t for t in results["task_pool"]["operator_types"])
    assert any(
        "ActorPoolMapOperator" in t for t in results["actor_pool"]["operator_types"]
    )
    # TaskPool：进程被复用（一个进程接多批），但函数无状态，counter 恒为 1。
    assert results["task_pool"]["max_batches_per_process"] > 1
    assert results["task_pool"]["max_counter"] == 1
    # ActorPool：实例数受 size 限制，实例状态跨调用累积。
    assert results["actor_pool"]["processes"] <= 2
    assert results["actor_pool"]["max_counter"] > 1
    return results


def section_pipeline_overlap():
    """上游 ActorPool + 下游 TaskPool 不能融合，于是能在时间上重叠。"""

    class Producer:
        def __init__(self):
            self.calls = 0

        def __call__(self, batch):
            self.calls += 1
            start = time.time()
            time.sleep(0.10)
            end = time.time()
            n = len(batch["id"])
            return {
                "id": batch["id"],
                "produced_start": np.full(n, start),
                "produced_end": np.full(n, end),
                "producer_instance": np.full(n, id(self)),
            }

    def consumer(batch):
        start = time.time()
        time.sleep(0.10)
        end = time.time()
        n = len(batch["id"])
        # 必须把上游时间戳带下来，否则 take_all() 只能看到末级算子的列。
        return {
            "id": batch["id"],
            "produced_start": batch["produced_start"],
            "produced_end": batch["produced_end"],
            "consumed_start": np.full(n, start),
            "consumed_end": np.full(n, end),
        }

    ds = ray.data.range(64, override_num_blocks=8).map_batches(
        Producer, batch_size=8, batch_format="numpy", num_cpus=1,
        udf_modifying_row_count=False,
        compute=ray.data.ActorPoolStrategy(
            size=1, max_tasks_in_flight_per_actor=1, max_concurrent_calls_per_actor=1,
        ),
    ).map_batches(
        consumer, batch_size=8, batch_format="numpy", num_cpus=1,
        udf_modifying_row_count=False,
    )
    text = explain_plan(ds._logical_plan)
    (RUN_DIR / "plans_pipeline_overlap.txt").write_text(text)
    plans = parse_plans(text)
    optimized = operator_types(plans["Physical Plan (Optimized)"])
    # 上游是 ActorPool，融合规则要求上游必须是 TaskPool，所以这三个 map 不会合并。
    assert len(optimized) == 4, optimized
    assert "ActorPoolMapOperator" in optimized, optimized

    materialized = ds.materialize()
    stats = materialized.stats()
    (RUN_DIR / "stats_pipeline_overlap.txt").write_text(stats)
    rows = materialized.take_all()

    produced = sorted({(round(r["produced_start"], 6), round(r["produced_end"], 6))
                       for r in rows})
    consumed = sorted({(round(r["consumed_start"], 6), round(r["consumed_end"], 6))
                       for r in rows})
    overlapped = [
        (p, c) for p in produced for c in consumed
        if c[0] < p[1] and p[0] < c[1]
    ]
    wall = max(c[1] for c in consumed) - min(p[0] for p in produced)
    serial_bound = 0.10 * (len(produced) + len(consumed))
    assert overlapped, "没有观察到算子间时间重叠，流水线假设不成立"
    (RUN_DIR / "overlap.json").write_text(
        __import__("json").dumps(
            {"produced": produced, "consumed": consumed,
             "overlapping_pairs": len(overlapped), "wall_s": round(wall, 3),
             "serial_bound_s": round(serial_bound, 3)},
            indent=2,
        )
    )
    return {
        "optimized_ops": optimized,
        "producer_calls": len(produced),
        "consumer_calls": len(consumed),
        "overlapping_pairs": len(overlapped),
        "wall_s": round(wall, 3),
        "serial_sum_s": round(serial_bound, 3),
        "faster_than_serial": wall < serial_bound,
    }


def experiment():
    with session():
        report = {
            "four_stage_plan": section_four_stage_plan(),
            "fusion_boundary": section_fusion_boundary(),
            "operator_level_parallelism": section_operator_level_parallelism(),
            "taskpool_vs_actorpool": section_taskpool_vs_actorpool(),
            "pipeline_overlap": section_pipeline_overlap(),
        }
        print(__import__("json").dumps(report, ensure_ascii=False, indent=2), flush=True)
        return {
            "scope": (
                "真实 CPU Ray Data 计划与执行；只看单机 4 CPU、内存数据源。"
                "不做跨节点、不对比真实 SQL 执行器。"
            ),
            "logical_to_physical": report["four_stage_plan"]["logical_ops"],
            "fused_operator": report["four_stage_plan"]["fused_operator"],
            "shuffle_is_fusion_boundary": True,
            "parallelism_is_per_operator": report["operator_level_parallelism"],
            "actor_vs_task_pool": report["taskpool_vs_actorpool"],
            "pipeline_overlap_pairs": report["pipeline_overlap"]["overlapping_pairs"],
            "pipeline_wall_vs_serial_s": [
                report["pipeline_overlap"]["wall_s"],
                report["pipeline_overlap"]["serial_sum_s"],
            ],
            "artifacts": str(RUN_DIR),
            "note": (
                "并行度结论只对 repartition 后的算子成立；pipeline 重叠只证明单机两个算子可同时在跑，"
                "不等于跨节点线性加速。stats 里的 Operator 编号是物理算子序号，不是 stage 序号。"
            ),
        }


if __name__ == "__main__":
    run(experiment)
