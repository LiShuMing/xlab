from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from tech_radar.domain import Signal
from tech_radar.publishers.markdown import MarkdownPublisher


class MarkdownPublisherTest(unittest.TestCase):
    def test_renders_diverse_candidate_lists(self) -> None:
        topics = ["数据库与查询引擎", "Rust 与 C++", "存储与硬件", "Linux 与系统工程"]
        signals = [
            Signal(
                external_id=str(index),
                source_id="discovery",
                platform="twitter",
                object_type="search",
                author=f"author{index % 6}",
                title=f"Technical candidate {index}",
                content=f"Detailed technical candidate content {index}",
                url=f"https://x.com/author/status/{index}",
                published_at=None,
                priority=50,
                score=100 - index,
                annotations={
                    "topic": topics[index % len(topics)],
                    "summary_zh": f"候选摘要 {index}",
                    "why_it_matters": "包含可验证的系统工程信号。",
                    "writing_angle": "从实现、性能和边界条件展开。",
                    "relevance": 90 - index,
                },
            )
            for index in range(12)
        ]
        with tempfile.TemporaryDirectory() as temporary_directory:
            publisher = MarkdownPublisher(
                "daily",
                Path(temporary_directory),
                priority_read_limit=8,
                writing_candidate_limit=10,
                topic_candidate_limit=3,
                people_limit=6,
                max_top_picks_per_author=2,
                max_top_picks_per_topic=2,
            )

            result = publisher.publish(signals, local_date="2026-10-07")
            content = Path(result.location).read_text(encoding="utf-8")

        top_picks = content.split("## 今日 Top Picks", 1)[1].split(
            "## 主题候选池", 1
        )[0]
        self.assertEqual(8, len(re.findall(r"^\d+\. ", top_picks, re.MULTILINE)))
        self.assertIn("## 主题候选池", content)
        self.assertIn("## 值得持续关注的人", content)
        self.assertIn("## 可写作选题", content)
        self.assertEqual(12, len(result.signal_keys))


if __name__ == "__main__":
    unittest.main()
