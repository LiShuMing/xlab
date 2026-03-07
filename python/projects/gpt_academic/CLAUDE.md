# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GPT Academic is a Gradio-based web interface for interacting with LLMs, optimized for academic research workflows. It features a plugin architecture for document processing, code analysis, and paper translation.

**Python Version**: 3.9 - 3.11 | **UI Framework**: Gradio 3.32.15

## Commands

### Installation & Running

```bash
# Install dependencies (use Python 3.9-3.11)
pip install -r requirements.txt

# Or with uv
uv venv --python=3.11
source ./.venv/bin/activate
uv pip install -r requirements.txt

# Run application
python main.py
```

### Docker Deployment

```bash
# Choose a方案 from docker-compose.yml, then:
docker-compose up
```

### Testing

```bash
python tests/test_plugins.py
python tests/test_llms.py
```

### Optional Dependencies (Local Models)

```bash
# ChatGLM support
pip install -r request_llms/requirements_chatglm.txt

# ChatGLM4 support (24GB VRAM required)
pip install -r request_llms/requirements_chatglm4.txt

# MOSS support
pip install -r request_llms/requirements_moss.txt
```

## Architecture

```
gpt_academic/
├── main.py                    # Entry point - Gradio UI orchestration
├── config.py                  # Base configuration
├── config_private.py          # User overrides (not tracked)
├── core_functional.py         # Core button functions (translate, polish, etc.)
├── crazy_functional.py        # Plugin registry
├── toolbox.py                 # Core decorators (@CatchException, @HotReload)
├── multi_language.py          # Auto-translation utility
│
├── crazy_functions/           # 70+ plugin modules
├── request_llms/              # LLM bridge modules
│   ├── bridge_all.py          # Main LLM router/dispatcher
│   ├── bridge_chatgpt.py      # OpenAI API
│   ├── bridge_*.py            # Other model implementations
│   └── oai_std_model_template.py
│
├── shared_utils/              # Shared utilities
│   ├── config_loader.py       # Config priority: ENV > config_private.py > config.py
│   ├── fastapi_server.py      # Server startup
│   ├── advanced_markdown_format.py
│   ├── context_clip_policy.py # Token management
│   └── key_pattern_manager.py # API key rotation
│
└── themes/                    # UI themes
```

## Key Components

### Configuration (`shared_utils/config_loader.py`)

Config priority: `ENV` > `config_private.py` > `config.py`

### Plugin System (`crazy_functional.py`)

Plugins are registered in `crazy_functional.py` and organized into groups: `对话` (Conversation), `编程` (Programming), `学术` (Academic), `智能体` (Agent).

### Plugin Pattern

```python
from toolbox import CatchException, update_ui

@CatchException
def my_plugin(txt, llm_kwargs, plugin_kwargs, chatbot, history, system_prompt, user_request):
    chatbot.append(("User message", "Bot response"))
    yield from update_ui(chatbot=chatbot, history=history)
```

Arguments:
- `txt` - User input or file path
- `llm_kwargs` - LLM parameters (api_key, temperature, etc.)
- `plugin_kwargs` - Advanced arguments from GUI
- `chatbot` - UI handle for display
- `history` - Conversation history
- `system_prompt` - System prompt
- `user_request` - Web request info

### Core Decorators (`toolbox.py`)

| Decorator | Purpose |
|-----------|---------|
| `@CatchException` | Catches errors and displays gracefully in chat |
| `@HotReload` | Enables plugin hot-reloading without restart |

### LLM Bridge (`request_llms/bridge_all.py`)

Unified interface for all LLM models (OpenAI, Claude, GLM, Qwen, DeepSeek, ChatGLM local models, etc.)

## Important Notes

- Use `loguru` for logging: `from loguru import logger`
- User uploads go to `private_upload/{username}/`
- Logs go to `gpt_log/{username}/`
- Plugins can be hot-reloaded with `PLUGIN_HOT_RELOAD = True` in config
- For background LLM calls, use `request_gpt_model_in_new_thread_with_ui_alive()`
