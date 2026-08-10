"""Shared service-layer conventions.

Domain services should be thin application functions that receive an explicit
database session and runtime settings from routers, CLIs, workers, or schedulers.
They may flush through repositories, but transaction ownership stays in
``backend._shared.storage.business_uow``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import ParamSpec, Protocol, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from backend.settings import Settings

P = ParamSpec("P")
T = TypeVar("T")


class DomainService(Protocol[P, T]):
    """Callable shape for async service functions."""

    def __call__(
        self,
        session: AsyncSession,
        settings: Settings,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Awaitable[T]: ...


def service_name(fn: Callable[..., object]) -> str:
    """Stable human-readable name for logging and architecture tests."""
    return f"{fn.__module__}.{fn.__name__}"
