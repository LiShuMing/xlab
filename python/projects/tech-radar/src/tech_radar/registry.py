from __future__ import annotations

from collections.abc import Callable
from importlib.metadata import entry_points
from typing import Any

from tech_radar.domain import Collector, Processor, Publisher

CollectorFactory = Callable[[dict[str, Any]], Collector]
ProcessorFactory = Callable[[dict[str, Any]], Processor]
PublisherFactory = Callable[[str, dict[str, Any]], Publisher]


class PluginRegistry:
    """Small explicit registry; third-party packages can register at startup."""

    def __init__(self) -> None:
        self._collectors: dict[str, CollectorFactory] = {}
        self._processors: dict[str, ProcessorFactory] = {}
        self._publishers: dict[str, PublisherFactory] = {}

    def register_collector(self, name: str, factory: CollectorFactory) -> None:
        self._register(self._collectors, name, factory)

    def register_processor(self, name: str, factory: ProcessorFactory) -> None:
        self._register(self._processors, name, factory)

    def register_publisher(self, name: str, factory: PublisherFactory) -> None:
        self._register(self._publishers, name, factory)

    @staticmethod
    def _register(registry: dict[str, Any], name: str, factory: Any) -> None:
        if not name or name in registry:
            raise ValueError(f"plugin already registered or invalid: {name}")
        registry[name] = factory

    def collector(self, name: str, options: dict[str, Any]) -> Collector:
        try:
            return self._collectors[name](options)
        except KeyError as exc:
            raise ValueError(f"unknown collector plugin: {name}") from exc

    def processor(self, name: str, options: dict[str, Any]) -> Processor:
        try:
            return self._processors[name](options)
        except KeyError as exc:
            raise ValueError(f"unknown processor plugin: {name}") from exc

    def publisher(
        self, name: str, publisher_id: str, options: dict[str, Any]
    ) -> Publisher:
        try:
            return self._publishers[name](publisher_id, options)
        except KeyError as exc:
            raise ValueError(f"unknown publisher plugin: {name}") from exc

    @property
    def names(self) -> dict[str, tuple[str, ...]]:
        return {
            "collectors": tuple(sorted(self._collectors)),
            "processors": tuple(sorted(self._processors)),
            "publishers": tuple(sorted(self._publishers)),
        }

    def load_entry_points(self) -> None:
        """Load separately packaged plugins without modifying the core project."""
        groups = {
            "tech_radar.collectors": self.register_collector,
            "tech_radar.processors": self.register_processor,
            "tech_radar.publishers": self.register_publisher,
        }
        for group, register in groups.items():
            for entry_point in entry_points(group=group):
                register(entry_point.name, entry_point.load())
