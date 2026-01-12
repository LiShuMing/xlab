# Project Structure

This directory contains multiple sub-projects that have been unified into a single application:

## Original Sub-Projects:
1. `blog-analyzer/` - Blog content analysis tool
2. `finance-unified/` - Original unified project (now legacy)
3. `starrocks-sql-generator/` - StarRocks SQL generation tool
4. `stock-analyzer-bot/` - Stock analysis tool
5. `yfinace/` - Basic yfinance usage examples

## Unified Project:
`finance-unified-project/` - The new unified application that combines all tools

## How to Run the Unified Project:
```bash
cd finance-unified-project
./run.sh
```

This will:
1. Activate the virtual environment
2. Install required dependencies
3. Start the Streamlit application

The unified project includes:
- Stock Analyzer Bot
- Blog Analyzer
- StarRocks SQL Generator
- ETF Momentum Analyzer