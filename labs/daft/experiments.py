"""Each invocation executes exactly one native experiment in a fresh process."""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
import traceback
import uuid
from pathlib import Path

import daft
import numpy as np
import psutil
import pyarrow.compute as pc
from daft import DataType, Series, col


def event(directory: str | None, kind: str, **values) -> None:
    if directory is None:
        return
    record = {
        "kind": kind,
        "pid": os.getpid(),
        "thread": threading.get_ident(),
        "monotonic_ns": time.monotonic_ns(),
        **values,
    }
    fd = os.open(
        str(Path(directory) / f"{os.getpid()}.jsonl"), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600
    )
    try:
        os.write(fd, (json.dumps(record) + "\n").encode())
    finally:
        os.close(fd)


def formula(values: Series):
    array = values.to_arrow()
    return pc.add(pc.multiply(array, array), pc.multiply(array, 3))


def build_query(case: str, variant: str, batch_size: int, events: str | None):
    frame = daft.read_parquet(".local/data/part-*.parquet")
    if case == "plan":

        @daft.func.batch(return_dtype=DataType.int64(), batch_size=1024, use_process=False)
        def measured(x: Series):
            event(events, "batch", rows=len(x))
            return formula(x)

        if variant == "filter-first":
            return (
                frame.where(col("group") < 4).with_column("y", measured(col("x"))).select("id", "y")
            )
        return frame.with_column("y", measured(col("x"))).where(col("group") < 4).select("id", "y")

    if case == "compute" and variant == "builtin":
        return frame.select("id", (col("x") * col("x") + 3 * col("x")).alias("y"))

    if case == "compute" and variant == "row":

        @daft.func(use_process=False)
        def row(x: int) -> int:
            return x * x + 3 * x

        return frame.select("id", row(col("x")).alias("y"))

    if case in {"compute", "batch"}:

        @daft.func.batch(return_dtype=DataType.int64(), batch_size=batch_size, use_process=False)
        def batch(x: Series):
            event(events, "batch", rows=len(x))
            return formula(x)

        return frame.into_batches(batch_size).select("id", batch(col("x")).alias("y"))

    if case == "state":
        if variant == "stateless-thread":

            @daft.func.batch(return_dtype=DataType.int64(), batch_size=1024, use_process=False)
            def initialize_each_batch(x: Series):
                instance = uuid.uuid4().hex
                event(events, "init", instance=instance)
                time.sleep(0.03)
                event(events, "batch", instance=instance, rows=len(x))
                return formula(x)

            return frame.select("id", initialize_each_batch(col("x")).alias("y"))

        @daft.cls(cpus=1, use_process=variant == "stateful-process")
        class ReusedState:
            def __init__(self):
                self.identity = uuid.uuid4().hex
                event(events, "init", instance=self.identity)
                time.sleep(0.03)

            @daft.method.batch(return_dtype=DataType.int64(), batch_size=1024)
            def transform(self, x: Series):
                event(events, "batch", instance=self.identity, rows=len(x))
                return formula(x)

        model = ReusedState()
        return frame.select("id", model.transform(col("x")).alias("y"))

    if case == "errors":

        @daft.func(use_process=False)
        def deliberate_error(x: int) -> int:
            raise ValueError("DAFT_LAB_EXPECTED_ERROR")

        return daft.from_pydict({"x": [1]}).select(deliberate_error(col("x")))
    raise ValueError(f"Unknown experiment: {case}/{variant}")


def validate(table, case: str, manifest: dict) -> dict:
    ids = table["id"].combine_chunks().to_numpy()
    actual = table["y"].combine_chunks().to_numpy()
    expected_ids = np.arange(manifest["rows"], dtype=np.int64)
    if case == "plan":
        groups = np.arange(manifest["rows"], dtype=np.int64) % 32
        if manifest["skew"]:
            groups = np.where(expected_ids % 10 != 0, 0, groups)
        expected_ids = expected_ids[groups < 4]
    order = np.argsort(ids)
    np.testing.assert_array_equal(ids[order], expected_ids)
    values = expected_ids % 97
    np.testing.assert_array_equal(actual[order], values * values + 3 * values)
    return {
        "rows": len(ids),
        "ids_unique": len(np.unique(ids)) == len(ids),
        "value_sum": int(actual.sum()),
        "status": "passed",
    }


def sample_memory(stop: threading.Event, samples: list) -> None:
    parent = psutil.Process()
    started = time.monotonic()
    while not stop.is_set():
        rss = pss = 0
        pss_available = True
        processes = [parent, *parent.children(recursive=True)]
        for process in processes:
            try:
                memory = process.memory_full_info()
                rss += memory.rss
                if hasattr(memory, "pss"):
                    pss += memory.pss
                else:
                    pss_available = False
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        samples.append(
            {
                "seconds": time.monotonic() - started,
                "rss_bytes": rss,
                "pss_bytes": pss if pss_available else None,
                "processes": len(processes),
            }
        )
        stop.wait(0.05)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--variant", required=True)
    parser.add_argument("--batch-size", type=int, default=1024)
    parser.add_argument("--mode", choices=["evidence", "timing"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    event_directory = args.output / "events"
    event_directory.mkdir()
    manifest = json.loads(Path(".local/data/manifest.json").read_text())
    evidence = str(event_directory.resolve()) if args.mode == "evidence" else None
    samples = []
    stop = threading.Event()
    monitor = threading.Thread(target=sample_memory, args=(stop, samples), daemon=True)
    result = {
        "case": args.case,
        "variant": args.variant,
        "batch_size": args.batch_size,
        "mode": args.mode,
        "pid": os.getpid(),
        "runner": "native",
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "status": "failed",
    }
    try:
        # Initialize the engine separately; this does not warm up or cache the measured query/UDF.
        daft.from_pydict({"x": [1, 2]}).select((col("x") + 1).alias("y")).collect()
        query = build_query(args.case, args.variant, args.batch_size, evidence)
        with (args.output / "plan.txt").open("w") as plan:
            query.explain(show_all=True, file=plan)
        monitor.start()
        started = time.perf_counter()
        try:
            table = query.to_arrow()
        except Exception as error:
            if args.case != "errors" or "DAFT_LAB_EXPECTED_ERROR" not in str(error):
                raise
            result["expected_error"] = str(error)
            result["validation"] = {"status": "passed", "expected_error_observed": True}
        else:
            if args.case == "errors":
                raise AssertionError("The intentional UDF failure was silently accepted")
            result["query_seconds"] = time.perf_counter() - started
            stop.set()
            monitor.join()
            result["validation"] = validate(table, args.case, manifest)
        result["status"] = "passed"
    except Exception:
        result["error"] = traceback.format_exc()
    finally:
        stop.set()
        if monitor.is_alive():
            monitor.join()
        (args.output / "memory.json").write_text(json.dumps(samples, indent=2) + "\n")
        events = []
        for event_file in event_directory.glob("*.jsonl"):
            events.extend(json.loads(line) for line in event_file.read_text().splitlines())
        batches = [item for item in events if item["kind"] == "batch"]
        initializations = [item for item in events if item["kind"] == "init"]
        batch_instrumented = evidence is not None and (
            args.case in {"plan", "batch", "state"}
            or (args.case == "compute" and args.variant == "batch")
        )
        result["observations"] = {
            "batch_calls": len(batches) if batch_instrumented else None,
            "udf_input_rows": sum(item["rows"] for item in batches) if batch_instrumented else None,
            "batch_sizes": sorted({item["rows"] for item in batches})
            if batch_instrumented
            else None,
            "initializations": len(initializations) if batch_instrumented else None,
            "instance_ids": sorted({item["instance"] for item in initializations})
            if batch_instrumented
            else None,
            "udf_pids": sorted({item["pid"] for item in events}) if batch_instrumented else None,
            "peak_pss_bytes": max((item["pss_bytes"] or 0 for item in samples), default=0),
            "peak_rss_bytes_including_shared_pages": max(
                (item["rss_bytes"] for item in samples), default=0
            ),
        }
        mechanism_errors = []
        if batch_instrumented and args.case in {"compute", "batch", "state"}:
            if sum(item["rows"] for item in batches) != manifest["rows"]:
                mechanism_errors.append("UDF event rows differ from input rows")
        if batches and args.case == "state":
            separate = {item["pid"] for item in batches} != {os.getpid()}
            expect_separate = args.variant == "stateful-process"
            result["observations"]["separate_process_observed"] = separate
            if separate != expect_separate:
                mechanism_errors.append("Observed PIDs do not match the requested execution mode")
        if mechanism_errors:
            result["status"] = "failed"
            result["error"] = "; ".join(mechanism_errors)
        result["mechanism_validation"] = {
            "status": "failed"
            if mechanism_errors
            else ("passed" if batch_instrumented else "not-instrumented"),
            "errors": mechanism_errors,
        }
        (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
