"""仅终止本实验自己的 Worker／Actor；演示重新执行与显式持久化。"""
import json
import os
import time
from pathlib import Path
import ray
from common import RUN_DIR, run, session


@ray.remote(max_retries=2)
def crash_once(marker):
    try:
        fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return {"value": 42, "retry_pid": os.getpid()}
    else:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        os._exit(23)  # 故意让本任务进程异常退出。


@ray.remote(num_cpus=1, max_restarts=2, max_task_retries=10)
class DurableCounter:
    def __init__(self, path):
        self.path = Path(path)
        self.value = json.loads(self.path.read_text()) if self.path.exists() else 0

    def add(self, increment, persist=True):
        self.value += increment
        if persist:
            temporary = self.path.with_suffix(".pending")
            temporary.write_text(json.dumps(self.value))
            temporary.replace(self.path)
        return self.snapshot()

    def snapshot(self):
        return {"value": self.value, "pid": os.getpid()}


def experiment():
    with session():
        marker = RUN_DIR / "crash_once.marker"
        task = ray.get(crash_once.remote(str(marker)), timeout=45)
        first_pid = int(marker.read_text())
        assert task["value"] == 42 and task["retry_pid"] != first_pid
        counter = DurableCounter.remote(str(RUN_DIR / "counter.json"))
        committed = ray.get(counter.add.remote(5), timeout=30)
        transient = ray.get(counter.add.remote(2, persist=False), timeout=10)
        assert transient["value"] == 7
        ray.kill(counter, no_restart=False)
        # kill() 发出请求后返回；必须等到新的进程出现，不能读到旧进程就验收。
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            try:
                restored = ray.get(counter.snapshot.remote(), timeout=5)
            except (ray.exceptions.GetTimeoutError, ray.exceptions.RayActorError):
                continue
            if restored["pid"] != committed["pid"]:
                break
            time.sleep(0.1)
        else:
            raise AssertionError("40 秒内未观察到 Actor 在新进程中重建")
        assert restored["value"] == 5
        return {"scope": "真实任务进程失败与 Actor 重启；单机文件持久化",
                "failed_task_pid": first_pid, "retried_task": task,
                "committed": committed, "uncommitted": transient, "restored": restored,
                "note": "重新执行而非指令级续跑；未持久化的 2 丢失；跨机器恢复需共享持久存储"}


if __name__ == "__main__":
    run(experiment)
