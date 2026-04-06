"""
MemoryReader - 记忆读取工具

从 SQLite 数据库读取历史记录和统计信息。
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from db import Database


@dataclass
class TopicHistory:
    """主题历史记录"""
    topic_id: str
    attempt_count: int
    avg_score: float
    last_attempt: Optional[str]
    current_level: int
    is_weak: bool
    recent_scores: List[float]


class MemoryReader:
    """
    记忆读取工具

    提供对历史答题记录和统计信息的查询接口。
    """

    def __init__(self, db: Database):
        """
        初始化工具

        Args:
            db: 数据库实例
        """
        self.db = db

    def get_topic_history(self, topic_id: str) -> TopicHistory:
        """
        获取主题历史

        Args:
            topic_id: 主题 ID

        Returns:
            主题历史记录
        """
        stats = self.db.get_topic_stats(topic_id)

        if not stats:
            return TopicHistory(
                topic_id=topic_id,
                attempt_count=0,
                avg_score=0.0,
                last_attempt=None,
                current_level=3,
                is_weak=False,
                recent_scores=[]
            )

        # 获取最近几次的得分
        recent_scores = self._get_recent_scores(topic_id, limit=5)

        return TopicHistory(
            topic_id=topic_id,
            attempt_count=stats.attempt_count,
            avg_score=stats.avg_score,
            last_attempt=stats.last_attempt,
            current_level=stats.current_level,
            is_weak=stats.is_weak,
            recent_scores=recent_scores
        )

    def _get_recent_scores(self, topic_id: str, limit: int = 5) -> List[float]:
        """获取主题最近几次的得分"""
        # 这里简化实现，实际应该从 answers 表查询
        # 由于 db.py 中未实现相关查询，先返回空列表
        return []

    def get_weak_topics(self) -> List[Dict[str, Any]]:
        """
        获取所有薄弱主题

        Returns:
            薄弱主题列表
        """
        weak = self.db.get_weak_topics()
        result = []
        for topic_id, stats in weak:
            topic = self.db.get_topic_by_id(topic_id)
            if topic:
                result.append({
                    'topic_id': topic_id,
                    'name': topic.name,
                    'domain_id': topic.domain_id,
                    'avg_score': stats.avg_score,
                    'attempt_count': stats.attempt_count,
                })
        return result

    def get_recent_questions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近的题目

        Args:
            limit: 数量限制

        Returns:
            题目列表
        """
        questions = self.db.get_recent_questions(limit)
        return [
            {
                'id': q.id,
                'date': q.date,
                'topic_id': q.topic_id,
                'level': q.level,
                'qtype': q.qtype,
                'status': q.status,
                'main': q.question_json.get('main', '')[:100] + '...' if len(q.question_json.get('main', '')) > 100 else q.question_json.get('main', ''),
            }
            for q in questions
        ]

    def get_weekly_progress(self) -> Dict[str, Any]:
        """
        获取本周进度

        Returns:
            进度信息字典
        """
        return self.db.get_weekly_summary()

    def check_duplicate_question(
        self,
        topic_id: str,
        question_main: str,
        similarity_threshold: float = 0.8
    ) -> bool:
        """
        检查题目是否重复

        Args:
            topic_id: 主题 ID
            question_main: 题目内容
            similarity_threshold: 相似度阈值

        Returns:
            是否重复
        """
        # 简化实现：检查最近10题中是否有同一 topic 的题目
        recent = self.db.get_recent_questions(10)
        for q in recent:
            if q.topic_id == topic_id:
                # 如果同一 topic 在最近的题目中，视为可能重复
                return True
        return False


class ConversationHistoryReader:
    """
    对话历史读取工具

    读取最近对话摘要，用于防止重复出题。
    """

    def __init__(self, db: Database):
        """
        初始化工具

        Args:
            db: 数据库实例
        """
        self.db = db

    def get_recent_summaries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近的对话摘要

        Args:
            limit: 数量限制

        Returns:
            对话摘要列表
        """
        # v0.1 版本简化实现，从 questions 表获取
        questions = self.db.get_recent_questions(limit)
        return [
            {
                'date': q.date,
                'topic_id': q.topic_id,
                'level': q.level,
                'status': q.status,
            }
            for q in questions
        ]
