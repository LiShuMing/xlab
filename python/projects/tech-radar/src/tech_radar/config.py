from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from tech_radar.domain import Target


class ConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PublisherConfig:
    id: str
    plugin: str
    enabled: bool = True
    options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AppConfig:
    path: Path
    database: Path
    timezone: str
    fail_fast: bool
    collector_options: Mapping[str, Mapping[str, Any]]
    processor_options: Mapping[str, Any]
    targets: tuple[Target, ...]
    publishers: tuple[PublisherConfig, ...]

    def resolve_path(self, value: str | Path) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else self.path.parent / path


def _required_text(record: Mapping[str, Any], key: str, kind: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{kind}.{key} must be a non-empty string")
    return value.strip()


def load_config(path: Path) -> AppConfig:
    config_path = path.expanduser().resolve()
    with config_path.open("rb") as stream:
        data = tomllib.load(stream)

    app = data.get("app", {})
    targets: list[Target] = []
    seen_ids: set[str] = set()
    for record in data.get("targets", []):
        target_id = _required_text(record, "id", "target")
        if target_id in seen_ids:
            raise ConfigError(f"duplicate target id: {target_id}")
        seen_ids.add(target_id)
        arguments = record.get("arguments", [])
        if not isinstance(arguments, list) or not all(
            isinstance(item, (str, int, float)) for item in arguments
        ):
            raise ConfigError(f"target {target_id} arguments must be an array")
        tags = record.get("tags", [])
        if not isinstance(tags, list) or not all(
            isinstance(tag, str) for tag in tags
        ):
            raise ConfigError(f"target {target_id} tags must be strings")
        try:
            priority = int(record.get("priority", 0))
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"target {target_id} priority must be an integer") from exc
        if not 0 <= priority <= 100:
            raise ConfigError(f"target {target_id} priority must be between 0 and 100")
        known = {
            "id",
            "collector",
            "platform",
            "command",
            "arguments",
            "tags",
            "priority",
            "enabled",
        }
        targets.append(
            Target(
                id=target_id,
                collector=_required_text(record, "collector", "target"),
                platform=_required_text(record, "platform", "target"),
                command=_required_text(record, "command", "target"),
                arguments=tuple(str(item) for item in arguments),
                tags=tuple(tags),
                priority=priority,
                enabled=bool(record.get("enabled", True)),
                options={key: value for key, value in record.items() if key not in known},
            )
        )

    publishers: list[PublisherConfig] = []
    for record in data.get("publishers", []):
        publisher_id = _required_text(record, "id", "publisher")
        known = {"id", "plugin", "enabled"}
        publishers.append(
            PublisherConfig(
                id=publisher_id,
                plugin=_required_text(record, "plugin", "publisher"),
                enabled=bool(record.get("enabled", True)),
                options={key: value for key, value in record.items() if key not in known},
            )
        )

    database = Path(str(app.get("database", "var/tech-radar.sqlite3")))
    if not database.is_absolute():
        database = config_path.parent / database
    return AppConfig(
        path=config_path,
        database=database,
        timezone=str(app.get("timezone", "Asia/Shanghai")),
        fail_fast=bool(app.get("fail_fast", False)),
        collector_options=data.get("collectors", {}),
        processor_options=data.get("processing", {}),
        targets=tuple(targets),
        publishers=tuple(publishers),
    )
