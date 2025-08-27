# Finance AI Toolkit - User Guide

This document provides instructions on how to use each tool in the Finance AI Toolkit.

## 1. Stock Analyzer Bot

The Stock Analyzer Bot helps you analyze stocks and make investment decisions with AI assistance.

### How to Use:
1. Select "Stock Analyzer Bot" from the navigation dropdown
2. Enter your investment-related query (e.g., "Is it a good time to invest in Tesla?")
3. Select the output language (English or Chinese)
4. Click "Analyze Stock" to get AI-powered investment recommendations

### Features:
- Extracts company name and stock ticker from your query
- Gathers stock price data, financial statements, and recent news
- Provides detailed analysis with investment recommendations
- Supports multiple languages

## 2. Blog Analyzer

The Blog Analyzer extracts insights from technical blogs, including summaries, technical concepts, and language learning notes.

### How to Use:
1. Select "Blog Analyzer" from the navigation dropdown
2. Enter the URL of an English technical blog
3. Select the type of analysis you want (Summary, Technical Insights, Language Notes)
4. Choose the output language
5. Click "Analyze Blog" to get insights

### Features:
- Web scraping to extract blog content
- Generates concise summaries of blog posts
- Extracts technical insights and explains key terms
- Provides language learning notes with translations
- Supports both English and Chinese output

## 3. StarRocks SQL Generator

The StarRocks SQL Generator creates StarRocks-compatible CREATE TABLE DDL and INSERT statements based on your SQL queries.

### How to Use:
1. Select "StarRocks SQL Generator" from the navigation dropdown
2. Enter your SQL query in the text area
3. Click "Generate DDL and Insert SQL"
4. View the generated statements and download if needed

### Features:
- Generates valid StarRocks CREATE TABLE statements
- Creates sample INSERT statements for testing
- Supports complex SQL queries
- Provides downloadable JSON results
- Includes StarRocks syntax reference

## 4. ETF Momentum Analyzer

The ETF Momentum Analyzer helps you analyze ETF performance using momentum strategies and backtest trading approaches.

### How to Use:
1. Select "ETF Momentum Analyzer" from the navigation dropdown
2. Enter ETF symbols separated by commas (e.g., QQQ,VTV,VOO)
3. Select the date range for analysis
4. Click "Run Analysis" to see the momentum strategy performance

### Features:
- Compares momentum strategy performance with equal-weight benchmark
- Visualizes results with interactive charts
- Shows performance metrics for both strategies
- Supports customizable date ranges
- Works with any ETF symbols

## API Configuration

All AI-powered tools require a DashScope API key:
1. Get your API key from [DashScope Console](https://dashscope.console.aliyun.com/)
2. Enter it in the sidebar API configuration section
3. The key will be used for all AI-powered features

## Troubleshooting

### Common Issues:
1. **API Key Error**: Make sure you've entered a valid DashScope API key
2. **Import Errors**: Ensure all requirements are installed with `pip install -r requirements.txt`
3. **Network Issues**: Check your internet connection for tools that fetch data online

### Getting Help:
- Check the README.md for detailed installation instructions
- Refer to individual tool sections in this guide
- For bugs, please open an issue on the project repository