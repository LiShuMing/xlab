"""Explicit adoption and restart of one local vLLM server with current tracing."""

import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from prometheus_client.parser import text_string_to_metric_families

from llm_observe import manager
from llm_observe.paths import LOCAL, ROOT, write_json
from llm_observe.vllm_launch import validate_arguments

PROFILE = LOCAL / "run" / "vllm-profile.json"
PROCESS = LOCAL / "run" / "vllm-process.json"


def listener(origin: str) -> int | None:
    port = urlsplit(origin).port or 80
    result = subprocess.run(
        ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode not in {0, 1}:
        raise RuntimeError("Could not identify model listener")
    pids = {int(line) for line in result.stdout.split()}
    if len(pids) > 1:
        raise RuntimeError("Multiple model listeners; refusing adoption/restart")
    return next(iter(pids), None)


def snapshot(pid: int) -> dict | None:
    identity = manager.identity(pid)
    if identity is None:
        return None
    try:
        pgid = os.getpgid(pid)
    except ProcessLookupError:
        return None
    return {"pid": pid, "identity": identity, "pgid": pgid}


def matches(record: dict) -> bool:
    actual = snapshot(record["pid"])
    if actual is None:
        return False
    if actual != record:
        raise RuntimeError(f"Model PID {record['pid']} identity changed; refusing to signal it")
    return True


def tree(pid: int) -> list[dict]:
    output = subprocess.check_output(["ps", "-axo", "pid=,ppid="], text=True)
    rows = [tuple(map(int, line.split())) for line in output.splitlines()]
    selected = {pid}
    while True:
        children = {child for child, parent in rows if parent in selected}
        if children <= selected:
            break
        selected |= children
    return [record for child in sorted(selected) if (record := snapshot(child)) is not None]


def require_idle(origin: str) -> None:
    metrics = manager.get(origin + "/metrics").decode()
    gauges = {"vllm:num_requests_running": [], "vllm:num_requests_waiting": []}
    for family in text_string_to_metric_families(metrics):
        for sample in family.samples:
            if sample.name in gauges:
                gauges[sample.name].append(sample.value)
    if any(not values for values in gauges.values()) or any(sum(v) for v in gauges.values()):
        raise RuntimeError("Model is busy or idle metrics are missing; old service left running")


def wait_gone(record: dict, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            living = matches(record)
        except RuntimeError:
            # During exit ps may expose transient argv; do not signal an unverified identity.
            pass
        else:
            if not living:
                return True
        time.sleep(0.1)
    return False


def terminate(records: list[dict], api_pid: int) -> None:
    root = next((record for record in records if record["pid"] == api_pid), None)
    if root is not None and matches(root):
        os.kill(api_pid, signal.SIGTERM)
        wait_gone(root, 30)
    for record in records:
        if not matches(record):
            continue
        os.kill(record["pid"], signal.SIGTERM)
        if wait_gone(record, 5):
            continue
        if matches(record):
            os.kill(record["pid"], signal.SIGKILL)
        if not wait_gone(record, 5):
            raise RuntimeError(f"Model process {record['pid']} did not exit")


def profile_from_args(args) -> dict:
    supplied = args.serve_args
    if supplied and supplied[0] == "--":
        supplied = supplied[1:]
    previous = json.loads(PROFILE.read_text()) if PROFILE.exists() else {}
    profile = {
        "python": args.python or previous.get("python"),
        "cwd": args.working_directory or previous.get("cwd"),
        "args": supplied or previous.get("args", []),
        "offline": args.offline if args.offline is not None else previous.get("offline", True),
        "instrument": args.instrument
        if args.instrument is not None
        else previous.get("instrument", True),
    }
    for key in ("python", "cwd"):
        if not profile[key]:
            raise ValueError(
                "First restart requires --python, --working-directory and -- MODEL ..."
            )
        profile[key] = str(Path(profile[key]).expanduser().absolute())
    if not os.access(profile["python"], os.X_OK) or not Path(profile["cwd"]).is_dir():
        raise ValueError("Model Python executable or working directory is unavailable")
    validate_arguments(profile["args"])
    return profile


def environment(profile: dict) -> dict[str, str]:
    return {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src") + os.pathsep + os.environ.get("PYTHONPATH", ""),
        "PATH": str(Path(profile["python"]).parent) + os.pathsep + os.environ.get("PATH", ""),
        "HF_HUB_OFFLINE": "1" if profile["offline"] else "0",
        "PYTORCH_ENABLE_MPS_FALLBACK": "0",
        "LLM_OBSERVE_INSTRUMENT": "1" if profile["instrument"] else "0",
    }


def restart(args) -> None:
    state = json.loads(manager.STATE.read_text())
    if not all(manager.healthy(url) for url in manager.endpoints(state).values()):
        raise RuntimeError("Monitoring must be healthy before restarting the model")
    profile = profile_from_args(args)
    origin = state["model_url"]
    run_id = uuid4().hex
    artifact = LOCAL / "artifacts" / f"restart-vllm-{run_id}"
    artifact.mkdir()
    preflight = subprocess.run(
        [profile["python"], "-m", "llm_observe.vllm_launch", "--check", *profile["args"]],
        cwd=profile["cwd"],
        env={**environment(profile), "LLM_OBSERVE_PREFLIGHT": "1"},
        capture_output=True,
        text=True,
        timeout=60,
    )
    (artifact / "preflight.log").write_text(preflight.stdout + preflight.stderr)
    if preflight.returncode:
        raise RuntimeError(f"Model preflight failed; old service left running; inspect {artifact}")
    current = listener(origin)
    old_records = []
    if current is not None:
        managed = json.loads(PROCESS.read_text()) if PROCESS.exists() else None
        if managed is not None:
            if managed["model_url"] != origin or managed["api"]["pid"] != current:
                raise RuntimeError(
                    "Listener differs from the managed model; explicit investigation required"
                )
            matches(managed["api"])
        elif args.adopt_pid != current:
            raise RuntimeError(
                "Unmanaged listener: supply its exact --adopt-pid to authorize replacement"
            )
        else:
            record = snapshot(current)
            if record is None or not re.search(
                r"(?:^|[/\s])vllm\s+serve(?:\s|$)", record["identity"]
            ):
                raise RuntimeError("Adoption target is not an identifiable vllm serve process")
        require_idle(origin)
        old_records = tree(current)
        write_json(artifact / "previous-processes.json", old_records)
        (artifact / "models-before.json").write_bytes(manager.get(origin + "/v1/models"))
    write_json(PROFILE, profile)
    if current is not None:
        print(f"Stopping verified vLLM PID {current}", flush=True)
        terminate(old_records, current)
    if listener(origin) is not None:
        raise RuntimeError("Model listener did not release the port; no replacement started")
    PROCESS.unlink(missing_ok=True)
    command = [profile["python"], "-m", "llm_observe.vllm_launch", *profile["args"]]
    log = LOCAL / "logs" / f"vllm-{run_id}.log"
    print(f"Starting vLLM with current tracing; log: {log}", flush=True)
    with log.open("ab") as output:
        child = subprocess.Popen(
            command,
            cwd=profile["cwd"],
            env={**environment(profile), "LLM_OBSERVE_RUN_ID": run_id},
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
    record = snapshot(child.pid)
    if record is None:
        raise RuntimeError(f"Model exited immediately; inspect {log}")
    process = {"api": record, "model_url": origin, "log": str(log), "run_id": run_id}
    write_json(PROCESS, process)
    deadline = time.monotonic() + args.timeout
    latest_records = [record]
    try:
        while time.monotonic() < deadline:
            latest_records = tree(child.pid) or latest_records
            if child.poll() is not None:
                raise RuntimeError(f"Model exited {child.returncode}; inspect {log}")
            if manager.healthy(origin + "/health"):
                if listener(origin) != child.pid:
                    raise RuntimeError("Health response came from another listener")
                (artifact / "models-after.json").write_bytes(manager.get(origin + "/v1/models"))
                process["api"] = next(p for p in latest_records if p["pid"] == child.pid)
                process["processes"] = latest_records
                write_json(PROCESS, process)
                write_json(artifact / "result.json", {"status": "ready", **process})
                print(
                    json.dumps(
                        {
                            "status": "ready",
                            "pid": child.pid,
                            "model_url": origin,
                            "otlp_http_port": state["ports"]["otlp_http"],
                            "artifact_dir": str(artifact),
                        },
                        indent=2,
                    )
                )
                return
            time.sleep(0.5)
        raise RuntimeError(f"Model readiness timed out; inspect {log}")
    except BaseException:
        terminate(latest_records, child.pid)
        child.wait(timeout=10)
        PROCESS.unlink(missing_ok=True)
        raise


def stop() -> None:
    if not PROCESS.exists():
        print("No managed model process; unmanaged listeners left untouched")
        return
    process = json.loads(PROCESS.read_text())
    if matches(process["api"]):
        require_idle(process["model_url"])
        terminate(tree(process["api"]["pid"]), process["api"]["pid"])
    PROCESS.unlink()
    print("Stopped managed vLLM; monitoring remains running")


def status() -> int:
    if not PROCESS.exists():
        print("No managed vLLM process")
        return 1
    process = json.loads(PROCESS.read_text())
    running = matches(process["api"])
    healthy = running and manager.healthy(process["model_url"] + "/health")
    print(
        json.dumps(
            {
                "pid": process["api"]["pid"],
                "running": running,
                "healthy": healthy,
                "model_url": process["model_url"],
                "log": process["log"],
            },
            indent=2,
        )
    )
    return 0 if healthy else 1
