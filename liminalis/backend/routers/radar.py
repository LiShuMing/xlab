"""Radar feed API routes."""

from fastapi import APIRouter, Depends, Query

from backend._shared.storage import business_uow
from backend.services.radar_service import RadarQuery, read_radar_items, read_snapshot_radar_items
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
) -> dict:
    radar_query = RadarQuery(
        page=page,
        per_page=per_page,
        content_type=content_type,
        product=product,
        query=q,
    )
    if not settings.postgres_configured:
        return read_snapshot_radar_items(settings, radar_query)

    async with business_uow() as session:
        return await read_radar_items(session, settings, radar_query)
