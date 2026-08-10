"""OpenAI-compatible LLM summarization for weekly radar facts."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from py_cli.radar.models import RepoRadarFacts

DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen-max"
DEFAULT_MAX_TOKENS = 2048
DEFAULT_CONCURRENCY = 3


class RadarLlmSummarizer:
    """Summarize radar facts through an OpenAI-compatible chat API."""

    def __init__(self, *, max_repos: int = 5, timeout: float = 180.0) -> None:
        load_dotenv(Path.home() / ".env")
        load_dotenv(override=True)
        self.api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        self.base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or DEFAULT_BASE_URL
        self.model = os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL
        self.max_tokens = _env_int("LLM_MAX_TOKENS", DEFAULT_MAX_TOKENS)
        self.max_repos = max_repos
        self.timeout = _env_float("LLM_TIMEOUT", timeout)
        self.concurrency = _env_int("LLM_CONCURRENCY", DEFAULT_CONCURRENCY)

    def summarize_repos(self, repos: list[RepoRadarFacts]) -> dict[str, tuple[str, str]]:
        """Return repo slug -> (summary_markdown, error)."""
        if not self.api_key:
            return {
                repo.repo.slug: ("", "LLM_API_KEY or OPENAI_API_KEY is not configured")
                for repo in repos
            }

        active = sorted(repos, key=_repo_importance, reverse=True)
        active = [repo for repo in active if repo.has_activity or repo.errors][: self.max_repos]
        if not active:
            return {}

        results: dict[str, tuple[str, str]] = {}
        max_workers = max(1, min(self.concurrency, len(active)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self._summarize_one, repo): repo for repo in active}
            for future in as_completed(futures):
                repo = futures[future]
                try:
                    summary, error = future.result()
                except Exception as exc:
                    summary, error = "", str(exc) or exc.__class__.__name__
                results[repo.repo.slug] = (summary, error or "")
        return results

    def _summarize_one(self, repo: RepoRadarFacts) -> tuple[str, str | None]:
        """Summarize exactly one repository."""
        prompt = _build_prompt(repo)
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a senior database/kernel engineer writing a weekly "
                        "open-source learning radar for exactly one project. "
                        "Be concise, source-grounded, and "
                        "focus on design trends, important files, and ideas worth borrowing. "
                        "Write in Chinese. Do not invent facts beyond the provided data. "
                        "Do not compare with or mention other projects unless they appear "
                        "inside the provided facts for this project. Use section headings "
                        "that stay inside this project section; do not use H1/H2/H3 headings."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }

        try:
            response = _post_json(_chat_completions_url(self.base_url), payload, self.api_key, self.timeout)
        except Exception as exc:
            return "", str(exc) or exc.__class__.__name__

        content = _extract_content(response)
        if not content:
            return "", "LLM response did not include assistant content"
        return _demote_headings(content.strip()), None


def _build_prompt(repo: RepoRadarFacts) -> str:
    sections = [
        f"请只基于项目 {repo.repo.full_name} 的事实，生成该项目独立的 weekly radar 学习总结。",
        "不要汇总、类比、混合或引用其他项目内容。",
        "",
        "输出结构：",
        "1. 本项目本周最值得关注的 3-5 个变化",
        "2. 设计趋势",
        "3. 值得精读的 PR / 文件",
        "4. 可以迁移到自己项目里的做法",
        "5. 风险或 breaking changes",
        "",
        "Facts:",
        f"\n## {repo.repo.full_name}",
        f"- Default branch: {repo.default_branch}",
        f"- Commits: {len(repo.commits)}",
        f"- PRs: {len(repo.pull_requests)}",
        f"- Releases: {len(repo.releases)}",
    ]

    if repo.pull_requests:
        sections.append("- Top PRs:")
        for pr in repo.pull_requests[:8]:
            files = ", ".join(pr.files[:6]) if pr.files else ""
            sections.append(
                "  - "
                f"#{pr.number} {pr.title}; score={pr.score}; "
                f"labels={','.join(pr.labels) or 'none'}; "
                f"churn=+{pr.additions}/-{pr.deletions}; "
                f"files={files}; url={pr.url}"
            )

    if repo.releases:
        sections.append("- Releases:")
        for release in repo.releases[:3]:
            body = " ".join(release.body.split())[:300]
            sections.append(
                f"  - {release.tag_name} {release.name}; "
                f"published={release.published_at}; notes={body}; url={release.url}"
            )

    if repo.commits:
        sections.append("- Commits:")
        for commit in repo.commits[:12]:
            sections.append(
                f"  - {commit.short_sha} {commit.date} {commit.author}: "
                f"{commit.title}; files={', '.join(commit.files[:5])}"
            )

    if repo.errors:
        sections.append("- Collection notes:")
        for error in repo.errors[:5]:
            sections.append(f"  - {error}")

    return "\n".join(sections)


def _post_json(url: str, payload: dict[str, Any], api_key: str, timeout: float) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"LLM request failed with HTTP {exc.code}: {detail}") from exc
    return json.loads(body)


def _chat_completions_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def _extract_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content", "")
    return content if isinstance(content, str) else ""


def _demote_headings(markdown: str) -> str:
    """Keep LLM-generated headings nested under a repo section."""
    lines: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("# "):
            lines.append("##### " + line[2:])
        elif line.startswith("## "):
            lines.append("##### " + line[3:])
        elif line.startswith("### "):
            lines.append("##### " + line[4:])
        elif line.startswith("#### "):
            lines.append("##### " + line[5:])
        else:
            lines.append(line)
    return "\n".join(lines)


def _repo_importance(repo: RepoRadarFacts) -> float:
    return sum(pr.score for pr in repo.pull_requests) + len(repo.commits) + len(repo.releases) * 5


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return max(1, int(raw))
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
