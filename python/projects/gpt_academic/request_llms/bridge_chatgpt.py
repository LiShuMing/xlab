"""
OpenAI / ChatGPT bridge — bridge_chatgpt.py
============================================
Provides two functions for the OpenAI API family (GPT-3.5, GPT-4, GPT-4o,
o1/o3/o4, Azure OpenAI, api2d, one-api, vllm, openrouter …):

    predict(...)                        — streaming, single-threaded, with UI
    predict_no_ui_long_connection(...)  — multi-thread safe, no UI update
"""

import json
import os
import re
import time
import traceback
import requests
import random

from loguru import logger

# config_private.py放自己的秘密如API和代理网址
# 读取时首先看是否存在私密的config_private配置文件（不受git管控），如果有，则覆盖原config文件
from toolbox import get_conf, update_ui, is_any_api_key, select_api_key, what_keys, clip_history
from toolbox import trimmed_format_exc, is_the_upload_folder, read_one_api_model_name, log_chat
from toolbox import ChatBotWithCookies, have_any_recent_upload_image_files, encode_image
proxies, WHEN_TO_USE_PROXY, TIMEOUT_SECONDS, MAX_RETRY, API_ORG, AZURE_CFG_ARRAY = \
    get_conf('proxies', 'WHEN_TO_USE_PROXY', 'TIMEOUT_SECONDS', 'MAX_RETRY', 'API_ORG', 'AZURE_CFG_ARRAY')

if "Connect_OpenAI" not in WHEN_TO_USE_PROXY:
    if proxies is not None:
        logger.error("虽然您配置了代理设置，但不会在连接OpenAI的过程中起作用，请检查WHEN_TO_USE_PROXY配置。")
        proxies = None

timeout_bot_msg = '[Local Message] Request timeout. Network error. Please check proxy settings in config.py.' + \
                  '网络错误，检查代理服务器是否可用，以及代理设置的格式是否正确，格式须是[协议]://[地址]:[端口]，缺一不可。'

def get_full_error(chunk, stream_response):
    """Consume the rest of the stream to get the full error message."""
    while True:
        try:
            chunk += next(stream_response)
        except:
            break
    return chunk

def make_multimodal_input(inputs, image_paths):
    image_base64_array = []
    for image_path in image_paths:
        path = os.path.abspath(image_path)
        base64 = encode_image(path)
        inputs = inputs + f'<br/><br/><div align="center"><img src="file={path}" base64="{base64}"></div>'
        image_base64_array.append(base64)
    return inputs, image_base64_array

def reverse_base64_from_input(inputs):
    # 定义一个正则表达式来匹配 Base64 字符串（假设格式为 base64="<Base64编码>"）
    # pattern = re.compile(r'base64="([^"]+)"></div>')
    pattern = re.compile(r'<br/><br/><div align="center"><img[^<>]+base64="([^"]+)"></div>')
    # 使用 findall 方法查找所有匹配的 Base64 字符串
    base64_strings = pattern.findall(inputs)
    # 返回反转后的 Base64 字符串列表
    return base64_strings

def contain_base64(inputs):
    base64_strings = reverse_base64_from_input(inputs)
    return len(base64_strings) > 0

def append_image_if_contain_base64(inputs):
    if not contain_base64(inputs):
        return inputs
    else:
        image_base64_array = reverse_base64_from_input(inputs)
        pattern = re.compile(r'<br/><br/><div align="center"><img[^><]+></div>')
        inputs = re.sub(pattern, '', inputs)
        res = []
        res.append({
            "type": "text",
            "text": inputs
        })
        for image_base64 in image_base64_array:
            res.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64}"
                }
            })
        return res

def remove_image_if_contain_base64(inputs):
    if not contain_base64(inputs):
        return inputs
    else:
        pattern = re.compile(r'<br/><br/><div align="center"><img[^><]+></div>')
        inputs = re.sub(pattern, '', inputs)
        return inputs

def decode_chunk(chunk):
    # 提前读取一些信息 （用于判断异常）
    chunk_decoded = chunk.decode()
    chunkjson = None
    has_choices = False
    choice_valid = False
    has_content = False
    has_role = False
    try:
        chunkjson = json.loads(chunk_decoded[6:])
        has_choices = 'choices' in chunkjson
        if has_choices: choice_valid = (len(chunkjson['choices']) > 0)
        if has_choices and choice_valid: has_content = ("content" in chunkjson['choices'][0]["delta"])
        if has_content: has_content = (chunkjson['choices'][0]["delta"]["content"] is not None)
        if has_choices and choice_valid: has_role = "role" in chunkjson['choices'][0]["delta"]
    except:
        pass
    return chunk_decoded, chunkjson, has_choices, choice_valid, has_content, has_role

from functools import lru_cache
@lru_cache(maxsize=32)
def verify_endpoint(endpoint):
    """
        检查endpoint是否可用
    """
    if "你亲手写的api名称" in endpoint:
        raise ValueError("Endpoint不正确, 请检查AZURE_ENDPOINT的配置! 当前的Endpoint为:" + endpoint)
    return endpoint

def predict_no_ui_long_connection(inputs: str, llm_kwargs: dict, history: list = [], sys_prompt: str = "",
                                  observe_window: list | None = None, console_silence: bool = False) -> str:
    """
    Send a request to the OpenAI API and wait for the full response.
    Uses streaming internally to avoid connection timeouts on long responses.

    Parameters
    ----------
    inputs : str
        The user's input for this turn.
    sys_prompt : str
        System instruction prepended to every request.
    llm_kwargs : dict
        LLM parameters (model name, temperature, api_key, …).
    history : list
        Alternating [user, assistant, …] conversation history.
    observe_window : list | None
        [output_buffer, watchdog_timestamp] for cross-thread progress streaming.
    console_silence : bool
        Suppress per-token stdout output when True.
    """
    from request_llms.bridge_all import model_info

    watch_dog_patience = 5  # watchdog patience in seconds

    if model_info[llm_kwargs['llm_model']].get('openai_disable_stream', False):
        stream = False
    else:
        stream = True

    headers, payload = generate_payload(inputs, llm_kwargs, history, system_prompt=sys_prompt, stream=stream)
    retry = 0
    while True:
        try:
            endpoint = verify_endpoint(model_info[llm_kwargs['llm_model']]['endpoint'])
            response = requests.post(endpoint, headers=headers, proxies=proxies,
                                     json=payload, stream=stream, timeout=TIMEOUT_SECONDS)
            break
        except requests.exceptions.ReadTimeout:
            retry += 1
            traceback.print_exc()
            if retry > MAX_RETRY:
                raise TimeoutError
            if MAX_RETRY != 0:
                logger.error(f"Request timed out, retrying ({retry}/{MAX_RETRY}) ...")

    if not stream:
        # Non-streaming path: only used for o-series models that disable streaming
        chunkjson = json.loads(response.content.decode())
        gpt_replying_buffer = chunkjson['choices'][0]["message"]["content"]
        return gpt_replying_buffer

    stream_response = response.iter_lines()
    result = ''
    json_data = None
    while True:
        try:
            chunk = next(stream_response)
        except StopIteration:
            break
        except requests.exceptions.ConnectionError:
            chunk = next(stream_response)  # retry once on connection error
        chunk_decoded, chunkjson, has_choices, choice_valid, has_content, has_role = decode_chunk(chunk)
        if len(chunk_decoded) == 0:
            continue
        if not chunk_decoded.startswith('data:'):
            error_msg = get_full_error(chunk, stream_response).decode()
            if "reduce the length" in error_msg:
                raise ConnectionAbortedError("OpenAI rejected the request: " + error_msg)
            elif 'type":"upstream_error","param":"307"' in error_msg:
                raise ConnectionAbortedError(
                    "Response truncated due to token limit. Please reduce input length."
                )
            else:
                raise RuntimeError("OpenAI rejected the request: " + error_msg)
        if 'data: [DONE]' in chunk_decoded:
            break  # normal termination for api2d / one-api
        if has_choices and not choice_valid:
            continue  # some non-standard third-party APIs emit this
        json_data = chunkjson['choices'][0]
        delta = json_data["delta"]

        if len(delta) == 0:
            is_termination_certain = (
                has_choices and chunkjson['choices'][0].get('finish_reason', 'null') == 'stop'
            )
            if is_termination_certain:
                break
            else:
                continue  # non-standard endpoint — keep reading

        if (not has_content) and has_role:
            continue
        if (not has_content) and (not has_role):
            continue
        if has_content:
            result += delta["content"]
            if not console_silence:
                print(delta["content"], end='')
            if observe_window is not None:
                if len(observe_window) >= 1:
                    observe_window[0] += delta["content"]  # update output buffer
                if len(observe_window) >= 2:
                    if (time.time() - observe_window[1]) > watch_dog_patience:
                        raise RuntimeError("Request cancelled by user.")
        else:
            raise RuntimeError("Unexpected JSON delta structure: " + str(delta))

    finish_reason = json_data.get('finish_reason', None) if json_data else None
    if finish_reason == 'content_filter':
        raise RuntimeError("由于提问含不合规内容被过滤。")
    if finish_reason == 'length':
        raise ConnectionAbortedError("正常结束，但显示Token不足，导致输出不完整，请削减单次输入的文本量。")

    return result


def predict(inputs: str, llm_kwargs: dict, plugin_kwargs: dict, chatbot: ChatBotWithCookies,
            history: list = [], system_prompt: str = '', stream: bool = True,
            additional_fn: str | None = None):
    """
    Stream a response from the OpenAI API and update the Gradio UI in real time.

    Parameters
    ----------
    inputs : str
        User input for this turn.
    llm_kwargs : dict
        LLM parameters (model, temperature, api_key, …).
    plugin_kwargs : dict
        Extra parameters forwarded from plugin advanced dialogs.
    chatbot : ChatBotWithCookies
        Gradio chatbot handle — yield updates to refresh the UI.
    history : list
        Alternating [user, assistant, …] conversation history.
    system_prompt : str
        System instruction prepended to every request.
    stream : bool
        Deprecated — kept for API compatibility.
    additional_fn : str | None
        Name of the core-function button that was clicked.
    """
    from request_llms.bridge_all import model_info
    if is_any_api_key(inputs):
        # Input looks like an API key — store it in session cookies
        chatbot._cookies['api_key'] = inputs
        chatbot.append(("Input recognised as an OpenAI API key.", what_keys(inputs)))
        yield from update_ui(chatbot=chatbot, history=history, msg="api_key imported")
        return
    elif not is_any_api_key(chatbot._cookies['api_key']):
        chatbot.append((inputs,
            "Missing API key.\n\n"
            "1. Quick fix: type the API key directly into the input box and press Enter.\n\n"
            "2. Permanent fix: set API_KEY in config.py or config_private.py."))
        yield from update_ui(chatbot=chatbot, history=history, msg="missing api_key")
        return

    user_input = inputs
    if additional_fn is not None:
        from core_functional import handle_core_functionality
        inputs, history = handle_core_functionality(additional_fn, inputs, history, chatbot)

    # Multimodal: attach recent uploaded images when the model supports it
    has_multimodal_capacity = model_info[llm_kwargs['llm_model']].get('has_multimodal_capacity', False)
    if has_multimodal_capacity:
        has_recent_image_upload, image_paths = have_any_recent_upload_image_files(chatbot, pop=True)
    else:
        has_recent_image_upload, image_paths = False, []
    if has_recent_image_upload:
        _inputs, image_base64_array = make_multimodal_input(inputs, image_paths)
    else:
        _inputs, image_base64_array = inputs, []
    chatbot.append((_inputs, ""))
    yield from update_ui(chatbot=chatbot, history=history, msg="Waiting for response")

    # Some o-series models do not support streaming
    if model_info[llm_kwargs['llm_model']].get('openai_disable_stream', False):
        stream = False
    else:
        stream = True

    # Guard against users accidentally clicking submit after uploading a file
    if is_the_upload_folder(user_input):
        chatbot[-1] = (inputs,
            "[Local Message] Incorrect action detected! "
            "After uploading a file please click a button in the **Plugin** panel, "
            "not the Submit button.")
        yield from update_ui(chatbot=chatbot, history=history, msg="ok")
        time.sleep(2)

    try:
        headers, payload = generate_payload(inputs, llm_kwargs, history, system_prompt,
                                            image_base64_array, has_multimodal_capacity, stream)
    except RuntimeError:
        chatbot[-1] = (inputs,
            f"The provided API key is not valid for model '{llm_kwargs['llm_model']}'. "
            "You may have selected the wrong model or API source.")
        yield from update_ui(chatbot=chatbot, history=history, msg="invalid api-key")
        return

    # Validate the endpoint URL
    try:
        endpoint = verify_endpoint(model_info[llm_kwargs['llm_model']]['endpoint'])
    except Exception:
        tb_str = '```\n' + trimmed_format_exc() + '```'
        chatbot[-1] = (inputs, tb_str)
        yield from update_ui(chatbot=chatbot, history=history, msg="invalid endpoint")
        return

    # Append current turn to history before streaming starts
    if has_recent_image_upload:
        history.extend([_inputs, ""])
    else:
        history.extend([inputs, ""])

    retry = 0
    previous_ui_reflesh_time = 0
    ui_reflesh_min_interval = 0.0
    while True:
        try:
            response = requests.post(endpoint, headers=headers, proxies=proxies,
                                     json=payload, stream=stream, timeout=TIMEOUT_SECONDS)
            break
        except Exception:
            retry += 1
            chatbot[-1] = (chatbot[-1][0], timeout_bot_msg)
            retry_msg = f", retrying ({retry}/{MAX_RETRY}) ..." if MAX_RETRY > 0 else ""
            yield from update_ui(chatbot=chatbot, history=history, msg="Request timed out" + retry_msg)
            if retry > MAX_RETRY:
                raise TimeoutError

    if not stream:
        # Non-streaming path for o-series models
        yield from handle_o1_model_special(response, inputs, llm_kwargs, chatbot, history)
        return

    if stream:
        reach_termination = False   # handle some non-standard third-party API quirks
        gpt_replying_buffer = ""
        is_head_of_the_stream = True
        stream_response = response.iter_lines()
        while True:
            try:
                chunk = next(stream_response)
            except StopIteration:
                # Some non-official endpoints don't send [DONE]; handle gracefully
                chunk_decoded = chunk.decode()
                error_msg = chunk_decoded
                if len(gpt_replying_buffer.strip()) > 0 and len(error_msg) == 0:
                    # Defective endpoint: stream ended without [DONE] — treat as success
                    yield from update_ui(chatbot=chatbot, history=history,
                                         msg="Detected a defective endpoint. Consider switching to a more stable one.")
                    if not reach_termination:
                        reach_termination = True
                        log_chat(llm_model=llm_kwargs["llm_model"], input_str=inputs, output_str=gpt_replying_buffer)
                    break
                chatbot, history = handle_error(inputs, llm_kwargs, chatbot, history, chunk_decoded, error_msg)
                yield from update_ui(chatbot=chatbot, history=history, msg="API error: " + chunk.decode())
                return

            chunk_decoded, chunkjson, has_choices, choice_valid, has_content, has_role = decode_chunk(chunk)

            if is_head_of_the_stream and ('"object":"error"' not in chunk_decoded) and ("content" not in chunk_decoded):
                # First frame of the stream typically has no content delta
                is_head_of_the_stream = False
                continue

            if "error" in chunk_decoded:
                logger.error(f"Unknown API error: {chunk_decoded}")

            if chunk:
                try:
                    if has_choices and not choice_valid:
                        continue  # non-standard endpoint quirk
                    if ('data: [DONE]' not in chunk_decoded) and len(chunk_decoded) > 0 and (chunkjson is None):
                        raise ValueError(f"Cannot parse the following data, check your config:\n\n{chunk_decoded}")
                    # Termination checks: api2d/one-api use [DONE], OpenAI uses empty delta
                    one_api_terminate = ('data: [DONE]' in chunk_decoded)
                    openai_terminate = has_choices and len(chunkjson['choices'][0]["delta"]) == 0
                    if one_api_terminate or openai_terminate:
                        is_termination_certain = one_api_terminate or (
                            has_choices and chunkjson['choices'][0].get('finish_reason', 'null') == 'stop'
                        )
                        if is_termination_certain:
                            reach_termination = True
                            log_chat(llm_model=llm_kwargs["llm_model"], input_str=inputs, output_str=gpt_replying_buffer)
                            break
                        else:
                            continue  # non-standard endpoint — keep reading
                    try:
                        status_text = f"finish_reason: {chunkjson['choices'][0].get('finish_reason', 'null')}"
                    except Exception:
                        logger.error(f"Third-party API returned unexpected structure: {chunk_decoded}")
                        status_text = "streaming"
                    # Process the content delta
                    if has_content:
                        gpt_replying_buffer += chunkjson['choices'][0]["delta"]["content"]
                    elif has_role:
                        continue  # role-only delta — skip
                    else:
                        if chunkjson['choices'][0]["delta"].get("content", None) is None:
                            logger.error(f"Non-standard delta, skipping: {chunk_decoded}")
                            continue
                        gpt_replying_buffer += chunkjson['choices'][0]["delta"]["content"]

                    history[-1] = gpt_replying_buffer
                    chatbot[-1] = (history[-2], history[-1])
                    if time.time() - previous_ui_reflesh_time > ui_reflesh_min_interval:
                        yield from update_ui(chatbot=chatbot, history=history, msg=status_text)
                        previous_ui_reflesh_time = time.time()
                except Exception as e:
                    yield from update_ui(chatbot=chatbot, history=history, msg="JSON parse error")
                    chunk = get_full_error(chunk, stream_response)
                    chunk_decoded = chunk.decode()
                    error_msg = chunk_decoded
                    chatbot, history = handle_error(inputs, llm_kwargs, chatbot, history, chunk_decoded, error_msg)
                    logger.error(error_msg)
                    yield from update_ui(chatbot=chatbot, history=history, msg="JSON error: " + error_msg)
                    return
        yield from update_ui(chatbot=chatbot, history=history, msg="Done")
        return  # end of streaming branch

def handle_o1_model_special(response, inputs, llm_kwargs, chatbot, history):
    try:
        chunkjson = json.loads(response.content.decode())
        gpt_replying_buffer = chunkjson['choices'][0]["message"]["content"]
        log_chat(llm_model=llm_kwargs["llm_model"], input_str=inputs, output_str=gpt_replying_buffer)
        history[-1] = gpt_replying_buffer
        chatbot[-1] = (history[-2], history[-1])
        yield from update_ui(chatbot=chatbot, history=history) # 刷新界面
    except Exception as e:
        yield from update_ui(chatbot=chatbot, history=history, msg="Json解析异常" + response.text) # 刷新界面

def handle_error(inputs, llm_kwargs, chatbot, history, chunk_decoded, error_msg):
    """Map common API error strings to user-friendly messages."""
    from request_llms.bridge_all import model_info
    openai_portal = " Check https://platform.openai.com/account/usage for details."
    if "reduce the length" in error_msg:
        if len(history) >= 2:
            history[-1] = ""
            history[-2] = ""
        history = clip_history(inputs=inputs, history=history,
                               tokenizer=model_info[llm_kwargs['llm_model']]['tokenizer'],
                               max_token_limit=model_info[llm_kwargs['llm_model']]['max_token'])
        chatbot[-1] = (chatbot[-1][0],
            "[Local Message] Input too long. History has been trimmed. Please try again.")
    elif "does not exist" in error_msg:
        chatbot[-1] = (chatbot[-1][0],
            f"[Local Message] Model '{llm_kwargs['llm_model']}' does not exist or you lack access.")
    elif "Incorrect API key" in error_msg:
        chatbot[-1] = (chatbot[-1][0],
            "[Local Message] Incorrect API key." + openai_portal)
    elif "exceeded your current quota" in error_msg:
        chatbot[-1] = (chatbot[-1][0],
            "[Local Message] Quota exceeded." + openai_portal)
    elif "account is not active" in error_msg or "associated with a deactivated account" in error_msg:
        chatbot[-1] = (chatbot[-1][0],
            "[Local Message] Account is deactivated." + openai_portal)
    elif "API key has been deactivated" in error_msg:
        chatbot[-1] = (chatbot[-1][0],
            "[Local Message] API key has been deactivated." + openai_portal)
    elif "bad forward key" in error_msg:
        chatbot[-1] = (chatbot[-1][0], "[Local Message] Bad forward key. API2D balance may be empty.")
    elif "Not enough point" in error_msg:
        chatbot[-1] = (chatbot[-1][0], "[Local Message] Not enough API2D points.")
    else:
        from toolbox import regular_txt_to_markdown
        tb_str = '```\n' + trimmed_format_exc() + '```'
        chatbot[-1] = (chatbot[-1][0], f"[Local Message] Error\n\n{tb_str}\n\n{regular_txt_to_markdown(chunk_decoded)}")
    return chatbot, history

def generate_payload(inputs: str, llm_kwargs: dict, history: list, system_prompt: str,
                     image_base64_array: list | None = None, has_multimodal_capacity: bool = False,
                     stream: bool = True):
    """
    Build the HTTP request headers and JSON payload for an OpenAI API call.

    Handles system prompt formatting, message history, multimodal image
    embedding, model name normalisation (api2d/one-api/vllm prefixes), and
    o-series temperature overrides.
    """
    if image_base64_array is None:
        image_base64_array = []
    from request_llms.bridge_all import model_info

    if not is_any_api_key(llm_kwargs['api_key']):
        raise AssertionError(
            "Invalid API key.\n\n"
            "1. Quick fix: type your API key into the input box and press Enter.\n\n"
            "2. Permanent fix: set API_KEY in config.py or config_private.py."
        )

    if llm_kwargs['llm_model'].startswith('vllm-'):
        api_key = 'no-api-key'
    else:
        api_key = select_api_key(llm_kwargs['api_key'], llm_kwargs['llm_model'])

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    if API_ORG.startswith('org-'): headers.update({"OpenAI-Organization": API_ORG})
    if llm_kwargs['llm_model'].startswith('azure-'):
        headers.update({"api-key": api_key})
        if llm_kwargs['llm_model'] in AZURE_CFG_ARRAY.keys():
            azure_api_key_unshared = AZURE_CFG_ARRAY[llm_kwargs['llm_model']]["AZURE_API_KEY"]
            headers.update({"api-key": azure_api_key_unshared})

    if has_multimodal_capacity:
        # Enable multimodal mode when the model supports it AND images are present
        # (either in the current input or in previous history turns)
        enable_multimodal_capacity = (len(image_base64_array) > 0) or any(contain_base64(h) for h in history)
    else:
        enable_multimodal_capacity = False

    conversation_cnt = len(history) // 2
    openai_disable_system_prompt = model_info[llm_kwargs['llm_model']].get('openai_disable_system_prompt', False)

    # o-series models do not support the "system" role; inject as first user message instead
    if openai_disable_system_prompt:
        messages = [{"role": "user", "content": system_prompt}]
    else:
        messages = [{"role": "system", "content": system_prompt}]

    if not enable_multimodal_capacity:
        # Text-only path
        if conversation_cnt:
            for index in range(0, 2*conversation_cnt, 2):
                what_i_have_asked = {}
                what_i_have_asked["role"] = "user"
                what_i_have_asked["content"] = remove_image_if_contain_base64(history[index])
                what_gpt_answer = {}
                what_gpt_answer["role"] = "assistant"
                what_gpt_answer["content"] = remove_image_if_contain_base64(history[index+1])
                if what_i_have_asked["content"] != "":
                    if what_gpt_answer["content"] == "": continue
                    if what_gpt_answer["content"] == timeout_bot_msg: continue
                    messages.append(what_i_have_asked)
                    messages.append(what_gpt_answer)
                else:
                    messages[-1]['content'] = what_gpt_answer['content']
        what_i_ask_now = {}
        what_i_ask_now["role"] = "user"
        what_i_ask_now["content"] = inputs
        messages.append(what_i_ask_now)
    else:
        # Multimodal path — embed base64 images in content arrays
        if conversation_cnt:
            for index in range(0, 2*conversation_cnt, 2):
                what_i_have_asked = {}
                what_i_have_asked["role"] = "user"
                what_i_have_asked["content"] = append_image_if_contain_base64(history[index])
                what_gpt_answer = {}
                what_gpt_answer["role"] = "assistant"
                what_gpt_answer["content"] = append_image_if_contain_base64(history[index+1])
                if what_i_have_asked["content"] != "":
                    if what_gpt_answer["content"] == "": continue
                    if what_gpt_answer["content"] == timeout_bot_msg: continue
                    messages.append(what_i_have_asked)
                    messages.append(what_gpt_answer)
                else:
                    messages[-1]['content'] = what_gpt_answer['content']
        what_i_ask_now = {}
        what_i_ask_now["role"] = "user"
        what_i_ask_now["content"] = []
        what_i_ask_now["content"].append({
            "type": "text",
            "text": inputs
        })
        for image_base64 in image_base64_array:
            what_i_ask_now["content"].append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64}"
                }
            })
        messages.append(what_i_ask_now)


    model = llm_kwargs['llm_model']
    if llm_kwargs['llm_model'].startswith('api2d-'):
        model = llm_kwargs['llm_model'][len('api2d-'):]
    if llm_kwargs['llm_model'].startswith('one-api-'):
        model = llm_kwargs['llm_model'][len('one-api-'):]
        model, _ = read_one_api_model_name(model)
    if llm_kwargs['llm_model'].startswith('vllm-'):
        model = llm_kwargs['llm_model'][len('vllm-'):]
        model, _ = read_one_api_model_name(model)
    if model == "gpt-3.5-random":  # randomly pick a variant to spread rate-limit load
        model = random.choice([
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k",
            "gpt-3.5-turbo-1106",
            "gpt-3.5-turbo-0613",
            "gpt-3.5-turbo-16k-0613",
            "gpt-3.5-turbo-0301",
        ])

    payload = {
        "model": model,
        "messages": messages,
        "temperature": llm_kwargs['temperature'],  # 1.0,
        "top_p": llm_kwargs['top_p'],  # 1.0,
        "n": 1,
        "stream": stream,
    }
    openai_force_temperature_one = model_info[llm_kwargs['llm_model']].get('openai_force_temperature_one', False)
    if openai_force_temperature_one:
        payload.pop('temperature')  # o-series models require temperature=1 (default); do not send it
    return headers, payload

