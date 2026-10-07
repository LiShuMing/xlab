from __future__ import annotations

import unittest

from tech_radar.domain import Signal
from tech_radar.processors import KeywordScorer, QualityFilter


def make_signal(
    external_id: str,
    content: str,
    *,
    author: str = "author",
    priority: int = 50,
) -> Signal:
    return Signal(
        external_id=external_id,
        source_id="source",
        platform="twitter",
        object_type="search",
        author=author,
        title=content,
        content=content,
        url=f"https://x.com/{author}/status/{external_id}",
        published_at=None,
        priority=priority,
    )


class ProcessorTest(unittest.TestCase):
    def test_quality_filter_deduplicates_and_filters_noise(self) -> None:
        processor = QualityFilter(
            minimum_length=20,
            negative_keywords=["giveaway"],
            protect_priority=100,
        )
        signals = [
            make_signal("1", "Detailed database optimizer architecture update"),
            make_signal("2", "Detailed database optimizer architecture update"),
            make_signal("3", "Database giveaway promotion with no technical details"),
            make_signal("4", "short"),
            make_signal("5", "short", priority=100),
        ]

        result = processor.process(signals)

        self.assertEqual(["1", "5"], [signal.external_id for signal in result])

    def test_trusted_author_weight_improves_ranking(self) -> None:
        processor = KeywordScorer(
            [], priority_weight=0, author_weights={"trusted": 50}
        )

        ranked = processor.process(
            [
                make_signal("1", "Database update", author="other"),
                make_signal("2", "Database update two", author="trusted"),
            ]
        )

        self.assertEqual("trusted", ranked[0].author)

    def test_personal_items_still_require_technical_relevance(self) -> None:
        processor = QualityFilter(
            personal_relevance_keywords=["rust", "database"],
            hard_negative_keywords=["nsfw"],
        )
        signals = [
            make_signal(
                "technical",
                "Rust compiler performance analysis",
                priority=100,
            ),
            make_signal(
                "unrelated",
                "A general entertainment discussion",
                priority=100,
            ),
            make_signal(
                "unsafe",
                "NSFW Rust themed promotion",
                priority=100,
            ),
        ]

        result = processor.process(signals)

        self.assertEqual(
            ["technical"], [signal.external_id for signal in result]
        )

    def test_required_keywords_use_boundaries_for_short_terms(self) -> None:
        processor = QualityFilter(required_keywords=["ai", "database"])
        signals = [
            make_signal("ai", "AI compiler optimization update"),
            make_signal("database", "Database execution engine update"),
            make_signal("false-positive", "Daily entertainment update"),
        ]

        result = processor.process(signals)

        self.assertEqual(
            ["ai", "database"],
            [signal.external_id for signal in result],
        )


if __name__ == "__main__":
    unittest.main()
