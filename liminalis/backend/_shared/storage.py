"""Shared storage boundaries for Liminalis.

Business data is centralized in the remote PostgreSQL database, typically
Supabase. Runtime caches and static snapshots are intentionally separate so
modules do not blur durable records with local acceleration artifacts.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.engine import get_session_factory
from backend.settings import Settings, get_settings


class StorageClass(StrEnum):
    """High-level storage classes used by the application."""

    BUSINESS_DATABASE = "business_database"
    RUNTIME_CACHE = "runtime_cache"
    STATIC_SNAPSHOT = "static_snapshot"


@dataclass(frozen=True)
class StorageLayout:
    """Resolved storage locations for the current runtime."""

    business_backend: str
    business_database: str | None
    business_remote: bool
    business_read_fallback: bool
    runtime_cache_dir: Path
    static_snapshot_dir: Path
    local_artifact_dir: Path


def describe_storage(settings: Settings | None = None) -> StorageLayout:
    """Describe the active storage layout without exposing credentials."""
    settings = settings or get_settings()
    return StorageLayout(
        business_backend=settings.business_database_backend,
        business_database=settings.business_database_name,
        business_remote=settings.business_database_remote,
        business_read_fallback=settings.allow_business_read_fallback,
        runtime_cache_dir=settings.data_dir / "cache",
        static_snapshot_dir=settings.frontend_dist_dir,
        local_artifact_dir=settings.data_dir / "artifacts",
    )


def runtime_cache_path(*parts: str, settings: Settings | None = None) -> Path:
    """Return a path under the runtime-cache storage class."""
    layout = describe_storage(settings)
    return layout.runtime_cache_dir.joinpath(*parts)


def local_artifact_path(*parts: str, settings: Settings | None = None) -> Path:
    """Return a path under local non-durable artifacts."""
    layout = describe_storage(settings)
    return layout.local_artifact_dir.joinpath(*parts)


def allow_business_read_fallback(settings: Settings | None = None) -> bool:
    """Whether read routes may fall back to static/local views after DB errors."""
    settings = settings or get_settings()
    return settings.allow_business_read_fallback


@asynccontextmanager
async def business_uow() -> AsyncIterator[AsyncSession]:
    """Open a business-database unit of work with centralized commit/rollback."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_business_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency for business database access."""
    async with business_uow() as session:
        yield session
