"""FastAPI entrypoint for the unified Liminalis backend."""

import logging
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.routers import admin, ego, health, invest, radar, wechat
from backend.settings import Settings, get_settings

logger = logging.getLogger("liminalis")


SPA_ROUTES = {
    "",
    "logos",
    "reports",
    "blogs",
    "radar",
    "invest",
    "ego",
    "ego/login",
    "ego/record",
    "ego/chat",
    "ego/timeline",
    "ego/me",
    "ego/roles",
    "praxis",
    "about",
    "wechat/callback",
}


def register_frontend(app: FastAPI, settings: Settings) -> None:
    dist_dir = settings.frontend_dist_dir
    assets_dir = dist_dir / "assets"

    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str = "") -> FileResponse:
        if full_path == "api" or full_path.startswith(("api/", "health")):
            raise HTTPException(status_code=404, detail="Not Found")

        requested = (dist_dir / full_path).resolve()
        if dist_dir.exists() and requested.is_file() and _is_relative_to(requested, dist_dir):
            return FileResponse(requested)

        index_file = dist_dir / "index.html"
        route = full_path.strip("/")
        if index_file.exists() and (route in SPA_ROUTES or not Path(route).suffix):
            return FileResponse(index_file)

        raise HTTPException(status_code=404, detail="Frontend build not found")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent.resolve())
        return True
    except ValueError:
        return False


class _TraceFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "trace_id"):
            record.trace_id = "-"
        return True


def _configure_logging(settings: Settings) -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s [%(trace_id)s] %(message)s"))
    handler.addFilter(_TraceFilter())
    root.addHandler(handler)
    root.setLevel(logging.INFO if settings.is_production else logging.DEBUG)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        trace_id = uuid.uuid4().hex[:12]
        logger.exception(
            "Unhandled exception on %s %s",
            request.method,
            request.url.path,
            extra={"trace_id": trace_id},
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "internal server error", "trace_id": trace_id},
        )


def register_cors(app: FastAPI, settings: Settings) -> None:
    origins = settings.cors_allowed_origins
    if not origins:
        return
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def create_app() -> FastAPI:
    settings = get_settings()
    _configure_logging(settings)
    app = FastAPI(title=settings.app_name)
    register_cors(app, settings)
    app.include_router(health.router)
    app.include_router(radar.router)
    app.include_router(admin.router)
    app.include_router(invest.router)
    app.include_router(ego.router)
    app.include_router(wechat.router)
    register_exception_handlers(app)
    register_frontend(app, settings)
    return app


app = create_app()


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run("backend.app:app", host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
