#!/usr/bin/env python3
"""
Quick launcher for the modernized GPT Academic.

This script:
1. Loads environment variables from ~/.bashrc if needed
2. Validates configuration
3. Launches the modern entry point

Usage:
    python run_modern.py
    python run_modern.py --model qwen3.5-plus
    python run_modern.py --port 8080 --debug
"""

import os
import subprocess
import sys
from pathlib import Path


def load_bashrc_env():
    """Load environment variables from ~/.bashrc."""
    bashrc = Path.home() / ".bashrc"
    if not bashrc.exists():
        return
    
    # Source bashrc and print env
    result = subprocess.run(
        ["bash", "-c", "source ~/.bashrc 2>/dev/null && env"],
        capture_output=True,
        text=True,
    )
    
    # Parse and set relevant env vars
    for line in result.stdout.split("\n"):
        if "=" in line:
            key, _, value = line.partition("=")
            # Only set if not already set
            if key not in os.environ:
                os.environ[key] = value


def main():
    """Main entry point."""
    # Load environment from bashrc
    load_bashrc_env()
    
    # Check for required vars
    required_vars = ["QWEN_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"]
    found = [v for v in required_vars if os.getenv(v)]
    
    if not found:
        print("⚠️  Warning: No API keys found in environment")
        print("Please set one of:")
        print("  - QWEN_API_KEY")
        print("  - OPENAI_API_KEY")
        print("  - ANTHROPIC_API_KEY")
        print("")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != "y":
            return 1
    else:
        print(f"✅ Found API keys: {', '.join(found)}")
    
    # Pass through to main_new.py
    args = sys.argv[1:]
    
    # If --model not specified and QWEN_API_KEY is set, default to qwen
    if "--model" not in args and os.getenv("QWEN_API_KEY"):
        if not any(os.getenv(v) for v in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"]):
            args.extend(["--model", "qwen3.5-plus"])
    
    cmd = [sys.executable, "main_new.py"] + args
    
    print(f"🚀 Starting GPT Academic Modern...")
    print(f"   Command: {' '.join(cmd)}")
    print("")
    
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
