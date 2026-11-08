"""Exercise real CSV, phase evidence, lazy construction and every state layout."""

import csv
import io
import math
from pathlib import Path
import subprocess
import sys
import unittest

BINARY = sys.argv[1]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from report import render


def run(method: str, size: int = 256, nulls: int = 10, distribution: str = "phases") -> dict:
    result = subprocess.run(
        [
            BINARY,
            "--method",
            method,
            "--case",
            "many-groups",
            "--n",
            "4096",
            "--ndv",
            "256",
            "--state-bytes",
            str(size),
            "--null-percent",
            str(nulls),
            "--distribution",
            distribution,
            "--repeat",
            "1",
            "--batch-ms",
            "1",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert len(rows) == 1 and None not in rows[0] and all(v is not None for v in rows[0].values())
    return rows[0]


class StateContractTests(unittest.TestCase):
    def test_layouts_and_initialization(self):
        for size in (16, 256, 4096):
            with self.subTest(size=size):
                rows = {
                    method: run(method, size)
                    for method in ("std", "std-eager", "inline", "arena-lazy")
                }
                self.assertEqual(len({row["trace_hash"] for row in rows.values()}), 1)
                self.assertEqual(len({row["state_digest"] for row in rows.values()}), 1)
                self.assertEqual(int(rows["std"]["state_init_count"]), int(rows["std"]["ndv"]))
                self.assertEqual(int(rows["std-eager"]["state_init_count"]), 4096)
                self.assertEqual(rows["arena-lazy"]["state_relocated_bytes"], "0")
                self.assertGreater(int(rows["inline"]["state_relocated_bytes"]), 0)
                for row in rows.values():
                    self.assertGreater(float(row["cpu_ns_per_op"]), 0)
                    self.assertGreaterEqual(int(row["peak_map_bytes"]), int(row["map_bytes"]))
                    self.assertEqual(
                        sum(int(row[f"phase{p}_new_groups"]) for p in range(1, 5)), int(row["ndv"])
                    )
                    self.assertGreater(int(row["phase2_new_groups"]), 0)
                    self.assertTrue(
                        math.isclose(
                            int(row["elapsed_ns"]) / int(row["operations"]),
                            float(row["ns_per_op"]),
                            rel_tol=1e-9,
                        )
                    )
                    passes = int(row["operations"]) // int(row["n"])
                    phase_total = sum(float(row[f"phase{p}_ns_per_op"]) for p in range(1, 5)) / 4
                    self.assertLessEqual(phase_total, float(row["ns_per_op"]) * 1.001)
                    self.assertGreater(passes, 0)
                document, summary = render({"family": "states"}, list(rows.values()))
                self.assertEqual(len(summary), 4)
                self.assertIn("四阶段 CPU 耗时", document)
                self.assertIn("不是 RSS", document)
                self.assertNotIn("包含 perfect 常量求值", document)

    def test_all_null_and_input_independent_of_state_size(self):
        rows = [run(method, nulls=100) for method in ("std", "std-eager", "inline", "arena-lazy")]
        self.assertTrue(all(row["ndv"] == "1" and row["null_rows"] == "4096" for row in rows))
        self.assertEqual(len({row["state_digest"] for row in rows}), 1)
        traces = [run("arena-lazy", size=size)["trace_hash"] for size in (16, 256, 4096)]
        self.assertEqual(len(set(traces)), 1)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
