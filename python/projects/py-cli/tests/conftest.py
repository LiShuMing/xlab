"""pytest fixtures for py-cli tests."""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def git_repo(temp_dir: Path) -> Path:
    """Create a temporary git repository with some commits."""
    import subprocess

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=temp_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=temp_dir,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    (temp_dir / "README.md").write_text("# Test Repo\n")
    subprocess.run(["git", "add", "."], cwd=temp_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=temp_dir,
        check=True,
        capture_output=True,
    )

    # Create a few more commits
    for i in range(3):
        (temp_dir / f"file{i}.txt").write_text(f"Content {i}\n")
        subprocess.run(
            ["git", "add", "."],
            cwd=temp_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", f"Add file {i}"],
            cwd=temp_dir,
            check=True,
            capture_output=True,
        )

    return temp_dir


@pytest.fixture
def mock_llm_config():
    """Mock LLM configuration."""
    from py_cli.config import LLMConfig

    return LLMConfig(
        api_key="test-api-key",
        model="claude-3-5-sonnet-20241022",
        max_tokens=1000,
        temperature=0.0,
    )


@pytest.fixture
def mock_analyzer_config():
    """Mock analyzer configuration."""
    from py_cli.config import AnalyzerConfig

    return AnalyzerConfig(
        default_days=30,
        max_commits=10,
        max_diff_size=10000,
        include_merge_commits=False,
    )
