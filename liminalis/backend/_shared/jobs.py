"""arq queue client wrapper.

M0 only exposes the connection pool factory and the WorkerSettings base
that backend/workers/ extends. M1+ registers actual tasks (radar.ingest_link,
invest.analyze_stock, ego.consolidate_memory).
"""

from __future__ import annotations

import uuid
from enum import StrEnum

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from backend._shared.serializers import utc_now
from backend.settings import Settings, get_settings

_pool: ArqRedis | None = None


class JobStatus(StrEnum):
    """Common job lifecycle labels."""

    QUEUED = "queued"
    FETCHING = "fetching"
    EXTRACTING = "extracting"
    ANALYZING = "analyzing"
    SAVING = "saving"
    COMPLETED = "completed"
    FAILED = "failed"
    DUPLICATE = "duplicate"


TERMINAL_JOB_STATUSES = {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.DUPLICATE}


class TaskStatus(StrEnum):
    """Common durable task lifecycle labels."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


TERMINAL_TASK_STATUSES = {TaskStatus.COMPLETED, TaskStatus.FAILED}


def new_job_id(prefix: str = "job") -> str:
    """Create a compact, sortable-ish job id."""
    return f"{prefix}_{utc_now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def redis_settings_from(settings: Settings) -> RedisSettings:
    """Translate liminalis Settings into arq's RedisSettings."""
    return RedisSettings.from_dsn(settings.redis_url)


async def get_arq_pool() -> ArqRedis:
    """FastAPI dependency — yields a cached arq Redis pool."""
    global _pool
    if _pool is None:
        _pool = await create_pool(redis_settings_from(get_settings()))
    return _pool


async def dispose_arq_pool() -> None:
    """Tear down the cached pool; call from app shutdown hooks / tests."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def reset_arq_pool() -> None:
    """Pytest helper — drop cached pool."""
    global _pool
    _pool = None
