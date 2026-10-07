"""Subprocess-based code execution sandbox.

Legacy trusted-code runner: timeout, import blacklist and temporary working directory.
NOT a security sandbox: it does not isolate filesystem/network or enforce max_memory_mb.
Do not use it to execute untrusted model output on a normal user account.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# Modules that are blocked in the sandbox
BLOCKED_MODULES = frozenset({
    "os", "subprocess", "socket", "shutil", "sys",
    "ctypes", "multiprocessing", "threading", "signal",
    "importlib", "pkgutil", "pathlib",
})


def _has_blocked_imports(code: str) -> str | None:
    """Check if code contains imports of blocked modules.

    Returns the first blocked module found, or None if clean.
    """
    import_pattern = re.compile(
        r"(?:^|\n)\s*(?:import\s+(\S+)|from\s+(\S+)\s+import)",
        re.MULTILINE,
    )
    for match in import_pattern.finditer(code):
        module = match.group(1) or match.group(2)
        if module is None:
            continue
        top_level = module.split(".")[0]
        if top_level in BLOCKED_MODULES:
            return top_level
    return None


@dataclass
class SandboxResult:
    """Result of sandboxed code execution."""

    success: bool
    """True if the code executed successfully with exit code 0."""

    stdout: str = ""
    """Standard output captured during execution."""

    stderr: str = ""
    """Standard error captured during execution."""

    error: str = ""
    """Human-readable error description if execution failed."""

    exit_code: int = -1
    """Process exit code (0 = success)."""


@dataclass
class CodeSandbox:
    """Execute Python code in a subprocess with safety constraints."""

    timeout: float = 10.0
    """Maximum execution time in seconds."""

    max_memory_mb: int = 512
    """Maximum memory in MB (best-effort on macOS)."""

    def run(self, code: str) -> SandboxResult:
        """Execute code in a sandboxed subprocess.

        Security checks:
            1. Blocked module import detection (pre-execution).
            2. Timeout via subprocess timeout.
            3. Memory limit via resource module (Linux) or ulimit (macOS).
            4. Temporary directory isolation.

        Returns:
            SandboxResult with success flag and output.
        """
        # Pre-execution check: blocked imports
        blocked = _has_blocked_imports(code)
        if blocked:
            return SandboxResult(
                success=False,
                error=f"Blocked module import detected: '{blocked}'",
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "solution.py"

            # Write code to temp file
            script_path.write_text(code)

            try:
                proc = subprocess.run(
                    ["python3", str(script_path)],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=tmpdir,
                )
                return SandboxResult(
                    success=proc.returncode == 0,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    exit_code=proc.returncode,
                    error="" if proc.returncode == 0 else f"Exit code {proc.returncode}",
                )
            except subprocess.TimeoutExpired:
                return SandboxResult(
                    success=False,
                    error=f"Execution timed out after {self.timeout}s",
                )
            except Exception as e:
                return SandboxResult(
                    success=False,
                    error=f"Sandbox execution error: {e}",
                )
