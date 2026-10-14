#!/usr/bin/env python3
"""Validate the bounded source-retirement manifest and maintained routes offline."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DocumentRetirementTests(unittest.TestCase):
    def test_only_manifested_bodies_are_retired(self):
        record = json.loads((ROOT / "docs/migrations/2026-10-14-cygnus-source-retirement.json").read_text())
        files = record["files"]
        self.assertEqual(len(files), 184)
        self.assertEqual(len({item["source"] for item in files}), 184)
        for item in files:
            path = ROOT / item["source"]
            with self.subTest(path=item["source"]):
                self.assertEqual(len(item["source_sha256"]), 64)
                self.assertEqual(len(item["destination_sha256"]), 64)
                if path.exists():
                    self.assertEqual(path.name, "README.md")
                    self.assertIn("已迁移至 Cygnus", path.read_text())
                else:
                    self.assertFalse(path.exists())
        roots = {"/".join(item["source"].split("/")[:3]) for item in files}
        self.assertEqual(len(roots), 9)
        for directory in roots:
            self.assertIn("https://github.com/LiShuMing/cygnus/", (ROOT / directory / "README.md").read_text())


if __name__ == "__main__":
    unittest.main()
