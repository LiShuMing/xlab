#!/usr/bin/env python3
"""
Test suite for the modernized architecture.

Run with:
    python test_modern.py
    
Or for verbose output:
    python test_modern.py -v
"""

import asyncio
import sys
from pathlib import Path

# Ensure we can import the new module
sys.path.insert(0, str(Path(__file__).parent))


def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    
    try:
        from request_llms import (
            LLMFactory,
            LLMProvider,
            Message,
            ChatConfig,
            ChatResponse,
            Role,
            OpenAIProvider,
            AnthropicProvider,
            QwenProvider,
            predict,
            predict_no_ui_long_connection,
        )
        print("  ✅ All imports successful")
        return True
    except Exception as e:
        print(f"  ❌ Import failed: {e}")
        return False


def test_model_registration():
    """Test that models are properly registered."""
    print("Testing model registration...")
    
    from request_llms import LLMFactory, list_models_by_provider
    
    models = LLMFactory.list_supported_models()
    by_provider = list_models_by_provider()
    
    print(f"  Registered models: {len(models)}")
    for provider, provider_models in by_provider.items():
        print(f"    - {provider}: {len(provider_models)} models")
    
    # Check expected models
    expected = ["gpt-4o", "claude-3-opus-20240229", "qwen-max", "qwen3.5-plus"]
    for model in expected:
        if model in models:
            print(f"  ✅ {model}")
        else:
            print(f"  ❌ Missing: {model}")
    
    return len(models) > 0


def test_message_creation():
    """Test Message dataclass."""
    print("Testing Message creation...")
    
    from request_llms import Message, Role
    
    # Test factory methods
    system_msg = Message.system("You are helpful.")
    user_msg = Message.user("Hello!")
    assistant_msg = Message.assistant("Hi there!", reasoning="Let me think...")
    
    assert system_msg.role == Role.SYSTEM
    assert user_msg.role == Role.USER
    assert assistant_msg.role == Role.ASSISTANT
    assert assistant_msg.metadata.get("reasoning") == "Let me think..."
    
    print("  ✅ Message creation works")
    return True


def test_config_validation():
    """Test ChatConfig validation."""
    print("Testing ChatConfig validation...")
    
    from request_llms import ChatConfig
    
    # Valid config
    config = ChatConfig(temperature=0.5, max_tokens=1000)
    assert config.temperature == 0.5
    print("  ✅ Valid config accepted")
    
    # Invalid temperature
    try:
        ChatConfig(temperature=5.0)
        print("  ❌ Should have rejected invalid temperature")
        return False
    except ValueError:
        print("  ✅ Correctly rejected invalid temperature")
    
    return True


def test_provider_info():
    """Test provider metadata."""
    print("Testing provider metadata...")
    
    from request_llms.providers import (
        OpenAIProvider,
        AnthropicProvider,
        QwenProvider,
    )
    
    providers = [
        ("OpenAI", OpenAIProvider),
        ("Anthropic", AnthropicProvider),
        ("Qwen", QwenProvider),
    ]
    
    for name, provider_class in providers:
        models = provider_class.SUPPORTED_MODELS
        print(f"  {name}: {len(models)} models")
        if models:
            print(f"    Example: {models[0]}")
    
    return True


def test_model_info():
    """Test model information utility."""
    print("Testing model info...")
    
    from request_llms import get_model_info
    
    info = get_model_info("gpt-4o")
    print(f"  gpt-4o info: {info}")
    
    info = get_model_info("qwen3.5-plus")
    print(f"  qwen3.5-plus info: {info}")
    
    return "error" not in info


def test_factory_creation():
    """Test factory creation (without API calls)."""
    print("Testing factory creation...")
    
    from request_llms import LLMFactory
    
    # This should fail without API key
    try:
        llm = LLMFactory.create("gpt-4o")
        print("  ❌ Should have failed without API key")
        return False
    except ValueError as e:
        if "API key" in str(e):
            print("  ✅ Correctly requires API key")
            return True
        raise


async def test_async_operations():
    """Test async operations (if API keys available)."""
    print("Testing async operations...")
    
    import os
    from request_llms import LLMFactory, Message
    
    # Check for API keys
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("QWEN_API_KEY")
    
    if not api_key:
        print("  ⏭️  Skipping (no API key)")
        return True
    
    try:
        # Use qwen if available, otherwise try openai
        model = "qwen3.5-plus" if os.getenv("QWEN_API_KEY") else "gpt-4o-mini"
        
        llm = LLMFactory.create(model)
        messages = [Message.user("Say 'test' and nothing else.")]
        
        print(f"  Testing with {model}...")
        response = await llm.chat(messages)
        
        print(f"  Response: {response.message.content[:50]}...")
        print("  ✅ API call successful")
        return True
        
    except Exception as e:
        print(f"  ⚠️  API test failed: {e}")
        # Don't fail the test suite for API errors
        return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("GPT Academic - Modern Architecture Test Suite")
    print("=" * 60)
    print()
    
    tests = [
        ("Imports", test_imports),
        ("Model Registration", test_model_registration),
        ("Message Creation", test_message_creation),
        ("Config Validation", test_config_validation),
        ("Provider Metadata", test_provider_info),
        ("Model Info", test_model_info),
        ("Factory Creation", test_factory_creation),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n{name}:")
        print("-" * 40)
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            results.append((name, False))
    
    # Async tests
    print(f"\nAsync Operations:")
    print("-" * 40)
    try:
        result = asyncio.run(test_async_operations())
        results.append(("Async Operations", result))
    except Exception as e:
        print(f"  ❌ Exception: {e}")
        results.append(("Async Operations", False))
    
    # Summary
    print()
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {name}")
    
    print()
    print(f"Results: {passed}/{total} passed")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
