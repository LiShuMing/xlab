"""Weekly radar orchestration."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, is_dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from py_cli.radar.git_collector import GitRadarClient
from py_cli.radar.github_collector import GitHubCollector
from py_cli.radar.llm_summary import RadarLlmSummarizer
from py_cli.radar.models import LocalRepo, RepoRadarFacts, WeeklyRadarReport
from py_cli.radar.renderer import render_weekly_report
from py_cli.radar.repo_discovery import RepoDiscovery


class WeeklyRadar:
    """Build a weekly GitHub radar report."""

    def __init__(
        self,
        *,
        root: Path,
        since: datetime,
        until: datetime,
        timezone: str,
        output: Path,
        fetch: bool = True,
        collect_github: bool = True,
        llm_summary: bool = False,
        llm_max_repos: int = 5,
        limit_repos: int | None = None,
        project_paths: list[Path] | None = None,
        include_inactive: bool = False,
        cache_dir: Path | None = None,
    ) -> None:
        self.root = root.expanduser().resolve()
        self.since = since
        self.until = until
        self.timezone = timezone
        self.output = output.expanduser().resolve()
        self.fetch = fetch
        self.collect_github = collect_github
        self.llm_summary = llm_summary
        self.llm_max_repos = llm_max_repos
        self.limit_repos = limit_repos
        self.project_paths = project_paths or []
        self.include_inactive = include_inactive
        self.cache_dir = cache_dir.expanduser().resolve() if cache_dir else self.output.parent / "cache"
        self.github = GitHubCollector()

    def run(self) -> Path:
        """Collect facts, render Markdown, and write files."""
        discovery = RepoDiscovery(self.root)
        if self.project_paths:
            local_repos, skipped = discovery.discover_paths(self.project_paths)
        else:
            local_repos, skipped = discovery.discover()

        if self.limit_repos is not None and not self.project_paths:
            local_repos = sorted(
                local_repos,
                key=lambda repo: repo.path.stat().st_mtime,
                reverse=True,
            )[: self.limit_repos]

        _progress(f"radar: discovered {len(local_repos)} GitHub repositories")
        repo_facts = []
        for index, repo in enumerate(local_repos, start=1):
            _progress(f"radar: [{index}/{len(local_repos)}] collecting {repo.github.full_name}")
            repo_facts.append(self._collect_repo(repo))

        if self.llm_summary:
            _progress("radar: generating per-project LLM learning notes")
            summaries = RadarLlmSummarizer(max_repos=self.llm_max_repos).summarize_repos(
                repo_facts
            )
            repo_facts = [
                _with_llm_summary(facts, summaries.get(facts.repo.slug))
                for facts in repo_facts
            ]

        report = WeeklyRadarReport(
            root=self.root,
            since=self.since,
            until=self.until,
            timezone=self.timezone,
            generated_at=datetime.now(self.since.tzinfo),
            repos=repo_facts,
            skipped=skipped,
            include_inactive=self.include_inactive,
        )

        self._write_cache(report)
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(render_weekly_report(report), encoding="utf-8")
        return self.output

    def _collect_repo(self, repo: LocalRepo) -> RepoRadarFacts:
        errors: list[str] = []
        git = GitRadarClient(repo)

        try:
            branch = git.default_branch()
            _progress(f"radar: {repo.github.full_name} default branch is {branch}")
        except Exception as exc:
            branch = "main"
            errors.append(f"default branch detection failed: {exc}")

        if self.fetch:
            try:
                _progress(f"radar: {repo.github.full_name} fetching {branch}")
                git.fetch(branch)
            except Exception as exc:
                errors.append(f"fetch failed: {exc}")

        try:
            commits = git.commits(branch, self.since, self.until)
            _progress(f"radar: {repo.github.full_name} commits={len(commits)}")
        except Exception as exc:
            commits = []
            errors.append(f"commit collection failed: {exc}")

        if self.collect_github:
            _progress(f"radar: {repo.github.full_name} collecting GitHub PRs/releases")
            pull_requests, pr_errors = self.github.pull_requests(
                repo.github,
                branch,
                self.since,
                self.until,
            )
            errors.extend(pr_errors)

            releases, release_errors = self.github.releases(repo.github, self.since, self.until)
            errors.extend(release_errors)
        else:
            pull_requests = []
            releases = []

        return RepoRadarFacts(
            repo=repo.github,
            local_path=repo.path,
            default_branch=branch,
            remote_url=repo.remote_url,
            since=self.since,
            until=self.until,
            commits=commits,
            pull_requests=pull_requests,
            releases=releases,
            errors=errors,
        )

    def _write_cache(self, report: WeeklyRadarReport) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        for repo in report.repos:
            path = self.cache_dir / f"{_week_label(self.since)}_{repo.repo.slug}.json"
            path.write_text(
                json.dumps(_to_jsonable(repo), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {key: _to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    return value


def _with_llm_summary(
    facts: RepoRadarFacts,
    summary_result: tuple[str, str] | None,
) -> RepoRadarFacts:
    if summary_result is None:
        return facts
    summary, error = summary_result
    return replace(facts, llm_summary=summary, llm_error=error)


def _week_label(value: datetime) -> str:
    year, week, _weekday = value.isocalendar()
    return f"{year}-W{week:02d}"


def _progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)
