#!/usr/bin/env python3
"""Guard the bounded Python retirement without network or runtime side effects."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / 'docs/migrations/2026-10-14-python-source-retirement.json'


class PythonRetirementTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads(RECORD.read_text())

    def test_exact_roots_and_inventory(self):
        counts = {'py-cli': 46, 'py-tools': 3, 'py-optimizer1': 95,
                  'py-optimizer2': 36, 'py-pia': 67, 'py-report': 35}
        self.assertEqual(self.record['file_count'], 282)
        self.assertEqual(len(self.record['files']), 282)
        self.assertEqual(len({x['source_path'] for x in self.record['files']}), 282)
        self.assertEqual(set(self.record['retired_roots']),
                         {'python/projects/' + x for x in counts})
        for name, count in counts.items():
            prefix = 'python/projects/' + name + '/'
            self.assertFalse((ROOT / prefix).exists(), prefix)
            self.assertEqual(sum(x['source_path'].startswith(prefix)
                                 for x in self.record['files']), count)
        self.assertEqual(self.record['dispositions'],
                         {'copied': 52, 'adapted': 189, 'excluded': 41})
        for item in self.record['files']:
            self.assertRegex(item['source_git_blob'], r'^[0-9a-f]{40}$')
            self.assertIn(item['source_mode'], ('100644', '100755'))
            self.assertIn(item['disposition'], ('copied', 'adapted', 'excluded'))
            if item['disposition'] == 'excluded':
                self.assertIsNone(item['destination_path'])
                self.assertTrue(item['reason'])
            else:
                self.assertRegex(item['destination_git_blob'], r'^[0-9a-f]{40}$')
                self.assertTrue(item['destination_path'])

    def test_acceptance_and_backup_receipts(self):
        self.assertEqual(self.record['backup_commit'],
                         'fd15e65059ff7d0d01ed48b6347cd75881fb4b36')
        self.assertEqual(set(self.record['targets']), {'lyra', 'vela', 'carina'})
        for target in self.record['targets'].values():
            self.assertTrue(target['ci'])
            for run in target['ci']:
                self.assertEqual(run['head_sha'], target['commit'])
                self.assertEqual(run['status'], 'completed')
                self.assertEqual(run['conclusion'], 'success')

    def test_current_routes_do_not_link_to_retired_sources(self):
        for name in ('README.md', 'PROJECTS.md', 'AGENTS.md', 'TASKS.md',
                     'docs/README.md', 'python/SKILL.md'):
            source = (ROOT / name).read_text()
            for target in re.findall(r'\]\(([^)]+)\)', source):
                self.assertFalse(any(root in target for root in self.record['retired_roots']),
                                 (name, target))
        self.assertNotIn('cd python/projects/py-report', (ROOT / 'AGENTS.md').read_text())
        for name in ('py-pia', 'py-report'):
            self.assertNotIn('#### Project: python/projects/' + name,
                             (ROOT / 'TASKS.md').read_text())

    def test_retained_neighbors_and_recovery(self):
        for name in ('py-lab', 'py-toydb'):
            self.assertTrue((ROOT / 'python/projects' / name).is_dir())
        # Consolidated cleanup later removes the legacy scheduler without a stub.
        self.assertFalse((ROOT / 'python/projects/cron.sh').exists())
        text = (RECORD.with_suffix('.md')).read_text()
        self.assertIn('git revert', text)
        self.assertIn('67', text)
        self.assertIn('cron.sh', text)


if __name__ == '__main__':
    unittest.main()
