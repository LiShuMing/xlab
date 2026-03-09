"""
OpenAI-compatible model template — oai_std_model_template.py
=============================================================
Factory function ``get_predict_function`` generates a pair of
(predict_no_ui_long_connection, predict) callables for any endpoint that
follows the OpenAI streaming chat-completions API.

Typical usage (in bridge_all.py):
    noui_fn, ui_fn = get_predict_function(
        api_key_conf_name="MY_API_KEY",
        max_output_token=8192,
        disable_proxy=False,
    )
    model_info["my-model"] = {
        "fn_without_ui": noui_fn,
        "fn_with_ui": ui_fn,
        "endpoint": "https://api.example.com/v1/chat/completions",
        ...
    }
"""

import json
import time
import traceback
import requests

from loguru import logger
from toolbox import get_conf, is_the_upload_folder, update_ui, update_ui_latest_msg

proxies, TIMEOUT_SECONDS, MAX_RETRY = get_conf(
    "proxies", "TIMEOUT_SECONDS", "MAX_RETRY"
)

timeout_bot_msg = (
    "[Local Message] Request timeout. Network error. "
    "Please check proxy settings in config.py."
)


def get_full_error(chunk, stream_response):
    """Consume the rest of the stream to collect the full error payload."""
    while True:
        try:
            chunk += next(stream_response)
        except:
            break
    return chunk


def decode_chunk(chunk):
    """
    Parse a raw SSE chunk.

    Returns (response_text, reasoning_content, finish_reason, raw_decoded).
    Also extracts chain-of-thought 'reasoning_content' when supported.
    """
    chunk = chunk.decode()
    response = ""
    reasoning_content = ""
    finish_reason = "False"

    # 考虑返回类型是 text/json 和 text/event-stream 两种
    if chunk.startswith("data: "):
        chunk = chunk[6:]
    else:
        chunk = chunk
    
    try:
        chunk = json.loads(chunk)
    except:
        response = ""
        finish_reason = chunk

    # 错误处理部分
    if "error" in chunk:
        response = "API_ERROR"
        try:
            chunk = json.loads(chunk)
            finish_reason = chunk["error"]["code"]
        except:
            finish_reason = "API_ERROR"
        return response, reasoning_content, finish_reason, str(chunk)

    try:
        if chunk["choices"][0]["delta"]["content"] is not None:
            response = chunk["choices"][0]["delta"]["content"]
    except:
        pass
    try:
        if chunk["choices"][0]["delta"]["reasoning_content"] is not None:
            reasoning_content = chunk["choices"][0]["delta"]["reasoning_content"]
    except:
        pass
    try:
        finish_reason = chunk["choices"][0]["finish_reason"]
    except:
        pass
    return response, reasoning_content, finish_reason, str(chunk)


def generate_message(input, model, key, history, max_output_token, system_prompt, temperature):
    """Build HTTP headers and JSON payload for an OpenAI-compatible chat request."""
    api_key = f"Bearer {key}"

    headers = {"Content-Type": "application/json", "Authorization": api_key}

    conversation_cnt = len(history) // 2

    messages = [{"role": "system", "content": system_prompt}]
    if conversation_cnt:
        for index in range(0, 2 * conversation_cnt, 2):
            what_i_have_asked = {}
            what_i_have_asked["role"] = "user"
            what_i_have_asked["content"] = history[index]
            what_gpt_answer = {}
            what_gpt_answer["role"] = "assistant"
            what_gpt_answer["content"] = history[index + 1]
            if what_i_have_asked["content"] != "":
                if what_gpt_answer["content"] == "":
                    continue
                if what_gpt_answer["content"] == timeout_bot_msg:
                    continue
                messages.append(what_i_have_asked)
                messages.append(what_gpt_answer)
            else:
                messages[-1]["content"] = what_gpt_answer["content"]
    what_i_ask_now = {}
    what_i_ask_now["role"] = "user"
    what_i_ask_now["content"] = input
    messages.append(what_i_ask_now)
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
        "max_tokens": max_output_token,
    }

    return headers, payload


def get_predict_function(
    api_key_conf_name: str,
    max_output_token: int,
    disable_proxy: bool = False,
    model_remove_prefix: list | None = None,
):
    """
    Factory: generate (predict_no_ui_long_connection, predict) for any
    OpenAI-compatible API endpoint.

    Parameters
    ----------
    api_key_conf_name : str
        The config.py key name that holds the API key, e.g. "MY_API_KEY".
    max_output_token : int
        Maximum tokens per response (the 'max_tokens' field in the payload).
        Note: this is NOT the model's context window size.
    disable_proxy : bool
        When True, bypass the global proxy setting for this provider.
    model_remove_prefix : list | None
        If set, strip these prefixes from the model name before sending
        (e.g. ["volcengine-"] to strip routing prefixes).
    """
    if model_remove_prefix is None:
        model_remove_prefix = []

    APIKEY = get_conf(api_key_conf_name)

    def remove_prefix(model_name: str) -> str:
        """Strip routing prefixes from the model name (e.g. 'volcengine-' -> '')."""
        for prefix in model_remove_prefix:
            if model_name.startswith(prefix):
                return model_name[len(prefix):]
        return model_name

    def predict_no_ui_long_connection(
        inputs: str,
        llm_kwargs: dict,
        history: list = [],
        sys_prompt: str = "",
        observe_window: list | None = None,
        console_silence: bool = False,
    ) -> str:
        """
        Send a request and return the complete response (multi-thread safe).
        Uses streaming internally to avoid connection timeouts on long responses.
        See bridge_all.py for full parameter documentation.
        """
        from .bridge_all import model_info
        watch_dog_patience = 5  # watchdog timeout in seconds
        if len(APIKEY) == 0:
            raise RuntimeError(f"API key is empty. Check the '{api_key_conf_name}' setting in config.py.")
        if inputs == "":
            inputs = "Hello"

        headers, payload = generate_message(
            input=inputs,
            model=remove_prefix(llm_kwargs["llm_model"]),
            key=APIKEY,
            history=history,
            max_output_token=max_output_token,
            system_prompt=sys_prompt,
            temperature=llm_kwargs["temperature"],
        )

        reasoning = model_info[llm_kwargs['llm_model']].get('enable_reasoning', False)

        retry = 0
        while True:
            try:
                endpoint = model_info[llm_kwargs["llm_model"]]["endpoint"]
                response = requests.post(
                    endpoint,
                    headers=headers,
                    proxies=None if disable_proxy else proxies,
                    json=payload,
                    stream=True,
                    timeout=TIMEOUT_SECONDS,
                )
                break
            except Exception:
                retry += 1
                traceback.print_exc()
                if retry > MAX_RETRY:
                    raise TimeoutError
                if MAX_RETRY != 0:
                    logger.error(f"Request timed out, retrying ({retry}/{MAX_RETRY}) ...")

        result = ""
        finish_reason = ""
        if reasoning:
            reasoning_buffer = ""

        stream_response = response.iter_lines()
        while True:
            try:
                chunk = next(stream_response)
            except StopIteration:
                if result == "":
                    raise RuntimeError(f"Empty response received. Possible cause: {finish_reason}")
                break
            except requests.exceptions.ConnectionError:
                chunk = next(stream_response)  # retry once on transient error
            response_text, reasoning_content, finish_reason, decoded_chunk = decode_chunk(chunk)
            # First delta is typically empty — wait for content
            if response_text == "" and (not reasoning or reasoning_content == "") and finish_reason != "False":
                continue
            if response_text == "API_ERROR" and finish_reason not in ("False", "stop"):
                chunk = get_full_error(chunk, stream_response)
                chunk_decoded = chunk.decode()
                logger.error(chunk_decoded)
                raise RuntimeError(f"API error — check terminal output. Finish reason: {finish_reason}")
            if chunk:
                try:
                    if finish_reason == "stop":
                        if not console_silence:
                            print(f"[response] {result}")
                        break
                    result += response_text
                    if reasoning:
                        reasoning_buffer += reasoning_content
                    if observe_window is not None:
                        if len(observe_window) >= 1:
                            observe_window[0] += response_text  # update output buffer
                        if len(observe_window) >= 2:
                            if (time.time() - observe_window[1]) > watch_dog_patience:
                                raise RuntimeError("Request cancelled by user.")
                except Exception as e:
                    chunk = get_full_error(chunk, stream_response)
                    logger.error(chunk.decode())
                    raise RuntimeError("Unexpected JSON structure in stream response.")

        if reasoning:
            paragraphs = "".join(
                f'<p style="margin: 1.25em 0;">{line}</p>'
                for line in reasoning_buffer.split("\n")
            )
            return f'<div class="reasoning_process">{paragraphs}</div>\n\n' + result
        return result

    def predict(
        inputs: str,
        llm_kwargs: dict,
        plugin_kwargs: dict,
        chatbot,
        history: list = [],
        system_prompt: str = "",
        stream: bool = True,
        additional_fn: str | None = None,
    ):
        """
        Stream a response from the provider and update the Gradio UI.
        See bridge_all.py for full parameter documentation.
        """
        from .bridge_all import model_info
        if not APIKEY:
            raise RuntimeError(
                f"API key is empty. Check '{api_key_conf_name}' in config.py."
            )
        if inputs == "":
            inputs = "Hello"
        if additional_fn is not None:
            from core_functional import handle_core_functionality
            inputs, history = handle_core_functionality(additional_fn, inputs, history, chatbot)
        logger.info(f"[raw_input] {inputs}")
        chatbot.append((inputs, ""))
        yield from update_ui(chatbot=chatbot, history=history, msg="Waiting for response")

        if is_the_upload_folder(inputs):
            chatbot[-1] = (
                inputs,
                "[Local Message] Incorrect action! After uploading a file use a Plugin button, not Submit.",
            )
            yield from update_ui(chatbot=chatbot, history=history, msg="ok")
            time.sleep(2)

        headers, payload = generate_message(
            input=inputs,
            model=remove_prefix(llm_kwargs["llm_model"]),
            key=APIKEY,
            history=history,
            max_output_token=max_output_token,
            system_prompt=system_prompt,
            temperature=llm_kwargs["temperature"],
        )
        
        reasoning = model_info[llm_kwargs['llm_model']].get('enable_reasoning', False)

        history.append(inputs)
        history.append("")
        retry = 0
        while True:
            try:
                endpoint = model_info[llm_kwargs["llm_model"]]["endpoint"]
                response = requests.post(
                    endpoint,
                    headers=headers,
                    proxies=None if disable_proxy else proxies,
                    json=payload,
                    stream=True,
                    timeout=TIMEOUT_SECONDS,
                )
                break
            except Exception:
                retry += 1
                chatbot[-1] = (chatbot[-1][0], timeout_bot_msg)
                retry_msg = f", retrying ({retry}/{MAX_RETRY}) ..." if MAX_RETRY > 0 else ""
                yield from update_ui(chatbot=chatbot, history=history, msg="Request timed out" + retry_msg)
                if retry > MAX_RETRY:
                    raise TimeoutError

        gpt_replying_buffer = ""
        if reasoning:
            gpt_reasoning_buffer = ""

        stream_response = response.iter_lines()
        wait_counter = 0
        while True:
            try:
                chunk = next(stream_response)
            except StopIteration:
                if wait_counter != 0 and gpt_replying_buffer == "":
                    yield from update_ui_latest_msg(lastmsg="模型调用失败 ...", chatbot=chatbot, history=history, msg="failed")
                break
            except requests.exceptions.ConnectionError:
                chunk = next(stream_response)  # 失败了，重试一次？再失败就没办法了。
            response_text, reasoning_content, finish_reason, decoded_chunk = decode_chunk(chunk)
            if decoded_chunk == ": keep-alive":
                wait_counter += 1
                yield from update_ui_latest_msg(
                    lastmsg="Waiting " + "." * (wait_counter % 10),
                    chatbot=chatbot, history=history, msg="waiting ...",
                )
                continue
            # First delta is typically empty — wait for content
            if response_text == "" and (not reasoning or reasoning_content == "") and finish_reason != "False":
                status_text = f"finish_reason: {finish_reason}"
                yield from update_ui(chatbot=chatbot, history=history, msg=status_text)
                continue
            if chunk:
                try:
                    if response_text == "API_ERROR" and finish_reason not in ("False", "stop"):
                        chunk = get_full_error(chunk, stream_response)
                        chunk_decoded = chunk.decode()
                        chatbot[-1] = (
                            chatbot[-1][0],
                            f"[Local Message] API error ({finish_reason}):\n" + chunk_decoded,
                        )
                        yield from update_ui(chatbot=chatbot, history=history,
                                             msg="API error: " + chunk_decoded)
                        logger.error(chunk_decoded)
                        return

                    if finish_reason == "stop":
                        logger.info(f"[response] {gpt_replying_buffer}")
                        break
                    status_text = f"finish_reason: {finish_reason}"
                    if reasoning:
                        gpt_replying_buffer += response_text
                        gpt_reasoning_buffer += reasoning_content
                        paragraphs = "".join(
                            f'<p style="margin: 1.25em 0;">{line}</p>'
                            for line in gpt_reasoning_buffer.split("\n")
                        )
                        history[-1] = (
                            f'<div class="reasoning_process">{paragraphs}</div>\n\n---\n\n'
                            + gpt_replying_buffer
                        )
                    else:
                        gpt_replying_buffer += response_text
                        history[-1] = gpt_replying_buffer
                    chatbot[-1] = (history[-2], history[-1])
                    yield from update_ui(chatbot=chatbot, history=history, msg=status_text)
                except Exception as e:
                    yield from update_ui(chatbot=chatbot, history=history, msg="JSON parse error")
                    chunk = get_full_error(chunk, stream_response)
                    chunk_decoded = chunk.decode()
                    chatbot[-1] = (
                        chatbot[-1][0],
                        "[Local Message] Parse error:\n" + chunk_decoded,
                    )
                    yield from update_ui(chatbot=chatbot, history=history,
                                         msg="JSON error: " + chunk_decoded)
                    logger.error(chunk_decoded)
                    return

    return predict_no_ui_long_connection, predict
