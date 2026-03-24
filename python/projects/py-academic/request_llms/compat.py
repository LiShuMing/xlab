"""
Backward compatibility layer for the legacy API.

Uses OpenAI SDK with configuration from ~/.env (LLM_BASE_URL, LLM_API_KEY, LLM_MODEL).
"""
from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator, Dict, List, Optional

from loguru import logger


def _get_model(llm_kwargs: Dict[str, Any]) -> str:
    """Get model from llm_kwargs or ~/.env"""
    import os
    # Priority: llm_kwargs > LLM_MODEL env
    return llm_kwargs.get("llm_model") or os.getenv("LLM_MODEL", "gpt-4o-mini")


async def _async_predict(
    inputs: str,
    llm_kwargs: Dict[str, Any],
    history: List[str],
    system_prompt: str,
    stream: bool = True,
) -> AsyncGenerator[str, None]:
    """
    Async implementation using OpenAI SDK directly.
    Configuration loaded from ~/.env (LLM_BASE_URL, LLM_API_KEY, LLM_MODEL).
    """
    try:
        # Import here to avoid circular dependency
        import sys
        import os
        
        # Add project root to path if needed
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        from config_new import get_openai_client, LLM_MODEL, LLM_TIMEOUT
        
        client = get_openai_client()
        model = _get_model(llm_kwargs)
        
        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add history (alternating user/assistant)
        for i, msg in enumerate(history):
            role = "user" if i % 2 == 0 else "assistant"
            messages.append({"role": role, "content": msg})
        
        # Add current input
        messages.append({"role": "user", "content": inputs})
        
        # Stream response
        if stream:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=llm_kwargs.get("temperature", 0.7),
                top_p=llm_kwargs.get("top_p", 1.0),
                max_tokens=llm_kwargs.get("max_tokens"),
                stream=True,
                timeout=LLM_TIMEOUT,
            )
            
            full_response = ""
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    yield full_response
        else:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=llm_kwargs.get("temperature", 0.7),
                top_p=llm_kwargs.get("top_p", 1.0),
                max_tokens=llm_kwargs.get("max_tokens"),
                stream=False,
                timeout=LLM_TIMEOUT,
            )
            yield response.choices[0].message.content
            
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
):
    """
    Legacy predict function - single-threaded with UI updates.
    Uses OpenAI SDK with ~/.env configuration.
    """
    history = history or []
    
    from toolbox import update_ui
    
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
        
        async_gen = _async_predict(inputs, llm_kwargs, history, system_prompt, stream)
        
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
    Uses OpenAI SDK with ~/.env configuration.
    """
    import time
    
    history = history or []
    observe_window = observe_window or []
    
    watch_dog_patience = 5
    response = ""
    last_update = time.time()
    
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
    """Get list of available models from config."""
    import os
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    return [model]
