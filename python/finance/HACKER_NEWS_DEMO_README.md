# Hacker News Summarizer with Qwen API

This demo visits Hacker News (https://news.ycombinator.com/news), extracts the top 10 stories, and uses Qwen API to summarize and translate them to Chinese.

## Features

- Web scraping using requests and BeautifulSoup
- LLM-powered summarization using Qwen API
- Translation to Chinese
- Clean formatted output

## Prerequisites

- Python 3.8+
- `openai` library
- `requests` library
- `beautifulsoup4` library
- Access to Qwen API (or OpenAI API as fallback)

## Installation

```bash
pip install openai requests beautifulsoup4
```

## Configuration

You need to set your Qwen API key as an environment variable:

```bash
export QWEN_API_KEY='your-qwen-api-key-here'
```

Alternatively, you can use an `.env` file:

```bash
echo "QWEN_API_KEY=your-qwen-api-key-here" > .env
```

By default, the script will use the Qwen API endpoint, but you can customize it:

```bash
export QWEN_API_BASE='https://dashscope.aliyuncs.com/compatible-mode/v1'
export MODEL_NAME='qwen-max'  # or 'qwen-plus', 'qwen-turbo', etc.
```

## Usage

### Quick Run
Run the provided script to start the demo:

```bash
./run_hacker_news_demo.sh
```

### Direct Run
Run the script directly:

```bash
python hacker_news_demo.py
```

## How It Works

1. **Web Scraping**: Uses requests and BeautifulSoup to fetch and parse Hacker News, extracting the top 10 stories
2. **Processing**: For each story, sends a prompt to Qwen API asking for:
   - English summary in 1-2 sentences
   - Chinese translation of both the title and summary
3. **Output**: Displays results in a formatted way with both English and Chinese

## Output Format

The script will output results in this format for each story:

```
1. Story:
--------------------------------------------------
Original Title: [Original English title]

Summary in English: [English summary here]

标题 (Title in Chinese): [Translated title here]

摘要 (Summary in Chinese): [Translated summary here]
--------------------------------------------------
```

## Troubleshooting

- If you get API errors, check your QWEN_API_KEY
- If web scraping fails, make sure the target website is accessible
- If you get rate limits from the API, consider reducing the number of stories processed
- If no API key is found, the script will run in demo mode with sample outputs

## Customization

You can modify the script to:
- Change the number of stories processed
- Adjust the prompt for different summarization styles
- Change the output format
- Use different Qwen models

## API Configuration

The script uses the OpenAI-compatible interface for Qwen APIs. Make sure you have:
- Correct API key with sufficient quota
- Appropriate permissions for the model you're using
- Correct base URL for the Qwen API endpoint

## Demo Mode

When no API key is provided, the script runs in demo mode, showing sample outputs for demonstration purposes.