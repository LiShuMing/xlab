"""Database initialization helpers."""
from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.models import Base

logger = logging.getLogger(__name__)


async def initialize_database(engine: AsyncEngine) -> None:
    """Create required extensions and tables for the configured database."""
    dialect_name = engine.dialect.name
    tables = None

    if dialect_name == "postgresql":
        try:
            async with engine.begin() as conn:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except SQLAlchemyError as exc:
            logger.warning(
                "pgvector extension is unavailable; starting without semantic memory table: %s",
                exc,
            )
            tables = [
                table
                for table in Base.metadata.sorted_tables
                if table.name != "memories"
            ]

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tables)
