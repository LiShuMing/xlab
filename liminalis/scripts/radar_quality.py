"""Live Radar audit using configured feeds, LLM, PostgreSQL and ASGI API.

Run with: .venv/bin/python -m scripts.radar_quality --refresh --rounds 2
Outputs contain public source material only; credentials are never serialized.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import shutil
from collections import Counter
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from time import perf_counter

import httpx
from sqlalchemy import select

from backend._shared.storage import business_uow
from backend.radar.db_models import RadarItem
from backend.radar.refresh import load_radar_artifact, refresh_latest_radar_news
from backend.settings import Settings, get_settings


def local_settings(settings: Settings) -> Settings:
    """Explicit isolated mode; no PostgreSQL credentials or connections are used."""
    return settings.model_copy(
        update={
            "data_dir": settings.data_dir / "e2e-local",
            "pgsql_url": None,
            "pgsql_host": None,
            "pgsql_user": None,
            "pgsql_password": None,
            "pgsql_passfile": None,
            "radar_refresh_on_startup": False,
        }
    )


def create_local_app():
    """Local browser preview: uvicorn scripts.radar_quality:create_local_app --factory."""
    from backend.app import create_app

    settings = local_settings(Settings())
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings

    @asynccontextmanager
    async def lifespan(_app):
        # Local preview must not start unrelated business DB jobs.
        yield

    app.router.lifespan_context = lifespan
    return app


async def audit(settings: Settings, *, pending: bool = False, storage: str = "postgres") -> dict:
    from backend.app import create_app

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings

    payload = (
        json.loads((settings.data_dir / "artifacts/radar/pending.json").read_text())
        if pending
        else load_radar_artifact(settings)
    )
    items = payload.get("items", [])
    errors: list[dict] = []
    checked = 0
    if settings.postgres_configured and not pending:
        async with business_uow() as session:
            rows = (
                (
                    await session.execute(
                        select(RadarItem).where(RadarItem.url.in_([item["url"] for item in items]))
                    )
                )
                .scalars()
                .all()
            )
        by_url = {row.url: row for row in rows}
        for item in items:
            row = by_url.get(item["url"])
            if row is None:
                errors.append({"url": item["url"], "error": "missing_database_row"})
                continue
            for field, attr in (
                ("summary", "summary"),
                ("contentHash", "content_hash"),
                ("analysisProvider", "analysis_provider"),
                ("evidence", "evidence"),
            ):
                if item.get(field) != getattr(row, attr):
                    errors.append({"url": item["url"], "error": f"database_mismatch:{field}"})
            if hashlib.sha256(row.raw_content.encode()).hexdigest() != row.content_hash:
                errors.append({"url": item["url"], "error": "source_hash_mismatch"})
            source = " ".join(row.raw_content.split())
            for evidence in item.get("evidence", []):
                checked += 1
                if not evidence.get("text") or " ".join(evidence["text"].split()) not in source:
                    errors.append({"url": item["url"], "error": "ungrounded_quote"})
    else:
        if storage != "local":
            errors.append({"error": "postgres_unavailable:durable_storage_unverified"})
        checkpoint_path = settings.data_dir / "artifacts/radar/pending.json"
        checkpoint = json.loads(checkpoint_path.read_text()) if checkpoint_path.exists() else {"items": []}
        sources = {item["url"]: item for item in checkpoint["items"]}
        for item in items:
            stored = sources.get(item["url"], {})
            raw = stored.get("rawContent", "")
            if hashlib.sha256(raw.encode()).hexdigest() != item.get("contentHash"):
                errors.append({"url": item["url"], "error": "source_hash_mismatch"})
            for field in ("summary", "evidence", "analysisProvider"):
                if stored.get(field) != item.get(field):
                    errors.append({"url": item["url"], "error": f"checkpoint_mismatch:{field}"})
            source = " ".join(raw.split())
            for evidence in item.get("evidence", []):
                checked += 1
                if not evidence.get("text") or " ".join(evidence["text"].split()) not in source:
                    errors.append({"url": item["url"], "error": "ungrounded_quote"})

    # In-process HTTP traverses the actual router, service and configured DB.
    # ASGITransport does not start background refresh or other app lifecycle jobs.
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://audit.local"
    ) as client:
        response = await client.get("/api/radar/items", params={"per_page": 100})
        response.raise_for_status()
        api = response.json()
        api_by_url = {item["url"]: item for item in api["items"]}
        if storage == "local":
            page = api
            while page.get("has_next"):
                response = await client.get(
                    "/api/radar/items", params={"per_page": 100, "page": page["page"] + 1}
                )
                response.raise_for_status()
                page = response.json()
                api_by_url.update({item["url"]: item for item in page["items"]})
        expected_storage = "artifact" if storage == "local" else "postgres"
        if api.get("storage") != expected_storage:
            errors.append({"error": f"api_storage_not_{expected_storage}"})
        for item in [] if pending else (items if storage == "local" else items[:10]):
            served = api_by_url.get(item["url"], {})
            for field in ("summary", "evidence", "contentHash", "analysisProvider"):
                if served.get(field) != item.get(field):
                    errors.append({"url": item["url"], "error": f"api_mismatch:{field}"})
        missing = await client.get("/api/radar/items", params={"product": "__radar_audit_no_such_product__"})
        missing.raise_for_status()
        if missing.json()["items"]:
            errors.append({"error": "empty_filter_fell_back_to_snapshot"})
        search = await client.get("/api/radar/items", params={"q": "数据库"})
        search.raise_for_status()
        frontend = await client.get("/radar")
        if frontend.status_code != 200:
            errors.append({"error": "frontend_not_built"})
    return {
        "checkedAt": datetime.now(UTC).isoformat(),
        "storageMode": storage,
        "skippedChecks": ["PostgreSQL migrations", "PostgreSQL upsert", "PostgreSQL search/indexes"]
        if storage == "local"
        else [],
        "items": len(items),
        "products": len({item.get("product") for item in items}),
        "providers": dict(Counter(item.get("analysisProvider", "unknown") for item in items)),
        "chineseSummaries": sum(
            bool(re.search(r"[\u4e00-\u9fff]", item.get("summary", ""))) for item in items
        ),
        "sourceQuotesChecked": checked,
        "errors": errors,
        "apiTotalItems": api["total_items"],
        "chineseSearchResults": search.json()["total_items"],
        "metrics": payload.get("metrics", {}),
        "feedHealth": payload.get("feedHealth", []),
        "sample": [
            {
                key: item.get(key)
                for key in (
                    "url",
                    "title",
                    "originalTitle",
                    "product",
                    "contentType",
                    "summary",
                    "evidence",
                    "analysisProvider",
                )
            }
            for item in items[:10]
        ],
        "limits": "Quote presence checks provenance, not semantic entailment. Human review is still required; vendor benchmarks are not independently reproduced.",
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh", action="store_true", help="Fetch, analyze and persist real data before audit"
    )
    parser.add_argument("--rounds", type=int, choices=range(1, 4), default=1)
    parser.add_argument("--storage", choices=("postgres", "local"), default="postgres")
    args = parser.parse_args()
    settings = Settings()
    if args.storage == "local":
        source = settings.data_dir / "artifacts/radar/pending.json"
        settings = local_settings(settings)
        target = settings.data_dir / "artifacts/radar/pending.json"
        if source.exists() and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    reports = []
    for index in range(args.rounds):
        started = perf_counter()
        pending = False
        try:
            refresh = await refresh_latest_radar_news(settings) if args.refresh else None
        except Exception as exc:
            refresh = {"state": "failed", "error": type(exc).__name__}
            pending = (settings.data_dir / "artifacts/radar/pending.json").exists()
        report = await audit(settings, pending=pending, storage=args.storage)
        if refresh and refresh.get("state") != "completed":
            report["errors"].append({"error": "refresh_failed", "reason": refresh.get("error")})
        report["refresh"] = refresh
        report["durationSeconds"] = round(perf_counter() - started, 2)
        reports.append(report)
        print(
            json.dumps(
                {
                    "round": index + 1,
                    **{
                        key: report[key]
                        for key in (
                            "storageMode",
                            "skippedChecks",
                            "items",
                            "products",
                            "providers",
                            "sourceQuotesChecked",
                            "errors",
                            "metrics",
                            "durationSeconds",
                            "chineseSearchResults",
                        )
                    },
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    path = (
        settings.data_dir
        / "artifacts"
        / "radar"
        / "quality"
        / (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + ".json")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Report: {path}")
    if any(report["errors"] for report in reports):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
