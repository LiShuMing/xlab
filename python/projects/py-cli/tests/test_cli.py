"""Tests for CLI commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from py_cli.cli import cli


class TestCLI:
    """Tests for main CLI."""

    def test_cli_help(self) -> None:
        """Test CLI help output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "py-cli" in result.output
        assert "LLM-powered" in result.output

    def test_version(self) -> None:
        """Test version flag."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestAnalyzeCommand:
    """Tests for analyze command."""

    def test_analyze_help(self) -> None:
        """Test analyze command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--help"])

        assert result.exit_code == 0
        assert "analyze" in result.output
        assert "--repo" in result.output
        assert "--since" in result.output

    @patch("py_cli.commands.analyze.Analyzer")
    def test_analyze_with_mock(self, mock_analyzer_class: MagicMock, git_repo: Path) -> None:
        """Test analyze command with mocked analyzer."""
        # Setup mock
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = Path("/tmp/report.md")
        mock_analyzer_class.return_value = mock_analyzer

        # Run command
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--repo", str(git_repo)])

        # Verify
        assert result.exit_code == 0
        mock_analyzer.analyze.assert_called_once()


class TestPromptsCommand:
    """Tests for prompts command."""

    def test_prompts_list(self) -> None:
        """Test prompts list command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["prompts", "list"])

        assert result.exit_code == 0
        assert "default" in result.output
        assert "clickhouse" in result.output

    def test_prompts_show(self) -> None:
        """Test prompts show command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["prompts", "show", "default"])

        assert result.exit_code == 0
        assert "System Prompt" in result.output
