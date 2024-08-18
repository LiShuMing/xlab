"""Record API routes for daily record management.

This module provides endpoints for:
- Creating daily records (text, voice, photo)
- Listing records with pagination
- Retrieving single records
- Deleting records
- Timeline data for calendar views
"""

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models import User
from app.schemas import (
    ErrorResponse,
    PaginatedResponse,
    RecordCreate,
    RecordResponse,
    SuccessResponse,
)
from app.services.record_service import RecordService

router = APIRouter(prefix="/records", tags=["records"])


@router.post(
    "",
    response_model=RecordResponse,
    status_code=status.HTTP_201_CREATED,
    responses={422: {"model": ErrorResponse}},
    summary="Create a new record",
    description="Create a new daily record (text, voice, or photo) for the authenticated user",
)
async def create_record(
    data: RecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecordResponse:
    """Create a new daily record.

    Creates a new record of the specified content type. The record is
    automatically associated with the current date.

    Args:
        data: Record creation data with content_type, content, and optional media_url.
        db: Async database session.
        current_user: The authenticated user.

    Returns:
        RecordResponse: The created record with generated ID and timestamps.
    """
    service = RecordService(db, current_user)
    record = await service.create_record(data)
    return record


@router.get(
    "",
    response_model=PaginatedResponse[RecordResponse],
    summary="List records",
    description="Retrieve paginated list of records for the authenticated user",
)
async def list_records(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    record_date: Optional[date] = Query(None, description="Filter by date"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[RecordResponse]:
    """List records with pagination.

    Retrieves records for the authenticated user with optional date filtering.
    Results are ordered by creation date (newest first).

    Args:
        page: Page number (1-indexed).
        size: Number of records per page (max 100).
        record_date: Optional filter to get records for a specific date.
        db: Async database session.
        current_user: The authenticated user.

    Returns:
        PaginatedResponse[RecordResponse]: Paginated list of records with total count.
    """
    service = RecordService(db, current_user)
    records, total = await service.get_records(page, size, record_date)
    return PaginatedResponse(items=records, total=total, page=page, size=size)


@router.get(
    "/timeline",
    summary="Get timeline",
    description="Get timeline data for a specific month showing record counts per day",
)
async def get_timeline(
    month: str = Query(
        ...,
        pattern=r"^\d{4}-\d{2}$",
        description="Month in YYYY-MM format",
        examples=["2026-03"],
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get timeline for a month.

    Returns a summary of records for each day in the specified month,
    useful for calendar/timeline views.

    Args:
        month: Month in YYYY-MM format (e.g., "2026-03").
        db: Async database session.
        current_user: The authenticated user.

    Returns:
        dict: Contains "days" key with list of daily summaries.
              Each summary has date, count, and preview fields.
    """
    year, month_num = map(int, month.split("-"))
    service = RecordService(db, current_user)
    timeline = await service.get_timeline(year, month_num)
    return {"days": timeline}


@router.get(
    "/{record_id}",
    response_model=RecordResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get a record",
    description="Retrieve a single record by ID",
)
async def get_record(
    record_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecordResponse:
    """Get a single record by ID.

    Retrieves a specific record, verifying it belongs to the current user.

    Args:
        record_id: UUID of the record to retrieve.
        db: Async database session.
        current_user: The authenticated user.

    Returns:
        RecordResponse: The requested record.

    Raises:
        NotFoundException: If record doesn't exist or doesn't belong to user.
    """
    service = RecordService(db, current_user)
    return await service.get_record(record_id)


@router.delete(
    "/{record_id}",
    response_model=SuccessResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Delete a record",
    description="Delete a record by ID",
)
async def delete_record(
    record_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SuccessResponse:
    """Delete a record.

    Removes a record from the database after verifying ownership.

    Args:
        record_id: UUID of the record to delete.
        db: Async database session.
        current_user: The authenticated user.

    Returns:
        SuccessResponse: Confirmation of deletion.

    Raises:
        NotFoundException: If record doesn't exist or doesn't belong to user.
    """
    service = RecordService(db, current_user)
    await service.delete_record(record_id)
    return SuccessResponse()