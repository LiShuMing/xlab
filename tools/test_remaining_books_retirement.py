"""Offline guards for accepted 76-file book retirement; no private bodies."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / 'docs/migrations/2026-10-15-remaining-books-retirement.json'


class RemainingBooksRetirementTests(unittest.TestCase):
    def test_exact_retirement_roots_and_public_schema(self):
        record = json.loads(RECORD.read_text())
        roots = {'docs/books/calcite-code-book': 22, 'docs/books/risingwave-book': 12,
                 'docs/books/claude-code-internals': 21, 'docs/books/feiman-book': 21}
        self.assertEqual(record['retired_roots'], roots)
        self.assertEqual(len(record['files']), 76)
        self.assertEqual(len({r['source_path'] for r in record['files']}), 76)
        self.assertFalse((ROOT / 'docs/books').exists())
        for root, count in roots.items():
            self.assertEqual(sum(r['source_path'].startswith(root + '/') for r in record['files']), count)
        fields = {'source_path', 'source_git_blob', 'source_sha256', 'source_mode',
                  'destination_path', 'destination_git_blob', 'destination_sha256'}
        for row in record['files']:
            self.assertEqual(set(row), fields)  # No manuscript bodies or private editorial metadata.
            self.assertEqual(row['source_mode'], '100644')
            self.assertEqual(row['destination_path'], row['source_path'].removeprefix('docs/'))
            for field in ('source_git_blob', 'destination_git_blob'):
                self.assertRegex(row[field], r'^[a-f0-9]{40}$')
            for field in ('source_sha256', 'destination_sha256'):
                self.assertRegex(row[field], r'^[a-f0-9]{64}$')

    def test_accepted_commit_ci_and_recovery(self):
        record = json.loads(RECORD.read_text())
        self.assertEqual(record['destination_commit'], 'ad36e55ea612f9a4a8fec3552f4a874610ab05f0')
        self.assertEqual(record['destination_tree'], '25d3103cf2d76dc4dfd31d1f6c48dab0aba1f872')
        self.assertEqual(record['ci']['head_sha'], record['destination_commit'])
        self.assertEqual((record['ci']['status'], record['ci']['conclusion']), ('completed', 'success'))
        self.assertEqual(record['source_commit'], 'bf3e2ed45c12cc551fd44ef3cb89366970cd92ba')
        self.assertEqual(record['backup_commit'], 'fd15e65059ff7d0d01ed48b6347cd75881fb4b36')
        text = RECORD.with_suffix('.md').read_text()
        for term in ('git revert', 'without stubs', 'not secure erasure', '76'):
            self.assertIn(term, text)

    def test_maintained_navigation_routes_to_destination(self):
        import re
        from urllib.parse import urlsplit, unquote
        for name in ('README.md', 'PROJECTS.md', 'AGENTS.md', 'TASKS.md', 'docs/README.md',
                     'docs/meta/repository-cleanup.md', 'docs/meta/retained-projects.md',
                     'docs/migrations/2026-10-15-remaining-books-retirement.md'):
            path = ROOT / name
            for target in re.findall(r'\]\(([^)]+)\)', path.read_text()):
                parsed = urlsplit(target)
                if not parsed.scheme and parsed.path:
                    self.assertTrue((path.parent / unquote(parsed.path)).exists(), (name, target))


if __name__ == '__main__':
    unittest.main()
