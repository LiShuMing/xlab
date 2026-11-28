"""Unit tests for tools/check_workspace_env.py (offline, uses temp dirs only)."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.check_workspace_env import (
    CheckReport,
    check_envs_layout,
    check_projects_sync,
    normalize_github_slug,
    parse_projects_registry,
)


class WorkspaceEnvCheckTests(unittest.TestCase):
    def test_normalize_github_slug_handles_https_and_ssh(self) -> None:
        self.assertEqual(
            normalize_github_slug("git@github.com:LiShuMing/xlab.git"),
            "lishuming/xlab",
        )
        self.assertEqual(
            normalize_github_slug("https://github.com/slatedb/slatedb.git"),
            "slatedb/slatedb",
        )
        self.assertEqual(
            normalize_github_slug("https://github.com/LiShuMing/vela"),
            "lishuming/vela",
        )
        self.assertIsNone(normalize_github_slug("https://example.com/foo/bar"))

    def test_parse_projects_registry_extracts_dirs_and_slugs(self) -> None:
        sample = """
| `~/work/xlab` | xlab | https://github.com/LiShuMing/xlab (`git@github.com:LiShuMing/xlab.git`) |
| `~/work/slatedb` | SlateDB | https://github.com/slatedb/slatedb |
"""
        parsed = parse_projects_registry(sample)
        self.assertEqual(parsed["xlab"], {"lishuming/xlab"})
        self.assertEqual(parsed["slatedb"], {"slatedb/slatedb"})

    def test_projects_sync_detects_missing_stale_and_remote_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            work.mkdir()
            (work / "alpha").mkdir()
            (work / "unregistered").mkdir()

            # Initialize git repo for alpha with mismatched remote
            subprocess.run(["git", "init", "-q", str(work / "alpha")], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(work / "alpha"),
                    "remote",
                    "add",
                    "origin",
                    "git@github.com:ExampleOrg/alpha-actual.git",
                ],
                check=True,
            )

            projects = root / ".PROJECTS"
            projects.write_text(
                "| `~/work/alpha` | https://github.com/ExampleOrg/alpha-wrong |\n"
                "| `~/work/ghost` | https://github.com/ExampleOrg/ghost |\n",
                encoding="utf-8",
            )

            report = CheckReport()
            check_projects_sync(projects, work, report, check_remotes=True)

            self.assertTrue(any("unregistered" in f for f in report.failures))
            self.assertTrue(any("remote mismatch" in f for f in report.failures))
            self.assertTrue(any("ghost" in w for w in report.warnings))

    def test_projects_sync_passes_when_aligned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            (work / "demo").mkdir(parents=True)
            subprocess.run(["git", "init", "-q", str(work / "demo")], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(work / "demo"),
                    "remote",
                    "add",
                    "origin",
                    "git@github.com:ExampleOrg/demo.git",
                ],
                check=True,
            )

            projects = root / ".PROJECTS"
            projects.write_text(
                "| `~/work/demo` | https://github.com/ExampleOrg/demo |\n",
                encoding="utf-8",
            )

            report = CheckReport()
            check_projects_sync(projects, work, report, check_remotes=True)
            self.assertEqual(report.failures, [])
            self.assertEqual(report.warnings, [])
            self.assertTrue(report.oks)

    def test_envs_layout_flags_secret_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            envs = Path(tmp) / ".ENVS"
            envs.mkdir()
            (envs / "env.sh").write_text("# loader\n", encoding="utf-8")
            (envs / "README.md").write_text("# doc\n", encoding="utf-8")
            (envs / ".env").write_text("SECRET=1\n", encoding="utf-8")

            report = CheckReport()
            ok = check_envs_layout(envs, report)
            self.assertFalse(ok)
            self.assertTrue(any("secret-like file" in f for f in report.failures))


if __name__ == "__main__":
    unittest.main()
