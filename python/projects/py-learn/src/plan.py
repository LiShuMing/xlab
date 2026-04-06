"""
Plan 模块 - 出题规划器

负责决定今天出什么领域、什么 topic、什么难度、什么题型。
基于历史表现、领域轮转策略和自适应算法。
"""

import random
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from db import Database, Domain, Topic, TopicStats


class QuestionType(Enum):
    """题型枚举"""
    CONCEPT = "concept"          # 深度概念题
    DEBUG = "debug"              # 找错/Debug题
    IMPLEMENTATION = "implementation"  # 白板实现题
    TRADEOFF = "tradeoff"        # Tradeoff分析题
    SYSTEM_DESIGN = "system_design"    # 系统设计题
    MANAGEMENT = "management"    # 管理决策题
    PAPER_REVIEW = "paper_review"      # 论文评述题
    ANALYSIS = "analysis"        # 系统分析题


@dataclass
class PlanResult:
    """规划结果"""
    domain: Domain
    topic: Topic
    level: int
    qtype: QuestionType
    context: Dict[str, Any]  # 额外上下文


class TopicSelector:
    """
    Topic 选择器

    使用加权随机选择算法，基于以下因素：
    - 基础权重
    - 薄弱点加成
    - 最近出题惩罚
    - 热点加成
    """

    def __init__(self, db: Database):
        self.db = db

    def select_topic(
        self,
        domain: Domain,
        weak_bonus_weight: float = 2.0,
        recency_penalty_weight: float = 1.0,
        frontier_bonus_weight: float = 1.5
    ) -> Topic:
        """
        为指定领域选择一个 topic

        Args:
            domain: 目标领域
            weak_bonus_weight: 薄弱点加成权重
            recency_penalty_weight: 最近出题惩罚权重
            frontier_bonus_weight: 热点加成权重

        Returns:
            选中的 Topic
        """
        topics = self.db.get_topics_by_domain(domain.id)
        if not topics:
            raise ValueError(f"领域 {domain.id} 没有配置 topics")

        # 计算每个 topic 的分数
        scores = []
        for topic in topics:
            score = self._calculate_topic_score(
                topic,
                weak_bonus_weight,
                recency_penalty_weight,
                frontier_bonus_weight
            )
            scores.append((topic, score))

        # 加权随机选择
        return self._weighted_random_choice(scores)

    def _calculate_topic_score(
        self,
        topic: Topic,
        weak_bonus_weight: float,
        recency_penalty_weight: float,
        frontier_bonus_weight: float
    ) -> float:
        """计算单个 topic 的分数"""
        base_weight = 1.0

        # 获取统计信息
        stats = self.db.get_topic_stats(topic.id)

        # 薄弱点加成：如果平均分低于阈值，增加权重
        weak_bonus = 0.0
        if stats and stats.avg_score > 0:
            if stats.avg_score < 6.0 or stats.is_weak:
                weak_bonus = weak_bonus_weight

        # 最近出题惩罚
        recency_penalty = 0.0
        if stats and stats.last_attempt:
            try:
                last_date = datetime.strptime(stats.last_attempt, "%Y-%m-%d")
                days_since = (datetime.now() - last_date).days
                if days_since < 7:
                    recency_penalty = recency_penalty_weight * (7 - days_since) / 7
            except ValueError:
                pass

        # 热点加成 (v0.1 暂不实现，预留接口)
        frontier_bonus = 0.0

        return base_weight + weak_bonus - recency_penalty + frontier_bonus

    def _weighted_random_choice(
        self,
        items: List[Tuple[Topic, float]]
    ) -> Topic:
        """
        加权随机选择

        Args:
            items: [(topic, score), ...]

        Returns:
            随机选中的 topic
        """
        total_score = sum(score for _, score in items)
        if total_score <= 0:
            # 如果所有分数都是0，均匀随机选择
            return random.choice([item for item, _ in items])

        # 根据权重随机选择
        r = random.uniform(0, total_score)
        cumulative = 0.0
        for topic, score in items:
            cumulative += score
            if r <= cumulative:
                return topic

        # 兜底返回最后一个
        return items[-1][0]


class DifficultyAdapter:
    """
    难度自适应器

    根据历史表现自动调整题目难度。
    """

    def __init__(self, db: Database):
        self.db = db

    def get_adaptive_level(
        self,
        topic: Topic,
        level_up_threshold: float = 9.0,
        level_up_consecutive: int = 2,
        level_down_threshold: float = 4.0,
        level_down_consecutive: int = 2,
        default_level: int = 3
    ) -> int:
        """
        获取自适应难度等级

        Args:
            topic: 主题
            level_up_threshold: 升级阈值
            level_up_consecutive: 连续几次达到阈值才升级
            level_down_threshold: 降级阈值
            level_down_consecutive: 连续几次低于阈值才降级
            default_level: 默认等级（首次出题）

        Returns:
            难度等级 (2-4)
        """
        stats = self.db.get_topic_stats(topic.id)

        if not stats or stats.attempt_count == 0:
            # 首次出题，使用默认值
            return topic.level_default or default_level

        # 获取最近几次的答题记录来判断趋势
        recent_questions = self._get_recent_questions(topic.id, max(level_up_consecutive, level_down_consecutive))

        if len(recent_questions) < 2:
            return stats.current_level

        # 检查是否需要升级
        recent_scores = [q['score'] for q in recent_questions[:level_up_consecutive]]
        if len(recent_scores) >= level_up_consecutive:
            if all(score >= level_up_threshold for score in recent_scores):
                return min(4, stats.current_level + 1)

        # 检查是否需要降级
        if len(recent_scores) >= level_down_consecutive:
            if all(score <= level_down_threshold for score in recent_scores[:level_down_consecutive]):
                return max(2, stats.current_level - 1)

        return stats.current_level

    def _get_recent_questions(self, topic_id: str, limit: int) -> List[Dict[str, Any]]:
        """获取 topic 的最近答题记录"""
        # 这里简化处理，实际应该查询 answers 表
        # 暂时返回空列表，后续完善
        return []


class QuestionTypeSelector:
    """
    题型选择器

    根据领域偏好选择题型。
    """

    # 领域默认题型偏好
    DOMAIN_TYPE_PREFERENCE: Dict[str, Tuple[QuestionType, List[QuestionType]]] = {
        'lang': (QuestionType.CONCEPT, [QuestionType.DEBUG]),
        'algo': (QuestionType.IMPLEMENTATION, [QuestionType.TRADEOFF]),
        'os': (QuestionType.ANALYSIS, [QuestionType.TRADEOFF]),
        'db': (QuestionType.TRADEOFF, [QuestionType.SYSTEM_DESIGN]),
        'arch': (QuestionType.SYSTEM_DESIGN, [QuestionType.MANAGEMENT]),
        'frontier': (QuestionType.PAPER_REVIEW, [QuestionType.CONCEPT]),
    }

    def select_type(
        self,
        domain: Domain,
        randomness: float = 0.3
    ) -> QuestionType:
        """
        为领域选择题型

        Args:
            domain: 领域
            randomness: 随机性概率 (0-1)，避免题型单调

        Returns:
            选中的题型
        """
        preference = self.DOMAIN_TYPE_PREFERENCE.get(
            domain.id,
            (QuestionType.CONCEPT, [])
        )

        main_type, alt_types = preference

        # 有一定概率选择备选题型
        if alt_types and random.random() < randomness:
            return random.choice(alt_types)

        return main_type


class PlanEngine:
    """
    出题规划引擎

    整合领域轮转、topic选择、难度自适应和题型选择。
    """

    # 领域轮转表: 0=周日, 1=周一, ..., 6=周六
    ROTATION_SCHEDULE = {
        1: 'lang',      # Mon: 语言精通
        2: 'algo',      # Tue: 算法解题
        3: 'os',        # Wed: Linux 精通
        4: 'db',        # Thu: OLAP/数据库
        5: 'arch',      # Fri: 大规模架构
        6: 'frontier',  # Sat: 前沿追踪
        0: 'review',    # Sun: 综合复盘
    }

    def __init__(self, db: Database, config: Optional[Dict[str, Any]] = None):
        """
        初始化规划引擎

        Args:
            db: 数据库实例
            config: 配置字典
        """
        self.db = db
        self.config = config or {}

        self.topic_selector = TopicSelector(db)
        self.difficulty_adapter = DifficultyAdapter(db)
        self.type_selector = QuestionTypeSelector()

    def get_today_domain(self) -> Optional[Domain]:
        """获取今天的领域"""
        today = datetime.now().weekday()  # 0=周一, 6=周日
        # 调整为 0=周日, 1=周一, ...
        day_index = (today + 1) % 7

        domain_id = self.ROTATION_SCHEDULE.get(day_index)
        if not domain_id:
            return None

        return self.db.get_domain_by_day(day_index)

    def plan_daily_question(self, override_domain: Optional[str] = None) -> PlanResult:
        """
        规划每日题目

        Args:
            override_domain: 强制指定领域 ID（可选）

        Returns:
            PlanResult 规划结果
        """
        # 1. 确定领域
        if override_domain:
            # TODO: 根据 domain_id 获取 Domain 对象
            domains = self.db.get_all_domains()
            domain = next((d for d in domains if d.id == override_domain), None)
            if not domain:
                raise ValueError(f"未知领域: {override_domain}")
        else:
            domain = self.get_today_domain()
            if not domain:
                # 周日复盘或其他特殊情况
                domain = self._handle_special_day()

        # 2. 选择 topic
        topic = self.topic_selector.select_topic(domain)

        # 3. 确定难度
        level = self.difficulty_adapter.get_adaptive_level(
            topic,
            level_up_threshold=self.config.get('level_up_threshold', 9.0),
            level_up_consecutive=self.config.get('level_up_consecutive', 2),
            level_down_threshold=self.config.get('level_down_threshold', 4.0),
            level_down_consecutive=self.config.get('level_down_consecutive', 2),
        )

        # 4. 选择题型
        qtype = self.type_selector.select_type(domain)

        # 5. 构建上下文
        context = {
            'domain_label': domain.label,
            'topic_name': topic.name,
            'subtopics': topic.subtopics,
            'key_points': topic.key_points,
            'references': topic.references,
        }

        # 获取历史统计
        stats = self.db.get_topic_stats(topic.id)
        if stats:
            context['stats'] = {
                'attempt_count': stats.attempt_count,
                'avg_score': stats.avg_score,
                'last_score': stats.last_score,
                'is_weak': stats.is_weak,
            }

        return PlanResult(
            domain=domain,
            topic=topic,
            level=level,
            qtype=qtype,
            context=context
        )

    def _handle_special_day(self) -> Domain:
        """处理特殊日期（如周日复盘）"""
        # 周日复盘：优先选择薄弱点
        weak_topics = self.db.get_weak_topics()

        if weak_topics:
            # 从薄弱点中随机选择一个
            topic_id, _ = random.choice(weak_topics)
            topic = self.db.get_topic_by_id(topic_id)
            if topic:
                # 返回该 topic 所属的领域
                domains = self.db.get_all_domains()
                domain = next((d for d in domains if d.id == topic.domain_id), None)
                if domain:
                    return domain

        # 如果没有薄弱点，随机选择一个领域
        domains = self.db.get_all_domains()
        return random.choice(domains)


def plan_daily(
    db: Database,
    config: Optional[Dict[str, Any]] = None,
    override_domain: Optional[str] = None
) -> PlanResult:
    """
    便捷的每日规划函数

    Args:
        db: 数据库实例
        config: 配置字典
        override_domain: 强制指定领域

    Returns:
        PlanResult
    """
    engine = PlanEngine(db, config)
    return engine.plan_daily_question(override_domain)
