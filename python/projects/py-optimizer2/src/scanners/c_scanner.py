"""C file scanner for PostgreSQL."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import BaseScanner, ScanResult


class CScanner(BaseScanner):
    """Scanner for C-based engines (PostgreSQL)."""

    def scan(self) -> List[ScanResult]:
        """Scan C files for function definitions."""
        results = []

        for category in ["rbo_rules", "cbo_rules", "scalar_rules", "post_opt", "properties"]:
            pattern_config = self.patterns.get(category)
            if not pattern_config:
                continue

            glob_pattern = pattern_config.get("glob", "")
            func_pattern = pattern_config.get("func_pattern", "")
            key_files = pattern_config.get("key_files", [])

            if key_files:
                # Use specific files
                files = []
                for kf in key_files:
                    fp = self.source_root / self.config.get("optimizer_root", "").lstrip("./") / kf
                    if fp.exists():
                        files.append(fp)
            else:
                files = self._find_files(glob_pattern)

            for file_path in files:
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    rules = self._extract_functions(content, file_path, func_pattern, category)
                    results.extend(rules)
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")

        return results

    def _extract_functions(
        self,
        content: str,
        file_path: Path,
        func_pattern: str,
        category: str
    ) -> List[ScanResult]:
        """Extract C function definitions."""
        results = []

        try:
            regex = re.compile(func_pattern, re.MULTILINE)
        except re.error:
            return results

        for match in regex.finditer(content):
            func_sig = match.group(0)
            func_name = self._extract_c_function_name(func_sig)
            start_pos = match.start()

            # Find opening brace
            brace_match = re.search(r"\{", content[match.end():])
            if not brace_match:
                continue

            brace_pos = match.end() + brace_match.start()
            func_body, _ = self._extract_with_brace_matching(content, brace_pos)

            # Extract block comment (PostgreSQL has excellent comments)
            comment = self._extract_c_block_comment(content, start_pos)

            snippet_parts = []
            if comment:
                snippet_parts.append(comment)
            snippet_parts.append(func_sig + " {")
            snippet_parts.append(func_body)

            full_snippet = "\n".join(snippet_parts)
            cleaned_snippet = self._clean_snippet(full_snippet)

            results.append(ScanResult(
                rule_name=func_name,
                category=category,
                source_file=file_path,
                source_snippet=cleaned_snippet
            ))

        return results

    def _extract_c_function_name(self, func_sig: str) -> str:
        """Extract function name from C signature."""
        # Remove common prefixes and extract name
        cleaned = re.sub(r"^(static\s+|extern\s+|inline\s+)", "", func_sig.strip())
        match = re.search(r"(\w+)\s*\(", cleaned)
        return match.group(1) if match else "Unknown"

    def _extract_c_block_comment(self, content: str, pos: int) -> str:
        """Extract C-style block comment before position."""
        # PostgreSQL uses excellent block comments
        text_before = content[:pos]

        # Find the last /* ... */ before position
        last_comment_end = text_before.rfind("*/")
        if last_comment_end == -1:
            return ""

        # Check if there's a /* before this */
        comment_start = text_before.rfind("/*", 0, last_comment_end)
        if comment_start == -1:
            return ""

        # Extract the comment
        comment = text_before[comment_start:last_comment_end + 2]

        # Check if comment is close enough (within 5 lines)
        text_between = text_before[last_comment_end + 2:pos]
        lines_between = text_between.count("\n")
        if lines_between > 5:
            return ""

        return comment
