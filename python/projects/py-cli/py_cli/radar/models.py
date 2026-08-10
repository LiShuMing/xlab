"""Data models for the weekly GitHub radar."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class GitHubRepo:
    """A GitHub repository identity."""

    owner: str
    name: str

    @property
    def full_name(self) -> str:
        """Return owner/name."""
        return f"{self.owner}/{self.name}"

    @property
    def slug(self) -> str:
        """Return a filesystem-safe repository slug."""
        return f"{self.owner}__{self.name}"


@dataclass(frozen=True)
class LocalRepo:
    """A discovered local GitHub repository."""

    path: Path
    remote_url: str
    remote_name: str
    github: GitHubRepo


@dataclass(frozen=True)
class CommitFact:
    """Facts collected from a Git commit."""

    sha: str
    date: str
    author: str
    title: str
    files: list[str] = field(default_factory=list)
    additions: int = 0
    deletions: int = 0

    @property
    def short_sha(self) -> str:
        """Return short SHA."""
        return self.sha[:7]


@dataclass(frozen=True)
class PullRequestFact:
    """Facts collected from a GitHub pull request."""

    number: int
    title: str
    url: str
    author: str
    merged_at: str
    labels: list[str] = field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    files: list[str] = field(default_factory=list)
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReleaseFact:
    """Facts collected from a GitHub release."""

    name: str
    tag_name: str
    published_at: str
    url: str
    body: str = ""


@dataclass(frozen=True)
class RepoRadarFacts:
    """All weekly radar facts for one repository."""

    repo: GitHubRepo
    local_path: Path
    default_branch: str
    remote_url: str
    since: datetime
    until: datetime
    commits: list[CommitFact] = field(default_factory=list)
    pull_requests: list[PullRequestFact] = field(default_factory=list)
    releases: list[ReleaseFact] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    llm_summary: str = ""
    llm_error: str = ""

    @property
    def has_activity(self) -> bool:
        """Return whether the repo has any relevant activity."""
        return bool(self.commits or self.pull_requests or self.releases)


@dataclass(frozen=True)
class WeeklyRadarReport:
    """Complete weekly radar output."""

    root: Path
    since: datetime
    until: datetime
    timezone: str
    generated_at: datetime
    repos: list[RepoRadarFacts]
    skipped: list[str] = field(default_factory=list)
    include_inactive: bool = False
