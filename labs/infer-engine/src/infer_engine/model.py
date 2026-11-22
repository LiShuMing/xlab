"""M2.1 & M2.2: Qwen3-architecture Transformer supporting Concat, Static, and Paged KV Cache.

Implements RMSNorm, Rotary Position Embeddings (RoPE), Grouped-Query Attention (GQA),
and SwiGLU MLP. All four execution paths (no-cache eager, Concat KV, Static KV, and
Paged KV / Continuous Batching) share the exact same weights and RoPE indexing so
greedy token-level parity holds 100%.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import torch
import torch.nn as nn
import torch.nn.functional as F

from infer_engine.paged_kv import PagedKVCache


@dataclass(frozen=True)
class ModelConfig:
    """Transformer architecture hyperparameters."""

    name: str
    vocab_size: int = 1024
    num_layers: int = 12
    hidden_size: int = 1024
    intermediate_size: int = 2816
    num_heads: int = 16
    num_kv_heads: int = 4
    max_seq_len: int = 2048
    rope_theta: float = 10000.0
    rms_norm_eps: float = 1e-6

    @property
    def head_dim(self) -> int:
        return self.hidden_size // self.num_heads


# Preset configs matching real Qwen3-0.6B / 1.7B / 4B hidden dimensions (compact vocab for fast offline tests)
TINY_TEST_CONFIG = ModelConfig(
    name="tiny_test",
    vocab_size=256,
    num_layers=4,
    hidden_size=256,
    intermediate_size=640,
    num_heads=8,
    num_kv_heads=2,
    max_seq_len=512,
)

QWEN_0_6B_CONFIG = ModelConfig(
    name="qwen3_0.6b_arch",
    vocab_size=2048,
    num_layers=24,
    hidden_size=1024,
    intermediate_size=3072,
    num_heads=16,
    num_kv_heads=8,
    max_seq_len=2048,
)

QWEN_4B_CONFIG = ModelConfig(
    name="qwen3_4b_arch",
    vocab_size=2048,
    num_layers=24,
    hidden_size=2560,
    intermediate_size=6912,
    num_heads=20,
    num_kv_heads=4,
    max_seq_len=2048,
)


def precompute_rope_tables(
    max_seq_len: int,
    head_dim: int,
    theta: float,
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Precompute FP32 RoPE cos/sin tables [max_seq_len, head_dim // 2]."""
    inv_freq = 1.0 / (
        theta ** (torch.arange(0, head_dim, 2, device=device, dtype=torch.float32) / head_dim)
    )
    t = torch.arange(max_seq_len, device=device, dtype=torch.float32)
    freqs = torch.outer(t, inv_freq)
    return torch.cos(freqs), torch.sin(freqs)


def apply_rope(
    x: torch.Tensor,
    cos: torch.Tensor,
    sin: torch.Tensor,
) -> torch.Tensor:
    """Apply rotary embedding to x: [..., num_heads, head_dim] with cos/sin [..., 1, head_dim//2]."""
    orig_dtype = x.dtype
    x_f = x.float()
    half = x_f.shape[-1] // 2
    x1 = x_f[..., :half]
    x2 = x_f[..., half:]
    out = torch.cat((x1 * cos - x2 * sin, x2 * cos + x1 * sin), dim=-1)
    return out.to(orig_dtype)


class ConcatKVCache:
    """Naive concat KV cache (mirrors reasoning-lab baseline; reallocates every token)."""

    def __init__(self, num_layers: int) -> None:
        self.k: list[torch.Tensor | None] = [None] * num_layers
        self.v: list[torch.Tensor | None] = [None] * num_layers

    def update(
        self, layer_idx: int, k_new: torch.Tensor, v_new: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        if self.k[layer_idx] is None:
            self.k[layer_idx] = k_new
            self.v[layer_idx] = v_new
        else:
            self.k[layer_idx] = torch.cat([self.k[layer_idx], k_new], dim=2)
            self.v[layer_idx] = torch.cat([self.v[layer_idx], v_new], dim=2)
        return self.k[layer_idx], self.v[layer_idx]


class StaticKVCache:
    """M2.1: Pre-allocated contiguous KV cache avoiding per-step torch.cat reallocations."""

    def __init__(
        self,
        num_layers: int,
        batch_size: int,
        num_kv_heads: int,
        max_seq_len: int,
        head_dim: int,
        device: torch.device | str,
        dtype: torch.dtype,
    ) -> None:
        self.max_seq_len = max_seq_len
        self.seq_len = 0
        self.k = [
            torch.empty(
                (batch_size, num_kv_heads, max_seq_len, head_dim),
                device=device,
                dtype=dtype,
            )
            for _ in range(num_layers)
        ]
        self.v = [
            torch.empty(
                (batch_size, num_kv_heads, max_seq_len, head_dim),
                device=device,
                dtype=dtype,
            )
            for _ in range(num_layers)
        ]

    @property
    def pool_bytes(self) -> int:
        one = self.k[0].numel() * self.k[0].element_size()
        return 2 * len(self.k) * one

    def update(
        self,
        layer_idx: int,
        k_new: torch.Tensor,
        v_new: torch.Tensor,
        start_pos: int,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        end_pos = start_pos + k_new.shape[2]
        self.k[layer_idx][:, :, start_pos:end_pos, :] = k_new
        self.v[layer_idx][:, :, start_pos:end_pos, :] = v_new
        return self.k[layer_idx][:, :, :end_pos, :], self.v[layer_idx][:, :, :end_pos, :]


@dataclass(frozen=True)
class PagedSequenceBatchItem:
    """Metadata for one sequence participating in a flattened continuous-batching step."""

    seq_id: int
    start_token_idx: int  # slice start inside flattened token tensor [total_tokens, H]
    num_new_tokens: int
    past_len: int  # tokens already in KV before this step


class DecoderLayer(nn.Module):
    """Single GQA + RoPE + RMSNorm + SwiGLU decoder layer."""

    def __init__(self, cfg: ModelConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self.num_heads = cfg.num_heads
        self.num_kv_heads = cfg.num_kv_heads
        self.head_dim = cfg.head_dim
        self.kv_repeat = cfg.num_heads // cfg.num_kv_heads

        self.input_norm_w = nn.Parameter(torch.ones(cfg.hidden_size))
        self.q_proj = nn.Linear(cfg.hidden_size, cfg.num_heads * cfg.head_dim, bias=False)
        self.k_proj = nn.Linear(cfg.hidden_size, cfg.num_kv_heads * cfg.head_dim, bias=False)
        self.v_proj = nn.Linear(cfg.hidden_size, cfg.num_kv_heads * cfg.head_dim, bias=False)
        self.o_proj = nn.Linear(cfg.num_heads * cfg.head_dim, cfg.hidden_size, bias=False)

        self.post_norm_w = nn.Parameter(torch.ones(cfg.hidden_size))
        self.gate_proj = nn.Linear(cfg.hidden_size, cfg.intermediate_size, bias=False)
        self.up_proj = nn.Linear(cfg.hidden_size, cfg.intermediate_size, bias=False)
        self.down_proj = nn.Linear(cfg.intermediate_size, cfg.hidden_size, bias=False)

    def _sdpa(
        self,
        q: torch.Tensor,
        k: torch.Tensor,
        v: torch.Tensor,
        past_len: int,
    ) -> torch.Tensor:
        """Exact causal GQA attention for q [B, H, Q, D] and k/v [B, KVH, KV, D]."""
        if self.kv_repeat > 1:
            k = k.repeat_interleave(self.kv_repeat, dim=1)
            v = v.repeat_interleave(self.kv_repeat, dim=1)
        q_len = q.shape[2]
        kv_len = k.shape[2]
        if q_len == 1:
            return F.scaled_dot_product_attention(q, k, v, is_causal=False)
        if past_len == 0 and q_len == kv_len:
            return F.scaled_dot_product_attention(q, k, v, is_causal=True)
        # Chunked prefill or speculative verify: query i at (past_len + i) attends to <= past_len + i.
        q_pos = torch.arange(past_len, past_len + q_len, device=q.device)[:, None]
        k_pos = torch.arange(kv_len, device=q.device)[None, :]
        mask = k_pos <= q_pos
        return F.scaled_dot_product_attention(q, k, v, attn_mask=mask)

    def forward_dense(
        self,
        x: torch.Tensor,
        cos: torch.Tensor,
        sin: torch.Tensor,
        layer_idx: int,
        kv_cache: ConcatKVCache | StaticKVCache | None,
        start_pos: int,
    ) -> torch.Tensor:
        bsz, seq_len, _ = x.shape
        h = F.rms_norm(x, (self.cfg.hidden_size,), self.input_norm_w, self.cfg.rms_norm_eps)
        q = self.q_proj(h).view(bsz, seq_len, self.num_heads, self.head_dim)
        k = self.k_proj(h).view(bsz, seq_len, self.num_kv_heads, self.head_dim)
        v = self.v_proj(h).view(bsz, seq_len, self.num_kv_heads, self.head_dim)

        # cos/sin: [seq_len, head_dim // 2] -> [1, seq_len, 1, head_dim // 2]
        cos_b = cos.unsqueeze(0).unsqueeze(2)
        sin_b = sin.unsqueeze(0).unsqueeze(2)
        q = apply_rope(q, cos_b, sin_b).transpose(1, 2)
        k = apply_rope(k, cos_b, sin_b).transpose(1, 2)
        v = v.transpose(1, 2)

        if isinstance(kv_cache, ConcatKVCache):
            k_all, v_all = kv_cache.update(layer_idx, k, v)
        elif isinstance(kv_cache, StaticKVCache):
            k_all, v_all = kv_cache.update(layer_idx, k, v, start_pos)
        else:
            k_all, v_all = k, v

        attn = self._sdpa(q, k_all, v_all, past_len=start_pos)
        attn = attn.transpose(1, 2).reshape(bsz, seq_len, self.cfg.hidden_size)
        x = x + self.o_proj(attn)

        h2 = F.rms_norm(x, (self.cfg.hidden_size,), self.post_norm_w, self.cfg.rms_norm_eps)
        ffn = self.down_proj(F.silu(self.gate_proj(h2)) * self.up_proj(h2))
        return x + ffn

    def forward_paged(
        self,
        x_flat: torch.Tensor,
        cos: torch.Tensor,
        sin: torch.Tensor,
        layer_idx: int,
        paged_kv: PagedKVCache,
        block_ids: torch.Tensor,
        block_offsets: torch.Tensor,
        batch_items: list[PagedSequenceBatchItem],
    ) -> torch.Tensor:
        """Flattened-token forward pass for Continuous Batching + Chunked Prefill + Paged KV.

        All linear projections (QKV, O, Gate/Up/Down) execute as batched GEMMs over
        `[total_tokens, hidden_size]`, matching vLLM's ragged/flattened batching layout.
        """
        total_tokens = x_flat.shape[0]
        h = F.rms_norm(x_flat, (self.cfg.hidden_size,), self.input_norm_w, self.cfg.rms_norm_eps)
        q = self.q_proj(h).view(total_tokens, self.num_heads, self.head_dim)
        k = self.k_proj(h).view(total_tokens, self.num_kv_heads, self.head_dim)
        v = self.v_proj(h).view(total_tokens, self.num_kv_heads, self.head_dim)

        cos_b = cos.unsqueeze(1)
        sin_b = sin.unsqueeze(1)
        q = apply_rope(q, cos_b, sin_b)
        k = apply_rope(k, cos_b, sin_b)

        paged_kv.write_layer_kv(layer_idx, k, v, block_ids, block_offsets)

        attn_out_flat = torch.empty(
            (total_tokens, self.cfg.hidden_size), device=x_flat.device, dtype=x_flat.dtype
        )
        for item in batch_items:
            s = item.start_token_idx
            e = s + item.num_new_tokens
            # q_seq: [1, num_heads, q_len, head_dim]
            q_seq = q[s:e].transpose(0, 1).unsqueeze(0)
            k_seq, v_seq = paged_kv.gather_sequence_kv(layer_idx, item.seq_id)
            out_seq = self._sdpa(q_seq, k_seq, v_seq, past_len=item.past_len)
            attn_out_flat[s:e] = out_seq.squeeze(0).transpose(0, 1).reshape(
                item.num_new_tokens, self.cfg.hidden_size
            )

        x_flat = x_flat + self.o_proj(attn_out_flat)
        h2 = F.rms_norm(x_flat, (self.cfg.hidden_size,), self.post_norm_w, self.cfg.rms_norm_eps)
        ffn = self.down_proj(F.silu(self.gate_proj(h2)) * self.up_proj(h2))
        return x_flat + ffn


class MiniLLM(nn.Module):
    """Qwen3-architecture decoder model supporting dense (no/concat/static) and paged KV paths."""

    def __init__(self, cfg: ModelConfig, seed: int = 42) -> None:
        super().__init__()
        self.cfg = cfg
        gen = torch.Generator()
        gen.manual_seed(seed)

        self.embed_tokens = nn.Embedding(cfg.vocab_size, cfg.hidden_size)
        self.layers = nn.ModuleList([DecoderLayer(cfg) for _ in range(cfg.num_layers)])
        self.final_norm_w = nn.Parameter(torch.ones(cfg.hidden_size))
        self.lm_head = nn.Linear(cfg.hidden_size, cfg.vocab_size, bias=False)

        # Scaled init so logits have realistic non-saturated variance across 24 layers.
        scale = 1.0 / math.sqrt(cfg.hidden_size)
        with torch.no_grad():
            for name, p in self.named_parameters():
                if name.endswith("_w"):
                    p.fill_(1.0)
                else:
                    p.normal_(mean=0.0, std=scale, generator=gen)

        self._rope_cos: torch.Tensor | None = None
        self._rope_sin: torch.Tensor | None = None

    def _get_rope(self, device: torch.device) -> tuple[torch.Tensor, torch.Tensor]:
        if self._rope_cos is None or self._rope_cos.device != device:
            self._rope_cos, self._rope_sin = precompute_rope_tables(
                self.cfg.max_seq_len, self.cfg.head_dim, self.cfg.rope_theta, device
            )
        return self._rope_cos, self._rope_sin

    def weight_bytes(self) -> int:
        return sum(p.numel() * p.element_size() for p in self.parameters())

    @torch.no_grad()
    def forward_dense(
        self,
        input_ids: torch.Tensor,
        kv_cache: ConcatKVCache | StaticKVCache | None = None,
        start_pos: int = 0,
    ) -> torch.Tensor:
        """Forward pass for [B, S] input_ids with no cache, ConcatKVCache, or StaticKVCache."""
        _, seq_len = input_ids.shape
        x = self.embed_tokens(input_ids)
        cos_all, sin_all = self._get_rope(x.device)
        cos = cos_all[start_pos : start_pos + seq_len]
        sin = sin_all[start_pos : start_pos + seq_len]

        for idx, layer in enumerate(self.layers):
            x = layer.forward_dense(x, cos, sin, idx, kv_cache, start_pos)
        x = F.rms_norm(x, (self.cfg.hidden_size,), self.final_norm_w, self.cfg.rms_norm_eps)
        return self.lm_head(x)

    @torch.no_grad()
    def forward_paged(
        self,
        input_ids_flat: torch.Tensor,
        positions_flat: torch.Tensor,
        paged_kv: PagedKVCache,
        block_ids: torch.Tensor,
        block_offsets: torch.Tensor,
        batch_items: list[PagedSequenceBatchItem],
    ) -> torch.Tensor:
        """Forward pass for flattened continuous-batching step [total_tokens]."""
        x = self.embed_tokens(input_ids_flat)
        cos_all, sin_all = self._get_rope(x.device)
        cos = cos_all.index_select(0, positions_flat)
        sin = sin_all.index_select(0, positions_flat)

        for idx, layer in enumerate(self.layers):
            x = layer.forward_paged(
                x, cos, sin, idx, paged_kv, block_ids, block_offsets, batch_items
            )
        x = F.rms_norm(x, (self.cfg.hidden_size,), self.final_norm_w, self.cfg.rms_norm_eps)
        return self.lm_head(x)
