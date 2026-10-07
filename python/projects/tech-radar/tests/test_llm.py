from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from tech_radar.domain import Signal
from tech_radar.llm import OpenAIEnricher


class FakeResponses:
    def __init__(self) -> None:
        self.request = None

    def create(self, **kwargs):
        self.request = kwargs
        output = {
            "items": [
                {
                    "item_key": "twitter:42",
                    "topic": "数据库与查询引擎",
                    "summary_zh": "新的向量化执行优化进入数据库主线。",
                    "why_it_matters": "可能降低分析查询的 CPU 成本。",
                    "writing_angle": "对比优化前后的执行路径与基准数据。",
                    "relevance": 88,
                }
            ]
        }
        return SimpleNamespace(output_text=json.dumps(output, ensure_ascii=False))


class OpenAIEnricherTest(unittest.TestCase):
    def test_structured_enrichment_is_merged(self) -> None:
        responses = FakeResponses()
        client = SimpleNamespace(responses=responses)
        processor = OpenAIEnricher(client, "test-model", relevance_weight=0.5)
        signal = Signal(
            external_id="42",
            source_id="x-liked",
            platform="twitter",
            object_type="likes",
            author="database_author",
            title="Vectorized execution update",
            content="A vectorized execution optimization landed.",
            url="https://x.com/database_author/status/42",
            published_at=None,
            priority=100,
            score=200.0,
        )

        enriched = processor.process([signal])[0]

        self.assertEqual("数据库与查询引擎", enriched.annotations["topic"])
        self.assertEqual("openai", enriched.annotations["enrichment"])
        self.assertEqual(244.0, enriched.score)
        self.assertEqual("json_schema", responses.request["text"]["format"]["type"])


if __name__ == "__main__":
    unittest.main()
