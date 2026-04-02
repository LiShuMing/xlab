"""Default analysis prompt for general git repositories."""

from __future__ import annotations

SYSTEM_PROMPT = """You are a senior software architect with deep expertise in code review, system design, and software engineering best practices.

Your task is to analyze git commits and code changes to produce a structured technical report that provides meaningful insights beyond simple commit message summaries.

When analyzing:
1. Look for patterns in the types of changes (features, bug fixes, refactors)
2. Identify the modules/components most actively developed
3. Assess the engineering quality and direction of the codebase
4. Highlight potential risks or technical debt
5. Provide actionable recommendations

Output must be structured and professional, suitable for engineering leadership review."""

USER_PROMPT_TEMPLATE = """Please analyze the following git commits and code changes from the past {time_range}.

Repository: {repo_name}

## Commit Statistics
- Total commits: {total_commits}
- Authors: {authors}
- Files changed: {files_changed}
- Lines added: {additions}
- Lines deleted: {deletions}

## Commit Details

{commit_details}

## Analysis Instructions

Please provide a structured analysis with the following sections:

1. **Executive Summary** (3-5 bullet points summarizing the most important changes)

2. **Changes by Category**: Group commits into:
   - Features (new functionality)
   - Enhancements (improvements to existing features)
   - Bug Fixes
   - Refactoring
   - Tests/Infrastructure
   - Documentation

3. **Key Changes**: Identify 3-5 most significant changes and explain:
   - What was changed
   - Why it matters
   - Impact on the system

4. **Architecture Direction**: Based on the changes, what direction is the codebase evolving?

5. **Recommendations**: 2-3 actionable suggestions for the team

Output format: Provide the analysis in clear Markdown format with appropriate headings."""


def format_commit_details(commits: list[dict]) -> str:
    """Format commit details for the prompt.

    Args:
        commits: List of commit dictionaries

    Returns:
        Formatted commit details string
    """
    lines = []
    for commit in commits:
        lines.extend(
            [
                f"### {commit.get('short_sha', 'unknown')} - {commit.get('author', 'unknown')}",
                f"Date: {commit.get('date', 'unknown')}",
                f"Message: {commit.get('message', 'no message')}",
                f"Files: {', '.join(commit.get('files_changed', [])[:10])}",
            ]
        )
        if len(commit.get("files_changed", [])) > 10:
            lines.append(f"... and {len(commit['files_changed']) - 10} more files")

        diff_preview = commit.get("diff", "")[:2000]
        if diff_preview:
            lines.extend(
                [
                    "",
                    "Diff preview:",
                    "```",
                    diff_preview,
                    "..." if len(commit.get("diff", "")) > 2000 else "",
                    "```",
                ]
            )
        lines.append("")

    return "\n".join(lines)
