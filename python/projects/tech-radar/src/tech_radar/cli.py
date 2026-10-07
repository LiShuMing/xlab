from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Sequence

from tech_radar.builtins import create_registry
from tech_radar.collectors.opencli import OpenCliClient
from tech_radar.config import AppConfig, load_config
from tech_radar.pipeline import RadarPipeline
from tech_radar.storage import SignalStore


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tech-radar",
        description="Collect, rank, store, and publish personal technology signals.",
    )
    parser.add_argument(
        "--config", type=Path, default=Path("config.toml"), help="TOML config path"
    )
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("check", help="validate configuration and plugin names")
    subparsers.add_parser("doctor", help="check OpenCLI and browser bridge")
    subparsers.add_parser("collect", help="collect and persist enabled targets")
    publish = subparsers.add_parser("publish", help="render enabled publishers")
    publish.add_argument("--date", type=date.fromisoformat)
    run = subparsers.add_parser("run", help="collect, then publish")
    run.add_argument("--date", type=date.fromisoformat)
    subparsers.add_parser(
        "workspace-sync", help="migrate legacy signals into workspace materials"
    )
    serve = subparsers.add_parser("serve", help="start the local content workspace")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    return parser


def _pipeline(config: AppConfig) -> RadarPipeline:
    return RadarPipeline(config, create_registry(), SignalStore(config.database))


def _check(config: AppConfig) -> int:
    registry = create_registry()
    names = registry.names
    errors: list[str] = []
    for target in config.targets:
        if target.collector not in names["collectors"]:
            errors.append(f"target {target.id}: unknown collector {target.collector}")
    for publisher in config.publishers:
        if publisher.plugin not in names["publishers"]:
            errors.append(
                f"publisher {publisher.id}: unknown plugin {publisher.plugin}"
            )
    if errors:
        for error in errors:
            print(f"ERROR {error}")
        return 2
    print(
        json.dumps(
            {
                "config": str(config.path),
                "database": str(config.database),
                "targets": len(config.targets),
                "enabled_targets": sum(target.enabled for target in config.targets),
                "publishers": len(config.publishers),
                "plugins": names,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _doctor(config: AppConfig) -> int:
    options = dict(config.collector_options.get("opencli", {}))
    raw_command = options.get("command")
    command = tuple(raw_command) if isinstance(raw_command, list) else None
    client = OpenCliClient(
        command=command,
        timeout_seconds=int(options.get("timeout_seconds", 120)),
    )
    version = client.run(("--version",)).stdout.strip()
    report = client.run(("doctor",)).stdout.strip()
    print(f"OpenCLI {version}\n{report}")
    return 1 if "[FAIL]" in report or "[MISSING]" in report else 0


def _collect(pipeline: RadarPipeline) -> int:
    report = pipeline.collect()
    print(
        json.dumps(
            {
                "fetched": report.fetched,
                "inserted": report.inserted,
                "updated": report.updated,
                "failures": [
                    {"target": failure.target_id, "message": failure.message}
                    for failure in report.failures
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if report.failures else 0


def _publish(pipeline: RadarPipeline, day: date | None) -> int:
    results = pipeline.publish(day)
    print(
        json.dumps(
            [
                {
                    "publisher": result.publisher_id,
                    "location": result.location,
                    "items": result.item_count,
                }
                for result in results
            ],
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = load_config(args.config)
    if args.action == "check":
        return _check(config)
    if args.action == "doctor":
        return _doctor(config)
    if args.action == "workspace-sync":
        from tech_radar.workspace import WorkspaceStore

        report = WorkspaceStore(config.database).initialize()
        print(
            json.dumps(
                {
                    "scanned": report.scanned,
                    "inserted": report.inserted,
                    "updated": report.updated,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.action == "serve":
        try:
            import uvicorn
        except ImportError as exc:
            raise SystemExit(
                "web dependencies are missing; install with pip install -e '.[web]'"
            ) from exc
        from tech_radar.web.app import create_app

        uvicorn.run(
            create_app(config.path),
            host=args.host,
            port=args.port,
        )
        return 0
    pipeline = _pipeline(config)
    if args.action == "collect":
        return _collect(pipeline)
    if args.action == "publish":
        return _publish(pipeline, args.date)
    if args.action == "run":
        collect_code = _collect(pipeline)
        publish_code = _publish(pipeline, args.date)
        return max(collect_code, publish_code)
    raise AssertionError(f"unsupported action: {args.action}")
