"""两节点集群上的对象副本生命周期：按需复制与引用计数释放。

单机实验（01~11）里所有 worker 共享同一个 Plasma，`node_ids` 恒为 1，
看不出对象的分布行为。本实验用 loopback 起两个真实 Ray 节点：

    127.0.0.1（或本机主 IP）= head，driver 所在节点
    127.0.0.2               = worker，对象的生产者所在节点

然后逐步验证四个事实：

    1. 对象产生后只有一份，在生产者节点
    2. 同节点的多个 task 共用这一份（副本粒度是节点，不是 task）
    3. 跨节点消费会产生第二份副本（按需复制，不是预复制）
    4. 引用计数归零后 Plasma 占用下降（对象被回收）

注意：两个节点是同一台机器上的两个 Ray 进程，走完整网络栈，
所以能反映跨节点的位置语义；但传输本身不出物理网卡，
本实验不做带宽或延迟测量。
"""

import gc
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from contextlib import contextmanager

import numpy as np
import ray
from ray._private import internal_api
from ray.util.scheduling_strategies import NodeAffinitySchedulingStrategy

from common import run

GCS_PORT = 6379
WORKER_IP = "127.0.0.2"
OBJECT_STORE_BYTES = 80 * 1024**2
PAYLOAD_BYTES = 8_000_000

# 节点临时目录固定用 /tmp：Ray 会在其下拼 sockets/plasma_store，
# AF_UNIX（Unix domain socket）路径上限 107 字节，工作区深路径会直接启动失败。
HEAD_TMP = "/tmp/raylab13_head"
WORKER_TMP = "/tmp/raylab13_node2"


def ray_cli():
    """用当前解释器执行 ray CLI。

    venv 里没有 ray 可执行文件（ray 通过 .pth 指向源码），PATH 上的 ray
    可能来自另一个环境，所以这里固定用 sys.executable + 源码入口。
    """
    return [sys.executable, "-c", "from ray.scripts.scripts import main; main()"]


def port_open(host, port):
    with socket.socket() as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


@contextmanager
def two_node_cluster():
    """起 head + worker 两个真实节点。实验独占端口，结束时整体回收。"""
    head_ip = socket.gethostbyname(socket.gethostname())
    if port_open(head_ip, GCS_PORT):
        raise RuntimeError(
            f"{head_ip}:{GCS_PORT} 已被占用，本实验需要独占两个节点；"
            "请先执行 ray stop --force"
        )
    env = os.environ.copy()
    env.pop("RAY_ADDRESS", None)  # lab.py 注入的 local 会干扰显式集群地址

    # 节点临时目录固定用 /tmp，原因见上方的路径长度说明。
    common = [
        "--disable-usage-stats",
        f"--object-store-memory={OBJECT_STORE_BYTES}",
        "--num-cpus=2",
    ]

    def start(tag, args):
        done = subprocess.run(
            [*ray_cli(), "start", *args],
            env=env, capture_output=True, text=True, timeout=240,
        )
        if done.returncode != 0:
            raise RuntimeError(
                f"{tag} 启动失败：\n{done.stdout[-1500:]}\n{done.stderr[-1500:]}"
            )
        return done.stdout

    try:
        start("head", [
            "--head", f"--node-ip-address={head_ip}", f"--port={GCS_PORT}",
            "--object-manager-port=8076", "--node-manager-port=8077",
            "--dashboard-agent-grpc-port=8078", "--dashboard-agent-listen-port=8079",
            f"--temp-dir={HEAD_TMP}", *common,
        ])
        start("worker", [
            f"--address={head_ip}:{GCS_PORT}", f"--node-ip-address={WORKER_IP}",
            "--object-manager-port=8176", "--node-manager-port=8177",
            "--dashboard-agent-grpc-port=8178", "--dashboard-agent-listen-port=8179",
            f"--temp-dir={WORKER_TMP}", *common,
        ])
        yield head_ip
    finally:
        subprocess.run(
            [*ray_cli(), "stop", "--force"], env=env, capture_output=True, timeout=180
        )
        for path in (HEAD_TMP, WORKER_TMP):
            shutil.rmtree(path, ignore_errors=True)


@ray.remote
def produce(nbytes):
    """产生一个不可变对象，返回值的大小由 nbytes 决定。"""
    return np.ones(nbytes // 8, dtype=np.float64)


@ray.remote
def measure(payload):
    """只读消费：返回载荷大小和所在进程，用于证明副本复用了同一块共享内存。"""
    return {"nbytes": int(payload.nbytes), "pid": os.getpid()}


def nodes_of(ref):
    """对象当前被登记在哪些节点上（Ray 只知道节点，不知道进程）。"""
    return set(ray.experimental.get_object_locations([ref])[ref]["node_ids"])


def wait_for_nodes(ref, expected, timeout=45):
    """位置通知是异步的，轮询到副本数符合预期或超时。"""
    deadline = time.monotonic() + timeout
    seen = set()
    while time.monotonic() < deadline:
        seen = nodes_of(ref)
        if len(seen) == expected:
            return seen
        time.sleep(0.2)
    raise AssertionError(f"等待 {expected} 个副本超时，实际 {len(seen)} 个：{seen}")


def plasma_used_mib():
    """当前节点 Plasma 已用内存（MiB）。走 raylet 本地 RPC，不依赖 dashboard。"""
    text = internal_api.memory_summary()
    match = re.search(r"Plasma memory usage ([\d.]+) MiB", text)
    if match is None:
        raise AssertionError(f"无法从 memory_summary 解析 Plasma 用量：\n{text[:400]}")
    return float(match.group(1))


def experiment():
    with two_node_cluster() as head_ip:
        os.environ.pop("RAY_ADDRESS", None)
        ray.init(
            address=f"{head_ip}:{GCS_PORT}",
            include_dashboard=False,
            _node_ip_address=head_ip,
        )
        try:
            by_ip = {node["NodeManagerAddress"]: node["NodeID"] for node in ray.nodes()}
            assert WORKER_IP in by_ip, f"第二节点未加入：{list(by_ip)}"
            assert head_ip in by_ip, f"head 未找到：{list(by_ip)}"
            head_id, worker_id = by_ip[head_ip], by_ip[WORKER_IP]
            topology = {
                "head": {"ip": head_ip, "node_id": head_id[:12]},
                "worker": {"ip": WORKER_IP, "node_id": worker_id[:12]},
                "cpus": ray.cluster_resources().get("CPU"),
                "object_store_mib": ray.cluster_resources().get("object_store_memory") // 2**20,
            }

            # ── 1. 产生，但不消费：只有生产者那一份 ───────────────────────
            ref = produce.options(
                scheduling_strategy=NodeAffinitySchedulingStrategy(
                    node_id=worker_id, soft=False
                )
            ).remote(PAYLOAD_BYTES)
            # fetch_local=False：只等任务完成，不把数据拉到 driver 所在节点。
            # 换成默认的 fetch_local=True，这一步就会自己制造出第二份副本。
            ray.wait([ref], timeout=60, fetch_local=False)
            after_produce = wait_for_nodes(ref, 1)
            assert after_produce == {worker_id}, (
                f"未消费时应只有生产者一份，实际 {after_produce}"
            )
            sizes = ray.experimental.get_object_locations([ref])[ref]

            # ── 2. 同节点的多个 task 共用一份 ────────────────────────────
            # 副本粒度是节点：同一节点上的 task 通过共享内存读同一块数据，
            # 不会因为并发 3 个消费者就产生 3 份。
            workers_side = [
                measure.options(
                    scheduling_strategy=NodeAffinitySchedulingStrategy(
                        node_id=worker_id, soft=False
                    )
                ).remote(ref)
                for _ in range(3)
            ]
            worker_calls = ray.get(workers_side, timeout=60)
            after_local_consume = wait_for_nodes(ref, 1)
            assert after_local_consume == {worker_id}, (
                f"同节点消费不应增加副本，实际 {after_local_consume}"
            )
            assert len({call["pid"] for call in worker_calls}) >= 1
            assert all(call["nbytes"] == PAYLOAD_BYTES for call in worker_calls)

            # ── 3. 跨节点消费：按需复制出第二份 ──────────────────────────
            # driver 在 head 上 ray.get，head 的 raylet 会从 worker 拉取整份对象，
            # 拉取完成后本地 Plasma 多一份副本，owner 收到位置更新通知。
            before_get = plasma_used_mib()
            payload = ray.get(ref, timeout=120)
            assert payload.nbytes == PAYLOAD_BYTES
            after_cross = wait_for_nodes(ref, 2)
            assert after_cross == {head_id, worker_id}, (
                f"跨节点消费后应有两份，实际 {after_cross}"
            )
            after_get = plasma_used_mib()
            copied_mib = round(after_get - before_get, 2)

            # ── 4. 引用计数归零：副本被回收 ──────────────────────────────
            # ObjectRef 析构会通知 owner 释放引用；owner 引用归零后通知各节点删除。
            # 这里只能观测 Plasma 占用下降——对象一旦删除就没有 ref 可查位置了。
            del payload
            del ref
            gc.collect()
            released = after_get
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                released = plasma_used_mib()
                if released < after_get - 1:
                    break
                time.sleep(0.5)
            else:
                raise AssertionError(
                    f"释放引用后 Plasma 用量未下降：释放前 {after_get} MiB，"
                    f"等待 30 秒后仍为 {released} MiB"
                )

            return {
                "scope": "两个真实 Ray 节点（loopback），观测对象分布，不做带宽测量",
                "topology": topology,
                "stages": {
                    "1_produce_only": {
                        "description": "在 worker 节点产生，未消费",
                        "node_ids": [n[:12] for n in sorted(after_produce)],
                        "copies": len(after_produce),
                        "object_size_bytes": sizes["object_size"],
                    },
                    "2_same_node_consume": {
                        "description": "worker 上 3 个并发 task 消费同一对象",
                        "node_ids": [n[:12] for n in sorted(after_local_consume)],
                        "copies": len(after_local_consume),
                        "consumer_pids": sorted({c["pid"] for c in worker_calls}),
                    },
                    "3_cross_node_consume": {
                        "description": "driver（head）get，触发按需拉取",
                        "node_ids": [n[:12] for n in sorted(after_cross)],
                        "copies": len(after_cross),
                        "payload_bytes": PAYLOAD_BYTES,
                        "plasma_head_before_mib": round(before_get, 2),
                        "plasma_head_after_mib": round(after_get, 2),
                        "plasma_delta_mib": copied_mib,
                    },
                    "4_release": {
                        "description": "删除引用后 Plasma 回收",
                        "plasma_before_release_mib": round(after_get, 2),
                        "plasma_after_release_mib": round(released, 2),
                        "reclaimed_mib": round(after_get - released, 2),
                    },
                },
                "conclusions": {
                    "default_copies": "1，位于生产者节点",
                    "copy_granularity": "节点；同节点 task 共享，不是每 task 一份",
                    "replication_trigger": "消费方拉取，不存在主动复制或副本因子",
                    "release_trigger": "ObjectRef 析构 → owner 引用归零 → 各节点删除",
                },
            }
        finally:
            ray.shutdown()


if __name__ == "__main__":
    run(experiment)
