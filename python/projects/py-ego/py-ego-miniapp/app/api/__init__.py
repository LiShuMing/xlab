"""API routes package for the application.

This module aggregates all API routers and exposes them through
a single api_router that can be included in the FastAPI app.
"""

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.records import router as records_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
api_router.include_router(records_router)

__all__ = ["api_router"]