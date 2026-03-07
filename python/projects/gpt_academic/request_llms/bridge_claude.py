# 借鉴了 https://github.com/GaiZhenbiao/ChuanhuChatGPT 项目
# 使用 Anthropic SDK 重写

"""
    该文件中主要包含2个函数

    不具备多线程能力的函数：
    1. predict: 正常对话时使用，具备完备的交互功能，不可多线程

    具备多线程调用能力的函数
    2. predict_no_ui_long_connection：支持多线程
"""
import os
import time
import traceback
from typing import List, Optional, Generator, Any, Dict
from loguru import logger
from toolbox import get_conf, update_ui, trimmed_format_exc, encode_image, every_image_file_in_path, log_chat

try:
    from anthropic import Anthropic, AnthropicError
    from anthropic.types import TextBlock
    # MessageParam might not be in all versions, use dict as type hint
    HAS_MESSAGE_PARAM = True
except ImportError as e:
    logger.error(f"[Claude] Anthropic SDK import failed: {e}")
    logger.error("[Claude] Please install the Anthropic SDK: pip install anthropic>=0.18.1")
    raise ImportError("Anthropic SDK is required for Claude integration")

picture_system_prompt = "\n当回复图像时,必须说明正在回复哪张图像。所有图像仅在最后一个问题中提供,即使它们在历史记录中被提及。请使用'这是第X张图像:'的格式来指明您正在描述的是哪张图像。"
Claude_3_Models = ["claude-3-haiku-20240307", "claude-3-sonnet-20240229", "claude-3-opus-20240229", "claude-3-5-sonnet-20240620", "claude-3-5-sonnet-20241022", "claude-3-haiku-20241022"]

# config_private.py放自己的秘密如API和代理网址
# 读取时首先看是否存在私密的config_private配置文件（不受git管控），如果有，则覆盖原config文件
from toolbox import get_conf, update_ui, trimmed_format_exc, ProxyNetworkActivate
proxies, TIMEOUT_SECONDS, MAX_RETRY, ANTHROPIC_API_KEY = \
    get_conf('proxies', 'TIMEOUT_SECONDS', 'MAX_RETRY', 'ANTHROPIC_API_KEY')

timeout_bot_msg = '[Local Message] Request timeout. Network error. Please check proxy settings in config.py.' + \
                  '网络错误，检查代理服务器是否可用，以及代理设置的格式是否正确，格式须是[协议]://[地址]:[端口]，缺一不可。'


def _get_client() -> Anthropic:
    """
    获取 Anthropic 客户端实例
    """
    return Anthropic(
        api_key=ANTHROPIC_API_KEY,
        timeout=TIMEOUT_SECONDS,
    )


def _build_messages(history: List[str], inputs: str, image_paths: Optional[List[str]] = None) -> List[dict]:
    """
    构建消息列表，用于发送给 API

    Args:
        history: 对话历史列表，交替包含用户和助手的消息
        inputs: 当前用户输入
        image_paths: 可选的图片路径列表

    Returns:
        格式化后的消息列表
    """
    conversation_cnt = len(history) // 2
    messages: List[Dict[str, Any]] = []

    if conversation_cnt:
        for index in range(0, 2 * conversation_cnt, 2):
            user_content = history[index]
            assistant_content = history[index + 1]

            if user_content and user_content != timeout_bot_msg:
                messages.append({
                    "role": "user",
                    "content": user_content
                })
                if assistant_content:
                    messages.append({
                        "role": "assistant",
                        "content": assistant_content
                    })
            else:
                # 如果用户消息为空，替换最后一条助手消息的内容
                if messages and assistant_content:
                    if isinstance(messages[-1]["content"], list):
                        # 如果是列表格式（包含图片），只替换文本部分
                        text_parts = [c["text"] for c in messages[-1]["content"] if c.get("type") == "text"]
                        if text_parts:
                            messages[-1]["content"] = assistant_content
                    elif isinstance(messages[-1]["content"], str):
                        messages[-1]["content"] = assistant_content

    # 添加当前用户消息
    if image_paths:
        current_content: List[Any] = []
        for image_path in image_paths:
            current_content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": _get_image_media_type(image_path),
                    "data": encode_image(image_path),
                }
            })
        current_content.append({"type": "text", "text": inputs})
        messages.append({
            "role": "user",
            "content": current_content
        })
    else:
        messages.append({
            "role": "user",
            "content": inputs
        })

    return messages


def _get_image_media_type(image_path: str) -> str:
    """
    根据图片扩展名返回对应的 MIME 类型
    """
    if image_path.endswith('.jpeg') or image_path.endswith('.jpg'):
        return 'image/jpeg'
    elif image_path.endswith('.png'):
        return 'image/png'
    elif image_path.endswith('.gif'):
        return 'image/gif'
    elif image_path.endswith('.webp'):
        return 'image/webp'
    return 'image/jpeg'


def predict_no_ui_long_connection(inputs: str, llm_kwargs: dict, history: list = [],
                                  sys_prompt: str = "", observe_window: list = None,
                                  console_silence: bool = False) -> str:
    """
    发送至 Claude，等待回复，一次性完成，不显示中间过程。但内部用 stream 的方法避免中途网线被掐。

    Args:
        inputs: 本次问询的输入
        llm_kwargs: Claude 的内部调优参数
        history: 之前的对话列表
        sys_prompt: 系统静默 prompt
        observe_window: 用于跨越线程传递已经输出的部分
        console_silence: 是否静默控制台输出

    Returns:
        模型回复的完整文本
    """
    watch_dog_patience = 5  # 看门狗的耐心, 设置5秒即可

    if len(ANTHROPIC_API_KEY) == 0:
        raise RuntimeError("没有设置 ANTHROPIC_API_KEY 选项")

    if inputs == "":
        inputs = "空空如也的输入栏"

    # 检查是否为 Claude 3 模型且有图片
    llm_model = llm_kwargs.get('llm_model', '')
    image_paths = llm_kwargs.get('image_paths', None)
    if image_paths is None:
        image_paths = []

    has_image_support = any([llm_model == model for model in Claude_3_Models])
    if has_image_support and image_paths:
        # 暂时不支持图片的多线程调用
        pass

    # 构建消息
    messages = _build_messages(history, inputs, image_paths if has_image_support else None)

    retry = 0
    client = _get_client()

    while True:
        try:
            response = client.messages.create(
                model=llm_model,
                max_tokens=llm_kwargs.get('max_tokens', 4096),
                messages=messages,
                system=sys_prompt,
                temperature=llm_kwargs.get('temperature', 0.7),
                stream=False,  # 非流式获取完整响应
            )
            break
        except AnthropicError as e:
            retry += 1
            logger.error(f"[Claude] API 请求失败: {e}")
            traceback.print_exc()
            if retry > MAX_RETRY:
                raise TimeoutError(f"请求超时，已重试 {MAX_RETRY} 次")
            if MAX_RETRY != 0:
                logger.error(f'请求超时，正在重试 ({retry}/{MAX_RETRY}) ……')
            time.sleep(1)

    # 提取响应文本
    result = ""
    if response.content:
        for block in response.content:
            if isinstance(block, TextBlock):
                result += block.text

    return result


def make_media_input(history: list, inputs: str, image_paths: List[str]) -> str:
    """
    构建包含图片的输入 HTML
    """
    for image_path in image_paths:
        inputs = inputs + f'<br/><br/><div align="center"><img src="file={os.path.abspath(image_path)}"></div>'
    return inputs


def predict(inputs: str, llm_kwargs: dict, plugin_kwargs: dict, chatbot: list,
            history: list = [], system_prompt: str = "", stream: bool = True,
            additional_fn: any = None) -> Generator[list, None, None]:
    """
    发送至 Claude，流式获取输出。
    用于基础的对话功能。

    Args:
        inputs: 本次问询的输入
        llm_kwargs: Claude 的内部调优参数（包含 model, temperature 等）
        plugin_kwargs: 插件参数
        chatbot: WebUI 中显示的对话列表
        history: 之前的对话列表
        system_prompt: 系统提示词
        stream: 是否使用流式输出
        additional_fn: 点击的按钮功能

    Yields:
        更新后的 chatbot 和 history
    """
    watch_dog_patience = 5  # 看门狗的耐心, 设置5秒即可
    logger.info(f"[Claude] predict called, model={llm_kwargs.get('llm_model')}, api_key set={len(ANTHROPIC_API_KEY) > 0}")

    if inputs == "":
        inputs = "空空如也的输入栏"

    if len(ANTHROPIC_API_KEY) == 0:
        chatbot.append((inputs, "没有设置 ANTHROPIC_API_KEY"))
        yield from update_ui(chatbot=chatbot, history=history, msg="等待响应")
        return

    # 处理额外的功能函数
    if additional_fn is not None:
        from core_functional import handle_core_functionality
        inputs, history = handle_core_functionality(additional_fn, inputs, history, chatbot)

    # 检查是否有图片
    have_recent_file, image_paths = every_image_file_in_path(chatbot)
    if len(image_paths) > 20:
        chatbot.append((inputs, "图片数量超过 api 上限(20张)"))
        yield from update_ui(chatbot=chatbot, history=history, msg="等待响应")
        return

    llm_model = llm_kwargs.get('llm_model', '')
    has_image_support = any([llm_model == model for model in Claude_3_Models])

    # 准备消息内容
    if has_image_support and have_recent_file:
        if inputs == "" or inputs == "空空如也的输入栏":
            inputs = "请描述给出的图片"
        system_prompt += picture_system_prompt
        chatbot.append((make_media_input(history, inputs, image_paths), ""))
        yield from update_ui(chatbot=chatbot, history=history, msg="等待响应")
    else:
        chatbot.append((inputs, ""))
        yield from update_ui(chatbot=chatbot, history=history, msg="等待响应")

    # 构建消息
    messages = _build_messages(history, inputs, image_paths if (has_image_support and have_recent_file) else None)

    history.append(inputs)
    history.append("")

    retry = 0
    client = _get_client()
    gpt_replying_buffer = ""

    logger.info(f"[Claude] 开始调用 API, model={llm_model}, messages_count={len(messages)}")

    while True:
        try:
            if stream:
                # 流式调用
                with client.messages.stream(
                    model=llm_model,
                    max_tokens=llm_kwargs.get('max_tokens', 4096),
                    messages=messages,
                    system=system_prompt,
                    temperature=llm_kwargs.get('temperature', 0.7),
                ) as stream_response:
                    for event in stream_response:
                        # 处理流式事件
                        if event.type == "content_block_delta" and event.delta.type == "text_delta":
                            text = event.delta.text
                            if text:
                                gpt_replying_buffer += text
                                history[-1] = gpt_replying_buffer
                                chatbot[-1] = (history[-2], history[-1])
                                yield from update_ui(chatbot=chatbot, history=history, msg='正常')

                        # 检查看门狗
                        if observe_window := llm_kwargs.get('observe_window'):
                            if len(observe_window) >= 2:
                                if (time.time() - observe_window[1]) > watch_dog_patience:
                                    raise RuntimeError("用户取消了程序。")

                # 流结束
                logger.info(f"[Claude] 流结束, response_len={len(gpt_replying_buffer)}")
                break
            else:
                # 非流式调用
                response = client.messages.create(
                    model=llm_model,
                    max_tokens=llm_kwargs.get('max_tokens', 4096),
                    messages=messages,
                    system=system_prompt,
                    temperature=llm_kwargs.get('temperature', 0.7),
                )
                if response.content:
                    for block in response.content:
                        if isinstance(block, TextBlock):
                            gpt_replying_buffer += block.text
                break

        except AnthropicError as e:
            retry += 1
            logger.error(f"[Claude] API 请求失败: {e}")
            traceback.print_exc()
            if retry > MAX_RETRY:
                chatbot[-1] = (inputs, f"请求失败，已重试 {MAX_RETRY} 次。错误: {str(e)}")
                yield from update_ui(chatbot=chatbot, history=history, msg='错误')
                return
            if MAX_RETRY != 0:
                logger.error(f'请求超时，正在重试 ({retry}/{MAX_RETRY}) ……')
            time.sleep(1)

    # 记录对话日志
    if gpt_replying_buffer:
        log_chat(llm_model=llm_model, input_str=inputs, output_str=gpt_replying_buffer)

    # 最终更新 UI
    if gpt_replying_buffer:
        history[-1] = gpt_replying_buffer
        chatbot[-1] = (history[-2], history[-1])
        logger.info(f"[Claude] 最终刷新 UI, response_len={len(gpt_replying_buffer)}")
        yield from update_ui(chatbot=chatbot, history=history, msg='完成')
        # 再 yield 一次确保刷新
        yield from update_ui(chatbot=chatbot, history=history, msg='完成')
    else:
        logger.warning(f"[Claude] 警告: gpt_replying_buffer 为空!")
        chatbot[-1] = (inputs, "未能获取到有效响应，请检查 API 配置")
        yield from update_ui(chatbot=chatbot, history=history, msg='错误')

    logger.info(f"[Claude] 完成, response='{gpt_replying_buffer[:100]}...' len={len(gpt_replying_buffer)}")
    return


def _ensure_text_content(content: Any) -> str:
    """
    确保内容是文本格式，提取文本部分
    """
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif block.get("type") == "image":
                    # 图片类型不做处理
                    pass
        return "".join(text_parts)
    return str(content)
