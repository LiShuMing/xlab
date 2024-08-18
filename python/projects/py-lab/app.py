"""
AI Lab Platform - Main Entry Point

A scalable, modular AI experimentation platform built with Streamlit and LangChain.
Features:
- Plugin-based module architecture
- Unified LLM factory (Qwen, OpenAI, Anthropic)
- Centralized configuration management
- Streaming output support
- Structured logging with tracing

Usage:
    streamlit run app.py
"""

import uuid

import streamlit as st

# Page configuration must be first Streamlit command
st.set_page_config(
    page_title="AI Lab Platform",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import after setting page config
from modules.base_module import ModuleRegistry
from utils.ui_helpers import render_sidebar_header, render_footer
from utils.logger import get_logger, set_correlation_id, configure_logging

# Configure logging on startup
configure_logging()

# Import modules to ensure registration
# ruff: noqa: F401
from modules.sandbox import SandboxModule
from modules.stock_analyzer import StockAnalyzerModule
from modules.blog_analyzer import BlogAnalyzerModule
from modules.starrocks_sql import StarRocksSQLModule
from modules.etf_analyzer import ETFAnalyzerModule

# Initialize logger
logger = get_logger(__name__)


def render_sidebar() -> str:
    """
    Render the sidebar with module selection and API configuration.
    
    Returns:
        Selected module full name (with icon).
    """
    render_sidebar_header("AI Lab Platform")
    
    # Get all registered modules
    modules = ModuleRegistry.get_modules()
    module_names = [m.get_full_name() for m in modules.values()]
    
    if not module_names:
        st.sidebar.error("No modules available!")
        return ""
    
    # Module selection
    st.sidebar.markdown("### 📦 Modules")
    selected = st.sidebar.selectbox(
        "Select Module",
        options=module_names,
        label_visibility="collapsed"
    )
    
    st.sidebar.divider()
    
    # API Configuration Status
    st.sidebar.markdown("### 🔑 API Status")
    from config.settings import settings
    
    render_api_status("Qwen (DashScope)", settings.dashscope_api_key)
    render_api_status("OpenAI", settings.openai_api_key)
    render_api_status("Anthropic", settings.anthropic_api_key)
    
    st.sidebar.divider()
    
    # About section
    with st.sidebar.expander("ℹ️ About"):
        st.markdown("""
        **AI Lab Platform** is a modular experimentation environment
        for AI agents, RAG, and LLM applications.
        
        **Features:**
        - 🧪 Sandbox experimentation
        - 🤖 Multi-agent systems
        - 📚 RAG knowledge bases
        - 🔄 Streaming output
        - 📊 Structured logging
        
        Built with Streamlit & LangChain.
        """)
    
    return selected


def render_api_status(provider: str, api_key: str | None) -> None:
    """Render API configuration status indicator."""
    icon = "✅" if api_key else "❌"
    status_color = "green" if api_key else "red"
    st.sidebar.markdown(f"{icon} <span style='color:{status_color}'>{provider}</span>", unsafe_allow_html=True)


def main() -> None:
    """Main application entry point."""
    # Set correlation ID for this session
    correlation_id = str(uuid.uuid4())[:8]
    set_correlation_id(correlation_id)
    
    logger.info("application_started", correlation_id=correlation_id)
    
    # Render sidebar and get selected module
    selected_module_name = render_sidebar()
    
    # Route to selected module
    if selected_module_name:
        module = ModuleRegistry.get_module_by_name(selected_module_name)
        if module:
            try:
                logger.info(
                    "module_rendering",
                    module=module.name,
                    correlation_id=correlation_id
                )
                module.render()
            except Exception as e:
                error_msg = f"Error rendering module: {str(e)}"
                st.error(error_msg)
                logger.error(
                    "module_render_error",
                    module=module.name,
                    error_type=type(e).__name__,
                    error=str(e),
                    exc_info=True
                )
        else:
            st.error(f"Module '{selected_module_name}' not found!")
            logger.error("module_not_found", module_name=selected_module_name)
    else:
        st.info("👈 Please select a module from the sidebar to begin.")
    
    # Render footer
    render_footer()
    
    logger.info("application_render_complete", correlation_id=correlation_id)


if __name__ == "__main__":
    main()
