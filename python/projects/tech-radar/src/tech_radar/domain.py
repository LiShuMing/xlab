from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol, Sequence


@dataclass(frozen=True, slots=True)
class Target:
    """One followed account, list, feed, query, repository, or topic."""

    id: str
    collector: str
    platform: str
    command: str
    arguments: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    priority: int = 0
    enabled: bool = True
    options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Signal:
    external_id: str
    source_id: str
    platform: str
    object_type: str
    author: str
    title: str
    content: str
    url: str
    published_at: str | None
    collected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    tags: tuple[str, ...] = ()
    metrics: Mapping[str, int | float] = field(default_factory=dict)
    media: tuple[str, ...] = ()
    priority: int = 0
    score: float = 0.0
    annotations: Mapping[str, Any] = field(default_factory=dict)
    raw: Mapping[str, Any] = field(default_factory=dict)

    def with_score(self, score: float) -> Signal:
        return replace(self, score=score)

    def with_annotations(self, **values: Any) -> Signal:
        merged = dict(self.annotations)
        merged.update(values)
        return replace(self, annotations=merged)


@dataclass(frozen=True, slots=True)
class PublishResult:
    publisher_id: str
    location: str
    item_count: int
    signal_keys: tuple[tuple[str, str], ...] = ()


class Collector(Protocol):
    def collect(self, target: Target) -> Sequence[Signal]: ...


class Processor(Protocol):
    def process(self, signals: Sequence[Signal]) -> Sequence[Signal]: ...


class Publisher(Protocol):
    def publish(
        self, signals: Sequence[Signal], *, local_date: str
    ) -> PublishResult: ...
