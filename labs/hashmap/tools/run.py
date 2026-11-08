"""Build, verify, measure and report local hashmap experiments without network access."""

import argparse
import csv
from datetime import datetime, timezone, timedelta
import hashlib
import io
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


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_command(command, cwd=None):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=20)
    return result.stdout.strip() if result.returncode == 0 else None


def matrix(config, perfect):
    jobs = []
    for case, hit, distribution, seed in itertools.product(
        config["fixed_cases"], config["hits"], config["distributions"], config["seeds"]
    ):
        methods = ["std", "linear", "sorted"] + (["perfect"] if perfect else [])
        if perfect and case in ("short8", "short64"):
            methods.append("wide")
        for method in methods:
            jobs.append(
                dict(
                    case=case,
                    hit=hit,
                    distribution=distribution,
                    seed=seed,
                    method=method,
                    load=0.75,
                    mode="lookup",
                    n=4096,
                )
            )
    # A power-of-two table would round small fixed N to the same capacity for many
    # target loads. Hold 8192 slots fixed and vary N to exercise actual occupancy.
    for load, hit, seed, method in itertools.product(
        config["load_sweep"], [0, 100], config["seeds"], ["std", "linear"]
    ):
        jobs.append(
            dict(
                case="uint64",
                hit=hit,
                distribution="uniform",
                seed=seed,
                method=method,
                load=load,
                mode="lookup",
                n=int(8192 * load),
            )
        )
    for (case, count), mode, seed, method in itertools.product(
        config["dynamic"],
        ["lookup", "build-reserved", "build-growing", "churn"],
        config["seeds"],
        ["std", "linear"],
    ):
        jobs.append(
            dict(
                case=case,
                n=count,
                hit=50,
                distribution="uniform",
                seed=seed,
                method=method,
                load=0.75,
                mode=mode,
            )
        )
    # Interleave competitors deterministically instead of running every baseline first.
    random.Random(20261108).shuffle(jobs)
    return jobs


def save_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    temporary.replace(path)


def run_checked(command, output, timeout):
    with output.open("w") as handle:
        subprocess.run(
            command, cwd=LAB, stdout=handle, stderr=subprocess.STDOUT, timeout=timeout, check=True
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("quick", "standard"), default="standard")
    parser.add_argument("--perfect-hash-root", type=Path)
    parser.add_argument("--compiler", default=os.environ.get("CXX", "c++"))
    parser.add_argument("--cxx-flags", default="")
    parser.add_argument("--linker-flags", default="")
    parser.add_argument("--build-dir", type=Path, default=LAB / ".local/build")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--clean-build", action="store_true")
    args = parser.parse_args()
    if (
        args.perfect_hash_root
        and not (args.perfect_hash_root / "singleheader/perfect_hash.h").is_file()
    ):
        parser.error("perfect-hash-root must contain singleheader/perfect_hash.h")
    compiler = shutil.which(args.compiler)
    if compiler is None:
        parser.error("compiler not found")
    config_path = LAB / "cases" / f"{args.suite}.json"
    config = json.loads(config_path.read_text())
    jobs = matrix(config, bool(args.perfect_hash_root))
    stamp = datetime.now(TZ).strftime("%Y%m%d-%H%M%S-%f")
    output = (args.output or LAB / ".local/results" / stamp).resolve()
    output.mkdir(parents=True, exist_ok=False)
    build = args.build_dir.resolve()
    if build == LAB or LAB in build.parents and ".local" not in build.parts:
        parser.error("build-dir inside source must be under .local")
    manifest = dict(
        schema_version=1,
        generator="20261108-v1",
        suite=args.suite,
        started_at=datetime.now(TZ).isoformat(),
        status="preparing",
        compiler=text_command([compiler, "--version"]),
        compiler_path=compiler,
        host=dict(system=platform.system(), machine=platform.machine(), release=platform.release()),
        config=config,
        config_sha256=sha256(config_path),
        git_head=text_command(["git", "rev-parse", "HEAD"], LAB),
        lab_status=text_command(["git", "status", "--short", "--", "labs/hashmap"], LAB),
        source_sha256={},
        jobs=[],
        failed_jobs=0,
        hardware_counters="not collected; no privileged operations",
        limitations=[
            "shared host",
            "warm independent-query throughput",
            "batch sample ranges are not operation percentiles",
            "memory excludes allocator overhead and shared literals",
        ],
    )
    for directory in ("maps", "bench", "tools", "tests", "cases", "assets"):
        for path in sorted((LAB / directory).iterdir()):
            if path.is_file():
                manifest["source_sha256"][str(path.relative_to(LAB))] = sha256(path)
    for name in ("CMakeLists.txt", "Makefile", "README.md"):
        if (LAB / name).is_file():
            manifest["source_sha256"][name] = sha256(LAB / name)
    if args.perfect_hash_root:
        root = args.perfect_hash_root.resolve()
        manifest["perfect_hash"] = dict(
            path=str(root),
            revision=text_command(["git", "rev-parse", "HEAD"], root),
            status=text_command(["git", "status", "--short"], root),
            header_sha256=sha256(root / "singleheader/perfect_hash.h"),
        )
    else:
        manifest["perfect_hash"] = {"status": "not requested; excluded from matrix"}

    def event(stage, **fields):
        entry = dict(time=datetime.now(TZ).isoformat(), stage=stage, **fields)
        with (output / "events.jsonl").open("a") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        save_json(output / "progress.json", entry)
        print(json.dumps(entry, ensure_ascii=False), flush=True)

    try:
        configure = [
            "cmake",
            "-S",
            str(LAB),
            "-B",
            str(build),
            "-DCMAKE_BUILD_TYPE=Release",
            f"-DCMAKE_CXX_COMPILER={compiler}",
            f"-DCMAKE_CXX_FLAGS={args.cxx_flags}",
            f"-DCMAKE_EXE_LINKER_FLAGS={args.linker_flags}",
            f"-DPERFECT_HASH_ROOT={args.perfect_hash_root.resolve() if args.perfect_hash_root else ''}",
        ]
        manifest["configure_command"] = configure
        event("configure", directory=str(output))
        run_checked(configure, output / "configure.log", 60)
        command = ["cmake", "--build", str(build), "--parallel", "2"]
        if args.clean_build:
            command.append("--clean-first")
        manifest["build_command"] = command
        event("build")
        started = time.monotonic()
        if Path("/usr/bin/time").is_file():
            timed = [
                "/usr/bin/time",
                "-f",
                "%e,%M",
                "-o",
                str(output / "build-resources.txt"),
                *command,
            ]
        else:
            timed = command
        run_checked(timed, output / "build.log", 600)
        manifest["build"] = dict(
            wall_seconds=round(time.monotonic() - started, 4),
            kind="clean" if args.clean_build else "incremental",
            peak_rss_kib=None,
        )
        if (output / "build-resources.txt").is_file():
            wall, rss = (output / "build-resources.txt").read_text().strip().split(",")
            manifest["build"].update(wall_seconds=float(wall), peak_rss_kib=int(rss))
        binary = build / "hashmap_bench"
        manifest["binary"] = dict(
            path=str(binary),
            sha256=sha256(binary),
            bytes=binary.stat().st_size,
            sections=text_command(["size", str(binary)]) if shutil.which("size") else None,
        )
        manifest["effective_compile_flags"] = (
            build / "CMakeFiles/hashmap_bench.dir/flags.make"
        ).read_text()
        manifest["effective_link_command"] = (
            build / "CMakeFiles/hashmap_bench.dir/link.txt"
        ).read_text()
        event("correctness")
        run_checked(
            [
                "ctest",
                "--test-dir",
                str(build),
                "--output-on-failure",
                "--no-tests=error",
                "--timeout",
                "60",
            ],
            output / "tests.log",
            180,
        )
        manifest["correctness"] = (
            "passed (see tests.log); each job also verifies contents and queries"
        )
        allowed = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else []
        selected = args.cpu if args.cpu is not None else (allowed[0] if allowed else None)
        if selected is not None and selected not in allowed:
            raise ValueError("requested CPU is outside current affinity")
        if selected is not None:
            os.sched_setaffinity(0, {selected})
        cpu = dict(
            selected=selected,
            allowed_before=allowed,
            model=None,
            governor=None,
            load_before=os.getloadavg() if hasattr(os, "getloadavg") else None,
        )
        if Path("/proc/cpuinfo").is_file():
            cpu["model"] = next(
                (
                    line.split(":", 1)[1].strip()
                    for line in Path("/proc/cpuinfo").read_text().splitlines()
                    if line.startswith("model name")
                ),
                None,
            )
        governor = Path(f"/sys/devices/system/cpu/cpu{selected}/cpufreq/scaling_governor")
        if governor.is_file():
            cpu["governor"] = governor.read_text().strip()
        manifest["cpu"] = cpu
        manifest["status"] = "running"
        save_json(output / "manifest.json", manifest)
        seen = {}
        with (output / "samples.csv").open("w", newline="") as handle:
            writer = None
            for index, job in enumerate(jobs):
                command = [str(binary)]
                for key, value in job.items():
                    command.extend(["--" + key, str(value)])
                command.extend(
                    ["--repeat", str(config["repeats"]), "--batch-ms", str(config["batch_ms"])]
                )
                result = subprocess.run(
                    command, cwd=LAB, capture_output=True, text=True, timeout=60
                )
                if result.returncode:
                    manifest["failed_jobs"] += 1
                    raise RuntimeError(f"job {index} failed: {result.stderr.strip()}")
                reader = csv.DictReader(io.StringIO(result.stdout))
                samples = list(reader)
                if len(samples) != config["repeats"]:
                    raise ValueError("sample count mismatch")
                for sample in samples:
                    identity = tuple(
                        sample[field]
                        for field in (
                            "mode",
                            "case_name",
                            "n",
                            "hit",
                            "distribution",
                            "target_load",
                            "seed",
                        )
                    )
                    previous = seen.setdefault(identity, sample["trace_hash"])
                    if previous != sample["trace_hash"]:
                        raise ValueError("competitors received different input traces")
                    if writer is None:
                        writer = csv.DictWriter(handle, fieldnames=reader.fieldnames)
                        writer.writeheader()
                    writer.writerow(sample)
                handle.flush()
                manifest["jobs"].append(
                    dict(
                        index=index,
                        parameters=job,
                        status="passed",
                        samples=len(samples),
                        trace_hash=samples[0]["trace_hash"],
                    )
                )
                if index % 20 == 0 or index + 1 == len(jobs):
                    event("measure", completed=index + 1, total=len(jobs), last=job)
                    save_json(output / "manifest.json", manifest)
        cpu["load_after"] = os.getloadavg() if hasattr(os, "getloadavg") else None
        manifest.update(status="completed", completed_at=datetime.now(TZ).isoformat())
        save_json(output / "manifest.json", manifest)
        report = generate(output)
        event("completed", report=str(report), samples=len(jobs) * config["repeats"])
        print(f"REPORT={report}", flush=True)
    except Exception as error:
        manifest.update(status="failed", error=str(error))
        save_json(output / "manifest.json", manifest)
        event("failed", error=str(error))
        raise


if __name__ == "__main__":
    main()
