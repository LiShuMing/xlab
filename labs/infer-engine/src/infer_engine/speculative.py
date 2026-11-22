"""M2.4: Lossless Speculative Decoding (Leviathan et al. 2023) on single GPU.

Uses a small Draft model to propose `gamma` tokens autoregressively, then verifies all
`gamma` tokens in a SINGLE batched forward pass of the Target model.
  - Greedy mode (`temperature == 0`): accepts longest matching prefix + 1 bonus token.
  - Sampling mode (`temperature > 0`): exact rejection sampling with adjusted residual
    distribution `norm(max(0, p_target - p_draft))`, mathematically guaranteed to match
    sampling directly from the Target distribution!
"""

from __future__ import annotations

from dataclasses import dataclass
import time
import torch
import torch.nn.functional as F

from infer_engine.model import MiniLLM, StaticKVCache


@dataclass(frozen=True)
class SpeculativeResult:
    generated_ids: list[int]
    total_draft_tokens: int
    total_accepted_tokens: int
    target_forward_calls: int
    accept_rate: float
    mean_tokens_per_target_step: float
    wall_ms: float


def sample_residual_distribution(
    p_target: torch.Tensor,
    p_draft: torch.Tensor,
    generator: torch.Generator | None = None,
) -> int:
    """Sample from normalized max(0, p_target - p_draft) for lossless rejection sampling."""
    diff = torch.clamp(p_target - p_draft, min=0.0)
    total = diff.sum()
    if total.item() <= 1e-12:
        probs = p_target
    else:
        probs = diff / total
    return int(torch.multinomial(probs, num_samples=1, generator=generator).item())


@torch.no_grad()
def speculative_generate(
    target_model: MiniLLM,
    draft_model: MiniLLM,
    prompt_ids: list[int],
    max_new_tokens: int,
    *,
    gamma: int = 4,
    temperature: float = 0.0,
    seed: int = 42,
) -> SpeculativeResult:
    """Run Speculative Decoding with Static KV caches for both Draft and Target models."""
    device = next(target_model.parameters()).device
    dtype = next(target_model.parameters()).dtype
    max_len = len(prompt_ids) + max_new_tokens + gamma + 4

    target_kv = StaticKVCache(
        target_model.cfg.num_layers,
        1,
        target_model.cfg.num_kv_heads,
        max_len,
        target_model.cfg.head_dim,
        device=device,
        dtype=dtype,
    )
    draft_kv = StaticKVCache(
        draft_model.cfg.num_layers,
        1,
        draft_model.cfg.num_kv_heads,
        max_len,
        draft_model.cfg.head_dim,
        device=device,
        dtype=dtype,
    )

    gen = torch.Generator(device=device)
    gen.manual_seed(seed)

    t0 = time.perf_counter()
    prompt_tensor = torch.tensor([prompt_ids], device=device, dtype=torch.long)

    # Prefill both models on the prompt.
    target_logits = target_model.forward_dense(prompt_tensor, target_kv, start_pos=0)
    _ = draft_model.forward_dense(prompt_tensor, draft_kv, start_pos=0)
    target_pos = len(prompt_ids)
    draft_pos = len(prompt_ids)

    # Emit the first token directly from Target prefill logits.
    if temperature <= 0.0:
        first_tok = int(torch.argmax(target_logits[0, -1]).item())
    else:
        probs = F.softmax(target_logits[0, -1].float() / temperature, dim=-1)
        first_tok = int(torch.multinomial(probs, num_samples=1, generator=gen).item())

    generated: list[int] = [first_tok]
    target_calls = 1
    total_draft = 0
    total_accepted = 0

    while len(generated) < max_new_tokens:
        remaining = max_new_tokens - len(generated)
        k_steps = min(gamma, remaining)

        # 1. Draft proposes k_steps tokens autoregressively starting from last accepted token.
        draft_tokens: list[int] = []
        draft_probs_list: list[torch.Tensor] = []
        cur_tok = generated[-1]
        for _ in range(k_steps):
            inp = torch.tensor([[cur_tok]], device=device, dtype=torch.long)
            d_logits = draft_model.forward_dense(inp, draft_kv, start_pos=draft_pos)[0, -1].float()
            draft_pos += 1
            if temperature <= 0.0:
                next_d = int(torch.argmax(d_logits).item())
                d_prob = F.one_hot(
                    torch.tensor(next_d, device=device), num_classes=d_logits.shape[-1]
                ).float()
            else:
                d_prob = F.softmax(d_logits / temperature, dim=-1)
                next_d = int(torch.multinomial(d_prob, num_samples=1, generator=gen).item())
            draft_tokens.append(next_d)
            draft_probs_list.append(d_prob)
            cur_tok = next_d

        total_draft += k_steps

        # 2. Target verifies `[last_accepted_tok, draft_0, ..., draft_{k-1}]` in ONE batched pass.
        verify_ids = [generated[-1]] + draft_tokens
        verify_tensor = torch.tensor([verify_ids], device=device, dtype=torch.long)
        t_logits_all = target_model.forward_dense(verify_tensor, target_kv, start_pos=target_pos)[
            0
        ].float()
        target_calls += 1

        # 3. Accept / Reject loop (exact Leviathan et al. rule).
        accepted = 0
        bonus_token: int | None = None
        for i in range(k_steps):
            cand = draft_tokens[i]
            t_logits = t_logits_all[i]
            if temperature <= 0.0:
                t_best = int(torch.argmax(t_logits).item())
                if cand == t_best:
                    accepted += 1
                else:
                    bonus_token = t_best
                    break
            else:
                p_t = F.softmax(t_logits / temperature, dim=-1)
                p_d = draft_probs_list[i]
                accept_prob = min(1.0, (p_t[cand] / torch.clamp(p_d[cand], min=1e-12)).item())
                u = float(torch.rand((), device=device, generator=gen).item())
                if u <= accept_prob:
                    accepted += 1
                else:
                    bonus_token = sample_residual_distribution(p_t, p_d, generator=gen)
                    break

        total_accepted += accepted
        generated.extend(draft_tokens[:accepted])

        # If all k_steps draft tokens were accepted, emit 1 bonus token from the (k_steps)-th logit!
        if accepted == k_steps and len(generated) < max_new_tokens:
            last_t_logits = t_logits_all[k_steps]
            if temperature <= 0.0:
                bonus_token = int(torch.argmax(last_t_logits).item())
            else:
                p_last = F.softmax(last_t_logits / temperature, dim=-1)
                bonus_token = int(torch.multinomial(p_last, num_samples=1, generator=gen).item())
            generated.append(bonus_token)
            # Target KV now holds `target_pos + k_steps + 1` tokens (including all k accepted drafts).
            # Draft KV has `draft_pos` up through `draft_{k-2}`; roll back to `target_pos + accepted`
            # so next iteration feeds `generated[-1]` cleanly? Wait: target_pos holds up to `generated[-2]`.
            target_pos += k_steps + 1
            # Feed the final accepted draft token into draft KV so draft_pos catches up to target_pos!
            last_draft_in = torch.tensor([[draft_tokens[-1]]], device=device, dtype=torch.long)
            _ = draft_model.forward_dense(last_draft_in, draft_kv, start_pos=draft_pos)
            draft_pos += 1
        elif bonus_token is not None and len(generated) < max_new_tokens:
            generated.append(bonus_token)
            # Rewind KV logical positions to include `[last_accepted_tok] + accepted_drafts`
            # (= 1 + accepted tokens); `bonus_token` will be fed on the next iteration!
            target_pos += accepted + 1
            draft_pos = target_pos

    if device.type == "cuda":
        torch.cuda.synchronize()
    wall_ms = (time.perf_counter() - t0) * 1000.0
    accept_rate = total_accepted / max(1, total_draft)
    mean_toks = len(generated) / max(1, target_calls)
    return SpeculativeResult(
        generated_ids=generated[:max_new_tokens],
        total_draft_tokens=total_draft,
        total_accepted_tokens=total_accepted,
        target_forward_calls=target_calls,
        accept_rate=accept_rate,
        mean_tokens_per_target_step=mean_toks,
        wall_ms=wall_ms,
    )
