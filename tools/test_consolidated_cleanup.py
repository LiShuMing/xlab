"""Offline invariants for consolidated maintenance and retention decisions."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ConsolidatedCleanupTests(unittest.TestCase):
    def test_legacy_cron_is_removed_without_a_stub(self):
        self.assertFalse((ROOT / 'python/projects/cron.sh').exists())
        text = (ROOT / 'docs/meta/repository-cleanup.md').read_text()
        self.assertIn('removed without a replacement stub', text)
        self.assertIn('inspected or changed', text)
        self.assertIn('missing-file error', text)
        self.assertIn('5d9e779b2e63295a56d120b4cd63ee6489c135c9', text)

    def test_project_inventory_matches_retained_tree(self):
        record = json.loads((ROOT / 'docs/meta/retained-projects.json').read_text())
        entries = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
        for row in record['projects']:
            with self.subTest(project=row['path']):
                self.assertEqual(row['disposition'], 'retain')
                self.assertEqual(sum(p.startswith(row['path'] + '/') for p in entries), row['tracked_entries'])
    def test_dependency_declarations_are_accounted_for(self):
        import configparser
        record = json.loads((ROOT / 'docs/meta/dependency-declarations.json').read_text())
        entries = record['entries']
        self.assertEqual(len(entries), 69)
        self.assertEqual(len({r['path'] for r in entries}), 69)
        config = configparser.ConfigParser()
        config.read(ROOT / '.gitmodules')
        self.assertEqual(len(config.sections()), 40)
        for row in entries:
            section = row['section_name']
            if row['recommendation'] == 'archive-declaration':
                self.assertNotIn(section, config)
                self.assertIsNone(row['gitlink_sha'])
            else:
                self.assertEqual(config[section]['path'], row['path'])
                self.assertEqual(config[section]['url'], row['original_url'])
        self.assertEqual(sum(r['recommendation'] == 'archive-declaration' for r in entries), 29)
        self.assertEqual(sum(r['orphan'] and r['recommendation'] == 'retain' for r in entries), 38)
        for path in ('cc/thirdparty/glog', 'cc/thirdparty/abseil-cpp', 'cc/thirdparty/fmt',
                     'cc/thirdparty/folly', 'cc/thirdparty/fast_float'):
            self.assertEqual(next(r['recommendation'] for r in entries if r['path'] == path), 'retain')
        ci = (ROOT / '.github/workflows/repository-checks.yml').read_text()
        self.assertIn('"$failures" -ne 38', ci)
        self.assertIn('"$orphans" -ne 38', ci)
        # All paths, including retired entry points, must trigger these checks.
        triggers = ci.split('permissions:', 1)[0]
        self.assertIn('  pull_request:', triggers)
        self.assertIn('  push:', triggers)
        self.assertNotIn('paths:', triggers)
        self.assertNotIn('paths-ignore:', triggers)

    def test_cleanup_document_links_resolve(self):
        from urllib.parse import urlsplit, unquote
        for name in ('repository-cleanup.md', 'retained-projects.md', 'dependency-declarations.md'):
            path = ROOT / 'docs/meta' / name
            for target in re.findall(r'\]\(([^)]+)\)', path.read_text()):
                parsed = urlsplit(target)
                if not parsed.scheme and parsed.path:
                    self.assertTrue((path.parent / unquote(parsed.path)).exists(), (name, target))

    def test_active_task_list_does_not_create_existing_files(self):
        for target in re.findall(r'- \[ \] 创建 `([^`]+)`', (ROOT / 'TASKS.md').read_text()):
            # Directory-layout proposals are not file-creation assertions.
            if not target.endswith('/'):
                self.assertFalse((ROOT / target).is_file(), target)
        text = (ROOT / 'TASKS.md').read_text()
        self.assertNotIn('12 本书约 9.5 万行', text)
        self.assertNotIn('subway-game 仅 26 行', text)
        self.assertIn('py-numpy-pandas` 有 8 个跟踪文件', text)


if __name__ == '__main__':
    unittest.main()
