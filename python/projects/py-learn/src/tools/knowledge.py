"""
KnowledgeGraphTool - 知识图谱工具

从 topics.yaml 加载知识图谱，提供主题相关信息查询。
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

import yaml


@dataclass
class SubTopic:
    """子主题"""
    name: str
    key_points: List[str] = field(default_factory=list)


@dataclass
class KnowledgeTopic:
    """知识图谱中的主题"""
    id: str
    domain_id: str
    name: str
    level_default: int
    tags: List[str] = field(default_factory=list)
    subtopics: List[str] = field(default_factory=list)
    key_points: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)


@dataclass
class KnowledgeDomain:
    """知识领域"""
    id: str
    label: str
    rotation_day: int
    topics: List[KnowledgeTopic] = field(default_factory=list)


class KnowledgeGraph:
    """
    知识图谱类

    管理领域和主题的层次结构，提供查询接口。
    """

    def __init__(self, topics_file: str):
        """
        初始化知识图谱

        Args:
            topics_file: topics.yaml 文件路径
        """
        self.topics_file = Path(topics_file)
        self.domains: Dict[str, KnowledgeDomain] = {}
        self.topics: Dict[str, KnowledgeTopic] = {}
        self._load()

    def _load(self) -> None:
        """从 YAML 文件加载知识图谱"""
        if not self.topics_file.exists():
            raise FileNotFoundError(f"知识图谱文件不存在: {self.topics_file}")

        with open(self.topics_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        for domain_data in data.get('domains', []):
            domain = KnowledgeDomain(
                id=domain_data['id'],
                label=domain_data['label'],
                rotation_day=domain_data.get('rotation_day', 0)
            )

            for topic_data in domain_data.get('topics', []):
                topic = KnowledgeTopic(
                    id=topic_data['id'],
                    domain_id=domain.id,
                    name=topic_data['name'],
                    level_default=topic_data.get('level_default', 3),
                    tags=topic_data.get('tags', []),
                    subtopics=topic_data.get('subtopics', []),
                    key_points=topic_data.get('key_points', []),
                    references=topic_data.get('references', [])
                )
                domain.topics.append(topic)
                self.topics[topic.id] = topic

            self.domains[domain.id] = domain

    def get_domain(self, domain_id: str) -> Optional[KnowledgeDomain]:
        """根据 ID 获取领域"""
        return self.domains.get(domain_id)

    def get_topic(self, topic_id: str) -> Optional[KnowledgeTopic]:
        """根据 ID 获取主题"""
        return self.topics.get(topic_id)

    def get_topics_by_domain(self, domain_id: str) -> List[KnowledgeTopic]:
        """获取领域下的所有主题"""
        domain = self.domains.get(domain_id)
        if domain:
            return domain.topics
        return []

    def get_all_domains(self) -> List[KnowledgeDomain]:
        """获取所有领域"""
        return list(self.domains.values())

    def get_context_for_generation(self, topic_id: str) -> Dict[str, Any]:
        """
        获取用于题目生成的上下文

        Args:
            topic_id: 主题 ID

        Returns:
            包含主题相关信息的字典
        """
        topic = self.get_topic(topic_id)
        if not topic:
            return {}

        domain = self.get_domain(topic.domain_id)

        return {
            'domain': {
                'id': domain.id if domain else '',
                'label': domain.label if domain else '',
            },
            'topic': {
                'id': topic.id,
                'name': topic.name,
                'level_default': topic.level_default,
            },
            'subtopics': topic.subtopics,
            'key_points': topic.key_points,
            'references': topic.references,
        }


class KnowledgeGraphTool:
    """
    知识图谱工具

    封装 KnowledgeGraph，提供标准工具接口。
    """

    def __init__(self, topics_file: str):
        """
        初始化工具

        Args:
            topics_file: topics.yaml 文件路径
        """
        self.graph = KnowledgeGraph(topics_file)

    def get_topic_context(self, topic_id: str) -> Dict[str, Any]:
        """
        获取主题上下文（工具主接口）

        Args:
            topic_id: 主题 ID

        Returns:
            主题上下文信息
        """
        return self.graph.get_context_for_generation(topic_id)

    def get_all_topics(self) -> List[Dict[str, Any]]:
        """获取所有主题列表"""
        return [
            {
                'id': t.id,
                'name': t.name,
                'domain_id': t.domain_id,
                'level_default': t.level_default,
            }
            for t in self.graph.topics.values()
        ]
