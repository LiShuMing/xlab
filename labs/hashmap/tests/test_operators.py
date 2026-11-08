"""Operator-specific eligibility, baseline and report semantics."""

import json
from pathlib import Path
import sys
import unittest

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "tools"))
from report import render, summarize
from run import matrix
from test_tools import Structure, sample


class OperatorsTests(unittest.TestCase):
    def test_matrix_contracts(self):
        config = json.loads((LAB / "cases/operators.json").read_text())
        jobs = matrix(config, False)
        self.assertEqual(len(jobs), len({tuple(sorted(job.items())) for job in jobs}))
        for job in jobs:
            baseline = dict(job, method="bucket" if job["mode"].startswith("join-") else "std")
            self.assertIn(baseline, jobs)
            if job["method"] in ("bitmap", "direct"):
                self.assertGreater(job["domain"], 0)
            if job["method"] == "bitmap":
                self.assertEqual(job["mode"], "semi-probe")
        self.assertTrue(any(job["distribution"] == "phases" for job in jobs))

    def test_baselines_and_dimensions(self):
        baseline = sample("bucket", "20")
        baseline.update(mode="join-probe", domain="4096", ndv_config="64", null_percent="10")
        candidate = dict(baseline, method="chain-fp", ns_per_op="10")
        rows = summarize([baseline, candidate])
        self.assertEqual(next(row for row in rows if row["method"] == "chain-fp")["speedup"], 2)
        other = dict(candidate, domain="8192")
        self.assertEqual(len(summarize([baseline, candidate, other])), 3)
        self.assertIsNone(
            next(row for row in summarize([baseline, other]) if row["method"] == "chain-fp")[
                "baseline"
            ]
        )

    def test_operator_report_semantics(self):
        row = sample()
        row.update(
            mode="aggregate",
            case_name="agg-dense8",
            distribution="phases",
            ndv="64",
            null_rows="12",
            actual_hit_ratio="0.5",
            cpu_ns_per_op="8",
            ndv_config="64",
            domain="256",
            null_percent="10",
        )
        document, _ = render({"family": "operators", "status": "completed"}, [row])
        self.assertIn("StarRocks", document)
        self.assertIn("不包含输出行物化", document)
        self.assertIn("进程 CPU", document)
        self.assertNotIn("字符串值统一为 uint32_t", document)
        structure = Structure()
        structure.feed(document)
        self.assertEqual(len(structure.ids), len(set(structure.ids)))
        self.assertTrue(set(structure.targets).issubset(structure.ids))
        self.assertFalse(structure.external_assets)


if __name__ == "__main__":
    unittest.main()
