"""固定数据分片留在 Actor 中；每轮只交换中心与局部 sum/count。

运行：./run.sh run 07
参数：RAYLAB_KMEANS_SHARDS=2 RAYLAB_KMEANS_ROWS=16000 ./run.sh run 07
不测网络流量；nbytes 仅表示算法传入/返回的 NumPy 数值载荷。
"""
import json
import os
import uuid

import numpy as np
import ray

from common import RUN_DIR, run, session

K = 4
DIM = 8
MAX_ITERATIONS = 30
TOLERANCE = 1e-8


@ray.remote(num_cpus=1)
class VectorShard:
    def __init__(self, values, shard_id):
        self.values = values  # 构造时接收一次，此后不重新传入原始向量。
        self.shard_id = shard_id
        self.instance = uuid.uuid4().hex
        self.calls = 0

    def identity(self):
        return {"shard_id": self.shard_id, "pid": os.getpid(),
                "instance": self.instance, "rows": len(self.values),
                "data_bytes": self.values.nbytes, "calls": self.calls}

    def partial(self, centers):
        self.calls += 1
        # 生产环境应进一步分批，避免构造过大的 N × K × D 临时数组。
        distances = ((self.values[:, None, :] - centers[None, :, :]) ** 2).sum(2)
        labels = distances.argmin(1)
        sums = np.zeros_like(centers)
        np.add.at(sums, labels, self.values)
        counts = np.bincount(labels, minlength=len(centers)).astype(np.int64)
        inertia = np.array([distances[np.arange(len(labels)), labels].sum()])
        return {"sums": sums, "counts": counts, "inertia": inertia,
                "identity": self.identity(),
                "numeric_payload_bytes": sums.nbytes + counts.nbytes + inertia.nbytes}

    def labels(self, centers):
        # 最后一轮为验收取回标签；不计入迭代中心/统计量的通信预算。
        return ((self.values[:, None, :] - centers[None, :, :]) ** 2).sum(2).argmin(1)


def serial_reference(values, centers):
    """独立串行路径：用点积计算距离，按类求均值。"""
    centers = centers.copy()
    for _ in range(MAX_ITERATIONS):
        distances = ((values * values).sum(1)[:, None]
                     + (centers * centers).sum(1)[None, :] - 2 * values @ centers.T)
        labels = distances.argmin(1)
        updated = np.stack([
            values[labels == i].mean(0) if np.any(labels == i) else centers[i]
            for i in range(K)
        ])
        shift = np.linalg.norm(updated - centers)
        centers = updated
        if shift <= TOLERANCE:
            break
    distances = ((values * values).sum(1)[:, None]
                 + (centers * centers).sum(1)[None, :] - 2 * values @ centers.T)
    return centers, distances.argmin(1)


def experiment():
    rows = int(os.environ.get("RAYLAB_KMEANS_ROWS", "12000"))
    shards = int(os.environ.get("RAYLAB_KMEANS_SHARDS", "3"))
    if not 1 <= shards <= 4 or not 128 <= rows <= 100000:
        raise ValueError("教学范围：SHARDS 为 1..4，ROWS 为 128..100000")
    rng = np.random.default_rng(20261031)
    true_centers = rng.normal(size=(K, DIM)) * 5
    values = true_centers[np.arange(rows) % K] + rng.normal(size=(rows, DIM)) * 0.5
    rng.shuffle(values)
    initial = values[rng.choice(rows, K, replace=False)].copy()
    expected_centers, expected_labels = serial_reference(values, initial)
    history = []
    converged = False

    with session():
        # ObjectRef 保持到实验结束；Actor 构造参数会被 Ray 自动解析。
        data_refs = [ray.put(part) for part in np.array_split(values, shards)]
        actors = [VectorShard.remote(ref, i) for i, ref in enumerate(data_refs)]
        identities = ray.get([actor.identity.remote() for actor in actors], timeout=45)
        assert len({v["pid"] for v in identities}) == shards
        centers = initial.copy()
        for iteration in range(MAX_ITERATIONS):
            center_ref = ray.put(centers)
            partials = ray.get([a.partial.remote(center_ref) for a in actors], timeout=30)
            sums = np.sum([p["sums"] for p in partials], axis=0)
            counts = np.sum([p["counts"] for p in partials], axis=0)
            assert counts.sum() == rows
            updated = centers.copy()  # 空簇保持旧中心。
            occupied = counts > 0
            updated[occupied] = sums[occupied] / counts[occupied, None]
            shift = float(np.linalg.norm(updated - centers))
            inertia = float(sum(p["inertia"][0] for p in partials))
            for original, partial in zip(identities, partials):
                current = partial["identity"]
                assert current["pid"] == original["pid"]
                assert current["instance"] == original["instance"]
                assert current["calls"] == iteration + 1
            if history:
                assert inertia <= history[-1]["inertia_before_update"] + 1e-6
            record = {
                "iteration": iteration + 1, "counts": counts.tolist(),
                "inertia_before_update": inertia, "center_shift": shift,
                "centers_to_actors_logical_bytes": centers.nbytes * shards,
                "partials_to_driver_numeric_bytes": sum(p["numeric_payload_bytes"] for p in partials),
                "actor_pids": [p["identity"]["pid"] for p in partials],
            }
            history.append(record)
            print(f"轮次 {iteration + 1}: SSE={inertia:.3f}, 中心移动={shift:.6f}, "
                  f"中心载荷={record['centers_to_actors_logical_bytes']} B, "
                  f"统计载荷={record['partials_to_driver_numeric_bytes']} B", flush=True)
            centers = updated
            if shift <= TOLERANCE:
                converged = True
                break
        assert converged, "未在轮次上限内收敛；请检查初始化、数据和上限"
        assert len(history) >= 2, "需要至少两轮来观察 Actor 数据复用"
        actual_labels = np.concatenate(ray.get(
            [a.labels.remote(ray.put(centers)) for a in actors], timeout=30,
        ))
        np.testing.assert_allclose(centers, expected_centers, rtol=1e-9, atol=1e-9)
        np.testing.assert_array_equal(actual_labels, expected_labels)
        np.savez(RUN_DIR / "centers.npz", initial=initial, distributed=centers,
                 serial=expected_centers)
        (RUN_DIR / "iterations.json").write_text(json.dumps(history, indent=2))
        return {
            "scope": "真实单机多进程 Actor KMeans；无 Spark/GPU 性能对比",
            "rows": rows, "dimensions": DIM, "clusters": K, "shards": shards,
            "iterations": len(history), "converged": converged,
            "serial_centers_match": True, "serial_labels_match": True,
            "actor_shards": identities, "input_numeric_bytes": values.nbytes,
            "per_round_logical_numeric_bytes": (
                history[0]["centers_to_actors_logical_bytes"]
                + history[0]["partials_to_driver_numeric_bytes"]),
            "history": str(RUN_DIR / "iterations.json"),
            "note": "载荷不含协议、序列化、元数据或最终标签验收；单机可能共享内存，不能称为实测网络流量。"
                    "Driver 保留小数据用于串行验收；Actor 丢失后的分片恢复不在本实验范围。",
        }


if __name__ == "__main__":
    run(experiment)
