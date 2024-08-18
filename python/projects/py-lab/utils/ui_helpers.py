"""
Streamlit UI helper functions for common components.

Provides reusable UI components for consistent styling and behavior
across all modules.
"""

from enum import Enum
from typing import Any

import streamlit as st

from utils.logger import get_logger

logger = get_logger(__name__)


class InfoBoxType(str, Enum):
    """Types of info boxes for render_info_box."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


def render_sidebar_header(title: str = "AI Lab Platform") -> None:
    """
    Render the standard sidebar header.
    
    Args:
        title: Application title to display
    """
    st.sidebar.title(f"🧠 {title}")
    st.sidebar.divider()


def render_footer() -> None:
    """Render the standard page footer with version info."""
    st.divider()
    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption(
            "🔧 AI Lab Platform | Built with Streamlit & LangChain | "
            "[Documentation](https://github.com)"
        )
    with col2:
        st.caption("v1.0.0")


def render_info_box(
    content: str,
    box_type: InfoBoxType = InfoBoxType.INFO
) -> None:
    """
    Render an info box with specified type.
    
    Args:
        content: Content to display
        box_type: Type of info box (info, success, warning, error)
        
    Example:
        >>> render_info_box("Operation completed", InfoBoxType.SUCCESS)
        >>> render_info_box("Check your input", InfoBoxType.WARNING)
    """
    match box_type:
        case InfoBoxType.INFO:
            st.info(content)
        case InfoBoxType.SUCCESS:
            st.success(content)
        case InfoBoxType.WARNING:
            st.warning(content)
        case InfoBoxType.ERROR:
            st.error(content)


def render_metric_row(metrics: dict[str, str | int | float]) -> None:
    """
    Render a row of metrics.
    
    Args:
        metrics: Dict of {label: value} pairs
        
    Example:
        >>> render_metric_row({"Accuracy": "95%", "Latency": "120ms"})
    """
    if not metrics:
        return
    
    cols = st.columns(len(metrics))
    for col, (label, value) in zip(cols, metrics.items()):
        col.metric(label, value)


def render_status_indicator(
    label: str,
    is_active: bool,
    active_text: str = "Active",
    inactive_text: str = "Inactive"
) -> None:
    """
    Render a status indicator with colored dot.
    
    Args:
        label: Status label
        is_active: Whether the status is active
        active_text: Text to show when active
        inactive_text: Text to show when inactive
    """
    color = "🟢" if is_active else "🔴"
    text = active_text if is_active else inactive_text
    st.markdown(f"{color} **{label}**: {text}")


def render_api_status(
    provider: str,
    is_configured: bool
) -> None:
    """
    Render API configuration status.
    
    Args:
        provider: Provider name (e.g., "Qwen", "OpenAI")
        is_configured: Whether API key is configured
    """
    icon = "✅" if is_configured else "❌"
    status = "configured" if is_configured else "not configured"
    st.markdown(f"{icon} {provider} ({status})")


def render_section_card(
    title: str,
    content: str,
    icon: str = "📄"
) -> None:
    """
    Render a card-style section.
    
    Args:
        title: Card title
        content: Card content (markdown supported)
        icon: Emoji icon
    """
    with st.container():
        st.markdown(f"### {icon} {title}")
        st.markdown(content)
        st.divider()


def render_loading_spinner(
    text: str = "Loading...",
    operation: str | None = None
) -> st.spinner:
    """
    Render a loading spinner with optional operation tracking.
    
    Args:
        text: Spinner text
        operation: Operation name for logging
        
    Returns:
        Streamlit spinner context manager
    """
    if operation:
        logger.debug("operation_started", operation=operation)
    return st.spinner(text)


def create_expander_with_icon(
    label: str,
    icon: str,
    expanded: bool = False
) -> st.expander:
    """
    Create an expander with an icon in the label.
    
    Args:
        label: Expander label
        icon: Emoji icon
        expanded: Whether expanded by default
        
    Returns:
        Streamlit expander
    """
    return st.expander(f"{icon} {label}", expanded=expanded)


def render_chat_message(
    role: str,
    content: str,
    avatar: str | None = None
) -> None:
    """
    Render a chat message with consistent styling.
    
    Args:
        role: Message role ("user", "assistant", "system")
        content: Message content
        avatar: Optional custom avatar emoji
    """
    default_avatars = {
        "user": "👤",
        "assistant": "🤖",
        "system": "⚙️",
    }
    
    display_avatar = avatar or default_avatars.get(role, "💬")
    
    with st.chat_message(role, avatar=display_avatar):
        st.markdown(content)


def render_code_block(
    code: str,
    language: str = "python",
    caption: str | None = None
) -> None:
    """
    Render a code block with optional caption.
    
    Args:
        code: Code content
        language: Programming language for syntax highlighting
        caption: Optional caption above the code block
    """
    if caption:
        st.caption(caption)
    st.code(code, language=language)


def render_data_table(
    data: list[dict[str, Any]],
    columns: list[str] | None = None
) -> None:
    """
    Render a data table from list of dictionaries.
    
    Args:
        data: List of data rows
        columns: Optional column names to display
    """
    if not data:
        st.info("No data to display")
        return
    
    if columns:
        filtered_data = [
            {k: v for k, v in row.items() if k in columns}
            for row in data
        ]
        st.dataframe(filtered_data, use_container_width=True, hide_index=True)
    else:
        st.dataframe(data, use_container_width=True, hide_index=True)
