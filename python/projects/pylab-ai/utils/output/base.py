"""
Base abstractions for output layer.

Following the design_doc.md specification:
- Renderers: Convert AnalysisReport to target format (HTML, JSON, PDF)
- Dispatchers: Send content to destination (Email, Web, Slack)
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ReportFormat(str, Enum):
    """Supported report output formats."""
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"
    PDF = "pdf"
    TXT = "txt"


class ReportSection(str, Enum):
    """Standard report sections."""
    OVERVIEW = "overview"
    MACRO = "macro"
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    MULTI_LENS = "multi_lens"
    RISK = "risk"
    POSITION = "position"
    RATING = "rating"


@dataclass
class ReportMetadata:
    """Metadata for a generated report."""
    title: str
    author: str = "AI Analyst"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    version: str = "1.0.0"
    language: str = "zh-CN"
    source: Optional[str] = None
    tags: list = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            "title": self.title,
            "author": self.author,
            "created_at": self.created_at,
            "version": self.version,
            "language": self.language,
            "source": self.source,
            "tags": self.tags,
        }


@dataclass
class Report:
    """
    Structured report data model.
    
    Contains both structured sections and raw content for flexible rendering.
    """
    # Core identification
    ticker: str
    company_name: str
    
    # Metadata
    metadata: ReportMetadata = field(default_factory=lambda: ReportMetadata(title=""))
    
    # Structured sections (for programmatic access)
    sections: Dict[ReportSection, str] = field(default_factory=dict)
    
    # Raw content (for direct rendering)
    content: str = ""
    
    # Additional data
    data: Dict[str, Any] = field(default_factory=dict)
    
    def get_section(self, section: ReportSection) -> str:
        """Get specific section content."""
        return self.sections.get(section, "")
    
    def set_section(self, section: ReportSection, content: str) -> None:
        """Set specific section content."""
        self.sections[section] = content
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "ticker": self.ticker,
            "company_name": self.company_name,
            "metadata": self.metadata.to_dict(),
            "sections": {k.value: v for k, v in self.sections.items()},
            "content": self.content,
            "data": self.data,
        }


class BaseRenderer(ABC):
    """
    Abstract base class for report renderers.
    
    Renderers convert Report objects to target format strings.
    """
    
    # Supported format for this renderer
    format: ReportFormat = ReportFormat.MARKDOWN
    
    @abstractmethod
    def render(self, report: Report) -> str:
        """
        Render report to target format.
        
        Args:
            report: Report object to render.
            
        Returns:
            Rendered content as string.
        """
        pass
    
    @abstractmethod
    def get_content_type(self) -> str:
        """
        Get MIME content type for the rendered format.
        
        Returns:
            MIME type string (e.g., "text/html", "application/json").
        """
        pass
    
    def get_file_extension(self) -> str:
        """Get file extension for the rendered format."""
        return self.format.value


class BaseDispatcher(ABC):
    """
    Abstract base class for content dispatchers.
    
    Dispatchers send rendered content to destinations (file, email, web, etc.).
    """
    
    @abstractmethod
    def dispatch(
        self, 
        content: str, 
        destination: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send content to destination.
        
        Args:
            content: Content to dispatch (already rendered).
            destination: Target destination (path, URL, email, etc.).
            metadata: Optional metadata for dispatch context.
            
        Returns:
            True if dispatch succeeded, False otherwise.
        """
        pass
    
    @abstractmethod
    def validate_destination(self, destination: str) -> bool:
        """
        Validate if destination is properly formatted.
        
        Args:
            destination: Destination string to validate.
            
        Returns:
            True if valid, False otherwise.
        """
        pass


class OutputManager:
    """
    Central manager for report output operations.
    
    Combines renderers and dispatchers for complete output workflow.
    """
    
    def __init__(self):
        """Initialize with empty renderer/dispatcher registries."""
        self._renderers: Dict[ReportFormat, BaseRenderer] = {}
        self._dispatchers: Dict[str, BaseDispatcher] = {}
    
    def register_renderer(self, renderer: BaseRenderer) -> None:
        """Register a renderer for its format."""
        self._renderers[renderer.format] = renderer
    
    def register_dispatcher(self, name: str, dispatcher: BaseDispatcher) -> None:
        """Register a dispatcher with a name."""
        self._dispatchers[name] = dispatcher
    
    def get_renderer(self, format: ReportFormat) -> Optional[BaseRenderer]:
        """Get renderer for specified format."""
        return self._renderers.get(format)
    
    def get_dispatcher(self, name: str) -> Optional[BaseDispatcher]:
        """Get dispatcher by name."""
        return self._dispatchers.get(name)
    
    def render(self, report: Report, format: ReportFormat) -> str:
        """
        Render report to specified format.
        
        Args:
            report: Report to render.
            format: Target format.
            
        Returns:
            Rendered content.
            
        Raises:
            ValueError: If no renderer registered for format.
        """
        renderer = self._renderers.get(format)
        if not renderer:
            raise ValueError(f"No renderer registered for format: {format}")
        return renderer.render(report)
    
    def output(
        self,
        report: Report,
        format: ReportFormat,
        dispatcher_name: str,
        destination: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Complete output workflow: render then dispatch.
        
        Args:
            report: Report to output.
            format: Target format.
            dispatcher_name: Name of dispatcher to use.
            destination: Destination for dispatch.
            metadata: Optional metadata.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            # Render
            content = self.render(report, format)
            
            # Dispatch
            dispatcher = self._dispatchers.get(dispatcher_name)
            if not dispatcher:
                raise ValueError(f"No dispatcher registered: {dispatcher_name}")
            
            return dispatcher.dispatch(content, destination, metadata)
        except Exception as e:
            # Log error and return failure
            from utils.logger import get_logger
            logger = get_logger(__name__)
            logger.error(f"Output failed: {e}")
            return False
