"""
Custom LangChain callback handlers for Streamlit streaming output.
"""

from typing import Any
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
import streamlit as st


class StreamlitStreamCallbackHandler(BaseCallbackHandler):
    """
    Callback handler for streaming LLM responses to Streamlit.
    Updates a placeholder container with tokens as they arrive.
    """
    
    def __init__(self, container: st.delta_generator.DeltaGenerator):
        """
        Initialize with a Streamlit container for output.
        
        Args:
            container: Streamlit container (from st.empty() or similar).
        """
        self.container = container
        self.text = ""
    
    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Run on new LLM token. Append to displayed text."""
        self.text += token
        self.container.markdown(self.text)
    
    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Run when LLM ends. Final update."""
        self.container.markdown(self.text)
    
    def on_llm_error(self, error: Exception, **kwargs: Any) -> None:
        """Run on LLM error. Display error message."""
        self.container.error(f"Error: {str(error)}")


class SimpleStreamHandler(BaseCallbackHandler):
    """
    Simple streaming handler that collects tokens in a list.
    Useful for testing or when direct container access isn't needed.
    """
    
    def __init__(self):
        """Initialize empty token list."""
        self.tokens = []
    
    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Collect token."""
        self.tokens.append(token)
    
    def get_full_text(self) -> str:
        """Get concatenated text."""
        return "".join(self.tokens)
