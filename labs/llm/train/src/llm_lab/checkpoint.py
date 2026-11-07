"""Atomic local checkpoints, loaded with PyTorch's restricted loader."""

import os
import tempfile
from pathlib import Path

import torch

from .model import LanguageModel, ModelConfig


def save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    os.close(fd)
    try:
        torch.save(payload, temporary)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def load(path: Path, device: torch.device) -> tuple[LanguageModel, dict]:
    payload = torch.load(path, map_location="cpu", weights_only=True)
    if payload.get("format_version") != 1:
        raise ValueError("Unsupported checkpoint version")
    model = LanguageModel(ModelConfig(**payload["model_config"]))
    model.load_state_dict(payload["model"], strict=True)
    return model.to(device), payload
