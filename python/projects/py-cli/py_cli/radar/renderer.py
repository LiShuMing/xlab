"""Render weekly radar facts to Markdown."""

from __future__ import annotations

import re

from py_cli.radar.models import (
    CommitFact,
    PullRequestFact,
    ReleaseFact,
    RepoRadarFacts,
    WeeklyRadarReport,
)


def render_weekly_report(report: WeeklyRadarReport) -> str:
    """Render a complete weekly radar report as Markdown."""
    active_repos = [repo for repo in report.repos if repo.has_activity]
    lines = [
        f"# GitHub Weekly Radar - {_week_label(report)}",
        "",
        f"- Root: `{report.root}`",
        f"- Period: {report.since.isoformat()} ~ {report.until.isoformat()}",
        f"- Timezone: `{report.timezone}`",
        f"- Generated: {report.generated_at.isoformat()}",
        f"- Repositories scanned: {len(report.repos)}",
        f"- Repositories with activity: {len(active_repos)}",
        "",
        "## Global TL;DR",
        "",
    ]

    if active_repos:
        for repo in sorted(active_repos, key=_repo_activity_score, reverse=True)[:10]:
            lines.append(
                "- "
                f"**{repo.repo.full_name}**: "
                f"{len(repo.pull_requests)} PRs, "
                f"{len(repo.commits)} commits, "
                f"{len(repo.releases)} releases"
            )
    else:
        lines.append("- No GitHub repository activity found in this period.")

    if report.skipped:
        lines.extend(["", "## Skipped", ""])
        for item in report.skipped[:100]:
            lines.append(f"- {item}")

    lines.extend(["", "## Repo Reports", ""])
    for repo in sorted(report.repos, key=_repo_activity_score, reverse=True):
        if not report.include_inactive and not repo.has_activity and not repo.errors:
            continue
        lines.extend(_render_repo(repo))

    return "\n".join(lines).rstrip() + "\n"


def _render_repo(repo: RepoRadarFacts) -> list[str]:
    lines = [
        f"### {repo.repo.full_name}",
        "",
        f"- Local path: `{repo.local_path}`",
        f"- Default branch: `{repo.default_branch}`",
        f"- Remote: {repo.remote_url}",
        f"- Commits: {len(repo.commits)}",
        f"- Merged PRs: {len(repo.pull_requests)}",
        f"- Releases: {len(repo.releases)}",
        "",
    ]

    if repo.errors:
        lines.extend(["#### Collection Notes", ""])
        for error in repo.errors:
            lines.append(f"- {error}")
        lines.append("")

    if repo.llm_summary:
        lines.extend(["#### Learning Notes", "", repo.llm_summary.strip(), ""])
    elif repo.llm_error:
        lines.extend(["#### Learning Notes", "", f"- LLM summary failed: {repo.llm_error}", ""])

    if repo.pull_requests:
        lines.extend(["#### Major PRs", ""])
        for pr in repo.pull_requests[:10]:
            lines.extend(_render_pr(pr))

    if repo.releases:
        lines.extend(["#### Releases", ""])
        for release in repo.releases[:5]:
            lines.extend(_render_release(release))

    if repo.commits:
        lines.extend(["#### Commit Digest", ""])
        lines.extend(
            [
                "| Commit | Author | Date | Message | PR |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for commit in repo.commits[:5]:
            lines.append(_render_commit_row(repo, commit))
        lines.append("")

    return lines


def _render_pr(pr: PullRequestFact) -> list[str]:
    labels = ", ".join(pr.labels) if pr.labels else "none"
    reasons = ", ".join(pr.reasons) if pr.reasons else "n/a"
    lines = [
        f"##### #{pr.number} {_escape_md(pr.title)}",
        "",
        f"- Link: {pr.url}",
        f"- Score: {pr.score} ({reasons})",
        f"- Author: `{pr.author}`",
        f"- Merged: `{pr.merged_at}`",
        f"- Labels: {labels}",
        f"- Churn: +{pr.additions} / -{pr.deletions}, {pr.changed_files} files",
    ]
    if pr.files:
        lines.append("- Files to read:")
        for file_path in pr.files[:8]:
            lines.append(f"  - `{file_path}`")
    lines.append("")
    return lines


def _render_release(release: ReleaseFact) -> list[str]:
    lines = [
        f"- **{_escape_md(release.name or release.tag_name)}** "
        f"(`{release.tag_name}`, {release.published_at})",
    ]
    if release.url:
        lines.append(f"  - Link: {release.url}")
    if release.body:
        summary = " ".join(release.body.split())[:300]
        lines.append(f"  - Notes: {summary}")
    return lines


def _render_commit_row(repo: RepoRadarFacts, commit: CommitFact) -> str:
    return (
        f"| `{commit.short_sha}` | {_table_cell(commit.author)} | "
        f"{_table_cell(commit.date)} | {_table_cell(commit.title)} | "
        f"{_commit_pr_links(repo, commit)} |"
    )


def _repo_activity_score(repo: RepoRadarFacts) -> float:
    pr_score = sum(pr.score for pr in repo.pull_requests)
    return pr_score + len(repo.commits) + len(repo.releases) * 5


def _week_label(report: WeeklyRadarReport) -> str:
    year, week, _weekday = report.since.isocalendar()
    return f"{year}-W{week:02d}"


def _escape_md(value: str) -> str:
    return value.replace("|", "\\|")


def _table_cell(value: str) -> str:
    return _escape_md(" ".join(value.split()))


def _commit_pr_links(repo: RepoRadarFacts, commit: CommitFact) -> str:
    numbers = sorted({int(match) for match in re.findall(r"#(\d+)", commit.title)})
    if not numbers:
        return ""
    return ", ".join(
        f"[#{number}](https://github.com/{repo.repo.full_name}/pull/{number})"
        for number in numbers
    )
