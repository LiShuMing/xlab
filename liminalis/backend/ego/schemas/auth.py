"""Ego auth request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PinLoginRequest(BaseModel):
    pin: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class AuthResponse(BaseModel):
    token: str
    user: dict
