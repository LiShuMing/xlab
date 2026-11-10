"""Cached host probes: a scrape never launches subprocesses."""

import argparse
import json
import os
import re
import signal
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily


def parse_vm(text: str) -> dict[str, float]:
    page_match = re.search(r"page size of (\d+) bytes", text)
    if not page_match:
        raise ValueError("vm_stat did not expose page size")
    page = int(page_match[1])
    values = {m[1].strip(): int(m[2]) for m in re.finditer(r"^([^:\n]+):\s+(\d+)\.", text, re.M)}
    return {
        "swapin_bytes_total": values["Swapins"] * page,
        "swapout_bytes_total": values["Swapouts"] * page,
        "compressor_bytes": values["Pages occupied by compressor"] * page,
        "wired_bytes": values["Pages wired down"] * page,
        "free_bytes": values["Pages free"] * page,
        "page_size_bytes": page,
    }


def parse_gpu(text: str) -> dict[str, float]:
    value = re.search(r'"Device Utilization %"\s*=\s*(\d+)', text)
    if value is None or not 0 <= int(value[1]) <= 100:
        raise ValueError("Device GPU utilization is unavailable")
    return {"gpu_device_utilization_ratio": int(value[1]) / 100}


def parse_cpu(text: str) -> dict[str, float]:
    value = re.search(r"CPU usage:\s+([\d.]+)% user,\s+([\d.]+)% sys,\s+([\d.]+)% idle", text)
    if value is None:
        raise ValueError("System CPU utilization is unavailable")
    return {
        f"cpu_{name}_ratio": float(number) / 100
        for name, number in zip(("user", "system", "idle"), value.groups(), strict=True)
    }


def cpu_seconds(value: str) -> float:
    parts = value.split(":")
    if len(parts) not in {2, 3}:
        raise ValueError("Unexpected ps CPU time format")
    result = float(parts[-1]) + 60 * int(parts[-2])
    if len(parts) == 3:
        result += 3600 * int(parts[0])
    return result


def command(arguments: list[str]) -> str:
    return subprocess.run(arguments, capture_output=True, text=True, check=True, timeout=3).stdout


class HostCollector:
    def __init__(self, interval: float = 1, state_file: Path | None = None) -> None:
        self.interval = interval
        self.state_file = state_file
        self.stop = threading.Event()
        self.mutex = threading.Lock()
        self.probes: dict[str, dict] = {}
        self.thread = threading.Thread(target=self.sample, daemon=True)

    def probe(self, name: str, function) -> None:
        started = time.monotonic()
        with self.mutex:
            previous = self.probes.get(name, {})
        try:
            values = function()
        except (OSError, ValueError, KeyError, subprocess.SubprocessError):
            record = {"success": 0, "last_success": previous.get("last_success", 0), "values": {}}
        else:
            record = {"success": 1, "last_success": time.time(), "values": values}
        record["duration"] = time.monotonic() - started
        with self.mutex:
            self.probes[name] = record

    def vm(self) -> dict[str, float]:
        if os.uname().sysname == "Darwin":
            return parse_vm(command(["vm_stat"]))
        values = dict(line.split() for line in Path("/proc/vmstat").read_text().splitlines())
        page = os.sysconf("SC_PAGE_SIZE")
        memory = {
            m[1]: int(m[2]) * 1024
            for m in re.finditer(r"^(\w+):\s+(\d+) kB", Path("/proc/meminfo").read_text(), re.M)
        }
        return {
            "swapin_bytes_total": int(values["pswpin"]) * page,
            "swapout_bytes_total": int(values["pswpout"]) * page,
            "free_bytes": memory["MemFree"],
            "available_bytes": memory["MemAvailable"],
            "page_size_bytes": page,
        }

    def processes(self) -> dict:
        roles = {os.getpid(): "exporter"}
        if self.state_file is not None and self.state_file.exists():
            state = json.loads(self.state_file.read_text())
            roles.update({int(p["pid"]): name for name, p in state["processes"].items()})
        values = {}
        for line in command(["ps", "-axo", "pid=,ppid=,time=,rss=,comm="]).splitlines():
            pid, _, cpu, rss, name = line.strip().split(None, 4)
            role = roles.get(int(pid))
            if role is None and name.startswith("VLLM::EngineCore"):
                role = "vllm_engine_candidate"
            if role:
                # Fixed roles only; never put command lines or arbitrary PID lists into labels.
                cpu_key, rss_key = (
                    ("process_cpu_seconds_total", role),
                    ("process_resident_bytes", role),
                )
                values[cpu_key] = values.get(cpu_key, 0) + cpu_seconds(cpu)
                values[rss_key] = values.get(rss_key, 0) + int(rss) * 1024
        return values

    def system(self) -> dict[str, float]:
        values = {"load1": os.getloadavg()[0]}
        if os.uname().sysname == "Darwin":
            values.update(parse_cpu(command(["top", "-l", "1", "-n", "0"])))
            swap = re.search(r"used\s*=\s*([\d.]+)M", command(["sysctl", "vm.swapusage"]))
            pressure = re.search(r"free percentage:\s*(\d+)%", command(["memory_pressure", "-Q"]))
            if swap is None or pressure is None:
                raise ValueError("System swap/pressure measurement unavailable")
            values["swap_used_bytes"] = float(swap[1]) * 1024 * 1024
            values["memory_pressure_free_ratio"] = int(pressure[1]) / 100
        return values

    def sample(self) -> None:
        cycle = 0
        while not self.stop.is_set():
            self.probe("vm_stat", self.vm)
            self.probe(
                "ioreg",
                lambda: parse_gpu(command(["ioreg", "-r", "-c", "AGXAccelerator", "-d", "1"])),
            )
            if cycle % 5 == 0:
                self.probe("process", self.processes)
                self.probe("system", self.system)
            cycle += 1
            self.stop.wait(self.interval)

    def collect(self):
        with self.mutex:
            probes = {name: dict(record) for name, record in self.probes.items()}
        for field in ("success", "last_success", "duration"):
            suffix = {
                "success": "success",
                "last_success": "last_success_timestamp_seconds",
                "duration": "duration_seconds",
            }[field]
            metric = GaugeMetricFamily(
                f"metal_host_probe_{suffix}", f"Host probe {field}", labels=["probe"]
            )
            for name, record in probes.items():
                metric.add_metric([name], record[field])
            yield metric
        process_metrics = {}
        for record in probes.values():
            for key, value in record["values"].items():
                if isinstance(key, tuple):
                    name, role = key
                    if name not in process_metrics:
                        constructor = (
                            CounterMetricFamily if name.endswith("_total") else GaugeMetricFamily
                        )
                        process_metrics[name] = constructor(
                            f"metal_host_{name}", name, labels=["role"]
                        )
                    process_metrics[name].add_metric([role], value)
                else:
                    constructor = (
                        CounterMetricFamily if key.endswith("_total") else GaugeMetricFamily
                    )
                    yield constructor(f"metal_host_{key}", key, value=value)
        yield from process_metrics.values()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--state-file", type=Path)
    args = parser.parse_args()
    collector = HostCollector(state_file=args.state_file)
    REGISTRY.register(collector)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/healthz":
                with collector.mutex:
                    vm = collector.probes.get("vm_stat", {})
                healthy = vm.get("success") == 1 and time.time() - vm["last_success"] < 5
                payload, content = b"ok\n" if healthy else b"not ready\n", "text/plain"
                self.send_response(200 if healthy else 503)
            elif self.path == "/metrics":
                payload, content = generate_latest(REGISTRY), CONTENT_TYPE_LATEST
                self.send_response(200)
            else:
                self.send_error(404)
                return
            self.send_header("Content-Type", content)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_args) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.timeout = 0.5
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: collector.stop.set())
    collector.thread.start()
    try:
        while not collector.stop.is_set():
            server.handle_request()
    finally:
        server.server_close()
        collector.stop.set()
        collector.thread.join(timeout=10)


if __name__ == "__main__":
    main()
