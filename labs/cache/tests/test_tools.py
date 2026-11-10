"""Matrix, grouping, escaping, offline resources and report anchors."""

from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "tools"))
from report import render, summarize
from run import matrix


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.targets, self.assets = [], [], []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "a" and attrs.get("href", "").startswith("#"):
            self.targets.append(attrs["href"][1:])
        if tag in ("script", "link") and (attrs.get("src") or attrs.get("href")):
            self.assets.append(attrs)


def job(algorithm: str = "lru", hits: int = 50, ns: float = 20, capacity: int = 512) -> dict:
    latency = {"count": 100, "p50": 30, "p95": 60, "p99": 90, "maximum": 100, "histogram": [100]}
    events = {
        "admissions": 50,
        "evictions": 0,
        "rejections": 0,
        "promotions": 1,
        "demotions": 0,
        "sketch_resets": 0,
        "ghost_hits": 0,
    }
    return dict(
        algorithm=algorithm,
        workload="hot_shift",
        capacity=capacity,
        count=100,
        seed=42,
        window_percent=1,
        protected_percent=80,
        aging_factor=10,
        trace_hash="123",
        hit_digest="456",
        hits=hits,
        latency={"all": latency, "point": latency, "scan": latency},
        clock_floor=latency,
        phase_latency=[latency] * 4,
        windows=[
            dict(
                begin=0,
                end=100,
                points=100,
                point_hits=hits,
                scans=0,
                scan_hits=0,
                hits=hits,
                events=events,
                layout={"sketch_bytes": 0, "history": 0},
            )
        ],
        samples=[dict(ns_per_op=ns, cpu_ns_per_op=ns, operations=100, elapsed_ns=ns * 100)],
    )


class ToolTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node unavailable; DOM logic test skipped")
    def test_offline_controls(self):
        subprocess.run(["node", str(LAB / "tests/report_ui_test.cjs")], check=True, timeout=10)

    def test_matrix_and_controls(self):
        config = json.loads((LAB / "cases.json").read_text())["standard"]
        self.assertEqual(len(matrix(config)), 540)
        jobs = matrix(config)
        self.assertEqual(jobs, matrix(config))
        self.assertEqual(len(jobs), len({tuple(sorted(j.items())) for j in jobs}))
        for entry in jobs:
            baseline = dict(
                entry, algorithm="lru", window_percent=1, protected_percent=80, aging_factor=10
            )
            self.assertIn(baseline, jobs)

    def test_baseline_and_parameter_identity(self):
        baseline = job()
        candidate = job("wtinylfu", hits=75, ns=10)
        rows = summarize([baseline, candidate])
        row = next(r for r in rows if r["algorithm"] == "wtinylfu")
        self.assertEqual(row["hit_delta_pp"], 25)
        self.assertEqual(row["delta_pct"], -50)
        other = dict(candidate, window_percent=20)
        self.assertEqual(len(summarize([baseline, candidate, other])), 3)
        self.assertIsNone(summarize([job(capacity=128), candidate])[1]["baseline_ns"])

    def test_offline_report_and_escaping(self):
        hostile = job()
        hostile["workload"] = '<img src=x onerror="bad">'
        document, _ = render(
            {"status": "completed", "started_at": "<script>bad</script>"}, [hostile]
        )
        self.assertNotIn(hostile["workload"], document)
        self.assertNotIn("<script>bad</script>", document)
        self.assertIn("&lt;img", document)
        self.assertIn("不能解释为数据库查询", document)
        self.assertIn("不描述具体产品的策略变更", document)
        parser = Structure()
        parser.feed(document)
        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        self.assertTrue(set(parser.targets) <= set(parser.ids))
        self.assertFalse(parser.assets)


if __name__ == "__main__":
    unittest.main()
