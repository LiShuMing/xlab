from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from tech_radar.config import AppConfig
from tech_radar.domain import PublishResult, Signal
from tech_radar.registry import PluginRegistry
from tech_radar.storage import SignalStore
from tech_radar.workspace import WorkspaceStore


@dataclass(frozen=True, slots=True)
class CollectionFailure:
    target_id: str
    message: str


@dataclass(frozen=True, slots=True)
class CollectionReport:
    fetched: int
    inserted: int
    updated: int
    failures: tuple[CollectionFailure, ...]


class RadarPipeline:
    def __init__(
        self,
        config: AppConfig,
        registry: PluginRegistry,
        store: SignalStore,
    ) -> None:
        self.config = config
        self.registry = registry
        self.store = store

    def collect(self) -> CollectionReport:
        self.store.initialize()
        workspace = WorkspaceStore(self.config.database)
        workspace.initialize()
        config_hash = hashlib.sha256(self.config.path.read_bytes()).hexdigest()
        run_id = workspace.begin_run("cli", config_hash)
        collector_cache: dict[str, Any] = {}
        collected: list[Signal] = []
        failures: list[CollectionFailure] = []
        try:
            for target in self.config.targets:
                if not target.enabled:
                    continue
                try:
                    collector = collector_cache.get(target.collector)
                    if collector is None:
                        options = dict(
                            self.config.collector_options.get(target.collector, {})
                        )
                        options.setdefault("_base_dir", self.config.path.parent)
                        collector = self.registry.collector(target.collector, options)
                        collector_cache[target.collector] = collector
                    target_signals = list(collector.collect(target))
                    collected.extend(target_signals)
                    workspace.record_target_run(
                        run_id,
                        target.id,
                        status="succeeded",
                        fetched=len(target_signals),
                    )
                except Exception as exc:
                    failures.append(CollectionFailure(target.id, str(exc)))
                    workspace.record_target_run(
                        run_id,
                        target.id,
                        status="failed",
                        error=str(exc),
                    )
                    if self.config.fail_fast:
                        raise

            plugins = self.config.processor_options.get("plugins", ["keyword-score"])
            if not isinstance(plugins, list):
                raise ValueError("processing.plugins must be an array")
            processed: list[Signal] = collected
            for plugin_name in plugins:
                processor = self.registry.processor(
                    str(plugin_name), dict(self.config.processor_options)
                )
                processed = list(processor.process(processed))
            inserted, updated = self.store.upsert_many(processed)
            sync = workspace.synchronize_legacy_signals(run_id)
            report = CollectionReport(
                fetched=len(collected),
                inserted=inserted,
                updated=updated,
                failures=tuple(failures),
            )
            workspace.finish_run(
                run_id,
                status="completed_with_errors" if failures else "succeeded",
                summary={
                    "fetched": report.fetched,
                    "inserted": report.inserted,
                    "updated": report.updated,
                    "material_inserted": sync.inserted,
                    "material_updated": sync.updated,
                    "failures": len(failures),
                },
            )
            return report
        except Exception as exc:
            workspace.finish_run(
                run_id,
                status="failed",
                summary={"fetched": len(collected), "failures": len(failures)},
                error=str(exc),
            )
            raise

    def publish(self, day: date | None = None) -> list[PublishResult]:
        self.store.initialize()
        zone = ZoneInfo(self.config.timezone)
        local_day = day or datetime.now(zone).date()
        results: list[PublishResult] = []
        for publisher_config in self.config.publishers:
            if not publisher_config.enabled:
                continue
            signals = self.store.undelivered(
                publisher_config.id, local_day, self.config.timezone
            )
            if not signals:
                continue
            options = dict(publisher_config.options)
            if "directory" in options:
                options["directory"] = str(
                    self.config.resolve_path(str(options["directory"]))
                )
            publisher = self.registry.publisher(
                publisher_config.plugin, publisher_config.id, options
            )
            result = publisher.publish(
                signals, local_date=local_day.isoformat()
            )
            delivered_keys = result.signal_keys or tuple(
                (signal.platform, signal.external_id)
                for signal in signals[: result.item_count]
            )
            self.store.mark_delivered(
                publisher_config.id, delivered_keys, result.location
            )
            results.append(result)
        return results
