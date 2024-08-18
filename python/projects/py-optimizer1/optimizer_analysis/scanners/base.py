"""Base classes for code scanners."""
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path


@dataclass
class CodeFile:
    """Represents a code file with its content and metadata."""
    path: str
    content: str
    language: str
    relative_path: Optional[str] = None


@dataclass
class ScanResult:
    """Result of scanning a directory for code files."""
    root_path: str
    files_scanned: int
    code_files: List[CodeFile] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class BaseScanner:
    """Base class for language-specific code scanners."""

    def __init__(self, language: str, extensions: List[str]):
        """Initialize the scanner.

        Args:
            language: The programming language name (e.g., "java", "python")
            extensions: List of file extensions to scan (e.g., [".java", ".jav"])
        """
        self.language = language
        self.extensions = extensions

    def scan_directory(self, path: str) -> ScanResult:
        """Scan a directory for code files of the configured language.

        Args:
            path: Root directory path to scan

        Returns:
            ScanResult with all found code files
        """
        root_path = Path(path)
        code_files: List[CodeFile] = []
        errors: List[str] = []

        if not root_path.exists():
            errors.append(f"Directory does not exist: {path}")
            return ScanResult(
                root_path=path,
                files_scanned=0,
                code_files=code_files,
                errors=errors
            )

        # Walk the directory tree
        for file_path in root_path.rglob("*"):
            if file_path.is_file() and file_path.suffix in self.extensions:
                try:
                    content = file_path.read_text(encoding="utf-8")
                    relative_path = str(file_path.relative_to(root_path))
                    code_file = CodeFile(
                        path=str(file_path),
                        content=content,
                        language=self.language,
                        relative_path=relative_path
                    )
                    code_files.append(code_file)
                except Exception as e:
                    errors.append(f"Failed to read {file_path}: {e}")

        return ScanResult(
            root_path=path,
            files_scanned=len(code_files),
            code_files=code_files,
            errors=errors
        )