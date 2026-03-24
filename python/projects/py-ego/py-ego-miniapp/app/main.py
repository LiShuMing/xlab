"""FastAPI application entry point for py-ego-miniapp.

This module creates and configures the FastAPI application with:
- CORS middleware
- API routes
- Exception handlers
- Health check endpoints
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.config import get_settings
from app.utils import AppException

settings = get_settings()

app = FastAPI(
    title="py-ego-miniapp",
    description="Backend API for WeChat Mini Program - Daily recording and AI psychological companion",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle custom application exceptions.

    Converts AppException instances to JSON responses with structured
    error information.

    Args:
        request: The incoming request (unused but required by FastAPI).
        exc: The application exception to handle.

    Returns:
        JSONResponse: Structured error response with code and message.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message},
    )


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Health check endpoint for monitoring and load balancers.

    Returns:
        dict: Health status and environment info.
    """
    return {"status": "ok", "env": settings.app_env}


@app.get("/", tags=["root"])
async def root() -> dict:
    """Root endpoint with API information.

    Returns:
        dict: Basic API metadata including name, version, and docs URL.
    """
    return {
        "name": "py-ego-miniapp",
        "version": "0.1.0",
        "docs": "/docs",
    }