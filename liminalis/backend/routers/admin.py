"""Radar admin API routes."""

from __future__ import annotations

from arq.connections import ArqRedis
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend._shared.jobs import get_arq_pool
from backend._shared.storage import business_uow, get_business_session
from backend.services.radar_admin_service import (
    COOKIE_NAME,
    admin_username,
    create_session_token,
    read_session_user,
    verify_admin_password,
)
from backend.services.radar_admin_service import (
    create_ingestion_job as _create_job,
)
from backend.services.radar_admin_service import (
    get_ingestion_job as _get_job,
)
from backend.services.radar_admin_service import (
    list_ingestion_jobs as _list_jobs,
)
from backend.settings import Settings, get_settings

router = APIRouter(prefix="/api/admin", tags=["admin"])


class LoginRequest(BaseModel):
    username: str = ""
    password: str = ""


class LinkIngestionRequest(BaseModel):
    url: str
    product: str = ""
    source: str = ""
    tags: list[str] = Field(default_factory=list)
    note: str = ""


def current_admin_user(
    settings: Settings = Depends(get_settings),
    token: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> str:
    user = read_session_user(settings, token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="admin authentication required")
    return user


@router.post("/login")
def login(
    payload: LoginRequest, response: Response, settings: Settings = Depends(get_settings)
) -> dict[str, object]:
    if payload.username != admin_username(settings) or not verify_admin_password(settings, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    response.set_cookie(
        COOKIE_NAME,
        create_session_token(settings),
        httponly=True,
        secure=settings.cookie_secure or settings.is_production,
        samesite="lax",
        path="/",
    )
    return {"ok": True, "user": admin_username(settings)}


@router.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(
    settings: Settings = Depends(get_settings),
    token: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> dict[str, object]:
    user = read_session_user(settings, token)
    return {"authenticated": bool(user), "user": user}


@router.post("/radar/links", status_code=status.HTTP_202_ACCEPTED)
async def submit_link(
    payload: LinkIngestionRequest,
    settings: Settings = Depends(get_settings),
    arq_pool: ArqRedis = Depends(get_arq_pool),
    _: str = Depends(current_admin_user),
) -> dict[str, object]:
    url = payload.url.strip()
    if not url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="url is required")

    product = payload.product.strip()
    source = payload.source.strip()
    tags = payload.tags
    note = payload.note.strip()

    async with business_uow() as session:
        job = await _create_job(
            session=session,
            settings=settings,
            url=url,
            product=product,
            source=source,
            tags=tags,
            note=note,
        )

    await arq_pool.enqueue_job(
        "ingest_link_task",
        job_id=job["id"],
        request_data={
            "url": url,
            "product": product,
            "source": source,
            "tags": tags or [],
            "note": note,
        },
        submitted_by=job["submitted_by"],
    )
    return {"jobId": job["id"], "status": job["status"], "job": job}


@router.get("/radar/jobs")
async def list_jobs(
    limit: int = Query(default=30, ge=1, le=100),
    session: AsyncSession = Depends(get_business_session),
    _: str = Depends(current_admin_user),
) -> dict[str, object]:
    return {"jobs": await _list_jobs(session, limit=limit)}


@router.get("/radar/jobs/{job_id}")
async def get_job(
    job_id: str,
    session: AsyncSession = Depends(get_business_session),
    _: str = Depends(current_admin_user),
) -> dict[str, object]:
    job = await _get_job(session, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return {"job": job}
