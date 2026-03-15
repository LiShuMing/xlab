"""日志系统 - 基于 structlog 的结构化日志"""

import logging
import sys
from typing import Any

import structlog
from structlog.typing import Processor


def get_logger(name: str = "invest-ai") -> structlog.BoundLogger:
    """获取结构化日志器"""
    return structlog.get_logger(name)


def setup_logging(level: str = "INFO") -> None:
    """配置日志系统"""

    # 标准库日志配置
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )

    # structlog 配置
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
        structlog.dev.ConsoleRenderer(),
    ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
