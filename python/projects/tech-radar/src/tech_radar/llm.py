from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from tech_radar.domain import Signal


ENRICHMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item_key": {"type": "string"},
                    "topic": {"type": "string"},
                    "summary_zh": {"type": "string"},
                    "why_it_matters": {"type": "string"},
                    "writing_angle": {"type": "string"},
                    "relevance": {"type": "integer"},
                },
                "required": [
                    "item_key",
                    "topic",
                    "summary_zh",
                    "why_it_matters",
                    "writing_angle",
                    "relevance",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """你是资深数据库内核与系统工程技术编辑。
对用户主动点赞的技术内容做保守、可追溯的整理。不得补造原文没有的事实。
topic 使用简洁中文技术分类；summary_zh 用一到两句话概括原文；
why_it_matters 解释它对数据库、系统软件或工程实践的潜在价值；
writing_angle 给出一个可以继续核验的技术写作角度；relevance 为 0 到 100。
必须为每个输入 item_key 返回且只返回一项。"""


class OpenAIEnricher:
    def __init__(
        self,
        client: Any,
        model: str,
        *,
        batch_size: int = 10,
        relevance_weight: float = 0.5,
        fail_open: bool = True,
    ) -> None:
        if not model:
            raise ValueError("processing.openai.model is required when enabled")
        if not 1 <= batch_size <= 50:
            raise ValueError("processing.openai.batch_size must be between 1 and 50")
        self.client = client
        self.model = model
        self.batch_size = batch_size
        self.relevance_weight = relevance_weight
        self.fail_open = fail_open

    def process(self, signals: Sequence[Signal]) -> list[Signal]:
        result: list[Signal] = []
        for start in range(0, len(signals), self.batch_size):
            batch = list(signals[start : start + self.batch_size])
            try:
                result.extend(self._enrich_batch(batch))
            except Exception:
                if not self.fail_open:
                    raise
                result.extend(batch)
        return sorted(result, key=lambda item: item.score, reverse=True)

    def _enrich_batch(self, signals: list[Signal]) -> list[Signal]:
        payload = [
            {
                "item_key": _item_key(signal),
                "platform": signal.platform,
                "author": signal.author,
                "title": signal.title[:500],
                "content": signal.content[:2000],
                "tags": list(signal.tags),
                "priority": signal.priority,
                "metrics": dict(signal.metrics),
            }
            for signal in signals
        ]
        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False),
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "tech_radar_enrichment",
                    "strict": True,
                    "schema": ENRICHMENT_SCHEMA,
                }
            },
        )
        parsed = json.loads(response.output_text)
        items = parsed.get("items", [])
        by_key = {
            str(item.get("item_key")): item
            for item in items
            if isinstance(item, dict)
        }
        enriched: list[Signal] = []
        for signal in signals:
            item = by_key.get(_item_key(signal))
            if item is None:
                enriched.append(signal)
                continue
            relevance = max(0, min(100, int(item["relevance"])))
            annotated = signal.with_annotations(
                topic=str(item["topic"]),
                summary_zh=str(item["summary_zh"]),
                why_it_matters=str(item["why_it_matters"]),
                writing_angle=str(item["writing_angle"]),
                relevance=relevance,
                enrichment="openai",
            )
            enriched.append(
                annotated.with_score(signal.score + relevance * self.relevance_weight)
            )
        return enriched


def _item_key(signal: Signal) -> str:
    return f"{signal.platform}:{signal.external_id}"


def create_openai_enricher(options: dict[str, Any]):
    section = options.get("openai", {})
    if not isinstance(section, dict):
        raise ValueError("processing.openai must be a table")
    if not bool(section.get("enabled", False)):
        from tech_radar.processors import PassthroughProcessor

        return PassthroughProcessor()
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "OpenAI enrichment requires `pip install -e '.[llm]'`"
        ) from exc
    return OpenAIEnricher(
        OpenAI(),
        str(section.get("model", "")),
        batch_size=int(section.get("batch_size", 10)),
        relevance_weight=float(section.get("relevance_weight", 0.5)),
        fail_open=bool(section.get("fail_open", True)),
    )
