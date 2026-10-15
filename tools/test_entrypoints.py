"""Offline placeholder and missing-prerequisite guards; no deployment/browser use."""
import ast
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class EntryPointTests(unittest.TestCase):
    def test_no_tracked_gitkeep_or_duplicate_java_readme(self):
        paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
        self.assertFalse(any(p.endswith('/.gitkeep') for p in paths))
        self.assertFalse((ROOT / 'java/xlab-itest/README').exists())
        self.assertTrue((ROOT / 'java/xlab-itest/README.md').is_file())
        # Semantic package and Rust module markers are not directory placeholders.
        self.assertTrue((ROOT / 'python/projects/py-torch/micrograd/__init__.py').is_file())
        self.assertTrue((ROOT / 'rust/rlab/tools/leetcode/src/problem/mod.rs').is_file())

    def test_go_help_matches_available_targets(self):
        path = ROOT / 'cc/golab'
        text = (path / 'Makefile').read_text()
        self.assertNotIn('go mod tidy', text)
        self.assertNotIn('PROG=', text)
        self.assertNotIn('MODULE :=', text)
        if shutil.which('make'):
            help_result = subprocess.run(['make', 'help'], cwd=path, capture_output=True, text=True, timeout=5)
            self.assertEqual(help_result.returncode, 0)
            self.assertIn('make leetcode_433', help_result.stdout)
            self.assertNotIn('tidy', help_result.stdout)

    def test_extension_preflight_fails_before_writes(self):
        source = ROOT / 'cc/extentions/gpt-extension/tools/build.py'
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'tools').mkdir()
            shutil.copy2(source, root / 'tools/build.py')
            result = subprocess.run([sys.executable, str(root / 'tools/build.py')], cwd=root,
                                    capture_output=True, text=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('manifest.json', result.stderr)
            self.assertIn('rules.json', result.stderr)
            self.assertIn('No output was written', result.stderr)
            self.assertEqual(sorted(p.name for p in root.iterdir()), ['tools'])
        assignments = [n for n in ast.parse(source.read_text()).body if isinstance(n, ast.Assign)]
        files = next(ast.literal_eval(n.value) for n in assignments
                     if any(isinstance(t, ast.Name) and t.id == 'SRC_FILES' for t in n.targets))
        self.assertIn('defaults.js', files)

    def test_deployment_missing_migrations_fails_before_docker(self):
        source = ROOT / 'python/projects/py-ego/py-ego-miniapp/deploy/scripts/deploy.sh'
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scripts = root / 'deploy/scripts'
            scripts.mkdir(parents=True)
            shutil.copy2(source, scripts / 'deploy.sh')
            result = subprocess.run(['/bin/bash', str(scripts / 'deploy.sh')], cwd=root / 'deploy',
                                    env={**os.environ, 'HOME': str(root)}, capture_output=True,
                                    text=True, timeout=5)
            self.assertEqual(result.returncode, 2)
            self.assertIn('missing migration prerequisite alembic.ini', result.stdout)
            self.assertIn('No deployment was attempted', result.stdout)
            self.assertEqual(sorted(p.name for p in root.iterdir()), ['deploy'])
        self.assertNotIn('alembic upgrade head ||', source.read_text())


if __name__ == '__main__':
    unittest.main()
