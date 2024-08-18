"""Optgen DSL scanner for CockroachDB."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import BaseScanner, ScanResult


class OptgenScanner(BaseScanner):
    """Scanner for CockroachDB Optgen DSL files."""

    def scan(self) -> List[ScanResult]:
        """Scan .opt files for rule definitions."""
        results = []

        for category in ["rbo_rules", "cbo_rules", "scalar_rules"]:
            pattern_config = self.patterns.get(category)
            if not pattern_config:
                continue

            glob_pattern = pattern_config.get("glob", "")
            dsl_pattern = pattern_config.get("dsl_rule_pattern", r"^\[\w+")

            files = self._find_files(glob_pattern)

            for file_path in files:
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    rules = self._extract_rules(content, file_path, dsl_pattern, category)
                    results.extend(rules)
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")

        return results

    def _extract_rules(
        self,
        content: str,
        file_path: Path,
        dsl_pattern: str,
        category: str
    ) -> List[ScanResult]:
        """Extract Optgen rule definitions."""
        results = []

        # Split by rule boundaries (lines starting with [)
        # Pattern: [RuleName, Tags]
        rule_boundary = re.compile(r"^\[(\w+)(?:,\s*[^\]]+)?\]", re.MULTILINE)

        # Find all rule positions
        matches = list(rule_boundary.finditer(content))

        for i, match in enumerate(matches):
            rule_name = match.group(1)
            start_pos = match.start()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)

            rule_content = content[start_pos:end_pos]

            # Extract comment lines before the rule
            comment = self._extract_optgen_comment(content, start_pos)

            # Find corresponding Go file
            go_file = self._find_generated_go(file_path, rule_name)
            go_snippet = None
            if go_file and go_file.exists():
                try:
                    go_snippet = self._extract_go_function(go_file, rule_name)
                except Exception:
                    pass

            snippet_parts = []
            if comment:
                snippet_parts.append(comment)
            snippet_parts.append(rule_content.strip())

            full_snippet = "\n".join(snippet_parts)
            cleaned_snippet = self._clean_snippet(full_snippet)

            results.append(ScanResult(
                rule_name=rule_name,
                category=category,
                source_file=go_file or file_path,
                source_snippet=go_snippet or cleaned_snippet,
                dsl_file=file_path,
                dsl_snippet=rule_content.strip(),
                metadata={"has_go_generated": go_file is not None}
            ))

        return results

    def _extract_optgen_comment(self, content: str, pos: int) -> str:
        """Extract # comment lines before position."""
        lines = content[:pos].split("\n")
        comment_lines = []

        for line in reversed(lines):
            stripped = line.strip()
            if stripped.startswith("#"):
                comment_lines.insert(0, stripped)
            elif stripped == "":
                continue
            else:
                break

        return "\n".join(comment_lines)

    def _find_generated_go(self, opt_file: Path, rule_name: str) -> Optional[Path]:
        """Find generated Go file for a rule."""
        # Generated files are typically in the same directory
        # with _gen.go or .og.go suffix
        dir_path = opt_file.parent

        # Try various naming patterns
        candidates = [
            dir_path / f"{opt_file.stem}_gen.go",
            dir_path / f"{opt_file.stem}.og.go",
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate

        return None

    def _extract_go_function(self, go_file: Path, rule_name: str) -> Optional[str]:
        """Extract generated Go function for a rule."""
        content = go_file.read_text(encoding="utf-8", errors="ignore")

        # Look for function definition
        pattern = rf"func\s+\([^)]+\)\s*{re.escape(rule_name)}\s*\("
        match = re.search(pattern, content)

        if not match:
            return None

        start_pos = match.start()
        brace_pos = content.find("{", match.end())
        if brace_pos == -1:
            return None

        func_body, _ = self._extract_with_brace_matching(content, brace_pos)
        func_sig = content[match.start():brace_pos]

        return func_sig + " " + func_body
