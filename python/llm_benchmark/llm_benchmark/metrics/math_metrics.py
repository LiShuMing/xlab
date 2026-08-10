"""Mathematical evaluation metrics: exact match and numeric tolerance."""

from __future__ import annotations

import re
import math


def _normalize(text: str) -> str:
    """Normalize text for comparison: strip whitespace, lowercase."""
    return text.strip().lower()


def _normalize_math(text: str) -> str:
    """Normalize math text: remove all whitespace, lowercase."""
    return re.sub(r"\s+", "", text.lower())


def _extract_boxed(text: str) -> str | None:
    """Extract the content of \\boxed{...} from LaTeX output."""
    # Handle nested braces
    pattern = r"\\boxed\{"
    match = re.search(pattern, text)
    if not match:
        return None
    start = match.end()
    depth = 1
    i = start
    while i < len(text) and depth > 0:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    if depth == 0:
        return text[start : i - 1].strip()
    return None


def _extract_numbers(text: str) -> list[float]:
    """Extract all numeric values (including negative, decimal, fractions) from text."""
    # Match: optional sign, digits, optional decimal, optional scientific notation
    # Also match fractions like 3/4
    numbers = []
    # Match standard numbers
    for m in re.finditer(r"-?\d+\.?\d*(?:[eE][+-]?\d+)?", text):
        try:
            numbers.append(float(m.group()))
        except ValueError:
            pass
    # Match fractions
    for m in re.finditer(r"(\d+)\s*/\s*(\d+)", text):
        num = int(m.group(1))
        den = int(m.group(2))
        if den != 0:
            numbers.append(num / den)
    return numbers


def exact_match(prediction: str, reference: str) -> bool:
    """Check if prediction exactly matches reference after normalization.

    For MATH: extracts the \\boxed{...} content from prediction and compares.
    For GSM8K: extracts the final numeric answer (after ####) and compares.
    """
    pred_norm = _normalize(prediction)
    ref_norm = _normalize(reference)

    # Try boxed extraction first (MATH style)
    pred_boxed = _extract_boxed(prediction)
    if pred_boxed is not None:
        return _normalize_math(pred_boxed) == _normalize_math(reference)

    # Try exact match after normalization
    if pred_norm == ref_norm:
        return True

    return False


def numeric_match(prediction: str, reference: str, tolerance: float = 1e-6) -> bool:
    """Check if the numeric value in prediction matches reference within tolerance.

    Extracts numbers from both strings and checks if any pair matches.
    """
    pred_nums = _extract_numbers(prediction)
    ref_nums = _extract_numbers(reference)

    if not ref_nums:
        # No reference numbers to compare against — fall back to exact match
        return exact_match(prediction, reference)

    ref_val = ref_nums[-1]  # Use the last number as reference
    for p in pred_nums:
        if math.isclose(p, ref_val, rel_tol=tolerance, abs_tol=tolerance):
            return True

    return False


def math_score(prediction: str, reference: str) -> float:
    """Combined math score: 1.0 if either exact_match or numeric_match passes.

    This is the primary metric for math datasets.
    """
    if exact_match(prediction, reference):
        return 1.0
    if numeric_match(prediction, reference):
        return 1.0
    return 0.0