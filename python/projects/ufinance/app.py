"""
AI Lab Platform - Main Entry Point

A scalable, modular AI experimentation platform built with Streamlit and LangChain.
Features:
- Plugin-based module architecture
- Unified LLM factory (Qwen, OpenAI, Anthropic)
- Centralized configuration management
- Streaming output support
"""

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
from utils.logger import get_logger

# Import modules to ensure registration
# pylint: disable=unused-import
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
        Selected module full name.
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
    
    if settings.DASHSCOPE_API_KEY:
        st.sidebar.success("✅ Qwen (DashScope)")
    else:
        st.sidebar.error("❌ Qwen (DashScope)")
    
    if settings.OPENAI_API_KEY:
        st.sidebar.success("✅ OpenAI")
    else:
        st.sidebar.error("❌ OpenAI")
    
    if settings.ANTHROPIC_API_KEY:
        st.sidebar.success("✅ Anthropic")
    else:
        st.sidebar.error("❌ Anthropic")
    
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
        
        Built with Streamlit & LangChain.
        """)
    
    return selected


def main() -> None:
    """Main application entry point."""
    logger.info("Application started")
    
    # Render sidebar and get selected module
    selected_module_name = render_sidebar()
    
    # Route to selected module
    if selected_module_name:
        module = ModuleRegistry.get_module_by_name(selected_module_name)
        if module:
            try:
                module.render()
            except Exception as e:
                st.error(f"Error rendering module: {str(e)}")
                logger.error(f"Module render error: {e}", exc_info=True)
        else:
            st.error(f"Module '{selected_module_name}' not found!")
    else:
        st.info("👈 Please select a module from the sidebar to begin.")
    
    # Render footer
    render_footer()


if __name__ == "__main__":
    main()
