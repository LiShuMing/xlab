"""
Backward compatibility layer for the legacy API.

Provides the old `predict` and `predict_no_ui_long_connection` functions
that are used throughout the codebase, but implemented using the new
modern provider architecture.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from loguru import logger

from .core import ChatConfig, LLMFactory, Message, Role


class ConversationHistory:
    """Helper class to manage conversation history."""
    
    def __init__(self, system_prompt: str = ""):
        self.messages: List[Message] = []
        self.system_prompt = system_prompt
        if system_prompt:
            self.messages.append(Message.system(system_prompt))
    
    def add_user_message(self, content: str) -> None:
        """Add a user message to the history."""
        self.messages.append(Message.user(content))
    
    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to the history."""
        self.messages.append(Message.assistant(content))
    
    def to_list(self) -> List[Message]:
        """Get messages as a list."""
        return self.messages.copy()


def _get_api_key(llm_kwargs: Dict[str, Any]) -> Optional[str]:
    """
    Extract API key from llm_kwargs or environment.
    
    Priority:
    1. api_key in llm_kwargs
    2. LLM_API_KEY from ~/.env (unified key)
    3. Provider-specific env var
    4. Generic API_KEY env var
    """
    import os
    
    # Check for explicit api_key
    if "api_key" in llm_kwargs:
        return llm_kwargs["api_key"]
    
    # Check for unified LLM_API_KEY from ~/.env (highest priority)
    llm_api_key = os.getenv("LLM_API_KEY")
    if llm_api_key:
        return llm_api_key
    
    # Check provider-specific keys
    model = llm_kwargs.get("llm_model", "")
    
    if "claude" in model.lower():
        return os.getenv("ANTHROPIC_API_KEY")
    
    if "qwen" in model.lower():
        return os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
    
    # Default to OpenAI
    return os.getenv("OPENAI_API_KEY")


def _get_base_url(llm_kwargs: Dict[str, Any]) -> Optional[str]:
    """Get custom base URL if configured."""
    import os
    
    # Check for LLM_BASE_URL from ~/.env (highest priority)
    base_url = os.getenv("LLM_BASE_URL")
    if base_url:
        return base_url
    
    # Fallback to Qwen custom base URL
    model = llm_kwargs.get("llm_model", "")
    if "qwen" in model.lower():
        return os.getenv("QWEN_BASE_URL")
    
    return None


async def _async_predict(
    inputs: str,
    llm_kwargs: Dict[str, Any],
    history: List[str],
    system_prompt: str,
    stream: bool = True,
) -> AsyncGenerator[str, None]:
    """
    Async implementation of predict.
    
    Yields response chunks for streaming or complete response for non-streaming.
    """
    import os
    model = llm_kwargs.get("llm_model", "gpt-3.5-turbo")
    base_url = _get_base_url(llm_kwargs)
    
    try:
        # If LLM_BASE_URL is set, force using OpenAI provider with custom endpoint
        if os.getenv("LLM_BASE_URL"):
            from .providers import OpenAIProvider
            provider = OpenAIProvider(
                model=model,
                api_key=_get_api_key(llm_kwargs),
                base_url=base_url,
            )
        else:
            # Use default provider selection
            provider = LLMFactory.create(
                model=model,
                api_key=_get_api_key(llm_kwargs),
                base_url=base_url,
            )
    except Exception as e:
        logger.error(f"Failed to create provider for {model}: {e}")
        yield f"[Error] Failed to initialize {model}: {e}"
        return
    
    # Build conversation
    conv = ConversationHistory(system_prompt=system_prompt)
    
    # Add history (alternating user/assistant)
    for i, msg in enumerate(history):
        if i % 2 == 0:
            conv.add_user_message(msg)
        else:
            conv.add_assistant_message(msg)
    
    # Add current input
    conv.add_user_message(inputs)
    
    # Create config
    config = ChatConfig(
        temperature=llm_kwargs.get("temperature", 0.7),
        top_p=llm_kwargs.get("top_p", 1.0),
        max_tokens=llm_kwargs.get("max_tokens"),
        stream=stream,
        timeout=llm_kwargs.get("timeout", 60.0),
    )
    
    try:
        if stream:
            # Stream response
            full_response = ""
            async for chunk in provider.chat_stream(conv.to_list(), config):
                full_response += chunk
                yield full_response
        else:
            # Non-streaming
            response = await provider.chat(conv.to_list(), config)
            yield response.message.content
            
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        yield f"[Error] {str(e)}"


def predict(
    inputs: str,
    llm_kwargs: Dict[str, Any],
    plugin_kwargs: Optional[Dict[str, Any]] = None,
    chatbot: Optional[Any] = None,
    history: Optional[List[str]] = None,
    system_prompt: str = "",
    stream: bool = True,
    additional_fn: Optional[str] = None,
) -> Any:
    """
    Legacy predict function - single-threaded with UI updates.
    
    This is the main entry point for normal conversations with UI.
    Not suitable for multi-threaded plugin usage.
    
    Args:
        inputs: User input text
        llm_kwargs: LLM configuration (model, temperature, etc.)
        plugin_kwargs: Plugin-specific arguments
        chatbot: Chatbot UI instance
        history: Conversation history as list of strings
        system_prompt: System prompt text
        stream: Whether to stream the response
        additional_fn: Additional function to apply
        
    Yields:
        Updated chatbot state
    """
    history = history or []
    
    # Import UI update functions
    from toolbox import update_ui, update_ui_latest_msg
    
    if chatbot is None:
        raise ValueError("chatbot instance required for predict()")
    
    # Add user message to UI
    chatbot.append((inputs, ""))
    yield from update_ui(chatbot=chatbot, history=history)
    
    # Handle additional functionality if specified
    if additional_fn:
        from core_functional import handle_core_functionality
        inputs, history = handle_core_functionality(additional_fn, inputs, history, chatbot)
        chatbot[-1] = (inputs, "")
        yield from update_ui(chatbot=chatbot, history=history)
    
    # Run async prediction in sync context
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        
        # Get the async generator
        async_gen = _async_predict(inputs, llm_kwargs, history, system_prompt, stream)
        
        # Consume the generator
        response_text = ""
        while True:
            try:
                future = async_gen.asend(None)
                response_text = loop.run_until_complete(future)
                
                # Update UI
                chatbot[-1] = (inputs, response_text)
                yield from update_ui(chatbot=chatbot, history=history)
                
            except StopAsyncIteration:
                break
        
        # Update history
        history.extend([inputs, response_text])
        yield from update_ui(chatbot=chatbot, history=history)
        
    finally:
        loop.close()


def predict_no_ui_long_connection(
    inputs: str,
    llm_kwargs: Dict[str, Any],
    history: Optional[List[str]] = None,
    sys_prompt: str = "",
    observe_window: Optional[List[Any]] = None,
    console_silence: bool = False,
) -> str:
    """
    Legacy predict function - for multi-threaded plugin usage.
    
    This function is designed for function plugins that need to call
    LLMs in separate threads. It returns the complete response as a string.
    
    Args:
        inputs: User input text
        llm_kwargs: LLM configuration
        history: Conversation history
        sys_prompt: System prompt
        observe_window: Optional list for observing progress [content, timestamp]
        console_silence: Whether to suppress console output
        
    Returns:
        Complete LLM response as string
    """
    import time
    
    history = history or []
    observe_window = observe_window or []
    
    watch_dog_patience = 5  # Seconds before watchdog timeout
    response = ""
    last_update = time.time()
    
    # Run async prediction
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        
        async_gen = _async_predict(
            inputs, llm_kwargs, history, sys_prompt, stream=True
        )
        
        while True:
            try:
                # Check watchdog timeout
                if len(observe_window) >= 2:
                    if time.time() - observe_window[1] > watch_dog_patience:
                        raise RuntimeError("Watchdog timeout - request took too long")
                
                future = async_gen.asend(None)
                response = loop.run_until_complete(future)
                
                # Update observe window if provided
                if observe_window:
                    observe_window[0] = response
                    last_update = time.time()
                    if len(observe_window) >= 2:
                        observe_window[1] = last_update
                
            except StopAsyncIteration:
                break
                
    finally:
        loop.close()
    
    return response


# Convenience function for getting available models
def get_available_models() -> List[str]:
    """Get list of all available models."""
    return LLMFactory.list_supported_models()
