"""Slash command handlers."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cli.ui import Colors, TerminalUI, colorize

if TYPE_CHECKING:
    from chat_service import ChatService
    from memory_store import MemoryStore
    from profile import ProfileManager
    from roles.role import Role


class CommandHandler:
    """Handler for slash commands."""

    def __init__(
        self,
        chat_service: "ChatService | None" = None,
        memory_store: "MemoryStore | None" = None,
        profile_manager: "ProfileManager | None" = None,
    ) -> None:
        self._chat_service = chat_service
        self._memory_store = memory_store
        self._profile_manager = profile_manager
        self._ui = TerminalUI()

    @property
    def memory_store(self) -> "MemoryStore":
        if self._chat_service:
            return self._chat_service.memory_store
        if self._memory_store:
            return self._memory_store
        raise RuntimeError("No memory store available")

    @property
    def profile_manager(self) -> "ProfileManager":
        if self._chat_service:
            return self._chat_service.profile_manager
        if self._profile_manager:
            return self._profile_manager
        raise RuntimeError("No profile manager available")

    @property
    def current_role(self) -> "Role | None":
        if self._chat_service:
            return self._chat_service.current_role
        return None

    def handle(self, command: str) -> bool:
        """Handle a slash command."""
        command = command.strip()
        if not command.startswith("/"):
            return False

        parts = command.split(None, 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        # Role commands
        if cmd == "/role":
            self._cmd_role(args)
        elif cmd == "/roles":
            self._cmd_roles()
        elif cmd == "/roleinfo":
            self._cmd_role_info()
        # Memory commands
        elif cmd == "/memory":
            self._cmd_show_memory()
        elif cmd == "/forget":
            self._cmd_forget(args)
        elif cmd == "/why":
            self._cmd_why()
        elif cmd == "/profile":
            self._cmd_profile()
        else:
            self._ui.safe_print(
                colorize(f"  ❌ 未知命令: {cmd}\n", Colors.BRIGHT_RED)
            )
            return False

        return True

    def _cmd_role(self, args: str) -> None:
        """Handle /role [name] command - switch or show current role."""
        if not self._chat_service:
            self._ui.print_error("角色切换不可用")
            return

        if not args.strip():
            # Show current role
            role = self._chat_service.current_role
            self._ui.print_role_info(role)
            return

        role_id = args.strip().lower()

        # List of valid role IDs
        valid_ids = list(self._chat_service.role_manager.available_roles.keys())

        if role_id not in valid_ids:
            self._ui.safe_print(
                colorize(f"  ❌ 未知角色: {role_id}\n", Colors.BRIGHT_RED)
            )
            self._ui.safe_print(
                colorize(f"  可用角色: {', '.join(valid_ids)}\n", Colors.DIM)
            )
            return

        if self._chat_service.switch_role(role_id):
            self._ui.print_role_switched(self._chat_service.current_role)
        else:
            self._ui.print_error(f"切换到角色 {role_id} 失败")

    def _cmd_roles(self) -> None:
        """Handle /roles command - list all available roles."""
        if not self._chat_service:
            self._ui.print_error("角色列表不可用")
            return

        roles = self._chat_service.role_manager.list_roles()
        current_id = self._chat_service.current_role.id
        self._ui.print_roles_list(roles, current_id)

    def _cmd_role_info(self) -> None:
        """Handle /roleinfo command - show detailed current role info."""
        role = self.current_role
        if role:
            self._ui.print_role_info(role)
        else:
            self._ui.print_error("角色信息不可用")

    def _cmd_show_memory(self) -> None:
        self._ui.print_memory_list(self.memory_store.memories, self.current_role)

    def _cmd_forget(self, args: str) -> None:
        try:
            n = int(args.strip())
        except ValueError:
            self._ui.safe_print(
                colorize(f"  ❌ '{args.strip()}' 不是有效的数字\n", Colors.BRIGHT_RED)
            )
            return

        total = len(self.memory_store.memories)
        if n < 0 or n >= total:
            self._ui.safe_print(
                colorize(
                    f"  ❌ 索引 {n} 超出范围（共 {total} 条记忆，编号 0–{total - 1}）\n",
                    Colors.BRIGHT_RED,
                )
            )
            return

        if total > 50:
            self._ui.safe_print(
                colorize(
                    f"  ⚠️  删除后需要重建索引（共 {total} 条记忆），可能需要几秒。"
                    "确认请按 Enter，取消请按 Ctrl+C：",
                    Colors.BRIGHT_YELLOW,
                ),
                end="",
            )
            try:
                input()
            except (KeyboardInterrupt, EOFError):
                self._ui.safe_print(colorize("\n  已取消\n", Colors.DIM))
                return

        try:
            self.memory_store.delete(n)
            self._ui.print_success(f"已删除第 {n} 条记忆")
            self._cmd_show_memory()
        except Exception as e:
            self._ui.safe_print(colorize(f"  ❌ 删除失败: {e}\n", Colors.BRIGHT_RED))

    def _cmd_why(self) -> None:
        if self._chat_service:
            memories = self._chat_service.get_last_memories()
        else:
            memories = []
        self._ui.print_memory_used(memories)

    def _cmd_profile(self) -> None:
        profile = self.profile_manager.get_profile()
        self._ui.print_profile(profile.content, self.current_role)