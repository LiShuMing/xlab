"""Radar admin service helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from werkzeug.security import check_password_hash

from backend._shared.auth import read_signed_payload, sign_payload
from backend._shared.jobs import new_job_id
from backend.radar.service import (
    create_ingestion_job as _create_pg_job,
)
from backend.radar.service import (
    get_ingestion_job as _get_pg_job,
)
from backend.radar.service import ingestion_job_to_dict
from backend.radar.service import (
    list_ingestion_jobs as _list_pg_jobs,
)
from backend.settings import Settings

COOKIE_NAME = "liminalis_radar_admin"


def admin_username(settings: Settings) -> str:
    return settings.radar_admin_user


def verify_admin_password(settings: Settings, password: str) -> bool:
    password_hash = settings.radar_admin_password_hash or ""
    plain_password = settings.radar_admin_password
    if password_hash:
        return check_password_hash(password_hash, password)
    return bool(plain_password) and password == plain_password


def create_session_token(settings: Settings) -> str:
    return sign_payload(settings, {"user": admin_username(settings)}, salt="liminalis-radar-admin")


def read_session_user(settings: Settings, token: str | None) -> str | None:
    if not token:
        return None
    data = read_signed_payload(settings, token, salt="liminalis-radar-admin")
    if data is None:
        return None
    user = data.get("user")
    return user if user == admin_username(settings) else None


async def create_ingestion_job(
    *,
    session: AsyncSession,
    settings: Settings,
    url: str,
    product: str = "",
    source: str = "",
    tags: list[str] | None = None,
    note: str = "",
) -> dict[str, Any]:
    job = await _create_pg_job(
        session,
        job_id=new_job_id("job"),
        url=url,
        submitted_by=admin_username(settings),
        metadata={
            "product": product,
            "source": source,
            "tags": tags or [],
            "note": note,
        },
    )
    return ingestion_job_to_dict(job)


async def get_ingestion_job(session: AsyncSession, job_id: str) -> dict[str, Any] | None:
    job = await _get_pg_job(session, job_id)
    if not job:
        return None
    return ingestion_job_to_dict(job)


async def list_ingestion_jobs(session: AsyncSession, limit: int = 30) -> list[dict[str, Any]]:
    jobs = await _list_pg_jobs(session, limit=limit)
    return [ingestion_job_to_dict(job) for job in jobs]
