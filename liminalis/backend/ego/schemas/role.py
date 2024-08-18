"""Ego role request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel


class RoleResponse(BaseModel):
    id: str
    name: str
    icon: str
    description: str


class UpdateCurrentRoleRequest(BaseModel):
    role_id: str
