# AI Lab Platform

A scalable, modular AI experimentation platform built with Streamlit and LangChain. Originally evolved from Finance AI Toolkit, now supporting multi-provider LLMs, plugin-based modules, and extensible AI capabilities.

## Features

### Core Platform
- **🧪 Sandbox** - Free-form AI experimentation with custom system prompts
- **🔌 Plugin Architecture** - Auto-discoverable modules with unified interface
- **🤖 Multi-Provider LLM Support** - Qwen (DashScope), OpenAI, Anthropic (Claude)
- **💨 Streaming Output** - Real-time token streaming for better UX
- **🧠 Conversation Memory** - Persistent multi-turn chat history

### Migrated Tools (Legacy Support)
- **📈 Stock Analyzer Bot** - AI-powered stock analysis with investment recommendations
- **📝 Blog Analyzer** - Technical blog content extraction and analysis
- **🗄️ StarRocks SQL Generator** - AI-assisted SQL DDL and INSERT statement generation
- **📊 ETF Momentum Analyzer** - Backtesting tool for ETF momentum strategies

## Requirements

- Python 3.8+
- At least one API key:
  - DashScope API key (for Qwen models)
  - OpenAI API key
  - Anthropic API key

## Installation

1. Clone or download this repository
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables:

   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

## Configuration

The platform supports multiple AI providers. Configure at least one:

### DashScope (Qwen)

```bash
export DASHSCOPE_API_KEY="your_dashscope_api_key_here"
```

### OpenAI

```bash
export OPENAI_API_KEY="your_openai_api_key_here"
```

### Anthropic (Claude)

```bash
export ANTHROPIC_API_KEY="your_anthropic_api_key_here"
```

Or use the `.env` file (see `.env.example` for all options).

## Usage

Run the application:

```bash
streamlit run app.py
```

Then:

1. Select a module from the sidebar
2. Configure model parameters (temperature, max tokens) if needed
3. Start experimenting!

## Architecture

```
.
├── app.py                  # Main entry point with module routing
├── config/                 # Centralized configuration
│   └── settings.py         # API keys, model params, paths
├── core/                   # Core infrastructure
│   ├── llm_factory.py      # Unified LLM factory
│   ├── callback_handler.py # Streaming output handlers
│   └── memory_manager.py   # Conversation memory
├── modules/                # Plugin modules
│   ├── base_module.py      # Abstract base class
│   ├── sandbox/            # Sandbox experimentation
│   ├── stock_analyzer/     # Stock analysis (migrated)
│   ├── blog_analyzer/      # Blog analysis (migrated)
│   ├── starrocks_sql/      # SQL generation (migrated)
│   └── etf_analyzer/       # ETF analysis (migrated)
├── tools/                  # Custom tool base classes
└── utils/                  # Shared utilities
```

## Creating Custom Modules

To add a new module:

```python
from modules.base_module import BaseModule, register_module

@register_module
class MyModule(BaseModule):
    name = "My Module"
    description = "What my module does"
    icon = "🚀"
    order = 30  # Sort order in sidebar
    
    def render(self) -> None:
        self.display_header()
        # Your UI code here
```

The module will be automatically discovered and added to the sidebar!

## Migration from Finance AI Toolkit

This project evolved from the Finance AI Toolkit. All 4 original tools have been successfully migrated to the new plugin architecture with improved features:
- Unified LLM factory supporting multiple providers
- Consistent UI patterns across all modules
- Better error handling and user feedback
- Configurable model parameters

| Original Tool | New Module | Status |
|--------------|------------|--------|
| Stock Analyzer Bot | modules/stock_analyzer/ | ✅ Migrated |
| Blog Analyzer | modules/blog_analyzer/ | ✅ Migrated |
| StarRocks SQL Generator | modules/starrocks_sql/ | ✅ Migrated |
| ETF Momentum Analyzer | modules/etf_analyzer/ | ✅ Migrated |

## License

MIT License - See LICENSE file for details.

## Resources

- [DashScope Documentation](https://dashscope.console.aliyun.com/)
- [LangChain Documentation](https://python.langchain.com/)
- [Streamlit Documentation](https://docs.streamlit.io/)
