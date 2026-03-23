#!/usr/bin/env python3
"""py-ego: Multi-role AI chatbot with memory system.

Usage:
    python main.py

Environment Variables:
    USE_SIMPLE_EMBEDDING - Set to 'true' for hash embeddings (testing)
    USE_REAL_EMBEDDING   - Set to 'true' for semantic embeddings
    LLM_MODEL           - LLM model name (default: gpt-3.5-turbo)
    LLM_BASE_URL        - LLM API base URL
    LLM_API_KEY         - LLM API key
"""
from __future__ import annotations

import atexit
import logging
import os
import sys
from pathlib import Path

# Configure environment before importing ML libraries
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

# Default to simple embedding mode for stability
if os.getenv("USE_REAL_EMBEDDING", "false").lower() != "true":
    os.environ["USE_SIMPLE_EMBEDDING"] = "true"

from chat_service import ChatService
from cli.commands import CommandHandler
from cli.ui import Colors, TerminalUI, colorize
from config import get_settings
from roles.role_manager import RoleManager

# ============================================================================
# Command History Support (Up/Down Arrow Keys)
# ============================================================================

HISTORY_FILE = Path(__file__).parent / "data" / ".input_history"
HISTORY_MAX_LENGTH = 1000


def setup_readline() -> None:
    """Configure readline for command history with up/down arrow navigation.

    Enables:
    - Up/Down arrows to navigate previous commands
    - History persistence across sessions
    - Tab completion (if desired in future)

    Note: readline is only available on Unix-like systems (macOS, Linux).
    Windows users would need pyreadline3 or prompt_toolkit.
    """
    try:
        import readline

        # Create history file directory if needed
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Load existing history
        if HISTORY_FILE.exists():
            readline.read_history_file(str(HISTORY_FILE))

        # Set max history length
        readline.set_history_length(HISTORY_MAX_LENGTH)

        # Save history on exit
        def save_history() -> None:
            try:
                readline.write_history_file(str(HISTORY_FILE))
            except Exception:
                pass

        atexit.register(save_history)

        # Enable readline features
        readline.parse_and_bind("set editing-mode emacs")
        readline.parse_and_bind("set show-all-if-ambiguous on")

    except ImportError:
        # readline not available (Windows), history feature disabled
        pass


def get_input_with_history(prompt: str = "") -> str:
    """Get user input with history support.

    On Unix systems, this enables up/down arrow key navigation
    through previous commands.

    Args:
        prompt: The prompt string to display.

    Returns:
        User input string.
    """
    try:
        import readline
        # Add to history after successful input
        line = input(prompt)
        if line.strip():
            readline.add_history(line)
        return line
    except ImportError:
        return input(prompt)


# ============================================================================
# Main Application
# ============================================================================


def setup_logging() -> None:
    """Configure logging for the application."""
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        encoding="utf-8",
    )

    for logger_name in [
        "sentence_transformers", "transformers", "urllib3", "httpcore",
        "openai", "huggingface_hub", "httpx", "tqdm", "torch",
    ]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def main() -> None:
    """Main entry point for the py-ego chatbot."""
    setup_logging()
    setup_readline()  # Enable command history
    settings = get_settings()
    ui = TerminalUI()

    # Initialize role manager and chat service
    role_manager = RoleManager()
    chat_service = ChatService(role_manager=role_manager)
    cmd_handler = CommandHandler(chat_service=chat_service)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    use_simple = os.getenv("USE_SIMPLE_EMBEDDING", "false").lower() == "true"

    # Print welcome with current role
    ui.print_welcome(
        role=chat_service.current_role,
        model=settings.llm_model,
        use_simple_embedding=use_simple,
    )

    while True:
        try:
            # Print prompt with role icon
            role = chat_service.current_role
            primary = Colors.get_color(role.style.primary_color)

            ui.safe_print(
                colorize(f"{role.icon} 你", primary, Colors.BOLD)
                + colorize("：", primary),
                end="",
            )

            try:
                user_input = get_input_with_history()
            except UnicodeDecodeError as e:
                logging.error(f"Input decode error: {e}")
                ui.safe_print("⚠️ 输入包含无法识别的字符，请重新输入\n")
                continue

            user_input = user_input.strip()

            if user_input.lower() in {"exit", "quit", "退出"}:
                ui.print_goodbye()
                break

            if user_input.lower() in {"clear", "清空"}:
                chat_service.clear_memory()
                ui.print_warning(f"已清空 {role.name} 的记忆")
                continue

            if not user_input:
                continue

            if user_input.startswith("/"):
                cmd_handler.handle(user_input)
                continue

            thinking_msg = colorize(
                f"{role.icon} {role.name}正在思考...",
                primary,
                Colors.DIM,
            )
            ui.safe_print(f"{thinking_msg}", end="\r")

            try:
                reply = chat_service.chat(user_input)
            except Exception as e:
                logging.error(f"Chat error: {e}")
                ui.safe_print(" " * 50, end="\r")
                ui.print_error(str(e))
                continue

            ui.safe_print(" " * 50, end="\r")
            ui.print_bot_reply(reply, role=role)

        except KeyboardInterrupt:
            ui.print_goodbye()
            break

        except EOFError:
            ui.print_goodbye()
            break

        except Exception as e:
            logging.exception("Runtime error")
            ui.print_error(str(e))


if __name__ == "__main__":
    main()