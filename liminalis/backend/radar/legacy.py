"""One-time import support for retired py-radar Parquet exports."""

from __future__ import annotations

import importlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from backend.radar.identity import canonicalize_radar_url, radar_item_id


@dataclass(frozen=True)
class LegacyRadarDataset:
    items: list[dict[str, Any]]
    files: tuple[Path, ...]
    input_rows: int
    duplicate_rows: int
    invalid_rows: int

    def summary(self) -> dict[str, Any]:
        return {
            "files": len(self.files),
            "inputRows": self.input_rows,
            "items": len(self.items),
            "duplicateRows": self.duplicate_rows,
            "invalidRows": self.invalid_rows,
        }


def load_legacy_parquet(path: Path) -> LegacyRadarDataset:
    """Load and merge one file or a directory of legacy Parquet exports."""
    files = tuple(sorted(path.rglob("*.parquet"))) if path.is_dir() else (path,)
    files = tuple(item for item in files if item.is_file())
    if not files:
        raise ValueError(f"No Parquet files found under {path}")

    try:
        duckdb = importlib.import_module("duckdb")
    except ImportError as exc:
        raise RuntimeError("Legacy import requires the 'legacy-radar' optional dependency") from exc

    connection = duckdb.connect(":memory:")
    try:
        relation = connection.read_parquet([str(item) for item in files], union_by_name=True)
        columns = relation.columns
        rows = [dict(zip(columns, values, strict=True)) for values in relation.fetchall()]
    finally:
        connection.close()
    return build_legacy_dataset(rows, files)


def build_legacy_dataset(
    rows: Iterable[dict[str, Any]], files: Iterable[Path] = ()
) -> LegacyRadarDataset:
    """Canonicalize and merge overlapping legacy export rows without losing enrichment."""
    source_rows = list(rows)
    merged: dict[str, dict[str, Any]] = {}
    invalid_rows = 0

    for row in sorted(source_rows, key=_row_timestamp):
        try:
            canonical_url = canonicalize_radar_url(str(row.get("url") or ""))
        except ValueError:
            invalid_rows += 1
            continue

        item = _normalize_row(row, canonical_url)
        existing = merged.get(canonical_url)
        if existing is None:
            merged[canonical_url] = item
        else:
            _merge_row(existing, item)

    items = sorted(
        merged.values(),
        key=lambda item: item.get("fetched_at") or datetime.min,
        reverse=True,
    )
    return LegacyRadarDataset(
        items=items,
        files=tuple(files),
        input_rows=len(source_rows),
        duplicate_rows=len(source_rows) - invalid_rows - len(items),
        invalid_rows=invalid_rows,
    )


def _normalize_row(row: dict[str, Any], canonical_url: str) -> dict[str, Any]:
    legacy_id = _text(row.get("id"))
    legacy_url = _text(row.get("url"))
    published_date = _valid_date(row.get("published_date"))
    sync_batch = _valid_date(row.get("sync_batch"))
    return {
        "id": radar_item_id(canonical_url),
        "url": canonical_url,
        "title": _text(row.get("title")),
        "original_title": _text(row.get("original_title")),
        "published_date": published_date,
        "product": _text(row.get("product")),
        "content_type": _text(row.get("content_type")) or "blog",
        "summary": _text(row.get("summary")),
        "tags": _string_list(row.get("tags")),
        "sources": _string_list(row.get("sources")),
        "fetched_at": row.get("fetched_at") if isinstance(row.get("fetched_at"), datetime) else None,
        "raw_content": _text(row.get("raw_content")),
        "sync_batch": sync_batch,
        "legacy_ids": [legacy_id] if legacy_id else [],
        "legacy_urls": [legacy_url] if legacy_url else [],
    }


def _merge_row(existing: dict[str, Any], incoming: dict[str, Any]) -> None:
    for key in ("title", "original_title", "product", "content_type"):
        if incoming[key]:
            existing[key] = incoming[key]
    for key in ("summary", "raw_content"):
        if len(incoming[key]) > len(existing[key]):
            existing[key] = incoming[key]
    for key in ("tags", "sources", "legacy_ids", "legacy_urls"):
        existing[key] = list(dict.fromkeys([*existing[key], *incoming[key]]))
    for key in ("published_date", "fetched_at", "sync_batch"):
        if incoming[key] is not None:
            existing[key] = incoming[key]


def _row_timestamp(row: dict[str, Any]) -> datetime:
    value = row.get("fetched_at")
    return value if isinstance(value, datetime) else datetime.min


def _valid_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        value = value.date()
    return value if isinstance(value, date) and value.year > 1900 else None


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]
