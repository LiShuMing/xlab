# Finance AI Toolkit

A unified platform for financial analysis, blog content analysis, technical reporting, and database management using Qwen AI via DashScope.

## Features

1. **Stock Analyzer Bot** - Analyze stocks and make investment decisions with AI
2. **Blog Analyzer** - Extract insights from technical blogs
3. **StarRocks SQL Generator** - Generate SQL DDL and INSERT statements for StarRocks
4. **ETF Momentum Analyzer** - Analyze ETF performance with momentum strategies

## Requirements

- Python 3.7+
- DashScope API key (get it from [DashScope Console](https://dashscope.console.aliyun.com/))

## Installation

1. Clone or download this repository
2. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

The application requires a DashScope API key to function. You can provide it in one of the following ways:

1. **Environment Variable**:
   ```bash
   export DASHSCOPE_API_KEY="your_dashscope_api_key_here"
   ```

2. **Direct Input**: Enter the API key in the application interface (less secure)

## Usage

Run the application with:

```bash
streamlit run app.py
```

Then:
1. Enter your DashScope API Key in the sidebar
2. Select the tool you want to use from the navigation dropdown
3. Follow the specific instructions for each tool

## Tools Overview

### Stock Analyzer Bot
Analyze stocks and get investment recommendations with AI assistance.

### Blog Analyzer
Analyze English technical blogs and extract key insights, technical concepts, and language learning notes.

### StarRocks SQL Generator
Generate StarRocks-compatible CREATE TABLE DDL and INSERT statements based on your SQL queries.

### ETF Momentum Analyzer
Analyze ETF performance using momentum strategies and backtest trading approaches.

## Notes

- All tools use Qwen AI via the DashScope API
- The application is designed to be modular and extensible
- Each tool can be run independently if needed