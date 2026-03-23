"""I/O utilities for reading and writing artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from paper_agent.utils.logging import get_logger

logger = get_logger(__name__)


def write_json(path: Path, data: Any, indent: int = 2) -> None:
    """Write data as JSON to a file.

    Args:
        path: Target file path
        data: Data to serialize
        indent: JSON indentation level
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
    logger.debug("json_written", path=str(path), size_bytes=path.stat().st_size)


def read_json(path: Path) -> Any:
    """Read JSON from a file.

    Args:
        path: Source file path

    Returns:
        Parsed JSON data

    Raises:
        FileNotFoundError: If the file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    logger.debug("json_read", path=str(path))
    return data


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    """Write a list of records as JSONL.

    Args:
        path: Target file path
        records: List of dictionaries to serialize
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    logger.debug("jsonl_written", path=str(path), records=len(records))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSONL file into a list of dicts.

    Args:
        path: Source file path

    Returns:
        List of parsed JSON objects
    """
    records: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    logger.warning(
                        "jsonl_parse_error",
                        path=str(path),
                        line=line_num,
                        error=str(e),
                    )
    logger.debug("jsonl_read", path=str(path), records=len(records))
    return records


def write_text(path: Path, text: str) -> None:
    """Write text to a file.

    Args:
        path: Target file path
        text: Text content to write
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    logger.debug("text_written", path=str(path), chars=len(text))


def read_text(path: Path) -> str:
    """Read text from a file.

    Args:
        path: Source file path

    Returns:
        File contents as string
    """
    with open(path, encoding="utf-8") as f:
        content = f.read()
    logger.debug("text_read", path=str(path), chars=len(content))
    return content
