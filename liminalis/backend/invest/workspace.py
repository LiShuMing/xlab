"""Invest workspace repository and thesis drafting helpers."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend._shared.serializers import utc_now, utc_timestamp_z
from backend.invest.db_models import (
    InvestJournalEntry,
    InvestReview,
    InvestThesis,
    InvestWatchItem,
)

DEFAULT_WATCH_ITEMS = [
    {
        "kind": "financial",
        "title": "跟踪下一次财报的收入、利润和现金流变化",
        "condition": "如果收入增速、利润率或自由现金流显著恶化，需要重新评估核心假设。",
        "priority": 10,
    },
    {
        "kind": "valuation",
        "title": "跟踪估值是否进入安全边际区间",
        "condition": "当价格或估值接近目标区间时，重新检查风险收益比。",
        "priority": 8,
    },
    {
        "kind": "risk",
        "title": "跟踪反方证据和证伪信号",
        "condition": "出现核心风险或证伪条件时，触发复盘。",
        "priority": 9,
    },
]


def _compact_list(*values: str | None) -> list[str]:
    return [value.strip() for value in values if isinstance(value, str) and value.strip()]


def _section_content(report_data: dict[str, Any], *keywords: str) -> str:
    sections = report_data.get("sections", [])
    if not isinstance(sections, list):
        return ""
    for section in sections:
        if not isinstance(section, dict):
            continue
        title = str(section.get("title", ""))
        if any(keyword in title for keyword in keywords):
            return str(section.get("content", "")).strip()
    return ""


def draft_thesis_from_report(report_data: dict[str, Any]) -> dict[str, Any]:
    """Create an editable investment thesis draft from a stored report JSON."""
    stock_code = str(report_data.get("stock_code") or report_data.get("stock") or "").strip()
    stock_name = str(report_data.get("stock_name") or report_data.get("name") or "").strip()
    rating = str(report_data.get("rating") or report_data.get("recommendation") or "hold").lower()
    confidence = str(report_data.get("confidence") or report_data.get("conviction") or "medium").lower()
    summary = str(report_data.get("summary") or "").strip()

    company = _section_content(report_data, "公司", "Company", "业务", "Overview")
    financial = _section_content(report_data, "财务", "Financial", "估值", "Valuation")
    risk = _section_content(report_data, "风险", "Risk")
    macro = _section_content(report_data, "行业", "宏观", "Sector", "Macro")

    core_parts = _compact_list(summary, company)
    core_thesis = "\n\n".join(core_parts) if core_parts else "请补充该标的的长期投资假设。"

    supporting_evidence = _compact_list(
        financial,
        macro,
        str(report_data.get("bull_case") or ""),
        str(report_data.get("base_case") or ""),
    )
    counter_evidence = _compact_list(risk, str(report_data.get("bear_case") or ""))

    target_price = report_data.get("target_price")
    margin_of_safety = (
        f"参考目标价/估值锚：{target_price}。需结合个人安全边际重新确认。"
        if target_price
        else "数据待补充：需要结合估值区间、自由现金流和风险收益比设置安全边际。"
    )
    status = "researching" if rating in {"buy", "hold", "outperform"} else "watchlist"

    return {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "status": status,
        "core_thesis": core_thesis,
        "supporting_evidence": supporting_evidence[:6],
        "counter_evidence": counter_evidence[:6],
        "disconfirming_signals": [
            "核心财务指标连续恶化",
            "原报告中的主要风险开始兑现",
            "估值安全边际消失且基本面没有同步改善",
        ],
        "margin_of_safety": margin_of_safety,
        "expected_holding_period": "长期跟踪，至少按季度复盘",
        "confidence": confidence if confidence in {"high", "medium", "low"} else "medium",
    }


def serialize_thesis(row: InvestThesis) -> dict[str, Any]:
    return {
        "id": row.id,
        "stock_code": row.stock_code,
        "stock_name": row.stock_name or "",
        "status": row.status,
        "core_thesis": row.core_thesis,
        "supporting_evidence": row.supporting_evidence or [],
        "counter_evidence": row.counter_evidence or [],
        "disconfirming_signals": row.disconfirming_signals or [],
        "margin_of_safety": row.margin_of_safety,
        "expected_holding_period": row.expected_holding_period,
        "confidence": row.confidence,
        "source_report_id": row.source_report_id,
        "created_at": utc_timestamp_z(row.created_at),
        "updated_at": utc_timestamp_z(row.updated_at),
    }


def serialize_watch_item(row: InvestWatchItem) -> dict[str, Any]:
    return {
        "id": row.id,
        "stock_code": row.stock_code,
        "thesis_id": row.thesis_id,
        "kind": row.kind,
        "title": row.title,
        "condition": row.condition,
        "status": row.status,
        "priority": row.priority,
        "due_date": row.due_date.isoformat() if row.due_date else None,
        "created_at": utc_timestamp_z(row.created_at),
        "updated_at": utc_timestamp_z(row.updated_at),
    }


def serialize_journal_entry(row: InvestJournalEntry) -> dict[str, Any]:
    return {
        "id": row.id,
        "stock_code": row.stock_code,
        "thesis_id": row.thesis_id,
        "entry_type": row.entry_type,
        "action": row.action,
        "price": row.price,
        "reason": row.reason,
        "emotion": row.emotion,
        "meta": row.meta or {},
        "created_at": utc_timestamp_z(row.created_at),
        "review_at": row.review_at.isoformat() if row.review_at else None,
    }


def serialize_review(row: InvestReview) -> dict[str, Any]:
    return {
        "id": row.id,
        "stock_code": row.stock_code,
        "thesis_id": row.thesis_id,
        "decision": row.decision,
        "thesis_valid": row.thesis_valid,
        "evidence_update": row.evidence_update,
        "valuation_update": row.valuation_update,
        "discipline_notes": row.discipline_notes,
        "next_action": row.next_action,
        "created_at": utc_timestamp_z(row.created_at),
    }


async def upsert_thesis(
    session: AsyncSession,
    *,
    stock_code: str,
    stock_name: str | None = None,
    status: str = "watchlist",
    core_thesis: str = "",
    supporting_evidence: list[str] | None = None,
    counter_evidence: list[str] | None = None,
    disconfirming_signals: list[str] | None = None,
    margin_of_safety: str = "",
    expected_holding_period: str = "",
    confidence: str = "medium",
    source_report_id: int | None = None,
) -> InvestThesis:
    values = {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "status": status,
        "core_thesis": core_thesis,
        "supporting_evidence": supporting_evidence or [],
        "counter_evidence": counter_evidence or [],
        "disconfirming_signals": disconfirming_signals or [],
        "margin_of_safety": margin_of_safety,
        "expected_holding_period": expected_holding_period,
        "confidence": confidence,
        "source_report_id": source_report_id,
    }
    stmt = insert(InvestThesis).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["stock_code"],
        set_={
            **values,
            "updated_at": utc_now(),
        },
    ).returning(InvestThesis)
    result = await session.execute(stmt)
    return result.scalar_one()


async def upsert_thesis_from_report(
    session: AsyncSession,
    *,
    report_id: int,
    report_data: dict[str, Any],
) -> InvestThesis:
    draft = draft_thesis_from_report(report_data)
    thesis = await upsert_thesis(session, source_report_id=report_id, **draft)
    await ensure_default_watch_items(session, thesis)
    return thesis


async def get_thesis(session: AsyncSession, stock_code: str) -> InvestThesis | None:
    result = await session.execute(select(InvestThesis).where(InvestThesis.stock_code == stock_code))
    return result.scalar_one_or_none()


async def list_theses(session: AsyncSession, limit: int = 50) -> list[InvestThesis]:
    result = await session.execute(
        select(InvestThesis).order_by(InvestThesis.updated_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def ensure_default_watch_items(session: AsyncSession, thesis: InvestThesis) -> None:
    result = await session.execute(
        select(InvestWatchItem).where(InvestWatchItem.stock_code == thesis.stock_code).limit(1)
    )
    if result.scalar_one_or_none() is not None:
        return
    for item in DEFAULT_WATCH_ITEMS:
        session.add(
            InvestWatchItem(
                stock_code=thesis.stock_code,
                thesis_id=thesis.id,
                kind=item["kind"],
                title=item["title"],
                condition=item["condition"],
                priority=item["priority"],
            )
        )


async def list_watch_items(session: AsyncSession, stock_code: str) -> list[InvestWatchItem]:
    result = await session.execute(
        select(InvestWatchItem)
        .where(InvestWatchItem.stock_code == stock_code)
        .order_by(InvestWatchItem.status, InvestWatchItem.priority.desc(), InvestWatchItem.created_at.desc())
    )
    return list(result.scalars().all())


async def create_watch_item(
    session: AsyncSession,
    *,
    stock_code: str,
    thesis_id: int | None,
    kind: str,
    title: str,
    condition: str = "",
    priority: int = 0,
    due_date: date | None = None,
) -> InvestWatchItem:
    row = InvestWatchItem(
        stock_code=stock_code,
        thesis_id=thesis_id,
        kind=kind,
        title=title,
        condition=condition,
        priority=priority,
        due_date=due_date,
    )
    session.add(row)
    await session.flush()
    return row


async def update_watch_item_status(session: AsyncSession, item_id: int, status: str) -> bool:
    result = await session.execute(
        update(InvestWatchItem).where(InvestWatchItem.id == item_id).values(status=status, updated_at=utc_now())
    )
    return result.rowcount > 0


async def delete_watch_item(session: AsyncSession, item_id: int) -> bool:
    result = await session.execute(delete(InvestWatchItem).where(InvestWatchItem.id == item_id))
    return result.rowcount > 0


async def list_journal_entries(session: AsyncSession, stock_code: str, limit: int = 50) -> list[InvestJournalEntry]:
    result = await session.execute(
        select(InvestJournalEntry)
        .where(InvestJournalEntry.stock_code == stock_code)
        .order_by(InvestJournalEntry.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def create_journal_entry(
    session: AsyncSession,
    *,
    stock_code: str,
    thesis_id: int | None,
    entry_type: str,
    action: str = "",
    price: float | None = None,
    reason: str = "",
    emotion: str = "",
    meta: dict[str, Any] | None = None,
    review_at: date | None = None,
) -> InvestJournalEntry:
    row = InvestJournalEntry(
        stock_code=stock_code,
        thesis_id=thesis_id,
        entry_type=entry_type,
        action=action,
        price=price,
        reason=reason,
        emotion=emotion,
        meta=meta or {},
        review_at=review_at,
    )
    session.add(row)
    await session.flush()
    return row


async def list_reviews(session: AsyncSession, stock_code: str, limit: int = 20) -> list[InvestReview]:
    result = await session.execute(
        select(InvestReview)
        .where(InvestReview.stock_code == stock_code)
        .order_by(InvestReview.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def create_review(
    session: AsyncSession,
    *,
    stock_code: str,
    thesis_id: int | None,
    decision: str,
    thesis_valid: bool | None = None,
    evidence_update: str = "",
    valuation_update: str = "",
    discipline_notes: str = "",
    next_action: str = "",
) -> InvestReview:
    row = InvestReview(
        stock_code=stock_code,
        thesis_id=thesis_id,
        decision=decision,
        thesis_valid=thesis_valid,
        evidence_update=evidence_update,
        valuation_update=valuation_update,
        discipline_notes=discipline_notes,
        next_action=next_action,
    )
    session.add(row)
    await session.flush()
    return row
