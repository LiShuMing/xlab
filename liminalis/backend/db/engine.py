"""Async SQLAlchemy engine + FastAPI session dependency.

The legacy sync `psycopg` adapters in `backend.db.postgres` continue to work
side-by-side until M1 finishes migrating radar to ORM-backed access. This
module exposes the async path that new code should use.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.settings import Settings, get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    settings = get_settings()
    if not settings.postgres_async_dsn:
        raise RuntimeError(
            "PostgreSQL is not configured; set PGSQL_HOST/PGSQL_USER/PGSQL_PASSWORD "
            "(or run docker compose up to use the bundled dev database)."
        )
    return create_async_engine(
        settings.postgres_async_dsn,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        echo=not settings.is_production and settings.environment == "debug",
    )


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency. Yields a session and rolls back on exception."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Tear down the cached engine; call from app shutdown hooks/tests."""
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


def reset_engine_cache(_settings: Settings | None = None) -> None:
    """Pytest helper — drop cached engine so a new Settings can take effect."""
    get_engine.cache_clear()
    get_session_factory.cache_clear()
