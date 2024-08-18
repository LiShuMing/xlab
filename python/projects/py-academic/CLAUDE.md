# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GPT Academic is a Gradio-based web interface for interacting with LLMs, optimized for academic research workflows. It features a plugin architecture for document processing, code analysis, and paper translation.

**Python Version**: 3.10 - 3.11 (type hints use `X | Y` union syntax requiring 3.10+)
**UI Framework**: Gradio 3.32.15

## Quick Start

### Installation

```bash
# Recommended: use uv for fast dependency management
uv venv --python=3.11
source ./.venv/bin/activate
uv pip install -r requirements.txt

# Or with pip
pip install -r requirements.txt
```

### Configuration

Copy `config.py` to `config_private.py` (git-ignored) and set your API keys:

```python
# config_private.py — your secrets, never committed

# OpenAI
API_KEY = "sk-..."

# Anthropic / Claude
ANTHROPIC_API_KEY = "sk-ant-..."

# Qwen / DashScope (either key name works)
DASHSCOPE_API_KEY = "sk-..."    # or
QWEN_API_KEY = "sk-..."

# Which models to show in the dropdown
AVAIL_LLM_MODELS = ["gpt-4o", "claude-sonnet-4-5", "qwen-max"]
LLM_MODEL = "gpt-4o"   # default selected model
```

Config priority: `ENV vars` > `config_private.py` > `config.py`

### Running

```bash
python main.py
# Open http://localhost:8888 in your browser
```

### Docker

```bash
docker-compose up
```

### Testing

```bash
python tests/test_plugins.py
python tests/test_llms.py
```

## Supported LLM Providers

The application has been refactored to support three first-class providers.
All others have been removed to keep the codebase maintainable.

### OpenAI

Set `API_KEY` in config.  Models: `gpt-4o`, `gpt-4o-mini`, `gpt-4.1`, `o1`,
`o3`, `o4-mini`, `gpt-3.5-turbo`, and more.

```python
API_KEY = "sk-..."
AVAIL_LLM_MODELS = ["gpt-4o", "gpt-4o-mini", "o1"]
```

### Anthropic / Claude

Install extra dep: `pip install anthropic>=0.18.1`

Set `ANTHROPIC_API_KEY` in config.  Models: `claude-sonnet-4-5`,
`claude-3-7-sonnet-20250219`, `claude-3-5-sonnet-20241022`, `claude-3-opus-20240229`, and more.

```python
ANTHROPIC_API_KEY = "sk-ant-..."
AVAIL_LLM_MODELS = ["claude-sonnet-4-5", "claude-3-5-sonnet-20241022"]
```

### Qwen / DashScope

Install extra dep: `pip install dashscope`

Set `QWEN_API_KEY` or `DASHSCOPE_API_KEY` in config.  Models: `qwen-max`,
`qwen-plus`, `qwen-turbo`, `dashscope-deepseek-r1`, `dashscope-qwen3-14b`, and more.

```python
QWEN_API_KEY = "sk-..."
AVAIL_LLM_MODELS = ["qwen-max", "qwen-plus", "dashscope-deepseek-r1"]
```

Optional custom endpoint (compatible proxy):
```python
QWEN_BASE_URL = "https://your-proxy.example.com/v1"
```

## Adding a New LLM Provider

1. Create `request_llms/bridge_<provider>.py` with two functions using the
   standard signatures (see existing bridges for reference):

   ```python
   def predict_no_ui_long_connection(inputs, llm_kwargs, history, sys_prompt,
                                     observe_window=None, console_silence=False): ...
   def predict(inputs, llm_kwargs, plugin_kwargs, chatbot, history,
               system_prompt, stream, additional_fn): ...
   ```

2. Register the model in `request_llms/bridge_all.py` — either as a static
   entry in `model_info` or as a lazy-load block (see the Claude / Qwen sections).

3. Add the model name to `AVAIL_LLM_MODELS` in `config_private.py`.

### Dynamic prefix aliases (no code changes needed)

| Prefix pattern | Description |
|---|---|
| `one-api-<model>(max_token=N)` | Any OpenAI-compatible one-api proxy |
| `vllm-<model>(max_token=N)` | Local vLLM server |
| `azure-<model>` | Azure OpenAI (mirrors a built-in OpenAI model) |
| `api2d-<model>` | api2d proxy (mirrors a built-in OpenAI model) |

Example:
```python
AVAIL_LLM_MODELS = [
    "one-api-mistral-7b(max_token=8192)",
    "vllm-/path/to/Qwen2-7B(max_token=32768)",
]
```

## Architecture

```text
gpt_academic/
├── main.py                    # Entry point — Gradio UI orchestration
├── config.py                  # Base configuration (defaults)
├── config_private.py          # User overrides — API keys, model lists (git-ignored)
├── core_functional.py         # Core button functions: translate, polish, summarize, …
├── crazy_functional.py        # Plugin registry
├── toolbox.py                 # Decorators (@CatchException, @HotReload) + utilities
│
├── request_llms/              # LLM bridge layer
│   ├── bridge_all.py          # Central router — model_info registry + predict()
│   ├── bridge_chatgpt.py      # OpenAI API (GPT-3.5, GPT-4, GPT-4o, o-series, …)
│   ├── bridge_claude.py       # Anthropic SDK (Claude 3/3.5/3.7/4 families)
│   ├── bridge_qwen.py         # Qwen / DashScope SDK bridge
│   ├── com_qwenapi.py         # Low-level DashScope client
│   ├── bridge_chatgpt_vision.py  # GPT-4 vision / multimodal
│   └── oai_std_model_template.py # Factory for any OpenAI-compatible endpoint
│
├── crazy_functions/           # 70+ plugin modules
│   ├── PDF_Translate.py
│   ├── SourceCode_Analyse.py
│   └── …
│
├── shared_utils/              # Shared internal utilities
│   ├── config_loader.py       # Config resolution with ENV > private > default
│   ├── fastapi_server.py      # Gradio + FastAPI server startup
│   ├── context_clip_policy.py # Token budget management
│   └── key_pattern_manager.py # Multi-key round-robin rotation
│
└── themes/                    # Gradio UI themes and JavaScript
```

## Key Components

### LLM Router (`request_llms/bridge_all.py`)

Central dispatcher.  `model_info` is a dict mapping model names to their
bridge functions, endpoints, and token metadata.  Two public functions:

- `predict(...)` — streaming, single-threaded, drives the chat UI
- `predict_no_ui_long_connection(...)` — multi-thread safe, used inside plugins

### Plugin System (`crazy_functional.py`)

Plugins are registered in `crazy_functional.py` and grouped into:
`对话` (Conversation), `编程` (Programming), `学术` (Academic), `智能体` (Agent).

#### Plugin pattern

```python
from toolbox import CatchException, update_ui

@CatchException
def my_plugin(txt, llm_kwargs, plugin_kwargs, chatbot, history, system_prompt, user_request):
    # txt      — user input text or uploaded file path
    # llm_kwargs — model parameters: api_key, temperature, llm_model, …
    # plugin_kwargs — advanced parameters from the GUI input box
    # chatbot  — Gradio chat list; append tuples and yield to update the UI
    # history  — flat [user, assistant, user, assistant, …] list
    chatbot.append(("Input", "Processing …"))
    yield from update_ui(chatbot=chatbot, history=history)
```

#### Background LLM calls (inside plugins)

```python
from crazy_functions.crazy_utils import request_gpt_model_in_new_thread_with_ui_alive

result = yield from request_gpt_model_in_new_thread_with_ui_alive(
    inputs="Summarise this paper",
    inputs_show_user="Summarising …",
    llm_kwargs=llm_kwargs,
    chatbot=chatbot,
    history=[],
    sys_prompt="You are a helpful assistant.",
)
```

### Core Decorators (`toolbox.py`)

| Decorator | Purpose |
|---|---|
| `@CatchException` | Catches errors and displays them gracefully in the chat panel |
| `@HotReload` | Enables plugin hot-reloading without restarting the server |

### Configuration Loader (`shared_utils/config_loader.py`)

Priority chain: environment variables → `config_private.py` → `config.py`.

Environment variable names follow the pattern `GPT_ACADEMIC_<KEY>` or just `<KEY>`.

## Code Style

- **Python 3.10+** syntax: use `X | Y` union types, `match` statements where appropriate.
- **Logging**: `from loguru import logger` — use `logger.info/warning/error`.
- **Comments**: English only.
- **Type hints**: required on all new public functions.
- File uploads land in `private_upload/{username}/`; logs in `gpt_log/{username}/`.
- Plugins can be hot-reloaded: set `PLUGIN_HOT_RELOAD = True` in config.
