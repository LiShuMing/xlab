# GPT Academic - Modern Architecture

## Overview

This document describes the modernized architecture of GPT Academic, focusing on the refactored LLM provider system.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              GPT Academic                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────────┐  │
│  │   UI Layer   │    │ Plugin Layer │    │        Core Layer            │  │
│  │  (Gradio)    │◄──►│  (Plugins)   │◄──►│   (Configuration, Utils)     │  │
│  └──────────────┘    └──────────────┘    └──────────────────────────────┘  │
│                                                     │                       │
│                                                     ▼                       │
│                              ┌──────────────────────────────────────┐     │
│                              │      LLM Provider System (New)       │     │
│                              │  request_llms_new/                   │     │
│                              ├──────────────────────────────────────┤     │
│                              │  • LLMFactory (Factory Pattern)      │     │
│                              │  • LLMProvider (Abstract Base)       │     │
│                              │  • OpenAIProvider                    │     │
│                              │  • AnthropicProvider                 │     │
│                              │  • QwenProvider                      │     │
│                              └──────────────────────────────────────┘     │
│                                                     │                       │
│                              ┌─────────────────────┼─────────────────────┐ │
│                              ▼                     ▼                     ▼ │
│                         ┌─────────┐        ┌────────────┐        ┌────────┐│
│                         │ OpenAI  │        │ Anthropic  │        │  Qwen  ││
│                         │   API   │        │   (Claude) │        │(Aliyun)││
│                         └─────────┘        └────────────┘        └────────┘│
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. LLM Provider System (`request_llms_new/`)

#### Core Abstractions (`core.py`)

- **LLMProvider**: Abstract base class for all LLM providers
  - `chat()`: Single-turn chat completion
  - `chat_stream()`: Streaming chat completion
  - `count_tokens()`: Token counting
  - `max_context_length`: Property for model limits

- **LLMFactory**: Factory pattern for provider instantiation
  - `create()`: Create provider by model name
  - Auto-detects provider from model name
  - Extensible registration system

- **Data Classes**:
  - `Message`: Immutable message with role, content, metadata
  - `ChatConfig`: Configuration for chat requests
  - `ChatResponse`: Structured response with usage stats

#### Provider Implementations (`providers.py`)

| Provider | Models | Key Features |
|----------|--------|--------------|
| `OpenAIProvider` | gpt-4o, gpt-4, gpt-3.5-turbo, o1-* | Streaming, custom base_url |
| `AnthropicProvider` | claude-3-opus, claude-3-sonnet, claude-3-haiku | 200k context, reasoning |
| `QwenProvider` | qwen-max, qwen-plus, qwen-turbo, qwen3.5-plus | DashScope, custom endpoints |

#### Model Registration (`models.py`)

```python
# Register new models here
LLMFactory.register_model("my-model", "provider_name")
```

#### Backward Compatibility (`compat.py`)

Legacy functions maintained for smooth migration:
- `predict()`: Single-threaded with UI updates
- `predict_no_ui_long_connection()`: Multi-threaded for plugins

### 2. Configuration System (`config_new.py`)

Modern dataclass-based configuration with validation:

```python
@dataclass
class AppConfig:
    llm: LLMConfig
    api_keys: APIKeys
    server: ServerConfig
    proxy: ProxyConfig
    ui: UIConfig
    advanced: AdvancedConfig
```

**Loading Priority**:
1. Environment variables (`GPT_ACADEMIC_*`)
2. `config_private.py` (user overrides)
3. `config.py` (defaults)

### 3. Migration Strategy

#### Phase 1: Parallel Systems
- New code uses `request_llms_new`
- Legacy code continues using `request_llms`
- Backward compatibility layer handles both

#### Phase 2: Gradual Migration
- Update plugins one by one
- Test thoroughly before removing old code

#### Phase 3: Cleanup
- Remove `request_llms/` directory
- Update all imports

## Usage Examples

### Basic Usage (New API)

```python
import asyncio
from request_llms_new import LLMFactory, Message

async def main():
    # Create provider
    llm = LLMFactory.create("gpt-4o")
    
    # Simple chat
    messages = [
        Message.system("You are a helpful assistant."),
        Message.user("Hello!")
    ]
    
    response = await llm.chat(messages)
    print(response.message.content)

asyncio.run(main())
```

### Streaming

```python
async for chunk in llm.chat_stream(messages):
    print(chunk, end="")
```

### Legacy Compatibility

```python
# Old code continues to work
from request_llms_new import predict, predict_no_ui_long_connection

# predict() for UI interactions
yield from predict(inputs, llm_kwargs, chatbot, history, system_prompt)

# predict_no_ui_long_connection() for plugins
response = predict_no_ui_long_connection(inputs, llm_kwargs, history, sys_prompt)
```

### Custom Configuration

```python
from request_llms_new import LLMFactory

# With custom API key and base URL
llm = LLMFactory.create(
    model="qwen3.5-plus",
    api_key="sk-...",
    base_url="https://custom.endpoint.com/v1"
)
```

## Adding New Providers

1. **Create Provider Class**:

```python
from request_llms_new.core import LLMProvider, Message, ChatConfig, ChatResponse

class MyProvider(LLMProvider):
    SUPPORTED_MODELS = ["my-model"]
    
    async def chat(self, messages, config=None) -> ChatResponse:
        # Implementation
        pass
    
    async def chat_stream(self, messages, config=None):
        # Implementation
        pass
    
    def count_tokens(self, text: str) -> int:
        return len(text) // 4
    
    @property
    def max_context_length(self) -> int:
        return 4096
```

2. **Register Models**:

```python
from request_llms_new.core import LLMFactory

LLMFactory.register_model("my-model", "myprovider")
```

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` |
| `ANTHROPIC_API_KEY` | Anthropic API key | `sk-ant-...` |
| `QWEN_API_KEY` | Qwen/DashScope API key | `sk-...` |
| `QWEN_BASE_URL` | Custom Qwen endpoint | `https://...` |
| `GPT_ACADEMIC_LLM_MODEL` | Default model | `gpt-4o` |
| `GPT_ACADEMIC_WEB_PORT` | Server port | `12345` |

## Best Practices

1. **Use Type Hints**: All new code should use full type annotations
2. **Async/Await**: Prefer async APIs for I/O operations
3. **Error Handling**: Use specific exception types, log errors
4. **Documentation**: Docstrings for all public APIs
5. **Testing**: Unit tests for new providers

## Performance Considerations

- **Connection Pooling**: httpx.AsyncClient reuses connections
- **Streaming**: Use streaming for long responses to reduce latency
- **Token Counting**: Cache encoders to avoid reloading
- **Batching**: Group multiple requests when possible

## Security Notes

- Never commit API keys to version control
- Use `config_private.py` or environment variables
- API keys are not logged or exposed in error messages
- Validate URLs before making requests
