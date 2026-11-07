"""Tests for code sandbox."""

from __future__ import annotations

import pytest

from llm_benchmark.runner.sandbox import CodeSandbox, SandboxResult, _has_blocked_imports


class TestHasBlockedImports:
    def test_clean_code(self):
        assert _has_blocked_imports("import math\nprint(1+1)") is None

    def test_blocked_import(self):
        assert _has_blocked_imports("import os\nos.system('ls')") == "os"

    def test_blocked_from_import(self):
        assert _has_blocked_imports("from os import path") == "os"

    def test_blocked_submodule(self):
        assert _has_blocked_imports("import os.path") == "os"

    def test_multiple_imports(self):
        code = "import math\nimport subprocess"
        assert _has_blocked_imports(code) == "subprocess"


class TestSandbox:
    @pytest.fixture
    def sandbox(self):
        return CodeSandbox(timeout=5.0)

    def test_simple_execution(self, sandbox):
        result = sandbox.run("print('hello')")
        assert result.success
        assert "hello" in result.stdout

    def test_math_computation(self, sandbox):
        result = sandbox.run("x = 2 + 2\nassert x == 4")
        assert result.success

    def test_failing_assertion(self, sandbox):
        result = sandbox.run("x = 2 + 2\nassert x == 5")
        assert not result.success
        assert result.exit_code != 0

    def test_blocked_import_blocked(self, sandbox):
        result = sandbox.run("import os\nprint('never')")
        assert not result.success
        assert "Blocked" in result.error

    def test_syntax_error(self, sandbox):
        result = sandbox.run("def broken(")
        assert not result.success

    def test_timeout(self, sandbox):
        sandbox.timeout = 0.5
        result = sandbox.run("import time\ntime.sleep(10)")
        assert not result.success
        assert "timed out" in result.error.lower()