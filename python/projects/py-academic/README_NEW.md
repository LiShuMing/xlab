# GPT Academic - Modernized

A streamlined, modernized version of GPT Academic focused on the three major LLM providers: **OpenAI**, **Anthropic (Claude)**, and **Qwen (Aliyun)**.

## ✨ What's New

- **Modern Python Architecture**: Type hints, dataclasses, async/await
- **Clean Provider System**: Factory pattern with easy extensibility
- **Simplified Dependencies**: Focused on core providers
- **Better Documentation**: Comprehensive guides and examples
- **Backward Compatible**: Legacy plugins continue to work

## 🚀 Quick Start

### 1. Installation

```bash
# Clone repository
git clone https://github.com/binary-husky/gpt_academic.git
cd gpt_academic

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Set your API key(s):

```bash
# Option 1: Environment variables
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export QWEN_API_KEY="sk-..."

# Option 2: Create config_private.py
cat > config_private.py << 'EOF'
OPENAI_API_KEY = "sk-..."
ANTHROPIC_API_KEY = "sk-ant-..."
QWEN_API_KEY = "sk-..."
LLM_MODEL = "gpt-4o"
EOF
```

### 3. Run

```bash
# Modern entry point
python main_new.py

# Or use the original
python main.py
```

## 📖 Usage

### Web Interface

Access the web UI at `http://localhost:12345` (or the port shown in console).

### Python API

```python
import asyncio
from request_llms import LLMFactory, Message

async def chat():
    # Create provider
    llm = LLMFactory.create("gpt-4o")
    
    # Build conversation
    messages = [
        Message.system("You are a helpful assistant."),
        Message.user("Explain quantum computing in simple terms.")
    ]
    
    # Get response
    response = await llm.chat(messages)
    print(response.message.content)
    
    # Or stream the response
    async for chunk in llm.chat_stream(messages):
        print(chunk, end="")

asyncio.run(chat())
```

### Legacy Compatibility

```python
# Old code continues to work
from request_llms import predict, predict_no_ui_long_connection

# Use in plugins
response = predict_no_ui_long_connection(
    inputs="Hello",
    llm_kwargs={"llm_model": "gpt-4o"},
    history=[],
    sys_prompt="You are helpful."
)
```

## 🔧 Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | - |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `QWEN_API_KEY` | Qwen/DashScope API key | - |
| `QWEN_BASE_URL` | Custom Qwen endpoint | - |
| `GPT_ACADEMIC_LLM_MODEL` | Default model | `gpt-4o-mini` |
| `GPT_ACADEMIC_WEB_PORT` | Server port | Random |
| `GPT_ACADEMIC_USE_PROXY` | Enable proxy | `False` |

### Supported Models

| Provider | Models |
|----------|--------|
| **OpenAI** | gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-4, gpt-3.5-turbo, o1-preview, o1-mini, o3-mini |
| **Anthropic** | claude-3-opus-20240229, claude-3-sonnet-20240229, claude-3-haiku-20240307, claude-3-5-sonnet-* |
| **Qwen** | qwen-max, qwen-plus, qwen-turbo, qwen3.5-plus, dashscope-qwen3-32b, dashscope-qwen3-14b |

## 🏗️ Architecture

```
gpt_academic/
├── request_llms/              # New LLM provider system
│   ├── __init__.py
│   ├── core.py               # Core abstractions (LLMProvider, LLMFactory)
│   ├── providers.py          # Provider implementations
│   ├── models.py             # Model registrations
│   └── compat.py             # Backward compatibility layer
├── config_new.py              # Modern configuration system
├── main_new.py                # New entry point
├── ARCHITECTURE.md            # Architecture documentation
└── MIGRATION_GUIDE.md         # Migration guide
```

## 🔌 Extending with Custom Providers

```python
from request_llms.core import LLMProvider, LLMFactory, Message, ChatConfig, ChatResponse

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

# Register
LLMFactory.register_model("my-model", "myprovider")

# Use
llm = LLMFactory.create("my-model")
```

## 🐳 Docker Deployment

```bash
# Build
docker build -t gpt-academic .

# Run
docker run -p 12345:12345 \
  -e OPENAI_API_KEY="sk-..." \
  -e GPT_ACADEMIC_LLM_MODEL="gpt-4o" \
  gpt-academic
```

Or use docker-compose:

```yaml
version: '3'
services:
  gpt_academic:
    build: .
    ports:
      - "12345:12345"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - GPT_ACADEMIC_LLM_MODEL=gpt-4o
```

## 📚 Documentation

- [Architecture Guide](ARCHITECTURE.md) - System design and components
- [Migration Guide](MIGRATION_GUIDE.md) - Migrate from legacy code
- [API Reference](docs/api_reference.md) - Python API documentation

## 🛠️ Development

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/

# Type checking
mypy request_llms/

# Linting
ruff check .
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the GNU GPL v3 License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Original GPT Academic by [binary-husky](https://github.com/binary-husky)
- OpenAI, Anthropic, and Alibaba for their excellent APIs
