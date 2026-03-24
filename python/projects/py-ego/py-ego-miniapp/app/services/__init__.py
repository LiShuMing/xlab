"""Service layer for business logic.

This package contains service classes that encapsulate business logic
and coordinate between models, schemas, and external services.
"""

from app.services.auth_service import AuthService

__all__ = ["AuthService"]