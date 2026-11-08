"""Check experiment inputs and reporting contracts without external test packages."""

from html.parser import HTMLParser
import json
import shutil
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "tools"))
from generate_cases import generate as generate_cases
from report import render, summarize
from run import matrix


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.targets = []
        self.external_assets = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "a" and attrs.get("href", "").startswith("#"):
            self.targets.append(attrs["href"][1:])
        if tag in ("script", "link") and (attrs.get("src") or attrs.get("href")):
            self.external_assets.append(attrs)


def sample(method="std", ns="10", seed="42"):
    return dict(
        mode="lookup",
        case_name="short64",
        key_type="string",
        n="64",
        method=method,
        hit="100",
        distribution="uniform",
        target_load="0.75",
        actual_load="0.5",
        seed=seed,
        sample="0",
        operations="1000",
        elapsed_ns=str(float(ns) * 1000),
        ns_per_op=ns,
        checksum="123",
        trace_hash="987",
        map_bytes="2048",
        key_payload_bytes="512",
        capacity="128",
        mean_probes="",
        mean_comparisons="",
        max_probes="",
        algorithm="test",
    )


class ToolTests(unittest.TestCase):
    def test_median_baseline_and_missing(self):
        rows = summarize([sample(ns="10"), sample(ns="20"), sample("linear", "5")])
        linear = next(row for row in rows if row["method"] == "linear")
        self.assertEqual(linear["baseline"], 15)
        self.assertEqual(linear["speedup"], 3)
        self.assertAlmostEqual(linear["delta_pct"], -200 / 3)
        self.assertIsNone(summarize([sample("perfect")])[0]["baseline"])

    def test_render_escapes_and_links(self):
        hostile = sample("perfect")
        hostile["algorithm"] = '<script>alert("bad")</script>'
        document, rows = render(
            {"started_at": "<script>bad</script>", "status": "completed"}, [hostile]
        )
        self.assertNotIn('<script>alert("bad")</script>', document)
        self.assertIn("&lt;script&gt;", document)
        self.assertIn("未测", document)
        parser = Structure()
        parser.feed(document)
        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        self.assertTrue(set(parser.targets).issubset(parser.ids))
        self.assertEqual(parser.external_assets, [])
        self.assertEqual(len(rows), 1)

    def test_invalid_measurement(self):
        with self.assertRaises(ValueError):
            summarize([sample(ns="0")])
        for ns in ("nan", "inf", "-1"):
            with self.assertRaises(ValueError):
                summarize([sample(ns=ns)])

    def test_render_escapes_imported_key_count(self):
        hostile = sample()
        hostile["n"] = '<img src=x onerror=alert(1)>'
        document, _ = render(
            {"status": "completed", "failed_jobs": hostile["n"]}, [hostile]
        )
        self.assertNotIn(hostile["n"], document)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", document)

    def test_matrix_capabilities_and_baselines(self):
        config = json.loads((LAB / "cases/standard.json").read_text())
        jobs = matrix(config, True)
        self.assertEqual(jobs, matrix(config, True))
        identities = set()
        for job in jobs:
            identity = tuple(sorted(job.items()))
            self.assertNotIn(identity, identities)
            identities.add(identity)
            if job["method"] in ("perfect", "wide", "sorted"):
                self.assertEqual(job["mode"], "lookup")
            baseline = dict(job, method="std")
            self.assertIn(baseline, jobs)
        self.assertFalse(any(j["method"] in ("perfect", "wide") for j in matrix(config, False)))

    @unittest.skipUnless(
        shutil.which("node"), "Node unavailable; browser-independent UI test skipped"
    )
    def test_offline_ui(self):
        subprocess.run(["node", str(LAB / "tests/report_ui_test.cjs")], check=True, timeout=10)

    def test_deterministic_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            generate_cases(output)
            first = {p.name: p.read_bytes() for p in output.iterdir()}
            generate_cases(output)
            self.assertEqual(first, {p.name: p.read_bytes() for p in output.iterdir()})
            self.assertIn("short255_keys", first["cases.h"].decode())
            self.assertIn("short256_map", first["perfect_cases.cc"].decode())


if __name__ == "__main__":
    unittest.main()
