# Migration Guide: Legacy → Modern Architecture

This guide helps you migrate from the legacy `request_llms` to the new modern architecture.

## Quick Start

### Option 1: Use Compatibility Layer (Easiest)

No code changes needed! The new module provides backward-compatible functions:

```python
# Old import
# from request_llms.bridge_all import predict

# New import (same interface)
from request_llms import predict, predict_no_ui_long_connection
```

### Option 2: Modern API (Recommended for New Code)

```python
from request_llms import LLMFactory, Message, ChatConfig

# Create provider
llm = LLMFactory.create("gpt-4o")

# Chat
messages = [Message.user("Hello!")]
response = await llm.chat(messages)
print(response.message.content)
```

## Detailed Migration

### 1. Plugin Development

#### Before (Legacy)

```python
from toolbox import CatchException, update_ui
from request_llms.bridge_all import predict_no_ui_long_connection

@CatchException
def my_plugin(txt, llm_kwargs, plugin_kwargs, chatbot, history, system_prompt, user_request):
    # Call LLM
    response = predict_no_ui_long_connection(
        inputs=txt,
        llm_kwargs=llm_kwargs,
        history=history,
        sys_prompt=system_prompt,
    )
    # Update UI
    chatbot.append(("Input", response))
    yield from update_ui(chatbot=chatbot, history=history)
```

#### After (Modern)

```python
from toolbox import CatchException, update_ui
from request_llms import predict_no_ui_long_connection  # Same function!

@CatchException
def my_plugin(txt, llm_kwargs, plugin_kwargs, chatbot, history, system_prompt, user_request):
    # Same code works!
    response = predict_no_ui_long_connection(
        inputs=txt,
        llm_kwargs=llm_kwargs,
        history=history,
        sys_prompt=system_prompt,
    )
    chatbot.append(("Input", response))
    yield from update_ui(chatbot=chatbot, history=history)
```

### 2. Direct LLM Usage

#### Before (Legacy)

```python
from request_llms.bridge_all import model_info

# Get model function
model = llm_kwargs["llm_model"]
fn = model_info[model]["fn_without_ui"]

# Call it
response = fn(inputs, llm_kwargs, history, sys_prompt)
```

#### After (Modern)

```python
from request_llms import LLMFactory
import asyncio

async def get_response():
    provider = LLMFactory.create(llm_kwargs["llm_model"])
    messages = [...]  # Build message list
    response = await provider.chat(messages)
    return response.message.content

response = asyncio.run(get_response())
```

### 3. Configuration

#### Before (Legacy)

```python
# config.py
API_KEY = "sk-..."
DASHSCOPE_API_KEY = "sk-..."
ANTHROPIC_API_KEY = "sk-..."
LLM_MODEL = "gpt-4o"
AVAIL_LLM_MODELS = [...]
```

#### After (Modern)

```python
# config_new.py style (dataclasses)
from dataclasses import dataclass

@dataclass
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    api_keys: APIKeys = field(default_factory=APIKeys)
```

Or continue using legacy `config.py` format - it's still supported!

## Configuration Changes

### Supported Models

The modern architecture focuses on three main providers:

| Provider | Models |
|----------|--------|
| OpenAI | gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-4, gpt-3.5-turbo, o1-*, o3-* |
| Anthropic | claude-3-opus, claude-3-sonnet, claude-3-haiku, claude-3.5-sonnet |
| Qwen | qwen-max, qwen-plus, qwen-turbo, qwen3.5-plus, dashscope-qwen3-* |

**Removed Models**: 
- Local models (ChatGLM, LLaMA, etc.) - can be added via Ollama compatibility
- Lesser-used cloud models (Cohere, Zhipu, Moonshot, etc.)

If you need a removed model, you can:
1. Use OpenAI-compatible endpoint via `base_url`
2. Add a custom provider (see ARCHITECTURE.md)

### Environment Variables

| Old | New | Notes |
|-----|-----|-------|
| `API_KEY` | `OPENAI_API_KEY` | OpenAI API key |
| `DASHSCOPE_API_KEY` | `QWEN_API_KEY` or `DASHSCOPE_API_KEY` | Both work |
| `ANTHROPIC_API_KEY` | `ANTHROPIC_API_KEY` | No change |
| `LLM_MODEL` | `GPT_ACADEMIC_LLM_MODEL` | With prefix |
| `AVAIL_LLM_MODELS` | `GPT_ACADEMIC_AVAIL_LLM_MODELS` | With prefix |

## Troubleshooting

### "No provider found for model"

Make sure the model is registered:

```python
from request_llms import LLMFactory

# Check available models
print(LLMFactory.list_supported_models())

# Register if missing
LLMFactory.register_model("my-model", "openai")  # or "anthropic", "qwen"
```

### "API key required"

Set the appropriate environment variable:

```bash
export OPENAI_API_KEY="sk-..."
# or
export ANTHROPIC_API_KEY="sk-ant-..."
# or
export QWEN_API_KEY="sk-..."
```

### Streaming not working

Ensure `stream=True` in config:

```python
config = ChatConfig(stream=True)
async for chunk in provider.chat_stream(messages, config):
    print(chunk)
```

## Testing Your Migration

1. **Basic Chat Test**:
```bash
python -c "
from request_llms import LLMFactory
llm = LLMFactory.create('gpt-4o-mini')
import asyncio
async def test():
    r = await llm.chat([])
    print('OK:', r.model)
asyncio.run(test())
"
```

2. **Compatibility Test**:
```bash
python -c "
from request_llms import predict_no_ui_long_connection
# Should work without errors
"
```

3. **Full Application Test**:
```bash
python main.py
```

## Getting Help

- Check `ARCHITECTURE.md` for detailed design
- Review `request_llms/` source code
- Open an issue with the `migration` label
