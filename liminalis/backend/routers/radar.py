"""Radar feed API routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.engine import get_session
from backend.services.radar_service import RadarQuery, read_radar_items
from backend.settings import Settings, get_settings

router = APIRouter(prefix="/api/radar", tags=["radar"])


@router.get("/items")
async def get_radar_items(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=80, ge=1, le=100),
    content_type: str = Query(default="all", alias="type"),
    product: str = "all",
    q: str = "",
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await read_radar_items(
        session,
        settings,
        RadarQuery(
            page=page,
            per_page=per_page,
            content_type=content_type,
            product=product,
            query=q,
        ),
    )
