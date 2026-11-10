"""真实任务、依赖解析、Object Store 和有状态 Actor。"""
import os
import time
import ray
from common import run, session


@ray.remote
def square(value):
    time.sleep(0.1)
    return {"value": value * value, "pid": os.getpid()}


@ray.remote
def plus_one(value):
    return value + 1


@ray.remote(num_cpus=1)
class Counter:
    def __init__(self):
        self.value = 0

    def add(self, increment):
        self.value += increment
        return {"value": self.value, "pid": os.getpid()}


def experiment():
    with session(num_cpus=2):
        tasks = ray.get([square.remote(i) for i in range(8)], timeout=30)
        assert [r["value"] for r in tasks] == [i * i for i in range(8)]
        reference = ray.put(41)
        assert ray.get(plus_one.remote(reference), timeout=10) == 42
        actor = Counter.remote()
        calls = ray.get([actor.add.remote(1) for _ in range(5)], timeout=15)
        assert [r["value"] for r in calls] == [1, 2, 3, 4, 5]
        assert len({r["pid"] for r in calls}) == 1
        return {"scope": "真实 CPU 执行", "tasks": tasks, "actor_calls": calls,
                "object_reference_dependency": 42}


if __name__ == "__main__":
    run(experiment)
