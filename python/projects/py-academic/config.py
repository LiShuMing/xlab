"""
Configuration file for py-academic.

Priority: environment variables (including ~/.env) > config_private.py > config.py

LLM API keys are NOT configured here. Set them in ~/.env:

    # ~/.env
    API_KEY=sk-...                    # OpenAI
    ANTHROPIC_API_KEY=sk-ant-...      # Claude / Anthropic
    QWEN_API_KEY=sk-...               # Qwen / DashScope
    DASHSCOPE_API_KEY=sk-...          # Alternative Qwen key name
    DEEPSEEK_API_KEY=sk-...           # DeepSeek

Non-secret settings (model selection, UI, etc.) can still be overridden via
config_private.py or environment variables.
"""

# --------------- LLM model selection ---------------

# Default model shown in the dropdown. Must be in AVAIL_LLM_MODELS.
LLM_MODEL = "claude-3-sonnet-20240229"

AVAIL_LLM_MODELS = [
    # Anthropic / Claude
    "claude-3-sonnet-20240229",
    "claude-3-5-sonnet-20241022",
    "claude-3-opus-20240229",
    # OpenAI
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
    "o1",
    "o1-mini",
    # Qwen / DashScope
    "qwen-max",
    "qwen-plus",
    "dashscope-qwen3-14b",
    "dashscope-qwen3-32b",
    "dashscope-deepseek-r1",
    "dashscope-deepseek-v3",
    # DeepSeek
    "deepseek-chat",
    "deepseek-reasoner",
]

EMBEDDING_MODEL = "text-embedding-3-small"

# Custom Qwen-compatible base URL (optional, for third-party proxies)
QWEN_BASE_URL = ""

# Models used when "Query multiple models" plugin is invoked (separated by &)
MULTI_QUERY_LLM_MODELS = "gpt-3.5-turbo&claude-3-sonnet-20240229"

# --------------- Network / proxy ---------------

# Set USE_PROXY=True and configure proxies below if you need a proxy.
USE_PROXY = False
if USE_PROXY:
    proxies = {
        "http":  "socks5h://localhost:11284",
        "https": "socks5h://localhost:11284",
    }
else:
    proxies = None

# URL redirect for OpenAI-compatible endpoints (advanced, rarely needed)
API_URL_REDIRECT = {}

# Organization ID for OpenAI (rarely needed)
API_ORG = ""

# Azure OpenAI configuration (single-deployment mode)
AZURE_ENDPOINT = ""
AZURE_ENGINE = ""
AZURE_CFG_ARRAY = {}

# --------------- UI settings ---------------

# Theme: "Default", "Chuanhu-Small-and-Beautiful", "High-Contrast", "Gstaff/Xkcd", "NoCrypt/Miku"
THEME = "Default"
AVAIL_THEMES = ["Default", "Chuanhu-Small-and-Beautiful", "High-Contrast", "Gstaff/Xkcd", "NoCrypt/Miku"]

FONT = "Theme-Default-Font"
AVAIL_FONTS = [
    "Theme-Default-Font",
    "Helvetica",
    "ui-sans-serif",
    "sans-serif",
    "system-ui",
]

# Default system prompt
INIT_SYS_PROMPT = "Serve me as a writing and programming assistant."

# Chat window height (only effective when LAYOUT="TOP-DOWN")
CHATBOT_HEIGHT = 1115

# Code syntax highlighting
CODE_HIGHLIGHT = True

# Window layout: "LEFT-RIGHT" or "TOP-DOWN"
LAYOUT = "LEFT-RIGHT"

# Dark mode
DARK_MODE = True

# Auto-clear input box after submission
AUTO_CLEAR_TXT = False

# Decorative live2d mascot
ADD_WAIFU = False

# Plugin groups shown by default in the UI
DEFAULT_FN_GROUPS = ['chat', 'coding', 'academic', 'agent']

# --------------- Server settings ---------------

# Web server port (-1 = random)
WEB_PORT = -1

# Open browser automatically on startup
AUTO_OPEN_BROWSER = True

# Number of parallel Gradio sessions
CONCURRENT_COUNT = 100

# Sub-path for the app (e.g. "/gpt_academic" to serve at http://ip:port/gpt_academic/)
CUSTOM_PATH = "/"

# HTTPS key and certificate (leave empty to use HTTP)
SSL_KEYFILE = ""
SSL_CERTFILE = ""

# Authentication: [("username", "password"), ...]
AUTHENTICATION = []

# --------------- Request settings ---------------

# Timeout in seconds for LLM requests
TIMEOUT_SECONDS = 30

# Max retries on network failure
MAX_RETRY = 2

# Number of parallel worker threads for multi-threaded plugins
DEFAULT_WORKER_NUM = 8

# --------------- Paths ---------------

# Temporary upload directory
PATH_PRIVATE_UPLOAD = "private_upload"

# Log directory
PATH_LOGGING = "gpt_log"

# ArXiv paper cache directory
ARXIV_CACHE_DIR = "gpt_log/arxiv_cache"

# --------------- Optional features ---------------

# Contexts in which the proxy is applied (advanced, rarely changed)
WHEN_TO_USE_PROXY = [
    "Connect_OpenAI", "Download_LLM", "Download_Gradio_Theme", "Connect_Grobid",
    "Warmup_Modules", "Nougat_Download", "AutoGen", "Connect_OpenAI_Embedding",
]

# Hot-reload plugins without restarting the server
PLUGIN_HOT_RELOAD = False

# Maximum number of custom basic buttons
NUM_CUSTOM_BASIC_BTN = 4

# Allow reconfiguring the app via natural language (risky, off by default)
ALLOW_RESET_CONFIG = False

# Run AutoGen code in Docker containers
AUTOGEN_USE_DOCKER = False

# GROBID servers for high-quality PDF parsing (can list multiple for load balancing)
GROBID_URLS = [
    "https://qingxu98-grobid.hf.space",
    "https://qingxu98-grobid2.hf.space",
]

# SearXNG internet search service URLs
SEARXNG_URLS = [f"https://kaletianlre-beardvs{i}dd.hf.space/" for i in range(1, 5)]

# Media agent service URLs
DAAS_SERVER_URLS = [f"https://niuziniu-biligpt{i}.hf.space/stream" for i in range(1, 5)]

# Text-to-speech settings
TTS_TYPE = "EDGE_TTS"  # Options: EDGE_TTS / LOCAL_SOVITS_API / DISABLE
GPT_SOVITS_URL = ""
EDGE_TTS_VOICE = "en-US-JennyNeural"

# Audio input (Aliyun real-time speech recognition)
ENABLE_AUDIO = False
ALIYUN_TOKEN = ""
ALIYUN_APPKEY = ""
ALIYUN_ACCESSKEY = ""
ALIYUN_SECRET = ""

# Context auto-clipping (reduces token usage for long conversations)
AUTO_CONTEXT_CLIP_ENABLE = False
AUTO_CONTEXT_CLIP_TRIGGER_TOKEN_LEN = 30 * 1000
AUTO_CONTEXT_MAX_ROUND = 64
AUTO_CONTEXT_MAX_CLIP_RATIO = [
    0.80, 0.60, 0.45, 0.25, 0.20, 0.18, 0.16, 0.14,
    0.12, 0.10, 0.08, 0.07, 0.06, 0.05, 0.04, 0.03, 0.02, 0.01,
]

# Custom API key format pattern (advanced, rarely needed)
CUSTOM_API_KEY_PATTERN = ""

# Baidu Qianfan model (if using qianfan model)
BAIDU_CLOUD_QIANFAN_MODEL = 'ERNIE-Bot'

# Local Qwen model selection
QWEN_LOCAL_MODEL_SELECTION = "Qwen/Qwen-1_8B-Chat-Int8"

# Local ChatGLM model path
CHATGLM_LOCAL_MODEL_PATH = "THUDM/glm-4-9b-chat"
CHATGLM_PTUNING_CHECKPOINT = ""

# Local LLM device and quantization
LOCAL_MODEL_DEVICE = "cpu"   # Options: "cpu", "cuda"
LOCAL_MODEL_QUANT = "FP16"   # Options: "FP16", "INT4", "INT8"
