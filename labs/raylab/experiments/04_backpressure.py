"""较快的数据生产者、慢消费者，验证实际执行器反压计时。"""
import time
import numpy as np
import ray
import ray.data
from common import RUN_DIR, run, session


def expand(batch):
    return {"id": batch["id"],
            "payload": np.ones((len(batch["id"]), 128 * 1024), dtype=np.uint8)}


class SlowConsumer:
    def __call__(self, batch):
        time.sleep(0.12)
        return {"id": batch["id"], "checksum": batch["payload"].sum(axis=1)}


def collect_metrics(summary):
    result = []
    for parent in summary.parents:
        result.extend(collect_metrics(parent))
    metrics = summary.extra_metrics
    result.append({"operator": summary.base_name, **{
        k: v for k, v in metrics.items()
        if "backpressure" in k or "obj_store_mem" in k
        or k in ("num_tasks_submitted", "num_tasks_finished")
    }})
    return result


def experiment():
    with session():
        ctx = ray.data.DataContext.get_current()
        ctx.execution_options.resource_limits = ray.data.ExecutionResources.for_limits(
            object_store_memory=16 * 1024**2,
        )
        ctx.target_max_block_size = 2 * 1024**2
        ds = ray.data.range(512, override_num_blocks=32).map_batches(
            expand, batch_size=16, batch_format="numpy",
            compute=ray.data.TaskPoolStrategy(size=2), num_cpus=1,
        ).map_batches(
            SlowConsumer, batch_size=16, batch_format="numpy", num_cpus=1,
            compute=ray.data.ActorPoolStrategy(
                size=1, max_tasks_in_flight_per_actor=1,
                max_concurrent_calls_per_actor=1,
            ),
        )
        done = ds.materialize()  # 最终输出很小；中间会产生约 64 MiB。
        rows = done.take_all()
        assert len(rows) == 512
        assert all(r["checksum"] == 128 * 1024 for r in rows)
        (RUN_DIR / "stats.txt").write_text(done.stats())
        metrics = collect_metrics(done.get_stats_summary())
        pressure_s = sum(
            m.get("task_submission_backpressure_time", 0)
            + m.get("task_output_backpressure_time", 0) for m in metrics
        )
        assert pressure_s > 0, "未观测到反压，不能把慢消费者直接视为反压证据"
        return {"scope": "真实 CPU 流水线与执行器指标",
                "rows": len(rows), "intermediate_mib": 64,
                "scheduling_object_store_budget_mib": 16,
                "observed_backpressure_s": pressure_s, "operator_metrics": metrics,
                "note": "计时是多算子累计值，可能重叠；预算不是内存硬隔离，也未证明任意规模内存稳定"}


if __name__ == "__main__":
    run(experiment)
