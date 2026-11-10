"""Build, check and replay deterministic cache workloads; no network at runtime."""

import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import random
import shutil
import subprocess
import time

from report import generate

LAB = Path(__file__).resolve().parents[1]
TZ = timezone(timedelta(hours=8))
ALGORITHMS = ["fifo", "lru", "lfu", "slru", "wtinylfu", "arc"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text(command: list[str], cwd: Path) -> str | None:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=20)
    return result.stdout.strip() if result.returncode == 0 else None


def matrix(config: dict) -> list[dict]:
    jobs = []
    for workload, capacity, seed, algorithm in itertools.product(
        config["workloads"],
        config["capacities"],
        config["seeds"],
        ALGORITHMS + ["reference-lru"],
    ):
        jobs.append(
            dict(
                workload=workload,
                capacity=capacity,
                seed=seed,
                algorithm=algorithm,
                window_percent=1,
                protected_percent=80,
                aging_factor=10,
            )
        )
    if config["sensitivity"]:
        variants = [
            dict(algorithm="wtinylfu", window_percent=10),
            dict(algorithm="wtinylfu", window_percent=20),
            dict(algorithm="wtinylfu", aging_factor=2),
            dict(algorithm="wtinylfu", aging_factor=40),
            dict(algorithm="slru", protected_percent=50),
            dict(algorithm="slru", protected_percent=90),
        ]
        for workload, seed, variant in itertools.product(
            ["hot_shift", "recency_bursts"], config["seeds"], variants
        ):
            job = dict(
                workload=workload,
                capacity=512,
                seed=seed,
                algorithm="wtinylfu",
                window_percent=1,
                protected_percent=80,
                aging_factor=10,
            )
            job.update(variant)
            jobs.append(job)
    random.Random(20261108).shuffle(jobs)
    return jobs


def save(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def checked(command: list[str], log: Path, timeout: int) -> None:
    with log.open("w") as handle:
        subprocess.run(
            command, cwd=LAB, stdout=handle, stderr=subprocess.STDOUT, timeout=timeout, check=True
        )


def validate(job: dict, config: dict) -> None:
    count = job["count"]
    assert count == config["count"] and len(job["samples"]) == config["repeats"]
    windows = job["windows"]
    assert sum(w["end"] - w["begin"] for w in windows) == count
    assert sum(w["hits"] for w in windows) == job["hits"]
    assert job["latency"]["all"]["count"] == count
    for latency in [*job["latency"].values(), *job["phase_latency"], job["clock_floor"]]:
        assert sum(latency["histogram"]) == latency["count"]
        if latency["count"]:
            assert latency["p50"] <= latency["p95"] <= latency["p99"] <= latency["maximum"]
        else:
            assert all(latency[key] is None for key in ("p50", "p95", "p99", "maximum"))
    admitted, evicted = 0, 0
    for w in windows:
        assert w["points"] + w["scans"] == w["end"] - w["begin"]
        assert w["point_hits"] + w["scan_hits"] == w["hits"]
        assert w["hits"] <= w["end"] - w["begin"]
        assert w["point_hits"] <= w["points"] and w["scan_hits"] <= w["scans"]
        assert w["layout"]["resident"] <= job["capacity"]
        assert w["layout"]["history"] <= job["capacity"]
        admitted += w["events"]["admissions"]
        evicted += w["events"]["evictions"]
        assert admitted - evicted == w["layout"]["resident"]
    for s in job["samples"]:
        assert s["operations"] % count == 0 and s["elapsed_ns"] > 0 and s["cpu_ns"] > 0
        passes = s["operations"] // count
        assert s["hits"] == job["hits"] * passes
        assert int(s["hit_digest"]) == (int(job["hit_digest"]) * passes) % (1 << 64)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=["quick", "standard"], default="standard")
    parser.add_argument("--compiler", default=os.environ.get("CXX", "c++"))
    parser.add_argument("--cxx-flags", default="")
    parser.add_argument("--linker-flags", default="")
    parser.add_argument("--build-dir", type=Path, default=LAB / ".local/build")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cpu", type=int)
    args = parser.parse_args()
    compiler = shutil.which(args.compiler)
    if not compiler:
        parser.error("compiler not found")
    build = args.build_dir.resolve()
    if build == LAB or LAB in build.parents and ".local" not in build.parts:
        parser.error("source-tree build must be under .local")
    config = json.loads((LAB / "cases.json").read_text())[args.suite]
    jobs = matrix(config)
    output = (
        args.output or LAB / ".local/results" / datetime.now(TZ).strftime("%Y%m%d-%H%M%S-%f")
    ).resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = dict(
        schema=1,
        status="preparing",
        suite=args.suite,
        started_at=datetime.now(TZ).isoformat(),
        config=config,
        total_jobs=len(jobs),
        completed_jobs=0,
        failed_jobs=0,
        compiler=text([compiler, "--version"], LAB),
        git_head=text(["git", "rev-parse", "HEAD"], LAB),
        lab_status=text(["git", "status", "--short", "--", "."], LAB),
        host=dict(system=platform.system(), machine=platform.machine(), release=platform.release()),
        source_sha256={},
        reference=dict(
            kind="in-repo",
            path="reference_lru.h",
            upstream="https://github.com/M4cr0Chen/CacheSystem",
            note="independent implementation of the upstream structure; no upstream file is read",
        ),
        limitations=[
            "single-thread shared host; no I/O, TTL, writes, pinning or variable-size blocks",
            "equal resident entry budgets; ghost/sketch metadata is additional",
            "policy latency is clock-instrumented; throughput includes full lifecycle",
            "payload budget models 4KiB blocks but does not allocate block payloads",
            "no database runtime or production causality evidence",
        ],
    )
    for directory in (LAB, LAB / "tools", LAB / "tests", LAB / "assets"):
        for path in sorted(directory.iterdir()):
            if path.is_file():
                manifest["source_sha256"][str(path.relative_to(LAB))] = sha256(path)

    def event(stage: str, **values: object) -> None:
        entry = dict(time=datetime.now(TZ).isoformat(), stage=stage, **values)
        with (output / "events.jsonl").open("a") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        save(output / "progress.json", entry)
        print(json.dumps(entry, ensure_ascii=False), flush=True)

    try:
        command = [
            "cmake",
            "-S",
            str(LAB),
            "-B",
            str(build),
            "-DCMAKE_BUILD_TYPE=Release",
            "-DCACHE_SANITIZE=OFF",
            f"-DCMAKE_CXX_COMPILER={compiler}",
            f"-DCMAKE_CXX_FLAGS={args.cxx_flags}",
            f"-DCMAKE_EXE_LINKER_FLAGS={args.linker_flags}",
        ]
        manifest["configure_command"] = command
        event("configure", directory=str(output))
        checked(command, output / "configure.log", 60)
        manifest["build_command"] = [
            "cmake",
            "--build",
            str(build),
            "--parallel",
            "2",
            "--clean-first",
        ]
        event("build")
        start = time.monotonic()
        checked(manifest["build_command"], output / "build.log", 300)
        manifest["build_seconds"] = time.monotonic() - start
        binary = build / "cache_bench"
        manifest["binary"] = dict(
            path=str(binary), sha256=sha256(binary), bytes=binary.stat().st_size
        )
        manifest["compile_flags"] = (build / "CMakeFiles/cache_bench.dir/flags.make").read_text()
        manifest["link_command"] = (build / "CMakeFiles/cache_bench.dir/link.txt").read_text()
        event("correctness")
        checked(
            [
                "ctest",
                "--test-dir",
                str(build),
                "--output-on-failure",
                "--verbose",
                "--no-tests=error",
                "--timeout",
                "120",
            ],
            output / "tests.log",
            240,
        )
        manifest["correctness"] = "passed; see tests.log; every timed pass checks replay hit digest"
        allowed = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else []
        cpu = args.cpu if args.cpu is not None else (allowed[0] if allowed else None)
        if cpu is not None:
            if cpu not in allowed:
                raise ValueError("CPU is outside current affinity")
            os.sched_setaffinity(0, {cpu})
        manifest["cpu"] = dict(selected=cpu, allowed=allowed, load_before=os.getloadavg())
        if Path("/proc/cpuinfo").is_file():
            manifest["cpu"]["model"] = next(
                (
                    line.split(":", 1)[1].strip()
                    for line in Path("/proc/cpuinfo").read_text().splitlines()
                    if line.startswith("model name")
                ),
                None,
            )
        governor = Path(f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor")
        manifest["cpu"]["governor"] = governor.read_text().strip() if governor.is_file() else None
        manifest["status"] = "running"
        save(output / "manifest.json", manifest)
        seen, lru_digests = {}, {}
        all_results = []
        with (output / "jobs.jsonl").open("w") as raw:
            for index, parameters in enumerate(jobs):
                command = [str(binary)]
                for key, value in dict(
                    parameters,
                    count=config["count"],
                    window_size=config["window_size"],
                    repeats=config["repeats"],
                    batch_ms=config["batch_ms"],
                ).items():
                    command.extend(["--" + key.replace("_", "-"), str(value)])
                result = subprocess.run(
                    command, capture_output=True, text=True, timeout=90, cwd=LAB
                )
                if result.returncode:
                    raise RuntimeError(f"job {index} failed: {result.stderr.strip()}")
                job = json.loads(result.stdout)
                validate(job, config)
                key = (job["workload"], job["seed"], job["count"])
                if seen.setdefault(key, job["trace_hash"]) != job["trace_hash"]:
                    raise ValueError("input traces differ")
                if job["algorithm"] in ("lru", "reference-lru"):
                    identity = key + (job["capacity"],)
                    if lru_digests.setdefault(identity, job["hit_digest"]) != job["hit_digest"]:
                        raise ValueError("reference LRU semantics differ")
                raw.write(json.dumps(job, separators=(",", ":")) + "\n")
                raw.flush()
                all_results.append(job)
                manifest["completed_jobs"] = index + 1
                if index % 20 == 0 or index + 1 == len(jobs):
                    event("measure", completed=index + 1, total=len(jobs), last=parameters)
                    save(output / "manifest.json", manifest)
        for name in ("samples", "windows"):
            records = []
            for job in all_results:
                identity = {
                    key: job[key]
                    for key in (
                        "algorithm",
                        "workload",
                        "capacity",
                        "count",
                        "seed",
                        "window_percent",
                        "protected_percent",
                        "aging_factor",
                        "trace_hash",
                    )
                }
                for entry in job[name]:
                    row = dict(identity)
                    for key, value in entry.items():
                        if isinstance(value, dict):
                            row.update(
                                {f"{key}_{field}": number for field, number in value.items()}
                            )
                        else:
                            row[key] = value
                    records.append(row)
            with (output / f"{name}.csv").open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=records[0].keys())
                writer.writeheader()
                writer.writerows(records)
        manifest.update(
            status="completed",
            completed_at=datetime.now(TZ).isoformat(),
            sample_count=len(jobs) * config["repeats"],
        )
        for name, digest in manifest["source_sha256"].items():
            if sha256(LAB / name) != digest:
                raise ValueError(f"source changed during measurement: {name}")
        manifest["cpu"]["load_after"] = os.getloadavg()
        save(output / "manifest.json", manifest)
        report = generate(output, manifest, all_results)
        event("completed", report=str(report), samples=manifest["sample_count"])
        print("REPORT=" + str(report), flush=True)
    except Exception as error:
        manifest.update(status="failed", failed_jobs=1, error=str(error))
        save(output / "manifest.json", manifest)
        event("failed", error=str(error))
        raise


if __name__ == "__main__":
    main()
