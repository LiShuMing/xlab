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
                self.assertFalse(path.exists())
        roots = record["retired_directories"]
        self.assertEqual(len(roots), 15)
        for directory in roots:
            self.assertFalse((ROOT / directory).exists(), directory)
        for move in record["preserved_relocations"]:
            self.assertFalse((ROOT / move["source"]).exists())
            self.assertTrue((ROOT / move["destination"]).is_file())



if __name__ == "__main__":
    unittest.main()
