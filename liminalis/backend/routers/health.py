"""Health and runtime introspection endpoints."""

import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import bindparam, text

from backend._shared.serializers import utc_now_iso
from backend._shared.storage import describe_storage
from backend.db.engine import get_engine
from backend.radar.refresh import get_radar_refresh_status
from backend.settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, object]:
    settings = get_settings()
    storage = describe_storage(settings)
    return {
        "ok": True,
        "service": settings.app_name,
        "dataDir": str(settings.data_dir),
        "database": {
            "backend": storage.business_backend,
            "name": storage.business_database,
            "configured": settings.postgres_configured,
            "remote": storage.business_remote,
        },
        "storage": {
            "business": {
                "class": "business_database",
                "backend": storage.business_backend,
                "database": storage.business_database,
                "remote": storage.business_remote,
                "readFallback": storage.business_read_fallback,
            },
            "runtimeCache": {
                "class": "runtime_cache",
                "path": str(storage.runtime_cache_dir),
            },
            "staticSnapshot": {
                "class": "static_snapshot",
                "path": str(storage.static_snapshot_dir),
            },
            "localArtifacts": {
                "class": "local_artifacts",
                "path": str(storage.local_artifact_dir),
            },
        },
        "radarRefresh": get_radar_refresh_status(),
        "timestamp": utc_now_iso(),
    }


@router.get("/health/deep")
async def deep_health() -> JSONResponse:
    settings = get_settings()
    checks: dict[str, object] = {
        "database": {
            "configured": settings.postgres_configured,
            "ok": not settings.postgres_configured,
            "backend": settings.business_database_backend,
        },
        "llm": {
            "configured": bool(settings.llm_api_key),
            "model": settings.llm_model,
        },
        "llmWiki": {
            "mode": "socket" if settings.llm_wiki_socket else "url",
            "target": str(settings.llm_wiki_socket or settings.llm_wiki_url),
        },
        "radarRefresh": {
            "enabled": settings.radar_refresh_on_startup,
            **get_radar_refresh_status(),
        },
    }

    if settings.postgres_configured:
        try:
            missing_tables = await asyncio.wait_for(
                _check_database_schema(),
                timeout=settings.health_check_timeout,
            )
            checks["database"] = {
                "configured": True,
                "ok": not missing_tables,
                "backend": settings.business_database_backend,
                "name": settings.business_database_name,
                "remote": settings.business_database_remote,
                "schemaReady": not missing_tables,
                "missingTables": missing_tables,
            }
        except Exception as exc:
            checks["database"] = {
                "configured": True,
                "ok": False,
                "backend": settings.business_database_backend,
                "name": settings.business_database_name,
                "remote": settings.business_database_remote,
                "error": exc.__class__.__name__,
            }

    ok = all(bool(check.get("ok", True)) if isinstance(check, dict) else True for check in checks.values())
    return JSONResponse(
        status_code=200 if ok else 503,
        content={
            "ok": ok,
            "service": settings.app_name,
            "checks": checks,
            "timestamp": utc_now_iso(),
        },
    )


async def _check_database_schema() -> list[str]:
    required_tables = [
        "radar_items",
        "radar_ingestion_jobs",
        "invest_daily_reports",
        "invest_stock_configs",
        "invest_theses",
        "invest_watch_items",
        "invest_journal_entries",
        "invest_reviews",
        "ego_records",
        "ego_sessions",
        "ego_messages",
        "ego_memories",
        "ego_profiles",
        "liminalis_users",
        "liminalis_user_identities",
    ]
    async with get_engine().connect() as conn:
        await conn.execute(text("select 1"))
        stmt = text(
            """
                select table_name
                from information_schema.tables
                where table_schema = 'public'
                  and table_name in :required_tables
                """
        ).bindparams(bindparam("required_tables", expanding=True))
        rows = await conn.execute(
            stmt,
            {"required_tables": required_tables},
        )
        existing = {row[0] for row in rows}
    return [table for table in required_tables if table not in existing]
