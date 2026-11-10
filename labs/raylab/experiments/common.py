"""Small helpers shared by standalone learning scripts."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal
import time
import traceback
import psutil

ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = Path(os.environ.get("RAYLAB_RUN_DIR", ROOT / "results" / "manual"))
RUN_DIR.mkdir(parents=True, exist_ok=True)


def interrupted(signum, frame):
    raise SystemExit(128 + signum)


signal.signal(signal.SIGTERM, interrupted)


@contextmanager
def session(*, num_cpus=4, num_gpus=0):
    import ray

    try:
        info = ray.init(
            address="local", num_cpus=num_cpus, num_gpus=num_gpus,
            object_store_memory=256 * 1024**2,
            include_dashboard=False, _node_ip_address="127.0.0.1",
            _temp_dir=str(ROOT / "tmp"),
        )
        (RUN_DIR / "ray_session.json").write_text(json.dumps({
            "session_dir": info.address_info.get("session_dir"),
            "gcs_address": info.address_info.get("gcs_address"),
            "cluster_resources": ray.cluster_resources(),
        }, indent=2))
        yield
    finally:
        owned = psutil.Process().children(recursive=True)
        identities = []
        for process in owned:
            try:
                identities.append({"pid": process.pid, "created": process.create_time(),
                                   "name": process.name()})
            except psutil.NoSuchProcess:
                pass
        ray.shutdown()  # Only shuts down the local cluster started above.
        _, alive = psutil.wait_procs(owned, timeout=5)
        remaining = []
        for process in alive:
            try:
                if process.is_running() and process.status() != psutil.STATUS_ZOMBIE:
                    remaining.append(process.pid)
            except psutil.NoSuchProcess:
                pass
        (RUN_DIR / "cleanup.json").write_text(json.dumps({
            "owned_processes": identities, "remaining_live_pids": remaining,
        }, indent=2))
        if remaining:
            raise RuntimeError(f"本实验仍有存活子进程，需检查 cleanup.json: {remaining}")


def run(experiment):
    start = time.monotonic()
    try:
        observations = experiment()
    except BaseException as error:
        result = {
            "status": "FAIL", "error": repr(error),
            "traceback": traceback.format_exc(),
            "elapsed_s": time.monotonic() - start,
        }
        (RUN_DIR / "result.json").write_text(json.dumps(result, indent=2))
        raise
    result = {
        "status": "PASS", "observations": observations,
        "elapsed_s": round(time.monotonic() - start, 3),
    }
    (RUN_DIR / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
