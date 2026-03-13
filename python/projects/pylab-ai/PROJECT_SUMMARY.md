# AI Lab Platform

A scalable, modular AI experimentation platform built with Streamlit and LangChain. Originally evolved from Finance AI Toolkit, now supporting multi-provider LLMs, plugin-based modules, and extensible AI capabilities.

## Core Features

1. **🧪 Sandbox** - Free-form AI experimentation with custom system prompts
2. **📈 Stock Analyzer** - AI-powered stock analysis with investment recommendations
3. **📝 Blog Analyzer** - Extract insights from technical blogs
4. **🗄️ StarRocks SQL** - Generate SQL DDL and INSERT statements
5. **📊 ETF Momentum** - Backtest ETF momentum strategies

## Project Structure

```text
ai-lab-platform/
├── app.py                  # Main Streamlit application with module routing
├── requirements.txt        # Python dependencies
├── README.md              # User documentation
├── USER_GUIDE.md          # Detailed usage guide
├── run.sh                 # Run script
├── .env.example           # Environment configuration template
├── .streamlit/
│   └── config.toml        # Streamlit configuration
│
├── config/                # Configuration management
│   ├── __init__.py
│   └── settings.py        # Centralized settings (API keys, models)
│
├── core/                  # Core infrastructure
│   ├── __init__.py
│   ├── llm_factory.py     # Unified LLM factory (Qwen/OpenAI/Anthropic)
│   ├── callback_handler.py # Streaming output handlers
│   └── memory_manager.py  # Conversation memory
│
├── modules/               # Plugin modules (auto-registered)
│   ├── base_module.py     # Abstract base class
│   ├── sandbox/           # Sandbox experimentation
│   ├── stock_analyzer/    # Stock analysis
│   ├── blog_analyzer/     # Blog content analysis
│   ├── starrocks_sql/     # SQL generation
│   └── etf_analyzer/      # ETF momentum analysis
│
├── tools/                 # Custom tool base classes
│   ├── __init__.py
│   └── base_tool.py       # Tool abstract base
│
├── utils/                 # Shared utilities
│   ├── __init__.py
│   ├── logger.py          # Logging utility
│   └── ui_helpers.py      # Streamlit UI components
│
├── tests/
│   └── test_app.py        # Unit tests
│
└── vector_store/          # FAISS vector storage
```

## Architecture Highlights

- **Plugin Architecture**: Modules auto-register via `@register_module` decorator
- **Multi-Provider LLM Support**: Qwen, OpenAI, Anthropic with unified interface
- **Centralized Configuration**: All settings in `config/settings.py` + `.env`
- **Streaming Output**: Real-time token streaming for better UX
- **Conversation Memory**: Persistent multi-turn chat history

## How to Run

1. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   ./run.sh
   # Or: streamlit run app.py
   ```

## API Configuration

The platform supports multiple AI providers. Configure at least one:

| Provider | Environment Variable | Documentation |
|----------|---------------------|---------------|
| Qwen (DashScope) | `DASHSCOPE_API_KEY` | https://dashscope.console.aliyun.com/ |
| Qwen Coding Plan | `DASHSCOPE_CODING_API_KEY` | https://www.aliyun.com/product/bailian/coding |
| OpenAI | `OPENAI_API_KEY` | https://platform.openai.com/ |
| Anthropic | `ANTHROPIC_API_KEY` | https://console.anthropic.com/ |

## Creating Custom Modules

To add a new module:

```python
from modules.base_module import BaseModule, register_module

@register_module
class MyModule(BaseModule):
    name = "My Module"
    description = "What my module does"
    icon = "🚀"
    order = 60
    
    def render(self) -> None:
        self.display_header()
        # Your UI code here
```

The module will be automatically discovered and added to the sidebar!

## License

MIT License
