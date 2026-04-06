"""Tests for statistics and cost extraction prompts."""

import pytest


class TestStatsPromptsExist:
    """Tests for statistics and cost extraction prompts existence and format."""

    def test_stats_extraction_prompt_exists(self):
        """STATS_EXTRACTION_PROMPT exists and is non-empty."""
        from optimizer_analysis.prompts import STATS_EXTRACTION_PROMPT

        assert isinstance(STATS_EXTRACTION_PROMPT, str)
        assert len(STATS_EXTRACTION_PROMPT) > 0

    def test_cost_extraction_prompt_exists(self):
        """COST_EXTRACTION_PROMPT exists and is non-empty."""
        from optimizer_analysis.prompts import COST_EXTRACTION_PROMPT

        assert isinstance(COST_EXTRACTION_PROMPT, str)
        assert len(COST_EXTRACTION_PROMPT) > 0

    def test_stats_extraction_prompt_contains_json_schema(self):
        """Stats prompt includes JSON output format specification."""
        from optimizer_analysis.prompts import STATS_EXTRACTION_PROMPT

        # Should mention JSON format
        assert "JSON" in STATS_EXTRACTION_PROMPT
        # Should include key fields
        assert "stats_source" in STATS_EXTRACTION_PROMPT
        assert "stats_objects" in STATS_EXTRACTION_PROMPT
        assert "stats_granularity" in STATS_EXTRACTION_PROMPT

    def test_cost_extraction_prompt_contains_json_schema(self):
        """Cost prompt includes JSON output format specification."""
        from optimizer_analysis.prompts import COST_EXTRACTION_PROMPT

        # Should mention JSON format
        assert "JSON" in COST_EXTRACTION_PROMPT
        # Should include key fields
        assert "cost_formula_location" in COST_EXTRACTION_PROMPT
        assert "cost_dimensions" in COST_EXTRACTION_PROMPT
        assert "operator_costs" in COST_EXTRACTION_PROMPT

    def test_stats_extraction_prompt_has_placeholders(self):
        """Stats prompt template has required placeholders."""
        from optimizer_analysis.prompts import STATS_EXTRACTION_PROMPT

        # Should have placeholders for code and engine
        assert "{code}" in STATS_EXTRACTION_PROMPT
        assert "{engine}" in STATS_EXTRACTION_PROMPT

    def test_cost_extraction_prompt_has_placeholders(self):
        """Cost prompt template has required placeholders."""
        from optimizer_analysis.prompts import COST_EXTRACTION_PROMPT

        # Should have placeholders for code and engine
        assert "{code}" in COST_EXTRACTION_PROMPT
        assert "{engine}" in COST_EXTRACTION_PROMPT

    def test_stats_prompt_mentions_statistics(self):
        """Stats prompt mentions statistics-related concepts."""
        from optimizer_analysis.prompts import STATS_EXTRACTION_PROMPT

        # Should mention statistics-related concepts
        assert "statistics" in STATS_EXTRACTION_PROMPT.lower()
        assert "histogram" in STATS_EXTRACTION_PROMPT.lower() or "ndv" in STATS_EXTRACTION_PROMPT.lower()

    def test_cost_prompt_mentions_cost_model(self):
        """Cost prompt mentions cost model-related concepts."""
        from optimizer_analysis.prompts import COST_EXTRACTION_PROMPT

        # Should mention cost-related concepts
        assert "cost" in COST_EXTRACTION_PROMPT.lower()

    def test_prompts_module_exports_stats_prompts(self):
        """Prompts __init__ exports stats and cost prompts."""
        from optimizer_analysis.prompts import __all__

        expected_exports = [
            "STATS_EXTRACTION_PROMPT",
            "COST_EXTRACTION_PROMPT",
        ]

        for export in expected_exports:
            assert export in __all__

    def test_stats_prompt_can_format(self):
        """Stats prompt can be formatted with placeholders."""
        from optimizer_analysis.prompts import STATS_EXTRACTION_PROMPT

        formatted = STATS_EXTRACTION_PROMPT.format(
            engine="clickhouse",
            code="public class StatisticsCollector {}"
        )

        assert "clickhouse" in formatted
        assert "public class StatisticsCollector" in formatted

    def test_cost_prompt_can_format(self):
        """Cost prompt can be formatted with placeholders."""
        from optimizer_analysis.prompts import COST_EXTRACTION_PROMPT

        formatted = COST_EXTRACTION_PROMPT.format(
            engine="starrocks",
            code="public class CostCalculator {}"
        )

        assert "starrocks" in formatted
        assert "public class CostCalculator" in formatted

    def test_stats_prompt_mentions_granularity_levels(self):
        """Stats prompt mentions granularity levels."""
        from optimizer_analysis.prompts import STATS_EXTRACTION_PROMPT

        # Should mention granularity options
        assert "table" in STATS_EXTRACTION_PROMPT or "column" in STATS_EXTRACTION_PROMPT
        assert "partition" in STATS_EXTRACTION_PROMPT or "histogram" in STATS_EXTRACTION_PROMPT

    def test_cost_prompt_mentions_dimensions(self):
        """Cost prompt mentions cost dimensions."""
        from optimizer_analysis.prompts import COST_EXTRACTION_PROMPT

        # Should mention cost dimension concepts
        assert "CPU" in COST_EXTRACTION_PROMPT or "I/O" in COST_EXTRACTION_PROMPT or "memory" in COST_EXTRACTION_PROMPT.lower()

    def test_stats_prompt_includes_evidence_field(self):
        """Stats prompt includes evidence field in schema."""
        from optimizer_analysis.prompts import STATS_EXTRACTION_PROMPT

        assert "evidence" in STATS_EXTRACTION_PROMPT

    def test_cost_prompt_includes_evidence_field(self):
        """Cost prompt includes evidence field in schema."""
        from optimizer_analysis.prompts import COST_EXTRACTION_PROMPT

        assert "evidence" in COST_EXTRACTION_PROMPT