"""Java file scanner for Calcite and Doris Nereids."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import javalang
    JAVA_PARSER_AVAILABLE = True
except ImportError:
    JAVA_PARSER_AVAILABLE = False

from .base import BaseScanner, ScanResult


class JavaScanner(BaseScanner):
    """Scanner for Java-based engines (Calcite, Doris FE)."""

    def scan(self) -> List[ScanResult]:
        """Scan Java files for rule classes."""
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
                    if JAVA_PARSER_AVAILABLE and self.scanner_hints.get("java_ast_parser"):
                        rules = self._extract_with_ast(content, file_path, class_pattern, key_methods, category)
                    else:
                        rules = self._extract_with_regex(content, file_path, class_pattern, key_methods, category)
                    results.extend(rules)
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")

        return results

    def _extract_with_ast(
        self,
        content: str,
        file_path: Path,
        class_pattern: str,
        key_methods: List[str],
        category: str
    ) -> List[ScanResult]:
        """Extract using javalang AST parser."""
        results = []

        try:
            tree = javalang.parse.parse(content)
        except Exception as e:
            print(f"Java parse error in {file_path}: {e}")
            return self._extract_with_regex(content, file_path, class_pattern, key_methods, category)

        for _, node in tree.filter(javalang.tree.ClassDeclaration):
            class_name = node.name

            # Check if class matches pattern
            if not self._class_matches_pattern(node, class_pattern):
                continue

            # Extract source lines for this class
            class_start = node.position.line - 1 if node.position else 0
            class_end = self._find_class_end(content, class_start)
            class_source = "\n".join(content.split("\n")[class_start:class_end])

            # Extract key methods
            method_snippets = []
            for method_decl in node.methods:
                if method_decl.name in key_methods:
                    method_snippet = self._extract_method_source(content, method_decl)
                    if method_snippet:
                        method_snippets.append(f"// {method_decl.name}:\n{method_snippet}")

            # Build snippet
            snippet_parts = []
            if node.documentation:
                snippet_parts.append(f"/** {node.documentation} */")
            snippet_parts.append(class_source)
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

    def _extract_with_regex(
        self,
        content: str,
        file_path: Path,
        class_pattern: str,
        key_methods: List[str],
        category: str
    ) -> List[ScanResult]:
        """Extract using regex fallback."""
        results = []

        try:
            regex = re.compile(class_pattern, re.MULTILINE)
        except re.error:
            return results

        for match in regex.finditer(content):
            class_name = self._extract_java_class_name(match.group(0))
            start_pos = match.start()

            # Extract class body
            brace_pos = content.find("{", match.end())
            if brace_pos == -1:
                continue

            class_body, _ = self._extract_with_brace_matching(content, brace_pos)

            # Extract key methods
            method_snippets = []
            for method in key_methods:
                method_snippet = self._extract_java_method(class_body, method)
                if method_snippet:
                    method_snippets.append(f"// {method}:\n{method_snippet}")

            # Extract Javadoc
            comment = self._extract_javadoc(content, start_pos)

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
                source_snippet=cleaned_snippet
            ))

        return results

    def _class_matches_pattern(self, node, class_pattern: str) -> bool:
        """Check if class declaration matches pattern."""
        # Simplified check - extract pattern from regex
        extends_match = re.search(r"extends\\s+(\w+)", class_pattern)
        if extends_match:
            base_class = extends_match.group(1)
            if node.extends and base_class in str(node.extends):
                return True
        return True  # Default to True if pattern is complex

    def _extract_java_class_name(self, class_decl: str) -> str:
        """Extract class name from declaration."""
        match = re.search(r"class\s+(\w+)", class_decl)
        return match.group(1) if match else "Unknown"

    def _extract_java_method(self, class_body: str, method_name: str) -> Optional[str]:
        """Extract method from class body."""
        pattern = rf"(?:@\w+\s+)*(?:public\s+)?(?:\w+\s+)?{re.escape(method_name)}\s*\([^)]*\)\s*(?:throws\s+\w+)?\s*"
        match = re.search(pattern, class_body)

        if not match:
            return None

        start_pos = match.start()
        brace_match = re.search(r"\{", class_body[match.end():])
        if not brace_match:
            return class_body[start_pos:match.end()]

        brace_pos = match.end() + brace_match.start()
        method_body, _ = self._extract_with_brace_matching(class_body, brace_pos)

        return class_body[start_pos:match.end()] + method_body

    def _extract_javadoc(self, content: str, pos: int) -> str:
        """Extract Javadoc comment before position."""
        lines = content[:pos].split("\n")
        comment_lines = []

        for line in reversed(lines):
            stripped = line.strip()
            if stripped.startswith("/**"):
                comment_lines.insert(0, stripped)
                break
            elif stripped.startswith("*") or stripped.startswith("/*"):
                comment_lines.insert(0, stripped)
            elif stripped == "":
                continue
            else:
                break

        return "\n".join(comment_lines)

    def _find_class_end(self, content: str, class_start: int) -> int:
        """Find the end line of a class."""
        lines = content.split("\n")
        brace_count = 0
        started = False

        for i, line in enumerate(lines[class_start:], start=class_start):
            for char in line:
                if char == "{":
                    brace_count += 1
                    started = True
                elif char == "}":
                    brace_count -= 1
                    if started and brace_count == 0:
                        return i + 1

        return len(lines)

    def _extract_method_source(self, content: str, method_decl) -> Optional[str]:
        """Extract method source using position info."""
        if not method_decl.position:
            return None

        lines = content.split("\n")
        start_line = method_decl.position.line - 1

        # Find method body
        brace_count = 0
        started = False
        end_line = start_line

        for i, line in enumerate(lines[start_line:], start=start_line):
            for char in line:
                if char == "{":
                    brace_count += 1
                    started = True
                elif char == "}":
                    brace_count -= 1
                    if started and brace_count == 0:
                        end_line = i + 1
                        break
            if started and brace_count == 0:
                break

        return "\n".join(lines[start_line:end_line])
