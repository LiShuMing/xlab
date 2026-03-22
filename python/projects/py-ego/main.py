#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import threading
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

PROFILE_FILE = Path(__file__).parent / "data" / "profile.md"

def get_chat_log_file() -> Path:
    """获取当天的聊天日志文件路径"""
    today = datetime.now().strftime("%Y-%m-%d")
    return CHAT_LOGS_DIR / f"chat_{today}.md"

def save_chat_to_file(user_msg: str, bot_reply: str, model: str):
    """将聊天记录保存到本地文件（Markdown 格式）"""
    log_file = get_chat_log_file()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    entry = f"""## {timestamp}

**用户：** {user_msg}

**机器人：** {bot_reply}

---

"""

    if not log_file.exists():
        header = f"""# 聊天记录

**日期：** {datetime.now().strftime("%Y-%m-%d")}
**模型：** {model}

---

"""
        log_file.write_text(header + entry, encoding='utf-8')
    else:
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
    """给文本添加颜色/样式。用法: colorize("Hello", Colors.RED, Colors.BOLD)"""
    style_codes = ''.join(styles)
    return f"{style_codes}{text}{Colors.RESET}"


# 检测终端是否支持颜色
_use_colors = True
if os.getenv('NO_COLOR') or os.getenv('TERM') == 'dumb':
    _use_colors = False
if sys.platform == 'win32':
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
        "当相关历史记忆存在时，请在回复中自然地引用它们，"
        "例如使用'你上次提到...'或'我注意到你多次提到...'，让用户感受到被真正记住和理解。"
    )
}

store = MemoryStore()

# ============ 用户画像（Phase 2）============
_profile_updating = False
_profile_lock = threading.Lock()


def update_profile(user_input: str, bot_reply: str):
    """在后台线程中异步更新用户画像（每次对话后调用）。

    线程安全：
    - _profile_updating 标志防止同时启动第二个更新线程
    - _profile_lock 保护文件读写操作
    - try/finally 确保标志在异常时也能清除
    """
    global _profile_updating
    _profile_updating = True
    try:
        with _profile_lock:
            current_profile = ""
            if PROFILE_FILE.exists():
                current_profile = PROFILE_FILE.read_text(encoding='utf-8')

        prompt = (
            "你是一个用户画像更新助手。请根据本轮对话，更新下方的用户画像。\n"
            "规则：\n"
            "1. 只记录用户明确说出的事实，不要推断或臆测\n"
            "2. 控制在300字以内\n"
            "3. 保留已有的准确信息，删除过时的信息\n"
            "4. 用第三人称描述（\"用户...\"）\n"
            "5. 如果已有信息较多，优先保留最近和最常出现的信息，适当压缩早期细节\n\n"
            f"当前画像：\n{current_profile}\n\n"
            f"本轮对话：\n用户：{user_input}\n机器人：{bot_reply}\n\n"
            "请输出更新后的用户画像（只输出画像内容，不要其他说明）："
        )

        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": clean_text(prompt)}],
            temperature=0.3,
            max_tokens=500
        )
        new_profile = clean_text(response.choices[0].message.content)

        with _profile_lock:
            PROFILE_FILE.parent.mkdir(exist_ok=True)
            PROFILE_FILE.write_text(new_profile, encoding='utf-8')

    except Exception as e:
        logger.error(f"更新用户画像失败: {e}")
    finally:
        _profile_updating = False


def clean_text(text):
    """清理文本，移除可能导致编码错误的字符"""
    if text is None:
        return ""
    text = str(text)
    text = text.encode('utf-8', 'ignore').decode('utf-8')
    text = ''.join(char for char in text if char == '\n' or char == '\t' or (ord(char) >= 32 and ord(char) <= 0x10FFFF))
    return text.strip()


def safe_print(text, end='\n'):
    """安全地打印文本，处理编码错误"""
    try:
        print(text, end=end)
    except UnicodeEncodeError:
        try:
            encoded = text.encode(sys.stdout.encoding, errors='ignore').decode(sys.stdout.encoding)
            print(encoded, end=end)
        except:
            print("[打印错误]")


def chat_with_llm(messages):
    """使用配置的 LLM API 进行对话"""
    try:
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


# ============ 斜杠命令处理 ============

def _cmd_show_memory():
    """显示所有存储的记忆（/memory 命令）"""
    total = len(store.memories)
    safe_print(colorize(f"\n  📚 记忆库 ({total} 条):", Colors.BRIGHT_CYAN, Colors.BOLD))
    if total == 0:
        safe_print(colorize("  （空）\n", Colors.DIM))
        return
    for i, m in enumerate(store.memories):
        ts = m.get('timestamp', '')[:16].replace('T', ' ')
        raw_text = m.get('text', '')
        text = raw_text[:60] + ('...' if len(raw_text) > 60 else '')
        safe_print(f"  [{i}] {colorize(ts, Colors.DIM)}  {text}")
    safe_print("")


def _cmd_forget(stripped):
    """处理 /forget N 命令 — 删除第 N 条记忆"""
    parts = stripped.split(None, 1)
    if len(parts) < 2:
        safe_print(colorize("  用法：/forget N（N 为记忆编号，可用 /memory 查看）\n", Colors.BRIGHT_YELLOW))
        return

    try:
        n = int(parts[1].strip())
    except ValueError:
        safe_print(colorize(f"  ❌ '{parts[1].strip()}' 不是有效的数字\n", Colors.BRIGHT_RED))
        return

    total = len(store.memories)
    if n < 0 or n >= total:
        safe_print(colorize(f"  ❌ 索引 {n} 超出范围（共 {total} 条记忆，编号 0–{total - 1}）\n", Colors.BRIGHT_RED))
        return

    # 大量记忆时给出确认提示（重建索引耗时较长）
    if total > 50:
        safe_print(colorize(
            f"  ⚠️  删除后需要重建索引（共 {total} 条记忆），可能需要几秒。"
            "确认请按 Enter，取消请按 Ctrl+C：",
            Colors.BRIGHT_YELLOW
        ), end='')
        try:
            input()
        except (KeyboardInterrupt, EOFError):
            safe_print(colorize("\n  已取消\n", Colors.DIM))
            return

    try:
        store.delete(n)
        safe_print(colorize(f"  ✅ 已删除第 {n} 条记忆\n", Colors.BRIGHT_GREEN))
        _cmd_show_memory()  # 立即显示更新后的列表，避免用户用错位的索引
    except Exception as e:
        safe_print(colorize(f"  ❌ 删除失败: {e}\n", Colors.BRIGHT_RED))


def _cmd_why(last_retrieved_memories):
    """显示上次回复用到了哪些记忆（/why 命令）"""
    if not last_retrieved_memories:
        safe_print(colorize("\n  💭 暂无检索记录（发一条消息后再试）\n", Colors.DIM))
        return

    safe_print(colorize("\n  🔍 上次回复用到的记忆：", Colors.BRIGHT_CYAN, Colors.BOLD))
    for i, (m, dist) in enumerate(last_retrieved_memories):
        if dist < 0.3:
            label = colorize("非常相关", Colors.BRIGHT_GREEN)
        elif dist < 0.6:
            label = colorize("较为相关", Colors.BRIGHT_YELLOW)
        else:
            label = colorize("模糊相关", Colors.DIM)
        ts = m.get('timestamp', '')[:16].replace('T', ' ')
        raw_text = m.get('text', '')
        text = raw_text[:60] + ('...' if len(raw_text) > 60 else '')
        safe_print(f"  [{i + 1}] {label}  {colorize(ts, Colors.DIM)}  {text}")
    safe_print("")


def _cmd_profile():
    """显示当前用户画像（/profile 命令）"""
    if not PROFILE_FILE.exists():
        safe_print(colorize("\n  尚未建立画像，继续对话后会自动生成。\n", Colors.DIM))
        return
    profile = PROFILE_FILE.read_text(encoding='utf-8').strip()
    if not profile:
        safe_print(colorize("\n  尚未建立画像，继续对话后会自动生成。\n", Colors.DIM))
        return
    safe_print(colorize("\n  👤 你的画像：", Colors.BRIGHT_CYAN, Colors.BOLD))
    safe_print(profile)
    safe_print("")


def print_welcome():
    """打印欢迎信息（带颜色）"""
    border = colorize("═" * 60, Colors.CYAN, Colors.BOLD)
    safe_print(f"\n{border}")

    title = colorize("  🧠 欢迎使用心理陪护机器人", Colors.BRIGHT_CYAN, Colors.BOLD)
    subtitle = colorize("（含记忆系统）", Colors.CYAN)
    safe_print(f"{title} {subtitle}")

    model_info = colorize(f"  🤖 当前使用模型: ", Colors.BRIGHT_GREEN) + colorize(LLM_MODEL, Colors.GREEN, Colors.BOLD)
    safe_print(model_info)

    safe_print("")

    tip_color = Colors.BRIGHT_YELLOW
    cmd_color = Colors.BRIGHT_WHITE
    desc_color = Colors.YELLOW

    safe_print(colorize("  💡 使用提示:", tip_color, Colors.BOLD))
    safe_print(f"     {colorize('•', Colors.BRIGHT_MAGENTA)} 输入 {colorize('exit', cmd_color, Colors.BOLD)} 或 {colorize('quit', cmd_color, Colors.BOLD)}  {colorize('→ 退出对话', desc_color)}")
    safe_print(f"     {colorize('•', Colors.BRIGHT_MAGENTA)} 输入 {colorize('clear', cmd_color, Colors.BOLD)}              {colorize('→ 清空记忆', desc_color)}")
    safe_print(f"     {colorize('•', Colors.BRIGHT_MAGENTA)} 输入 {colorize('/memory', cmd_color, Colors.BOLD)}            {colorize('→ 查看记忆库', desc_color)}")
    safe_print(f"     {colorize('•', Colors.BRIGHT_MAGENTA)} 输入 {colorize('/forget N', cmd_color, Colors.BOLD)}          {colorize('→ 删除第 N 条记忆', desc_color)}")
    safe_print(f"     {colorize('•', Colors.BRIGHT_MAGENTA)} 输入 {colorize('/why', cmd_color, Colors.BOLD)}               {colorize('→ 查看上次用了哪些记忆', desc_color)}")
    safe_print(f"     {colorize('•', Colors.BRIGHT_MAGENTA)} 输入 {colorize('/profile', cmd_color, Colors.BOLD)}           {colorize('→ 查看你的画像', desc_color)}")
    safe_print(f"     {colorize('•', Colors.BRIGHT_MAGENTA)} {colorize('直接输入内容', cmd_color)}            {colorize('→ 开始对话', desc_color)}")

    safe_print("")

    log_file = get_chat_log_file()
    log_tip = colorize("  📝 聊天记录自动保存至: ", Colors.BRIGHT_BLACK, Colors.DIM)
    log_path = colorize(f"{log_file}", Colors.BLACK, Colors.DIM)
    safe_print(f"{log_tip}{log_path}")

    safe_print(f"{border}\n")


def main():
    print_welcome()

    # 初始化：上次检索到的记忆（用于 /why 命令）
    last_retrieved_memories = []

    while True:
        try:
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
                store.delete_all()  # 清空内存 + 删除磁盘文件（下次启动也不会重载）
                store = MemoryStore()
                safe_print(colorize("  🗑️ 记忆已清空\n", Colors.BRIGHT_YELLOW))
                continue

            if not user_input.strip():
                continue

            # ── 斜杠命令处理（不存入记忆库）─────────────────────────
            stripped = user_input.strip()

            if stripped == '/memory':
                _cmd_show_memory()
                continue

            elif stripped.startswith('/forget'):
                _cmd_forget(stripped)
                continue

            elif stripped == '/why':
                _cmd_why(last_retrieved_memories)
                continue

            elif stripped == '/profile':
                _cmd_profile()
                continue
            # ─────────────────────────────────────────────────────────

            # 存入记忆库（仅限正常对话输入，不含斜杠命令）
            try:
                store.add(user_input)
            except Exception as e:
                logger.error(f"添加到记忆库失败: {e}")

            # 查询最相关的历史对话片段
            try:
                related_memories = store.query(user_input, k=3)
                last_retrieved_memories = related_memories
                memory_context = "\n".join(
                    [f"过去你曾说过：{clean_text(m['text'])}" for m, _ in related_memories]
                )
            except Exception as e:
                logger.error(f"查询记忆失败: {e}")
                memory_context = ""
                last_retrieved_memories = []

            # 构建消息上下文
            # 顺序：系统提示 → 用户画像（若有）→ 历史记忆（若有）→ 用户消息
            messages = [system_prompt]

            if PROFILE_FILE.exists():
                try:
                    profile_content = PROFILE_FILE.read_text(encoding='utf-8').strip()
                    if profile_content:
                        messages.append({
                            "role": "system",
                            "content": f"用户画像：\n{profile_content}"
                        })
                except Exception as e:
                    logger.error(f"读取用户画像失败: {e}")

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

            # 打印回复
            bot_label = colorize("🤖 陪护机器人", Colors.BRIGHT_MAGENTA, Colors.BOLD)
            separator = colorize("：", Colors.MAGENTA)
            safe_print(f"\n{bot_label}{separator}")
            reply_colored = colorize(reply, Colors.BRIGHT_WHITE)
            safe_print(f"   {reply_colored}")
            footer = colorize("─" * 40, Colors.DIM)
            safe_print(f"   {footer}\n")

            # 保存聊天记录到本地文件
            try:
                save_chat_to_file(user_input, reply, LLM_MODEL)
            except Exception as e:
                logger.error(f"保存聊天记录失败: {e}")

            # 异步更新用户画像（Phase 2：在后台线程中运行，不阻塞对话）
            if not _profile_updating:
                t = threading.Thread(
                    target=update_profile,
                    args=(user_input, reply),
                    daemon=True
                )
                t.start()

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
