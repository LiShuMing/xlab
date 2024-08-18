"""Base class for file scanners."""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ScanResult:
    """Result of scanning a rule."""
    rule_name: str
    category: str
    source_file: Path
    source_snippet: str
    dsl_file: Optional[Path] = None
    dsl_snippet: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseScanner(ABC):
    """Base class for language-specific file scanners."""

    def __init__(self, config: Dict[str, Any], source_root: Path):
        """Initialize scanner with engine config and source root."""
        self.config = config
        self.source_root = source_root
        self.patterns = config.get("patterns", {})
        self.scanner_hints = config.get("scanner_hints", {})

    @abstractmethod
    def scan(self) -> List[ScanResult]:
        """Scan source files and return rule definitions."""
        pass

    def _find_files(self, glob_pattern: str) -> List[Path]:
        """Find files matching glob pattern relative to optimizer_root."""
        optimizer_root_str = self.config.get("optimizer_root", "")
        # Handle absolute vs relative paths correctly
        if optimizer_root_str.startswith("/"):
            optimizer_root = Path(optimizer_root_str)
        else:
            optimizer_root = self.source_root / optimizer_root_str.lstrip("./")
        if not optimizer_root.exists():
            return []
        # Use rglob for recursive glob
        pattern = glob_pattern.replace("**/", "")
        return list(optimizer_root.rglob(pattern))

    def _extract_with_brace_matching(
        self, content: str, start_pos: int, open_brace: str = "{", close_brace: str = "}"
    ) -> Tuple[str, int]:
        """Extract content between matching braces."""
        depth = 0
        in_string = False
        string_char = None
        result = []
        i = start_pos

        while i < len(content):
            char = content[i]

            # Handle string literals
            if char in ('"', "'") and not in_string:
                in_string = True
                string_char = char
                result.append(char)
            elif char == string_char and in_string:
                # Check for escaped quotes
                if i > 0 and content[i - 1] != "\\":
                    in_string = False
                    string_char = None
                result.append(char)
            elif in_string:
                result.append(char)
            elif char == open_brace:
                depth += 1
                result.append(char)
            elif char == close_brace:
                depth -= 1
                result.append(char)
                if depth == 0:
                    return "".join(result), i + 1
            elif depth > 0:
                result.append(char)
            elif char == open_brace and depth == 0:
                # Start of block
                depth = 1
                result.append(char)

            i += 1

        return "".join(result), i

    def _extract_doxygen_comment(self, content: str, pos: int) -> str:
        """Extract Doxygen/Javadoc style comment before position."""
        # Look backwards for comment
        lines = content[:pos].split("\n")
        comment_lines = []

        for line in reversed(lines):
            stripped = line.strip()
            if stripped.startswith("/**") or stripped.startswith("/*"):
                comment_lines.insert(0, stripped)
                break
            elif stripped.startswith("*") or stripped.startswith("//"):
                comment_lines.insert(0, stripped)
            elif stripped == "" or stripped.startswith("#"):
                continue
            else:
                break

        return "\n".join(comment_lines)

    def _clean_snippet(self, snippet: str, max_tokens: int = 2000) -> str:
        """Clean and truncate snippet to fit token budget."""
        # Remove excessive whitespace
        lines = snippet.split("\n")
        cleaned = []
        for line in lines:
            stripped = line.rstrip()
            if stripped or cleaned:  # Keep empty lines only if we have content
                cleaned.append(stripped)

        # Remove leading/trailing blank lines
        while cleaned and not cleaned[0]:
            cleaned.pop(0)
        while cleaned and not cleaned[-1]:
            cleaned.pop()

        result = "\n".join(cleaned)

        # Rough token estimate: ~4 chars per token
        max_chars = max_tokens * 4
        if len(result) > max_chars:
            result = result[:max_chars] + "\n// ... truncated"

        return result
