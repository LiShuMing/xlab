#!/usr/bin/env python3
"""Test Anthropic SDK with the API."""
import asyncio
import os
from dotenv import load_dotenv
from anthropic import AsyncAnthropic

load_dotenv(override=True)

async def test():
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("QWEN_API_KEY")
    base_url = os.environ.get("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    model = os.environ.get("ANTHROPIC_MODEL") or os.environ.get("QWEN_MODEL", "qwen-max")
    
    print(f"Base URL: {base_url}")
    print(f"Model: {model}")
    
    async with AsyncAnthropic(
        api_key=api_key,
        base_url=base_url,
        timeout=120.0,
    ) as client:
        message = await client.messages.create(
            model=model,
            max_tokens=2000,
            temperature=0.3,
            messages=[
                {"role": "user", "content": "Write a brief report about Snowflake. Keep it under 500 words."},
            ],
        )
        
        print(f"\nStop reason: {message.stop_reason}")
        print(f"Usage: {message.usage}")
        print(f"\nNumber of content blocks: {len(message.content)}")
        
        for i, block in enumerate(message.content):
            print(f"\n--- Block {i} ---")
            print(f"Type: {type(block).__name__}")
            if hasattr(block, 'text'):
                print(f"Text: {block.text[:200]}...")
            elif hasattr(block, 'thinking'):
                print(f"Thinking: {block.thinking[:200]}...")
            else:
                print(f"Content: {str(block)[:200]}...")

if __name__ == "__main__":
    asyncio.run(test())
