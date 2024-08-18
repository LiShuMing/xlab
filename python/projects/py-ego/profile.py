"""User profile management with layered profile support."""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from config import get_settings
from llm_client import LLMClient
from models import UserProfile

__all__ = ["ProfileManager"]

DEFAULT_PROFILE_FILE = Path(__file__).parent / "data" / "profile.md"


class ProfileManager:
    """Manages user profile updates and persistence with layered profile support.

    Layered profiles:
    - Global profile: Shared across all roles
    - Role profile: Specific to a role, takes precedence

    When reading, role profile overrides global profile for overlapping fields.
    When updating, both profiles are considered.

    Thread Safety:
        - Uses a lock to protect file read/write operations
        - Uses a flag to prevent concurrent updates
    """

    def __init__(
        self,
        global_profile_file: Path | str | None = None,
        role_profile_file: Path | str | None = None,
    ) -> None:
        """Initialize the profile manager.

        Args:
            global_profile_file: Path to global profile file.
            role_profile_file: Path to role-specific profile file.
        """
        self._global_profile_file = Path(global_profile_file) if global_profile_file else DEFAULT_PROFILE_FILE
        self._role_profile_file = Path(role_profile_file) if role_profile_file else None

        self._global_profile_file.parent.mkdir(parents=True, exist_ok=True)
        if self._role_profile_file:
            self._role_profile_file.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._updating = False
        self._logger = logging.getLogger(__name__)
        self._llm_client = LLMClient()
        self._settings = get_settings()

    def get_global_profile(self) -> UserProfile:
        """Get the global user profile."""
        with self._lock:
            if not self._global_profile_file.exists():
                return UserProfile()

            content = self._global_profile_file.read_text(encoding="utf-8").strip()
            return UserProfile(content=content)

    def get_role_profile(self) -> UserProfile:
        """Get the role-specific user profile."""
        if not self._role_profile_file:
            return UserProfile()

        with self._lock:
            if not self._role_profile_file.exists():
                return UserProfile()

            content = self._role_profile_file.read_text(encoding="utf-8").strip()
            return UserProfile(content=content)

    def get_combined_profile(self) -> str:
        """Get combined profile (role profile appended to global profile).

        Returns:
            Combined profile content.
        """
        global_profile = self.get_global_profile()
        role_profile = self.get_role_profile()

        parts = []

        if not global_profile.is_empty():
            parts.append("【全局画像】\n" + global_profile.content)

        if not role_profile.is_empty():
            parts.append("【角色画像】\n" + role_profile.content)

        return "\n\n".join(parts) if parts else ""

    def get_profile(self) -> UserProfile:
        """Get the effective user profile.

        For backward compatibility, returns role profile if available,
        otherwise global profile.

        Returns:
            UserProfile object with combined content.
        """
        combined = self.get_combined_profile()
        return UserProfile(content=combined)

    def update(self, user_input: str, bot_reply: str, prompt: str | None = None) -> None:
        """Update the user profile synchronously.

        Args:
            user_input: The user's message.
            bot_reply: The assistant's response.
            prompt: Custom prompt for profile update. If None, role-specific prompt is used.
        """
        self._updating = True
        try:
            current_profile = self.get_combined_profile()

            if prompt is None:
                prompt = self._build_default_prompt(current_profile, user_input, bot_reply)

            try:
                new_profile = self._llm_client.chat_completion(
                    [{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=500,
                )

                # Write to role-specific profile if available
                target_file = self._role_profile_file or self._global_profile_file
                with self._lock:
                    target_file.write_text(new_profile, encoding="utf-8")

            except Exception as e:
                self._logger.error(f"Failed to update profile: {e}")

        finally:
            self._updating = False

    def update_async(self, user_input: str, bot_reply: str, prompt: str | None = None) -> None:
        """Update the user profile asynchronously."""
        if self._updating:
            self._logger.debug("Profile update already in progress, skipping")
            return

        thread = threading.Thread(
            target=self.update,
            args=(user_input, bot_reply, prompt),
            daemon=True,
        )
        thread.start()

    def _build_default_prompt(
        self, current_profile: str, user_input: str, bot_reply: str
    ) -> str:
        return (
            "你是一个用户画像更新助手。请根据本轮对话，更新下方的用户画像。\n"
            "规则：\n"
            "1. 只记录用户明确说出的事实，不要推断或臆测\n"
            "2. 控制在300字以内\n"
            "3. 保留已有的准确信息，删除过时的信息\n"
            "4. 用第三人称描述（\"用户...\"）\n"
            "5. 如果已有信息较多，优先保留最近和最常出现的信息，适当压缩早期细节\n\n"
            f"当前画像：\n{current_profile}\n\n"
            f"本轮对话：\n用户：{user_input}\n机器人：{bot_reply}\n\n"
            "请输出更新后的用户画像（只输出画像内容，不要其他说明）："
        )

    def is_empty(self) -> bool:
        """Check if both profiles are empty."""
        return self.get_global_profile().is_empty() and self.get_role_profile().is_empty()

    def clear(self) -> None:
        """Clear both profile files."""
        with self._lock:
            if self._global_profile_file.exists():
                self._global_profile_file.unlink()
            if self._role_profile_file and self._role_profile_file.exists():
                self._role_profile_file.unlink()