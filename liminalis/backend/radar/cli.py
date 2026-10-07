"""Unified Radar CLI backed by the business database.

The historical DuckDB/OSS sync CLI was removed from the normal Liminalis entry
point. Radar business data now lives in PostgreSQL/Supabase and all writes go
through the shared unit-of-work boundary.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

import click

from backend._shared.storage import business_uow
from backend.radar import service as radar_service
from backend.radar.legacy import LegacyRadarDataset, load_legacy_parquet
from backend.services.radar_service import load_py_radar_snapshot
from backend.settings import get_settings


@click.group()
def cli() -> None:
    """Radar data commands backed by PostgreSQL/Supabase."""


@cli.command("status")
def status() -> None:
    """Show Radar business database status."""
    asyncio.run(_status())


async def _status() -> None:
    settings = get_settings()
    click.echo(
        json.dumps(
            {
                "configured": settings.postgres_configured,
                "backend": settings.business_database_backend,
                "database": settings.business_database_name,
                "remote": settings.business_database_remote,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if not settings.postgres_configured:
        return

    async with business_uow() as session:
        result = await radar_service.query_radar_items(
            session,
            page=1,
            per_page=1,
            content_type="all",
            product="all",
            query="",
        )
    result = result or {}
    click.echo(
        json.dumps(
            {
                "items": result.get("total_items", 0),
                "latestSyncBatch": result.get("latestSyncBatch"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


@cli.command("items")
@click.option("--limit", type=int, default=10, show_default=True, help="Maximum items to print.")
@click.option("--query", "-q", default="", help="Text query.")
@click.option("--product", default="all", help="Product filter.")
@click.option("--type", "content_type", default="all", help="Content type filter.")
def items(limit: int, query: str, product: str, content_type: str) -> None:
    """List recent Radar items from the business database."""
    asyncio.run(_items(limit=limit, query=query, product=product, content_type=content_type))


async def _items(limit: int, query: str, product: str, content_type: str) -> None:
    async with business_uow() as session:
        result = await radar_service.query_radar_items(
            session,
            page=1,
            per_page=max(1, min(limit, 100)),
            content_type=content_type,
            product=product,
            query=query,
        )
    result = result or {"items": []}
    for item in result.get("items", []):
        click.echo(f"{item['id']}  {item.get('publishedDate') or '-'}  {item['title']}")


@cli.command("import-snapshot")
@click.option(
    "--snapshot",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to pyRadarFeed.js. Defaults to the bundled frontend snapshot.",
)
def import_snapshot(snapshot: Path | None) -> None:
    """Import bundled static Radar snapshot into the business database."""
    asyncio.run(_import_snapshot(snapshot))


async def _import_snapshot(snapshot: Path | None) -> None:
    settings = get_settings()
    snapshot_path = snapshot or settings.xlab_root / "liminalis" / "src" / "data" / "pyRadarFeed.js"
    payload = load_py_radar_snapshot(snapshot_path)
    items = payload.get("items") or []

    count = 0
    async with business_uow() as session:
        for item in items:
            await radar_service.upsert_radar_item(session, item)
            count += 1

    click.echo(f"Imported {count} Radar items into {settings.business_database_name}")


@cli.command("migrate-legacy")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--apply",
    is_flag=True,
    help="Write the merged rows to PostgreSQL. Without this flag the command only inspects data.",
)
def migrate_legacy(path: Path, apply: bool) -> None:
    """Inspect or import retired py-radar Parquet exports."""
    try:
        dataset = load_legacy_parquet(path)
    except (RuntimeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    if not apply:
        click.echo(json.dumps(dataset.summary(), ensure_ascii=False, indent=2))
        return

    settings = get_settings()
    if not settings.postgres_configured:
        raise click.ClickException("PostgreSQL is not configured; refusing to discard legacy data")
    asyncio.run(_migrate_legacy(dataset))


async def _migrate_legacy(dataset: LegacyRadarDataset) -> None:
    settings = get_settings()
    async with business_uow() as session:
        imported = await radar_service.upsert_radar_items_bulk(session, dataset.items)
        result = await radar_service.query_radar_items(
            session,
            page=1,
            per_page=1,
            content_type="all",
            product="all",
            query="",
        )
    summary = dataset.summary()
    summary.update(
        {
            "upserted": imported,
            "databaseItems": (result or {}).get("total_items", 0),
            "database": settings.business_database_name,
        }
    )
    click.echo(json.dumps(summary, ensure_ascii=False, indent=2))


@cli.command("add-url")
@click.argument("url")
@click.option("--submitted-by", default="cli", show_default=True)
def add_url(url: str, submitted_by: str) -> None:
    """Create a Radar ingestion job in the business database.

    This records the job only. Run the unified worker/arq path to process it.
    """
    asyncio.run(_add_url(url, submitted_by))


async def _add_url(url: str, submitted_by: str) -> None:
    async with business_uow() as session:
        job = await radar_service.create_ingestion_job(
            session,
            job_id=uuid.uuid4().hex,
            url=url,
            submitted_by=submitted_by,
            metadata={"source": "cli"},
        )
    click.echo(json.dumps(radar_service.ingestion_job_to_dict(job), ensure_ascii=False, indent=2))
