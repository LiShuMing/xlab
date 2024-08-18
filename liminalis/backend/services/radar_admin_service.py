"""Radar admin service helpers."""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any

from arq.connections import ArqRedis
from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy.ext.asyncio import AsyncSession
from werkzeug.security import check_password_hash

from backend.radar.service import (
    create_ingestion_job as _create_pg_job,
)
from backend.radar.service import (
    get_ingestion_job as _get_pg_job,
)
from backend.radar.service import (
    list_ingestion_jobs as _list_pg_jobs,
)
from backend.settings import Settings

COOKIE_NAME = "liminalis_radar_admin"


def admin_username(settings: Settings) -> str:
    return os.environ.get("RADAR_ADMIN_USER") or settings.radar_admin_user


def verify_admin_password(settings: Settings, password: str) -> bool:
    password_hash = settings.radar_admin_password_hash or os.environ.get("RADAR_ADMIN_PASSWORD_HASH", "")
    plain_password = os.environ.get("RADAR_ADMIN_PASSWORD") or settings.radar_admin_password
    if password_hash:
        return check_password_hash(password_hash, password)
    return bool(plain_password) and password == plain_password


def session_serializer(settings: Settings) -> URLSafeSerializer:
    return URLSafeSerializer(settings.session_secret, salt="liminalis-radar-admin")


def create_session_token(settings: Settings) -> str:
    return session_serializer(settings).dumps({"user": admin_username(settings)})


def read_session_user(settings: Settings, token: str | None) -> str | None:
    if not token:
        return None
    try:
        data = session_serializer(settings).loads(token)
    except BadSignature:
        return None
    user = data.get("user")
    return user if user == admin_username(settings) else None


async def create_ingestion_job(
    *,
    session: AsyncSession,
    arq_pool: ArqRedis,
    settings: Settings,
    url: str,
    product: str = "",
    source: str = "",
    tags: list[str] | None = None,
    note: str = "",
) -> dict[str, Any]:
    job_id = f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    job = await _create_pg_job(
        session,
        job_id=job_id,
        url=url,
        submitted_by=admin_username(settings),
        metadata={
            "product": product,
            "source": source,
            "tags": tags or [],
            "note": note,
        },
    )
    await session.commit()

    await arq_pool.enqueue_job(
        "ingest_link_task",
        job_id=job_id,
        request_data={
            "url": url,
            "product": product,
            "source": source,
            "tags": tags or [],
            "note": note,
        },
        submitted_by=admin_username(settings),
    )

    return {
        "id": job.id,
        "status": job.status,
        "url": job.url,
        "submitted_by": job.submitted_by,
        "submitted_at": job.submitted_at.isoformat() if job.submitted_at else None,
    }


async def get_ingestion_job(session: AsyncSession, job_id: str) -> dict[str, Any] | None:
    job = await _get_pg_job(session, job_id)
    if not job:
        return None
    return {
        "id": job.id,
        "url": job.url,
        "status": job.status,
        "error": job.error,
        "item_id": job.item_id,
        "submitted_by": job.submitted_by,
        "submitted_at": job.submitted_at.isoformat() if job.submitted_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "metadata": job.metadata_,
    }


async def list_ingestion_jobs(session: AsyncSession, limit: int = 30) -> list[dict[str, Any]]:
    jobs = await _list_pg_jobs(session, limit=limit)
    return [
        {
            "id": j.id,
            "url": j.url,
            "status": j.status,
            "error": j.error,
            "item_id": j.item_id,
            "submitted_by": j.submitted_by,
            "submitted_at": j.submitted_at.isoformat() if j.submitted_at else None,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            "metadata": j.metadata_,
        }
        for j in jobs
    ]
