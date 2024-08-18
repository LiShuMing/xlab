"""SQLAlchemy ORM models for the radar domain."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import ARRAY, JSON, Date, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


class RadarItem(Base):
    __tablename__ = "radar_items"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    original_title: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    published_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    product: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    content_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="blog")
    summary: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    sources: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    raw_content: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    sync_batch: Mapped[date | None] = mapped_column(Date, nullable=True)

    ingestion_jobs: Mapped[list[RadarIngestionJob]] = relationship(back_populates="item", lazy="raise")

    __table_args__ = (
        Index(
            "idx_radar_items_sync_batch",
            sync_batch.desc().nullslast(),
            published_date.desc().nullslast(),
            fetched_at.desc(),
        ),
        Index("idx_radar_items_product", product),
        Index("idx_radar_items_content_type", content_type),
        Index("idx_radar_items_published_date", published_date.desc().nullslast()),
        Index("idx_radar_items_tags", tags, postgresql_using="gin"),
    )


class RadarIngestionJob(Base):
    __tablename__ = "radar_ingestion_jobs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("radar_items.id", ondelete="SET NULL"), nullable=True
    )
    submitted_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, server_default="{}")

    item: Mapped[RadarItem | None] = relationship(back_populates="ingestion_jobs", lazy="raise")

    __table_args__ = (
        Index("idx_radar_ingestion_jobs_status", status),
        Index("idx_radar_ingestion_jobs_submitted_at", submitted_at.desc()),
    )
