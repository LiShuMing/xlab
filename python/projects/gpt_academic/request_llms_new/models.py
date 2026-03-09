"""
Model definitions and registrations.

This module registers all supported models with their respective providers,
making them available through the LLMFactory.
"""

from .core import LLMFactory


def register_all_models() -> None:
    """
    Register all supported models with the factory.
    
    This function is called automatically when the module is imported.
    Add new models here to make them available in the system.
    """
    
    # ========== OpenAI Models ==========
    openai_models = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo",
        "o1-preview",
        "o1-mini",
        "o3-mini",
    ]
    
    for model in openai_models:
        LLMFactory.register_model(model, "openai")
    
    # ========== Anthropic (Claude) Models ==========
    anthropic_models = [
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
        "claude-3-5-sonnet-20240620",
        "claude-3-5-sonnet-20241022",
    ]
    
    for model in anthropic_models:
        LLMFactory.register_model(model, "anthropic")
    
    # ========== Qwen (Aliyun) Models ==========
    qwen_models = [
        "qwen-max",
        "qwen-max-latest",
        "qwen-max-2025-01-25",
        "qwen-plus",
        "qwen-turbo",
        "qwen3.5-plus",
        "dashscope-qwen3-14b",
        "dashscope-qwen3-32b",
        "dashscope-qwen3-235b-a22b",
        "dashscope-deepseek-r1",
        "dashscope-deepseek-v3",
    ]
    
    for model in qwen_models:
        LLMFactory.register_model(model, "qwen")


# Auto-register on import
register_all_models()


def list_models_by_provider() -> dict:
    """
    Get all registered models grouped by provider.
    
    Returns:
        Dictionary mapping provider names to lists of models.
    """
    from .core import LLMFactory
    
    result = {
        "openai": [],
        "anthropic": [],
        "qwen": [],
    }
    
    for model, provider in LLMFactory.MODEL_PROVIDERS.items():
        if provider in result:
            result[provider].append(model)
    
    return result


def get_model_info(model: str) -> dict:
    """
    Get information about a specific model.
    
    Args:
        model: The model identifier
        
    Returns:
        Dictionary with model information
    """
    from .providers import OpenAIProvider, AnthropicProvider, QwenProvider
    
    provider_map = {
        "openai": (OpenAIProvider, "https://platform.openai.com"),
        "anthropic": (AnthropicProvider, "https://console.anthropic.com"),
        "qwen": (QwenProvider, "https://dashscope.console.aliyun.com"),
    }
    
    # Find provider for model
    provider_name = None
    for m, p in LLMFactory.MODEL_PROVIDERS.items():
        if m == model:
            provider_name = p
            break
    
    if not provider_name or provider_name not in provider_map:
        return {"error": f"Unknown model: {model}"}
    
    provider_class, console_url = provider_map[provider_name]
    
    return {
        "model": model,
        "provider": provider_name,
        "provider_class": provider_class.__name__,
        "console_url": console_url,
        "max_context": provider_class.CONTEXT_LENGTHS.get(model, "Unknown"),
        "supported": model in provider_class.SUPPORTED_MODELS,
    }
