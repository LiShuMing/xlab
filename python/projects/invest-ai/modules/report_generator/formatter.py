"""报告格式化器"""

from .types import Report, ReportFormat


class ReportFormatter:
    """报告格式化器 - 将报告转换为不同格式"""

    @staticmethod
    def format(report: Report, format_type: ReportFormat = ReportFormat.MARKDOWN) -> str:
        """格式化报告"""
        if format_type == ReportFormat.MARKDOWN:
            return ReportFormatter._to_markdown(report)
        elif format_type == ReportFormat.HTML:
            return ReportFormatter._to_html(report)
        elif format_type == ReportFormat.JSON:
            return ReportFormatter._to_json(report)
        else:
            return ReportFormatter._to_markdown(report)

    @staticmethod
    def _to_markdown(report: Report) -> str:
        """转换为 Markdown 格式"""
        md = ""

        # 标题
        title = report.title or f"{report.stock_name} ({report.stock_code}) 投资分析报告"
        md += f"# {title}\n\n"

        # 报告元信息
        md += f"**生成时间**: {report.created_at.strftime('%Y-%m-%d %H:%M')}\n"
        md += f"**分析模型**: {report.model_name}\n"
        md += f"**分析耗时**: {report.analysis_duration:.2f}秒\n\n"

        # 摘要
        if report.summary:
            md += f"## 摘要\n\n{report.summary}\n\n"

        # 评级
        if report.rating:
            md += "## 投资评级\n\n"
            rating_emoji = {
                "强烈推荐": "🔥",
                "推荐": "👍",
                "中性": "😐",
                "谨慎": "⚠️",
                "不推荐": "❌",
            }
            emoji = rating_emoji.get(report.rating, "📊")
            md += f"| 项目 | 评估 |\n|------|------|\n"
            md += f"| 综合评级 | {emoji} {report.rating} |\n"
            if report.confidence:
                md += f"| 置信度 | {report.confidence} |\n"
            if report.target_price:
                md += f"| 目标价 | ${report.target_price:.2f} |\n"
            md += "\n"

        # 正文章节
        md += "## 详细分析\n\n"
        for section in report.sections:
            md += f"### {section.title}\n\n"
            md += f"{section.content}\n\n"

        # 免责声明
        md += "---\n\n"
        md += "## 免责声明\n\n"
        md += "本报告由 AI 生成，仅供参考，不构成投资建议。投资有风险，入市需谨慎。\n"

        return md

    @staticmethod
    def _to_html(report: Report) -> str:
        """转换为 HTML 格式"""
        import markdown

        md_content = ReportFormatter._to_markdown(report)
        html_body = markdown.markdown(
            md_content,
            extensions=["tables", "fenced_code", "toc"],
        )

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report.title or '投资分析报告'}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.6; }}
        h1 {{ color: #1a1a1a; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #333; margin-top: 30px; }}
        h3 {{ color: #555; }}
        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
        th {{ background-color: #f5f5f5; }}
        .summary {{ background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 20px 0; }}
        .rating {{ background: #fff3cd; padding: 15px; border-radius: 8px; }}
        .disclaimer {{ color: #6c757d; font-size: 0.9em; margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; }}
    </style>
</head>
<body>
    {html_body}
</body>
</html>"""
        return html

    @staticmethod
    def _to_json(report: Report) -> str:
        """转换为 JSON 格式"""
        import json

        data = {
            "report_id": report.report_id,
            "stock_code": report.stock_code,
            "stock_name": report.stock_name,
            "title": report.title,
            "summary": report.summary,
            "rating": report.rating,
            "confidence": report.confidence,
            "target_price": report.target_price,
            "created_at": report.created_at.isoformat(),
            "model_name": report.model_name,
            "analysis_duration": report.analysis_duration,
            "sections": [
                {"title": s.title, "content": s.content, "order": s.order}
                for s in report.sections
            ],
        }
        return json.dumps(data, ensure_ascii=False, indent=2)
