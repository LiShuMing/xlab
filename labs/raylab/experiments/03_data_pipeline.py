"""用 NumPy 模拟小模型；观察跨 batch 复用同一模型 Actor。"""
import os
import time
import uuid
import numpy as np
import ray
import ray.data
from common import RUN_DIR, run, session


class Predictor:
    def __init__(self):
        time.sleep(0.1)  # 模拟加载模型的固定开销。
        self.weights = np.array([2.0, 1.0])
        self.instance = uuid.uuid4().hex
        self.calls = 0

    def __call__(self, batch):
        self.calls += 1
        time.sleep(0.02)
        ids = batch["id"]
        return {"id": ids,
                "prediction": ids * self.weights[0] + self.weights[1],
                "model_instance": np.full(len(ids), self.instance),
                "actor_pid": np.full(len(ids), os.getpid()),
                "batch_call": np.full(len(ids), self.calls)}


def experiment():
    with session():
        ds = ray.data.range(512, override_num_blocks=16).map_batches(
            Predictor, batch_size=16, batch_format="numpy", num_cpus=1,
            udf_modifying_row_count=False,
            compute=ray.data.ActorPoolStrategy(
                size=2, max_tasks_in_flight_per_actor=1,
                max_concurrent_calls_per_actor=1,
            ),
        )
        output = RUN_DIR / "predictions"
        ds.write_parquet(str(output))
        stats = ds.stats()
        print(stats)
        (RUN_DIR / "stats.txt").write_text(stats)

        rows = ray.data.read_parquet(str(output)).take_all()
        assert len(rows) == 512 and len({r["id"] for r in rows}) == 512
        assert all(r["prediction"] == 2 * r["id"] + 1 for r in rows)
        models = {r["model_instance"] for r in rows}
        assert 1 <= len(models) <= 2
        assert max(r["batch_call"] for r in rows) > 1
        return {"scope": "真实 CPU Ray Data，无深度学习模型／GPU",
                "rows": len(rows), "unique_model_instances": len(models),
                "actor_pids": sorted({r["actor_pid"] for r in rows}),
                "max_calls_per_model": max(r["batch_call"] for r in rows),
                "output": str(output), "stats": str(RUN_DIR / "stats.txt")}


if __name__ == "__main__":
    run(experiment)
