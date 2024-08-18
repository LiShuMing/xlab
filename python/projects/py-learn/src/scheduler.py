"""
Scheduler 模块 - 定时调度器

基于 APScheduler 实现定时任务调度，
支持每日题目推送、提醒和超时处理。
"""

import asyncio
import logging
from typing import Optional, Callable
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from config import ScheduleConfig


logger = logging.getLogger(__name__)


class Scheduler:
    """
    任务调度器

    管理所有定时任务：
    - 每日 08:00 推送题目
    - 每日 20:00 发送提醒（可选）
    - 每日 23:30 处理超时
    """

    def __init__(self, config: ScheduleConfig):
        """
        初始化调度器

        Args:
            config: 调度配置
        """
        self.config = config
        self.scheduler: Optional[AsyncIOScheduler] = None

        # 回调函数
        self._push_callback: Optional[Callable] = None
        self._reminder_callback: Optional[Callable] = None
        self._timeout_callback: Optional[Callable] = None

    def initialize(self) -> None:
        """初始化调度器"""
        self.scheduler = AsyncIOScheduler(timezone=self.config.timezone)

        # 添加任务
        self._add_jobs()

        # 注册事件监听
        self.scheduler.add_listener(
            self._on_job_executed,
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
        )

    def _add_jobs(self) -> None:
        """添加定时任务"""
        # 1. 每日推送题目
        self.scheduler.add_job(
            self._on_push,
            CronTrigger.from_crontab(f"{self.config.push_time.replace(':', ' ')} * * *"),
            id="daily_push",
            name="每日题目推送",
            replace_existing=True
        )

        # 2. 每日提醒（如果启用）
        if self.config.reminder_enabled:
            self.scheduler.add_job(
                self._on_reminder,
                CronTrigger.from_crontab(f"{self.config.reminder_time.replace(':', ' ')} * * *"),
                id="daily_reminder",
                name="每日提醒",
                replace_existing=True
            )

        # 3. 每日超时处理
        self.scheduler.add_job(
            self._on_timeout,
            CronTrigger(hour=23, minute=30),
            id="daily_timeout",
            name="每日超时处理",
            replace_existing=True
        )

    def _on_job_executed(self, event) -> None:
        """任务执行事件处理"""
        if event.exception:
            logger.error(f"任务 {event.job_id} 执行失败: {event.exception}")
        else:
            logger.info(f"任务 {event.job_id} 执行成功")

    async def _on_push(self) -> None:
        """推送题目任务"""
        logger.info("执行每日题目推送任务")
        if self._push_callback:
            try:
                await self._push_callback()
            except Exception as e:
                logger.error(f"推送任务执行失败: {e}")

    async def _on_reminder(self) -> None:
        """发送提醒任务"""
        logger.info("执行每日提醒任务")
        if self._reminder_callback:
            try:
                await self._reminder_callback()
            except Exception as e:
                logger.error(f"提醒任务执行失败: {e}")

    async def _on_timeout(self) -> None:
        """超时处理任务"""
        logger.info("执行每日超时处理任务")
        if self._timeout_callback:
            try:
                await self._timeout_callback()
            except Exception as e:
                logger.error(f"超时处理任务执行失败: {e}")

    def set_callbacks(
        self,
        push: Optional[Callable] = None,
        reminder: Optional[Callable] = None,
        timeout: Optional[Callable] = None
    ) -> None:
        """
        设置回调函数

        Args:
            push: 推送题目回调
            reminder: 提醒回调
            timeout: 超时处理回调
        """
        self._push_callback = push
        self._reminder_callback = reminder
        self._timeout_callback = timeout

    def start(self) -> None:
        """启动调度器"""
        if not self.scheduler:
            self.initialize()
        self.scheduler.start()
        logger.info("调度器已启动")

    def shutdown(self) -> None:
        """关闭调度器"""
        if self.scheduler:
            self.scheduler.shutdown()
            logger.info("调度器已关闭")

    def get_next_run_time(self, job_id: str) -> Optional[datetime]:
        """
        获取任务下次执行时间

        Args:
            job_id: 任务 ID

        Returns:
            下次执行时间
        """
        if not self.scheduler:
            return None

        job = self.scheduler.get_job(job_id)
        if job:
            return job.next_run_time
        return None


class ManualTrigger:
    """
    手动触发器

    用于手动触发出题等操作。
    """

    @staticmethod
    async def trigger_push(callback: Callable) -> bool:
        """
        手动触发推送

        Args:
            callback: 推送回调函数

        Returns:
            是否成功
        """
        try:
            await callback()
            return True
        except Exception as e:
            logger.error(f"手动触发推送失败: {e}")
            return False
