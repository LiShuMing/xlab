"""Importance scoring for weekly radar facts."""

from __future__ import annotations

from py_cli.radar.models import PullRequestFact

LABEL_WEIGHTS = {
    "breaking-change": 12,
    "breaking change": 12,
    "security": 10,
    "performance": 8,
    "perf": 8,
    "api": 7,
    "feature": 6,
    "bug": 4,
    "bugfix": 4,
    "docs": 2,
}

CORE_PATH_PREFIXES = (
    "src/",
    "packages/",
    "compiler/",
    "runtime/",
    "storage/",
    "query/",
    "engine/",
    "core/",
    "lib/",
)

PUBLIC_SURFACE_PREFIXES = ("docs/", "examples/", "api/", "sdk/")


def score_pull_request(pr: PullRequestFact) -> PullRequestFact:
    """Score a PR and return a copy with score reasons."""
    score = 0.0
    reasons: list[str] = []

    file_score = min(pr.changed_files, 50) * 0.5
    if file_score:
        score += file_score
        reasons.append(f"{pr.changed_files} changed files")

    churn = pr.additions + pr.deletions
    churn_score = min(churn, 5000) / 250
    if churn_score:
        score += churn_score
        reasons.append(f"{churn} changed lines")

    for label in pr.labels:
        normalized = label.lower()
        weight = LABEL_WEIGHTS.get(normalized)
        if weight:
            score += weight
            reasons.append(f"label:{label}")

    if any(_matches_prefix(path, CORE_PATH_PREFIXES) for path in pr.files):
        score += 5
        reasons.append("core path touched")

    if any(_matches_prefix(path, PUBLIC_SURFACE_PREFIXES) for path in pr.files):
        score += 3
        reasons.append("public surface/docs touched")

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
        files=pr.files,
        score=round(score, 2),
        reasons=reasons,
    )


def _matches_prefix(path: str, prefixes: tuple[str, ...]) -> bool:
    lowered = path.lower()
    return any(lowered.startswith(prefix) for prefix in prefixes)
