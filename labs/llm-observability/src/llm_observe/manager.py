"""Own only processes started by this lab; never manage the inference server."""

import fcntl
import json
import os
import signal
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from string import Template
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener
from uuid import uuid4

import yaml

from llm_observe.downloads import binaries
from llm_observe.paths import LOCAL, ROOT, local_origin, write_json

STATE = LOCAL / "run" / "services.json"
PORTS = {
    "prometheus": 9090,
    "exporter": 9108,
    "jaeger_ui": 16686,
    "jaeger_query": 16685,
    "jaeger_metrics": 8888,
    "otlp_grpc": 4317,
    "otlp_http": 4318,
}


@contextmanager
def lock():
    with (LOCAL / "run" / "manager.lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("Another lifecycle/download command is running") from error
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def get(url: str) -> bytes:
    with build_opener(ProxyHandler({})).open(url, timeout=2) as response:
        return response.read()


def identity(pid: int) -> str | None:
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "stat=,lstart=,command="],
        capture_output=True,
        text=True,
        env={**os.environ, "LC_ALL": "C"},
        timeout=3,
    )
    if result.returncode == 1 or not result.stdout.strip():
        return None
    result.check_returncode()
    state, fingerprint = result.stdout.strip().split(None, 1)
    return None if state.startswith("Z") else fingerprint


def owned(record: dict) -> bool:
    actual = identity(record["pid"])
    if actual is None:
        return False
    if actual != record["identity"] or os.getpgid(record["pid"]) != record["pid"]:
        raise RuntimeError(f"PID {record['pid']} identity changed; refusing to signal it")
    return True


def render(model_url: str, offset: int) -> dict:
    model_url = local_origin(model_url)
    ports = {name: value + offset for name, value in PORTS.items()}
    if any(not 1 <= value <= 65535 for value in ports.values()):
        raise ValueError("Port offset is outside the allowed range")
    substitutions = {name.upper() + "_PORT": value for name, value in ports.items()}
    model = urlsplit(model_url)
    host = f"[{model.hostname}]" if model.hostname == "::1" else model.hostname
    substitutions["MODEL_TARGET"] = f"{host}:{model.port or 80}"
    for name in ("prometheus", "jaeger"):
        value = Template((ROOT / "config" / f"{name}.yml.in").read_text()).substitute(substitutions)
        yaml.safe_load(value)
        (LOCAL / "run" / f"{name}.yml").write_text(value)
    return {"model_url": model_url, "ports": ports}


def validate(executables: dict[str, str]) -> None:
    for command in (
        [executables["promtool"], "check", "config", str(LOCAL / "run" / "prometheus.yml")],
        [executables["jaeger"], "validate", "--config", str(LOCAL / "run" / "jaeger.yml")],
    ):
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        path = LOCAL / "logs" / f"validate-{Path(command[0]).name}.log"
        path.write_text(f"returncode={result.returncode}\n" + result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f"Native validation exited {result.returncode}; inspect {path}")


def halt(record: dict) -> None:
    if not owned(record):
        return
    os.kill(record["pid"], signal.SIGTERM)
    if wait_for_exit(record, 5):
        return
    if owned(record):
        os.kill(record["pid"], signal.SIGKILL)
    if wait_for_exit(record, 3):
        return
    raise RuntimeError(f"Owned process {record['pid']} did not exit")


def wait_for_exit(record: dict, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            running = owned(record)
        except RuntimeError:
            # ps can expose transitional command/state during exit. Wait without signaling;
            # the next signal still requires the full original identity to match.
            pass
        else:
            if not running:
                return True
        time.sleep(0.1)
    return False


def start(model_url: str, offset: int) -> None:
    if STATE.exists():
        state = json.loads(STATE.read_text())
        living = [name for name, record in state["processes"].items() if owned(record)]
        if living:
            if state["model_url"] != local_origin(model_url) or state["port_offset"] != offset:
                raise ValueError("Stack already running with different arguments; stop it first")
            if len(living) != 3 or status() != 0:
                raise RuntimeError("Partial/unhealthy stack; inspect logs, then stop/start")
            print("Stack already running; no duplicate processes started")
            return
    config = render(model_url, offset)
    for port in config["ports"].values():
        with socket.socket() as sock:
            # Match Go's listeners: allow restart after our closed connections enter TIME_WAIT.
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError as error:
                raise RuntimeError(f"Port {port} is occupied; no processes started") from error
    executables = binaries()
    validate(executables)
    ports = config["ports"]
    commands = {
        "jaeger": [executables["jaeger"], "--config", str(LOCAL / "run" / "jaeger.yml")],
        "exporter": [
            sys.executable,
            "-m",
            "llm_observe.exporter",
            "--port",
            str(ports["exporter"]),
            "--state-file",
            str(STATE),
        ],
        "prometheus": [
            executables["prometheus"],
            "--config.file=" + str(LOCAL / "run" / "prometheus.yml"),
            f"--web.listen-address=127.0.0.1:{ports['prometheus']}",
            "--storage.tsdb.path=" + str(LOCAL / "data" / "prometheus"),
            "--storage.tsdb.retention.time=48h",
            "--storage.tsdb.retention.size=512MB",
        ],
    }
    state = {**config, "port_offset": offset, "run_id": uuid4().hex, "processes": {}}
    write_json(STATE, state)
    children = []
    try:
        for name, command in commands.items():
            log = LOCAL / "logs" / f"{name}-{state['run_id']}.log"
            with log.open("ab") as output:
                child = subprocess.Popen(
                    command,
                    cwd=ROOT,
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                    env={**os.environ, "GOMEMLIMIT": "200MiB"},
                )
            children.append(child)
            fingerprint = identity(child.pid)
            if fingerprint is None:
                raise RuntimeError(f"{name} exited immediately; inspect {log}")
            state["processes"][name] = {
                "pid": child.pid,
                "identity": fingerprint,
                "log": str(log),
            }
            write_json(STATE, state)
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if any(child.poll() is not None for child in children):
                raise RuntimeError(f"A service exited; inspect {LOCAL / 'logs'}")
            if all(healthy(url) for url in endpoints(state).values()):
                status()
                return
            time.sleep(0.25)
        raise RuntimeError(f"Readiness timed out; inspect {LOCAL / 'logs'}")
    except BaseException:
        # Roll back only this invocation's children, never a pre-existing model server.
        for child in reversed(children):
            record = next((p for p in state["processes"].values() if p["pid"] == child.pid), None)
            if record is not None:
                halt(record)
            elif child.poll() is None:
                child.terminate()
            child.wait(timeout=10)
        STATE.unlink(missing_ok=True)
        raise


def endpoints(state: dict) -> dict[str, str]:
    ports = state["ports"]
    return {
        "jaeger": f"http://127.0.0.1:{ports['jaeger_ui']}/",
        "exporter": f"http://127.0.0.1:{ports['exporter']}/healthz",
        "prometheus": f"http://127.0.0.1:{ports['prometheus']}/-/ready",
    }


def healthy(url: str) -> bool:
    try:
        get(url)
        return True
    except (URLError, TimeoutError):
        return False


def status() -> int:
    if not STATE.exists():
        print("Stack stopped (no lab-owned PID records)")
        return 1
    state = json.loads(STATE.read_text())
    statuses = {}
    for name, url in endpoints(state).items():
        record = state["processes"].get(name)
        statuses[name] = {
            "pid": record["pid"] if record else None,
            "owned_and_running": bool(record and owned(record)),
            "healthy": bool(record and healthy(url)),
            "url": url,
        }
    print(json.dumps({"services": statuses, "model_server_managed": False}, indent=2))
    return 0 if all(v["owned_and_running"] and v["healthy"] for v in statuses.values()) else 1


def stop() -> None:
    if not STATE.exists():
        print("Already stopped; no model server touched")
        return
    state = json.loads(STATE.read_text())
    for name in ("prometheus", "exporter", "jaeger"):
        if name in state["processes"]:
            halt(state["processes"][name])
    STATE.unlink()
    print("Stopped lab-owned monitoring processes; retained data/logs; model server untouched")


def check() -> None:
    from llm_observe.safegit import check_git

    check_git()
    if not (LOCAL / "run" / "prometheus.yml").exists():
        render("http://127.0.0.1:8000", 0)
    validate(binaries())
    print("Native Prometheus/Jaeger configuration and Git runtime exclusions passed")
