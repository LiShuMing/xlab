# AI Lab Platform - User Guide

Complete guide for using the AI Lab Platform and its modules.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Core Modules](#core-modules)
   - [Sandbox](#1-sandbox)
3. [Legacy Tools](#legacy-tools)
   - [Stock Analyzer Bot](#stock-analyzer-bot)
   - [Blog Analyzer](#blog-analyzer)
   - [StarRocks SQL Generator](#starrocks-sql-generator)
   - [ETF Momentum Analyzer](#etf-momentum-analyzer)
4. [Configuration](#configuration)
5. [Troubleshooting](#troubleshooting)

---

## Quick Start

### First Run

1. **Set up API keys** (choose at least one):
   ```bash
   # Option 1: Environment variables
   export DASHSCOPE_API_KEY="your_key_here"
   
   # Option 2: .env file
   cp .env.example .env
   # Edit .env with your keys
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Launch the platform**:
   ```bash
   streamlit run app.py
   ```

4. **Select a module** from the sidebar and start experimenting!

---

## Core Modules

### 1. Sandbox

The **Sandbox** is a free-form AI experimentation space where you can:
- Customize system prompts
- Have multi-turn conversations
- Test different models and parameters
- Track token usage and response times

#### How to Use

1. Select **"🧪 Sandbox"** from the sidebar
2. Choose a system prompt preset or write your own
3. Adjust model parameters (temperature, max tokens)
4. Type messages in the chat input

#### System Prompt Presets

| Preset | Description |
|--------|-------------|
| Default | Standard helpful assistant |
| Code Assistant | Expert programmer with clean code |
| Creative Writer | Imaginative and engaging writing |
| Technical Expert | Precise, thorough with citations |
| Simplifier | Complex topics explained simply |

#### Parameters

- **Temperature** (0.0 - 2.0): Controls randomness. Lower = more deterministic
- **Max Tokens** (100 - 4000): Maximum response length
- **Provider**: Switch between Qwen, OpenAI, Anthropic
- **Model**: Provider-specific model selection

#### Tips

- Use the **Clear Conversation** button to start fresh
- Check token estimates to manage context window
- Different presets dramatically change AI behavior

---

## Core Modules (Migrated)

### Stock Analyzer Bot

AI-powered stock analysis with investment recommendations.

#### How to Use

1. Select **"📈 Stock Analyzer Bot"** from the navigation
2. Enter your investment query (e.g., "Should I invest in Tesla?")
3. Select output language (English or Chinese)
4. Click **"Analyze Stock"**

#### Features

- Automatic company/ticker extraction
- Stock price and financial data retrieval
- Recent news aggregation
- Investment recommendation with reasoning

---

### Blog Analyzer

Extract insights from technical blogs.

#### How to Use

1. Select **"📝 Blog Analyzer"** from the navigation
2. Enter the URL of an English technical blog
3. Select analysis type:
   - **Summary** - Concise overview
   - **Technical Insights** - Key concepts explained
   - **Language Notes** - Vocabulary and translations
4. Choose output language
5. Click **"Analyze Blog"**

#### Features

- Web scraping for content extraction
- Multiple analysis modes
- Technical term explanations
- Language learning support

---

### StarRocks SQL Generator

Generate StarRocks-compatible SQL statements.

#### How to Use

1. Select **"🗄️ StarRocks SQL Generator"** from the navigation
2. Enter your SQL query in the text area
3. Click **"Generate DDL and Insert SQL"**
4. View or download results

#### Features

- CREATE TABLE DDL generation
- Sample INSERT statements
- Complex query support
- JSON export
- StarRocks syntax reference

---

### ETF Momentum Analyzer

Analyze ETF performance with momentum strategies.

#### How to Use

1. Select **"📊 ETF Momentum Analyzer"** from the navigation
2. Enter ETF symbols (comma-separated, e.g., `QQQ,VTV,VOO`)
3. Select date range
4. Click **"Run Analysis"**

#### Features

- Momentum vs equal-weight comparison
- Interactive charts
- Performance metrics
- Customizable date ranges

---

## Configuration

### Environment Variables

| Variable | Description | Required For |
|----------|-------------|--------------|
| `DASHSCOPE_API_KEY` | Qwen AI access | Qwen models |
| `OPENAI_API_KEY` | OpenAI access | GPT models |
| `ANTHROPIC_API_KEY` | Claude access | Claude models |
| `DEFAULT_PROVIDER` | Default LLM provider | All |
| `DEFAULT_MODEL` | Default model name | All |
| `DEFAULT_TEMPERATURE` | Default temperature | All |
| `DEFAULT_MAX_TOKENS` | Default token limit | All |

### Model Selection Guide

#### Qwen Models (via DashScope)

| Model | Best For | Context |
|-------|----------|---------|
| qwen-turbo | Fast, simple tasks | 8K |
| qwen-plus | Balanced quality/speed | 32K |
| qwen-max | Complex reasoning | 32K |
| qwen-max-longcontext | Long documents | 128K |

#### OpenAI Models

| Model | Best For |
|-------|----------|
| gpt-3.5-turbo | Fast, cost-effective |
| gpt-4 | Complex tasks |
| gpt-4-turbo | Latest capabilities |

#### Anthropic Models

| Model | Best For |
|-------|----------|
| claude-3-sonnet | Balanced |
| claude-3-opus | Most capable |

---

## Troubleshooting

### Common Issues

#### API Key Errors

**Problem**: "API key for provider 'xxx' is not configured"

**Solutions**:
1. Check `.env` file exists and has correct keys
2. Verify environment variables are set: `echo $DASHSCOPE_API_KEY`
3. Restart the Streamlit app after setting keys

#### Module Not Loading

**Problem**: Sidebar shows no modules

**Solutions**:
1. Check for Python import errors in console
2. Verify `modules/` directory structure
3. Ensure modules use `@register_module` decorator

#### Streaming Not Working

**Problem**: Responses appear all at once

**Solutions**:
1. Verify `streaming=True` in LLM config
2. Check callback handler is properly attached
3. Some providers may not support streaming

#### Out of Memory

**Problem**: App crashes with large conversations

**Solutions**:
1. Clear conversation history
2. Reduce `max_tokens` parameter
3. Start a new session

### Getting Help

1. Check the sidebar **"ℹ️ About"** section
2. Review this guide for specific modules
3. Check logs in `logs/` directory
4. Open an issue with error details

### Debug Mode

Enable detailed logging:

```python
# In config/settings.py or .env
LOG_LEVEL=DEBUG
```

Logs are saved to `logs/ai_lab_YYYYMMDD.log`.

---

## Tips & Best Practices

1. **Start with Sandbox** to test prompts before building modules
2. **Use Temperature 0.7** for creative tasks, 0.1 for factual tasks
3. **Clear conversations** periodically to save context window
4. **Save useful prompts** as presets in your modules
5. **Compare providers** - different models excel at different tasks

---

*Last updated: March 2025*
