"""
Test suite for AI Lab Platform.

Uses pytest for testing with proper fixtures and mocking.
Run with: pytest tests/test_app.py -v
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).parent.parent


class TestSettings:
    """Tests for configuration management."""
    
    def test_settings_default_values(self):
        """Test that settings have sensible defaults."""
        from config.settings import Settings
        
        settings = Settings()
        
        assert settings.default_provider == "qwen"
        assert settings.default_model == "qwen-turbo"
        assert settings.default_temperature == 0.7
        assert settings.default_max_tokens == 2000
        assert settings.chunk_size == 500
        assert settings.top_k_retrieval == 4
    
    def test_settings_validation(self):
        """Test settings validation."""
        from config.settings import Settings
        
        # Test temperature bounds
        with pytest.raises(Exception):  # pydantic.ValidationError
            Settings(default_temperature=3.0)  # Should fail, max is 2.0
        
        with pytest.raises(Exception):
            Settings(default_temperature=-0.1)  # Should fail, min is 0.0
    
    def test_settings_api_key_validation(self):
        """Test API key validation method."""
        from config.settings import Settings
        
        settings = Settings()
        
        # Without API keys, all should return False
        assert settings.validate_api_key("qwen") is False
        assert settings.validate_api_key("openai") is False
        assert settings.validate_api_key("anthropic") is False
        assert settings.validate_api_key("unknown") is False
    
    def test_settings_available_models(self):
        """Test getting available models for providers."""
        from config.settings import Settings
        
        settings = Settings()
        
        qwen_models = settings.get_available_models("qwen")
        assert "qwen-turbo" in qwen_models
        assert "qwen-plus" in qwen_models
        
        openai_models = settings.get_available_models("openai")
        assert "gpt-3.5-turbo" in openai_models
        
        # Unknown provider returns empty dict
        assert settings.get_available_models("unknown") == {}


class TestMemoryManager:
    """Tests for session memory management."""
    
    @patch('core.memory_manager.st')
    def test_memory_manager_init(self, mock_st):
        """Test memory manager initialization."""
        from core.memory_manager import SessionMemoryManager
        
        mock_session_state = {}
        mock_st.session_state = mock_session_state
        
        manager = SessionMemoryManager("test_session")
        
        assert manager.session_key == "test_session"
        assert "test_session" in mock_session_state
    
    @patch('core.memory_manager.st')
    def test_add_messages(self, mock_st):
        """Test adding messages to memory."""
        from core.memory_manager import SessionMemoryManager
        from langchain_core.messages import HumanMessage, AIMessage
        
        mock_session_state = {"test_chat": []}
        mock_st.session_state = mock_session_state
        
        manager = SessionMemoryManager("test_chat")
        manager.add_user_message("Hello")
        manager.add_ai_message("Hi there!")
        
        history = manager.get_history()
        assert len(history) == 2
        assert isinstance(history[0], HumanMessage)
        assert isinstance(history[1], AIMessage)
        assert history[0].content == "Hello"
    
    @patch('core.memory_manager.st')
    def test_clear_history(self, mock_st):
        """Test clearing history."""
        from core.memory_manager import SessionMemoryManager
        
        mock_session_state = {"test_chat": []}
        mock_st.session_state = mock_session_state
        
        manager = SessionMemoryManager("test_chat")
        manager.add_user_message("Hello")
        manager.clear()
        
        assert manager.get_history() == []
    
    @patch('core.memory_manager.st')
    def test_get_last_n_messages(self, mock_st):
        """Test retrieving last N messages."""
        from core.memory_manager import SessionMemoryManager
        
        mock_session_state = {"test_chat": []}
        mock_st.session_state = mock_session_state
        
        manager = SessionMemoryManager("test_chat")
        for i in range(5):
            manager.add_user_message(f"Message {i}")
        
        last_3 = manager.get_last_n_messages(3)
        assert len(last_3) == 3
    
    @patch('core.memory_manager.st')
    def test_token_estimate(self, mock_st):
        """Test token estimation."""
        from core.memory_manager import SessionMemoryManager
        
        mock_session_state = {"test_chat": []}
        mock_st.session_state = mock_session_state
        
        manager = SessionMemoryManager("test_chat")
        manager.add_user_message("Hello world")  # 11 chars
        
        # ~4 chars per token, so 11/4 = ~2-3 tokens
        estimate = manager.get_token_estimate()
        assert estimate >= 2


class TestOutput:
    """Tests for output layer."""
    
    def test_report_creation(self):
        """Test report creation."""
        from utils.output import Report, ReportMetadata, ReportSection
        
        metadata = ReportMetadata(title="Test Report")
        report = Report(metadata=metadata)
        
        report.add_section(ReportSection(title="Section 1", content="Content 1", order=2))
        report.add_section(ReportSection(title="Section 2", content="Content 2", order=1))
        
        # Should be sorted by order
        assert report.sections[0].title == "Section 2"
        assert report.sections[1].title == "Section 1"
    
    def test_report_to_markdown(self):
        """Test markdown conversion."""
        from utils.output import Report, ReportMetadata
        
        metadata = ReportMetadata(title="Test Report")
        report = Report(metadata=metadata, raw_content="# Test Content")
        
        markdown = report.to_markdown()
        assert "# Test Report" in markdown
        assert "# Test Content" in markdown
    
    def test_report_to_html(self):
        """Test HTML conversion."""
        from utils.output import Report, ReportMetadata
        
        metadata = ReportMetadata(title="Test Report")
        report = Report(metadata=metadata, raw_content="Test Content")
        
        html = report.to_html()
        assert "<html>" in html
        assert "Test Report" in html
        assert "Test Content" in html
    
    def test_report_to_json(self):
        """Test JSON conversion."""
        from utils.output import Report, ReportMetadata
        import json
        
        metadata = ReportMetadata(title="Test Report")
        report = Report(metadata=metadata, data={"key": "value"})
        
        json_str = report.to_json()
        data = json.loads(json_str)
        assert data["metadata"]["title"] == "Test Report"
        assert data["data"]["key"] == "value"
    
    def test_stock_report_creation(self):
        """Test stock report helper."""
        from utils.output import create_stock_report
        
        report = create_stock_report(
            ticker="AAPL",
            company_name="Apple Inc.",
            content="Analysis content",
            data={"price": 150.0}
        )
        
        assert report.metadata.title == "AAPL Investment Analysis"
        assert report.data["price"] == 150.0
        assert "aapl" in report.metadata.tags  # Tags are lowercased
    
    def test_file_output_handler(self, tmp_path):
        """Test file output handler."""
        from utils.output import FileOutputHandler, Report, ReportMetadata, ReportFormat
        
        handler = FileOutputHandler(tmp_path)
        report = Report(metadata=ReportMetadata(title="Test Report"), raw_content="Test")
        
        result = handler.handle(report, ReportFormat.MARKDOWN)
        
        assert result["success"] is True
        assert "filepath" in result
        assert Path(result["filepath"]).exists()


class TestLogger:
    """Tests for structured logging."""
    
    def test_get_logger(self):
        """Test logger creation."""
        from utils.logger import get_logger
        from structlog.stdlib import BoundLogger
        
        logger = get_logger("test_module")
        assert logger is not None
        assert isinstance(logger, BoundLogger)
    
    def test_context_variables(self):
        """Test context variable management."""
        from utils.logger import (
            set_correlation_id, get_correlation_id,
            set_session_id, get_session_id,
            reset_agent_step, increment_agent_step
        )
        
        # Test correlation ID
        set_correlation_id("test-corr-id")
        assert get_correlation_id() == "test-corr-id"
        
        # Test session ID
        set_session_id("test-session-id")
        assert get_session_id() == "test-session-id"
        
        # Test agent step
        reset_agent_step()
        assert increment_agent_step() == 1
        assert increment_agent_step() == 2


class TestTools:
    """Tests for tool framework."""
    
    def test_base_tool_schema(self):
        """Test tool schema generation."""
        from tools.base_tool import BaseTool, ToolInputSchema
        from pydantic import BaseModel, Field
        
        class TestInput(BaseModel):
            query: str = Field(description="Search query")
            limit: int = Field(default=10, description="Result limit")
        
        class TestTool(BaseTool):
            name = "test_tool"
            description = "A test tool"
            input_schema = TestInput
            
            def run(self, **kwargs) -> str:
                return "test result"
        
        tool = TestTool()
        desc = tool.get_description_with_schema()
        
        assert tool.name == "test_tool"
        assert "query" in desc
        assert "limit" in desc
        assert "Search query" in desc
    
    def test_tool_registry(self):
        """Test tool registration."""
        from tools.base_tool import ToolRegistry, register_tool, BaseTool
        
        ToolRegistry.clear()
        
        @register_tool
        class RegisteredTool(BaseTool):
            name = "registered_tool"
            description = "A registered tool"
            
            def run(self, **kwargs) -> str:
                return "result"
        
        assert ToolRegistry.get_tool("registered_tool") is not None
        assert len(ToolRegistry.get_all_tools()) == 1
        
        ToolRegistry.clear()


class TestFileStructure:
    """Tests for project file structure."""
    
    def test_requirements_file_exists(self):
        """Test that requirements.txt exists."""
        assert (PROJECT_ROOT / "requirements.txt").exists()
    
    def test_main_app_exists(self):
        """Test that main app file exists."""
        assert (PROJECT_ROOT / "app.py").exists()
    
    def test_config_files_exist(self):
        """Test that configuration files exist."""
        assert (PROJECT_ROOT / "config" / "settings.py").exists()
        assert (PROJECT_ROOT / "core" / "llm_factory.py").exists()
        assert (PROJECT_ROOT / "core" / "memory_manager.py").exists()
        assert (PROJECT_ROOT / "core" / "callback_handler.py").exists()
    
    def test_all_modules_exist(self):
        """Test that all expected module directories exist."""
        modules_dir = PROJECT_ROOT / "modules"
        expected_modules = [
            "sandbox",
            "stock_analyzer",
            "blog_analyzer",
            "starrocks_sql",
            "etf_analyzer",
        ]
        
        for module in expected_modules:
            assert (modules_dir / module).exists(), f"Module {module} missing"
            assert (modules_dir / module / "__init__.py").exists()
    
    def test_utils_modules_exist(self):
        """Test that utility modules exist."""
        assert (PROJECT_ROOT / "utils" / "logger.py").exists()
        assert (PROJECT_ROOT / "utils" / "output.py").exists()
        assert (PROJECT_ROOT / "utils" / "ui_helpers.py").exists()
    
    def test_tools_module_exists(self):
        """Test that tools module exists."""
        assert (PROJECT_ROOT / "tools" / "base_tool.py").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
