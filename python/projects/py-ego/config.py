"""
LLM 配置模块 - 从 ~/.env 加载配置
"""
import os
from dotenv import load_dotenv
from pathlib import Path

# 加载 ~/.env 文件
default_env_path = Path.home() / ".env"
env_path = os.getenv("ENV_PATH", str(default_env_path))
load_dotenv(dotenv_path=env_path)

# LLM 配置
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "120"))

# Embedding 配置（使用本地模型作为默认，因为 Kimi 暂不支持 embeddings）
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
USE_LOCAL_EMBEDDING = os.getenv("USE_LOCAL_EMBEDDING", "true").lower() == "true"

# 日志级别
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# OpenAI 兼容客户端配置
def get_openai_client():
    """获取 OpenAI 兼容客户端"""
    from openai import OpenAI
    return OpenAI(
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        timeout=LLM_TIMEOUT
    )
