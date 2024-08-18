"""PostgreSQL access for the unified Liminalis backend."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any

from psycopg import Connection, sql
from psycopg.rows import dict_row

from backend.settings import Settings

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS radar_items (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL DEFAULT '',
    original_title TEXT NOT NULL DEFAULT '',
    published_date DATE,
    product TEXT NOT NULL DEFAULT '',
    content_type TEXT NOT NULL DEFAULT 'blog',
    summary TEXT NOT NULL DEFAULT '',
    tags TEXT[] NOT NULL DEFAULT '{}',
    sources TEXT[] NOT NULL DEFAULT '{}',
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    raw_content TEXT NOT NULL DEFAULT '',
    sync_batch DATE
);

CREATE INDEX IF NOT EXISTS idx_radar_items_sync_batch
    ON radar_items (sync_batch DESC NULLS LAST, published_date DESC NULLS LAST, fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_radar_items_product ON radar_items (product);
CREATE INDEX IF NOT EXISTS idx_radar_items_content_type ON radar_items (content_type);
CREATE INDEX IF NOT EXISTS idx_radar_items_published_date ON radar_items (published_date DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_radar_items_tags ON radar_items USING GIN (tags);

CREATE TABLE IF NOT EXISTS radar_ingestion_jobs (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    status TEXT NOT NULL,
    error TEXT,
    item_id TEXT REFERENCES radar_items(id) ON DELETE SET NULL,
    submitted_by TEXT,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_radar_ingestion_jobs_status ON radar_ingestion_jobs(status);
CREATE INDEX IF NOT EXISTS idx_radar_ingestion_jobs_submitted_at
    ON radar_ingestion_jobs(submitted_at DESC);
"""

_availability_checked = False
_available = False


@contextmanager
def connect(settings: Settings) -> Iterator[Connection]:
    if not settings.postgres_dsn:
        raise RuntimeError("PostgreSQL is not configured")
    with Connection.connect(settings.postgres_dsn, row_factory=dict_row) as conn:
        yield conn


def init_schema(settings: Settings) -> None:
    with connect(settings) as conn:
        conn.execute(SCHEMA_SQL)
        conn.commit()


def ensure_database(settings: Settings) -> bool:
    if not settings.postgres_maintenance_dsn:
        raise RuntimeError("PostgreSQL is not configured")

    with Connection.connect(settings.postgres_maintenance_dsn, autocommit=True, row_factory=dict_row) as conn:
        row = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %(database)s",
            {"database": settings.pgsql_database},
        ).fetchone()
        if row:
            return False
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(settings.pgsql_database)))
        return True


def postgres_is_available(settings: Settings) -> bool:
    global _availability_checked, _available

    if settings.storage_backend == "duckdb" or not settings.postgres_configured:
        return False
    if _availability_checked:
        return _available

    try:
        init_schema(settings)
        _available = True
    except Exception:
        _available = False
        if settings.storage_backend == "postgres":
            raise
    _availability_checked = True
    return _available


def upsert_radar_items(settings: Settings, items: list[dict[str, Any]]) -> int:
    if not items:
        return 0

    init_schema(settings)
    rows = [_normalize_item(item) for item in items]
    with connect(settings) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO radar_items (
                    id, url, title, original_title, published_date, product,
                    content_type, summary, tags, sources, fetched_at, raw_content, sync_batch
                )
                VALUES (
                    %(id)s, %(url)s, %(title)s, %(original_title)s, %(published_date)s, %(product)s,
                    %(content_type)s, %(summary)s, %(tags)s, %(sources)s, %(fetched_at)s,
                    %(raw_content)s, %(sync_batch)s
                )
                ON CONFLICT (id) DO UPDATE SET
                    url = EXCLUDED.url,
                    title = EXCLUDED.title,
                    original_title = EXCLUDED.original_title,
                    published_date = EXCLUDED.published_date,
                    product = EXCLUDED.product,
                    content_type = EXCLUDED.content_type,
                    summary = EXCLUDED.summary,
                    tags = EXCLUDED.tags,
                    sources = EXCLUDED.sources,
                    fetched_at = EXCLUDED.fetched_at,
                    raw_content = EXCLUDED.raw_content,
                    sync_batch = EXCLUDED.sync_batch
                """,
                rows,
            )
        conn.commit()
    return len(rows)


def query_radar_items(
    settings: Settings,
    *,
    page: int,
    per_page: int,
    content_type: str,
    product: str,
    query: str,
) -> dict[str, Any] | None:
    if not postgres_is_available(settings):
        return None

    where_sql, params = _radar_where(content_type=content_type, product=product, query=query)
    offset = (page - 1) * per_page

    with connect(settings) as conn:
        total_row = conn.execute(
            f"SELECT COUNT(*) AS count FROM radar_items WHERE {where_sql}", params
        ).fetchone()
        total_items = int(total_row["count"] if total_row else 0)
        if total_items == 0:
            return None

        rows = conn.execute(
            f"""
            SELECT id, url, title, original_title, published_date, product, content_type,
                   summary, tags, sources, fetched_at, raw_content, sync_batch
            FROM radar_items
            WHERE {where_sql}
            ORDER BY sync_batch DESC NULLS LAST, published_date DESC NULLS LAST, fetched_at DESC
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            {**params, "limit": per_page, "offset": offset},
        ).fetchall()

        product_counts = conn.execute(
            """
            SELECT product AS name, COUNT(*) AS count
            FROM radar_items
            WHERE product <> ''
            GROUP BY product
            ORDER BY count DESC, product ASC
            LIMIT 24
            """
        ).fetchall()

        type_counts = conn.execute(
            """
            SELECT content_type AS name, COUNT(*) AS count
            FROM radar_items
            WHERE content_type <> ''
            GROUP BY content_type
            ORDER BY count DESC, content_type ASC
            """
        ).fetchall()

        latest_row = conn.execute("SELECT MAX(sync_batch) AS latest FROM radar_items").fetchone()

    total_pages = (total_items + per_page - 1) // per_page if total_items else 0
    return {
        "items": [_row_to_api_dict(row) for row in rows],
        "page": page,
        "per_page": per_page,
        "total_items": total_items,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "products": [{"name": row["name"], "count": row["count"]} for row in product_counts],
        "contentTypes": [{"name": row["name"], "count": row["count"]} for row in type_counts],
        "latestSyncBatch": latest_row["latest"].isoformat() if latest_row and latest_row["latest"] else None,
    }


def _radar_where(*, content_type: str, product: str, query: str) -> tuple[str, dict[str, Any]]:
    clauses = ["1=1"]
    params: dict[str, Any] = {}
    if content_type not in {"", "all"}:
        clauses.append("content_type = %(content_type)s")
        params["content_type"] = content_type
    if product not in {"", "all"}:
        clauses.append("product = %(product)s")
        params["product"] = product
    if query:
        clauses.append(
            """
            to_tsvector(
                'simple',
                coalesce(title, '') || ' ' ||
                coalesce(original_title, '') || ' ' ||
                coalesce(product, '') || ' ' ||
                coalesce(content_type, '') || ' ' ||
                coalesce(summary, '') || ' ' ||
                array_to_string(tags, ' ')
            ) @@ plainto_tsquery('simple', %(query)s)
            """
        )
        params["query"] = query
    return " AND ".join(clauses), params


def _normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    published_date = _parse_date(item.get("published_date") or item.get("publishedDate"))
    fetched_at = _parse_datetime(item.get("fetched_at") or item.get("fetchedAt")) or datetime.now()
    sync_batch = _parse_date(item.get("sync_batch") or item.get("syncBatch")) or published_date
    return {
        "id": item["id"],
        "url": item["url"],
        "title": item.get("title") or "",
        "original_title": item.get("original_title") or item.get("originalTitle") or item.get("title") or "",
        "published_date": published_date,
        "product": item.get("product") or "",
        "content_type": item.get("content_type") or item.get("contentType") or "blog",
        "summary": item.get("summary") or "",
        "tags": item.get("tags") or [],
        "sources": item.get("sources") or [],
        "fetched_at": fetched_at,
        "raw_content": item.get("raw_content") or item.get("rawContent") or "",
        "sync_batch": sync_batch,
    }


def _row_to_api_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "originalTitle": row["original_title"] or row["title"],
        "url": row["url"],
        "site": _extract_domain(row["url"]),
        "product": row["product"],
        "summary": row["summary"],
        "tags": row["tags"] or [],
        "sources": row["sources"] or [],
        "publishedDate": row["published_date"].isoformat() if row["published_date"] else None,
        "contentType": row["content_type"],
        "fetchedAt": row["fetched_at"].isoformat() if row["fetched_at"] else None,
        "syncBatch": row["sync_batch"].isoformat() if row["sync_batch"] else None,
    }


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str) and value:
        return date.fromisoformat(value[:10])
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None


def _extract_domain(url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return parsed.netloc.replace("www.", "") or ""
