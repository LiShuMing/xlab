"""Offline placeholder and missing-prerequisite guards; no deployment/browser use."""
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

    def test_portable_build_script_selects_sanitizer_and_runs_tests(self):
        script = ROOT / 'cc/cclab/build.sh'
        modes = {'ASAN': 'address', 'UBSAN': 'undefined', 'LSAN': 'leak', 'RELEASE': 'none'}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            log = root / 'commands'
            # Capture CLI arguments without a compiler, network or source writes.
            for name in ('cmake', 'ctest'):
                tool = root / name
                tool.write_text(f'#!{sys.executable}\n'
                                'import os, sys\n'
                                'with open(os.environ["XLAB_TEST_LOG"], "a") as f:\n'
                                '    f.write(repr(sys.argv) + "\\n")\n')
                tool.chmod(0o755)
            for mode, sanitizer in modes.items():
                with self.subTest(mode=mode):
                    log.write_text('')
                    result = subprocess.run(['bash', str(script), mode], capture_output=True,
                                            text=True, timeout=5, env={
                                                **os.environ, 'CMAKE_BIN': str(root / 'cmake'),
                                                'CTEST_BIN': str(root / 'ctest'),
                                                'BUILD_DIR': str(root / 'build'),
                                                'CCLAB_PORTABLE_ONLY': 'ON', 'GCC_HOME': '',
                                                'XLAB_TEST_LOG': str(log),
                                            })
                    self.assertEqual(result.returncode, 0, result.stderr)
                    commands = log.read_text().splitlines()
                    self.assertEqual(len(commands), 3)
                    self.assertIn('-DXLAB_SANITIZER=' + sanitizer, commands[0])
                    self.assertIn('--build', commands[1])
                    self.assertIn('--no-tests=error', commands[2])

    def test_portable_build_script_stops_on_configure_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tool = root / 'cmake'
            tool.write_text('#!/bin/sh\nexit 7\n')
            tool.chmod(0o755)
            result = subprocess.run(['bash', str(ROOT / 'cc/cclab/build.sh'), 'UBSAN'],
                                    env={**os.environ, 'CMAKE_BIN': str(tool), 'GCC_HOME': '',
                                         'CTEST_BIN': str(root / 'must-not-run')},
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 7, result.stderr)

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
