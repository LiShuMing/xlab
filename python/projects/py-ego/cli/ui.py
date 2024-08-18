"""Terminal UI utilities."""
from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from roles.role import Role


class Colors:
    """ANSI color codes for terminal output."""

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright foreground colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Styles
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    # Reset
    RESET = "\033[0m"

    @classmethod
    def disable(cls) -> None:
        """Disable all colors."""
        for attr in dir(cls):
            if not attr.startswith("_") and attr.isupper():
                setattr(cls, attr, "")

    @classmethod
    def get_color(cls, name: str) -> str:
        """Get color code by name."""
        return getattr(cls, name.upper(), cls.CYAN)


def colorize(text: Any, *styles: str) -> str:
    """Apply ANSI styles to text."""
    style_codes = "".join(styles)
    return f"{style_codes}{text}{Colors.RESET}"


# Detect terminal color support
_use_colors = True
if os.getenv("NO_COLOR") or os.getenv("TERM") == "dumb":
    _use_colors = False
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        _use_colors = False

if not _use_colors:
    Colors.disable()


class TerminalUI:
    """Terminal user interface for the chat application."""

    def __init__(self) -> None:
        self._colors_enabled = _use_colors

    def safe_print(self, text: Any, end: str = "\n") -> None:
        """Print text safely, handling encoding errors."""
        try:
            print(text, end=end)
        except UnicodeEncodeError:
            try:
                encoded = text.encode(sys.stdout.encoding, errors="ignore")
                decoded = encoded.decode(sys.stdout.encoding)
                print(decoded, end=end)
            except Exception:
                print("[打印错误]")

    def print_welcome(
        self,
        role: "Role",
        model: str,
        use_simple_embedding: bool = False,
    ) -> None:
        """Print the welcome screen with role info."""
        # Get colors from role style
        primary = Colors.get_color(role.style.primary_color)
        secondary = Colors.get_color(role.style.secondary_color)

        border = colorize("═" * 60, primary, Colors.BOLD)
        self.safe_print(f"\n{border}")

        title = colorize(f"  {role.icon} 欢迎使用{role.name}", secondary, Colors.BOLD)
        subtitle = colorize("（含记忆系统）", primary)
        self.safe_print(f"{title} {subtitle}")

        model_info = (
            colorize("  🤖 当前使用模型: ", Colors.BRIGHT_GREEN)
            + colorize(model, Colors.GREEN, Colors.BOLD)
        )
        self.safe_print(model_info)

        # Role info
        role_info = (
            colorize("  📌 当前角色: ", Colors.BRIGHT_GREEN)
            + colorize(role.name, Colors.GREEN, Colors.BOLD)
            + colorize(f" - {role.description}", Colors.DIM)
        )
        self.safe_print(role_info)

        if use_simple_embedding:
            embed_mode = "哈希嵌入 (测试模式)"
            embed_color = Colors.BRIGHT_YELLOW
        else:
            embed_mode = "语义嵌入 (BAAI/bge-small-zh-v1.5)"
            embed_color = Colors.BRIGHT_GREEN

        self.safe_print(
            colorize("  📦 记忆嵌入：", Colors.BRIGHT_GREEN)
            + colorize(embed_mode, embed_color)
        )
        if use_simple_embedding:
            self.safe_print(
                colorize(
                    "     💡 提示：设置 USE_REAL_EMBEDDING=true 启用真实语义嵌入",
                    Colors.DIM,
                )
            )

        self.safe_print("")

        tip_color = Colors.BRIGHT_YELLOW
        cmd_color = Colors.BRIGHT_WHITE
        desc_color = Colors.YELLOW

        self.safe_print(colorize("  💡 使用提示:", tip_color, Colors.BOLD))
        self.safe_print(
            f"     {colorize('•', Colors.BRIGHT_MAGENTA)} "
            f"输入 {colorize('exit', cmd_color, Colors.BOLD)} 或 {colorize('quit', cmd_color, Colors.BOLD)}  "
            f"{colorize('→ 退出对话', desc_color)}"
        )
        self.safe_print(
            f"     {colorize('•', Colors.BRIGHT_MAGENTA)} "
            f"输入 {colorize('clear', cmd_color, Colors.BOLD)}              "
            f"{colorize('→ 清空当前角色记忆', desc_color)}"
        )
        self.safe_print(
            f"     {colorize('•', Colors.BRIGHT_MAGENTA)} "
            f"输入 {colorize('/role [name]', cmd_color, Colors.BOLD)}      "
            f"{colorize('→ 切换角色', desc_color)}"
        )
        self.safe_print(
            f"     {colorize('•', Colors.BRIGHT_MAGENTA)} "
            f"输入 {colorize('/roles', cmd_color, Colors.BOLD)}            "
            f"{colorize('→ 查看所有角色', desc_color)}"
        )
        self.safe_print(
            f"     {colorize('•', Colors.BRIGHT_MAGENTA)} "
            f"输入 {colorize('/memory', cmd_color, Colors.BOLD)}            "
            f"{colorize('→ 查看记忆库', desc_color)}"
        )
        self.safe_print(
            f"     {colorize('•', Colors.BRIGHT_MAGENTA)} "
            f"输入 {colorize('/profile', cmd_color, Colors.BOLD)}           "
            f"{colorize('→ 查看你的画像', desc_color)}"
        )

        self.safe_print("")
        self.safe_print(f"{border}\n")

    def print_role_switched(self, role: "Role") -> None:
        """Print role switch confirmation."""
        primary = Colors.get_color(role.style.primary_color)
        self.safe_print(
            colorize(f"\n  ✅ 已切换到角色: ", Colors.BRIGHT_GREEN)
            + colorize(f"{role.icon} {role.name}", primary, Colors.BOLD)
        )
        self.safe_print(colorize(f"     {role.description}\n", Colors.DIM))

    def print_roles_list(self, roles: list["Role"], current_id: str) -> None:
        """Print list of available roles."""
        self.safe_print(colorize("\n  📋 可用角色列表：", Colors.BRIGHT_CYAN, Colors.BOLD))

        for role in roles:
            is_current = role.id == current_id
            if is_current:
                marker = colorize("  → ", Colors.BRIGHT_GREEN)
                name = colorize(f"{role.icon} {role.name}", Colors.BRIGHT_GREEN, Colors.BOLD)
            else:
                marker = "     "
                primary = Colors.get_color(role.style.primary_color)
                name = colorize(f"{role.icon} {role.name}", primary)

            desc = colorize(f" - {role.description}", Colors.DIM)
            self.safe_print(f"{marker}{name}{desc}")

        self.safe_print("")
        self.safe_print(colorize("  使用 /role [name] 切换角色\n", Colors.DIM))

    def print_role_info(self, role: "Role") -> None:
        """Print detailed role information."""
        primary = Colors.get_color(role.style.primary_color)

        self.safe_print(colorize(f"\n  📌 当前角色详情：", Colors.BRIGHT_CYAN, Colors.BOLD))
        self.safe_print(f"     {colorize('ID', Colors.DIM)}: {role.id}")
        self.safe_print(f"     {colorize('名称', Colors.DIM)}: {colorize(f'{role.icon} {role.name}', primary, Colors.BOLD)}")
        self.safe_print(f"     {colorize('描述', Colors.DIM)}: {role.description}")
        self.safe_print("")

    def print_memory_list(self, memories: list[dict[str, Any]], role: "Role | None" = None) -> None:
        """Print the list of stored memories."""
        total = len(memories)
        role_name = role.name if role else ""
        self.safe_print(
            colorize(f"\n  📚 {role_name}记忆库 ({total} 条):", Colors.BRIGHT_CYAN, Colors.BOLD)
        )

        if total == 0:
            self.safe_print(colorize("  （空）\n", Colors.DIM))
            return

        for i, m in enumerate(memories):
            ts = m.get("timestamp", "")[:16].replace("T", " ")
            raw_text = m.get("text", "")
            text = raw_text[:60] + ("..." if len(raw_text) > 60 else "")
            self.safe_print(f"  [{i}] {colorize(ts, Colors.DIM)}  {text}")

        self.safe_print("")

    def print_memory_used(
        self, memories: list[tuple[dict[str, Any], float]]
    ) -> None:
        """Print the memories used in the last response."""
        if not memories:
            self.safe_print(
                colorize("\n  💭 暂无检索记录（发一条消息后再试）\n", Colors.DIM)
            )
            return

        self.safe_print(
            colorize("\n  🔍 上次回复用到的记忆：", Colors.BRIGHT_CYAN, Colors.BOLD)
        )

        for i, (m, dist) in enumerate(memories):
            if dist < 0.3:
                label = colorize("非常相关", Colors.BRIGHT_GREEN)
            elif dist < 0.6:
                label = colorize("较为相关", Colors.BRIGHT_YELLOW)
            else:
                label = colorize("模糊相关", Colors.DIM)

            ts = m.get("timestamp", "")[:16].replace("T", " ")
            raw_text = m.get("text", "")
            text = raw_text[:60] + ("..." if len(raw_text) > 60 else "")
            self.safe_print(f"  [{i + 1}] {label}  {colorize(ts, Colors.DIM)}  {text}")

        self.safe_print("")

    def print_profile(self, content: str, role: "Role | None" = None) -> None:
        """Print the user profile."""
        if not content.strip():
            self.safe_print(
                colorize("\n  尚未建立画像，继续对话后会自动生成。\n", Colors.DIM)
            )
            return

        role_name = f"{role.name}角色" if role else ""
        self.safe_print(colorize(f"\n  👤 {role_name}画像：", Colors.BRIGHT_CYAN, Colors.BOLD))
        self.safe_print(content)
        self.safe_print("")

    def print_bot_reply(self, reply: str, role: "Role | None" = None) -> None:
        """Print the bot's reply with styling."""
        role_name = role.name if role else "机器人"
        role_icon = role.icon if role else "🤖"

        primary = Colors.get_color(role.style.primary_color) if role else Colors.BRIGHT_MAGENTA

        bot_label = colorize(f"{role_icon} {role_name}", primary, Colors.BOLD)
        separator = colorize("：", primary)
        self.safe_print(f"\n{bot_label}{separator}")
        reply_colored = colorize(reply, Colors.BRIGHT_WHITE)
        self.safe_print(f"   {reply_colored}")
        footer = colorize("─" * 40, Colors.DIM)
        self.safe_print(f"   {footer}\n")

    def print_goodbye(self) -> None:
        """Print goodbye message."""
        self.safe_print(
            colorize("\n👋 再见！期待下次与你交流 💚\n", Colors.BRIGHT_GREEN, Colors.BOLD)
        )

    def print_error(self, message: str) -> None:
        """Print an error message."""
        self.safe_print(colorize(f"\n[错误] {message}\n", Colors.BRIGHT_RED, Colors.BOLD))

    def print_success(self, message: str) -> None:
        """Print a success message."""
        self.safe_print(colorize(f"  ✅ {message}\n", Colors.BRIGHT_GREEN))

    def print_warning(self, message: str) -> None:
        """Print a warning message."""
        self.safe_print(colorize(f"  ⚠️  {message}\n", Colors.BRIGHT_YELLOW))