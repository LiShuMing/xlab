from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from tech_radar.config import load_config
from tech_radar.delivery import create_delivery_adapters
from tech_radar.workspace import WorkspaceStore


class RouteMaterialsRequest(BaseModel):
    material_ids: list[str] = Field(min_length=1, max_length=100)
    topic_name: str = Field(min_length=1, max_length=120)


class CreateDraftRequest(BaseModel):
    limit: int = Field(default=12, ge=1, le=50)


class CreateArticleVersionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    summary: str = Field(max_length=2000)
    body_markdown: str = Field(min_length=1, max_length=200_000)
    expected_version: int = Field(ge=1)


class CreatePublicationsRequest(BaseModel):
    platforms: list[str] = Field(min_length=1, max_length=10)


class RecordPublishedRequest(BaseModel):
    external_url: str = Field(min_length=8, max_length=2000)
    confirmation_note: str = Field(min_length=1, max_length=2000)


def create_app(config_path: Path) -> FastAPI:
    config = load_config(config_path)
    store = WorkspaceStore(config.database)
    sync_report = store.initialize()

    app = FastAPI(
        title="Tech Radar Workspace",
        version="0.2.0",
        description="Local-first material and topic workspace API.",
    )
    app.state.config = config
    app.state.store = store
    app.state.sync_report = sync_report
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Idempotency-Key"],
    )

    @app.get("/api/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "database": str(config.database),
            "legacy_sync": {
                "scanned": sync_report.scanned,
                "inserted": sync_report.inserted,
                "updated": sync_report.updated,
            },
        }

    @app.get("/api/overview")
    def overview() -> dict[str, object]:
        return store.overview()

    @app.get("/api/materials")
    def materials(
        limit: int = Query(50, ge=1, le=100),
        cursor: str | None = None,
        view: str = Query("all", pattern="^(all|new|personal|needs_review)$"),
        platform: str | None = None,
        topic_id: str | None = None,
        q: str | None = Query(None, max_length=200),
    ) -> dict[str, object]:
        try:
            page = store.list_materials(
                limit=limit,
                cursor=cursor,
                view=view,
                platform=platform,
                topic_id=topic_id,
                query=q,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"items": page.items, "next_cursor": page.next_cursor}

    @app.get("/api/materials/{material_id}")
    def material(material_id: str) -> dict[str, object]:
        result = store.get_material(material_id)
        if result is None:
            raise HTTPException(status_code=404, detail="material not found")
        return result

    @app.post("/api/materials/batch/route")
    def route_materials(request: RouteMaterialsRequest) -> dict[str, object]:
        try:
            return store.route_materials(request.material_ids, request.topic_name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/topics")
    def topics() -> list[dict[str, object]]:
        return store.list_topics()

    @app.post("/api/topics/{topic_id}/drafts")
    def create_draft(
        topic_id: str, request: CreateDraftRequest
    ) -> dict[str, object]:
        try:
            return store.create_rule_article(topic_id, request.limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/articles/{article_id}")
    def article(article_id: str) -> dict[str, object]:
        result = store.get_article(article_id)
        if result is None:
            raise HTTPException(status_code=404, detail="article not found")
        return result

    @app.get("/api/articles")
    def articles(limit: int = Query(50, ge=1, le=100)) -> list[dict[str, object]]:
        return store.list_articles(limit)

    @app.post("/api/articles/{article_id}/versions")
    def create_article_version(
        article_id: str, request: CreateArticleVersionRequest
    ) -> dict[str, object]:
        try:
            return store.create_article_version(
                article_id,
                title=request.title,
                summary=request.summary,
                body_markdown=request.body_markdown,
                expected_version=request.expected_version,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/article-versions/{version_id}/approve")
    def approve_article(version_id: str) -> dict[str, object]:
        try:
            return store.approve_article_version(version_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/article-versions/{version_id}/publications")
    def create_publications(
        version_id: str, request: CreatePublicationsRequest
    ) -> list[dict[str, object]]:
        try:
            return store.create_publication_jobs(version_id, request.platforms)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/publications")
    def publications(
        limit: int = Query(100, ge=1, le=200)
    ) -> list[dict[str, object]]:
        return store.list_publications(limit)

    @app.post("/api/publication-jobs/{job_id}/prepare")
    def prepare_publication(job_id: str) -> dict[str, object]:
        try:
            return store.prepare_publication(job_id)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/publication-jobs/{job_id}/preview")
    def preview_publication(job_id: str) -> dict[str, object]:
        try:
            return store.preview_publication(job_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/publication-jobs/{job_id}/record-published")
    def record_publication(
        job_id: str, request: RecordPublishedRequest
    ) -> dict[str, object]:
        try:
            return store.record_publication(
                job_id,
                external_url=request.external_url,
                confirmation_note=request.confirmation_note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/extensions/deliveries")
    def delivery_extensions() -> list[dict[str, object]]:
        return [
            {
                "id": adapter.manifest.id,
                "platform": adapter.manifest.platform,
                "version": adapter.manifest.version,
                "capabilities": adapter.manifest.capabilities,
                "manual_confirmation_required": (
                    adapter.manifest.manual_confirmation_required
                ),
            }
            for adapter in create_delivery_adapters().values()
        ]

    @app.get("/api/artifacts/{artifact_id}", include_in_schema=False)
    def artifact(artifact_id: str) -> FileResponse:
        try:
            path = store.artifact_path(artifact_id)
        except ValueError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        if path is None or not path.is_file():
            raise HTTPException(status_code=404, detail="artifact not found")
        return FileResponse(path)

    @app.get("/api/runs")
    def runs(limit: int = Query(20, ge=1, le=100)) -> list[dict[str, object]]:
        return store.list_runs(limit)

    web_dist = Path(__file__).resolve().parents[3] / "web" / "dist"
    assets = web_dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False, response_model=None)
    def frontend(path: str) -> FileResponse | dict[str, str]:
        index = web_dist / "index.html"
        if index.is_file() and not path.startswith("api/"):
            return FileResponse(index)
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API route not found")
        return {
            "message": "Tech Radar API is running; build web/ to enable the UI.",
            "docs": "/docs",
        }

    return app
