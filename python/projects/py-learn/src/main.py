"""
每日精进 Agent - 主入口

整合所有模块，提供完整的每日学习 Agent 功能。
支持定时调度运行和手动触发模式。
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

from config import load_config, Config
from db import Database, Domain, Topic
from plan import PlanEngine, PlanResult, plan_daily
from generate import QuestionGenerator, GeneratedQuestion
from reflect import ReflectEngine, EvaluationResult
from bot import TelegramBot, QuestionMessage, BotRunner
from scheduler import Scheduler, ManualTrigger
from tools.knowledge import KnowledgeGraphTool
from tools.memory import MemoryReader


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


class DailyLearningAgent:
    """
    每日精进 Agent 主类

    整合 Plan、Generate、Reflect、Bot 等模块，
    提供完整的每日学习流程。
    """

    def __init__(self, config: Config):
        """
        初始化 Agent

        Args:
            config: 应用配置
        """
        self.config = config

        # 初始化数据库
        db_path = Path(config.paths.data_dir) / "memory.db"
        self.db = Database(str(db_path))

        # 初始化知识图谱
        self.knowledge_tool = KnowledgeGraphTool(config.paths.topics_file)

        # 初始化记忆读取工具
        self.memory_reader = MemoryReader(self.db)

        # 初始化 Plan 引擎
        learning_config = {
            'level_up_threshold': config.learning.level_up_threshold,
            'level_up_consecutive': config.learning.level_up_consecutive,
            'level_down_threshold': config.learning.level_down_threshold,
            'level_down_consecutive': config.learning.level_down_consecutive,
        }
        self.plan_engine = PlanEngine(self.db, learning_config)

        # 初始化生成器
        self.question_generator = QuestionGenerator(config.llm)

        # 初始化评估引擎
        self.reflect_engine = ReflectEngine(config.llm, self.db)

        # 初始化 Bot（如果配置了 token）
        self.bot: TelegramBot | None = None
        if config.telegram.bot_token and config.telegram.chat_id:
            self.bot = TelegramBot(config.telegram, self.db)
            self.bot.set_answer_callback(self._on_answer_received)

        # 初始化调度器
        self.scheduler = Scheduler(config.schedule)
        self.scheduler.set_callbacks(
            push=self._on_scheduled_push,
            reminder=self._on_scheduled_reminder,
            timeout=self._on_scheduled_timeout
        )

        # 初始化数据
        self._init_data()

    def _init_data(self) -> None:
        """初始化数据库数据（从 topics.yaml 导入）"""
        # 导入领域
        domains = [
            Domain(id=d.id, label=d.label, rotation_day=d.rotation_day)
            for d in self.knowledge_tool.graph.get_all_domains()
        ]
        self.db.init_domains(domains)

        # 导入主题
        topics = [
            Topic(
                id=t.id,
                domain_id=t.domain_id,
                name=t.name,
                level_default=t.level_default,
                tags=t.tags,
                subtopics=t.subtopics,
                key_points=t.key_points,
                references=t.references,
            )
            for t in self.knowledge_tool.graph.topics.values()
        ]
        self.db.init_topics(topics)

        logger.info(f"已初始化 {len(domains)} 个领域，{len(topics)} 个主题")

    async def _on_scheduled_push(self) -> None:
        """定时推送处理器"""
        logger.info("定时任务：开始推送今日题目")
        await self.push_daily_question()

    async def _on_scheduled_reminder(self) -> None:
        """定时提醒处理器"""
        logger.info("定时任务：发送提醒")

        # 检查今天是否有未回答的题目
        question = self.db.get_today_question()
        if question and question.status == 'pending':
            if self.bot:
                await self.bot.application.bot.send_message(
                    chat_id=self.config.telegram.chat_id,
                    text="⏰ 今日题目还未作答哦，别忘了打卡！\n发送 /tm_status 查看进度"
                )

    async def _on_scheduled_timeout(self) -> None:
        """定时超时处理器"""
        logger.info("定时任务：处理超时")

        # 检查今天是否有 pending 的题目
        question = self.db.get_today_question()
        if question and question.status == 'pending':
            self.db.update_question_status(question.id, 'timeout')
            logger.info(f"题目 {question.id} 已标记为超时")

    def _on_answer_received(self, question_id: int, answer_text: str) -> None:
        """
        用户答案接收处理器

        Args:
            question_id: 题目 ID
            answer_text: 答案文本
        """
        logger.info(f"收到题目 {question_id} 的答案，开始评估...")

        # 异步执行评估
        asyncio.create_task(self._evaluate_answer(question_id, answer_text))

    async def _evaluate_answer(self, question_id: int, answer_text: str) -> None:
        """
        评估答案

        Args:
            question_id: 题目 ID
            answer_text: 答案文本
        """
        try:
            # 获取题目信息
            question = self.db.get_question_by_id(question_id)
            if not question:
                logger.error(f"题目 {question_id} 不存在")
                return

            question_data = question.question_json
            question_main = question_data.get('main', '')
            question_intent = question_data.get('intent', [])

            # 执行评估
            result = self.reflect_engine.evaluate(
                question_main=question_main,
                question_intent=question_intent,
                user_answer=answer_text
            )

            # 保存评估结果
            self.reflect_engine.save_evaluation(
                question_id=question_id,
                user_answer=answer_text,
                result=result
            )

            logger.info(f"题目 {question_id} 评估完成，总分: {result.total_score:.1f}")

            # 推送反馈
            if self.bot:
                await self.bot.push_feedback(
                    concept_score=result.concept_score,
                    depth_score=result.depth_score,
                    boundary_score=result.boundary_score,
                    total_score=result.total_score,
                    strengths=result.strengths,
                    gaps=result.gaps,
                    summary=result.summary,
                    references=question_data.get('references', [])
                )

        except Exception as e:
            logger.error(f"评估答案失败: {e}")

    async def push_daily_question(self, override_domain: str | None = None) -> bool:
        """
        推送每日题目

        Args:
            override_domain: 强制指定领域（可选）

        Returns:
            是否成功
        """
        try:
            # 1. Plan - 规划题目
            logger.info("开始规划题目...")
            plan = self.plan_engine.plan_daily_question(override_domain)
            logger.info(f"规划结果: {plan.domain.label} - {plan.topic.name} (L{plan.level})")

            # 2. 获取上下文
            knowledge_context = self.knowledge_tool.get_topic_context(plan.topic.id)
            memory_context = {
                'stats': plan.context.get('stats', {}),
            }

            # 3. Generate - 生成题目
            logger.info("开始生成题目...")
            question = self.question_generator.generate(
                plan=plan,
                knowledge_context=knowledge_context,
                memory_context=memory_context
            )
            logger.info("题目生成完成")

            # 4. 保存到数据库
            question_data = {
                'main': question.main,
                'intent': question.intent,
                'followups': question.followups,
                'extension': question.extension,
                'references': question.references,
            }

            question_id = self.db.create_question(
                topic_id=plan.topic.id,
                level=plan.level,
                qtype=plan.qtype.value,
                question_data=question_data
            )
            logger.info(f"题目已保存，ID: {question_id}")

            # 5. 推送到 Telegram
            if self.bot:
                # 确保 Bot 已初始化
                if not self.bot.application:
                    await self.bot.initialize()

                date_str = datetime.now().strftime("%m/%d")
                message = QuestionMessage(
                    domain_label=plan.domain.label,
                    topic_name=plan.topic.name,
                    level=plan.level,
                    main=question.main,
                    date_str=date_str
                )

                success = await self.bot.push_question(question_id, message)
                if success:
                    logger.info("题目推送成功")
                else:
                    logger.error("题目推送失败")

            return True

        except Exception as e:
            logger.error(f"推送题目失败: {e}")
            return False

    async def run_scheduler(self) -> None:
        """运行调度器模式"""
        logger.info("启动调度器模式...")

        if self.bot:
            await self.bot.initialize()
            await self.bot.start()

        self.scheduler.start()

        logger.info("Agent 已启动，等待定时任务...")
        logger.info(f"下次推送时间: {self.scheduler.get_next_run_time('daily_push')}")

        try:
            # 保持运行
            while True:
                await asyncio.sleep(3600)
        except KeyboardInterrupt:
            logger.info("收到停止信号，正在关闭...")
        finally:
            self.scheduler.shutdown()
            if self.bot:
                await self.bot.stop()

    async def run_once(self) -> bool:
        """运行一次（手动模式）"""
        logger.info("运行手动出题模式...")
        return await self.push_daily_question()


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="每日精进 Agent")
    parser.add_argument(
        "--config",
        default=None,
        help="配置文件路径 (默认: config.yaml)"
    )
    parser.add_argument(
        "--mode",
        choices=["scheduler", "once"],
        default="scheduler",
        help="运行模式: scheduler (定时调度) 或 once (单次运行)"
    )
    parser.add_argument(
        "--domain",
        default=None,
        help="强制指定领域 (仅对 once 模式有效)"
    )

    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)

    # 创建 Agent
    agent = DailyLearningAgent(config)

    # 根据模式运行
    if args.mode == "scheduler":
        await agent.run_scheduler()
    else:
        success = await agent.run_once()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
