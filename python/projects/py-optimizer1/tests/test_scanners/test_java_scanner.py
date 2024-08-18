"""Test Java scanner implementation."""
import os
from optimizer_analysis.scanners.base import CodeFile, ScanResult
from optimizer_analysis.scanners.java_scanner import JavaScanner


class TestCodeFile:
    """Tests for CodeFile model."""

    def test_code_file_creation(self):
        """Test CodeFile can be created with required fields."""
        code_file = CodeFile(
            path="/path/to/Test.java",
            content="public class Test {}",
            language="java",
            relative_path="Test.java"
        )
        assert code_file.path == "/path/to/Test.java"
        assert code_file.content == "public class Test {}"
        assert code_file.language == "java"
        assert code_file.relative_path == "Test.java"

    def test_code_file_optional_relative_path(self):
        """Test CodeFile with optional relative_path as None."""
        code_file = CodeFile(
            path="/path/to/Test.java",
            content="public class Test {}",
            language="java"
        )
        assert code_file.relative_path is None


class TestJavaScanner:
    """Tests for JavaScanner."""

    def test_java_scanner_init(self):
        """Test JavaScanner initialization."""
        scanner = JavaScanner()
        assert scanner.language == "java"
        assert scanner.extensions == [".java"]

    def test_java_scanner_extract_classes(self):
        """Test extracting class names from Java code."""
        scanner = JavaScanner()
        code = """
        public class MyClass {
            private int x;
        }

        class AnotherClass {
        }

        interface MyInterface {
        }
        """
        classes = scanner.extract_classes(code)
        assert "MyClass" in classes
        assert "AnotherClass" in classes
        assert "MyInterface" in classes
        assert len(classes) == 3

    def test_java_scanner_extract_methods(self):
        """Test extracting method names from Java code."""
        scanner = JavaScanner()
        code = """
        public class Test {
            public void myMethod() {}

            private String getName() { return "test"; }

            static int calculate(int x) { return x * 2; }
        }
        """
        methods = scanner.extract_methods(code)
        assert "myMethod" in methods
        assert "getName" in methods
        assert "calculate" in methods
        assert len(methods) == 3

    def test_java_scanner_extract_package(self):
        """Test extracting package name from Java code."""
        scanner = JavaScanner()
        code = """
        package com.example.myapp;

        public class Test {}
        """
        package = scanner.extract_package(code)
        assert package == "com.example.myapp"

    def test_java_scanner_extract_package_no_package(self):
        """Test extracting package when none exists."""
        scanner = JavaScanner()
        code = """
        public class Test {}
        """
        package = scanner.extract_package(code)
        assert package == ""

    def test_java_scanner_scan_directory(self):
        """Test scanning a directory for Java files."""
        starrocks_path = "/home/lism/work/starrocks"
        if not os.path.exists(starrocks_path):
            # Skip test if starrocks doesn't exist
            return

        scanner = JavaScanner()
        result = scanner.scan_directory(starrocks_path)

        assert isinstance(result, ScanResult)
        assert result.root_path == starrocks_path
        assert result.files_scanned > 0
        assert len(result.code_files) > 0
        assert result.files_scanned == len(result.code_files)

        # Verify all code files are Java
        for code_file in result.code_files:
            assert code_file.language == "java"
            assert code_file.path.endswith(".java")
            assert len(code_file.content) > 0