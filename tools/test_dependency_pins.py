#!/usr/bin/env python3
"""Offline checks for the two explicitly restored dependency gitlinks."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
PINS = {
    "googletest": "b514bdc898e2951020cbdca1304b75f5950d1f59",
    "benchmark": "c58e6d0710581e3a08d65c349664128a8d9a2461",
}

class DependencyPinTests(unittest.TestCase):
    def test_gitlinks_match_cmake_and_official_urls(self):
        rows = subprocess.check_output(
            ["git", "ls-files", "--stage", "-z"], cwd=ROOT).decode().split("\0")
        links = {}
        for row in rows:
            if row.startswith("160000 "):
                metadata, path = row.split("\t", 1)
                links[path] = metadata.split()[1]
        self.assertEqual(links, {f"cc/thirdparty/{name}": sha for name, sha in PINS.items()})
        cmake = (ROOT / "cmake/XlabDependencies.cmake").read_text()
        for name, sha in PINS.items():
            with self.subTest(dependency=name):
                self.assertIn(sha, cmake)
                url = subprocess.check_output([
                    "git", "config", "--file", ".gitmodules", "--get",
                    f"submodule.cc/thirdparty/{name}.url"], cwd=ROOT).decode().strip()
                self.assertEqual(url, f"https://github.com/google/{name}.git")

if __name__ == "__main__":
    unittest.main()
