"""报告构建器"""

import uuid
from datetime import datetime
from typing import Optional

from .types import Report, ReportSection, ReportFormat


class ReportBuilder:
    """报告构建器 - 流式构建报告"""

    def __init__(self):
        self._report = Report(report_id=str(uuid.uuid4())[:8])
        self._section_order = 0

    def set_stock(self, stock_code: str, stock_name: str = "") -> "ReportBuilder":
        """设置股票信息"""
        self._report.stock_code = stock_code
        self._report.stock_name = stock_name
        return self

    def set_title(self, title: str) -> "ReportBuilder":
        """设置报告标题"""
        self._report.title = title
        return self

    def set_summary(self, summary: str) -> "ReportBuilder":
        """设置摘要"""
        self._report.summary = summary
        return self

    def set_rating(self, rating: str, confidence: str = "") -> "ReportBuilder":
        """设置评级"""
        self._report.rating = rating
        self._report.confidence = confidence
        return self

    def set_target_price(self, price: float) -> "ReportBuilder":
        """设置目标价"""
        self._report.target_price = price
        return self

    def add_section(
        self,
        title: str,
        content: str,
        order: Optional[int] = None,
    ) -> "ReportBuilder":
        """添加章节"""
        self._report.sections.append(
            ReportSection(
                title=title,
                content=content,
                order=order if order is not None else self._section_order,
            )
        )
        self._section_order += 1
        return self

    def set_model(self, model_name: str) -> "ReportBuilder":
        """设置模型信息"""
        self._report.model_name = model_name
        return self

    def set_duration(self, duration: float) -> "ReportBuilder":
        """设置分析耗时"""
        self._report.analysis_duration = duration
        return self

    def set_raw_data(self, raw_data: dict) -> "ReportBuilder":
        """设置原始数据"""
        self._report.raw_data = raw_data
        return self

    def build(self) -> Report:
        """构建报告"""
        self._report.sort_sections()
        return self._report

    def reset(self) -> "ReportBuilder":
        """重置构建器"""
        self._report = Report(report_id=str(uuid.uuid4())[:8])
        self._section_order = 0
        return self
