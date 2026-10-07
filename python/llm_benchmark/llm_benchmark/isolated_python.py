"""Namespace-isolated Python execution for small HumanEval candidates on Linux.

No network, no home/repository mount, read-only runtime, dropped capabilities and
resource limits. This is not a VM or a general hostile-code execution service.
"""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from llm_benchmark.runner.sandbox import SandboxResult


class IsolatedPython:
    def __init__(self, executable: Path | None = None, timeout: float = 10) -> None:
        local = Path(__file__).resolve().parents[1] / ".tools/bwrap/usr/bin/bwrap"
        found = shutil.which("bwrap")
        self.executable = executable or (Path(found) if found else local)
        self.timeout = timeout
        if sys.platform != "linux" or not self.executable.is_file():
            raise RuntimeError("Linux Bubblewrap is required; no unsafe subprocess fallback")
        if not shutil.which("prlimit"):
            raise RuntimeError("prlimit is required for code evaluation")

    def run(self, code: str) -> SandboxResult:
        with tempfile.TemporaryDirectory(prefix="strata-code-") as directory:
            work = Path(directory)
            source = work / "solution.py"
            source.write_text(code, encoding="utf-8")
            command = [
                str(self.executable),
                "--unshare-all",
                "--unshare-user",
                "--die-with-parent",
                "--new-session",
                "--disable-userns",
                "--cap-drop",
                "ALL",
                "--clearenv",
                "--ro-bind",
                "/usr",
                "/usr",
                "--ro-bind",
                str(work),
                "/work",
                "--proc",
                "/proc",
                "--dev",
                "/dev",
                "--size",
                "8388608",
                "--tmpfs",
                "/tmp",
            ]
            # Support merged-/usr and distributions with separate library directories.
            for name in ("bin", "lib", "lib64"):
                path = Path("/" + name)
                if path.is_symlink():
                    command.extend(["--symlink", str(path.readlink()), "/" + name])
                elif path.exists():
                    command.extend(["--ro-bind", str(path), "/" + name])
            command.extend(
                [
                    "--setenv",
                    "PATH",
                    "/usr/bin:/bin",
                    "--setenv",
                    "LANG",
                    "C.UTF-8",
                    "--chdir",
                    "/work",
                    "--remount-ro",
                    "/",
                    "--",
                    "/usr/bin/prlimit",
                    "--as=268435456",
                    "--cpu=5",
                    "--fsize=1048576",
                    "--nofile=64",
                    "--nproc=128",
                    "--core=0",
                    "--",
                    "/usr/bin/python3",
                    "-I",
                    "-S",
                    "-B",
                    "/work/solution.py",
                ]
            )
            # File-backed capture is bounded by RLIMIT_FSIZE; pipes could grow without bound.
            with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
                try:
                    result = subprocess.run(
                        command,
                        stdin=subprocess.DEVNULL,
                        stdout=stdout,
                        stderr=stderr,
                        timeout=self.timeout,
                        close_fds=True,
                    )
                except subprocess.TimeoutExpired:
                    return SandboxResult(success=False, error="isolated execution timed out")
                stdout.seek(0)
                stderr.seek(0)
                out = stdout.read(65536).decode("utf-8", errors="replace")
                err = stderr.read(65536).decode("utf-8", errors="replace")
            return SandboxResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=out,
                stderr=err,
                error="" if result.returncode == 0 else "isolated execution failed",
            )

    def preflight(self) -> None:
        """Check the policy before submitting or executing generated candidates."""
        probe = self.run(
            "import os, socket\n"
            "assert not os.path.exists('/home/lism/work/xlab/AGENTS.md')\n"
            "assert not os.path.exists('/mnt/c')\n"
            "assert os.environ.get('HF_TOKEN') is None\n"
            "try:\n    open('/usr/strata-write-probe', 'w')\n"
            "except OSError:\n    pass\n"
            "else:\n    raise AssertionError('runtime writable')\n"
            "try:\n    socket.create_connection(('127.0.0.1', 8080), timeout=1)\n"
            "except OSError:\n    pass\n"
            "else:\n    raise AssertionError('host network reachable')\n"
            "print('ISOLATION_OK')\n"
        )
        if not probe.success or "ISOLATION_OK" not in probe.stdout:
            raise RuntimeError(f"Isolation policy probe failed: {probe.error} {probe.stderr}")


def candidate_code(response: str, task: dict) -> str:
    """Accept full-function chat answers or body-only HumanEval completions."""
    import re

    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", response, flags=re.S)
    code = blocks[0] if blocks else response
    code = code.rstrip() + "\n"
    try:
        tree = ast.parse(code)
    except (SyntaxError, IndentationError):
        tree = None
    if tree and any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == task["entry_point"]
        for node in tree.body
    ):
        # Keep the official prompt's import prefix if the answer omits imports.
        prefix = task["prompt"].split("def ", 1)[0]
        return prefix + code
    return task["prompt"] + code


def grade_candidate(response: str, task: dict, sandbox: IsolatedPython) -> dict:
    code = candidate_code(response, task)
    marker = "TESTS_PASSED_" + uuid.uuid4().hex
    script = code + "\n" + task["test"] + "\n"
    script += f"check({task['entry_point']})\nprint({json.dumps(marker)})\n"
    result = sandbox.run(script)
    return {
        "passed": result.success and marker in result.stdout.splitlines(),
        "candidate_code": code,
        "exit_code": result.exit_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "execution_error": result.error,
    }
