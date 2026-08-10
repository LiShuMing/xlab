"""Configuration loading for radar reports."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RadarConfig:
    """Config values for a weekly radar run."""

    root: Path | None = None
    since: str | None = None
    until: str | None = None
    timezone: str | None = None
    output: Path | None = None
    cache_dir: Path | None = None
    fetch: bool | None = None
    github: bool | None = None
    llm_summary: bool | None = None
    llm_max_repos: int | None = None
    limit_repos: int | None = None
    include_inactive: bool | None = None
    projects: list[Path] = field(default_factory=list)


def load_radar_config(path: Path) -> RadarConfig:
    """Load a radar config from TOML or JSON."""
    raw = _load_raw(path.expanduser())
    data = raw.get("radar", raw)
    projects = raw.get("projects", data.get("projects", []))

    return RadarConfig(
        root=_path_or_none(data.get("root")),
        since=_str_or_none(data.get("since")),
        until=_str_or_none(data.get("until")),
        timezone=_str_or_none(data.get("timezone")),
        output=_path_or_none(data.get("out") or data.get("output")),
        cache_dir=_path_or_none(data.get("cache_dir")),
        fetch=_bool_or_none(data.get("fetch")),
        github=_bool_or_none(data.get("github")),
        llm_summary=_bool_or_none(data.get("llm_summary")),
        llm_max_repos=_int_or_none(data.get("llm_max_repos")),
        limit_repos=_int_or_none(data.get("limit_repos")),
        include_inactive=_bool_or_none(data.get("include_inactive")),
        projects=_project_paths(projects),
    )


def _load_raw(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"radar config not found: {path}")

    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))

    with path.open("rb") as handle:
        return tomllib.load(handle)


def _project_paths(value: object) -> list[Path]:
    if not isinstance(value, list):
        return []

    paths: list[Path] = []
    for item in value:
        if isinstance(item, str):
            paths.append(Path(item).expanduser())
        elif isinstance(item, dict) and item.get("path"):
            paths.append(Path(str(item["path"])).expanduser())
    return paths


def _path_or_none(value: object) -> Path | None:
    return Path(str(value)).expanduser() if value else None


def _str_or_none(value: object) -> str | None:
    return str(value) if value is not None else None


def _bool_or_none(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _int_or_none(value: object) -> int | None:
    return int(value) if isinstance(value, int) else None
