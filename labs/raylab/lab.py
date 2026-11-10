"""Run each learning experiment in its own process, with bounded execution."""

import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
EXPERIMENTS = {
    "01": ("core", "真实 Task、ObjectRef、Actor"),
    "02": ("logical_gpu", "逻辑 GPU 份额、排队和资源释放（不执行 CUDA）"),
    "03": ("data_pipeline", "Ray Data 批量推理、模型常驻和结果校验"),
    "04": ("backpressure", "慢下游与实际反压指标"),
    "05": ("recovery", "进程失败重试与 Actor 持久状态恢复"),
    "06": ("autoscaler", "真实装箱算法和状态转移的离线模拟"),
    "07": ("kmeans", "固定分片 Actor KMeans、逐轮归约与串行结果对照"),
    "08": ("llm_preprocess", "清洗、常驻分词、确定性拼接及写入失败重试"),
    "09": ("operators", "四段执行计划、算子融合、算子级并行度与流水线重叠"),
    "10": ("shuffle", "五条 shuffle 路径、分区数与输入块数解耦、热 key 倾斜"),
    "11": ("multimodal", "图像/音频/文本混存、列裁剪、按模态解码与先窄化再 shuffle"),
    "13": ("object_lifecycle", "两节点副本生命周期：按需复制、节点级共享与引用计数释放"),
}


def doctor():
    import ray
    import ray.data
    import ray._raylet

    packages = {}
    for name in ("ray", "numpy", "pandas", "pyarrow", "grpcio", "pytest"):
        packages[name] = importlib.metadata.version(name)
    return {
        "python": sys.executable,
        "virtual_environment": sys.prefix,
        "inherits_conda_dependencies": True,
        "ray_source": ray.__file__,
        "ray_native": ray._raylet.__file__,
        "source_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT.parent, text=True
        ).strip(),
        "packages": packages,
        "cpu_visible": os.cpu_count(),
        "gpu_device_present": Path("/dev/nvidia0").exists(),
        "default_experiment_cpus": 4,
        "default_object_store_mib": 256,
        "temp_directory": str(ROOT / "tmp"),
        "note": "import 检查；不代表 Ray 服务或真实 GPU 已通过验证",
    }


def stop_owned_process(process):
    """Only signal the process group created for this exact experiment."""
    if process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def run_one(key, timeout_s, suite_dir):
    slug, description = EXPERIMENTS[key]
    run_dir = suite_dir / f"{key}_{slug}"
    run_dir.mkdir()
    env = os.environ.copy()
    env.update({
        "RAYLAB_RUN_DIR": str(run_dir),
        "RAYLAB_HOME": str(ROOT),
        "RAY_ADDRESS": "local",
        "RAY_USAGE_STATS_ENABLED": "0",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "TMPDIR": str(ROOT / "tmp"),
        "RAY_TMPDIR": str(ROOT / "tmp"),
    })
    print(f"\n[{key}] {description}\n输出：{run_dir}", flush=True)
    started = time.monotonic()
    process = subprocess.Popen(
        [sys.executable, "-u", str(ROOT / "experiments" / f"{key}_{slug}.py")],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    (run_dir / "process.json").write_text(json.dumps({
        "pid": process.pid, "started_at": datetime.now(timezone.utc).isoformat(),
        "timeout_s": timeout_s,
    }, indent=2))
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    timed_out = False
    try:
        with (run_dir / "console.log").open("wb") as log:
            while selector.get_map():
                if time.monotonic() - started > timeout_s and process.poll() is None:
                    timed_out = True
                    print(f"实验超过 {timeout_s} 秒，正在退出自己的进程。", flush=True)
                    stop_owned_process(process)
                for entry, _ in selector.select(timeout=0.25):
                    data = os.read(entry.fd, 65536)
                    if not data:
                        selector.unregister(entry.fileobj)
                        continue
                    log.write(data)
                    log.flush()
                    sys.stdout.write(data.decode(errors="replace"))
                    sys.stdout.flush()
            code = process.wait(timeout=5)
    finally:
        stop_owned_process(process)
        selector.close()
        process.stdout.close()
    result_path = run_dir / "result.json"
    result = json.loads(result_path.read_text()) if result_path.exists() else {}
    status = "PASS" if code == 0 and result.get("status") == "PASS" else "FAIL"
    summary = {
        "experiment": key, "status": status, "exit_code": code,
        "timed_out": timed_out, "elapsed_s": round(time.monotonic() - started, 2),
        "directory": str(run_dir),
    }
    (run_dir / "runner.json").write_text(json.dumps(summary, indent=2))
    print(f"[{key}] {status} ({summary['elapsed_s']}s)", flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description="当前机器的 Ray 学习实验室")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="检查 Python、依赖和源码位置")
    sub.add_parser("list", help="列出实验")
    run = sub.add_parser("run", help="执行一个实验或 all")
    run.add_argument("experiment", choices=[*EXPERIMENTS, "all"])
    run.add_argument("--timeout", type=int, default=180, help="每个实验超时秒数")
    args = parser.parse_args()
    if args.command == "doctor":
        print(json.dumps(doctor(), ensure_ascii=False, indent=2))
        return
    if args.command == "list":
        for key, (_, description) in EXPERIMENTS.items():
            print(f"{key}  {description}")
        return
    if args.timeout < 1:
        parser.error("--timeout 必须为正数")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    suite_dir = ROOT / "results" / stamp
    suite_dir.mkdir(parents=True)
    (suite_dir / "environment.json").write_text(
        json.dumps(doctor(), ensure_ascii=False, indent=2)
    )
    keys = list(EXPERIMENTS) if args.experiment == "all" else [args.experiment]
    results = []
    for key in keys:
        results.append(run_one(key, args.timeout, suite_dir))
        if results[-1]["status"] != "PASS":
            break  # Fail closed: inspect the failing experiment before continuing.
    (suite_dir / "summary.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2)
    )
    print(f"\n本次结果：{suite_dir / 'summary.json'}")
    if any(result["status"] != "PASS" for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
