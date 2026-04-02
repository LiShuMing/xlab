# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2024-04-01

### Added

- Initial release of py-cli
- `analyze` command for generating code change reports from git history
- `prompts list` and `prompts show` commands for prompt management
- Support for multiple prompt templates:
  - `default`: General purpose code change analysis
  - `clickhouse`: Database/kernel specific analysis (Chinese output)
- Git operations via GitClient class
- Anthropic Claude API integration via LLMClient class
- Comprehensive test suite with pytest
- Type-safe implementation with mypy strict mode
- Full project documentation (README, AGENTS.md, RULES.md)

### Features

- Analyze commits within custom date ranges
- Maximum commit limit to control API usage
- Auto-generated output filenames with timestamps
- Git statistics (authors, files changed, additions/deletions)
- Markdown report generation
- Configuration via environment variables (~/.env)
- Extensible CLI architecture with Click
- Async LLM client support for concurrent requests

### Technical

- Python 3.13+ support
- PEP 8 compliant with black formatting
- Strict type checking with mypy
- Linting with ruff
- Import sorting with isort
- pytest with async support
- Code coverage reporting

## [Unreleased]

### Planned

- HTML report output format
- Custom prompt template loading from files
- Support for additional LLM providers (OpenAI, etc.)
- Caching layer for LLM responses
- Configuration file support (~/.py-cli/config.toml)
- Progress bars for long-running operations
- Batch analysis across multiple repositories
- Integration with GitHub/GitLab APIs for PR/Issue context
