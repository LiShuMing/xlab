"""
Backward compatibility layer for the legacy API.

Uses OpenAI SDK with configuration from ~/.env (LLM_BASE_URL, LLM_API_KEY, LLM_MODEL).
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, AsyncGenerator, Dict, List, Optional

from loguru import logger


def _get_model(llm_kwargs: Dict[str, Any]) -> str:
    """Get model from llm_kwargs or ~/.env"""
    # Priority: llm_kwargs > LLM_MODEL env
    return llm_kwargs.get("llm_model") or os.getenv("LLM_MODEL", "gpt-4o-mini")


def _try_read_file_or_directory(inputs: str) -> tuple[str, bool]:
    """
    Try to read file or directory if inputs is a valid path.
    Returns: (content_or_original, is_file_content)
    """
    # Check if inputs looks like a path
    if not inputs or len(inputs) > 500:
        return inputs, False
    
    # Strip whitespace and quotes
    path = inputs.strip().strip('"\'').strip()
    
    # Skip if it doesn't look like a path
    if not path or ' ' in path or '\n' in path:
        return inputs, False
    
    # Check if it's a valid path
    if not os.path.exists(path):
        return inputs, False
    
    try:
        # If it's a file
        if os.path.isfile(path):
            # Read text files
            if path.endswith(('.txt', '.md', '.py', '.json', '.yaml', '.yml', '.csv')):
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                filename = os.path.basename(path)
                return f"[File: {filename}]\n```\n{content[:8000]}{'...' if len(content) > 8000 else ''}\n```", True
            # For PDFs, return path info for plugins to handle
            elif path.endswith('.pdf'):
                return f"[PDF File: {os.path.basename(path)}]\nPath: {path}\n\n请使用 PDF 插件分析此文件。", True
            # For other files, just note the path
            else:
                return f"[File: {os.path.basename(path)}]\nPath: {path}", True
        
        # If it's a directory
        elif os.path.isdir(path):
            files = []
            for root, dirs, filenames in os.walk(path):
                for filename in filenames:
                    files.append(os.path.join(root, filename))
            # Limit file list
            file_list = '\n'.join(files[:50])
            if len(files) > 50:
                file_list += f'\n... and {len(files) - 50} more files'
            return f"[Directory: {path}]\nContains {len(files)} files:\n```\n{file_list}\n```", True
            
    except Exception as e:
        logger.debug(f"Failed to read path {path}: {e}")
    
    return inputs, False


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
    Automatically reads file/directory paths in inputs.
    """
    history = history or []
    
    from toolbox import update_ui
    
    if chatbot is None:
        raise ValueError("chatbot instance required for predict()")
    
    # Try to read file/directory if inputs is a path
    processed_inputs, is_file_content = _try_read_file_or_directory(inputs)
    
    # Add user message to UI (show original or processed)
    display_input = processed_inputs if is_file_content else inputs
    chatbot.append((display_input, ""))
    yield from update_ui(chatbot=chatbot, history=history)
    
    # Handle additional functionality if specified
    if additional_fn:
        from core_functional import handle_core_functionality
        inputs, history = handle_core_functionality(additional_fn, inputs, history, chatbot)
        chatbot[-1] = (inputs, "")
        yield from update_ui(chatbot=chatbot, history=history)
        # Re-process after additional_fn
        processed_inputs, is_file_content = _try_read_file_or_directory(inputs)
    
    # Run async prediction in sync context
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        
        # Use processed inputs for LLM
        async_gen = _async_predict(processed_inputs, llm_kwargs, history, system_prompt, stream)
        
        response_text = ""
        while True:
            try:
                future = async_gen.asend(None)
                response_text = loop.run_until_complete(future)
                
                # Update UI
                chatbot[-1] = (display_input, response_text)
                yield from update_ui(chatbot=chatbot, history=history)
                
            except StopAsyncIteration:
                break
        
        # Update history (use display_input for history too)
        history.extend([display_input, response_text])
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
    
    # Try to read file/directory if inputs is a path
    processed_inputs, _ = _try_read_file_or_directory(inputs)
    
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        
        async_gen = _async_predict(
            processed_inputs, llm_kwargs, history, sys_prompt, stream=True
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
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    return [model]
