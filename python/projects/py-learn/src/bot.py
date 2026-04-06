"""
Telegram Bot 模块 - 交互层

提供 Telegram 消息推送和用户命令处理。
支持题目推送、答案收集、评分反馈和命令交互。
"""

import logging
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass

from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from config import TelegramConfig
from db import Database


# 配置日志
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


@dataclass
class QuestionMessage:
    """题目消息"""
    domain_label: str
    topic_name: str
    level: int
    main: str
    date_str: str


class TelegramBot:
    """
    Telegram Bot 封装

    处理消息推送、命令交互和用户答案收集。
    """

    def __init__(self, config: TelegramConfig, db: Database):
        """
        初始化 Bot

        Args:
            config: Telegram 配置
            db: 数据库实例
        """
        self.config = config
        self.db = db
        self.application: Optional[Application] = None
        self._answer_callback: Optional[Callable[[int, str], None]] = None

    async def initialize(self) -> None:
        """初始化应用"""
        self.application = (
            Application.builder()
            .token(self.config.bot_token)
            .build()
        )

        # 注册命令处理器
        self.application.add_handler(CommandHandler("start", self._cmd_start))
        self.application.add_handler(CommandHandler("tm_hint", self._cmd_hint))
        self.application.add_handler(CommandHandler("tm_skip", self._cmd_skip))
        self.application.add_handler(CommandHandler("tm_status", self._cmd_status))
        self.application.add_handler(CommandHandler("tm_history", self._cmd_history))
        self.application.add_handler(CommandHandler("tm_weak", self._cmd_weak))
        self.application.add_handler(CommandHandler("tm_topic", self._cmd_topic))
        self.application.add_handler(CommandHandler("tm_level", self._cmd_level))

        # 注册消息处理器（处理用户答案）
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )

    async def start(self) -> None:
        """启动 Bot"""
        if not self.application:
            await self.initialize()

        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        logger.info("Telegram Bot 已启动")

    async def stop(self) -> None:
        """停止 Bot"""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("Telegram Bot 已停止")

    def set_answer_callback(self, callback: Callable[[int, str], None]) -> None:
        """
        设置答案回调函数

        Args:
            callback: 接收 (question_id, answer_text) 的回调
        """
        self._answer_callback = callback

    async def push_question(self, question_id: int, message: QuestionMessage) -> bool:
        """
        推送题目

        Args:
            question_id: 题目 ID
            message: 题目消息

        Returns:
            是否发送成功
        """
        try:
            text = self._format_question(message)

            await self.application.bot.send_message(
                chat_id=self.config.chat_id,
                text=text,
                parse_mode="HTML"
            )
            return True
        except Exception as e:
            logger.error(f"推送题目失败: {e}")
            return False

    async def push_feedback(
        self,
        concept_score: float,
        depth_score: float,
        boundary_score: float,
        total_score: float,
        strengths: list,
        gaps: list,
        summary: str,
        references: list
    ) -> bool:
        """
        推送评分反馈

        Args:
            concept_score: 概念准确性得分
            depth_score: 系统深度得分
            boundary_score: 边界思考得分
            total_score: 总得分
            strengths: 答得好的点
            gaps: 遗漏的关键点
            summary: 标准答案摘要
            references: 参考资料

        Returns:
            是否发送成功
        """
        try:
            text = self._format_feedback(
                concept_score, depth_score, boundary_score, total_score,
                strengths, gaps, summary, references
            )

            await self.application.bot.send_message(
                chat_id=self.config.chat_id,
                text=text,
                parse_mode="HTML"
            )
            return True
        except Exception as e:
            logger.error(f"推送反馈失败: {e}")
            return False

    def _format_question(self, msg: QuestionMessage) -> str:
        """格式化题目消息"""
        level_stars = "★" * msg.level + "☆" * (4 - msg.level)

        return f"""━━━━━━━━━━━━━━━━━━━━
📚 今日精进 · {msg.date_str} · {msg.domain_label} · L{msg.level}

{msg.main}

━━━━━━━━━━━━━━━━━━━━
可用命令：
/tm_hint   — 获取一次提示（-1分）
/tm_skip   — 跳过今日题目
/tm_status — 查看本周进度
━━━━━━━━━━━━━━━━━━━━"""

    def _format_feedback(
        self,
        concept_score: float,
        depth_score: float,
        boundary_score: float,
        total_score: float,
        strengths: list,
        gaps: list,
        summary: str,
        references: list
    ) -> str:
        """格式化反馈消息"""
        def bar(score: float, max_score: float) -> str:
            filled = int(score / max_score * 10)
            return "█" * filled + "░" * (10 - filled)

        lines = [
            "━━━━━━━━━━━━━━━━━━━━",
            "📊 评分结果",
            "",
            f"概念准确性   {bar(concept_score, 3)}  {concept_score:.1f}/3",
            f"系统深度     {bar(depth_score, 4)}  {depth_score:.1f}/4",
            f"边界思考     {bar(boundary_score, 3)}  {boundary_score:.1f}/3",
            "─────────────────────",
            f"总分：{total_score:.1f} / 10",
            "",
        ]

        if strengths:
            lines.append("✅ 答得好的部分：")
            for s in strengths[:3]:
                lines.append(f"   • {s}")
            lines.append("")

        if gaps:
            lines.append("⚠️  遗漏的关键点：")
            for g in gaps[:3]:
                lines.append(f"   • {g}")
            lines.append("")

        if summary:
            lines.extend([
                "📖 标准答案摘要：",
                f"   {summary}",
                ""
            ])

        if references:
            lines.extend([
                "🔗 参考：",
                f"   {', '.join(references[:2])}"
            ])

        lines.append("━━━━━━━━━━━━━━━━━━━━")

        return "\n".join(lines)

    # ==================== 命令处理器 ====================

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/start 命令"""
        await update.message.reply_text(
            "🎯 欢迎来到每日精进 Agent！\n\n"
            "每天 08:00 推送一道架构师级别的题目。\n"
            "直接回复消息即可提交答案。\n\n"
            "可用命令：\n"
            "/tm_hint - 获取提示\n"
            "/tm_skip - 跳过今日\n"
            "/tm_status - 查看进度\n"
            "/history - 查看历史"
        )

    async def _cmd_hint(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/tm_hint 命令 - 获取提示"""
        # TODO: 从题目中获取追问预案并发送
        await update.message.reply_text(
            "💡 提示功能开发中...\n"
            "（使用提示会扣除 1 分）"
        )

    async def _cmd_skip(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/tm_skip 命令 - 跳过题目"""
        question = self.db.get_today_question()
        if question:
            self.db.update_question_status(question.id, 'skip')
            await update.message.reply_text("⏭️ 已跳过今日题目。明天见！")
        else:
            await update.message.reply_text("今天还没有题目需要跳过。")

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/tm_status 命令 - 查看进度"""
        summary = self.db.get_weekly_summary()

        completion_bar = "█" * int(summary['completion_rate'] * 10) + \
                        "░" * (10 - int(summary['completion_rate'] * 10))

        await update.message.reply_text(
            f"📈 本周进度\n\n"
            f"出题数: {summary['total_questions']}\n"
            f"已完成: {summary['answered']}\n"
            f"完成率: {completion_bar} {summary['completion_rate']*100:.0f}%\n"
            f"平均分: {summary['avg_score']:.1f}"
        )

    async def _cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/tm_history 命令 - 查看历史"""
        # 解析参数
        args = context.args
        limit = int(args[0]) if args and args[0].isdigit() else 5

        questions = self.db.get_recent_questions(limit)

        if not questions:
            await update.message.reply_text("暂无历史记录。")
            return

        lines = ["📜 最近答题记录", ""]
        for i, q in enumerate(questions, 1):
            status_emoji = {
                'answered': '✅',
                'pending': '⏳',
                'timeout': '⌛',
                'skip': '⏭️'
            }.get(q.status, '❓')

            lines.append(f"{i}. {status_emoji} {q.date} · L{q.level} · {q.qtype}")

        await update.message.reply_text("\n".join(lines))

    async def _cmd_weak(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/tm_weak 命令 - 查看薄弱点"""
        weak_topics = self.db.get_weak_topics()

        if not weak_topics:
            await update.message.reply_text("🎉 目前没有薄弱点，继续保持！")
            return

        lines = ["📌 当前薄弱点", ""]
        for topic_id, stats in weak_topics[:5]:
            topic = self.db.get_topic_by_id(topic_id)
            if topic:
                lines.append(f"• {topic.name} (avg: {stats.avg_score:.1f})")

        await update.message.reply_text("\n".join(lines))

    async def _cmd_topic(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/tm_topic 命令 - 指定下次题目主题"""
        await update.message.reply_text(
            "📝 /topic 命令开发中...\n"
            "用法: /topic <主题名称>"
        )

    async def _cmd_level(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """/tm_level 命令 - 临时覆盖难度"""
        await update.message.reply_text(
            "📊 /level 命令开发中...\n"
            "用法: /level <L2/L3/L4>"
        )

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理用户消息（答案）"""
        # 验证 chat_id
        if str(update.effective_chat.id) != self.config.chat_id:
            logger.warning(f"收到来自未授权 chat_id 的消息: {update.effective_chat.id}")
            return

        # 检查是否有待回答的题目
        question = self.db.get_today_question()
        if not question:
            await update.message.reply_text("今天还没有题目哦，请稍后再试。")
            return

        if question.status != 'pending':
            await update.message.reply_text("今天的题目已经回答过了，明天见！")
            return

        # 获取答案文本
        answer_text = update.message.text

        # 更新题目状态
        self.db.update_question_status(question.id, 'answered')

        # 调用回调函数处理答案
        if self._answer_callback:
            self._answer_callback(question.id, answer_text)

        await update.message.reply_text("✅ 答案已提交，正在评分...")


class BotRunner:
    """
    Bot 运行器

    简化 Bot 启动和管理的辅助类。
    """

    def __init__(self, config: TelegramConfig, db: Database):
        self.bot = TelegramBot(config, db)

    async def run(self) -> None:
        """运行 Bot"""
        await self.bot.start()

    async def stop(self) -> None:
        """停止 Bot"""
        await self.bot.stop()
