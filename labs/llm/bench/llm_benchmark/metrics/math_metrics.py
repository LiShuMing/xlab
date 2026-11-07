"""Mathematical evaluation metrics: exact match and numeric tolerance."""

from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation


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
    matches = list(re.finditer(pattern, text))
    if not matches:
        return None
    match = matches[-1]
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


def final_answer(text: str) -> str:
    """Extract the explicit final answer, never a number from intermediate reasoning."""
    if "####" in text:
        return (
            text.rsplit("####", 1)[1].strip().splitlines()[0].strip()
            if text.rsplit("####", 1)[1].strip()
            else ""
        )
    boxed = _extract_boxed(text)
    if boxed is not None:
        return boxed
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def _decimal(text: str) -> Decimal | None:
    value = text.strip().replace(",", "")
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", value):
        return None
    try:
        result = Decimal(value)
        return result if result.is_finite() else None
    except InvalidOperation:
        return None


def gsm8k_score(prediction: str, reference: str) -> float:
    """Strict numeric equality of a #### final answer (or a bare numeric response).

    No tolerance, no searching intermediate steps, and no last-number heuristic.
    """
    answer = final_answer(prediction) if "####" in prediction else prediction.strip()
    predicted, expected = _decimal(answer), _decimal(reference)
    return float(predicted is not None and expected is not None and predicted == expected)


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
    pred_norm = _normalize(final_answer(prediction))
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

    Compares the final candidate only; does not reward intermediate matching numbers.
    """
    answer = final_answer(prediction)
    reference_numeric = re.sub(r"^(?:the\s+)?answer\s+is\s+", "", reference.strip(), flags=re.I)
    if not re.fullmatch(r"-?\d+\.?\d*(?:[eE][+-]?\d+)?(?:\s*/\s*\d+)?", reference_numeric):
        return exact_match(prediction, reference)
    pred_nums = _extract_numbers(answer)
    ref_nums = _extract_numbers(reference_numeric)

    if not ref_nums:
        # No reference numbers to compare against — fall back to exact match
        return exact_match(prediction, reference)

    ref_val = ref_nums[-1]  # Use the last number as reference
    return bool(pred_nums) and math.isclose(
        pred_nums[-1], ref_val, rel_tol=tolerance, abs_tol=tolerance
    )


def math_score(prediction: str, reference: str) -> float:
    """Combined math score: 1.0 if either exact_match or numeric_match passes.

    This is the primary metric for math datasets.
    """
    if exact_match(prediction, reference):
        return 1.0
    if numeric_match(prediction, reference):
        return 1.0
    return 0.0
