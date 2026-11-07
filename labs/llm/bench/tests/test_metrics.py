"""Tests for math and code metrics."""

from __future__ import annotations

import pytest

from llm_benchmark.metrics.math_metrics import exact_match, math_score, numeric_match
from llm_benchmark.metrics.code_metrics import pass_at_k, compute_pass_at_k_scores


class TestExactMatch:
    def test_identical_strings(self):
        assert exact_match("42", "42")

    def test_whitespace_normalized(self):
        assert exact_match(" 42 ", "42")

    def test_case_insensitive(self):
        assert exact_match("HELLO", "hello")

    def test_different_strings(self):
        assert not exact_match("42", "43")

    def test_boxed_extraction(self):
        """MATH-style \\boxed{} answer extraction."""
        prediction = "Therefore, the answer is \\boxed{3x + 5}."
        assert exact_match(prediction, "3x+5")

    def test_boxed_extraction_no_match(self):
        prediction = "The answer is 42"
        assert not exact_match(prediction, "43")


class TestNumericMatch:
    def test_exact_numeric(self):
        assert numeric_match("42", "42")

    def test_tolerance(self):
        assert numeric_match("3.14159", "3.1416", tolerance=1e-3)

    def test_extracts_number_from_text(self):
        assert numeric_match("The answer is 42.", "42")

    def test_negative_numbers(self):
        assert numeric_match("-5", "answer is -5")

    def test_scientific_notation(self):
        assert numeric_match("1.5e10", "15000000000")

    def test_fraction(self):
        assert numeric_match("3/4", "0.75")

    def test_no_reference_numbers(self):
        """Falls back to exact match when no reference numbers."""
        assert numeric_match("hello", "hello")
        assert not numeric_match("hello", "world")


class TestMathScore:
    def test_exact_match_pass(self):
        assert math_score("42", "42") == 1.0

    def test_numeric_match_pass(self):
        assert math_score("The answer is 42.", "42") == 1.0

    def test_full_fail(self):
        assert math_score("42", "43") == 0.0


class TestPassAtK:
    def test_all_correct(self):
        """n=5, c=5, k=1 -> pass@1 = 1.0"""
        assert pass_at_k(5, 5, 1) == 1.0

    def test_none_correct(self):
        assert pass_at_k(5, 0, 1) == 0.0

    def test_one_correct_pass1(self):
        """n=5, c=1, k=1 — unbiased estimate: 1 - C(4,1)/C(5,1) = 1 - 4/5 = 0.2"""
        score = pass_at_k(5, 1, 1)
        assert abs(score - 0.2) < 1e-9

    def test_one_correct_pass5(self):
        """n=5, c=1, k=5: n-c=4 < k=5 so returns 1.0"""
        assert pass_at_k(5, 1, 5) == 1.0

    def test_known_benchmark_value(self):
        """HumanEval paper: n=200, c=150, pass@1 ≈ 0.75"""
        score = pass_at_k(200, 150, 1)
        assert abs(score - 0.75) < 0.01


class TestComputePassAtK:
    def test_basic(self):
        results = [
            [True, False, False, False, False],  # 1/5 correct
            [True, True, True, False, False],     # 3/5 correct
        ]
        scores = compute_pass_at_k_scores(results, k_values=[1, 5])
        # Problem 1: pass@1 = 0.2, pass@5 = 1.0
        # Problem 2: pass@1 = 0.6, pass@5 = 1.0
        # Average pass@1 = (0.2 + 0.6) / 2 = 0.4
        assert abs(scores[1] - 0.4) < 1e-9
        assert scores[5] == 1.0

    def test_empty(self):
        scores = compute_pass_at_k_scores([], k_values=[1, 5])
        assert scores[1] == 0.0
        assert scores[5] == 0.0