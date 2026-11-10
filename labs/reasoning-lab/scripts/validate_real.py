"""Bounded real-model acceptance: Base, SFT, full resume, GRPO and comparisons.

Run from this project with `uv run --locked python scripts/validate_real.py`.
Uses an isolated 8/2/2/2 dataset; it does not inspect formal test/OOD answers.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=".local/models/qwen3-0.6b")
    parser.add_argument("--device", default="mps", choices=["cpu", "mps"])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    stamp = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d-%H%M%S-%f")
    output = root / ".local" / "acceptance" / stamp
    output.mkdir(parents=True, exist_ok=False)
    data, runs = output / "data", output / "runs"
    runs.mkdir()

    def invoke(label: str, command: list[str]) -> None:
        with (output / f"{label}.log").open("w") as log:
            result = subprocess.run(
                [sys.executable, "-m", "reasoning_lab", *command],
                cwd=root,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        if result.returncode:
            raise RuntimeError(f"{label} failed; inspect {output / (label + '.log')}")
        print(f"Passed: {label}", flush=True)

    invoke(
        "data",
        ["data", "--output", str(data), "--train", "8", "--dev", "2", "--test", "2", "--ood", "2"],
    )

    def experiment(label: str, config: str, extra: list[str]) -> Path:
        before = set(runs.iterdir())
        invoke(
            label,
            [
                "run",
                "--config",
                f"configs/{config}.yaml",
                "--model",
                args.model,
                "--data",
                str(data),
                "--device",
                args.device,
                "--dtype",
                "float32",
                "--max-seconds",
                "300",
                "--output",
                str(runs),
                *extra,
            ],
        )
        created = set(runs.iterdir()) - before
        if len(created) != 1:
            raise RuntimeError("Expected exactly one isolated run")
        path = created.pop()
        summary = json.loads((path / "summary.json").read_text())
        if summary.get("complete") is False:
            raise RuntimeError(f"Incomplete evaluation: {path}")
        return path

    base = experiment("base", "base", [])
    sft = experiment("sft", "sft", ["--steps", "3"])
    resumed = experiment(
        "resume", "sft", ["--steps", "4", "--resume", str(sft / "checkpoints" / "final.pt")]
    )
    summary = json.loads((resumed / "summary.json").read_text())
    if summary["updates"] != 4 or summary["cursor"] != 4:
        raise RuntimeError("Resume did not preserve step/cursor")
    grpo = experiment(
        "grpo", "grpo", ["--steps", "2", "--adapter", str(resumed / "checkpoints" / "best.pt")]
    )
    metrics = [json.loads(line) for line in (grpo / "metrics.jsonl").read_text().splitlines()]
    updates = [row for row in metrics if row.get("stage") == "grpo"]
    if len(updates) != 2 or any(
        abs(row["ratio_min"] - 1) > 1e-4 or abs(row["ratio_max"] - 1) > 1e-4 for row in updates
    ):
        raise RuntimeError("GRPO initial-ratio invariant failed")
    invoke(
        "compare-base-sft",
        [
            "compare",
            str(base / "eval" / "dev"),
            str(resumed / "eval" / "dev-full"),
            "--output",
            str(output / "base-sft.json"),
        ],
    )
    invoke(
        "compare-sft-grpo",
        [
            "compare",
            str(resumed / "eval" / "dev-full"),
            str(grpo / "eval" / "dev-full"),
            "--output",
            str(output / "sft-grpo.json"),
        ],
    )
    report = {
        "passed": True,
        "device": args.device,
        "runs": {"base": str(base), "sft": str(sft), "resume": str(resumed), "grpo": str(grpo)},
        "scope": (
            "Execution and numerical acceptance only; "
            "two dev questions do not establish quality gains."
        ),
    }
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"output": str(output), **report}, indent=2))


if __name__ == "__main__":
    main()
