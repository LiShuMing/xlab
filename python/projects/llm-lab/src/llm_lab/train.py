"""Train a tiny model with deterministic batch sampling and resume."""

import math
import time
from pathlib import Path

import torch
from torch.nn import functional as F

from . import checkpoint
from .data import prepare
from .model import LanguageModel, ModelConfig
from .runtime import device_for, environment, synchronize
from .tokenizer import PAD


@torch.no_grad()
def evaluate(model: LanguageModel, data: tuple, device: torch.device, batch_size: int) -> float:
    model.eval()
    total, count = 0.0, 0
    x, y = data
    for start in range(0, len(x), batch_size):
        target = y[start : start + batch_size].to(device)
        logits = model(x[start : start + batch_size].to(device))
        total += F.cross_entropy(
            logits.flatten(0, 1), target.flatten(), ignore_index=PAD, reduction="sum"
        ).item()
        count += int((target != PAD).sum().item())
    return total / count


def train(
    config: dict,
    out: Path,
    device_name: str,
    data_path: Path | None = None,
    resume: Path | None = None,
) -> dict:
    c = ModelConfig(**config["model"])
    t = config["training"]
    steps, batch = t["steps"], t["batch_size"]
    if steps <= 0 or batch <= 0 or not math.isfinite(t["learning_rate"]) or t["learning_rate"] <= 0:
        raise ValueError("steps, batch_size and learning_rate must be positive")
    device = device_for(device_name)
    torch.set_num_threads(t.get("threads", 4))
    torch.manual_seed(t["seed"])
    rng = torch.Generator().manual_seed(t["seed"])
    train_data, valid_data, provenance = prepare(data_path, c.context_length, t["seed"])
    model = LanguageModel(c).to(device)
    start = 0
    payload = None
    if resume:
        model, payload = checkpoint.load(resume, device)
        if model.config != c or payload["data"] != provenance:
            raise ValueError("Resume model or data differs from checkpoint")
        if payload["training"]["batch_size"] != batch:
            raise ValueError("Resume batch_size differs from checkpoint")
        rng.set_state(payload["batch_rng"])
        torch.set_rng_state(payload["torch_rng"])
        start = payload["step"]
    optimizer = torch.optim.AdamW(model.parameters(), lr=t["learning_rate"])
    if payload:
        optimizer.load_state_dict(payload["optimizer"])
        if payload["training"]["learning_rate"] != t["learning_rate"]:
            raise ValueError("Resume learning_rate differs from checkpoint")
    if start >= steps:
        raise ValueError("steps is total target and must exceed checkpoint step")
    initial = evaluate(model, valid_data, device, batch)
    history = []
    synchronize(device)
    begin = time.perf_counter()
    for step in range(start, steps):
        model.train()
        indices = torch.randint(len(train_data[0]), (batch,), generator=rng)
        x, y = (part[indices].to(device) for part in train_data)
        optimizer.zero_grad(set_to_none=True)
        logits = model(x)
        loss = F.cross_entropy(logits.flatten(0, 1), y.flatten(), ignore_index=PAD)
        if not torch.isfinite(loss).item():
            raise ValueError("Nonfinite training loss")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        if (step + 1) % max(1, steps // 5) == 0:
            record = {"step": step + 1, "train_loss": loss.item()}
            history.append(record)
            print(record, flush=True)
    synchronize(device)
    elapsed = time.perf_counter() - begin
    final = evaluate(model, valid_data, device, batch)
    checkpoint.save(
        out / "last.pt",
        {
            "format_version": 1,
            "model_config": c.to_dict(),
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "step": steps,
            "training": t,
            "data": provenance,
            "batch_rng": rng.get_state(),
            "torch_rng": torch.get_rng_state(),
        },
    )
    report = {
        "environment": environment(),
        "device": str(device),
        "dtype": "float32",
        "parameters": sum(p.numel() for p in model.parameters()),
        "config": config,
        "data": provenance,
        "initial_validation_loss": initial,
        "final_validation_loss": final,
        "training_seconds": elapsed,
        "start_step": start,
        "history": history,
        "checkpoint": str(out / "last.pt"),
    }
    return report
