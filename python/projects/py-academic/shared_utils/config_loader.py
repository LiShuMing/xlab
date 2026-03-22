import importlib
import time
import os
from functools import lru_cache
from shared_utils.colorful import log亮红, log亮绿, log亮蓝

pj = os.path.join
default_user_name = 'default_user'

# LLM API key names that must come from ~/.env (never from config files)
_LLM_API_KEY_NAMES = {
    "API_KEY",
    "ANTHROPIC_API_KEY",
    "DASHSCOPE_API_KEY",
    "QWEN_API_KEY",
    "DEEPSEEK_API_KEY",
    "AZURE_API_KEY",
    "ZHIPUAI_API_KEY",
    "MOONSHOT_API_KEY",
    "YIMODEL_API_KEY",
    "ARK_API_KEY",
    "GROK_API_KEY",
    "MINIMAX_API_KEY",
    "GEMINI_API_KEY",
    "HUGGINGFACE_ACCESS_TOKEN",
    "XFYUN_API_KEY",
    "XFYUN_APPID",
    "XFYUN_API_SECRET",
    "MATHPIX_APPID",
    "MATHPIX_APPKEY",
    "DOC2X_API_KEY",
    "JINA_API_KEY",
    "SEMANTIC_SCHOLAR_KEY",
    "SLACK_CLAUDE_BOT_ID",
    "SLACK_CLAUDE_USER_TOKEN",
    "BAIDU_CLOUD_API_KEY",
    "BAIDU_CLOUD_SECRET_KEY",
    "TAICHU_API_KEY",
    "ALIYUN_TOKEN",
    "ALIYUN_APPKEY",
    "ALIYUN_ACCESSKEY",
    "ALIYUN_SECRET",
}


def _load_dotenv():
    """Load ~/.env file into os.environ if it exists. Called once at startup."""
    env_path = os.path.expanduser("~/.env")
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # Strip surrounding quotes
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                # Only set if not already present (env vars take precedence)
                if key and key not in os.environ:
                    os.environ[key] = value
        log亮绿(f"[CONFIG] Loaded ~/.env from {env_path}")
    except Exception as e:
        log亮红(f"[CONFIG] Failed to load ~/.env: {e}")


# Load ~/.env at module import time
_load_dotenv()


def read_env_variable(arg, default_value):
    """
    Read a config value from environment variables.
    Supports two naming patterns:
      - GPT_ACADEMIC_<ARG>  (higher priority)
      - <ARG>
    """
    arg_with_prefix = "GPT_ACADEMIC_" + arg
    if arg_with_prefix in os.environ:
        env_arg = os.environ[arg_with_prefix]
    elif arg in os.environ:
        env_arg = os.environ[arg]
    else:
        raise KeyError
    log亮绿(f"[ENV_VAR] Loading {arg}, default: {default_value!r} --> override: {env_arg!r}")
    try:
        if isinstance(default_value, bool):
            env_arg = env_arg.strip()
            if env_arg == 'True':
                r = True
            elif env_arg == 'False':
                r = False
            else:
                log亮红('Expected `True` or `False`, got:', env_arg)
                r = default_value
        elif isinstance(default_value, int):
            r = int(env_arg)
        elif isinstance(default_value, float):
            r = float(env_arg)
        elif isinstance(default_value, str):
            r = env_arg.strip()
        elif isinstance(default_value, dict):
            r = eval(env_arg)
        elif isinstance(default_value, list):
            r = eval(env_arg)
        elif default_value is None:
            assert arg == "proxies"
            r = eval(env_arg)
        else:
            log亮红(f"[ENV_VAR] {arg} does not support environment variable override!")
            raise KeyError
    except:
        log亮红(f"[ENV_VAR] Failed to load environment variable {arg}!")
        raise KeyError(f"[ENV_VAR] Failed to load environment variable {arg}!")

    log亮绿(f"[ENV_VAR] Successfully loaded {arg}")
    return r


@lru_cache(maxsize=128)
def read_single_conf_with_lru_cache(arg):
    from shared_utils.key_pattern_manager import is_any_api_key

    # LLM API keys must come from ~/.env / environment variables only
    if arg in _LLM_API_KEY_NAMES:
        try:
            default_ref = getattr(importlib.import_module('config'), arg)
        except AttributeError:
            default_ref = ""
        try:
            r = read_env_variable(arg, default_ref)
        except KeyError:
            r = ""  # Return empty string if not set in environment
            log亮红(f"[CONFIG] LLM key '{arg}' not found in ~/.env or environment. "
                    f"Please add it to ~/.env.")
        return r

    try:
        # Priority 1: environment variable
        default_ref = getattr(importlib.import_module('config'), arg)
        r = read_env_variable(arg, default_ref)
    except:
        try:
            # Priority 2: config_private.py
            r = getattr(importlib.import_module('config_private'), arg)
        except:
            # Priority 3: config.py default
            r = getattr(importlib.import_module('config'), arg)

    # Validate API_URL_REDIRECT format
    if arg == 'API_URL_REDIRECT':
        oai_rd = r.get("https://api.openai.com/v1/chat/completions", None)
        if oai_rd and not oai_rd.endswith('/completions'):
            log亮红("\n\n[API_URL_REDIRECT] API_URL_REDIRECT appears malformed. "
                    "Please check the configuration.")
            time.sleep(5)

    if arg == 'API_KEY':
        log亮蓝(f"[API_KEY] Supports OpenAI and Azure api-keys. "
                f"Multiple keys can be comma-separated: API_KEY=\"key1,key2,key3\"")
        log亮蓝(f"[API_KEY] You can set this in ~/.env or pass a temporary key in the input box.")
        if is_any_api_key(r):
            log亮绿(f"[API_KEY] API_KEY loaded: {r[:15]}***")
        else:
            if r:
                log亮红(f"[API_KEY] API_KEY ({r[:15]}***) does not match any known key format.")

    if arg == 'proxies':
        if not read_single_conf_with_lru_cache('USE_PROXY'):
            r = None
        if r is None:
            log亮红('[PROXY] No proxy configured. OpenAI models may be unreachable without a proxy.')
        else:
            log亮绿('[PROXY] Proxy configured:', str(r))
            assert isinstance(r, dict), 'proxies must be a dict. Check the proxies config format.'
    return r


@lru_cache(maxsize=128)
def get_conf(*args):
    """
    Retrieve one or more configuration values.

    Priority: ~/.env / environment variables > config_private.py > config.py
    LLM API keys are loaded exclusively from ~/.env / environment variables.
    """
    res = []
    for arg in args:
        r = read_single_conf_with_lru_cache(arg)
        res.append(r)
    if len(res) == 1:
        return res[0]
    return res


def set_conf(key, value):
    from toolbox import read_single_conf_with_lru_cache
    read_single_conf_with_lru_cache.cache_clear()
    get_conf.cache_clear()
    os.environ[key] = str(value)
    altered = get_conf(key)
    return altered


def set_multi_conf(dic):
    for k, v in dic.items():
        set_conf(k, v)
    return
