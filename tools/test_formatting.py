"""Offline fixtures for staged and committed first-party formatting checks."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CHECKER = Path(__file__).with_name('check_formatting.py').resolve()


class FormattingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='xlab formatting ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.write('base.txt', b'baseline\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'baseline')
        self.base = self.git('rev-parse', 'HEAD').strip()

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root).decode()

    def write(self, path, data):
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def check(self, *args):
        return subprocess.run([sys.executable, str(CHECKER), *args], cwd=self.root,
                              capture_output=True, text=True, timeout=20)

    def test_staged_spaces_filename(self):
        self.write('space name.py', b'x = 1 \n')
        self.git('add', '.')
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn('space name.py: added line has trailing whitespace', result.stderr)

    def test_clean_checkout_still_checks_committed_range(self):
        self.write('bad.py', b'x = 1 \n')
        self.git('add', '.')
        self.git('commit', '-qm', 'bad fixture')
        self.assertEqual(self.check().returncode, 0)
        result = self.check('--base', self.base, '--head', 'HEAD')
        self.assertEqual(result.returncode, 1)
        self.assertIn('trailing whitespace', result.stderr)

    def test_markdown_batch_binary_and_gitlink_exceptions(self):
        self.write('note.md', b'first  \nsecond\n')
        self.write('windows.bat', b'@echo off\r\n')
        self.write('image.bin', b'\x00\xffdata')
        self.git('add', '.')
        self.git('update-index', '--add', '--cacheinfo', '160000', '1234567890123456789012345678901234567890', 'reference')
        self.assertEqual(self.check().returncode, 0)

    def test_committed_absent_gitlink_object_is_skipped(self):
        self.git('update-index', '--add', '--cacheinfo', '160000',
                 '1234567890123456789012345678901234567890', 'missing reference')
        self.git('commit', '-qm', 'gitlink without local object')
        self.assertEqual(self.check('--base', self.base, '--head', 'HEAD').returncode, 0)

    def test_newline_crlf_and_indentation_errors(self):
        for path, data, message in [('missing.py', b'x=1', 'final newline'),
                                    ('crlf.py', b'x=1\r\n', 'LF line endings'),
                                    ('tabs.py', b' \tx=1\n', 'spaces before a tab')]:
            with self.subTest(path=path):
                self.write(path, data)
                self.git('add', path)
                result = self.check()
                self.assertEqual(result.returncode, 1)
                self.assertIn(message, result.stderr)
                self.git('reset', '-q')

    def test_deleted_and_imported_content_is_not_reformatted(self):
        self.git('rm', '-q', 'base.txt')
        for p in ('python/projects/py-academic/a.py', 'cc/thirdparty/a.txt',
                  'notebook.ipynb', 'uv.lock', 'src/robin_hood_map.h'):
            self.write(p, b'old legacy \r\nno newline')
        self.git('add', '.')
        self.assertEqual(self.check().returncode, 0)

    def test_unrelated_legacy_whitespace_is_not_rejected(self):
        self.write('old.py', b'old = 1 \nnew = 0\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'legacy whitespace')
        base = self.git('rev-parse', 'HEAD').strip()
        self.write('old.py', b'old = 1 \nnew = 2\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'good changed line')
        self.assertEqual(self.check('--base', base, '--head', 'HEAD').returncode, 0)

    def test_workflow_checks_all_code_changes(self):
        workflow = CHECKER.parents[1] / '.github/workflows/repository-checks.yml'
        triggers = workflow.read_text().split('permissions:', 1)[0]
        self.assertIn('  pull_request:', triggers)
        self.assertIn('  push:', triggers)
        self.assertNotIn('paths:', triggers)
        self.assertNotIn('paths-ignore:', triggers)

    def test_empty_tree_range_checks_root_commit(self):
        empty_tree = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'
        self.assertEqual(self.check('--base', empty_tree, '--head', self.base).returncode, 0)
        result = subprocess.check_output(
            ['bash', '-c', 'git rev-parse --verify "$1^" 2>/dev/null || printf "%s" "$2"',
             'fixture', self.base, empty_tree], cwd=self.root).decode()
        self.assertEqual(result, empty_tree)

    def test_bad_ref_and_incomplete_range_fail_closed(self):
        self.assertEqual(self.check('--base', self.base).returncode, 2)
        self.assertEqual(self.check('--base', '--not-a-ref', '--head', 'HEAD').returncode, 2)


if __name__ == '__main__':
    unittest.main()
