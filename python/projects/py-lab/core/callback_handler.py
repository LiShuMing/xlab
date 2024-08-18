"""
Custom LangChain callback handlers for Streamlit streaming output.

Provides handlers for real-time token streaming and response display.
"""

from typing import Any

import streamlit as st
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from utils.logger import get_logger

logger = get_logger(__name__)


class StreamlitStreamCallbackHandler(BaseCallbackHandler):
    """
    Callback handler for streaming LLM responses to Streamlit.
    
    Updates a placeholder container with tokens as they arrive,
    providing real-time streaming output for better UX.
    
    Example:
        >>> container = st.empty()
        >>> handler = StreamlitStreamCallbackHandler(container)
        >>> llm = get_llm(streaming=True)
        >>> response = llm.invoke(messages, config={"callbacks": [handler]})
    """
    
    def __init__(self, container: st.delta_generator.DeltaGenerator):
        """
        Initialize with a Streamlit container for output.
        
        Args:
            container: Streamlit container (from st.empty() or similar).
        """
        self.container = container
        self.text: str = ""
        self.token_count: int = 0
    
    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """
        Run on new LLM token. Append to displayed text.
        
        Args:
            token: New token from LLM
            **kwargs: Additional arguments from LangChain
        """
        self.text += token
        self.token_count += 1
        self.container.markdown(self.text)
    
    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """
        Run when LLM ends. Final update.
        
        Args:
            response: Final LLM result
            **kwargs: Additional arguments from LangChain
        """
        self.container.markdown(self.text)
        logger.debug(
            "stream_complete",
            token_count=self.token_count,
            final_length=len(self.text)
        )
    
    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        """
        Run on LLM error. Display error message.
        
        Args:
            error: Exception that occurred
            **kwargs: Additional arguments from LangChain
        """
        error_msg = f"Error: {str(error)}"
        self.container.error(error_msg)
        logger.error(
            "stream_error",
            error_type=type(error).__name__,
            error=str(error),
            tokens_received=self.token_count
        )
    
    def get_full_text(self) -> str:
        """Get the complete accumulated text."""
        return self.text


class SimpleStreamHandler(BaseCallbackHandler):
    """
    Simple streaming handler that collects tokens in a list.
    
    Useful for testing or when direct container access isn't needed.
    Does not depend on Streamlit, making it suitable for backend use.
    
    Example:
        >>> handler = SimpleStreamHandler()
        >>> llm = get_llm(streaming=True)
        >>> response = llm.invoke(messages, config={"callbacks": [handler]})
        >>> print(handler.get_full_text())
    """
    
    def __init__(self):
        """Initialize empty token list."""
        self.tokens: list[str] = []
        self.token_count: int = 0
    
    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """
        Collect token.
        
        Args:
            token: New token from LLM
            **kwargs: Additional arguments from LangChain
        """
        self.tokens.append(token)
        self.token_count += 1
    
    def get_full_text(self) -> str:
        """Get concatenated text."""
        return "".join(self.tokens)
    
    def get_token_count(self) -> int:
        """Get number of tokens received."""
        return self.token_count
    
    def reset(self) -> None:
        """Reset the handler state."""
        self.tokens = []
        self.token_count = 0


class TokenCountingHandler(BaseCallbackHandler):
    """
    Handler that counts tokens and estimates costs.
    
    Useful for monitoring API usage and costs across different providers.
    """
    
    # Approximate costs per 1K tokens (as of 2024, update as needed)
    COST_PER_1K_TOKENS: dict[str, dict[str, float]] = {
        "gpt-3.5-turbo": {"prompt": 0.0015, "completion": 0.002},
        "gpt-4": {"prompt": 0.03, "completion": 0.06},
        "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
        "claude-3-sonnet": {"prompt": 0.003, "completion": 0.015},
        "claude-3-opus": {"prompt": 0.015, "completion": 0.075},
        "qwen-turbo": {"prompt": 0.0005, "completion": 0.0005},
        "qwen-plus": {"prompt": 0.002, "completion": 0.002},
        "qwen-max": {"prompt": 0.01, "completion": 0.01},
    }
    
    def __init__(self, model: str = "unknown"):
        """
        Initialize token counter.
        
        Args:
            model: Model name for cost estimation
        """
        self.model = model
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.total_tokens: int = 0
    
    def on_llm_start(
        self,
        serialized: dict[str, Any] | None,
        prompts: list[str],
        **kwargs: Any
    ) -> None:
        """Count prompt tokens on start."""
        # Rough estimate: 4 chars per token
        self.prompt_tokens = sum(len(p) for p in prompts) // 4
    
    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Count completion tokens."""
        self.completion_tokens += 1
        self.total_tokens = self.prompt_tokens + self.completion_tokens
    
    def get_cost_estimate(self) -> float:
        """
        Get estimated cost in USD.
        
        Returns:
            Estimated cost, or 0.0 if model costs unknown
        """
        costs = self.COST_PER_1K_TOKENS.get(self.model)
        if not costs:
            return 0.0
        
        prompt_cost = (self.prompt_tokens / 1000) * costs["prompt"]
        completion_cost = (self.completion_tokens / 1000) * costs["completion"]
        return round(prompt_cost + completion_cost, 6)
    
    def get_summary(self) -> dict[str, Any]:
        """Get token usage summary."""
        return {
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.get_cost_estimate(),
        }
