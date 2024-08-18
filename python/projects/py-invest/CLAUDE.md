# CLAUDE.md - py-invest Project Guidelines

## Change Log Policy

**IMPORTANT**: Every code change and design decision MUST be documented in `CHANGE_LOGS.md`.

### Before Committing
1. Update `CHANGE_LOGS.md` with:
   - Date of change
   - Files modified/created/deleted
   - Summary of changes (Added/Changed/Removed)
   - Key technical details or decisions

2. Format for `CHANGE_LOGS.md`:
```markdown
## [Date] - YYYY-MM-DD

### Added/Changed/Removed
- **Feature Name** (`path/to/file.py`)
  - Description of change
  - Technical details
```

### Rule
- No change is considered "done" until it's logged in `CHANGE_LOGS.md`
- Include rationale for significant architectural decisions
- Link to related issues or design documents if applicable

## Project Structure

```
py-invest/
├── agents/              # Multi-agent system
│   ├── base.py          # AgentState, ToolResult, BaseAgentTool
│   ├── orchestrator.py  # SimpleAgentOrchestrator (multi-agent pipeline)
│   ├── specialist_agents.py  # 4 specialist analyst agents
│   └── synthesis_agent.py    # Report synthesizer
├── modules/
│   └── report_generator/
│       ├── types.py     # Report, ReportSection dataclasses
│       ├── formatter.py # Markdown/HTML/JSON formatters
│       └── builder.py   # Report builder
├── core/
│   ├── llm.py          # LLMClient, LLMConfig (loads ~/.env)
│   └── logger.py       # Logging utilities
├── cli.py              # CLI interface
└── pyproject.toml
```

## Key Components

### Multi-Agent Pipeline
1. Data Collection (sequential): price, kline, financials, news
2. Specialist Analysis (parallel): Technical, Fundamental, Risk, Sector
3. Synthesis: Combines into 9-section GS-style report

### Report Fields
- `bull_case`, `bear_case`, `base_case`: Scenario analysis
- `target_price`: With methodology
- `rating`: Buy/Hold/Sell
- `confidence`: high/medium/low

### LLM Configuration
- Loads from `~/.env` first
- Supports `LLM_API_KEY` or `ANTHROPIC_API_KEY`
- Default model: `qwen3.5-plus`

## Usage

```bash
# Analyze a stock
python cli.py analyze sh600519 "综合分析" -v

# Save report
python cli.py analyze sh600519 > report.md
```
