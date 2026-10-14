#!/usr/bin/env python3
"""Check maintained navigation links without following external/private URLs."""
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
GUIDES = [
    "README.md", "PROJECTS.md", "AGENTS.md", "SKILL.md", "TASKS.md",
    "docs/README.md", "docs/meta/migration-guide.md",
    "docs/migrations/2026-10-13-constellation.md",
    "docs/skills/personal-knowledge-base.md",
    "docs/migrations/2026-10-14-cygnus-source-retirement.md",
    *[str(path.relative_to(ROOT)) for path in (ROOT / "docs/books").glob("*/README.md")
      if "已迁移至 Cygnus" in path.read_text()],
    *[str(path.relative_to(ROOT)) for path in (ROOT / "docs/reports").glob("*/README.md")
      if "已迁移至 Cygnus" in path.read_text()],
    *[f"{language}/SKILL.md" for language in
      ("cc", "go", "haskell", "java", "python", "rust", "shell")],
    *[str(path.relative_to(ROOT)) for path in (ROOT / "docs/learn").glob("*.md")],
]


class NavigationTests(unittest.TestCase):
    def test_local_link_targets_exist(self):
        checked = 0
        for name in GUIDES:
            path = ROOT / name
            # Fenced templates are examples, not assertions of existing notes.
            source = re.sub(r"```.*?```", "", path.read_text(), flags=re.S)
            for target in re.findall(r"\]\(([^)]+)\)", source):
                parsed = urlsplit(target)
                if parsed.scheme or not parsed.path:
                    continue
                checked += 1
                with self.subTest(document=name, target=target):
                    self.assertTrue((path.parent / unquote(parsed.path)).exists())
        self.assertGreater(checked, 100)


if __name__ == "__main__":
    unittest.main()
