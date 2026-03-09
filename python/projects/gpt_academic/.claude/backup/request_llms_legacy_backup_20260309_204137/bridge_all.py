"""
LLM Router — bridge_all.py
==========================
This module is the central dispatcher for all LLM backends. It exposes two
public functions that are called throughout the codebase:

    predict(...)                    — streaming, single-threaded, with UI
    predict_no_ui_long_connection(...)  — non-streaming-friendly, multi-thread safe

Supported providers (built-in):
    - OpenAI  (gpt-3.5, gpt-4, gpt-4o, o1, o3, o4, gpt-4.1 …)
    - Anthropic / Claude  (claude-3, claude-3.5, claude-3.7, claude-sonnet-4 …)
    - Qwen / DashScope  (qwen-turbo, qwen-plus, qwen-max, dashscope-* …)

Extensibility — dynamic prefixes (add new models without code changes):
    - "one-api-<model>(max_token=N)"   — any OpenAI-compatible one-api endpoint
    - "vllm-<model>(max_token=N)"      — local vLLM server (OpenAI-compatible)
    - "azure-<model>"                  — Azure OpenAI (mirrors built-in model)
    - "api2d-<model>"                  — api2d proxy (mirrors built-in model)

How to add a new LLM provider:
    1. Create request_llms/bridge_<provider>.py with predict() and
       predict_no_ui_long_connection() using the standard signatures.
    2. Add a model entry in the model_info dict (or a lazy-load block below).
    3. Add the model name to AVAIL_LLM_MODELS in config.py / config_private.py.
"""

import copy
import importlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Generator

import tiktoken
from loguru import logger

from toolbox import (
    apply_gpt_academic_string_mask,
    get_conf,
    read_one_api_model_name,
    trimmed_format_exc,
)

# ---------------------------------------------------------------------------
# OpenAI bridge (always loaded — no optional dependency)
# ---------------------------------------------------------------------------
from .bridge_chatgpt import predict as chatgpt_ui
from .bridge_chatgpt import predict_no_ui_long_connection as chatgpt_noui
from .bridge_chatgpt_vision import predict as chatgpt_vision_ui
from .bridge_chatgpt_vision import predict_no_ui_long_connection as chatgpt_vision_noui

# Standard OpenAI-compatible template — used for azure, one-api, vllm, etc.
from .oai_std_model_template import get_predict_function

# ---------------------------------------------------------------------------
# Colors used when querying multiple models in parallel
# ---------------------------------------------------------------------------
colors = ["#FF00FF", "#00FFFF", "#FF0000", "#990099", "#009999", "#990044"]


# ---------------------------------------------------------------------------
# Lazy tokenizer loader (avoids downloading tiktoken models at import time)
# ---------------------------------------------------------------------------
class LazyloadTiktoken:
    """Wraps a tiktoken encoder and defers loading until first use."""

    def __init__(self, model: str) -> None:
        self.model = model

    @staticmethod
    @lru_cache(maxsize=128)
    def get_encoder(model: str):
        logger.info("Loading tiktoken tokenizer — this may take a moment on first run.")
        enc = tiktoken.encoding_for_model(model)
        logger.info("Tiktoken tokenizer loaded.")
        return enc

    def encode(self, *args, **kwargs):
        return self.get_encoder(self.model).encode(*args, **kwargs)

    def decode(self, *args, **kwargs):
        return self.get_encoder(self.model).decode(*args, **kwargs)


# ---------------------------------------------------------------------------
# Endpoint configuration
# ---------------------------------------------------------------------------
API_URL_REDIRECT, AZURE_ENDPOINT, AZURE_ENGINE = get_conf(
    "API_URL_REDIRECT", "AZURE_ENDPOINT", "AZURE_ENGINE"
)

openai_endpoint = "https://api.openai.com/v1/chat/completions"
api2d_endpoint  = "https://openai.api2d.net/v1/chat/completions"

if not AZURE_ENDPOINT.endswith("/"):
    AZURE_ENDPOINT += "/"
azure_endpoint = (
    AZURE_ENDPOINT
    + f"openai/deployments/{AZURE_ENGINE}/chat/completions?api-version=2023-05-15"
)

# Backward-compat: honour deprecated API_URL option
try:
    _legacy_url = get_conf("API_URL")
    if _legacy_url != "https://api.openai.com/v1/chat/completions":
        openai_endpoint = _legacy_url
        logger.warning(
            "API_URL config option is deprecated. Please use API_URL_REDIRECT instead."
        )
except Exception:
    pass

# Apply redirect overrides from config
if openai_endpoint in API_URL_REDIRECT:
    openai_endpoint = API_URL_REDIRECT[openai_endpoint]
if api2d_endpoint in API_URL_REDIRECT:
    api2d_endpoint = API_URL_REDIRECT[api2d_endpoint]

# ---------------------------------------------------------------------------
# Tokenizers
# ---------------------------------------------------------------------------
tokenizer_gpt35 = LazyloadTiktoken("gpt-3.5-turbo")
tokenizer_gpt4  = LazyloadTiktoken("gpt-4")
get_token_num_gpt35 = lambda txt: len(tokenizer_gpt35.encode(txt, disallowed_special=()))
get_token_num_gpt4  = lambda txt: len(tokenizer_gpt4.encode(txt, disallowed_special=()))

# ---------------------------------------------------------------------------
# Read available models from config
# ---------------------------------------------------------------------------
AVAIL_LLM_MODELS, LLM_MODEL = get_conf("AVAIL_LLM_MODELS", "LLM_MODEL")
AVAIL_LLM_MODELS = AVAIL_LLM_MODELS + [LLM_MODEL]

# ===========================================================================
# model_info — the central model registry
# ===========================================================================
# Each entry must have:
#   fn_with_ui     : streaming predict function (for direct chat)
#   fn_without_ui  : non-streaming predict function (for plugins / multi-thread)
#   endpoint       : API endpoint URL (None for SDK-based models)
#   max_token      : maximum context tokens supported by the model
#   tokenizer      : LazyloadTiktoken instance (used for rough token counting)
#   token_cnt      : callable(str) -> int  (exact token count helper)
#
# Optional flags:
#   can_multi_thread          : bool — whether the model supports parallel calls
#   has_multimodal_capacity   : bool — whether the model accepts image inputs
#   enable_reasoning          : bool — whether the model exposes chain-of-thought
#   openai_disable_stream     : bool — force non-streaming (e.g. o1 series)
#   openai_disable_system_prompt : bool — omit system prompt (e.g. o1 series)
#   openai_force_temperature_one : bool — lock temperature=1 (e.g. o1 series)
# ===========================================================================
model_info: dict = {

    # ------------------------------------------------------------------
    # OpenAI — GPT-3.5 family
    # ------------------------------------------------------------------
    "gpt-3.5-turbo": {
        "fn_with_ui": chatgpt_ui,
        "fn_without_ui": chatgpt_noui,
        "endpoint": openai_endpoint,
        "max_token": 16385,
        "tokenizer": tokenizer_gpt35,
        "token_cnt": get_token_num_gpt35,
    },
    "gpt-3.5-turbo-16k": {
        "fn_with_ui": chatgpt_ui,
        "fn_without_ui": chatgpt_noui,
        "endpoint": openai_endpoint,
        "max_token": 16385,
        "tokenizer": tokenizer_gpt35,
        "token_cnt": get_token_num_gpt35,
    },
    "gpt-3.5-turbo-0125": {
        "fn_with_ui": chatgpt_ui,
        "fn_without_ui": chatgpt_noui,
        "endpoint": openai_endpoint,
        "max_token": 16385,
        "tokenizer": tokenizer_gpt35,
        "token_cnt": get_token_num_gpt35,
    },
    "gpt-3.5-random": {
        "fn_with_ui": chatgpt_ui,
        "fn_without_ui": chatgpt_noui,
        "endpoint": openai_endpoint,
        "max_token": 4096,
        "tokenizer": tokenizer_gpt4,
        "token_cnt": get_token_num_gpt4,
    },

    # ------------------------------------------------------------------
    # OpenAI — GPT-4 family
    # ------------------------------------------------------------------
    "gpt-4": {
        "fn_with_ui": chatgpt_ui,
        "fn_without_ui": chatgpt_noui,
        "endpoint": openai_endpoint,
        "max_token": 8192,
        "tokenizer": tokenizer_gpt4,
        "token_cnt": get_token_num_gpt4,
    },
    "gpt-4-32k": {
        "fn_with_ui": chatgpt_ui,
        "fn_without_ui": chatgpt_noui,
        "endpoint": openai_endpoint,
        "max_token": 32768,
        "tokenizer": tokenizer_gpt4,
        "token_cnt": get_token_num_gpt4,
    },
    "gpt-4-turbo": {
        "fn_with_ui": chatgpt_ui,
        "fn_without_ui": chatgpt_noui,
        "has_multimodal_capacity": True,
        "endpoint": openai_endpoint,
        "max_token": 128000,
        "tokenizer": tokenizer_gpt4,
        "token_cnt": get_token_num_gpt4,
    },
    "gpt-4-turbo-preview": {
        "fn_with_ui": chatgpt_ui,
        "fn_without_ui": chatgpt_noui,
        "endpoint": openai_endpoint,
        "max_token": 128000,
        "tokenizer": tokenizer_gpt4,
        "token_cnt": get_token_num_gpt4,
    },
    "gpt-4-vision-preview": {
        "fn_with_ui": chatgpt_vision_ui,
        "fn_without_ui": chatgpt_vision_noui,
        "endpoint": openai_endpoint,
        "max_token": 4096,
        "tokenizer": tokenizer_gpt4,
        "token_cnt": get_token_num_gpt4,
    },

    # ------------------------------------------------------------------
    # OpenAI — GPT-4o family
    # ------------------------------------------------------------------
    "gpt-4o": {
        "fn_with_ui": chatgpt_ui,
        "fn_without_ui": chatgpt_noui,
        "endpoint": openai_endpoint,
        "has_multimodal_capacity": True,
        "max_token": 128000,
        "tokenizer": tokenizer_gpt4,
        "token_cnt": get_token_num_gpt4,
    },
    "gpt-4o-mini": {
        "fn_with_ui": chatgpt_ui,
        "fn_without_ui": chatgpt_noui,
        "endpoint": openai_endpoint,
        "has_multimodal_capacity": True,
        "max_token": 128000,
        "tokenizer": tokenizer_gpt4,
        "token_cnt": get_token_num_gpt4,
    },
    "gpt-4o-2024-05-13": {
        "fn_with_ui": chatgpt_ui,
        "fn_without_ui": chatgpt_noui,
        "has_multimodal_capacity": True,
        "endpoint": openai_endpoint,
        "max_token": 128000,
        "tokenizer": tokenizer_gpt4,
        "token_cnt": get_token_num_gpt4,
    },
    "chatgpt-4o-latest": {
        "fn_with_ui": chatgpt_ui,
        "fn_without_ui": chatgpt_noui,
        "endpoint": openai_endpoint,
        "has_multimodal_capacity": True,
        "max_token": 128000,
        "tokenizer": tokenizer_gpt4,
        "token_cnt": get_token_num_gpt4,
    },

    # ------------------------------------------------------------------
    # OpenAI — GPT-4.1 family (2025)
    # ------------------------------------------------------------------
    "gpt-4.1": {
        "fn_with_ui": chatgpt_ui,
        "fn_without_ui": chatgpt_noui,
        "has_multimodal_capacity": True,
        "endpoint": openai_endpoint,
        "max_token": 828000,
        "tokenizer": tokenizer_gpt4,
        "token_cnt": get_token_num_gpt4,
    },
    "gpt-4.1-mini": {
        "fn_with_ui": chatgpt_ui,
        "fn_without_ui": chatgpt_noui,
        "has_multimodal_capacity": True,
        "endpoint": openai_endpoint,
        "max_token": 828000,
        "tokenizer": tokenizer_gpt4,
        "token_cnt": get_token_num_gpt4,
    },

    # ------------------------------------------------------------------
    # OpenAI — o-series (reasoning models — stream and system prompt
    # are disabled; temperature is forced to 1)
    # ------------------------------------------------------------------
    "o1-mini": {
        "fn_with_ui": chatgpt_ui,
        "fn_without_ui": chatgpt_noui,
        "endpoint": openai_endpoint,
        "can_multi_thread": True,
        "max_token": 128000,
        "tokenizer": tokenizer_gpt4,
        "token_cnt": get_token_num_gpt4,
        "openai_disable_system_prompt": True,
        "openai_disable_stream": True,
        "openai_force_temperature_one": True,
    },
    "o1-preview": {
        "fn_with_ui": chatgpt_ui,
        "fn_without_ui": chatgpt_noui,
        "endpoint": openai_endpoint,
        "max_token": 128000,
        "tokenizer": tokenizer_gpt4,
        "token_cnt": get_token_num_gpt4,
        "openai_disable_system_prompt": True,
        "openai_disable_stream": True,
        "openai_force_temperature_one": True,
    },
    "o1": {
        "fn_with_ui": chatgpt_ui,
        "fn_without_ui": chatgpt_noui,
        "endpoint": openai_endpoint,
        "max_token": 200000,
        "tokenizer": tokenizer_gpt4,
        "token_cnt": get_token_num_gpt4,
        "openai_disable_system_prompt": True,
        "openai_disable_stream": True,
        "openai_force_temperature_one": True,
    },
    "o1-2024-12-17": {
        "fn_with_ui": chatgpt_ui,
        "fn_without_ui": chatgpt_noui,
        "endpoint": openai_endpoint,
        "max_token": 200000,
        "tokenizer": tokenizer_gpt4,
        "token_cnt": get_token_num_gpt4,
        "openai_disable_system_prompt": True,
        "openai_disable_stream": True,
        "openai_force_temperature_one": True,
    },
    "o3": {
        "fn_with_ui": chatgpt_ui,
        "fn_without_ui": chatgpt_noui,
        "has_multimodal_capacity": True,
        "endpoint": openai_endpoint,
        "max_token": 828000,
        "tokenizer": tokenizer_gpt4,
        "token_cnt": get_token_num_gpt4,
        "openai_disable_system_prompt": True,
        "openai_disable_stream": True,
        "openai_force_temperature_one": True,
    },
    "o4-mini": {
        "fn_with_ui": chatgpt_ui,
        "fn_without_ui": chatgpt_noui,
        "has_multimodal_capacity": True,
        "can_multi_thread": True,
        "endpoint": openai_endpoint,
        "max_token": 828000,
        "tokenizer": tokenizer_gpt4,
        "token_cnt": get_token_num_gpt4,
    },

    # ------------------------------------------------------------------
    # Azure OpenAI (static entries for the default Azure deployment)
    # ------------------------------------------------------------------
    "azure-gpt-3.5": {
        "fn_with_ui": chatgpt_ui,
        "fn_without_ui": chatgpt_noui,
        "endpoint": azure_endpoint,
        "max_token": 4096,
        "tokenizer": tokenizer_gpt35,
        "token_cnt": get_token_num_gpt35,
    },
    "azure-gpt-4": {
        "fn_with_ui": chatgpt_ui,
        "fn_without_ui": chatgpt_noui,
        "endpoint": azure_endpoint,
        "max_token": 8192,
        "tokenizer": tokenizer_gpt4,
        "token_cnt": get_token_num_gpt4,
    },

    # ------------------------------------------------------------------
    # api2d proxy (static entry — mirrors api2d-gpt-4)
    # ------------------------------------------------------------------
    "api2d-gpt-4": {
        "fn_with_ui": chatgpt_ui,
        "fn_without_ui": chatgpt_noui,
        "endpoint": api2d_endpoint,
        "max_token": 8192,
        "tokenizer": tokenizer_gpt4,
        "token_cnt": get_token_num_gpt4,
    },
}

# ---------------------------------------------------------------------------
# api2d — auto-mirror any built-in model under the "api2d-" prefix
# ---------------------------------------------------------------------------
for _model in AVAIL_LLM_MODELS:
    if _model.startswith("api2d-") and _model.replace("api2d-", "") in model_info:
        _mi = copy.deepcopy(model_info[_model.replace("api2d-", "")])
        _mi["endpoint"] = api2d_endpoint
        model_info[_model] = _mi

# ---------------------------------------------------------------------------
# azure — auto-mirror any built-in model under the "azure-" prefix
# ---------------------------------------------------------------------------
for _model in AVAIL_LLM_MODELS:
    if _model.startswith("azure-") and _model.replace("azure-", "") in model_info:
        _mi = copy.deepcopy(model_info[_model.replace("azure-", "")])
        _mi["endpoint"] = azure_endpoint
        model_info[_model] = _mi

# ===========================================================================
# Anthropic / Claude — lazy-load to avoid hard dependency when unused
# ===========================================================================
_claude_models = [
    # Claude 3 family
    "claude-3-haiku-20240307",
    "claude-3-sonnet-20240229",
    "claude-3-opus-20240229",
    # Claude 3.5 family
    "claude-3-5-sonnet-20240620",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    # Claude 3.7 family
    "claude-3-7-sonnet-20250219",
    # Claude 4 / Sonnet 4
    "claude-sonnet-4-5",
    # Legacy
    "claude-2.1",
    "claude-2.0",
    "claude-instant-1.2",
]
if any(m in _claude_models for m in AVAIL_LLM_MODELS):
    try:
        from .bridge_claude import predict as claude_ui
        from .bridge_claude import predict_no_ui_long_connection as claude_noui

        for _m in _claude_models:
            # max_token: older models 100k, newer models 200k
            _max_tok = 100_000 if _m.startswith("claude-instant") or _m.startswith("claude-2.0") else 200_000
            model_info[_m] = {
                "fn_with_ui": claude_ui,
                "fn_without_ui": claude_noui,
                "endpoint": None,  # Claude SDK handles the endpoint internally
                "max_token": _max_tok,
                "tokenizer": tokenizer_gpt35,
                "token_cnt": get_token_num_gpt35,
            }
    except Exception:
        logger.error(trimmed_format_exc())

# ===========================================================================
# Qwen / DashScope — lazy-load to avoid hard dependency when unused
# ===========================================================================
_qwen_models = [
    # Standard Qwen API models
    "qwen-turbo",
    "qwen-plus",
    "qwen-max",
    "qwen-max-latest",
    "qwen-max-2025-01-25",
    "qwen3.5-plus",
    # DashScope-hosted third-party / Qwen3 models
    "dashscope-deepseek-r1",
    "dashscope-deepseek-v3",
    "dashscope-qwen3-14b",
    "dashscope-qwen3-32b",
    "dashscope-qwen3-235b-a22b",
]
if any(m in _qwen_models for m in AVAIL_LLM_MODELS):
    try:
        from .bridge_qwen import predict as qwen_ui
        from .bridge_qwen import predict_no_ui_long_connection as qwen_noui

        model_info.update({
            "qwen-turbo": {
                "fn_with_ui": qwen_ui,
                "fn_without_ui": qwen_noui,
                "can_multi_thread": True,
                "endpoint": None,
                "max_token": 100_000,
                "tokenizer": tokenizer_gpt35,
                "token_cnt": get_token_num_gpt35,
            },
            "qwen-plus": {
                "fn_with_ui": qwen_ui,
                "fn_without_ui": qwen_noui,
                "can_multi_thread": True,
                "endpoint": None,
                "max_token": 129_024,
                "tokenizer": tokenizer_gpt35,
                "token_cnt": get_token_num_gpt35,
            },
            "qwen3.5-plus": {
                "fn_with_ui": qwen_ui,
                "fn_without_ui": qwen_noui,
                "can_multi_thread": True,
                "endpoint": None,
                "max_token": 129_024,
                "tokenizer": tokenizer_gpt35,
                "token_cnt": get_token_num_gpt35,
            },
            "qwen-max": {
                "fn_with_ui": qwen_ui,
                "fn_without_ui": qwen_noui,
                "can_multi_thread": True,
                "endpoint": None,
                "max_token": 30_720,
                "tokenizer": tokenizer_gpt35,
                "token_cnt": get_token_num_gpt35,
            },
            "qwen-max-latest": {
                "fn_with_ui": qwen_ui,
                "fn_without_ui": qwen_noui,
                "can_multi_thread": True,
                "endpoint": None,
                "max_token": 30_720,
                "tokenizer": tokenizer_gpt35,
                "token_cnt": get_token_num_gpt35,
            },
            "qwen-max-2025-01-25": {
                "fn_with_ui": qwen_ui,
                "fn_without_ui": qwen_noui,
                "can_multi_thread": True,
                "endpoint": None,
                "max_token": 30_720,
                "tokenizer": tokenizer_gpt35,
                "token_cnt": get_token_num_gpt35,
            },
            # DashScope-hosted DeepSeek models (via Qwen bridge)
            "dashscope-deepseek-r1": {
                "fn_with_ui": qwen_ui,
                "fn_without_ui": qwen_noui,
                "enable_reasoning": True,
                "can_multi_thread": True,
                "endpoint": None,
                "max_token": 57_344,
                "tokenizer": tokenizer_gpt35,
                "token_cnt": get_token_num_gpt35,
            },
            "dashscope-deepseek-v3": {
                "fn_with_ui": qwen_ui,
                "fn_without_ui": qwen_noui,
                "can_multi_thread": True,
                "endpoint": None,
                "max_token": 57_344,
                "tokenizer": tokenizer_gpt35,
                "token_cnt": get_token_num_gpt35,
            },
            # DashScope-hosted Qwen3 models
            "dashscope-qwen3-14b": {
                "fn_with_ui": qwen_ui,
                "fn_without_ui": qwen_noui,
                "enable_reasoning": True,
                "can_multi_thread": True,
                "endpoint": None,
                "max_token": 129_024,
                "tokenizer": tokenizer_gpt35,
                "token_cnt": get_token_num_gpt35,
            },
            "dashscope-qwen3-32b": {
                "fn_with_ui": qwen_ui,
                "fn_without_ui": qwen_noui,
                "can_multi_thread": True,
                "endpoint": None,
                "max_token": 129_024,
                "tokenizer": tokenizer_gpt35,
                "token_cnt": get_token_num_gpt35,
            },
            "dashscope-qwen3-235b-a22b": {
                "fn_with_ui": qwen_ui,
                "fn_without_ui": qwen_noui,
                "can_multi_thread": True,
                "endpoint": None,
                "max_token": 129_024,
                "tokenizer": tokenizer_gpt35,
                "token_cnt": get_token_num_gpt35,
            },
        })
    except Exception:
        logger.error(trimmed_format_exc())

# ===========================================================================
# Dynamic prefix handlers — extend model support without code changes
# ===========================================================================

# ---------------------------------------------------------------------------
# "one-api-<model>(max_token=N)" — OpenAI-compatible one-api proxy
# ---------------------------------------------------------------------------
for _model in [m for m in AVAIL_LLM_MODELS if m.startswith("one-api-")]:
    try:
        _origin, _max_tok = read_one_api_model_name(_model)
    except Exception:
        logger.error(f"one-api model '{_model}' has an invalid max_token value.")
        continue
    _base_name = _origin.replace("one-api-", "", 1)
    _base_info = model_info.get(_base_name)
    _entry: dict = {
        "fn_with_ui": chatgpt_ui,
        "fn_without_ui": chatgpt_noui,
        "can_multi_thread": True,
        "endpoint": openai_endpoint,
        "max_token": _max_tok,
        "tokenizer": tokenizer_gpt35,
        "token_cnt": get_token_num_gpt35,
    }
    # Inherit multimodal flag from the base model if known
    if _base_info and _base_info.get("has_multimodal_capacity"):
        _entry["has_multimodal_capacity"] = True
    model_info[_model] = _entry

# ---------------------------------------------------------------------------
# "vllm-<model>(max_token=N)" — local vLLM OpenAI-compatible server
# ---------------------------------------------------------------------------
for _model in [m for m in AVAIL_LLM_MODELS if m.startswith("vllm-")]:
    try:
        _, _max_tok = read_one_api_model_name(_model)
    except Exception:
        logger.error(f"vllm model '{_model}' has an invalid max_token value.")
        continue
    model_info[_model] = {
        "fn_with_ui": chatgpt_ui,
        "fn_without_ui": chatgpt_noui,
        "can_multi_thread": True,
        "endpoint": openai_endpoint,
        "max_token": _max_tok,
        "tokenizer": tokenizer_gpt35,
        "token_cnt": get_token_num_gpt35,
    }

# ---------------------------------------------------------------------------
# AZURE_CFG_ARRAY — multiple Azure deployments defined in config
# ---------------------------------------------------------------------------
AZURE_CFG_ARRAY = get_conf("AZURE_CFG_ARRAY")
if AZURE_CFG_ARRAY:
    for _az_name, _az_cfg in AZURE_CFG_ARRAY.items():
        if not _az_name.startswith("azure"):
            raise ValueError(
                f"All models in AZURE_CFG_ARRAY must start with 'azure', got: '{_az_name}'"
            )
        _az_endpoint = (
            _az_cfg["AZURE_ENDPOINT"]
            + f"openai/deployments/{_az_cfg['AZURE_ENGINE']}"
            + "/chat/completions?api-version=2023-05-15"
        )
        model_info[_az_name] = {
            "fn_with_ui": chatgpt_ui,
            "fn_without_ui": chatgpt_noui,
            "endpoint": _az_endpoint,
            "azure_api_key": _az_cfg["AZURE_API_KEY"],
            "max_token": _az_cfg["AZURE_MODEL_MAX_TOKEN"],
            "tokenizer": tokenizer_gpt35,
            "token_cnt": get_token_num_gpt35,
        }
        if _az_name not in AVAIL_LLM_MODELS:
            AVAIL_LLM_MODELS.append(_az_name)

# ===========================================================================
# Internal routing helpers
# ===========================================================================

import core_functional
from shared_utils.doc_loader_dynamic import (
    contain_uploaded_files,
    load_uploaded_files,
    load_web_content,
    start_with_url,
)


def LLM_CATCH_EXCEPTION(f):
    """
    Decorator that catches any exception from an LLM call and writes the
    traceback into observe_window[0] instead of crashing the thread.
    Used for multi-model parallel queries.
    """
    def decorated(
        inputs: str,
        llm_kwargs: dict,
        history: list,
        sys_prompt: str,
        observe_window: list,
        console_silence: bool,
    ):
        try:
            return f(inputs, llm_kwargs, history, sys_prompt, observe_window, console_silence)
        except Exception:
            tb = "\n```\n" + trimmed_format_exc() + "\n```\n"
            observe_window[0] = tb
            return tb

    return decorated


def execute_model_override(
    llm_kwargs: dict, additional_fn: str, method
) -> tuple:
    """
    Check whether the clicked button in the core function panel specifies a
    ModelOverride.  If so, swap the active model to the override model.

    Returns (llm_kwargs, additional_fn, method) — possibly updated.
    """
    functional = core_functional.get_core_functions()
    if additional_fn in functional and "ModelOverride" in functional[additional_fn]:
        importlib.reload(core_functional)
        functional = core_functional.get_core_functions()
        override_model = functional[additional_fn]["ModelOverride"]
        if override_model not in model_info:
            raise ValueError(
                f"ModelOverride '{override_model}' is not a supported model. "
                "Check AVAIL_LLM_MODELS in config."
            )
        method = model_info[override_model]["fn_with_ui"]
        llm_kwargs["llm_model"] = override_model
    return llm_kwargs, additional_fn, method


# ===========================================================================
# Public API
# ===========================================================================

def predict_no_ui_long_connection(
    inputs: str,
    llm_kwargs: dict,
    history: list,
    sys_prompt: str,
    observe_window: list | None = None,
    console_silence: bool = False,
) -> str:
    """
    Send a request to the selected LLM and wait for the full response.

    This function is designed for use inside plugin functions and supports
    multi-threading.  It does NOT update the Gradio UI.

    Parameters
    ----------
    inputs : str
        The user's input text for this turn.
    llm_kwargs : dict
        LLM parameters dict (must contain 'llm_model', 'temperature', etc.).
        Use '&' to query multiple models in parallel, e.g. "gpt-4o&qwen-max".
    history : list
        Alternating list of [user, assistant, user, assistant, …] messages.
    sys_prompt : str
        System-level instruction sent before the conversation.
    observe_window : list | None
        Two-element list used for cross-thread progress streaming:
            observe_window[0] — output buffer (read by the UI thread)
            observe_window[1] — watchdog timestamp (written by the UI thread)
    console_silence : bool
        If True, suppress per-token stdout logging.

    Returns
    -------
    str
        The model's complete response text.
    """
    inputs = apply_gpt_academic_string_mask(inputs, mode="show_llm")
    model = llm_kwargs["llm_model"]

    if "&" not in model:
        # Single model path (common case)
        method = model_info[model]["fn_without_ui"]
        return method(inputs, llm_kwargs, history, sys_prompt, observe_window, console_silence)

    # Multi-model parallel path
    models = model.split("&")
    n_model = len(models)
    assert len(observe_window) == 3, "observe_window must have length 3 for multi-model queries"

    window_mutex = [["", time.time(), ""] for _ in range(n_model)] + [True]
    executor = ThreadPoolExecutor(max_workers=4)

    futures = []
    for i, m in enumerate(models):
        kw = copy.deepcopy(llm_kwargs)
        kw["llm_model"] = m
        method = model_info[m]["fn_without_ui"]
        futures.append(
            executor.submit(LLM_CATCH_EXCEPTION(method), inputs, kw, history, sys_prompt, window_mutex[i], console_silence)
        )

    def _mutex_manager(window_mutex: list, observe_window: list) -> None:
        """Merge per-model buffers into observe_window for live preview."""
        while window_mutex[-1]:
            time.sleep(0.25)
            for i in range(n_model):
                window_mutex[i][1] = observe_window[1]  # refresh watchdog
            parts = [
                f'【{models[i]} 说】: <font color="{colors[i % len(colors)]}"> {window_mutex[i][0]} </font>'
                for i in range(n_model)
            ]
            observe_window[0] = "<br/><br/>\n\n---\n\n".join(parts)

    t_merger = threading.Thread(target=_mutex_manager, args=(window_mutex, observe_window), daemon=True)
    t_merger.start()

    while not all(f.done() for f in futures):
        time.sleep(1)
    executor.shutdown()
    window_mutex[-1] = False  # stop merger thread

    results = [
        f'【{models[i]} 说】: <font color="{colors[i % len(colors)]}"> {futures[i].result()} </font>'
        for i in range(n_model)
    ]
    return "<br/><br/>\n\n---\n\n".join(results)


def predict(
    inputs: str,
    llm_kwargs: dict,
    plugin_kwargs: dict,
    chatbot,
    history: list | None = None,
    system_prompt: str = "",
    stream: bool = True,
    additional_fn: str | None = None,
) -> Generator:
    """
    Send a request to the selected LLM and stream the response back to
    the Gradio UI.  This is the main chat function.

    Parameters
    ----------
    inputs : str
        The user's input text for this turn.
    llm_kwargs : dict
        LLM parameters (model name, temperature, api_key, …).
    plugin_kwargs : dict
        Extra parameters forwarded from advanced plugin dialogs.
    chatbot : ChatBotWithCookies
        Gradio chatbot component handle — yield updates to refresh the UI.
    history : list | None
        Alternating [user, assistant, …] conversation history.
    system_prompt : str
        System-level instruction prepended to every request.
    stream : bool
        Deprecated — kept for API compatibility. Streaming is always on.
    additional_fn : str | None
        Name of the core-function button that was clicked (e.g. "translate").

    Yields
    ------
    Gradio UI updates via update_ui().
    """
    from toolbox import update_ui

    if history is None:
        history = []

    inputs = apply_gpt_academic_string_mask(inputs, mode="show_llm")

    if llm_kwargs["llm_model"] not in model_info:
        chatbot.append([
            inputs,
            f"Model '{llm_kwargs['llm_model']}' is not available.<br/>"
            "(1) Check AVAIL_LLM_MODELS in config.<br/>"
            "(2) Check request_llms/bridge_all.py model registry.",
        ])
        yield from update_ui(chatbot=chatbot, history=history)
        return

    method = model_info[llm_kwargs["llm_model"]]["fn_with_ui"]

    if additional_fn:
        llm_kwargs, additional_fn, method = execute_model_override(llm_kwargs, additional_fn, method)

    if start_with_url(inputs):
        yield from load_web_content(inputs, chatbot, history)
        return

    if contain_uploaded_files(inputs):
        inputs = yield from load_uploaded_files(
            inputs, method, llm_kwargs, plugin_kwargs, chatbot, history, system_prompt, stream, additional_fn
        )

    yield from method(inputs, llm_kwargs, plugin_kwargs, chatbot, history, system_prompt, stream, additional_fn)
