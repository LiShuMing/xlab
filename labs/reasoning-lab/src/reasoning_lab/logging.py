"""Human-readable progress logging; machine-readable records stay in the run directory.

stdout is a data channel: one JSON record per training step and one result object per
command. Every human line therefore goes to stderr and, for a run, to ``run.log``.

人类可读的日志走 stderr 与 run.log，stdout 只留给 JSON 结果：
这样 `... | jq` 不会因为多出一行进度文本而解析失败。
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

ENVIRONMENT_VARIABLE = "REASONING_LAB_LOG_LEVEL"
DEFAULT_LEVEL = "INFO"
FORMAT = "%(asctime)s %(levelname)-5s %(name)s: %(message)s"
DATE_FORMAT = "%H:%M:%S"
ROOT = "reasoning_lab"

stream_handler: logging.Handler | None = None


def parse_level(name: str) -> int:
    value = logging.getLevelName(name.strip().upper())
    if not isinstance(value, int):
        raise ValueError(f"Unknown log level {name!r}; use DEBUG, INFO, WARNING or ERROR")
    return value


def level_from_environment(default: str = DEFAULT_LEVEL) -> int:
    return parse_level(os.environ.get(ENVIRONMENT_VARIABLE, default))


def configure(stream=None) -> logging.Logger:
    """安装唯一的 stderr handler；重复进入也不能叠加前缀。

    命名空间固定为 reasoning_lab，并关闭 propagate：
    第三方库的日志不会混进 run.log，只留本包自己的记录。
    """
    global stream_handler

    logger = logging.getLogger(ROOT)
    logger.setLevel(level_from_environment())
    # Keep third-party libraries out of this namespace and out of the run log.
    logger.propagate = False
    if stream_handler is None:
        stream_handler = logging.StreamHandler(stream or sys.stderr)
        stream_handler.setFormatter(logging.Formatter(FORMAT, DATE_FORMAT))
        logger.addHandler(stream_handler)
    return logger


def attach_file(path: Path) -> logging.Handler:
    """把日志镜像到 run 目录，让一次跑完的实验能自解释。

    用 handler 而不是在模块里直接写文件：所有模块共用同一个 logger，
    挂一次就能全部进日志。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter(FORMAT, DATE_FORMAT))
    logging.getLogger(ROOT).addHandler(handler)
    return handler


def detach(handler: logging.Handler) -> None:
    """run 结束时必须摘掉：否则下一条命令的日志会继续写进上一个 run 的文件。"""
    logger = logging.getLogger(ROOT)
    logger.removeHandler(handler)
    handler.close()


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"{ROOT}.{name}")


def duration(value: float) -> str:
    """Keep sub-minute budgets readable instead of printing 3725.4."""
    return f"{value:.3f}s" if value < 60 else f"{value / 60:.1f}min"
