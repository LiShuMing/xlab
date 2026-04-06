"""C++ file scanners for class-based and function-based engines."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base import BaseScanner, ScanResult


class CppClassScanner(BaseScanner):
    """Scanner for C++ class inheritance pattern (StarRocks, GPDB, Columbia)."""

    def scan(self) -> List[ScanResult]:
        """Scan C++ files for rule classes."""
        results = []

        for category in ["rbo_rules", "cbo_rules", "scalar_rules", "post_opt", "properties"]:
            pattern_config = self.patterns.get(category)
            if not pattern_config:
                continue

            glob_pattern = pattern_config.get("glob", "")
            class_pattern = pattern_config.get("class_pattern", "")
            key_methods = pattern_config.get("key_methods", [])

            files = self._find_files(glob_pattern)

            for file_path in files:
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    rules = self._extract_classes(content, file_path, class_pattern, key_methods, category)
                    results.extend(rules)
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")

        return results

    def _extract_classes(
        self,
        content: str,
        file_path: Path,
        class_pattern: str,
        key_methods: List[str],
        category: str
    ) -> List[ScanResult]:
        """Extract class definitions matching the pattern."""
        results = []

        try:
            regex = re.compile(class_pattern, re.MULTILINE)
        except re.error as e:
            print(f"Invalid regex pattern: {class_pattern}, error: {e}")
            return results

        for match in regex.finditer(content):
            class_name = self._extract_class_name(match.group(0))
            start_pos = match.end()

            # Extract class body with brace matching
            class_body, _ = self._extract_with_brace_matching(content, start_pos)

            # Extract key methods
            method_snippets = []
            for method in key_methods:
                method_snippet = self._extract_method(class_body, method)
                if method_snippet:
                    method_snippets.append(f"// {method}:\n{method_snippet}")

            # Extract comment
            comment = self._extract_doxygen_comment(content, match.start())

            # Build full snippet
            snippet_parts = []
            if comment:
                snippet_parts.append(comment)
            snippet_parts.append(f"class {class_name} {{")
            snippet_parts.append(class_body)
            if method_snippets:
                snippet_parts.append("\n// Key methods:\n" + "\n\n".join(method_snippets))

            full_snippet = "\n".join(snippet_parts)
            cleaned_snippet = self._clean_snippet(full_snippet)

            results.append(ScanResult(
                rule_name=class_name,
                category=category,
                source_file=file_path,
                source_snippet=cleaned_snippet,
                metadata={"key_methods_found": len(method_snippets)}
            ))

        return results

    def _extract_class_name(self, class_decl: str) -> str:
        """Extract class name from declaration."""
        # class RuleXxx : public Base -> RuleXxx
        match = re.search(r"class\s+(\w+)", class_decl)
        return match.group(1) if match else "Unknown"

    def _extract_method(self, class_body: str, method_name: str) -> Optional[str]:
        """Extract a method from class body."""
        # Look for method signature
        pattern = rf"(?:virtual\s+)?(?:\w+::)?{re.escape(method_name)}\s*\([^)]*\)\s*(?:const)?\s*"
        match = re.search(pattern, class_body)

        if not match:
            return None

        start_pos = match.start()
        # Find opening brace
        brace_match = re.search(r"\{", class_body[match.end():])
        if not brace_match:
            return class_body[start_pos:match.end()]

        brace_pos = match.end() + brace_match.start()
        method_body, _ = self._extract_with_brace_matching(class_body, brace_pos)

        return class_body[start_pos:match.end()] + method_body


class CppFunctionScanner(BaseScanner):
    """Scanner for C++ function-based engines (ClickHouse)."""

    def scan(self) -> List[ScanResult]:
        """Scan C++ files for rule functions."""
        results = []

        for category in ["rbo_rules", "cbo_rules", "scalar_rules", "post_opt"]:
            pattern_config = self.patterns.get(category)
            if not pattern_config:
                continue

            glob_pattern = pattern_config.get("glob", "")
            func_pattern = pattern_config.get("func_pattern", "")

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
        """Extract function definitions matching the pattern."""
        results = []

        try:
            regex = re.compile(func_pattern, re.MULTILINE)
        except re.error:
            return results

        for match in regex.finditer(content):
            func_signature = match.group(0)
            func_name = self._extract_function_name(func_signature)
            start_pos = match.start()

            # Find opening brace
            brace_match = re.search(r"\{", content[match.end():])
            if not brace_match:
                continue

            brace_pos = match.end() + brace_match.start()
            func_body, _ = self._extract_with_brace_matching(content, brace_pos)

            # Extract comment
            comment = self._extract_c_comment(content, start_pos)

            snippet_parts = []
            if comment:
                snippet_parts.append(comment)
            snippet_parts.append(func_signature + " ")
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

    def _extract_function_name(self, func_signature: str) -> str:
        """Extract function name from signature."""
        # tryXxx, optimizeTreeXxx, etc.
        match = re.search(r"(\w+)\s*\(", func_signature)
        return match.group(1) if match else "Unknown"

    def _extract_c_comment(self, content: str, pos: int) -> str:
        """Extract C-style comment before position."""
        lines = content[:pos].split("\n")
        comment_lines = []

        for line in reversed(lines):
            stripped = line.strip()
            if stripped.startswith("/*"):
                comment_lines.insert(0, stripped)
                break
            elif stripped.startswith("*") or stripped.startswith("//"):
                comment_lines.insert(0, stripped)
            elif stripped == "":
                continue
            else:
                break

        return "\n".join(comment_lines)
