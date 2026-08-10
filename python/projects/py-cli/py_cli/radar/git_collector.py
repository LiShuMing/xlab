"""Collect weekly facts from local Git repositories."""

from __future__ import annotations

import re
import os
import subprocess
from datetime import datetime
from pathlib import Path

from py_cli.radar.models import CommitFact, LocalRepo


class GitRadarClient:
    """Small Git wrapper tailored to weekly radar collection."""

    def __init__(self, repo: LocalRepo) -> None:
        self.repo = repo

    def default_branch(self) -> str:
        """Resolve the default branch from the remote, with common fallbacks."""
        symbolic = self._git(
            "symbolic-ref",
            "--short",
            f"refs/remotes/{self.repo.remote_name}/HEAD",
            check=False,
        )
        if symbolic and "/" in symbolic:
            return symbolic.split("/", 1)[1]

        for candidate in ("main", "master", "trunk"):
            if self._git(
                "rev-parse",
                "--verify",
                f"{self.repo.remote_name}/{candidate}",
                check=False,
            ):
                return candidate

        shown = self._git("remote", "show", self.repo.remote_name, check=False)
        if shown:
            for line in shown.splitlines():
                match = re.search(r"HEAD branch:\s+(.+)$", line.strip())
                if match:
                    branch = match.group(1).strip()
                    if branch and branch != "(unknown)":
                        return branch
        return "main"

    def fetch(self, branch: str) -> None:
        """Fetch the selected default branch and tags."""
        self._git(
            "fetch",
            self.repo.remote_name,
            branch,
            "--prune",
            "--tags",
            check=True,
            timeout=_env_float("RADAR_GIT_TIMEOUT", 120.0),
        )

    def commits(self, branch: str, since: datetime, until: datetime) -> list[CommitFact]:
        """Collect commits in the time window from origin/default branch."""
        ref = f"{self.repo.remote_name}/{branch}"
        fmt = "%H%x00%ad%x00%an%x00%s"
        output = self._git(
            "log",
            ref,
            f"--since={_git_dt(since)}",
            f"--until={_git_dt(until)}",
            "--date=iso-strict",
            f"--pretty=format:{fmt}",
            check=False,
        )
        if not output:
            return []

        commits: list[CommitFact] = []
        for line in output.splitlines():
            parts = line.split("\x00")
            if len(parts) != 4:
                continue
            sha, date, author, title = parts
            files, additions, deletions = self._commit_numstat(sha)
            commits.append(
                CommitFact(
                    sha=sha,
                    date=date,
                    author=author,
                    title=title,
                    files=files,
                    additions=additions,
                    deletions=deletions,
                )
            )
        return commits

    def _commit_numstat(self, sha: str) -> tuple[list[str], int, int]:
        output = self._git("show", "--numstat", "--format=", sha, check=False)
        if not output:
            return [], 0, 0

        files: list[str] = []
        additions = 0
        deletions = 0
        for line in output.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            add, delete, file_path = parts[0], parts[1], parts[2]
            files.append(file_path)
            additions += _numstat_int(add)
            deletions += _numstat_int(delete)
        return files, additions, deletions

    def _git(
        self,
        *args: str,
        check: bool,
        timeout: float = 60.0,
    ) -> str | None:
        try:
            result = subprocess.run(
                ["git", "-C", str(self.repo.path), *args],
                capture_output=True,
                check=check,
                text=True,
                timeout=timeout,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() if exc.stderr else str(exc)
            raise RuntimeError(stderr) from exc
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            if check:
                raise RuntimeError(str(exc)) from exc
            return None

        if result.returncode != 0:
            if check:
                raise RuntimeError(result.stderr.strip())
            return None
        return result.stdout.strip() or None


def _git_dt(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _numstat_int(value: str) -> int:
    return int(value) if value.isdigit() else 0


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return max(1.0, float(raw))
    except ValueError:
        return default
