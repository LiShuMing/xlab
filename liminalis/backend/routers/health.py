"""Health and runtime introspection endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter

from backend.settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, object]:
    settings = get_settings()
    return {
        "ok": True,
        "service": settings.app_name,
        "dataDir": str(settings.data_dir),
        "database": {
            "backend": "postgres" if settings.postgres_configured else "fallback",
            "name": settings.pgsql_database if settings.postgres_configured else None,
            "configured": settings.postgres_configured,
        },
        "timestamp": datetime.now(UTC).isoformat(),
    }
