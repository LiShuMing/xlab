"""Policy and grading checks; skip real namespace tests when the helper is absent."""

import pytest

from llm_benchmark.isolated_python import IsolatedPython, candidate_code, grade_candidate


@pytest.fixture
def sandbox():
    try:
        value = IsolatedPython(timeout=3)
    except RuntimeError as exc:
        pytest.skip(str(exc))
    value.preflight()
    return value


def task():
    return {
        "entry_point": "add",
        "prompt": 'def add(a, b):\n    """Add numbers."""\n',
        "test": "def check(candidate):\n    assert candidate(1, 2) == 3\n",
    }


def test_candidate_forms():
    sample = task()
    assert "return a + b" in candidate_code("    return a + b\n", sample)
    assert "def add" in candidate_code("```python\ndef add(a, b):\n    return a + b\n```", sample)


def test_actual_isolation_and_correctness(sandbox):
    assert grade_candidate("def add(a, b):\n    return a + b\n", task(), sandbox)["passed"]
    assert not grade_candidate("def add(a, b):\n    return a - b\n", task(), sandbox)["passed"]
    assert not grade_candidate("raise SystemExit(0)\n", task(), sandbox)["passed"]


def test_memory_limit(sandbox):
    result = sandbox.run("payload = bytearray(1024 * 1024 * 1024)\n")
    assert not result.success and "MemoryError" in result.stderr


def test_cpu_or_wall_limit(sandbox):
    assert not sandbox.run("while True: pass\n").success


def test_private_host_file_and_environment_not_visible(sandbox, tmp_path, monkeypatch):
    private = tmp_path / "private-canary.txt"
    private.write_text("private test data", encoding="utf-8")
    monkeypatch.setenv("HF_TOKEN", "test-secret-not-for-child")
    sandbox.preflight()
    result = sandbox.run(f"from pathlib import Path\nassert not Path({str(private)!r}).exists()\n")
    assert result.success
