#!/usr/bin/env python3
"""Generate data and run isolated, auditable Daft learning experiments."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import signal
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from bootstrap import verify_ready

ROOT = Path(__file__).resolve().parent
LOCAL = ROOT / ".local"
MATRIX = {
    "plan": [("filter-first", 1024), ("udf-first", 1024)],
    "compute": [("builtin", 1024), ("row", 1024), ("batch", 1024)],
    "batch": [("batch-64", 64), ("batch-1024", 1024), ("batch-16384", 16384)],
    "state": [("stateless-thread", 1024), ("stateful-thread", 1024), ("stateful-process", 1024)],
    "errors": [("intentional-udf-error", 1024)],
}


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def doctor(display: bool = True) -> dict:
    verify_ready(LOCAL / "rootfs", ROOT / "image.lock.json")
    import daft

    information = {
        "python": sys.version,
        "executable": sys.executable,
        "libc": platform.libc_ver(),
        "machine": platform.machine(),
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "versions": {
            name: importlib.metadata.version(name)
            for name in ["daft", "pyarrow", "numpy", "psutil"]
        },
        "daft_import": daft.__file__,
        "runtime_kind": "released-wheel",
        "source_reference": json.loads((ROOT / "source-reference.json").read_text()),
        "source_reference_is_runtime_build": False,
        "image": json.loads((ROOT / "image.lock.json").read_text()),
        "lock_sha256": digest(ROOT / "uv.lock"),
    }
    assert information["versions"]["daft"] == "0.7.26"
    assert hasattr(daft, "func") and hasattr(daft, "cls")
    if display:
        print(json.dumps(information, indent=2))
    return information


def generate(rows: int, files: int, skew: bool) -> None:
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq

    if rows < 0 or not 1 <= files <= 128 or rows > 10_000_000:
        raise SystemExit("Require 0 <= rows <= 10000000 and 1 <= files <= 128")
    directory = LOCAL / "data"
    directory.mkdir(parents=True, exist_ok=True)
    # Only replace this generator's exact owned files, never arbitrary user data.
    old_manifest = directory / "manifest.json"
    if old_manifest.is_symlink():
        raise SystemExit("Generated manifest is a symlink; preserve and inspect it")
    if old_manifest.exists():
        previous = json.loads(old_manifest.read_text())
        owned_names = {record["name"] for record in previous["files"]}
        for existing in directory.glob("part-*.parquet"):
            if existing.is_symlink() or existing.name not in owned_names:
                raise SystemExit(f"Unowned partition or symlink; preserve and inspect it: {existing}")
        for record in previous["files"]:
            owned = directory / record["name"]
            if owned.parent != directory or not owned.name.startswith("part-"):
                raise ValueError("Unexpected file in generated-data manifest")
            if not owned.exists() or digest(owned) != record["sha256"]:
                raise SystemExit(f"Generated file changed; preserve and inspect it: {owned}")
        for record in previous["files"]:
            (directory / record["name"]).unlink()
    elif any(directory.glob("part-*.parquet")):
        raise SystemExit("Unowned Parquet files exist; refusing to replace them")
    records = []
    width = max(1, (rows + files - 1) // files)
    for index, start in enumerate(range(0, max(rows, 1), width)):
        ids = np.arange(start, min(start + width, rows), dtype=np.int64)
        groups = ids % 32
        if skew:
            groups = np.where(ids % 10 != 0, 0, groups)
        table = pa.table({"id": ids, "group": groups, "x": ids % 97})
        path = directory / f"part-{index:04d}.parquet"
        # Exclusive creation also refuses a newly appeared file or symlink.
        with path.open("xb") as output:
            pq.write_table(table, output, row_group_size=8192)
        records.append({"name": path.name, "rows": len(ids), "sha256": digest(path)})
    manifest = {
        "schema_version": 1,
        "rows": rows,
        "skew": skew,
        "generator": "id=arange(rows); x=id%97; group=id%32",
        "files": records,
    }
    old_manifest.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


def run(case: str, mode: str, repeats: int) -> None:
    manifest_path = LOCAL / "data/manifest.json"
    if not manifest_path.exists():
        raise SystemExit("Generate input first: python lab.py generate")
    manifest = json.loads(manifest_path.read_text())
    for record in manifest["files"]:
        if digest(LOCAL / "data" / record["name"]) != record["sha256"]:
            raise SystemExit("Input differs from its generated manifest")
    identifier = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    directory = LOCAL / "runs" / identifier
    directory.mkdir(parents=True)
    environment = doctor(display=False)
    (directory / "environment.json").write_text(json.dumps(environment, indent=2) + "\n")
    (directory / "input.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (directory / "code.json").write_text(
        json.dumps({name: digest(ROOT / name) for name in ["lab.py", "experiments.py"]}, indent=2)
        + "\n"
    )
    failures = []
    cases = list(MATRIX) if case == "all" else [case]
    for name in cases:
        for variant, batch_size in MATRIX[name]:
            for repeat in range(repeats):
                output = directory / f"{name}-{variant}-{repeat}"
                command = [
                    sys.executable,
                    str(ROOT / "experiments.py"),
                    "--case",
                    name,
                    "--variant",
                    variant,
                    "--batch-size",
                    str(batch_size),
                    "--mode",
                    mode,
                    "--output",
                    str(output),
                ]
                with (directory / f"{output.name}.log").open("w") as log:
                    try:
                        process = subprocess.Popen(
                            command,
                            cwd=ROOT,
                            stdout=log,
                            stderr=subprocess.STDOUT,
                            start_new_session=True,
                        )
                        if process.wait(timeout=180):
                            failures.append(output.name)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                        failures.append(output.name)
                print(f"{'FAIL' if output.name in failures else 'PASS'} {output.name}", flush=True)
                if failures:
                    break
            if failures:
                break
        if failures:
            break
    summary = {
        "run_id": identifier,
        "case": case,
        "mode": mode,
        "repeats": repeats,
        "status": "failed" if failures else "passed",
        "failures": failures,
    }
    (directory / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    write_report(directory)
    print(f"Evidence: {directory}")
    if failures:
        raise SystemExit(1)


def write_report(directory: Path) -> None:
    summary = json.loads((directory / "summary.json").read_text())
    input_manifest = json.loads((directory / "input.json").read_text())
    lines = [
        "# Daft native 实验记录",
        "",
        f"运行：`{summary['run_id']}`；状态：**{summary['status']}**。",
        "",
        f"输入 {input_manifest['rows']} 行；模式 `{summary['mode']}`。",
        "实际运行 Daft 0.7.26 发行包；源码参考 checkout 没有参与本次构建。",
        "",
        "| 实验 / 变体 | 结果 | 查询秒数 | 批调用 | UDF 输入行数 | 初始化次数 | UDF PID |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for path in sorted(directory.glob("*/result.json")):
        result = json.loads(path.read_text())
        observation = result["observations"]
        seconds = result.get("query_seconds")
        cells = [
            f"{result['case']} / {result['variant']}",
            result["status"],
            f"{seconds:.4f}" if seconds is not None else "—",
            observation["batch_calls"],
            observation["udf_input_rows"],
            observation["initializations"],
            observation["udf_pids"],
        ]
        lines.append("| " + " | ".join("—" if cell is None else str(cell) for cell in cells) + " |")
    lines += [
        "",
        "事件采集影响耗时；此表用于学习执行机制，不是公平性能基准。",
        "详细版本、代码和输入哈希见同目录 JSON；计划和事件见各变体子目录。",
        "",
    ]
    (directory / "report.md").write_text("\n".join(lines))


def report() -> None:
    runs = LOCAL / "runs"
    if not runs.exists():
        raise SystemExit("No runs recorded")
    for directory in sorted(runs.iterdir()):
        summary_path = directory / "summary.json"
        if not summary_path.exists() or (directory / "audit.json").exists():
            continue
        print(json.dumps(json.loads(summary_path.read_text())))
        for path in sorted(directory.glob("*/result.json")):
            result = json.loads(path.read_text())
            observations = result["observations"]
            print(
                json.dumps(
                    {
                        "case": result["case"],
                        "variant": result["variant"],
                        "status": result["status"],
                        "seconds": result.get("query_seconds"),
                        **observations,
                    }
                )
            )


def main() -> None:
    os.chdir(ROOT)
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor")
    generator = subparsers.add_parser("generate")
    generator.add_argument("--rows", type=int, default=100_000)
    generator.add_argument("--files", type=int, default=4)
    generator.add_argument("--skew", action="store_true")
    runner = subparsers.add_parser("run")
    runner.add_argument("--case", choices=["all", *MATRIX], default="all")
    runner.add_argument("--mode", choices=["evidence", "timing"], default="evidence")
    runner.add_argument("--repeats", type=int, choices=range(1, 11), default=1)
    subparsers.add_parser("report")
    args = parser.parse_args()
    if args.command == "doctor":
        doctor()
    elif args.command == "generate":
        generate(args.rows, args.files, args.skew)
    elif args.command == "run":
        run(args.case, args.mode, args.repeats)
    else:
        report()


if __name__ == "__main__":
    main()
