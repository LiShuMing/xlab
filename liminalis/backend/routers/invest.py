"""Investment analysis API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.services.invest_service import analyze_stock, get_cached_report
from backend.services.invest_service import status as invest_status
from backend.settings import Settings, get_settings

router = APIRouter(prefix="/api/invest", tags=["invest"])


class AnalyzeStockRequest(BaseModel):
    stock: str = ""
    stock_code: str = ""
    query: str = "价值投资分析"
    lang: str = "zh"
    mode: str = "fast"
    use_cache: bool = True


@router.get("/status")
def get_status() -> dict[str, object]:
    return invest_status()


@router.post("/analyze-stock")
async def post_analyze_stock(
    payload: AnalyzeStockRequest,
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    stock_code = (payload.stock or payload.stock_code).strip()
    query = payload.query.strip() or "价值投资分析"
    lang = payload.lang.strip() or "zh"
    mode = payload.mode.strip() or "fast"

    if not stock_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="stock is required")

    if payload.use_cache:
        cached = get_cached_report(settings, stock_code, mode)
        if cached:
            return JSONResponse({"success": True, "cached": True, **cached})

    report = await analyze_stock(settings, stock_code=stock_code, query=query, lang=lang, mode=mode)
    return JSONResponse({"success": True, **report})
