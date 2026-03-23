"""Chat service layer combining memory, profile, role, and LLM."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from config import get_settings
from llm_client import LLMClient
from memory_store import MemoryStore
from profile import ProfileManager
from roles.role_manager import RoleManager

__all__ = ["ChatService", "ChatContext"]

DEFAULT_CHAT_LOGS_DIR = Path(__file__).parent / "chat_logs"


class ChatContext:
    """Context for a single chat interaction."""

    def __init__(
        self,
        user_input: str,
        memories: list[tuple[dict[str, Any], float]] | None = None,
        profile: str | None = None,
        examples: str | None = None,
    ) -> None:
        self.user_input = user_input
        self.memories = memories or []
        self.profile = profile
        self.examples = examples

    def to_messages(self, system_prompt: str) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]

        # Add few-shot examples if available
        if self.examples:
            messages.append({
                "role": "system",
                "content": self.examples,
            })

        # Add profile
        if self.profile:
            messages.append({
                "role": "system",
                "content": f"用户画像：\n{self.profile}"
            })

        # Add memories
        if self.memories:
            memory_context = "\n".join(
                f"过去你曾说过：{m['text']}"
                for m, _ in self.memories
            )
            messages.append({
                "role": "system",
                "content": f"相关历史记忆:\n{memory_context}"
            })

        messages.append({"role": "user", "content": self.user_input})

        return messages


class ChatService:
    """Main chat service orchestrating memory, profile, role, and LLM."""

    def __init__(
        self,
        role_manager: RoleManager | None = None,
        chat_logs_dir: Path | str | None = None,
    ) -> None:
        self._settings = get_settings()
        self._logger = logging.getLogger(__name__)
        self._llm_client = LLMClient()

        self._role_manager = role_manager or RoleManager()

        self._chat_logs_dir = Path(chat_logs_dir) if chat_logs_dir else DEFAULT_CHAT_LOGS_DIR
        self._chat_logs_dir.mkdir(parents=True, exist_ok=True)

        self._last_memories: list[tuple[dict[str, Any], float]] = []

    @property
    def role_manager(self) -> RoleManager:
        return self._role_manager

    @property
    def memory_store(self) -> MemoryStore:
        return self._role_manager.memory_store

    @property
    def profile_manager(self) -> ProfileManager:
        return self._role_manager.profile_manager

    @property
    def current_role(self):
        return self._role_manager.current_role

    def switch_role(self, role_id: str) -> bool:
        success = self._role_manager.switch_role(role_id)
        if success:
            self._last_memories = []
        return success

    def chat(self, user_input: str) -> str:
        """Process a user message and generate a response."""
        # Store in memory
        self.memory_store.add(user_input)

        # Retrieve relevant memories
        self._last_memories = self.memory_store.query(user_input, k=3)

        # Get profile
        profile = self.profile_manager.get_profile()
        profile_content = profile.content if not profile.is_empty() else None

        # Get examples
        examples = self._role_manager.get_examples_context()

        # Build context
        context = ChatContext(
            user_input=user_input,
            memories=self._last_memories,
            profile=profile_content,
            examples=examples,
        )

        # Get full system prompt with personality, knowledge, relationship
        system_prompt = self._role_manager.get_system_prompt()

        # Generate response
        messages = context.to_messages(system_prompt)
        reply = self._llm_client.chat_completion(messages)

        # Log chat
        self._log_chat(user_input, reply)

        # Update profile asynchronously
        profile_prompt = self._role_manager.get_profile_update_prompt(user_input, reply)
        self.profile_manager.update_async(user_input, reply, profile_prompt)

        return reply

    def get_last_memories(self) -> list[tuple[dict[str, Any], float]]:
        return self._last_memories

    def _log_chat(self, user_msg: str, bot_reply: str) -> None:
        log_file = self._get_log_file()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        role_info = f"**角色：** {self.current_role.name} ({self.current_role.id})\n"

        entry = f"""## {timestamp}

**用户：** {user_msg}

**{self.current_role.name}：** {bot_reply}

---

"""

        if not log_file.exists():
            header = f"""# 聊天记录

**日期：** {datetime.now().strftime("%Y-%m-%d")}
**模型：** {self._settings.llm_model}
{role_info}
---

"""
            log_file.write_text(header + entry, encoding="utf-8")
        else:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(entry)

        self._logger.debug(f"Chat logged to: {log_file}")

    def _get_log_file(self) -> Path:
        today = datetime.now().strftime("%Y-%m-%d")
        return self._chat_logs_dir / f"chat_{today}.md"

    def clear_memory(self) -> None:
        self.memory_store.delete_all()
        self._last_memories = []

    def clear_relationship(self) -> None:
        """Clear relationship memory for current role."""
        self._role_manager.relationship_manager.clear()