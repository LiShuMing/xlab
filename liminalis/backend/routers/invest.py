"""Investment analysis API routes."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend._shared.errors import require_business_database, should_fallback_after_read_error
from backend._shared.storage import business_uow
from backend.invest import workspace as invest_workspace
from backend.services.invest_service import (
    analyze_stock,
    delete_reports,
    get_cached_report,
    get_workspace_snapshot,
    list_configured_stocks,
    list_reports,
    list_stocks,
)
from backend.services.invest_service import get_dashboard_report as get_invest_report
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


class UpsertThesisRequest(BaseModel):
    stock_code: str = ""
    stock_name: str | None = None
    status: str = "watchlist"
    core_thesis: str = ""
    supporting_evidence: list[str] = Field(default_factory=list)
    counter_evidence: list[str] = Field(default_factory=list)
    disconfirming_signals: list[str] = Field(default_factory=list)
    margin_of_safety: str = ""
    expected_holding_period: str = ""
    confidence: str = "medium"
    source_report_id: int | None = None


class CreateWatchItemRequest(BaseModel):
    thesis_id: int | None = None
    kind: str = "manual"
    title: str
    condition: str = ""
    priority: int = 0
    due_date: date | None = None


class UpdateWatchItemStatusRequest(BaseModel):
    status: str


class CreateJournalEntryRequest(BaseModel):
    thesis_id: int | None = None
    entry_type: str
    action: str = ""
    price: float | None = None
    reason: str = ""
    emotion: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)
    review_at: date | None = None


class CreateReviewRequest(BaseModel):
    thesis_id: int | None = None
    decision: str = "no_action"
    thesis_valid: bool | None = None
    evidence_update: str = ""
    valuation_update: str = ""
    discipline_notes: str = ""
    next_action: str = ""


@router.get("/status")
def get_status() -> dict[str, object]:
    return invest_status()


@router.get("/stocks")
async def get_stocks(
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    if not settings.postgres_configured:
        return list_configured_stocks(settings)
    try:
        async with business_uow() as session:
            return await list_stocks(session, settings)
    except Exception:
        if not should_fallback_after_read_error(settings):
            raise
        return list_configured_stocks(settings)


@router.get("/reports")
async def get_reports(
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    if not settings.postgres_configured:
        return {"reports": []}
    try:
        async with business_uow() as session:
            return await list_reports(session, settings)
    except Exception:
        if not should_fallback_after_read_error(settings):
            raise
        return {"reports": []}


@router.delete("/reports")
async def delete_all_invest_reports(
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    if not settings.postgres_configured:
        return {"success": True, "deleted": 0}
    try:
        async with business_uow() as session:
            return await delete_reports(session, settings)
    except Exception:
        if not should_fallback_after_read_error(settings):
            raise
        return {"success": True, "deleted": 0}


@router.get("/report/{stock_code}")
async def get_report(
    stock_code: str,
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    if not settings.postgres_configured:
        return {"error": "Report not found"}
    try:
        async with business_uow() as session:
            return await get_invest_report(session, settings, stock_code)
    except Exception:
        if not should_fallback_after_read_error(settings):
            raise
        return {"error": "Report not found"}


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
    require_business_database(settings)

    async with business_uow() as session:
        if payload.use_cache:
            cached = await get_cached_report(session, settings, stock_code, mode)
            if cached:
                snapshot = await get_workspace_snapshot(session, stock_code)
                return JSONResponse({"success": True, "cached": True, **cached, **snapshot})

        report = await analyze_stock(
            session,
            settings,
            stock_code=stock_code,
            query=query,
            lang=lang,
            mode=mode,
        )
    return JSONResponse({"success": True, **report})


@router.get("/workspace/{stock_code}")
async def get_workspace(
    stock_code: str,
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_business_database(settings)
    async with business_uow() as session:
        return await get_workspace_snapshot(session, stock_code.strip())


@router.get("/theses")
async def list_invest_theses(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    require_business_database(settings)
    async with business_uow() as session:
        rows = await invest_workspace.list_theses(session)
        return {"theses": [invest_workspace.serialize_thesis(row) for row in rows]}


@router.put("/thesis/{stock_code}")
async def put_invest_thesis(
    stock_code: str,
    payload: UpsertThesisRequest,
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_business_database(settings)
    final_stock_code = (payload.stock_code or stock_code).strip()
    if not final_stock_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="stock_code is required")
    async with business_uow() as session:
        thesis = await invest_workspace.upsert_thesis(
            session,
            stock_code=final_stock_code,
            stock_name=payload.stock_name,
            status=payload.status,
            core_thesis=payload.core_thesis,
            supporting_evidence=payload.supporting_evidence,
            counter_evidence=payload.counter_evidence,
            disconfirming_signals=payload.disconfirming_signals,
            margin_of_safety=payload.margin_of_safety,
            expected_holding_period=payload.expected_holding_period,
            confidence=payload.confidence,
            source_report_id=payload.source_report_id,
        )
        await invest_workspace.ensure_default_watch_items(session, thesis)
        return {"thesis": invest_workspace.serialize_thesis(thesis)}


@router.post("/watch-items/{stock_code}")
async def post_watch_item(
    stock_code: str,
    payload: CreateWatchItemRequest,
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_business_database(settings)
    async with business_uow() as session:
        row = await invest_workspace.create_watch_item(
            session,
            stock_code=stock_code.strip(),
            thesis_id=payload.thesis_id,
            kind=payload.kind,
            title=payload.title,
            condition=payload.condition,
            priority=payload.priority,
            due_date=payload.due_date,
        )
        return {"watch_item": invest_workspace.serialize_watch_item(row)}


@router.patch("/watch-items/{item_id}")
async def patch_watch_item_status(
    item_id: int,
    payload: UpdateWatchItemStatusRequest,
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_business_database(settings)
    async with business_uow() as session:
        ok = await invest_workspace.update_watch_item_status(session, item_id, payload.status)
        if not ok:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="watch item not found")
        return {"success": True}


@router.delete("/watch-items/{item_id}")
async def delete_watch_item(
    item_id: int,
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_business_database(settings)
    async with business_uow() as session:
        ok = await invest_workspace.delete_watch_item(session, item_id)
        if not ok:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="watch item not found")
        return {"success": True}


@router.post("/journal/{stock_code}")
async def post_journal_entry(
    stock_code: str,
    payload: CreateJournalEntryRequest,
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_business_database(settings)
    async with business_uow() as session:
        row = await invest_workspace.create_journal_entry(
            session,
            stock_code=stock_code.strip(),
            thesis_id=payload.thesis_id,
            entry_type=payload.entry_type,
            action=payload.action,
            price=payload.price,
            reason=payload.reason,
            emotion=payload.emotion,
            meta=payload.meta,
            review_at=payload.review_at,
        )
        return {"journal_entry": invest_workspace.serialize_journal_entry(row)}


@router.post("/reviews/{stock_code}")
async def post_review(
    stock_code: str,
    payload: CreateReviewRequest,
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    require_business_database(settings)
    async with business_uow() as session:
        row = await invest_workspace.create_review(
            session,
            stock_code=stock_code.strip(),
            thesis_id=payload.thesis_id,
            decision=payload.decision,
            thesis_valid=payload.thesis_valid,
            evidence_update=payload.evidence_update,
            valuation_update=payload.valuation_update,
            discipline_notes=payload.discipline_notes,
            next_action=payload.next_action,
        )
        return {"review": invest_workspace.serialize_review(row)}
