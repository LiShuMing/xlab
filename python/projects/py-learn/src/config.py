"""
配置模块

提供配置文件的加载和管理功能。
支持从 YAML 文件加载配置，并自动从环境变量读取敏感信息。
"""

import os
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

import yaml


@dataclass
class ScheduleConfig:
    """调度配置"""
    timezone: str = "Asia/Tokyo"
    push_time: str = "08:00"
    reminder_time: str = "20:00"
    timeout_hours: int = 24
    reminder_enabled: bool = True


@dataclass
class TelegramConfig:
    """Telegram 配置"""
    bot_token: str = ""
    chat_id: str = ""


@dataclass
class LLMConfig:
    """LLM 配置"""
    provider: str = "openai"
    model: str = "qwen-coding-plan"
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    question_max_tokens: int = 1200
    reflect_max_tokens: int = 800
    retry_max: int = 3


@dataclass
class CrawlerConfig:
    """爬虫配置"""
    enabled: bool = False
    run_day: str = "Monday"
    run_time: str = "07:00"
    sources: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class LearningConfig:
    """学习配置"""
    default_level: int = 3
    level_up_threshold: float = 9.0
    level_up_consecutive: int = 2
    level_down_threshold: float = 4.0
    level_down_consecutive: int = 2
    weak_threshold: float = 6.0
    weak_recovery_score: float = 8.0
    weak_recovery_consecutive: int = 2
    hint_penalty: float = 1.0


@dataclass
class PathConfig:
    """路径配置"""
    data_dir: str = "./data"
    logs_dir: str = "./logs"
    topics_file: str = "./topics.yaml"


@dataclass
class Config:
    """总配置类"""
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    crawler: CrawlerConfig = field(default_factory=CrawlerConfig)
    learning: LearningConfig = field(default_factory=LearningConfig)
    paths: PathConfig = field(default_factory=PathConfig)


class ConfigLoader:
    """
    配置加载器

    负责从 YAML 文件加载配置，并自动替换环境变量占位符。
    支持 ${VAR_NAME} 和 ${VAR_NAME:default} 两种格式。
    """

    # 环境变量占位符正则
    ENV_PATTERN = re.compile(r'\$\{(\w+)(?::([^}]*))?\}')

    @classmethod
    def load(cls, config_path: str) -> Config:
        """
        从文件加载配置

        Args:
            config_path: 配置文件路径

        Returns:
            Config 对象
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 替换环境变量
        content = cls._replace_env_vars(content)

        # 解析 YAML
        data = yaml.safe_load(content)

        return cls._parse_config(data)

    @classmethod
    def _replace_env_vars(cls, content: str) -> str:
        """替换内容中的环境变量占位符"""
        def replacer(match: re.Match) -> str:
            var_name = match.group(1)
            default_value = match.group(2)

            # 优先从 ~/.env 加载
            value = cls._get_env_from_file(var_name)
            if value is None:
                value = os.environ.get(var_name)
            if value is None and default_value is not None:
                value = default_value
            if value is None:
                raise ValueError(f"环境变量未设置: {var_name}")

            return value

        return cls.ENV_PATTERN.sub(replacer, content)

    @classmethod
    def _get_env_from_file(cls, var_name: str) -> Optional[str]:
        """从 ~/.env 文件读取环境变量"""
        env_file = Path.home() / '.env'
        if not env_file.exists():
            return None

        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        key, value = line.split('=', 1)
                        if key.strip() == var_name:
                            # 去除可能的引号
                            value = value.strip().strip('"\'')
                            return value
        except Exception:
            pass

        return None

    @classmethod
    def _parse_config(cls, data: Dict[str, Any]) -> Config:
        """解析配置字典为 Config 对象"""
        config = Config()

        if 'schedule' in data:
            s = data['schedule']
            config.schedule = ScheduleConfig(
                timezone=s.get('timezone', 'Asia/Tokyo'),
                push_time=s.get('push_time', '08:00'),
                reminder_time=s.get('reminder_time', '20:00'),
                timeout_hours=s.get('timeout_hours', 24),
                reminder_enabled=s.get('reminder_enabled', True)
            )

        if 'telegram' in data:
            t = data['telegram']
            config.telegram = TelegramConfig(
                bot_token=t.get('bot_token', ''),
                chat_id=t.get('chat_id', '')
            )

        if 'llm' in data:
            l = data['llm']
            config.llm = LLMConfig(
                provider=l.get('provider', 'openai'),
                model=l.get('model', 'qwen-coding-plan'),
                base_url=l.get('base_url'),
                api_key=l.get('api_key'),
                question_max_tokens=l.get('question_max_tokens', 1200),
                reflect_max_tokens=l.get('reflect_max_tokens', 800),
                retry_max=l.get('retry_max', 3)
            )

        if 'crawler' in data:
            c = data['crawler']
            config.crawler = CrawlerConfig(
                enabled=c.get('enabled', False),
                run_day=c.get('run_day', 'Monday'),
                run_time=c.get('run_time', '07:00'),
                sources=c.get('sources', [])
            )

        if 'learning' in data:
            l = data['learning']
            config.learning = LearningConfig(
                default_level=l.get('default_level', 3),
                level_up_threshold=l.get('level_up_threshold', 9.0),
                level_up_consecutive=l.get('level_up_consecutive', 2),
                level_down_threshold=l.get('level_down_threshold', 4.0),
                level_down_consecutive=l.get('level_down_consecutive', 2),
                weak_threshold=l.get('weak_threshold', 6.0),
                weak_recovery_score=l.get('weak_recovery_score', 8.0),
                weak_recovery_consecutive=l.get('weak_recovery_consecutive', 2),
                hint_penalty=l.get('hint_penalty', 1.0)
            )

        if 'paths' in data:
            p = data['paths']
            config.paths = PathConfig(
                data_dir=p.get('data_dir', './data'),
                logs_dir=p.get('logs_dir', './logs'),
                topics_file=p.get('topics_file', './topics.yaml')
            )

        return config


def load_config(config_path: Optional[str] = None) -> Config:
    """
    加载配置的便捷函数

    Args:
        config_path: 配置文件路径，默认为当前目录的 config.yaml

    Returns:
        Config 对象
    """
    if config_path is None:
        # 尝试从多个位置查找配置文件
        candidates = [
            Path.cwd() / 'config.yaml',
            Path(__file__).parent.parent / 'config.yaml',
            Path.home() / '.daily-agent' / 'config.yaml',
        ]
        for path in candidates:
            if path.exists():
                config_path = str(path)
                break

    if config_path is None:
        raise FileNotFoundError("未找到配置文件 config.yaml")

    return ConfigLoader.load(config_path)
