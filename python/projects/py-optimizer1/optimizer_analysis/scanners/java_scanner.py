"""Java code scanner implementation."""
import re
from typing import List
from .base import BaseScanner


class JavaScanner(BaseScanner):
    """Scanner for Java source code files."""

    def __init__(self):
        """Initialize the Java scanner."""
        super().__init__(language="java", extensions=[".java"])

    def extract_classes(self, code: str) -> List[str]:
        """Extract class, interface, and enum names from Java code.

        Args:
            code: Java source code

        Returns:
            List of class/interface/enum names
        """
        # Match class, interface, enum declarations
        # Pattern: (public|private|protected)? (abstract|final)? (class|interface|enum) ClassName
        pattern = r'\b(?:public|private|protected)?\s*(?:abstract|final)?\s*(?:class|interface|enum)\s+(\w+)'
        matches = re.findall(pattern, code)
        return matches

    def extract_methods(self, code: str) -> List[str]:
        """Extract method names from Java code.

        Args:
            code: Java source code

        Returns:
            List of method names
        """
        # Match method declarations
        # Pattern: (public|private|protected)? (static)? returnType methodName(parameters)
        # This is a simplified pattern that captures most method declarations
        pattern = r'\b(?:public|private|protected)?\s*(?:static)?\s*\w+(?:<[^>]+>)?\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\s*\{'
        matches = re.findall(pattern, code)
        return matches

    def extract_package(self, code: str) -> str:
        """Extract package name from Java code.

        Args:
            code: Java source code

        Returns:
            Package name or empty string if not found
        """
        # Match package declaration
        pattern = r'^\s*package\s+([\w.]+)\s*;'
        match = re.search(pattern, code, re.MULTILINE)
        if match:
            return match.group(1)
        return ""