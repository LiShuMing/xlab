"""
Output layer for AI Lab Platform.

Provides standardized report generation and distribution capabilities.
Following the design_doc.md Output Layer specification.

Usage:
    from utils.output import Report, ReportFormat, OutputManager
    from utils.output import MarkdownRenderer, HtmlRenderer, FileDispatcher
    
    # Create report
    report = Report(
        ticker="AAPL",
        company_name="Apple Inc.",
        metadata=ReportMetadata(title="Investment Analysis Report"),
        content="# Analysis Report\n..."
    )
    
    # Setup output manager
    manager = OutputManager()
    manager.register_renderer(MarkdownRenderer())
    manager.register_dispatcher("file", FileDispatcher())
    
    # Render and save
    markdown = manager.render(report, ReportFormat.MARKDOWN)
    manager.output(report, ReportFormat.MARKDOWN, "file", "report.md")

Quick Output (for most common use cases):
    from utils.output import quick_output, ReportFormat
    
    # One-liner to render and save
    quick_output(report, format=ReportFormat.HTML, filename="AAPL_report.html")
"""

# Base abstractions
from utils.output.base import (
    BaseRenderer,
    BaseDispatcher,
    OutputManager,
    Report,
    ReportFormat,
    ReportSection,
    ReportMetadata,
)

# Renderers
from utils.output.renderers import (
    MarkdownRenderer,
    HtmlRenderer,
    JsonRenderer,
    TextRenderer,
    get_default_renderers,
)

# Dispatchers
from utils.output.dispatchers import (
    FileDispatcher,
    StreamlitDispatcher,
    MemoryDispatcher,
    get_file_dispatcher,
    get_streamlit_dispatcher,
    get_memory_dispatcher,
)

__all__ = [
    # Base classes
    "BaseRenderer",
    "BaseDispatcher",
    "OutputManager",
    "Report",
    "ReportFormat",
    "ReportSection",
    "ReportMetadata",
    
    # Renderers
    "MarkdownRenderer",
    "HtmlRenderer",
    "JsonRenderer",
    "TextRenderer",
    "get_default_renderers",
    
    # Dispatchers
    "FileDispatcher",
    "StreamlitDispatcher",
    "MemoryDispatcher",
    "get_file_dispatcher",
    "get_streamlit_dispatcher",
    "get_memory_dispatcher",
    
    # Convenience functions
    "quick_output",
    "create_stock_report",
]


# Import types for function signatures
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime


def quick_output(
    report: Report,
    format: ReportFormat = ReportFormat.MARKDOWN,
    filename: Optional[str] = None,
    output_dir: Optional[Path] = None,
    show_streamlit: bool = True,
    show_download: bool = True,
) -> Dict[str, Any]:
    """
    Quick output function for common use cases.
    
    Renders report to specified format, saves to file, and optionally displays in Streamlit.
    
    Args:
        report: Report to output.
        format: Target format (default: markdown).
        filename: Output filename (auto-generated if None).
        output_dir: Directory for file output (default: ./reports).
        show_streamlit: Whether to display in Streamlit UI.
        show_download: Whether to show download button.
        
    Returns:
        Dictionary with 'content', 'filepath', and 'success' status.
    """
    from pathlib import Path
    from datetime import datetime
    from typing import Optional, Dict, Any
    
    # Setup manager with default renderers
    manager = OutputManager()
    for fmt, renderer in get_default_renderers().items():
        manager.register_renderer(renderer)
    
    # Setup file dispatcher
    file_dispatcher = get_file_dispatcher(output_dir)
    manager.register_dispatcher("file", file_dispatcher)
    
    # Generate filename if not provided
    if filename is None:
        ts = datetime.now().strftime('%Y%m%d')
        ext = format.value
        filename = f"{report.ticker}_analysis_{ts}.{ext}"
    
    # Render content
    try:
        content = manager.render(report, format)
    except Exception as e:
        return {
            "success": False,
            "error": f"Render failed: {e}",
            "content": None,
            "filepath": None,
        }
    
    # Save to file
    success = manager.output(report, format, "file", filename)
    filepath = file_dispatcher.base_dir / filename if success else None
    
    # Streamlit display
    if show_streamlit:
        try:
            import streamlit as st
            
            # Show success message
            if success and filepath:
                st.success(f"✅ Report saved: {filepath.name}")
            
            # Display content
            st_dispatcher = get_streamlit_dispatcher()
            if format == ReportFormat.HTML:
                st_dispatcher.dispatch(content, 'html', {'unsafe_allow_html': True})
            elif format == ReportFormat.JSON:
                st.json(report.to_dict())
            else:
                st.markdown(content)
            
            # Download button
            if show_download:
                mime_types = {
                    ReportFormat.MARKDOWN: "text/markdown",
                    ReportFormat.HTML: "text/html",
                    ReportFormat.JSON: "application/json",
                    ReportFormat.TXT: "text/plain",
                }
                st.download_button(
                    label=f"📥 Download {format.value.upper()}",
                    data=content,
                    file_name=filename,
                    mime=mime_types.get(format, "text/plain"),
                    use_container_width=True,
                )
                
        except ImportError:
            pass  # Not running in Streamlit
    
    return {
        "success": success,
        "content": content,
        "filepath": str(filepath) if filepath else None,
        "format": format.value,
    }


def create_stock_report(
    ticker: str,
    company_name: str,
    content: str,
    title: Optional[str] = None,
    sections: Optional[Dict[ReportSection, str]] = None,
    data: Optional[Dict[str, Any]] = None,
) -> Report:
    """
    Factory function to create a stock analysis report.
    
    Args:
        ticker: Stock ticker symbol.
        company_name: Company name.
        content: Main report content (markdown).
        title: Report title (default: "{ticker} Investment Analysis").
        sections: Optional structured sections.
        data: Optional additional data.
        
    Returns:
        Configured Report instance.
    """
    from datetime import datetime
    
    if title is None:
        title = f"{ticker} Investment Analysis Report"
    
    metadata = ReportMetadata(
        title=title,
        created_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    )
    
    return Report(
        ticker=ticker,
        company_name=company_name,
        metadata=metadata,
        content=content,
        sections=sections or {},
        data=data or {},
    )
