"""Collect GitHub facts through the GitHub CLI."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime

from py_cli.radar.models import GitHubRepo, PullRequestFact, ReleaseFact
from py_cli.radar.scorer import score_pull_request


class GitHubCollector:
    """GitHub collector using the local `gh` CLI."""

    def __init__(self) -> None:
        self.available = shutil.which("gh") is not None

    def pull_requests(
        self,
        repo: GitHubRepo,
        base_branch: str,
        since: datetime,
        until: datetime,
        *,
        max_items: int = 50,
        hydrate_files_for_top: int = 10,
    ) -> tuple[list[PullRequestFact], list[str]]:
        """Collect merged PRs in the window."""
        if not self.available:
            return [], ["gh CLI not found; skipped GitHub PR collection"]

        max_items = _env_int("RADAR_GH_MAX_PRS", max_items)
        hydrate_files_for_top = _env_int("RADAR_GH_HYDRATE_TOP", hydrate_files_for_top)
        query = f"merged:{since:%Y-%m-%d}..{until:%Y-%m-%d}"
        data, error = self._gh_json(
            "pr",
            "list",
            "--repo",
            repo.full_name,
            "--state",
            "merged",
            "--base",
            base_branch,
            "--search",
            query,
            "--limit",
            str(max_items),
            "--json",
            "number,title,url,author,mergedAt,labels,additions,deletions,changedFiles",
        )
        if error:
            return [], [error]

        prs = [_pr_from_list_item(item) for item in data if isinstance(item, dict)]
        scored = [score_pull_request(pr) for pr in prs]
        scored.sort(key=lambda pr: pr.score, reverse=True)

        hydrated: list[PullRequestFact] = []
        errors: list[str] = []
        for index, pr in enumerate(scored):
            if index >= hydrate_files_for_top:
                hydrated.append(pr)
                continue
            files, error = self._pr_files(repo, pr.number)
            if error:
                errors.append(error)
                hydrated.append(pr)
                continue
            hydrated.append(score_pull_request(_replace_pr_files(pr, files)))

        hydrated.sort(key=lambda item: item.score, reverse=True)
        return hydrated, errors

    def releases(
        self,
        repo: GitHubRepo,
        since: datetime,
        until: datetime,
        *,
        max_items: int = 20,
    ) -> tuple[list[ReleaseFact], list[str]]:
        """Collect releases published in the window."""
        if not self.available:
            return [], ["gh CLI not found; skipped GitHub release collection"]

        max_items = _env_int("RADAR_GH_MAX_RELEASES", max_items)
        data, error = self._gh_json(
            "release",
            "list",
            "--repo",
            repo.full_name,
            "--limit",
            str(max_items),
            "--json",
            "name,tagName,publishedAt",
        )
        if error:
            return [], [error]

        releases: list[ReleaseFact] = []
        errors: list[str] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            published_at = str(item.get("publishedAt", ""))
            if not _within_window(published_at, since, until):
                continue
            body, error = self._release_body(repo, str(item.get("tagName", "")))
            if error:
                errors.append(error)
            releases.append(
                ReleaseFact(
                    name=str(item.get("name") or item.get("tagName") or ""),
                    tag_name=str(item.get("tagName") or ""),
                    published_at=published_at,
                    url=_release_url(repo, str(item.get("tagName") or "")),
                    body=body,
                )
            )
        return releases, errors

    def _pr_files(self, repo: GitHubRepo, number: int) -> tuple[list[str], str | None]:
        data, error = self._gh_json(
            "pr",
            "view",
            str(number),
            "--repo",
            repo.full_name,
            "--json",
            "files",
        )
        if error:
            return [], error
        files = data.get("files", []) if isinstance(data, dict) else []
        return [str(item.get("path", "")) for item in files if isinstance(item, dict)], None

    def _release_body(self, repo: GitHubRepo, tag_name: str) -> tuple[str, str | None]:
        if not tag_name:
            return "", None
        data, error = self._gh_json(
            "release",
            "view",
            tag_name,
            "--repo",
            repo.full_name,
            "--json",
            "body",
        )
        if error:
            return "", error
        if isinstance(data, dict):
            return str(data.get("body") or ""), None
        return "", None

    def _gh_json(self, *args: str) -> tuple[object, str | None]:
        try:
            result = subprocess.run(
                ["gh", *args],
                capture_output=True,
                check=False,
                text=True,
                timeout=_env_float("RADAR_GH_TIMEOUT", 120.0),
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return [], f"gh failed: {exc}"

        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip()
            return [], f"gh {' '.join(args[:2])} failed: {message}"

        try:
            return json.loads(result.stdout or "[]"), None
        except json.JSONDecodeError as exc:
            return [], f"gh returned invalid JSON: {exc}"


def _pr_from_list_item(item: dict) -> PullRequestFact:
    labels = item.get("labels") or []
    author = item.get("author") or {}
    return PullRequestFact(
        number=int(item.get("number") or 0),
        title=str(item.get("title") or ""),
        url=str(item.get("url") or ""),
        author=str(author.get("login") or author.get("name") or ""),
        merged_at=str(item.get("mergedAt") or ""),
        labels=[str(label.get("name") or "") for label in labels if isinstance(label, dict)],
        additions=int(item.get("additions") or 0),
        deletions=int(item.get("deletions") or 0),
        changed_files=int(item.get("changedFiles") or 0),
    )


def _replace_pr_files(pr: PullRequestFact, files: list[str]) -> PullRequestFact:
    return PullRequestFact(
        number=pr.number,
        title=pr.title,
        url=pr.url,
        author=pr.author,
        merged_at=pr.merged_at,
        labels=pr.labels,
        additions=pr.additions,
        deletions=pr.deletions,
        changed_files=pr.changed_files,
        files=files,
        score=pr.score,
        reasons=pr.reasons,
    )


def _within_window(value: str, since: datetime, until: datetime) -> bool:
    if not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    if since.tzinfo is not None and parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=since.tzinfo)
    return since <= parsed <= until


def _release_url(repo: GitHubRepo, tag_name: str) -> str:
    if not tag_name:
        return ""
    return f"https://github.com/{repo.full_name}/releases/tag/{tag_name}"


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return max(1.0, float(raw))
    except ValueError:
        return default
