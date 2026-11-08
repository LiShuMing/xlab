"""Check the actual executable's cross-strategy semantics and CSV/report roundtrip."""

import csv
import io
from pathlib import Path
import subprocess
import sys
import unittest

BINARY = sys.argv[1]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from report import render


def run(method, mode="join-probe", hit=50, nulls=10, case="join-dense", domain=256):
    result = subprocess.run(
        [
            BINARY,
            "--case",
            case,
            "--mode",
            mode,
            "--method",
            method,
            "--n",
            "1024",
            "--ndv",
            "64",
            "--domain",
            str(domain),
            "--hit",
            str(hit),
            "--null-percent",
            str(nulls),
            "--repeat",
            "1",
            "--batch-ms",
            "1",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert len(rows) == 1 and None not in rows[0]
    return rows[0]


class ContractTests(unittest.TestCase):
    def test_join_duplicates_equal_across_strategies(self):
        rows = [run(method) for method in ("bucket", "chain", "chain-fp", "direct")]
        self.assertEqual(len({row["trace_hash"] for row in rows}), 1)
        self.assertEqual(len({row["join_result_digest"] for row in rows}), 1)
        self.assertGreater(int(rows[0]["join_result_digest"]), 0)
        for row in rows:
            self.assertGreater(float(row["cpu_ns_per_op"]), 0)
        document, summary = render({"family": "operators"}, rows)
        self.assertEqual(len(summary), 4)
        self.assertIn("bucket", document)
        self.assertNotIn("字符串值统一为 uint32_t", document)

    def test_exact_nonnull_hits_and_nulls(self):
        self.assertEqual(float(run("direct", hit=0, nulls=0)["actual_hit_ratio"]), 0)
        self.assertEqual(float(run("direct", hit=100, nulls=0)["actual_hit_ratio"]), 1)
        nullable = float(run("direct", hit=100, nulls=10)["actual_hit_ratio"])
        self.assertTrue(0.85 < nullable < 0.95)

    def test_compound_state_and_membership(self):
        packed = run("flat-fp", mode="aggregate", case="agg-composite32x2", domain=0)
        serialized = run("flat-bytes", mode="aggregate", case="agg-composite32x2", domain=0)

        def cycle(row):
            return int(row["checksum"]) // (int(row["operations"]) // int(row["n"]))

        self.assertEqual(cycle(packed), cycle(serialized))
        bitmap = run("bitmap", mode="semi-probe", case="semi-dense")
        baseline = run("std", mode="semi-probe", case="semi-dense")
        self.assertEqual(bitmap["trace_hash"], baseline["trace_hash"])
        self.assertEqual(bitmap["actual_hit_ratio"], baseline["actual_hit_ratio"])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
