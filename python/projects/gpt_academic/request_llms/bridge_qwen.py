"""
Qwen / DashScope bridge — bridge_qwen.py
=========================================
Supports all Qwen cloud models accessed through the DashScope SDK, including:
    - qwen-turbo, qwen-plus, qwen-max, qwen-max-latest, …
    - dashscope-deepseek-r1, dashscope-deepseek-v3 (hosted on DashScope)
    - dashscope-qwen3-* (Qwen3 series hosted on DashScope)

Required dependency: dashscope
    pip install --upgrade dashscope

API keys (checked in priority order):
    1. Environment variable QWEN_API_KEY
    2. Config option QWEN_API_KEY  (config_private.py or config.py)
    3. Config option DASHSCOPE_API_KEY
"""

import time
import os
from toolbox import update_ui, get_conf, update_ui_latest_msg
from toolbox import check_packages, log_chat

_MODEL_DISPLAY_NAME = "Qwen"


def get_qwen_api_key() -> str:
    """
    Retrieve the Qwen / DashScope API key.

    Priority: env QWEN_API_KEY > config QWEN_API_KEY > config DASHSCOPE_API_KEY.
    Returns an empty string if no key is configured.
    """
    qwen_key = os.environ.get("QWEN_API_KEY")
    if qwen_key:
        return qwen_key
    conf_qwen_key = get_conf("QWEN_API_KEY")
    if conf_qwen_key and conf_qwen_key.strip():
        return conf_qwen_key
    return get_conf("DASHSCOPE_API_KEY")


def predict_no_ui_long_connection(inputs: str, llm_kwargs: dict, history: list = [],
                                  sys_prompt: str = "", observe_window: list = [],
                                  console_silence: bool = False) -> str:
    """
    Send a request to Qwen and wait for the full response (multi-thread safe).
    See request_llms/bridge_all.py for the full parameter description.
    """
    watch_dog_patience = 5  # seconds before watchdog kills the call
    response = ""

    from .com_qwenapi import QwenRequestInstance
    client = QwenRequestInstance()
    for response in client.generate(inputs, llm_kwargs, history, sys_prompt):
        if len(observe_window) >= 1:
            observe_window[0] = response  # update output buffer for live preview
        if len(observe_window) >= 2:
            if (time.time() - observe_window[1]) > watch_dog_patience:
                raise RuntimeError("Request cancelled by user.")
    return response


def predict(inputs, llm_kwargs, plugin_kwargs, chatbot, history=[], system_prompt='',
            stream=True, additional_fn=None):
    """
    Stream a response from Qwen and update the Gradio UI in real time.
    See request_llms/bridge_all.py for the full parameter description.
    """
    chatbot.append((inputs, ""))
    yield from update_ui(chatbot=chatbot, history=history)

    # Verify that the dashscope package is installed
    try:
        check_packages(["dashscope"])
    except Exception:
        yield from update_ui_latest_msg(
            "Missing dependency. Install with: ```pip install --upgrade dashscope```",
            chatbot=chatbot, history=history, delay=0,
        )
        return

    # Verify that an API key is configured
    if not get_qwen_api_key():
        yield from update_ui_latest_msg(
            "Please configure QWEN_API_KEY or DASHSCOPE_API_KEY in config_private.py.",
            chatbot=chatbot, history=history, delay=0,
        )
        return

    if additional_fn is not None:
        from core_functional import handle_core_functionality
        inputs, history = handle_core_functionality(additional_fn, inputs, history, chatbot)
        chatbot[-1] = (inputs, "")
        yield from update_ui(chatbot=chatbot, history=history)

    # Stream the response
    from .com_qwenapi import QwenRequestInstance
    client = QwenRequestInstance()
    response = f"[Local Message] Waiting for {_MODEL_DISPLAY_NAME} response ..."
    for response in client.generate(inputs, llm_kwargs, history, system_prompt):
        chatbot[-1] = (inputs, response)
        yield from update_ui(chatbot=chatbot, history=history)

    log_chat(llm_model=llm_kwargs["llm_model"], input_str=inputs, output_str=response)

    # Check for empty/error response
    if response == f"[Local Message] Waiting for {_MODEL_DISPLAY_NAME} response ...":
        response = f"[Local Message] {_MODEL_DISPLAY_NAME} returned an unexpected response."
    history.extend([inputs, response])
    yield from update_ui(chatbot=chatbot, history=history)