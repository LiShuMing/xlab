#!/usr/bin/env python3
"""Demo script to showcase mini-program chat interface output.

This script simulates the WeChat mini-program chat interface,
demonstrating how different AI roles respond to user messages.
"""
from __future__ import annotations

from datetime import datetime

from app.core.role import PREDEFINED_ROLES


def print_header(title: str) -> None:
    """Print a section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_chat_message(role_icon: str, role_name: str, content: str, is_user: bool = False) -> None:
    """Print a chat message in mini-program style.

    Args:
        role_icon: Emoji icon for the role
        role_name: Display name of the role
        content: Message content
        is_user: Whether this is a user message
    """
    timestamp = datetime.now().strftime("%H:%M")

    if is_user:
        # User message - right aligned
        print(f"\n{' ' * 40} [{timestamp}] 我")
        print(f"{' ' * 20} ┌─{'─' * 38}┐")
        for line in content.split('\n'):
            print(f"{' ' * 20} │ {line:<36} │")
        print(f"{' ' * 20} └─{'─' * 38}┘")
    else:
        # AI message - left aligned with role info
        print(f"\n{role_icon} {role_name} [{timestamp}]")
        print(f"┌─{'─' * 58}┐")
        for line in content.split('\n'):
            # Handle long lines
            while len(line) > 56:
                print(f"│ {line[:56]:<56} │")
                line = line[56:]
            print(f"│ {line:<56} │")
        print(f"└─{'─' * 58}┘")


def print_role_card(role_id: str) -> None:
    """Print a role selection card."""
    role = PREDEFINED_ROLES[role_id]
    print(f"\n┌─{'─' * 40}┐")
    print(f"│  {role.icon} {role.name:<33} │")
    print(f"├─{'─' * 40}┤")
    print(f"│  {role.description:<36} │")
    print(f"└─{'─' * 40}┘")


def demo_therapist() -> None:
    """Demo the therapist role."""
    print_header("🧠 心理陪护师 - 温暖倾听，专业支持")

    role = PREDEFINED_ROLES["therapist"]
    print_role_card("therapist")

    # Simulate conversation
    user_msg = "最近工作压力很大，晚上总是睡不着..."
    print_chat_message("👤", "我", user_msg, is_user=True)

    ai_reply = (
        "听起来工作压力让你很困扰，这种辗转难眠的感觉确实很难受。\n\n"
        "你提到脑子里一直在想工作的事情——那些想法是什么样的呢？\n"
        "是担心具体的事情，还是停不下来的各种可能？\n\n"
        "我听到了你的感受。这种感觉是很正常的。"
    )
    print_chat_message(role.icon, role.name, ai_reply)


def demo_researcher() -> None:
    """Demo the researcher role."""
    print_header("🔬 研究员 - 系统分析，深度洞察")

    role = PREDEFINED_ROLES["researcher"]
    print_role_card("researcher")

    user_msg = "帮我分析一下新能源汽车行业"
    print_chat_message("👤", "我", user_msg, is_user=True)

    ai_reply = (
        "好的，我来帮你系统地梳理中国新能源汽车行业的发展情况。\n\n"
        "从研究的角度来看，我们可以从以下几个维度来分析：\n\n"
        "**1. 市场规模**\n"
        "• 销量数据及增长趋势\n"
        "• 市场渗透率变化\n\n"
        "**2. 竞争格局**\n"
        "• 主要玩家及市场份额\n"
        "• 技术路线对比\n\n"
        "**3. 政策环境**\n"
        "• 补贴政策演变\n"
        "• 双积分制度影响\n\n"
        "数据显示，这个市场正在经历快速变革。你希望先深入哪个方面？"
    )
    print_chat_message(role.icon, role.name, ai_reply)


def demo_learner() -> None:
    """Demo the learner role."""
    print_header("📚 学习者 - 科学学习，高效成长")

    role = PREDEFINED_ROLES["learner"]
    print_role_card("learner")

    user_msg = "我想学Python编程，但不知道从哪里开始"
    print_chat_message("👤", "我", user_msg, is_user=True)

    ai_reply = (
        "太好了！Python是入门编程的绝佳选择。让我们一步步来。\n\n"
        "**第一阶段：基础语法（2-3周）**\n"
        "• 变量、数据类型、运算符\n"
        "• 条件语句和循环\n"
        "• 函数和模块\n"
        "📚 推荐资源：Python官方教程\n\n"
        "**第二阶段：实践项目（3-4周）**\n"
        "• 自动化脚本\n"
        "• 简单的游戏\n"
        "🎯 目标：做3个小项目\n\n"
        "你已经掌握了核心思路。你现在的编程基础如何？"
    )
    print_chat_message(role.icon, role.name, ai_reply)


def demo_philosopher() -> None:
    """Demo the philosopher role."""
    print_header("🤔 哲学家 - 深度思考，人生智慧")

    role = PREDEFINED_ROLES["philosopher"]
    print_role_card("philosopher")

    user_msg = "人活着到底有什么意义？感觉每天都很空虚"
    print_chat_message("👤", "我", user_msg, is_user=True)

    ai_reply = (
        "这是一个古老而深刻的问题，人类思考了几千年。\n\n"
        "这让我想起萨特的话：「存在先于本质。」\n"
        "意思是，我们首先「存在」，然后通过选择和行动来定义自己。\n\n"
        "某种程度上，东方的智慧则提供了另一种视角。\n"
        "道家说「无为而无不为」，有时候，放下对「意义」的执着，\n"
        "活在当下，意义反而会显现。\n\n"
        "一个值得思考的问题是：在哪些时刻，你会感到一种「对了」的感觉？"
    )
    print_chat_message(role.icon, role.name, ai_reply)


def print_api_response_demo() -> None:
    """Print API response format demo."""
    print_header("📡 API 响应格式（小程序实际接收的数据）")

    print("\n【发送消息】POST /api/chat/sessions/{id}/messages")
    print("Request:")
    print('  {')
    print('    "content": "最近工作压力很大..."')
    print('  }')

    print("\nResponse:")
    print('  {')
    print('    "reply": "听起来工作压力让你很困扰...",')
    print('    "memories_used": 3,')
    print('    "role": "therapist",')
    print('    "timestamp": "2024-03-24T14:30:00Z"')
    print('  }')

    print("\n【获取历史消息】GET /api/chat/sessions/{id}/messages")
    print('  {')
    print('    "items": [')
    print('      {')
    print('        "id": "msg_001",')
    print('        "role": "user",')
    print('        "content": "最近工作压力很大...",')
    print('        "created_at": "2024-03-24T14:30:00Z"')
    print('      },')
    print('      {')
    print('        "id": "msg_002",')
    print('        "role": "assistant",')
    print('        "content": "听起来工作压力让你很困扰...",')
    print('        "created_at": "2024-03-24T14:30:05Z"')
    print('      }')
    print('    ],')
    print('    "has_more": false')
    print('  }')


def main() -> None:
    """Run the demo."""
    print("\n" + "🌟" * 30)
    print("  PyEgo Mini-Program Chat Interface Demo")
    print("  AI 心理陪伴小程序 - 聊天界面效果展示")
    print("🌟" * 30)

    demo_therapist()
    demo_researcher()
    demo_learner()
    demo_philosopher()
    print_api_response_demo()

    print_header("✨ 特性总结")
    print("""
📱 小程序界面特点：
   • 角色头像 + 名称显示
   • 时间戳标记
   • 气泡式对话布局
   • 支持 Markdown 格式（粗体、列表等）

🤖 AI 角色特色：
   • 🧠 心理陪护师 - 温暖共情，专业引导
   • 🔬 研究员     - 结构化分析，数据驱动
   • 📚 学习者     - 循序渐进，鼓励成长
   • 🤔 哲学家     - 深度思考，引用经典

⚡ 技术亮点：
   • 语义记忆检索（memories_used）
   • 角色专属 system prompt
   • 对话历史上下文
   • 流式响应支持
""")


if __name__ == "__main__":
    main()
