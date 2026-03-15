"""
Concrete dispatcher implementations for report output.

Supports file, streamlit UI, and email dispatch.
"""

from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime

from utils.output.base import BaseDispatcher
from utils.logger import get_logger

logger = get_logger(__name__)


class FileDispatcher(BaseDispatcher):
    """
    Dispatcher for saving content to local files.
    """
    
    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize file dispatcher.
        
        Args:
            base_dir: Base directory for file output. Defaults to current directory.
        """
        self.base_dir = base_dir or Path.cwd()
    
    def dispatch(
        self, 
        content: str, 
        destination: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Save content to file.
        
        Args:
            content: Content to save.
            destination: File path (relative to base_dir or absolute).
            metadata: Optional metadata (may include 'encoding', 'create_dirs').
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            # Resolve path
            path = Path(destination)
            if not path.is_absolute():
                path = self.base_dir / path
            
            # Create directories if needed
            if metadata and metadata.get('create_dirs', True):
                path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            encoding = metadata.get('encoding', 'utf-8') if metadata else 'utf-8'
            path.write_text(content, encoding=encoding)
            
            logger.info(f"File saved: {path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save file: {e}")
            return False
    
    def validate_destination(self, destination: str) -> bool:
        """Validate file path."""
        try:
            path = Path(destination)
            # Check if path is valid (doesn't contain invalid characters)
            return bool(path.name)
        except Exception:
            return False
    
    def generate_filename(
        self, 
        ticker: str, 
        extension: str = "md",
        timestamp: Optional[str] = None
    ) -> str:
        """
        Generate standardized filename for reports.
        
        Args:
            ticker: Stock ticker symbol.
            extension: File extension.
            timestamp: Optional timestamp (defaults to now).
            
        Returns:
            Generated filename.
        """
        ts = timestamp or datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"{ticker}_analysis_{ts}.{extension}"


class StreamlitDispatcher(BaseDispatcher):
    """
    Dispatcher for displaying content in Streamlit UI.
    
    Renders content directly to the Streamlit interface.
    """
    
    def __init__(self, use_expander: bool = False):
        """
        Initialize Streamlit dispatcher.
        
        Args:
            use_expander: Whether to wrap content in an expander.
        """
        self.use_expander = use_expander
    
    def dispatch(
        self, 
        content: str, 
        destination: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Display content in Streamlit.
        
        Args:
            content: Content to display.
            destination: Display mode ('markdown', 'html', 'code', 'json').
            metadata: Optional metadata (may include 'height', 'unsafe_allow_html').
            
        Returns:
            True (Streamlit doesn't return success status).
        """
        try:
            import streamlit as st
            
            mode = destination.lower()
            
            if mode == 'markdown':
                if self.use_expander and metadata:
                    with st.expander(metadata.get('expander_title', 'Report')):
                        st.markdown(content)
                else:
                    st.markdown(content)
                    
            elif mode == 'html':
                unsafe = metadata.get('unsafe_allow_html', True) if metadata else True
                if self.use_expander and metadata:
                    with st.expander(metadata.get('expander_title', 'HTML Report')):
                        st.html(content)
                else:
                    st.html(content)
                    
            elif mode == 'code':
                language = metadata.get('language', 'text') if metadata else 'text'
                st.code(content, language=language)
                
            elif mode == 'json':
                st.json(content)
                
            else:
                # Default to markdown
                st.markdown(content)
            
            return True
            
        except Exception as e:
            logger.error(f"Streamlit display failed: {e}")
            return False
    
    def validate_destination(self, destination: str) -> bool:
        """Validate display mode."""
        valid_modes = {'markdown', 'html', 'code', 'json'}
        return destination.lower() in valid_modes
    
    def download_button(
        self,
        content: str,
        filename: str,
        label: str = "📥 Download Report",
        mime: str = "text/markdown",
        use_container_width: bool = True
    ) -> bool:
        """
        Render a download button in Streamlit.
        
        Args:
            content: Content to download.
            filename: Suggested filename.
            label: Button label.
            mime: MIME type.
            use_container_width: Whether to use full container width.
            
        Returns:
            True if button was clicked, False otherwise.
        """
        try:
            import streamlit as st
            
            return st.download_button(
                label=label,
                data=content,
                file_name=filename,
                mime=mime,
                use_container_width=use_container_width
            )
        except Exception as e:
            logger.error(f"Download button failed: {e}")
            return False


class MemoryDispatcher(BaseDispatcher):
    """
    Dispatcher that stores content in memory.
    
    Useful for caching or testing without I/O.
    """
    
    def __init__(self):
        """Initialize with empty storage."""
        self.storage: Dict[str, str] = {}
    
    def dispatch(
        self, 
        content: str, 
        destination: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Store content in memory.
        
        Args:
            content: Content to store.
            destination: Key for storage.
            metadata: Optional metadata (ignored).
            
        Returns:
            True if successful.
        """
        self.storage[destination] = content
        return True
    
    def validate_destination(self, destination: str) -> bool:
        """Any non-empty string is valid as a key."""
        return bool(destination)
    
    def get(self, key: str) -> Optional[str]:
        """Retrieve stored content."""
        return self.storage.get(key)
    
    def clear(self) -> None:
        """Clear all stored content."""
        self.storage.clear()


# Pre-configured dispatcher instances for common use cases

def get_file_dispatcher(output_dir: Optional[Path] = None) -> FileDispatcher:
    """Get file dispatcher with optional output directory."""
    from config.settings import BASE_DIR
    
    if output_dir is None:
        output_dir = BASE_DIR / "reports"
        output_dir.mkdir(exist_ok=True)
    
    return FileDispatcher(base_dir=output_dir)


def get_streamlit_dispatcher() -> StreamlitDispatcher:
    """Get standard Streamlit dispatcher."""
    return StreamlitDispatcher()


def get_memory_dispatcher() -> MemoryDispatcher:
    """Get memory dispatcher (useful for testing)."""
    return MemoryDispatcher()
