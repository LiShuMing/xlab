"""Radar commands."""

from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import click

from py_cli.radar.config import RadarConfig, load_radar_config
from py_cli.radar.weekly import WeeklyRadar


@click.group(name="radar")
def radar_group() -> None:
    """Build learning-oriented GitHub radar reports."""


@radar_group.command(name="weekly")
@click.option(
    "--config",
    "config_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="TOML or JSON config file. CLI options override config values.",
)
@click.option(
    "--root",
    "-r",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="Root directory containing local GitHub repositories.",
)
@click.option("--since", default=None, help="Start date, YYYY-MM-DD.")
@click.option("--until", default=None, help="End date, YYYY-MM-DD.")
@click.option(
    "--timezone",
    "timezone_name",
    default=None,
    help="Timezone used for date windows.",
)
@click.option(
    "--out",
    "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Output Markdown path.",
)
@click.option(
    "--cache-dir",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="Directory for per-repo JSON facts.",
)
@click.option(
    "--fetch/--no-fetch",
    default=None,
    help="Fetch default branches before collecting commits.",
)
@click.option(
    "--github/--no-github",
    "collect_github",
    default=None,
    help="Collect merged PRs and releases with the GitHub CLI.",
)
@click.option(
    "--llm-summary/--no-llm-summary",
    default=None,
    help="Generate a Chinese learning summary using ~/.env LLM settings.",
)
@click.option(
    "--llm-max-repos",
    type=int,
    default=None,
    help="Maximum active repos to include in the LLM summary prompt.",
)
@click.option(
    "--limit-repos",
    type=int,
    default=None,
    help="Only scan the N most recently modified local GitHub repos.",
)
@click.option(
    "--include-inactive/--exclude-inactive",
    default=None,
    help="Include repos without activity in the Markdown report.",
)
def weekly_command(
    config_path: Path | None,
    root: Path | None,
    since: str | None,
    until: str | None,
    timezone_name: str | None,
    out: Path | None,
    cache_dir: Path | None,
    fetch: bool | None,
    collect_github: bool | None,
    llm_summary: bool | None,
    llm_max_repos: int | None,
    limit_repos: int | None,
    include_inactive: bool | None,
) -> None:
    """Generate a weekly GitHub radar report."""
    try:
        config = load_radar_config(config_path) if config_path else RadarConfig()
        root_value = root or config.root or Path("/Users/lism/xwork/projects")
        since_value = since or config.since
        until_value = until or config.until
        if not since_value or not until_value:
            raise click.ClickException("--since and --until are required unless set in --config")

        timezone_value = timezone_name or config.timezone or "Asia/Shanghai"
        fetch_value = _pick_bool(fetch, config.fetch, default=True)
        github_value = _pick_bool(collect_github, config.github, default=True)
        llm_summary_value = _pick_bool(llm_summary, config.llm_summary, default=False)
        llm_max_repos_value = _pick_int(llm_max_repos, config.llm_max_repos, default=5)
        limit_repos_value = _pick_optional_int(limit_repos, config.limit_repos)
        include_inactive_value = _pick_bool(
            include_inactive,
            config.include_inactive,
            default=False,
        )
        cache_dir_value = cache_dir or config.cache_dir

        tz = ZoneInfo(timezone_value)
        since_dt = datetime.combine(_parse_date(since_value), time.min, tzinfo=tz)
        until_dt = datetime.combine(
            _parse_date(until_value),
            time.max.replace(microsecond=0),
            tzinfo=tz,
        )
        output = out or config.output or _default_output(since_dt)

        path = WeeklyRadar(
            root=root_value,
            since=since_dt,
            until=until_dt,
            timezone=timezone_value,
            output=output,
            fetch=fetch_value,
            collect_github=github_value,
            llm_summary=llm_summary_value,
            llm_max_repos=llm_max_repos_value,
            limit_repos=limit_repos_value,
            project_paths=config.projects,
            include_inactive=include_inactive_value,
            cache_dir=cache_dir_value,
        ).run()
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Weekly radar written to: {path}")


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise click.BadParameter(f"Invalid date {value!r}; expected YYYY-MM-DD") from exc


def _default_output(since: datetime) -> Path:
    year, week, _weekday = since.isocalendar()
    return Path(f"/Users/lism/xwork/reports/github-weekly/{year}-W{week:02d}.md")


def _pick_bool(value: bool | None, config_value: bool | None, *, default: bool) -> bool:
    if value is not None:
        return value
    if config_value is not None:
        return config_value
    return default


def _pick_int(value: int | None, config_value: int | None, *, default: int) -> int:
    if value is not None:
        return value
    if config_value is not None:
        return config_value
    return default


def _pick_optional_int(value: int | None, config_value: int | None) -> int | None:
    return value if value is not None else config_value
