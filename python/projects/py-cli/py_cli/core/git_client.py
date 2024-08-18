"""Git operations wrapper for py-cli."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from py_cli.exceptions import GitError

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True)
class CommitInfo:
    """Information about a git commit."""

    sha: str
    short_sha: str
    author: str
    date: datetime
    message: str
    files_changed: list[str]
    diff: str


@dataclass(frozen=True)
class GitStats:
    """Statistics for a set of commits."""

    total_commits: int
    authors: set[str]
    files_changed: set[str]
    additions: int
    deletions: int


class GitClient:
    """Client for git operations."""

    def __init__(self, repo_path: Path) -> None:
        """Initialize git client.

        Args:
            repo_path: Path to the git repository

        Raises:
            GitError: If path is not a valid git repository
        """
        self.repo_path = repo_path.resolve()
        self._validate_repo()

    def _validate_repo(self) -> None:
        """Validate that the path is a git repository."""
        git_dir = self.repo_path / ".git"
        if not git_dir.exists():
            msg = f"Not a git repository: {self.repo_path}"
            raise GitError(msg)

    def _run_git(self, args: Sequence[str], cwd: Path | None = None) -> str:
        """Run a git command and return output.

        Args:
            args: Git command arguments
            cwd: Working directory (defaults to repo_path)

        Returns:
            Command stdout as string

        Raises:
            GitError: If command fails
        """
        cmd = ["git", *args]
        working_dir = cwd or self.repo_path

        try:
            result = subprocess.run(
                cmd,
                cwd=working_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            msg = f"Git command failed: {' '.join(cmd)}\nError: {e.stderr}"
            raise GitError(msg) from e
        except FileNotFoundError as e:
            msg = "Git command not found. Please install git."
            raise GitError(msg) from e

    def get_commits(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
        max_count: int = 100,
        include_merges: bool = False,
    ) -> list[CommitInfo]:
        """Get commits within a date range.

        Args:
            since: Start date (inclusive)
            until: End date (inclusive)
            max_count: Maximum number of commits to retrieve
            include_merges: Whether to include merge commits

        Returns:
            List of commit information
        """
        # Build log command
        format_str = (
            "%H%x00%an%x00%ai%x00%s%x00"  # sha, author, date, subject
        )

        args = [
            "log",
            f"--format={format_str}",
            f"--max-count={max_count}",
        ]

        if not include_merges:
            args.append("--no-merges")

        if since:
            since_str = since.strftime("%Y-%m-%d %H:%M:%S")
            args.extend(["--since", since_str])

        if until:
            until_str = until.strftime("%Y-%m-%d %H:%M:%S")
            args.extend(["--until", until_str])

        output = self._run_git(args)

        if not output:
            return []

        commits: list[CommitInfo] = []
        for line in output.split("\n"):
            if not line.strip():
                continue

            parts = line.split("\x00")
            if len(parts) < 4:
                continue

            sha, author, date_str, message = parts[0], parts[1], parts[2], parts[3]

            # Parse date
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z")
                date = date.astimezone(timezone.utc)
            except ValueError:
                date = datetime.now(timezone.utc)

            # Get files changed in this commit
            files_changed = self._get_commit_files(sha)

            # Get diff for this commit
            diff = self._get_commit_diff(sha)

            commits.append(
                CommitInfo(
                    sha=sha,
                    short_sha=sha[:7],
                    author=author,
                    date=date,
                    message=message,
                    files_changed=files_changed,
                    diff=diff,
                )
            )

        return commits

    def _get_commit_files(self, sha: str) -> list[str]:
        """Get list of files changed in a commit."""
        try:
            output = self._run_git(
                ["diff-tree", "--no-commit-id", "--name-only", "-r", sha]
            )
            return [f for f in output.split("\n") if f.strip()]
        except GitError:
            return []

    def _get_commit_diff(self, sha: str) -> str:
        """Get diff for a specific commit."""
        try:
            return self._run_git(["show", "--patch", "--stat", sha])
        except GitError:
            return ""

    def get_stats(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> GitStats:
        """Get statistics for commits in a date range.

        Args:
            since: Start date
            until: End date

        Returns:
            Git statistics
        """
        commits = self.get_commits(since=since, until=until)

        if not commits:
            return GitStats(
                total_commits=0,
                authors=set(),
                files_changed=set(),
                additions=0,
                deletions=0,
            )

        authors: set[str] = set()
        files_changed: set[str] = set()
        total_additions = 0
        total_deletions = 0

        for commit in commits:
            authors.add(commit.author)
            files_changed.update(commit.files_changed)

        # Get total additions/deletions using git diff --shortstat
        args = ["diff", "--shortstat", "HEAD"]

        if since:
            # Find the first commit before 'since' date
            since_str = since.strftime("%Y-%m-%d")
            try:
                base_commit = self._run_git(
                    ["rev-list", "--max-count=1", f"--before={since_str}", "HEAD"]
                )
                if base_commit:
                    args = ["diff", "--shortstat", base_commit, "HEAD"]
            except GitError:
                pass

        try:
            stat_output = self._run_git(args)
            # Parse output like: "10 files changed, 100 insertions(+), 50 deletions(-)"
            if stat_output:
                import re

                add_match = re.search(r"(\d+) insertion", stat_output)
                del_match = re.search(r"(\d+) deletion", stat_output)

                if add_match:
                    total_additions = int(add_match.group(1))
                if del_match:
                    total_deletions = int(del_match.group(1))
        except GitError:
            pass

        return GitStats(
            total_commits=len(commits),
            authors=authors,
            files_changed=files_changed,
            additions=total_additions,
            deletions=total_deletions,
        )

    def get_repo_name(self) -> str:
        """Get the repository name from git config or directory name."""
        try:
            remote_url = self._run_git(["config", "--get", "remote.origin.url"])
            if remote_url:
                # Extract name from URL like git@github.com:user/repo.git or https://github.com/user/repo.git
                name = remote_url.split("/")[-1].replace(".git", "")
                return name
        except GitError:
            pass

        return self.repo_path.name
