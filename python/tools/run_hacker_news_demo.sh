#!/bin/bash
# Script to run the Hacker News demo with Qwen API

echo "Hacker News Summarization Demo with Qwen API"
echo "============================================="

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Python3 is not installed or not in PATH"
    exit 1
fi

# Check if required dependencies are installed
echo "Checking dependencies..."
python3 -c "import requests, bs4, openai" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing required dependencies..."
    pip3 install requests beautifulsoup4 openai
fi

echo ""
echo "To use with Qwen API, set your environment variables:"
echo "export QWEN_API_KEY='your-key-here'"
echo "export QWEN_API_BASE='https://dashscope.aliyuncs.com/compatible-mode/v1'"
echo "export MODEL_NAME='qwen-max'" # or qwen-plus, qwen-turbo
echo ""
echo "Running the demo..."
python3 hacker_news_demo.py

echo ""
echo "Demo completed!"