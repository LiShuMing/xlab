"""
DashScope / Qwen API client — com_qwenapi.py
=============================================
Low-level client that wraps the ``dashscope`` SDK for streaming Qwen requests.

API key resolution order:
    1. Environment variable QWEN_API_KEY
    2. Config option QWEN_API_KEY  (config_private.py or config.py)
    3. Config option DASHSCOPE_API_KEY

Custom base URL (optional):
    Set QWEN_BASE_URL (env var or config) to redirect to a compatible proxy.
    The SDK appends the correct path automatically; trailing '/v1' is stripped.
"""

from http import HTTPStatus
from toolbox import get_conf
import threading
import os

timeout_bot_msg = "[Local Message] Request timeout. Network error."
# DashScope-hosted third-party models are prefixed with "dashscope-" in our
# model registry but the SDK expects the bare model name.
_DASHSCOPE_PREFIX = "dashscope-"


class QwenRequestInstance:
    """
    Stateful request instance for a single Qwen streaming call.

    Instantiate once per request; call generate() to iterate over partial
    responses.
    """

    def __init__(self) -> None:
        import dashscope
        self.time_to_yield_event = threading.Event()
        self.time_to_exit_event = threading.Event()
        self.result_buf = ""
        self.use_custom_endpoint = False

        def _resolve_api_key() -> tuple[bool, str | None, str | None]:
            """Return (valid, api_key, source_label)."""
            qwen_key = os.environ.get("QWEN_API_KEY") or get_conf("QWEN_API_KEY")
            if qwen_key:
                return True, qwen_key, "QWEN_API_KEY"
            dashscope_key = get_conf("DASHSCOPE_API_KEY")
            if dashscope_key:
                return True, dashscope_key, "DASHSCOPE_API_KEY"
            return False, None, None

        valid, api_key, _ = _resolve_api_key()
        if not valid:
            raise RuntimeError(
                "Please configure DASHSCOPE_API_KEY or QWEN_API_KEY in config_private.py."
            )
        dashscope.api_key = api_key

        # Optional: redirect to a custom DashScope-compatible proxy
        base_url = os.environ.get("QWEN_BASE_URL") or get_conf("QWEN_BASE_URL")
        if base_url and base_url.strip():
            self.use_custom_endpoint = True
            self.custom_base_url = base_url.strip().rstrip("/")
            # Strip trailing /v1 — the SDK appends its own path
            if self.custom_base_url.endswith("/v1"):
                self.custom_base_url = self.custom_base_url[:-3]

    def _format_reasoning(self, reasoning_content: str, main_content: str) -> str:
        """Wrap chain-of-thought reasoning in a styled HTML block."""
        if reasoning_content:
            paragraphs = "".join(
                f'<p style="margin: 1.25em 0;">{line}</p>'
                for line in reasoning_content.split("\n")
            )
            return f'<div class="reasoning_process">{paragraphs}</div>\n\n---\n\n' + main_content
        return main_content

    def generate(self, inputs, llm_kwargs, history, system_prompt):
        """
        Yield partial response strings as the model streams its answer.

        Each yielded value is the complete accumulated text so far
        (including any reasoning block), not just the latest delta.
        """
        from dashscope import Generation

        # Clamp top_p away from exact 0 / 1 to avoid SDK validation errors
        top_p = llm_kwargs.get("top_p", 0.8)
        if top_p == 0:
            top_p += 1e-5
        if top_p == 1:
            top_p -= 1e-5

        # Strip the "dashscope-" prefix — the SDK uses the bare model name
        model_name = llm_kwargs["llm_model"]
        if model_name.startswith(_DASHSCOPE_PREFIX):
            model_name = model_name[len(_DASHSCOPE_PREFIX):]

        self.reasoning_buf = ""
        self.result_buf = ""

        call_kwargs = {
            "model": model_name,
            "messages": generate_message_payload(inputs, llm_kwargs, history, system_prompt),
            "top_p": top_p,
            "temperature": llm_kwargs.get("temperature", 1.0),
            "result_format": "message",
            "stream": True,
            "incremental_output": True,
        }

        # Inject custom base URL if configured
        if self.use_custom_endpoint:
            call_kwargs["base_http_api_url"] = self.custom_base_url

        responses = Generation.call(**call_kwargs)

        for response in responses:
            if response.status_code == HTTPStatus.OK:
                finish_reason = response.output.choices[0].finish_reason
                if finish_reason == "stop":
                    try:
                        self.result_buf += response.output.choices[0].message.content
                    except Exception:
                        pass
                    yield self._format_reasoning(self.reasoning_buf, self.result_buf)
                    break
                elif finish_reason == "length":
                    self.result_buf += "[Local Message] Output truncated due to length limit."
                    yield self._format_reasoning(self.reasoning_buf, self.result_buf)
                    break
                else:
                    # Incremental delta
                    try:
                        has_reasoning = hasattr(response.output.choices[0].message, "reasoning_content")
                    except Exception:
                        has_reasoning = False
                    if has_reasoning:
                        self.reasoning_buf += response.output.choices[0].message.reasoning_content
                    self.result_buf += response.output.choices[0].message.content
                    yield self._format_reasoning(self.reasoning_buf, self.result_buf)
            else:
                self.result_buf += (
                    f"[Local Message] Request error: status={response.status_code}, "
                    f"code={response.code}, message={response.message}"
                )
                yield self._format_reasoning(self.reasoning_buf, self.result_buf)
                break

        # Exhaust the generator to prevent SDK resource leak warnings
        while True:
            try:
                next(responses)
            except Exception:
                break

        return self.result_buf


def generate_message_payload(inputs: str, llm_kwargs: dict, history: list, system_prompt: str) -> list:
    """
    Build the messages list for a DashScope Generation call.

    The DashScope SDK does not support a dedicated system role, so the system
    prompt is injected as the first user/assistant exchange (a common workaround).
    """
    conversation_cnt = len(history) // 2
    if not system_prompt:
        system_prompt = "Hello!"

    # Inject system prompt as a priming exchange
    messages = [
        {"role": "user", "content": system_prompt},
        {"role": "assistant", "content": "Certainly!"},
    ]

    if conversation_cnt:
        for index in range(0, 2 * conversation_cnt, 2):
            user_msg = {"role": "user", "content": history[index]}
            asst_msg = {"role": "assistant", "content": history[index + 1]}
            if user_msg["content"]:
                if not asst_msg["content"] or asst_msg["content"] == timeout_bot_msg:
                    continue
                messages.append(user_msg)
                messages.append(asst_msg)
            else:
                # Empty user turn — fold assistant content into previous message
                messages[-1]["content"] = asst_msg["content"]

    messages.append({"role": "user", "content": inputs})
    return messages
