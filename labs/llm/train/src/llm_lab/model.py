"""Explicit pre-norm decoder; no opaque Transformer wrapper."""

import math
from dataclasses import asdict, dataclass

import torch
from torch import nn


@dataclass(frozen=True)
class ModelConfig:
    kind: str = "tiny"
    vocab_size: int = 259
    context_length: int = 64
    num_layers: int = 2
    hidden_size: int = 64
    num_heads: int = 4
    ffn_size: int = 256
    layer_norm_eps: float = 1e-5

    def __post_init__(self) -> None:
        if self.kind not in {"tiny", "bigram"}:
            raise ValueError("kind must be tiny or bigram")
        for key in ("context_length", "num_layers", "hidden_size", "num_heads", "ffn_size"):
            if type(getattr(self, key)) is not int or getattr(self, key) <= 0:
                raise ValueError(f"{key} must be a positive integer")
        if self.hidden_size % self.num_heads or self.vocab_size != 259:
            raise ValueError("Invalid head dimensions or byte-tokenizer vocabulary")
        if not math.isfinite(self.layer_norm_eps) or self.layer_norm_eps <= 0:
            raise ValueError("layer_norm_eps must be finite and positive")

    def to_dict(self) -> dict:
        return asdict(self)


class Attention(nn.Module):
    def __init__(self, c: ModelConfig):
        super().__init__()
        self.heads = c.num_heads
        self.q_proj = nn.Linear(c.hidden_size, c.hidden_size, bias=False)
        self.k_proj = nn.Linear(c.hidden_size, c.hidden_size, bias=False)
        self.v_proj = nn.Linear(c.hidden_size, c.hidden_size, bias=False)
        self.out_proj = nn.Linear(c.hidden_size, c.hidden_size, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch, length, width = x.shape

        def split(layer: nn.Linear) -> torch.Tensor:
            return layer(x).view(batch, length, self.heads, width // self.heads).transpose(1, 2)

        q, k, v = split(self.q_proj), split(self.k_proj), split(self.v_proj)
        scores = q @ k.transpose(-2, -1) / math.sqrt(width // self.heads)
        mask = torch.ones(length, length, device=x.device, dtype=torch.bool).triu(1)
        weights = scores.masked_fill(mask, float("-inf")).softmax(dim=-1)
        result = (weights @ v).transpose(1, 2).contiguous().view(batch, length, width)
        return self.out_proj(result)


class FFN(nn.Module):
    def __init__(self, c: ModelConfig):
        super().__init__()
        self.up = nn.Linear(c.hidden_size, c.ffn_size, bias=False)
        self.down = nn.Linear(c.ffn_size, c.hidden_size, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.down(torch.nn.functional.gelu(self.up(x), approximate="none"))


class Block(nn.Module):
    def __init__(self, c: ModelConfig):
        super().__init__()
        self.ln1 = nn.LayerNorm(c.hidden_size, eps=c.layer_norm_eps)
        self.ln2 = nn.LayerNorm(c.hidden_size, eps=c.layer_norm_eps)
        self.attn = Attention(c)
        self.ffn = FFN(c)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.attn(self.ln1(x))
        return x + self.ffn(self.ln2(x))


class LanguageModel(nn.Module):
    def __init__(self, config: ModelConfig):
        super().__init__()
        self.config = config
        if config.kind == "bigram":
            self.token_embedding = nn.Embedding(config.vocab_size, config.vocab_size)
        else:
            self.token_embedding = nn.Embedding(config.vocab_size, config.hidden_size)
            self.position_embedding = nn.Embedding(config.context_length, config.hidden_size)
            self.blocks = nn.ModuleList(Block(config) for _ in range(config.num_layers))
            self.final_norm = nn.LayerNorm(config.hidden_size, eps=config.layer_norm_eps)
            self.lm_head = nn.Linear(config.hidden_size, config.vocab_size, bias=False)

    def forward(self, ids: torch.Tensor) -> torch.Tensor:
        if ids.ndim != 2 or not 0 < ids.shape[1] <= self.config.context_length:
            raise ValueError("Expected [batch, time] with time inside context capacity")
        if self.config.kind == "bigram":
            return self.token_embedding(ids)
        positions = torch.arange(ids.shape[1], device=ids.device)
        x = self.token_embedding(ids) + self.position_embedding(positions)
        for block in self.blocks:
            x = block(x)
        return self.lm_head(self.final_norm(x))
