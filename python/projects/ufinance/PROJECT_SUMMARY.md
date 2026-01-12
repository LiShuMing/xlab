# Finance AI Toolkit - Unified Project

This project unifies multiple finance-related tools into a single application:

1. **Stock Analyzer Bot** - Analyze stocks and make investment decisions with AI
2. **Blog Analyzer** - Extract insights from technical blogs
3. **StarRocks SQL Generator** - Generate SQL DDL and INSERT statements for StarRocks
4. **ETF Momentum Analyzer** - Analyze ETF performance with momentum strategies

## Project Structure

```
finance-unified-project/
├── app.py                 # Main Streamlit application
├── requirements.txt       # Python dependencies
├── README.md             # Project documentation
├── run.sh                # Run script
├── .streamlit/
│   └── config.toml       # Streamlit configuration
├── apps/                 # Individual tool modules
│   ├── __init__.py
│   ├── stock_analyzer.py
│   ├── blog_analyzer.py
│   ├── starrocks_sql_generator.py
│   └── etf_analyzer.py
├── tests/
│   └── test_app.py       # Unit tests
└── assets/               # Static assets (if needed)
```

## Features

- **Unified Interface**: All tools accessible from a single Streamlit application
- **Qwen AI Integration**: Uses DashScope API for advanced AI capabilities
- **Modular Design**: Each tool is a separate module for easy maintenance
- **Easy Deployment**: Simple run script to start the application
- **Configurable**: Streamlit configuration for customizing the UI

## How to Run

1. Make sure you have Python 3.7+ installed
2. Navigate to the project directory
3. Run the application using either:
   - `./run.sh` (recommended)
   - Or manually:
     ```bash
     source ../.venv/bin/activate
     pip install -r requirements.txt
     streamlit run app.py
     ```

## API Keys

To use the AI-powered features, you'll need a DashScope API key:
1. Get your API key from [DashScope Console](https://dashscope.console.aliyun.com/)
2. Set it as an environment variable:
   ```bash
   export DASHSCOPE_API_KEY="your_api_key_here"
   ```
3. Or enter it directly in the application interface

## Tools Overview

### Stock Analyzer Bot
Analyze stocks and get investment recommendations with AI assistance. Enter your investment-related query and get AI-powered analysis.

### Blog Analyzer
Analyze English technical blogs and extract key insights, technical concepts, and language learning notes. Simply provide a blog URL to get started.

### StarRocks SQL Generator
Generate StarRocks-compatible CREATE TABLE DDL and INSERT statements based on your SQL queries. Enter any SQL query to generate the corresponding StarRocks statements.

### ETF Momentum Analyzer
Analyze ETF performance using momentum strategies and backtest trading approaches. Compare different ETFs and see how momentum strategies perform against benchmarks.