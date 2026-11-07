"""Uncached autoregressive reference generation."""

import math
from pathlib import Path

import torch

from .checkpoint import load
from .runtime import device_for
from .tokenizer import BOS, EOS, PAD, decode, encode


@torch.no_grad()
def generate(
    path: Path,
    prompt: str,
    max_new_tokens: int,
    device_name: str,
    temperature: float = 0.0,
    seed: int = 42,
) -> dict:
    if max_new_tokens < 0 or temperature < 0 or not math.isfinite(temperature):
        raise ValueError("Generation length and temperature must be finite and nonnegative")
    device = device_for(device_name)
    model, _ = load(path, device)
    model.eval()
    tokens = [BOS] + encode(prompt)
    if len(tokens) > model.config.context_length:
        raise ValueError("Prompt exceeds context capacity")
    rng = torch.Generator().manual_seed(seed)
    generated = []
    reason = "length"
    for _ in range(max_new_tokens):
        if len(tokens) > model.config.context_length:
            reason = "context_limit"
            break
        logits = model(torch.tensor([tokens], device=device))[0, -1].float().cpu()
        # Generation-only mask; raw forward logits and reference tensors remain unchanged.
        logits[BOS] = logits[PAD] = float("-inf")
        next_id = (
            int(logits.argmax())
            if temperature == 0
            else int(torch.multinomial((logits / temperature).softmax(-1), 1, generator=rng))
        )
        generated.append(next_id)
        tokens.append(next_id)
        if next_id == EOS:
            reason = "eos"
            break
    return {
        "prompt": prompt,
        "completion": decode(generated),
        "token_ids": generated,
        "finish_reason": reason,
        "device": str(device),
    }
