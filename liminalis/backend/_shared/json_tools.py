"""Shared helpers for parsing JSON from model output."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

JSONKind = Literal["object", "array"]


class JSONTextError(ValueError):
    """Raised when JSON cannot be extracted from mixed text."""


def strip_markdown_fences(text: str) -> str:
    """Return the content inside a full markdown code fence, if present."""
    match = re.fullmatch(r"\s*```(?:json)?\s*(.*?)\s*```\s*", text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()


def load_json_object(text: str) -> dict[str, Any]:
    value = loads_json_from_text(text, expected="object")
    if not isinstance(value, dict):
        raise JSONTextError("Expected JSON object")
    return value


def load_json_array(text: str) -> list[Any]:
    value = loads_json_from_text(text, expected="array")
    if not isinstance(value, list):
        raise JSONTextError("Expected JSON array")
    return value


def loads_json_from_text(text: str, *, expected: JSONKind = "object") -> Any:
    """Parse JSON from raw text, fenced markdown, or surrounding prose."""
    if not text or not text.strip():
        raise JSONTextError("Empty JSON text")

    candidates = _candidate_json_texts(text, expected=expected)
    last_error: Exception | None = None
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc

    raise JSONTextError(f"Failed to parse JSON: {last_error}") from last_error


def _candidate_json_texts(text: str, *, expected: JSONKind) -> list[str]:
    stripped = strip_markdown_fences(text)
    candidates = [stripped]
    candidates.extend(match.strip() for match in re.findall(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL))

    open_char, close_char = ("{", "}") if expected == "object" else ("[", "]")
    for source in (stripped, text):
        extracted = _extract_balanced(source, open_char, close_char)
        if extracted:
            candidates.append(extracted)

    unique: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in unique:
            unique.append(candidate)
    return unique


def _extract_balanced(text: str, open_char: str, close_char: str) -> str | None:
    start = text.find(open_char)
    if start < 0:
        return None

    depth = 0
    for index, char in enumerate(text[start:], start):
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None
