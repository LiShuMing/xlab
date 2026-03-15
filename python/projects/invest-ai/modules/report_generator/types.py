"""报告类型定义"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ReportFormat(str, Enum):
    """报告格式"""

    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"


@dataclass
class ReportSection:
    """报告章节"""

    title: str
    content: str
    order: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class Report:
    """投资分析报告"""

    # 基本信息
    stock_code: str
    stock_name: str = ""
    report_id: str = ""

    # 报告内容
    title: str = ""
    summary: str = ""
    sections: list[ReportSection] = field(default_factory=list)

    # 评级和推荐
    rating: str = ""  # 强烈推荐/推荐/中性/谨慎/不推荐
    confidence: str = ""  # 高/中/低
    target_price: Optional[float] = None

    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    model_name: str = ""
    analysis_duration: float = 0.0  # 秒

    # 原始数据
    raw_data: dict = field(default_factory=dict)

    def add_section(self, title: str, content: str, order: int = 0) -> "Report":
        """添加章节"""
        self.sections.append(
            ReportSection(
                title=title,
                content=content,
                order=order or len(self.sections),
            )
        )
        return self

    def get_section(self, title: str) -> Optional[ReportSection]:
        """获取章节"""
        for section in self.sections:
            if section.title == title:
                return section
        return None

    def sort_sections(self) -> "Report":
        """按顺序排序章节"""
        self.sections.sort(key=lambda s: s.order)
        return self
