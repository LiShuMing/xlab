"""Git change analysis orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from py_cli.config import Config
from py_cli.core.git_client import GitClient
from py_cli.exceptions import AnalysisError
from py_cli.llm.client import LLMClient
from py_cli.llm.models import AnalysisResult
from py_cli.llm.prompts import get_prompt
from py_cli.utils import format_date, get_default_output_path, truncate_text

if TYPE_CHECKING:
    from py_cli.core.git_client import CommitInfo


@dataclass(frozen=True)
class AnalysisContext:
    """Context for analysis operation."""

    repo_path: Path
    output_path: Path
    since: datetime
    until: datetime
    prompt_name: str
    max_commits: int


class Analyzer:
    """Orchestrates git analysis using LLM."""

    def __init__(self, config: Config | None = None) -> None:
        """Initialize analyzer.

        Args:
            config: Application configuration
        """
        self.config = config or Config.load()
        self.llm_client = LLMClient(self.config.llm)

    def analyze(
        self,
        repo_path: Path | None = None,
        output_path: Path | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        prompt_name: str = "default",
    ) -> Path:
        """Run analysis on a git repository.

        Args:
            repo_path: Path to git repository (default: current directory)
            output_path: Output file path (default: auto-generated)
            since: Start date for analysis
            until: End date for analysis
            prompt_name: Name of prompt template to use

        Returns:
            Path to generated report

        Raises:
            AnalysisError: If analysis fails
        """
        # Resolve paths
        repo = (repo_path or Path.cwd()).resolve()
        if output_path is None:
            output = get_default_output_path(repo)
        else:
            output = output_path.resolve()

        # Default date range
        if until is None:
            until = datetime.now(timezone.utc)
        if since is None:
            since = until - __import__("datetime").timedelta(
                days=self.config.analyzer.default_days
            )

        context = AnalysisContext(
            repo_path=repo,
            output_path=output,
            since=since,
            until=until,
            prompt_name=prompt_name,
            max_commits=self.config.analyzer.max_commits,
        )

        return self._run_analysis(context)

    def _run_analysis(self, context: AnalysisContext) -> Path:
        """Execute the analysis workflow.

        Args:
            context: Analysis context

        Returns:
            Path to generated report
        """
        import time

        start_time = time.time()

        # Initialize git client
        git = GitClient(context.repo_path)

        print(f"Analyzing repository: {git.get_repo_name()}")
        print(f"Date range: {format_date(context.since)} to {format_date(context.until)}")
        print(f"Using prompt: {context.prompt_name}")
        print()

        # Fetch commits
        print("Fetching commits...")
        commits = git.get_commits(
            since=context.since,
            until=context.until,
            max_count=context.max_commits,
            include_merges=self.config.analyzer.include_merge_commits,
        )

        if not commits:
            msg = "No commits found in the specified date range"
            raise AnalysisError(msg)

        print(f"Found {len(commits)} commits")

        # Get statistics
        stats = git.get_stats(since=context.since, until=context.until)

        # Prepare commit data for prompt
        commit_data = self._prepare_commit_data(commits)

        # Get prompt template
        prompt_module = get_prompt(context.prompt_name)

        # Build prompt
        time_range = f"{format_date(context.since)} to {format_date(context.until)}"

        user_prompt = prompt_module.USER_PROMPT_TEMPLATE.format(
            time_range=time_range,
            repo_name=git.get_repo_name(),
            total_commits=len(commits),
            authors=", ".join(sorted(set(c.author for c in commits))),
            files_changed=len(stats.files_changed),
            additions=stats.additions,
            deletions=stats.deletions,
            commit_details=prompt_module.format_commit_details(commit_data),
        )

        # Call LLM
        print("Analyzing with LLM...")
        try:
            response = self.llm_client.complete(
                system_prompt=prompt_module.SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
        except Exception as e:
            msg = f"LLM analysis failed: {e}"
            raise AnalysisError(msg) from e

        # Generate report
        report = self._generate_report(
            response.content,
            git.get_repo_name(),
            context,
            commits,
            stats,
        )

        # Write output
        output_path = context.output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")

        elapsed = time.time() - start_time
        print(f"\nAnalysis complete!")
        print(f"Report saved to: {output_path}")
        print(f"Time elapsed: {elapsed:.1f}s")

        return output_path

    def _prepare_commit_data(self, commits: list[CommitInfo]) -> list[dict]:
        """Convert CommitInfo objects to dictionaries for prompt formatting.

        Args:
            commits: List of commit info objects

        Returns:
            List of commit dictionaries
        """
        result = []
        max_diff_size = self.config.analyzer.max_diff_size // len(commits)

        for commit in commits:
            result.append(
                {
                    "sha": commit.sha,
                    "short_sha": commit.short_sha,
                    "author": commit.author,
                    "date": format_date(commit.date),
                    "message": commit.message,
                    "files_changed": commit.files_changed,
                    "diff": truncate_text(commit.diff, max_diff_size),
                }
            )

        return result

    def _generate_report(
        self,
        analysis_content: str,
        repo_name: str,
        context: AnalysisContext,
        commits: list[CommitInfo],
        stats: "GitStats",
    ) -> str:
        """Generate the final report.

        Args:
            analysis_content: LLM-generated analysis
            repo_name: Repository name
            context: Analysis context
            commits: List of commits analyzed
            stats: Git statistics

        Returns:
            Complete report as markdown string
        """
        lines = [
            f"# {repo_name} - Code Change Analysis",
            "",
            f"**Analysis Period:** {format_date(context.since)} to {format_date(context.until)}",
            f"**Prompt Used:** {context.prompt_name}",
            f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            "---",
            "",
        ]

        # Add analysis content from LLM
        lines.append(analysis_content)

        # Add appendix with commit list
        lines.extend(
            [
                "",
                "---",
                "",
                "## Appendix: Commit List",
                "",
                f"Total commits analyzed: {len(commits)}",
                "",
            ]
        )

        for commit in commits:
            lines.append(
                f"- `{commit.short_sha}` - {commit.author} - {commit.message[:80]}"
            )

        return "\n".join(lines)
