#!/usr/bin/env python3
"""Check maintained navigation links without following external/private URLs."""
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
GUIDES = [
    "README.md", "PROJECTS.md", "AGENTS.md",
    "cc/cclab/docs/api/README.md", "cc/cclab/docs/architecture/README.md",
    "docs/README.md",
    "ocaml/README.md", "ocaml/TUTORIAL.md",
    "lean4/README.md", "lean4/TUTORIAL.md",
    # Every docs section index is a maintained guide: adding a new top-level
    # docs directory without a README, or breaking a link inside one, fails here.
    *[str(path.relative_to(ROOT)) for path in (ROOT / "docs").glob("*/README.md")],
    *[str(path.relative_to(ROOT)) for path in (ROOT / "docs/notes").glob("*.md")],
    *[str(path.relative_to(ROOT)) for path in (ROOT / "docs/design").glob("*.md")],
]


class NavigationTests(unittest.TestCase):
    def test_guides_exist(self):
        for name in GUIDES:
            with self.subTest(document=name):
                self.assertTrue((ROOT / name).is_file(), f"listed guide is missing: {name}")

    def test_populated_llm_lab_dirs_have_no_redundant_placeholder(self):
        for folder in ('configs', 'src/llm_lab', 'tests'):
            path = ROOT / 'labs/llm/train' / folder
            self.assertFalse((path / '.gitkeep').exists())
            self.assertTrue(any(item.is_file() for item in path.iterdir()))

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
