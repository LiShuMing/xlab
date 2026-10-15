"""Offline guards for the bounded books/email/learning source retirement."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / 'docs/migrations/2026-10-14-books-email-learning-retirement.json'


class BooksEmailLearningRetirementTests(unittest.TestCase):
    def test_inventory_and_dispositions(self):
        record = json.loads(RECORD.read_text())
        rows = record['files']
        self.assertEqual(len(rows), 174)
        self.assertEqual(len({r['source_path'] for r in rows}), 174)
        self.assertEqual(sum(r['disposition'] == 'excluded' for r in rows), 13)
        self.assertEqual(sum(bool(r['destinations']) for r in rows), 161)
        counts = {'docs/books/codex-code-book': 20, 'docs/books/deep-linux-book': 76,
                  'python/projects/py-email': 57, 'python/projects/py-learn': 21}
        self.assertEqual(set(record['retired_roots']), set(counts))
        for root, count in counts.items():
            self.assertFalse((ROOT / root).exists())
            self.assertEqual(sum(r['source_path'].startswith(root + '/') for r in rows), count)
        for row in rows:
            self.assertRegex(row['source_git_blob'], r'^[a-f0-9]{40}$')
            self.assertRegex(row['source_sha256'], r'^[a-f0-9]{64}$')
            self.assertTrue(row['reason'])
            if row['disposition'] == 'excluded':
                self.assertEqual(row['destinations'], [])

    def test_acceptance_recovery_and_routes(self):
        record = json.loads(RECORD.read_text())
        self.assertEqual(record['backup_commit'], 'fd15e65059ff7d0d01ed48b6347cd75881fb4b36')
        for target in record['targets'].values():
            self.assertTrue(target['ci'])
            for run in target['ci']:
                self.assertEqual(run['head_sha'], target['commit'])
                self.assertEqual((run['status'], run['conclusion']), ('completed', 'success'))
        for name in ('README.md', 'PROJECTS.md', 'AGENTS.md', 'TASKS.md', 'docs/README.md', 'python/SKILL.md'):
            for url in re.findall(r'\]\(([^)]+)\)', (ROOT / name).read_text()):
                self.assertFalse(any(root in url for root in record['retired_roots']), (name, url))
        self.assertTrue((ROOT / 'python/projects/cron.sh').is_file())
        text = RECORD.with_suffix('.md').read_text()
        for term in ('git revert', 'unsupported', '13', '174', '161'):
            self.assertIn(term, text)


if __name__ == '__main__':
    unittest.main()
