from __future__ import annotations

import pytest

from backend._shared.json_tools import JSONTextError, load_json_array, load_json_object, strip_markdown_fences


def test_strip_markdown_fences_handles_json_block() -> None:
    assert strip_markdown_fences('```json\n{"ok": true}\n```') == '{"ok": true}'


def test_load_json_object_from_surrounding_text() -> None:
    parsed = load_json_object('Here is the result:\n{"name": "Liminalis", "ok": true}\nThanks.')

    assert parsed == {"name": "Liminalis", "ok": True}


def test_load_json_array_from_fenced_text() -> None:
    parsed = load_json_array('```json\n[{"product": "Snowflake"}]\n```')

    assert parsed == [{"product": "Snowflake"}]


def test_load_json_object_rejects_array() -> None:
    with pytest.raises(JSONTextError):
        load_json_object("[1, 2, 3]")
