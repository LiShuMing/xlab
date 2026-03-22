#!/bin/bash

# Run script for Finance AI Toolkit

# Check if virtual environment exists
if [ ! -d "../.venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv ../.venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source ../.venv/bin/activate

# Run the application
echo "Starting Finance AI Toolkit..."
streamlit run app.py
