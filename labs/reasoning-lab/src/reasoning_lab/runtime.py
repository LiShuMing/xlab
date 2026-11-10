"""Device selection, synchronized stage timing and sampled memory telemetry."""

from __future__ import annotations

import contextlib
import importlib.metadata
import json
import platform
import random
import subprocess
import threading
import time
from pathlib import Path

import numpy as np
import psutil
import torch


def choose_device(value: str = "auto") -> str:
    """auto 优先 MPS，其余必须显式指定。

    指定 mps 但环境不支持时直接报错，而不是悄悄退回 cpu：
    换了设备，同一条 seed 的数值也会不同，静默回退会让复现失败无法解释。
    """
    if value == "auto":
        return "mps" if torch.backends.mps.is_available() else "cpu"
    if value == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS is not available in this Python/PyTorch environment")
    if value not in {"cpu", "mps"}:
        raise ValueError("Supported devices: auto, cpu, mps")
    return value


def seed_all(seed: int) -> None:
    """一次性对齐四路随机源。只调 torch.manual_seed 不够：
    题目抽样走 python random，bootstrap 走 numpy。
    """
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.backends.mps.is_available():
        torch.mps.manual_seed(seed)


def synchronize(device: str) -> None:
    """MPS 的 kernel 是异步提交的，不同步就拿不到真实耗时（会漏掉排队时间）。
    CPU 同步执行，不需要额外动作。
    """
    if device == "mps":
        torch.mps.synchronize()


def environment(device: str) -> dict:
    """运行环境快照，写进每个 run 目录。

    版本、机器、时区、内存都记：结果变了的时候，先排除“环境其实换了”。
    cpu_fallback 记录 MPS 是否允许算子回退到 CPU，回退会让速度数字失真。
    """
    import os

    return {
        "python": platform.python_version(),
        "machine": platform.machine(),
        "os": platform.platform(),
        "timezone": "Asia/Shanghai",
        "device": device,
        "packages": {
            name: importlib.metadata.version(name)
            for name in ["torch", "transformers", "safetensors", "huggingface-hub"]
        },
        "mps_available": torch.backends.mps.is_available(),
        "cpu_fallback": os.environ.get("PYTORCH_ENABLE_MPS_FALLBACK", "0"),
        "physical_memory_bytes": psutil.virtual_memory().total,
    }


def memory_snapshot(device: str) -> dict:
    """一次内存读数：RSS、可用内存、swap 换入换出，MPS 再加三项分配量。

    swap 在这里很关键：一旦开始换页，训练会从“慢”变成“抖动”，
    所以调用方要能区分“占了很多内存”和“已经在换页”。
    """
    swap, virtual = psutil.swap_memory(), psutil.virtual_memory()
    snapshot = {
        "rss_bytes": psutil.Process().memory_info().rss,
        "available_bytes": virtual.available,
        "swap_used_bytes": swap.used,
        "swap_out_bytes": swap.sout,
        "swap_in_bytes": swap.sin,
    }
    if device == "mps":
        snapshot.update(
            mps_current_bytes=torch.mps.current_allocated_memory(),
            mps_driver_bytes=torch.mps.driver_allocated_memory(),
            mps_recommended_bytes=torch.mps.recommended_max_memory(),
        )
    return snapshot


class Monitor:
    """周期性内存采样 + Chrome trace 阶段记录。

    采到的是“观察到的水位”，不是 GPU 精确峰值：一秒一个点会错过更短的尖峰，
    所以它只能证明“至少用过这么多”，不能证明“从未超过”。
    """

    def __init__(self, path: Path, device: str, interval: float = 1.0):
        self.path, self.device, self.interval = path, device, interval
        self.stage = "start"
        # One clock for spans and samples: mixing monotonic() with perf_counter() would
        # put trace events and system.jsonl rows on unrelated timelines.
        self.started = time.perf_counter()
        self.depth = 0
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.high_water = {}
        self.initial = memory_snapshot(device)
        self.thread = threading.Thread(target=self._sample, daemon=True)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.error = None
        self.spans = []

    def snapshot(self) -> dict:
        """采一次样：绝对值 + 相对启动时刻的增量。

        增量比绝对值有用：swap 本来就可能已有存量，
        真正的判据是“这次运行期间又涨了多少”。
        """
        record = memory_snapshot(self.device)
        record.update(
            seconds=time.perf_counter() - self.started,
            stage=self.stage,
            swap_growth_bytes=record["swap_used_bytes"] - self.initial["swap_used_bytes"],
            pageout_growth_bytes=record["swap_out_bytes"] - self.initial["swap_out_bytes"],
        )
        with self.lock:
            for key in ["rss_bytes", "mps_current_bytes", "mps_driver_bytes"]:
                if key in record:
                    self.high_water[key] = max(self.high_water.get(key, 0), record[key])
            with self.path.open("a") as file:
                file.write(json.dumps(record) + "\n")
        return record

    def _sample(self):
        """后台采样线程。异常只记录不抛：监控故障不能把训练杀掉。"""
        try:
            while not self.stop_event.wait(self.interval):
                self.snapshot()
        except Exception as exc:
            self.error = repr(exc)

    def __enter__(self):
        """先同步采一次基线，再启动采样线程。"""
        self.snapshot()
        self.thread.start()
        return self

    def __exit__(self, *_args):
        """停线程、补最后一次采样，并把 spans 写成 Chrome trace 格式。"""
        self.stop_event.set()
        self.thread.join()
        self.snapshot()
        with self.path.with_name("trace.json").open("w") as file:
            json.dump({"traceEvents": self.spans, "displayTimeUnit": "ms"}, file)

    @contextlib.contextmanager
    def phase(self, name: str, metrics: dict, **labels):
        """记录一个被测量的阶段；额外 labels 会出现在 trace 的 args 里。

        depth 表示嵌套层级（trace 视图里每一层占一行）；前后各同步一次，
        保证子阶段的时间不被异步排队污染。
        metrics 里存的是 `<name>_seconds`（供 metrics.jsonl），
        spans 里存的是 Chrome trace 的 begin/duration 微秒。
        """
        stage, depth = self.stage, self.depth
        self.stage, self.depth = name, depth + 1
        synchronize(self.device)
        started = time.perf_counter()
        try:
            yield
        finally:
            synchronize(self.device)
            self.depth = depth
            # Samples taken between phases keep the name of the phase that just ended.
            self.stage = name if depth == 0 else stage
            seconds = time.perf_counter() - started
            metrics[f"{name}_seconds"] = seconds
            self.spans.append(
                {
                    "name": name,
                    "ph": "X",
                    "pid": 1,
                    "tid": depth + 1,
                    "ts": (started - self.started) * 1e6,
                    "dur": seconds * 1e6,
                    "args": {"depth": depth, **labels},
                }
            )
            self.snapshot()

    def event(self, name: str, **fields) -> None:
        """打一个瞬时事件（trace 里的 ph="i"），让“某个决定”与阶段时间对齐。"""
        with self.lock:
            self.spans.append(
                {
                    "name": name,
                    "ph": "i",
                    "s": "t",
                    "pid": 1,
                    "tid": 1,
                    "ts": (time.perf_counter() - self.started) * 1e6,
                    "args": {"stage": self.stage, **fields},
                }
            )


def git_identity(root: Path) -> dict:
    """git 提交号 + 未提交改动的哈希。

    工作区脏的时候 commit 号不足以标识代码，所以把 diff 文本也哈希一份。
    git 不可用（返回非零）时 commit 记为 None，运行继续，但 provenance 会显示 none。
    """

    def git(*args):
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else None

    from .tasks import digest

    return {"commit": git("rev-parse", "HEAD"), "dirty_diff_hash": digest(git("diff", "HEAD"))}


def doctor(device: str) -> dict:
    """最小可跑的端到端探针，fp32 和 bf16 各试一次。

    它覆盖链路上最容易“静默坏掉”的四个算子：SDPA、rsqrt 归一化、
    矩阵乘、cross_entropy + backward + AdamW.step。
    passed 要求梯度有限且权重真的被更新：只“跑通不报错”是不够的。
    """
    report = environment(device)
    probes = {}
    for name, dtype in [("fp32", torch.float32), ("bf16", torch.bfloat16)]:
        try:
            x = torch.randn(1, 2, 4, 8, device=device, dtype=dtype, requires_grad=True)
            weight = torch.nn.Parameter(torch.randn(8, 8, device=device, dtype=dtype))
            optimizer = torch.optim.AdamW([weight], lr=1e-3, weight_decay=0)
            before = weight.detach().clone()
            y = torch.nn.functional.scaled_dot_product_attention(x, x, x, is_causal=True)
            y = y * torch.rsqrt(y.float().square().mean(-1, keepdim=True) + 1e-6).to(dtype)
            logits = y @ weight
            loss = torch.nn.functional.cross_entropy(
                logits.float().reshape(-1, 8), torch.zeros(8, device=device, dtype=torch.long)
            )
            loss.backward()
            finite = bool(torch.isfinite(weight.grad).all())
            optimizer.step()
            synchronize(device)
            probes[name] = {
                "passed": finite and not torch.equal(before, weight),
                "loss": loss.item(),
            }
        except (RuntimeError, TypeError) as exc:
            probes[name] = {"passed": False, "error": str(exc)}
    report.update(probes=probes, resources=memory_snapshot(device), passed=probes["fp32"]["passed"])
    return report
