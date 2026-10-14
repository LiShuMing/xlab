#!/usr/bin/env python3
"""Offline regression fixtures: python3 -m unittest discover -s tools -p 'test_*.py'."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("healthcheck.sh").resolve()


class HealthcheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="xlab health 空 ")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        self.git("init", "-q")

    def git(self, *args):
        return subprocess.check_output(
            ["git", "-C", str(self.repo), *args], stderr=subprocess.STDOUT
        ).decode().strip()

    def run_check(self, **env):
        result = subprocess.run(
            ["bash", str(SCRIPT)], cwd=self.repo,
            env={**os.environ, "LC_ALL": "C", **env},
            text=True, capture_output=True, timeout=20,
        )
        self.assertEqual(result.stderr, "")
        return result

    def declare(self, name, path):
        self.git("config", "-f", ".gitmodules", f"submodule.{name}.path", path)
        self.git("config", "-f", ".gitmodules", f"submodule.{name}.url",
                 "https://example.com/reference.git")

    def test_empty_repo_has_no_false_large_files(self):
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("OK: no files larger than 10M", result.stdout)
        self.assertIn("declarations: 0\ngitlinks: 0", result.stdout)

    def test_large_file_space_and_unicode(self):
        for name in ["large file.txt", "大文件.txt", "new\nline.txt"]:
            (self.repo / name).write_bytes(b"x" * 2048)
        result = self.run_check(BIG_FILE_THRESHOLD="1k")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("WARN: large files found", result.stdout)
        # Each complete shell-escaped path occupies one line, including non-ASCII.
        lines = result.stdout.split("WARN: large files found\n")[1].split("\n\n")[0].splitlines()
        self.assertEqual(len(lines), 3)
        for line in lines:
            self.assertIn("\t", line)
        self.assertIn("large\\ file.txt", result.stdout)

    def test_orphan_declaration_is_failure_even_with_empty_submodule_status(self):
        self.declare("ref", "refs/space 中文")
        self.assertEqual(self.git("submodule", "status"), "")
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("declaration without gitlink: refs/space 中文", result.stdout)
        self.assertNotIn("submodule status works", result.stdout)

    def test_duplicate_and_missing_url(self):
        self.declare("one", "refs/space 中文")
        self.declare("two", "refs/space 中文")
        self.git("config", "-f", ".gitmodules", "--unset", "submodule.two.url")
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("duplicate submodule path: refs/space 中文", result.stdout)
        self.assertIn("missing or suspicious submodule URL", result.stdout)

    def make_gitlink(self, path):
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.com",
                       "commit", "--allow-empty", "-qm", "fixture")
        sha = self.git("rev-parse", "HEAD")
        self.git("update-index", "--add", "--cacheinfo", f"160000,{sha},{path}")

    def test_gitlink_without_declaration(self):
        self.make_gitlink("refs/space 中文")
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("gitlink without declaration: refs/space 中文", result.stdout)

    def test_matching_uninitialized_gitlink_is_warning(self):
        self.make_gitlink("refs/space 中文")
        self.declare("ref", "refs/space 中文")
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("declarations: 1\ngitlinks: 1", result.stdout)
        self.assertIn("WARN: tracked submodules are not initialized", result.stdout)

    def test_size_subtracts_git_metadata_independently(self):
        (self.repo / ".git" / "fixture-size").write_bytes(b"x" * (1024 * 1024))
        def kib(path):
            return int(subprocess.check_output(["du", "-sk", str(path)]).split()[0])
        expected = f"worktree: {(kib(self.repo) - kib(self.repo / '.git')) / 1024:.1f}M"
        result = self.run_check()
        self.assertIn(expected, result.stdout)

    def test_linked_worktree_size_excludes_only_pointer(self):
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.com",
                 "commit", "--allow-empty", "-qm", "fixture")
        linked = Path(self.temp.name) / "linked"
        self.git("worktree", "add", "-q", "-b", "linked", str(linked))
        self.repo = linked
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("worktree: n/a", result.stdout)

    def test_invalid_gitmodules_and_broken_link(self):
        (self.repo / ".gitmodules").write_text("[broken\n")
        (self.repo / "missing link").symlink_to("absent")
        result = subprocess.run(["bash", str(SCRIPT)], cwd=self.repo,
                                text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 1)
        self.assertIn(".gitmodules cannot be parsed", result.stdout)
        self.assertIn("broken symlinks found", result.stdout)


if __name__ == "__main__":
    unittest.main()
