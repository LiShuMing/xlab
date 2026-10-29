"""Check bootstrap boundaries without downloading or installing toolchains."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FunctionalLearningTests(unittest.TestCase):
    def test_invalid_target_has_no_install_side_effect(self):
        with tempfile.TemporaryDirectory() as temp:
            install_root = Path(temp) / 'must-not-be-created'
            result = subprocess.run(
                ['bash', str(ROOT / 'tools/setup-learning.sh'), 'unknown'],
                env={**os.environ, 'XLAB_LEARNING_HOME': str(install_root)},
                capture_output=True, text=True, timeout=5,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn('Usage:', result.stderr)
            self.assertFalse(install_root.exists())

    def test_activation_respects_custom_location_and_existing_opam(self):
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run(
                ['bash', '-c', 'source "$1"; printf "%s\\n" "$OPAMROOT" "$OPAMSWITCH" "$ELAN_HOME" "$PATH"',
                 'learning-env', str(ROOT / 'tools/learning-env.sh')],
                env={**os.environ, 'XLAB_LEARNING_HOME': temp,
                     'OPAMROOT': '/existing/opam', 'OPAMSWITCH': 'existing-switch'},
                capture_output=True, text=True, timeout=5,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            root, switch, elan, path = result.stdout.splitlines()
            self.assertEqual(root, '/existing/opam')
            self.assertEqual(switch, 'existing-switch')
            self.assertEqual(elan, str(Path(temp) / 'elan'))
            self.assertTrue(path.startswith(str(Path(temp) / 'ocaml/5.5.2/bin') + ':'))

    def test_source_lean_uses_its_compiler_without_changing_global_cc(self):
        with tempfile.TemporaryDirectory() as temp:
            build = Path(temp) / 'sources/lean-4.35.0/build/xlab-release'
            (build / 'stage1').mkdir(parents=True)
            (build / '.xlab-complete').touch()
            (build / 'stage1/CMakeCache.txt').write_text('CMAKE_C_COMPILER:FILEPATH=/test/clang\n')
            for explicit, expected in [('', '/test/clang'), ('/user/compiler', '/user/compiler')]:
                with self.subTest(explicit=explicit):
                    result = subprocess.run(
                        ['bash', '-c', 'source "$1"; printf "%s\\n" "$LEAN_CC" "$CC" "$CXX"',
                         'learning-env', str(ROOT / 'tools/learning-env.sh')],
                        env={**os.environ, 'XLAB_LEARNING_HOME': temp, 'LEAN_CC': explicit,
                             'CC': '/existing/cc', 'CXX': '/existing/cxx'},
                        capture_output=True, text=True, timeout=5,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.splitlines(), [expected, '/existing/cc', '/existing/cxx'])


if __name__ == '__main__':
    unittest.main()
