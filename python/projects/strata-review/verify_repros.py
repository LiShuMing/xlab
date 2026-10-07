"""Run only the checked-in, agent-authored ASan ground-truth reproductions."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--task-thread", action="store_true", help="Also check the real repository header")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).resolve().with_name("reproduce_known.cpp")
    binary = output / "known_repros"
    command = [
        "clang++", "-std=c++20", "-O0", "-g", "-fsanitize=address",
        "-fno-omit-frame-pointer", str(source), "-o", str(binary),
    ]
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if compiled.returncode:
        raise SystemExit("ASan compilation failed: " + compiled.stderr)
    rows = []
    for mode, expected in [("bounds", "heap-buffer-overflow"), ("lifetime", "heap-use-after-free")]:
        result = subprocess.run([str(binary), mode], capture_output=True, text=True, timeout=15)
        detected = result.returncode != 0 and expected in result.stderr
        log = output / f"asan-{mode}.log"
        with log.open("x", encoding="utf-8") as handle:
            handle.write(result.stdout + result.stderr)
        rows.append({"mode": mode, "expected": expected, "returncode": result.returncode,
                     "confirmed": detected, "log": str(log)})
        print(json.dumps(rows[-1]), flush=True)
    with (output / "asan-summary.json").open("x", encoding="utf-8") as handle:
        json.dump({"compile_command": command, "checks": rows,
                   "scope": "Checked-in reproductions only; never execute model output."}, handle, indent=2)
        handle.write("\n")
    if args.task_thread:
        project = Path(__file__).resolve().parent
        root = project.parents[2]
        task_binary = output / "task_thread_repro"
        task_command = ["clang++", "-std=c++20", "-pthread", "-O0", "-g",
                        "-I", str(root / "cc/cclab/src/utils"),
                        str(project / "reproduce_task_thread.cpp"), "-o", str(task_binary)]
        compiled = subprocess.run(task_command, capture_output=True, text=True, timeout=60)
        if compiled.returncode:
            raise SystemExit("TaskThread compilation failed: " + compiled.stderr)
        task_rows = []
        for mode in ["control", "reentrant"]:
            timed_out = False
            try:
                result = subprocess.run([str(task_binary), mode], capture_output=True, timeout=3)
                stderr, returncode = result.stderr.decode("utf-8"), result.returncode
            except subprocess.TimeoutExpired as exc:
                timed_out = True
                stderr, returncode = (exc.stderr or b"").decode("utf-8"), None
            confirmed = ((not timed_out and returncode == 0 and "shutdown_returned" in stderr)
                         if mode == "control" else
                         (timed_out and "callback_entered" in stderr and "callback_returned" not in stderr))
            with (output / f"task-thread-{mode}.log").open("x", encoding="utf-8") as handle:
                handle.write(stderr)
            task_rows.append({"mode": mode, "timeout": timed_out, "returncode": returncode,
                              "confirmed": confirmed})
            print(json.dumps(task_rows[-1]), flush=True)
        with (output / "task-thread-summary.json").open("x", encoding="utf-8") as handle:
            json.dump({"compile_command": task_command, "checks": task_rows,
                       "scope": "Actual unchanged header; control exits, reentrant shutdown callback hangs."},
                      handle, indent=2)
            handle.write("\n")
        rows.extend(task_rows)
    return 0 if all(row["confirmed"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
