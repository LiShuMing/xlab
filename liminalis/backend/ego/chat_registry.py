"""Per-user ChatService lifecycle manager.

Each authenticated user gets a dedicated ChatService that lives for the
lifetime of the server process (FAISS index, profile, role manager per user).
"""

from __future__ import annotations

import asyncio

from backend.ego.chat_service import ChatService
from backend.ego.roles.role_manager import RoleManager

_chat_services: dict[str, ChatService] = {}
_lock = asyncio.Lock()


async def get_chat_service(user_id: str) -> ChatService:
    if user_id in _chat_services:
        return _chat_services[user_id]

    async with _lock:
        if user_id in _chat_services:
            return _chat_services[user_id]
        svc = ChatService(role_manager=RoleManager())
        _chat_services[user_id] = svc
        return svc


async def switch_chat_role(user_id: str, role_id: str) -> bool:
    svc = _chat_services.get(user_id)
    if svc is None:
        return False
    return svc.switch_role(role_id)
