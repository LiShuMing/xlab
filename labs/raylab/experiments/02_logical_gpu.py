"""只模拟 GPU 记账；不导入 CUDA，不声称验证显存或真实 GPU 性能。"""
import os
import ray
from common import run, session


@ray.remote(num_cpus=1, num_gpus=0.5)
class HalfGPU:
    def info(self):
        return {"pid": os.getpid(), "gpu_ids": ray.get_gpu_ids(),
                "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES")}


def experiment():
    with session(num_gpus=1):
        first, second = HalfGPU.remote(), HalfGPU.remote()
        assigned = ray.get([first.info.remote(), second.info.remote()], timeout=30)
        assert assigned[0]["gpu_ids"] == assigned[1]["gpu_ids"]

        third = HalfGPU.remote()
        waiting = third.info.remote()
        ready, _ = ray.wait([waiting], timeout=1)
        assert not ready, "第三个 Actor 应等待 GPU 额度"

        ray.kill(first, no_restart=True)
        admitted = ray.get(waiting, timeout=30)
        assert admitted["gpu_ids"] == assigned[0]["gpu_ids"]
        return {"scope": "真实 Ray 调度，虚拟 GPU 资源，无 CUDA 执行",
                "first_two": assigned, "third_waited": True,
                "third_after_release": admitted}


if __name__ == "__main__":
    run(experiment)
