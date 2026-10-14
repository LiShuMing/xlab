#!/usr/bin/env python3
"""Keep the bounded DayLog retirement and its public recovery evidence intact."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DayLogRetirementTests(unittest.TestCase):
    def test_retired_namespace_is_absent(self):
        record = json.loads((ROOT / "docs/migrations/2026-10-14-daylog-source-retirement.json").read_text())
        self.assertEqual(record["file_count"], 97)
        self.assertEqual(len(record["files"]), 97)
        self.assertEqual(len({f["source_path"] for f in record["files"]}), 97)
        self.assertEqual(len({f["destination_path"] for f in record["files"]}), 97)
        transformed = []
        for item in record["files"]:
            source = item["source_path"]
            self.assertTrue(source.startswith("swift/projects/daylog/"))
            self.assertEqual(item["destination_path"], source.replace("swift/projects/daylog/", "apps/daylog/", 1))
            self.assertRegex(item["source_git_blob_sha1"], r"^[0-9a-f]{40}$")
            for key in ("source_sha256", "destination_sha256"):
                self.assertRegex(item[key], r"^[0-9a-f]{64}$")
            self.assertFalse((ROOT / source).exists())
            if item["source_sha256"] != item["destination_sha256"]:
                transformed.append(source)
                self.assertTrue(item["transformations"])
        self.assertEqual(len(transformed), 1)
        self.assertTrue(transformed[0].endswith("README.md"))
        self.assertEqual(record["retired_directories"], ["swift/projects/daylog", "swift/projects", "swift"])
        for directory in record["retired_directories"]:
            self.assertFalse((ROOT / directory).exists(), directory)
        self.assertIn("not_run", record["native_ui_acceptance"])
        self.assertIn("owner waived", record["native_ui_acceptance"])

    def test_maintained_routes_do_not_link_to_old_source(self):
        for name in ("README.md", "PROJECTS.md", "AGENTS.md", "TASKS.md", "SKILL.md", "docs/README.md"):
            source = (ROOT / name).read_text()
            self.assertNotRegex(source, r"\]\([^)]*swift/projects/daylog")
        record = (ROOT / "docs/migrations/2026-10-14-daylog-source-retirement.md").read_text()
        self.assertIn("原生 UI 验收未运行", record)
        self.assertIn("git revert", record)


if __name__ == "__main__":
    unittest.main()
