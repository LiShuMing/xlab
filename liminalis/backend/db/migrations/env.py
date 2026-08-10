"""Alembic environment — uses backend.settings for the connection URL."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from backend.db.base import Base  # noqa: F401  -- ensures Base import path is registered
from backend.ego import db_models as _ego_db_models  # noqa: F401
from backend.invest import db_models as _invest_db_models  # noqa: F401
from backend.radar import db_models as _radar_db_models  # noqa: F401
from backend.settings import get_settings
from backend.wechat import db_models as _wechat_db_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the runtime DB URL so we don't keep a stale one in alembic.ini
get_settings.cache_clear()
settings = get_settings()
if settings.postgres_async_dsn:
    config.set_main_option("sqlalchemy.url", settings.postgres_async_dsn.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
