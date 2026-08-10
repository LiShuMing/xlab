"""Discover local GitHub repositories under a root directory."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from py_cli.radar.models import GitHubRepo, LocalRepo

HTTPS_RE = re.compile(r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$")
SSH_RE = re.compile(r"^git@github\.com:(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$")
SSH_SCHEME_RE = re.compile(
    r"^ssh://git@github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$"
)


def parse_github_remote(url: str) -> GitHubRepo | None:
    """Parse a GitHub remote URL into owner/repo."""
    for pattern in (HTTPS_RE, SSH_RE, SSH_SCHEME_RE):
        match = pattern.match(url.strip())
        if match:
            return GitHubRepo(owner=match.group("owner"), name=match.group("repo"))
    return None


class RepoDiscovery:
    """Find GitHub repositories in a local directory tree."""

    def __init__(
        self,
        root: Path,
        *,
        remote_preference: str = "origin",
        skip_hidden_dirs: bool = True,
    ) -> None:
        self.root = root.expanduser().resolve()
        self.remote_preference = remote_preference
        self.skip_hidden_dirs = skip_hidden_dirs

    def discover(self) -> tuple[list[LocalRepo], list[str]]:
        """Discover local GitHub repositories and return skipped reasons."""
        repos: list[LocalRepo] = []
        skipped: list[str] = []
        for path in self._iter_repo_roots():
            repo, error = self._local_repo(path)
            if repo:
                repos.append(repo)
            elif error:
                skipped.append(error)

        return repos, skipped

    def discover_paths(self, paths: list[Path]) -> tuple[list[LocalRepo], list[str]]:
        """Discover explicit repository paths from config."""
        repos: list[LocalRepo] = []
        skipped: list[str] = []
        for raw_path in paths:
            path = raw_path.expanduser().resolve()
            if not path.exists():
                skipped.append(f"{path}: path does not exist")
                continue
            repo, error = self._local_repo(path)
            if repo:
                repos.append(repo)
            elif error:
                skipped.append(error)
        return repos, skipped

    def _iter_repo_roots(self) -> list[Path]:
        if not self.root.is_dir():
            return []

        found: list[Path] = []
        for dirpath, dirnames, _filenames in os.walk(self.root, topdown=True):
            path = Path(dirpath)
            if self.skip_hidden_dirs:
                rel = path.relative_to(self.root)
                if any(part.startswith(".") for part in rel.parts):
                    dirnames[:] = []
                    continue

            if ".git" in dirnames:
                dirnames.remove(".git")

            git_entry = path / ".git"
            if git_entry.is_dir() or git_entry.is_file():
                found.append(path)

        return sorted(found, key=lambda p: str(p).lower())

    def _select_remote(self, repo: Path) -> tuple[str | None, str | None]:
        preferred = self._remote_url(repo, self.remote_preference)
        if preferred:
            return self.remote_preference, preferred

        names = self._git(repo, "remote")
        if names is None:
            return None, None

        for name in [line.strip() for line in names.splitlines() if line.strip()]:
            url = self._remote_url(repo, name)
            if url:
                return name, url

        return None, None

    def _local_repo(self, path: Path) -> tuple[LocalRepo | None, str | None]:
        git_entry = path / ".git"
        if not (git_entry.is_dir() or git_entry.is_file()):
            return None, f"{path}: not a git repository"

        remote_name, remote_url = self._select_remote(path)
        if not remote_url or not remote_name:
            return None, f"{path}: no git remote found"

        github = parse_github_remote(remote_url)
        if github is None:
            return None, f"{path}: non-GitHub remote {remote_url}"

        return (
            LocalRepo(
                path=path,
                remote_url=remote_url,
                remote_name=remote_name,
                github=github,
            ),
            None,
        )

    def _remote_url(self, repo: Path, remote: str) -> str | None:
        return self._git(repo, "remote", "get-url", remote)

    def _git(self, repo: Path, *args: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", "-C", str(repo), *args],
                capture_output=True,
                check=False,
                text=True,
                timeout=30,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

        if result.returncode != 0:
            return None
        return result.stdout.strip() or None
