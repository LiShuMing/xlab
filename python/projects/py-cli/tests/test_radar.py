"""Tests for weekly radar functionality."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from click.testing import CliRunner

from py_cli.cli import cli
from py_cli.commands.radar import _default_output, _previous_week_dates
from py_cli.radar.config import load_radar_config
from py_cli.radar.git_collector import GitRadarClient, _git_dt
from py_cli.radar.models import (
    CommitFact,
    GitHubRepo,
    LocalRepo,
    PullRequestFact,
    RepoRadarFacts,
    WeeklyRadarReport,
)
from py_cli.radar.renderer import render_weekly_report
from py_cli.radar.repo_discovery import RepoDiscovery, parse_github_remote
from py_cli.radar.scorer import score_pull_request


class TestParseGithubRemote:
    """Tests for GitHub remote parsing."""

    def test_https_remote(self) -> None:
        repo = parse_github_remote("https://github.com/org/name.git")
        assert repo is not None
        assert repo.full_name == "org/name"

    def test_ssh_remote(self) -> None:
        repo = parse_github_remote("git@github.com:org/name.git")
        assert repo is not None
        assert repo.full_name == "org/name"

    def test_non_github_remote(self) -> None:
        assert parse_github_remote("https://gitlab.com/org/name.git") is None


class TestRepoDiscovery:
    """Tests for bounded repository discovery."""

    def test_prunes_working_tree_after_finding_repository(self, tmp_path: Path) -> None:
        repo = tmp_path / "large-repo"
        nested = repo / "vendor" / "nested-repo"
        (repo / ".git").mkdir(parents=True)
        (nested / ".git").mkdir(parents=True)

        found = RepoDiscovery(tmp_path)._iter_repo_roots()

        assert found == [repo]

    def test_discovers_repositories_below_container_directories(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path / "group" / "repo"
        (repo / ".git").mkdir(parents=True)

        assert RepoDiscovery(tmp_path)._iter_repo_roots() == [repo]


class TestGitRadarClient:
    """Tests for bounded Git collection behavior."""

    def _client(self, tmp_path: Path) -> GitRadarClient:
        return GitRadarClient(
            LocalRepo(
                path=tmp_path,
                remote_url="https://github.com/org/repo.git",
                remote_name="origin",
                github=GitHubRepo("org", "repo"),
            )
        )

    def test_fetch_skips_tags_by_default(self, tmp_path: Path) -> None:
        client = self._client(tmp_path)
        client._git = MagicMock(return_value=None)  # type: ignore[method-assign]

        client.fetch("main")

        assert client._git.call_args.args == ("fetch", "origin", "main", "--prune")

    def test_fetch_can_include_tags(self, tmp_path: Path) -> None:
        client = self._client(tmp_path)
        client._git = MagicMock(return_value=None)  # type: ignore[method-assign]

        client.fetch("main", include_tags=True)

        assert client._git.call_args.args == (
            "fetch",
            "origin",
            "main",
            "--prune",
            "--tags",
        )

    def test_git_datetime_preserves_timezone_offset(self) -> None:
        value = datetime(2026, 9, 14, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

        assert _git_dt(value) == "2026-09-14 00:00:00+08:00"


class TestScorer:
    """Tests for PR scoring."""

    def test_scores_core_performance_pr(self) -> None:
        pr = PullRequestFact(
            number=123,
            title="Speed up runtime scheduler",
            url="https://github.com/org/repo/pull/123",
            author="alice",
            merged_at="2026-06-23T01:00:00Z",
            labels=["performance"],
            additions=500,
            deletions=100,
            changed_files=5,
            files=["runtime/scheduler.cc", "docs/runtime.md"],
        )
        scored = score_pull_request(pr)

        assert scored.score > 0
        assert "label:performance" in scored.reasons
        assert "core path touched" in scored.reasons
        assert "public surface/docs touched" in scored.reasons


class TestRenderer:
    """Tests for Markdown rendering."""

    def test_render_weekly_report(self, tmp_path: Path) -> None:
        tz = ZoneInfo("Asia/Shanghai")
        facts = RepoRadarFacts(
            repo=GitHubRepo("org", "repo"),
            local_path=tmp_path / "repo",
            default_branch="main",
            remote_url="https://github.com/org/repo.git",
            since=datetime(2026, 6, 22, tzinfo=tz),
            until=datetime(2026, 6, 28, 23, 59, 59, tzinfo=tz),
            commits=[
                CommitFact(
                    sha="abcdef123456",
                    date="2026-06-23T01:00:00+08:00",
                    author="alice",
                    title="Add useful thing (#42)",
                    files=["src/a.cc"],
                    additions=10,
                    deletions=2,
                )
            ]
            + [
                CommitFact(
                    sha=f"feedface{i}",
                    date="2026-06-23T01:00:00+08:00",
                    author="alice",
                    title=f"Extra commit {i}",
                )
                for i in range(6)
            ],
            pull_requests=[
                PullRequestFact(
                    number=1,
                    title="Improve API",
                    url="https://github.com/org/repo/pull/1",
                    author="alice",
                    merged_at="2026-06-23T01:00:00Z",
                    score=10,
                    reasons=["label:api"],
                )
            ],
            llm_summary="项目内独立学习总结",
        )
        report = WeeklyRadarReport(
            root=tmp_path,
            since=facts.since,
            until=facts.until,
            timezone="Asia/Shanghai",
            generated_at=facts.until,
            repos=[facts],
        )

        markdown = render_weekly_report(report)

        assert "GitHub Weekly Radar" in markdown
        assert "org/repo" in markdown
        assert "#1 Improve API" in markdown
        assert "`abcdef1`" in markdown
        assert "[#42](https://github.com/org/repo/pull/42)" in markdown
        assert "Extra commit 4" not in markdown
        assert "#### Learning Notes" in markdown
        assert "项目内独立学习总结" in markdown
        assert "## LLM Learning Summary" not in markdown


class TestRadarConfig:
    """Tests for radar config loading."""

    def test_load_toml_project_list(self, tmp_path: Path) -> None:
        repo_a = tmp_path / "repo-a"
        repo_b = tmp_path / "repo-b"
        config_path = tmp_path / "radar.toml"
        config_path.write_text(
            f"""
[radar]
root = "{tmp_path}"
since = "2026-06-22"
until = "2026-06-28"
out = "{tmp_path / "weekly.md"}"
fetch = false
fetch_tags = true
github = false
llm_summary = true
llm_max_repos = 2
repo_concurrency = 4
include_inactive = true

[[projects]]
path = "{repo_a}"

[[projects]]
path = "{repo_b}"
""",
            encoding="utf-8",
        )

        config = load_radar_config(config_path)

        assert config.root == tmp_path
        assert config.since == "2026-06-22"
        assert config.until == "2026-06-28"
        assert config.output == tmp_path / "weekly.md"
        assert config.fetch is False
        assert config.fetch_tags is True
        assert config.github is False
        assert config.llm_summary is True
        assert config.llm_max_repos == 2
        assert config.repo_concurrency == 4
        assert config.include_inactive is True
        assert config.projects == [repo_a, repo_b]


class TestRadarCli:
    """Tests for radar Click command."""

    @patch("py_cli.commands.radar.WeeklyRadar")
    def test_weekly_command(self, mock_radar_class: MagicMock, tmp_path: Path) -> None:
        output = tmp_path / "weekly.md"
        mock_radar = MagicMock()
        mock_radar.run.return_value = output
        mock_radar_class.return_value = mock_radar

        result = CliRunner().invoke(
            cli,
            [
                "radar",
                "weekly",
                "--root",
                str(tmp_path),
                "--since",
                "2026-06-22",
                "--until",
                "2026-06-28",
                "--out",
                str(output),
                "--no-fetch",
            ],
        )

        assert result.exit_code == 0
        assert "Weekly radar written" in result.output
        mock_radar.run.assert_called_once()

    @patch("py_cli.commands.radar.WeeklyRadar")
    @patch(
        "py_cli.commands.radar._previous_week_dates",
        return_value=(date(2026, 9, 14), date(2026, 9, 20)),
    )
    def test_previous_week_builds_complete_week(
        self,
        _mock_dates: MagicMock,
        mock_radar_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        output = tmp_path / "weekly.md"
        mock_radar = MagicMock()
        mock_radar.run.return_value = output
        mock_radar_class.return_value = mock_radar

        result = CliRunner().invoke(
            cli,
            [
                "radar",
                "weekly",
                "--root",
                str(tmp_path),
                "--previous-week",
                "--out",
                str(output),
                "--no-fetch",
            ],
        )

        assert result.exit_code == 0
        kwargs = mock_radar_class.call_args.kwargs
        assert kwargs["since"] == datetime(
            2026,
            9,
            14,
            tzinfo=ZoneInfo("Asia/Shanghai"),
        )
        assert kwargs["until"] == datetime(
            2026,
            9,
            20,
            23,
            59,
            59,
            tzinfo=ZoneInfo("Asia/Shanghai"),
        )
        assert kwargs["fetch_tags"] is False

    def test_previous_week_date_math(self) -> None:
        assert _previous_week_dates(date(2026, 9, 21)) == (
            date(2026, 9, 14),
            date(2026, 9, 20),
        )
        assert _previous_week_dates(date(2026, 9, 24)) == (
            date(2026, 9, 14),
            date(2026, 9, 20),
        )

    def test_previous_week_rejects_explicit_dates(self, tmp_path: Path) -> None:
        result = CliRunner().invoke(
            cli,
            [
                "radar",
                "weekly",
                "--root",
                str(tmp_path),
                "--previous-week",
                "--since",
                "2026-09-14",
            ],
        )

        assert result.exit_code != 0
        assert "cannot be combined" in result.output

    def test_default_output_is_under_home_xwork(self) -> None:
        since = datetime(2026, 9, 14, tzinfo=ZoneInfo("Asia/Shanghai"))
        with patch("py_cli.commands.radar.Path.home", return_value=Path("/home/test")):
            assert _default_output(since) == Path(
                "/home/test/xwork/reports/github-weekly/2026-W38.md"
            )

    @patch("py_cli.commands.radar.WeeklyRadar")
    def test_weekly_command_uses_config_projects(
        self,
        mock_radar_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        output = tmp_path / "weekly.md"
        repo_a = tmp_path / "repo-a"
        repo_b = tmp_path / "repo-b"
        config_path = tmp_path / "radar.toml"
        config_path.write_text(
            f"""
[radar]
root = "{tmp_path}"
since = "2026-06-22"
until = "2026-06-28"
out = "{output}"
fetch = false
fetch_tags = true
github = false
llm_summary = true
llm_max_repos = 3
repo_concurrency = 4
include_inactive = true

[[projects]]
path = "{repo_a}"

[[projects]]
path = "{repo_b}"
""",
            encoding="utf-8",
        )
        mock_radar = MagicMock()
        mock_radar.run.return_value = output
        mock_radar_class.return_value = mock_radar

        result = CliRunner().invoke(
            cli,
            [
                "radar",
                "weekly",
                "--config",
                str(config_path),
                "--no-llm-summary",
            ],
        )

        assert result.exit_code == 0
        kwargs = mock_radar_class.call_args.kwargs
        assert kwargs["root"] == tmp_path
        assert kwargs["output"] == output
        assert kwargs["fetch"] is False
        assert kwargs["fetch_tags"] is True
        assert kwargs["collect_github"] is False
        assert kwargs["llm_summary"] is False
        assert kwargs["llm_max_repos"] == 3
        assert kwargs["repo_concurrency"] == 4
        assert kwargs["project_paths"] == [repo_a, repo_b]
        assert kwargs["include_inactive"] is True
        mock_radar.run.assert_called_once()
