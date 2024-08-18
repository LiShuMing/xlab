"""arq worker configuration.

WorkerSettings is the single registry for tasks across all domains. Each
milestone appends its tasks here:

- M1 (radar): ingest_link, generate_summary
- M2 (invest): analyze_stock
- M3 (ego):   consolidate_memory

Run with: `liminalis worker` or `arq backend.workers.WorkerSettings`.
"""

from __future__ import annotations

from arq.connections import RedisSettings

from backend._shared.jobs import redis_settings_from
from backend.radar.tasks import ingest_link_task  # noqa: F401  # isort: split
from backend.settings import get_settings


async def startup(_ctx: dict[str, object]) -> None:
    from backend._shared.logging import configure_logging

    configure_logging(get_settings())


async def shutdown(_ctx: dict[str, object]) -> None:  # pragma: no cover
    pass


def _build_redis_settings() -> RedisSettings:
    return redis_settings_from(get_settings())


class WorkerSettings:
    """arq worker config. arq reads this class's attributes directly so each
    field must be a class attribute (not a property). Domain modules in M1+
    extend `functions` and `cron_jobs`."""

    functions: list = [  # type: ignore[type-arg]
        ingest_link_task,
    ]
    cron_jobs: list = []  # type: ignore[type-arg]
    on_startup = startup
    on_shutdown = shutdown
    job_timeout = 600  # 10 min default for invest/radar long tasks
    max_jobs = 8
    redis_settings = _build_redis_settings()
