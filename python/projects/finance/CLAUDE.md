# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python-based Streamlit application for financial analysis with AI-powered tools. The main application is in `ufinance/`.

## Running the Application

```bash
# From the finance directory
cd ufinance
./run.sh  # Installs deps and runs streamlit
# Or manually:
source ../.venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Dependencies

Key packages: `streamlit`, `dashscope`, `openai`, `yfinance`, `pandas`, `matplotlib`, `akshare`

Virtual environment is located at `python/finance/.venv` (parent directory).

## API Configuration

Supports two API providers (checked in order):

1. **Anthropic** (preferred if `ANTHROPIC_API_KEY` is set):
   - `ANTHROPIC_API_KEY` - API key
   - `ANTHROPIC_BASE_URL` - Optional base URL (for custom endpoints)

2. **DashScope** (fallback):
   - `DASHSCOPE_API_KEY` - Qwen API key

Can also be set via Streamlit sidebar input at runtime.

## Architecture

```
ufinance/
├── app.py              # Main entry, routing between tools
├── apps/               # Individual Streamlit apps (modular tools)
│   ├── stock_analyzer.py
│   ├── blog_analyzer.py
│   ├── starrocks_sql_generator.py
│   └── etf_analyzer.py
├── lib/                # Shared utilities and AI clients
│   ├── qwen.py         # Qwen API client (OpenAI SDK compatible)
│   ├── deepseek.py     # DeepSeek API client
│   ├── stock_analysis.py
│   ├── news.py         # News retrieval utilities
│   └── logger.py       # Logging utilities
└── .streamlit/config.toml  # Streamlit configuration
```

## Key Patterns

- AI clients use OpenAI SDK compatible interfaces (`openai.OpenAI`)
- API calls via DashScope (`https://dashscope.aliyuncs.com/compatible-mode/v1`)
- Apps follow: input → API call → display result flow
- Logging via `lib/logger.py` with function call tracking
