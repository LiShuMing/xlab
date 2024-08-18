"""Tests for GitClient."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from py_cli.core.git_client import GitClient
from py_cli.exceptions import GitError


class TestGitClient:
    """Tests for GitClient class."""

    def test_init_valid_repo(self, git_repo: Path) -> None:
        """Test initializing with a valid git repo."""
        client = GitClient(git_repo)
        assert client.repo_path == git_repo.resolve()

    def test_init_invalid_repo(self, temp_dir: Path) -> None:
        """Test initializing with a non-git directory."""
        with pytest.raises(GitError, match="Not a git repository"):
            GitClient(temp_dir)

    def test_get_commits(self, git_repo: Path) -> None:
        """Test getting commits."""
        client = GitClient(git_repo)
        commits = client.get_commits()

        assert len(commits) == 4  # Initial + 3 commits

        # Check first commit (most recent)
        first = commits[0]
        assert first.message.startswith("Add file")
        assert first.author == "Test User"
        assert len(first.files_changed) > 0

    def test_get_commits_with_date_range(self, git_repo: Path) -> None:
        """Test getting commits within a date range."""
        client = GitClient(git_repo)

        # Get commits from the past
        since = datetime.now(timezone.utc) - timedelta(days=1)
        commits = client.get_commits(since=since)

        # Should get all commits
        assert len(commits) == 4

        # Get commits from future (should be empty)
        since = datetime.now(timezone.utc) + timedelta(days=1)
        commits = client.get_commits(since=since)
        assert len(commits) == 0

    def test_get_commits_max_count(self, git_repo: Path) -> None:
        """Test max_count parameter."""
        client = GitClient(git_repo)
        commits = client.get_commits(max_count=2)

        assert len(commits) == 2

    def test_get_repo_name_from_directory(self, git_repo: Path) -> None:
        """Test getting repo name from directory."""
        client = GitClient(git_repo)
        name = client.get_repo_name()

        assert name == git_repo.name

    def test_get_stats(self, git_repo: Path) -> None:
        """Test getting repository statistics."""
        client = GitClient(git_repo)
        stats = client.get_stats()

        assert stats.total_commits == 4
        assert "Test User" in stats.authors
        assert len(stats.files_changed) >= 4  # README + 3 files
