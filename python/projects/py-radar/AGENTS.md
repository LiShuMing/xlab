# AI Agent Guidelines

## Overview

This document provides guidelines for AI Agents working on the Daily DB Radar project.

## Mandatory Dependencies

### 1. RULE.md (Required)

**ALL AI Agents MUST read and follow RULE.md before making any code changes.**

The RULE.md file defines:
- Structured output validation requirements (Pydantic)
- Observability and telemetry standards (structlog)
- Error handling and resilience patterns (tenacity)
- Prompt engineering best practices
- Testing and evaluation requirements
- Performance and resource management rules
- Configuration management standards
- Documentation requirements

### Reading Order

When starting work on this project, read files in this order:

1. **RULE.md** - Engineering standards and constraints (MANDATORY)
2. **CLAUDE.md** - Project-specific context and conventions
3. **CHANGE_LOGS.md** - Recent changes and project history
4. **README.md** - Project overview and usage

### Compliance Verification

Before completing any task, verify compliance with RULE.md:

- [ ] LLM outputs are validated with Pydantic models
- [ ] Structured logging is used instead of print()
- [ ] Retry logic is implemented for external API calls
- [ ] Changes are documented in CHANGE_LOGS.md
- [ ] Configuration follows Pydantic Settings pattern

## Agent Capabilities

### Code Generation

When generating code:
- Follow TYPE HINTS strictly (Python 3.12+ syntax)
- Use `str | None` instead of `Optional[str]`
- Use modern built-ins (pathlib, f-strings)
- Design for testability with dependency injection

### Documentation

When updating documentation:
- Update CHANGE_LOGS.md for every code change
- Follow existing format with date headers
- Include technical details and usage examples

### Testing

When writing tests:
- Use pytest with fixtures
- Mock external API calls
- Add evaluation tests for LLM outputs
- Verify deterministic behavior

## Prohibited Actions

1. **DO NOT** use `print()` statements - use structured logging
2. **DO NOT** hardcode prompts - use external prompt files
3. **DO NOT** skip CHANGE_LOGS.md updates
4. **DO NOT** modify config files without explicit approval
5. **DO NOT** modify files outside project directory without 3x confirmation

## Communication Style

- Be concise and direct
- Include file paths with line numbers for references
- Use markdown for formatting
- Ask clarifying questions when requirements are ambiguous

## Task Completion

Before marking a task complete:
1. Verify RULE.md compliance
2. Update CHANGE_LOGS.md
3. Run tests to verify functionality
4. Summarize changes made
