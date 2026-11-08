"""Keep state size in comparison identities and retain offline report contracts."""

import json
from pathlib import Path
import sys
import unittest

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "tools"))
from report import render, summarize
from run import matrix
from test_tools import Structure, sample


class StateToolsTests(unittest.TestCase):
    def test_controlled_matrix(self):
        config = json.loads((LAB / "cases/states.json").read_text())
        jobs = matrix(config, False)
        self.assertEqual(len(jobs), 180)
        self.assertEqual(jobs, matrix(config, False))
        self.assertEqual(len(jobs), len({tuple(sorted(job.items())) for job in jobs}))
        for job in jobs:
            self.assertIn(dict(job, method="std"), jobs)
            if job["case"] == "unique":
                self.assertEqual(job["n"], job["ndv"])
                self.assertEqual(job["null-percent"], 0)

    def test_state_sizes_do_not_share_baseline(self):
        baseline = dict(sample(ns="20"), state_bytes="16", mode="state-build")
        other = dict(baseline, method="arena-lazy", ns_per_op="5", state_bytes="4096")
        rows = summarize([baseline, other])
        self.assertIsNone(next(row for row in rows if row["method"] == "arena-lazy")["baseline"])

    def test_report_structure_and_escape(self):
        row = dict(
            sample(),
            mode="state-build",
            state_bytes="4096",
            ndv="8",
            cpu_ns_per_op="9",
            peak_map_bytes="4096",
            allocations="16",
            allocated_bytes="8192",
            state_init_bytes="4096",
            state_relocated_bytes="2048",
            rehashes="4",
        )
        for phase in range(1, 5):
            row.update(
                {
                    f"phase{phase}_ns_per_op": "8",
                    f"phase{phase}_cpu_ns_per_op": "7",
                    f"phase{phase}_new_groups": "2",
                    f"phase{phase}_rehashes": "1",
                }
            )
        row["case_name"] = '<img src=x onerror="bad">'
        document, _ = render({"family": "states", "status": "completed"}, [row])
        self.assertNotIn(row["case_name"], document)
        self.assertIn("&lt;img", document)
        structure = Structure()
        structure.feed(document)
        self.assertEqual(len(structure.ids), len(set(structure.ids)))
        self.assertTrue(set(structure.targets) <= set(structure.ids))
        self.assertFalse(structure.external_assets)


if __name__ == "__main__":
    unittest.main()
