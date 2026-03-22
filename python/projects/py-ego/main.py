#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
from datetime import datetime
from pathlib import Path

# 抑制 HuggingFace 警告和日志
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
os.environ['TRANSFORMERS_VERBOSITY'] = 'error'

# 设置日志级别
import logging as _logging
_logging.getLogger('sentence_transformers').setLevel(_logging.WARNING)
_logging.getLogger('transformers').setLevel(_logging.ERROR)
_logging.getLogger('urllib3').setLevel(_logging.WARNING)
_logging.getLogger('httpcore').setLevel(_logging.WARNING)
_logging.getLogger('openai').setLevel(_logging.WARNING)

from memory_store import MemoryStore
from config import get_openai_client, LLM_MODEL, LOG_LEVEL
import logging

# 设置 stdout 编码为 utf-8（解决 Windows 和一些终端的编码问题）
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

# 配置日志
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)
logger = logging.getLogger(__name__)

# ============ 聊天日志记录 ============
CHAT_LOGS_DIR = Path(__file__).parent / "chat_logs"
CHAT_LOGS_DIR.mkdir(exist_ok=True)

def get_chat_log_file() -> Path:
    """获取当天的聊天日志文件路径"""
    today = datetime.now().strftime("%Y-%m-%d")
    return CHAT_LOGS_DIR / f"chat_{today}.md"

def save_chat_to_file(user_msg: str, bot_reply: str, model: str):
    """将聊天记录保存到本地文件（Markdown 格式）"""
    log_file = get_chat_log_file()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 构建 Markdown 格式的记录
    entry = f"""## {timestamp}

**用户：** {user_msg}

**机器人：** {bot_reply}

---

"""
    
    # 如果是新文件，添加文件头
    if not log_file.exists():
        header = f"""# 聊天记录

**日期：** {datetime.now().strftime("%Y-%m-%d")}  
**模型：** {model}

---

"""
        log_file.write_text(header + entry, encoding='utf-8')
    else:
        # 追加到文件
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(entry)
    
    logger.debug(f"聊天记录已保存到: {log_file}")


# ============ 终端颜色工具 ============
class Colors:
    """ANSI 颜色码 - 让终端输出更加多彩"""
    # 前景色
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # 亮色
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'
    
    # 背景色
    BG_BLACK = '\033[40m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA = '\033[45m'
    BG_CYAN = '\033[46m'
    BG_WHITE = '\033[47m'
    
    # 样式
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'
    BLINK = '\033[5m'
    REVERSE = '\033[7m'
    STRIKE = '\033[9m'
    
    # 重置
    RESET = '\033[0m'
    
    @classmethod
    def disable(cls):
        """禁用所有颜色（用于不支持颜色的终端）"""
        for attr in dir(cls):
            if not attr.startswith('_'):
                setattr(cls, attr, '')


def colorize(text, *styles):
    """
    给文本添加颜色/样式
    用法: colorize("Hello", Colors.RED, Colors.BOLD)
    """
    style_codes = ''.join(styles)
    return f"{style_codes}{text}{Colors.RESET}"


# 检测终端是否支持颜色
_use_colors = True
if os.getenv('NO_COLOR') or os.getenv('TERM') == 'dumb':
    _use_colors = False
if sys.platform == 'win32':
    # Windows 10+ 支持 ANSI 颜色
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except:
        _use_colors = False

if not _use_colors:
    Colors.disable()

# 初始化 OpenAI 兼容客户端
client = get_openai_client()

system_prompt = {
    "role": "system",
    "content": (
        "你是一位专业的心理陪护机器人，擅长认知行为疗法（CBT）、情绪识别和情感共情，"
        "你的任务是帮助用户识别情绪、接受自己、构建健康心态。你会结合用户的过去经历给出个性化回应。"
    )
}

store = MemoryStore()


def clean_text(text):
    """清理文本，移除可能导致编码错误的字符"""
    if text is None:
        return ""
    text = str(text)
    # 移除 surrogate 字符
    text = text.encode('utf-8', 'ignore').decode('utf-8')
    # 移除控制字符（保留换行和制表符）
    text = ''.join(char for char in text if char == '\n' or char == '\t' or (ord(char) >= 32 and ord(char) <= 0x10FFFF))
    return text.strip()


def safe_print(text, end='\n'):
    """安全地打印文本，处理编码错误"""
    try:
        print(text, end=end)
    except UnicodeEncodeError:
        # 如果编码失败，尝试忽略错误字符
        try:
            encoded = text.encode(sys.stdout.encoding, errors='ignore').decode(sys.stdout.encoding)
            print(encoded, end=end)
        except:
            print("[打印错误]")


def chat_with_llm(messages):
    """
    使用配置的 LLM API 进行对话
    """
    try:
        # 清理所有消息内容
        cleaned_messages = []
        for msg in messages:
            cleaned_msg = {
                "role": msg["role"],
                "content": clean_text(msg["content"])
            }
            cleaned_messages.append(cleaned_msg)
        
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=cleaned_messages,
            temperature=0.8,
            max_tokens=2048
        )
        return clean_text(response.choices[0].message.content)
    except Exception as e:
        logger.error(f"LLM API 调用失败: {e}")
        return f"[错误] 无法获取回复: {e}"


def print_welcome():
    """打印欢迎信息（带颜色）"""
    # 渐变色边框
    border = colorize("═" * 60, Colors.CYAN, Colors.BOLD)
    safe_print(f"\n{border}")
    
    # 标题 - 渐变效果
    title = colorize("  🧠 欢迎使用心理陪护机器人", Colors.BRIGHT_CYAN, Colors.BOLD)
    subtitle = colorize("（含记忆系统）", Colors.CYAN)
    safe_print(f"{title} {subtitle}")
    
    # 模型信息
    model_info = colorize(f"  🤖 当前使用模型: ", Colors.BRIGHT_GREEN) + colorize(LLM_MODEL, Colors.GREEN, Colors.BOLD)
    safe_print(model_info)
    
    safe_print("")
    
    # 提示信息 - 带图标和颜色
    tip_color = Colors.BRIGHT_YELLOW
    cmd_color = Colors.BRIGHT_WHITE
    desc_color = Colors.YELLOW
    
    safe_print(colorize("  💡 使用提示:", tip_color, Colors.BOLD))
    safe_print(f"     {colorize('•', Colors.BRIGHT_MAGENTA)} 输入 {colorize('exit', cmd_color, Colors.BOLD)} 或 {colorize('quit', cmd_color, Colors.BOLD)}  {colorize('→ 退出对话', desc_color)}")
    safe_print(f"     {colorize('•', Colors.BRIGHT_MAGENTA)} 输入 {colorize('clear', cmd_color, Colors.BOLD)}              {colorize('→ 清空记忆', desc_color)}")
    safe_print(f"     {colorize('•', Colors.BRIGHT_MAGENTA)} {colorize('直接输入内容', cmd_color)}            {colorize('→ 开始对话', desc_color)}")
    
    safe_print("")
    
    # 聊天记录保存提示
    log_file = get_chat_log_file()
    log_tip = colorize("  📝 聊天记录自动保存至: ", Colors.BRIGHT_BLACK, Colors.DIM)
    log_path = colorize(f"{log_file}", Colors.BLACK, Colors.DIM)
    safe_print(f"{log_tip}{log_path}")
    
    safe_print(f"{border}\n")


def main():
    print_welcome()
    
    while True:
        try:
            # 使用更安全的输入方式
            # 用户输入提示（蓝色）
            safe_print(colorize("你", Colors.BRIGHT_BLUE, Colors.BOLD) + colorize("：", Colors.BLUE), end='')
            try:
                user_input = input()
            except UnicodeDecodeError as e:
                logger.error(f"输入解码错误: {e}")
                safe_print("⚠️ 输入包含无法识别的字符，请重新输入\n")
                continue
            
            user_input = clean_text(user_input)
            
            if user_input.strip().lower() in {"exit", "quit", "退出"}:
                safe_print(colorize("\n👋 再见！期待下次与你交流 💚\n", Colors.BRIGHT_GREEN, Colors.BOLD))
                break
            
            if user_input.strip().lower() in {"clear", "清空"}:
                global store
                store = MemoryStore()
                safe_print(colorize("  🗑️ 记忆已清空\n", Colors.BRIGHT_YELLOW))
                continue
            
            if not user_input.strip():
                continue

            # 添加到记忆库
            try:
                store.add(user_input)
            except Exception as e:
                logger.error(f"添加到记忆库失败: {e}")
                # 继续执行，不影响对话

            # 查询最相关的历史对话片段
            try:
                related_memories = store.query(user_input, k=3)
                memory_context = "\n".join([f"过去你曾说过：{clean_text(m['text'])}" for m in related_memories])
            except Exception as e:
                logger.error(f"查询记忆失败: {e}")
                memory_context = ""

            # 构建消息上下文
            messages = [system_prompt]
            if memory_context:
                messages.append({"role": "system", "content": f"相关历史记忆:\n{memory_context}"})
            messages.append({"role": "user", "content": user_input})

            # 请求 LLM
            thinking_msg = colorize("🤖 陪护机器人正在思考", Colors.BRIGHT_MAGENTA, Colors.DIM)
            dots = colorize("...", Colors.BRIGHT_MAGENTA, Colors.DIM)
            safe_print(f"{thinking_msg}{dots}", end='\r')
            reply = chat_with_llm(messages)
            
            # 清除 "正在思考" 的输出
            safe_print(" " * 40, end='\r')
            
            # 打印回复 - 带颜色边框
            bot_label = colorize("🤖 陪护机器人", Colors.BRIGHT_MAGENTA, Colors.BOLD)
            separator = colorize("：", Colors.MAGENTA)
            safe_print(f"\n{bot_label}{separator}")
            
            # 回复内容（白色高亮）
            reply_colored = colorize(reply, Colors.BRIGHT_WHITE)
            safe_print(f"   {reply_colored}")
            
            # 底部装饰线
            footer = colorize("─" * 40, Colors.DIM)
            safe_print(f"   {footer}\n")
            
            # 保存聊天记录到本地文件
            try:
                save_chat_to_file(user_input, reply, LLM_MODEL)
            except Exception as e:
                logger.error(f"保存聊天记录失败: {e}")
                # 不影响正常对话流程
            
        except KeyboardInterrupt:
            safe_print(colorize("\n\n👋 再见！期待下次与你交流 💚\n", Colors.BRIGHT_GREEN, Colors.BOLD))
            break
        except EOFError:
            safe_print(colorize("\n\n👋 再见！期待下次与你交流 💚\n", Colors.BRIGHT_GREEN, Colors.BOLD))
            break
        except Exception as e:
            logger.error(f"运行时错误: {e}")
            error_msg = colorize(f"\n[错误] {e}\n", Colors.BRIGHT_RED, Colors.BOLD)
            safe_print(error_msg)


if __name__ == "__main__":
    main()
