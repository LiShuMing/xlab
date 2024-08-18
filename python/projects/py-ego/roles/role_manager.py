"""Role manager for loading, switching, and managing agent personas."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from memory_store import MemoryStore
from profile import ProfileManager
from roles.role import PREDEFINED_ROLES, Role

__all__ = ["RoleManager"]

DEFAULT_ROLES_DIR = Path(__file__).parent


class RelationshipManager:
    """Manages relationship memory between role and user.

    Relationship memory stores:
    - Key moments in the user-role interaction
    - Shared experiences and references
    - Important things the role should remember about this user
    """

    def __init__(self, relationship_file: Path) -> None:
        self._file = relationship_file
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._logger = logging.getLogger(__name__)

    def get_relationship(self) -> str:
        """Get the relationship memory content."""
        if not self._file.exists():
            return ""
        return self._file.read_text(encoding="utf-8").strip()

    def update_relationship(self, new_entry: str) -> None:
        """Add a new entry to relationship memory."""
        existing = self.get_relationship()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        entry = f"\n## {timestamp}\n{new_entry}\n"

        if not existing:
            content = f"# 关系记忆\n{entry}"
        else:
            content = existing + entry

        self._file.write_text(content, encoding="utf-8")

    def clear(self) -> None:
        """Clear relationship memory."""
        if self._file.exists():
            self._file.unlink()


class RoleManager:
    """Manages role loading, switching, and associated state.

    Each role has:
    - Independent memory store
    - Layered profile (global + role-specific)
    - Relationship memory (shared history with user)
    """

    def __init__(
        self,
        roles_dir: Path | None = None,
        data_dir: Path | None = None,
    ) -> None:
        self._roles_dir = roles_dir or DEFAULT_ROLES_DIR
        self._data_dir = data_dir or Path(__file__).parent.parent / "data"
        self._logger = logging.getLogger(__name__)

        # Load available roles
        self._roles = self._load_roles()

        # Default to therapist
        self._current_role: Role = self._roles.get("therapist", PREDEFINED_ROLES["therapist"])

        # Initialize state for current role
        self._memory_store = self._create_memory_store()
        self._profile_manager = self._create_profile_manager()
        self._relationship_manager = self._create_relationship_manager()

    def _load_roles(self) -> dict[str, Role]:
        """Load roles from YAML files or use predefined."""
        yaml_file = self._roles_dir / "roles.yaml"
        if yaml_file.exists():
            try:
                roles = Role.load_all(self._roles_dir)
                if roles:
                    return roles
            except Exception as e:
                self._logger.warning(f"Failed to load roles from YAML: {e}")
        return dict(PREDEFINED_ROLES)

    def _create_memory_store(self) -> MemoryStore:
        """Create a memory store for the current role."""
        role_data_dir = self._data_dir / self._current_role.id
        return MemoryStore(data_dir=role_data_dir)

    def _create_profile_manager(self) -> ProfileManager:
        """Create a profile manager with layered profiles."""
        global_profile = self._data_dir / "profile.md"
        role_profile = self._data_dir / self._current_role.profile_filename
        return ProfileManager(
            global_profile_file=global_profile,
            role_profile_file=role_profile,
        )

    def _create_relationship_manager(self) -> RelationshipManager:
        """Create a relationship manager for the current role."""
        relationship_file = self._data_dir / self._current_role.relationship_filename
        return RelationshipManager(relationship_file)

    @property
    def current_role(self) -> Role:
        return self._current_role

    @property
    def memory_store(self) -> MemoryStore:
        return self._memory_store

    @property
    def profile_manager(self) -> ProfileManager:
        return self._profile_manager

    @property
    def relationship_manager(self) -> RelationshipManager:
        return self._relationship_manager

    @property
    def available_roles(self) -> dict[str, Role]:
        return self._roles

    def switch_role(self, role_id: str) -> bool:
        """Switch to a different role."""
        if role_id not in self._roles:
            self._logger.warning(f"Role not found: {role_id}")
            return False

        if role_id == self._current_role.id:
            return True

        self._current_role = self._roles[role_id]

        # Recreate state for new role
        self._memory_store = self._create_memory_store()
        self._profile_manager = self._create_profile_manager()
        self._relationship_manager = self._create_relationship_manager()

        self._logger.info(f"Switched to role: {self._current_role.name}")
        return True

    def get_role(self, role_id: str) -> Role | None:
        return self._roles.get(role_id)

    def list_roles(self) -> list[Role]:
        return list(self._roles.values())

    def get_system_prompt(self) -> str:
        """Get the complete system prompt with all dimensions."""
        relationship = self._relationship_manager.get_relationship()
        return self._current_role.build_full_system_prompt(relationship)

    def get_examples_context(self) -> str:
        """Get few-shot examples for the current role."""
        return self._current_role.build_examples_context()

    def get_profile_update_prompt(self, user_input: str, bot_reply: str) -> str:
        """Build the profile update prompt for the current role."""
        base_prompt = (
            "你是一个用户画像更新助手。请根据本轮对话，更新下方的用户画像。\n"
            "规则：\n"
            "1. 只记录用户明确说出的事实，不要推断或臆测\n"
            "2. 控制在300字以内\n"
            "3. 保留已有的准确信息，删除过时的信息\n"
            "4. 用第三人称描述（\"用户...\"）\n"
            "5. 如果已有信息较多，优先保留最近和最常出现的信息，适当压缩早期细节\n"
        )

        if self._current_role.profile_prompt:
            base_prompt += f"6. {self._current_role.profile_prompt}\n"

        current_profile = self._profile_manager.get_combined_profile()

        return (
            base_prompt + "\n"
            f"当前画像：\n{current_profile}\n\n"
            f"本轮对话：\n用户：{user_input}\n机器人：{bot_reply}\n\n"
            "请输出更新后的用户画像（只输出画像内容，不要其他说明）："
        )

    def update_relationship_async(self, user_input: str, bot_reply: str, key_insight: str) -> None:
        """Update relationship memory asynchronously.

        Args:
            user_input: The user's message.
            bot_reply: The assistant's response.
            key_insight: Key insight from this conversation.
        """
        import threading

        def update():
            if key_insight:
                self._relationship_manager.update_relationship(key_insight)

        thread = threading.Thread(target=update, daemon=True)
        thread.start()