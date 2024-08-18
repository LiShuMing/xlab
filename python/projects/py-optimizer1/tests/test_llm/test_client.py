"""Tests for LLM client."""
import pytest
import httpx

from optimizer_analysis.config import LLMConfig
from optimizer_analysis.llm_client import LLMClient, ChatMessage, create_llm_client


class TestLLMClient:
    """Tests for LLM client."""

    @pytest.fixture
    def llm_config(self):
        """Get LLM config from environment."""
        return LLMConfig.from_env_file("~/.env")

    def test_create_client(self, llm_config):
        """Test client creation."""
        assert llm_config.base_url != ""
        assert llm_config.api_key != ""
        assert llm_config.model != ""

    def test_simple_chat(self, llm_config):
        """Test simple chat completion."""
        try:
            with LLMClient(llm_config, max_retries=3) as client:
                response = client.chat([
                    ChatMessage(role="user", content="Say 'hello' in one word.")
                ])
                assert response is not None
                assert len(response) > 0
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as e:
            pytest.skip(f"Network error (transient): {type(e).__name__}")

    def test_analyze_optimizer_code(self, llm_config):
        """Test code analysis capability."""
        sample_code = '''
        public class Optimizer {
            private Memo memo;
            private RuleSet ruleSet;

            public OptExpression optimize(OptExpression input) {
                memo = new Memo(input);
                explore(memo);
                return extractBestPlan(memo);
            }
        }
        '''
        try:
            with LLMClient(llm_config, max_retries=3) as client:
                response = client.analyze_code(
                    code=sample_code,
                    question="What optimizer pattern does this code follow?",
                )
                assert response is not None
                assert len(response) > 0
                # Should mention Cascades or memo-based optimization
                assert any(kw in response.lower() for kw in ["cascade", "memo", "optim", "rule"])
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as e:
            pytest.skip(f"Network error (transient): {type(e).__name__}")

    def test_create_llm_client_factory(self):
        """Test factory function."""
        with create_llm_client() as client:
            assert client.config is not None


class TestChatMessage:
    """Tests for ChatMessage model."""

    def test_chat_message_creation(self):
        """Test creating a chat message."""
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_chat_message_model_dump(self):
        """Test serializing chat message."""
        msg = ChatMessage(role="system", content="You are helpful.")
        data = msg.model_dump()
        assert data == {"role": "system", "content": "You are helpful."}