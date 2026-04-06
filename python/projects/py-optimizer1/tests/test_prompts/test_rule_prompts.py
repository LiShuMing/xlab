"""Tests for rule extraction prompts."""

import pytest


class TestRulePromptsExist:
    """Tests for rule extraction prompts existence and format."""

    def test_rule_extraction_prompts_exist(self):
        """All required rule extraction prompts exist."""
        from optimizer_analysis.prompts import (
            RULE_EXTRACTION_SYSTEM_PROMPT,
            RULE_EXTRACTION_USER_PROMPT,
            RBO_RULE_PROMPT,
            CBO_RULE_PROMPT,
        )

        # Verify prompts are non-empty strings
        assert isinstance(RULE_EXTRACTION_SYSTEM_PROMPT, str)
        assert len(RULE_EXTRACTION_SYSTEM_PROMPT) > 0

        assert isinstance(RULE_EXTRACTION_USER_PROMPT, str)
        assert len(RULE_EXTRACTION_USER_PROMPT) > 0

        assert isinstance(RBO_RULE_PROMPT, str)
        assert len(RBO_RULE_PROMPT) > 0

        assert isinstance(CBO_RULE_PROMPT, str)
        assert len(CBO_RULE_PROMPT) > 0

    def test_rule_extraction_system_prompt_contains_json_schema(self):
        """System prompt includes JSON output format specification."""
        from optimizer_analysis.prompts import RULE_EXTRACTION_SYSTEM_PROMPT

        # Should mention JSON format
        assert "JSON" in RULE_EXTRACTION_SYSTEM_PROMPT
        # Should include key fields
        assert "rule_id" in RULE_EXTRACTION_SYSTEM_PROMPT
        assert "rule_name" in RULE_EXTRACTION_SYSTEM_PROMPT
        assert "rule_category" in RULE_EXTRACTION_SYSTEM_PROMPT

    def test_rule_extraction_user_prompt_has_placeholders(self):
        """User prompt template has required placeholders."""
        from optimizer_analysis.prompts import RULE_EXTRACTION_USER_PROMPT

        # Should have placeholders for code, engine, category
        assert "{code}" in RULE_EXTRACTION_USER_PROMPT
        assert "{engine}" in RULE_EXTRACTION_USER_PROMPT
        assert "{category}" in RULE_EXTRACTION_USER_PROMPT

    def test_rbo_rule_prompt_has_placeholders(self):
        """RBO prompt template has required placeholders."""
        from optimizer_analysis.prompts import RBO_RULE_PROMPT

        assert "{code}" in RBO_RULE_PROMPT
        assert "{engine}" in RBO_RULE_PROMPT

    def test_cbo_rule_prompt_has_placeholders(self):
        """CBO prompt template has required placeholders."""
        from optimizer_analysis.prompts import CBO_RULE_PROMPT

        assert "{code}" in CBO_RULE_PROMPT
        assert "{engine}" in CBO_RULE_PROMPT

    def test_rbo_prompt_mentions_rule_based(self):
        """RBO prompt mentions RBO characteristics."""
        from optimizer_analysis.prompts import RBO_RULE_PROMPT

        # Should mention RBO-related concepts
        assert "Rule-Based" in RBO_RULE_PROMPT or "RBO" in RBO_RULE_PROMPT
        assert "heuristic" in RBO_RULE_PROMPT.lower()

    def test_cbo_prompt_mentions_cost_based(self):
        """CBO prompt mentions CBO characteristics."""
        from optimizer_analysis.prompts import CBO_RULE_PROMPT

        # Should mention CBO-related concepts
        assert "Cost-Based" in CBO_RULE_PROMPT or "CBO" in CBO_RULE_PROMPT
        assert "statistics" in CBO_RULE_PROMPT.lower() or "cost" in CBO_RULE_PROMPT.lower()

    def test_prompts_module_exports_all_prompts(self):
        """Prompts __init__ exports all required prompts."""
        from optimizer_analysis.prompts import __all__

        expected_exports = [
            "RULE_EXTRACTION_SYSTEM_PROMPT",
            "RULE_EXTRACTION_USER_PROMPT",
            "RBO_RULE_PROMPT",
            "CBO_RULE_PROMPT",
        ]

        for export in expected_exports:
            assert export in __all__

    def test_prompts_can_format_user_prompt(self):
        """User prompt can be formatted with placeholders."""
        from optimizer_analysis.prompts import RULE_EXTRACTION_USER_PROMPT

        formatted = RULE_EXTRACTION_USER_PROMPT.format(
            engine="clickhouse",
            category="rbo",
            code="SELECT * FROM table"
        )

        assert "clickhouse" in formatted
        assert "rbo" in formatted
        assert "SELECT * FROM table" in formatted

    def test_prompts_can_format_rbo_prompt(self):
        """RBO prompt can be formatted with placeholders."""
        from optimizer_analysis.prompts import RBO_RULE_PROMPT

        formatted = RBO_RULE_PROMPT.format(
            engine="starrocks",
            code="class FilterPushdownRule"
        )

        assert "starrocks" in formatted
        assert "class FilterPushdownRule" in formatted

    def test_prompts_can_format_cbo_prompt(self):
        """CBO prompt can be formatted with placeholders."""
        from optimizer_analysis.prompts import CBO_RULE_PROMPT

        formatted = CBO_RULE_PROMPT.format(
            engine="postgres",
            code="class CostBasedOptimizer"
        )

        assert "postgres" in formatted
        assert "class CostBasedOptimizer" in formatted