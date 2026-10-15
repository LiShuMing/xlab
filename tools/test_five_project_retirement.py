"""Owner-authorized five-project retirement, independent of migration completeness."""
import json
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'docs/migrations/2026-10-15-five-project-retirement.json'
EXPECTED = {
    'rust/projects/fragment-tutor': 63,
    'rust/projects/umbra': 37,
    'rust/projects/subway-game': 57,
    'rust/projects/llm-runtime': 8,
    'python/projects/py-academic': 374,
}


class FiveProjectRetirementTests(unittest.TestCase):
    def test_exact_ledger_and_no_source_stubs(self):
        data = json.loads(LEDGER.read_text())
        self.assertEqual(data['roots'], EXPECTED)
        self.assertEqual(data['source_commit'], 'f20485e3b278e34df0b927c89dba1591d65ba6ba')
        self.assertEqual(len(data['entries']), 539)
        self.assertEqual(len({e['path'] for e in data['entries']}), 539)
        paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
        for root, count in EXPECTED.items():
            self.assertFalse((ROOT / root).exists(), root)
            self.assertFalse(any(p.startswith(root + '/') for p in paths))
            self.assertEqual(sum(e['path'].startswith(root + '/') for e in data['entries']), count)
        for entry in data['entries']:
            self.assertEqual(set(entry), {'path', 'mode', 'blob_sha'})
            self.assertIn(entry['mode'], {'100644', '100755'})
            self.assertRegex(entry['blob_sha'], r'^[0-9a-f]{40}$')

    def test_retained_inventory_and_active_routes(self):
        data = json.loads((ROOT / 'docs/meta/retained-projects.json').read_text())
        self.assertFalse(set(EXPECTED) & {e['path'] for e in data['projects']})
        for name in ('README.md', 'PROJECTS.md', 'AGENTS.md', 'rust/SKILL.md',
                     'docs/README.md', 'python/projects/llm-lab/README.md'):
            text = (ROOT / name).read_text()
            for target in re.findall(r'\]\(([^)]+)\)', text):
                self.assertFalse(any(root in target for root in EXPECTED), (name, target))
        tasks = (ROOT / 'TASKS.md').read_text()
        for root in EXPECTED:
            self.assertNotIn('#### Project: ' + root, tasks)
        for retained in ('python/projects/llm-lab', 'python/projects/py-lab',
                         'python/projects/py-numpy-pandas', 'rust/rlab', 'rust/rdb'):
            self.assertTrue((ROOT / retained).is_dir(), retained)

    def test_stale_local_copies_are_ignored(self):
        for root in EXPECTED:
            result = subprocess.run(['git', 'check-ignore', root + '/stale.txt'],
                                    cwd=ROOT, capture_output=True)
            self.assertEqual(result.returncode, 0, root)
        record = (ROOT / 'docs/migrations/2026-10-15-five-project-retirement.md').read_text()
        self.assertIn('regardless of destination', record)
        self.assertIn('does not assert destination equivalence', record)


if __name__ == '__main__':
    unittest.main()
