"""
Streamlit UI helper functions for common components.
"""

import streamlit as st


def render_sidebar_header(title: str = "AI Lab Platform") -> None:
    """
    Render the standard sidebar header.
    
    Args:
        title: Application title.
    """
    st.sidebar.title(f"🧠 {title}")
    st.sidebar.divider()


def render_footer() -> None:
    """Render the standard page footer."""
    st.divider()
    st.caption(
        "🔧 AI Lab Platform | Built with Streamlit & LangChain | "
        "[Documentation](#)"
    )


def render_info_box(
    content: str,
    box_type: str = "info"
) -> None:
    """
    Render an info box with specified type.
    
    Args:
        content: Content to display.
        box_type: One of "info", "success", "warning", "error".
    """
    if box_type == "info":
        st.info(content)
    elif box_type == "success":
        st.success(content)
    elif box_type == "warning":
        st.warning(content)
    elif box_type == "error":
        st.error(content)


def render_metric_row(metrics: dict) -> None:
    """
    Render a row of metrics.
    
    Args:
        metrics: Dict of {label: value} pairs.
    """
    cols = st.columns(len(metrics))
    for col, (label, value) in zip(cols, metrics.items()):
        col.metric(label, value)
