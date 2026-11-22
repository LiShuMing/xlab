"""Unit & parity tests for labs/infer-engine (M2.1 - M2.4).

Verifies:
  1. 100% greedy token-level parity across all 7 execution paths:
     no-cache eager == Concat KV == Static KV == Paged KV == Chunked Prefill
     == Preemption (Recompute & Swap) == Radix Prefix Cache hit.
  2. Strict physical block conservation (`free + used == total`, zero leaks).
  3. Radix Prefix Cache eviction: LFU protects hot system prefixes from scan bursts.
  4. Speculative Decoding: greedy exact parity (both high-accept & low-accept drafts)
     and exact lossless rejection-sampling distribution invariance.
"""

from __future__ import annotations

import unittest
import torch

from infer_engine.model import (
    ConcatKVCache,
    MiniLLM,
    StaticKVCache,
    TINY_TEST_CONFIG,
)
from infer_engine.paged_kv import PagedKVCache
from infer_engine.prefix_cache import RadixPrefixCache
from infer_engine.scheduler import ContinuousBatchingEngine, SequenceRequest
from infer_engine.speculative import sample_residual_distribution, speculative_generate


def greedy_generate_no_cache(
    model: MiniLLM, prompt_ids: list[int], max_new_tokens: int, device: torch.device
) -> list[int]:
    """Ground-truth reference: full recompute from scratch at every token."""
    tokens = list(prompt_ids)
    for _ in range(max_new_tokens):
        inp = torch.tensor([tokens], device=device, dtype=torch.long)
        logits = model.forward_dense(inp, kv_cache=None, start_pos=0)
        tokens.append(int(torch.argmax(logits[0, -1]).item()))
    return tokens[len(prompt_ids) :]


def greedy_generate_dense_kv(
    model: MiniLLM,
    prompt_ids: list[int],
    max_new_tokens: int,
    device: torch.device,
    cache_kind: str,
) -> list[int]:
    if cache_kind == "concat":
        kv = ConcatKVCache(model.cfg.num_layers)
    else:
        kv = StaticKVCache(
            model.cfg.num_layers,
            1,
            model.cfg.num_kv_heads,
            len(prompt_ids) + max_new_tokens + 2,
            model.cfg.head_dim,
            device=device,
            dtype=next(model.parameters()).dtype,
        )
    inp = torch.tensor([prompt_ids], device=device, dtype=torch.long)
    logits = model.forward_dense(inp, kv_cache=kv, start_pos=0)
    generated = [int(torch.argmax(logits[0, -1]).item())]
    pos = len(prompt_ids)
    for _ in range(max_new_tokens - 1):
        step_in = torch.tensor([[generated[-1]]], device=device, dtype=torch.long)
        logits = model.forward_dense(step_in, kv_cache=kv, start_pos=pos)
        pos += 1
        generated.append(int(torch.argmax(logits[0, -1]).item()))
    return generated


class InferEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        # Use FP32 for exact deterministic parity tests without BF16 rounding ambiguity.
        cls.model = MiniLLM(TINY_TEST_CONFIG, seed=7).to(device=cls.device, dtype=torch.float32).eval()
        cls.prompts = [
            [1, 5, 9, 13, 17, 21, 25, 29, 33, 37, 41, 45, 49, 53, 57, 61, 65, 69, 73],
            [1, 5, 9, 13, 17, 21, 25, 29, 33, 37, 41, 45, 49, 53, 57, 61, 90, 91, 92, 93, 94],
            [4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44],
        ]
        cls.max_new = 12
        cls.refs = [
            greedy_generate_no_cache(cls.model, p, cls.max_new, cls.device) for p in cls.prompts
        ]

    def test_m21_concat_and_static_kv_parity(self) -> None:
        for p, ref in zip(self.prompts, self.refs):
            self.assertEqual(
                greedy_generate_dense_kv(self.model, p, self.max_new, self.device, "concat"), ref
            )
            self.assertEqual(
                greedy_generate_dense_kv(self.model, p, self.max_new, self.device, "static"), ref
            )

    def test_m22_m23_paged_continuous_and_chunked_prefill_parity(self) -> None:
        for budget in (256, 17):  # 256 = full prefill; 17 = non-aligned chunked prefill
            kv = PagedKVCache(
                TINY_TEST_CONFIG.num_layers,
                num_blocks=64,
                num_kv_heads=TINY_TEST_CONFIG.num_kv_heads,
                block_size=8,
                head_dim=TINY_TEST_CONFIG.head_dim,
                device=self.device,
                dtype=torch.float32,
            )
            engine = ContinuousBatchingEngine(
                self.model, kv, max_num_batched_tokens=budget, max_running_seqs=8
            )
            for sid, p in enumerate(self.prompts):
                engine.add_request(SequenceRequest(seq_id=sid, prompt_ids=p, max_new_tokens=self.max_new))

            while engine.waiting or engine.running or engine.swapped:
                engine.step()
                kv.manager.check_invariants()

            by_id = {r.seq_id: r.generated_ids for r in engine.finished}
            for sid, ref in enumerate(self.refs):
                self.assertEqual(by_id[sid], ref, f"Mismatch for budget={budget}, seq_id={sid}")
            self.assertEqual(kv.manager.num_free_blocks, kv.num_blocks)

    def test_m23_preemption_recompute_and_swap_parity(self) -> None:
        # Tight pool (8 blocks * 8 tokens = 64 token slots) for 3 sequences totaling ~90 tokens
        # forces real preemptions while still allowing any single sequence to complete.
        for mode in ("recompute", "swap"):
            kv = PagedKVCache(
                TINY_TEST_CONFIG.num_layers,
                num_blocks=8,
                num_kv_heads=TINY_TEST_CONFIG.num_kv_heads,
                block_size=8,
                head_dim=TINY_TEST_CONFIG.head_dim,
                device=self.device,
                dtype=torch.float32,
            )
            engine = ContinuousBatchingEngine(
                self.model,
                kv,
                max_num_batched_tokens=64,
                max_running_seqs=3,
                preemption_mode=mode,
            )
            for sid, p in enumerate(self.prompts):
                engine.add_request(SequenceRequest(seq_id=sid, prompt_ids=p, max_new_tokens=self.max_new))

            while engine.waiting or engine.running or engine.swapped:
                engine.step()
                kv.manager.check_invariants()

            self.assertGreater(engine.total_preemptions, 0, f"Expected preemptions in mode={mode}")
            by_id = {r.seq_id: r.generated_ids for r in engine.finished}
            for sid, ref in enumerate(self.refs):
                self.assertEqual(by_id[sid], ref, f"Preemption parity failed in mode={mode}")
            self.assertEqual(kv.manager.num_free_blocks, kv.num_blocks)

    def test_m24_prefix_cache_parity_and_lfu_vs_lru_eviction(self) -> None:
        # 1. Parity on shared-prefix prompts (prompts[0] and prompts[1] share first 16 tokens = 2 blocks).
        kv = PagedKVCache(
            TINY_TEST_CONFIG.num_layers,
            num_blocks=32,
            num_kv_heads=TINY_TEST_CONFIG.num_kv_heads,
            block_size=8,
            head_dim=TINY_TEST_CONFIG.head_dim,
            device=self.device,
            dtype=torch.float32,
        )
        pc = RadixPrefixCache(kv.manager, eviction_policy="lru")
        engine = ContinuousBatchingEngine(self.model, kv, max_num_batched_tokens=64, prefix_cache=pc)

        # Run prompt 0 first so its prefix blocks enter the radix tree, then prompt 1 hits them.
        engine.add_request(SequenceRequest(seq_id=0, prompt_ids=self.prompts[0], max_new_tokens=self.max_new))
        engine.run_until_complete()
        engine.add_request(SequenceRequest(seq_id=1, prompt_ids=self.prompts[1], max_new_tokens=self.max_new))
        engine.run_until_complete()

        by_id = {r.seq_id: r for r in engine.finished}
        self.assertEqual(by_id[0].generated_ids, self.refs[0])
        self.assertEqual(by_id[1].generated_ids, self.refs[1])
        self.assertEqual(by_id[1].prefix_hit_tokens, 16)
        pc.clear()
        kv.manager.check_invariants()
        self.assertEqual(kv.manager.num_free_blocks, kv.num_blocks)

        # 2. Eviction policy comparison: hot system prefix + scan burst of one-hit prompts.
        # Pool has only 4 blocks; hot prefix uses 2 blocks; 3 unique one-hit prompts each insert 2 blocks.
        hot_prefix = list(range(1, 17))  # 2 blocks of 8
        hit_counts: dict[str, int] = {}
        for policy in ("lru", "lfu"):
            kv_p = PagedKVCache(1, num_blocks=4, num_kv_heads=1, block_size=8, head_dim=8, device="cpu", dtype=torch.float32)
            tree = RadixPrefixCache(kv_p.manager, eviction_policy=policy)

            # Warm hot prefix 4 times so LFU records high frequency.
            b0, b1 = kv_p.manager.alloc_block(), kv_p.manager.alloc_block()
            tree.insert_sequence_blocks(hot_prefix, [b0, b1])
            kv_p.manager.dec_ref(b0)
            kv_p.manager.dec_ref(b1)
            for _ in range(3):
                matched, _ = tree.match_prefix(hot_prefix + [99])
                self.assertEqual(len(matched), 2)

            # Inject 2 one-hit scan blocks forcing eviction of 2 blocks.
            for scan_id in range(2):
                if kv_p.manager.num_free_blocks < 2:
                    tree.evict(2 - kv_p.manager.num_free_blocks)
                sb0, sb1 = kv_p.manager.alloc_block(), kv_p.manager.alloc_block()
                scan_toks = [100 + scan_id * 20 + i for i in range(16)]
                tree.insert_sequence_blocks(scan_toks, [sb0, sb1])
                kv_p.manager.dec_ref(sb0)
                kv_p.manager.dec_ref(sb1)

            matched_after, _ = tree.match_prefix(hot_prefix + [99])
            hit_counts[policy] = len(matched_after)
            tree.clear()
            kv_p.manager.check_invariants()

        # LFU retains the hot prefix; pure LRU gets polluted by the scan burst.
        self.assertEqual(hit_counts["lru"], 0)
        self.assertEqual(hit_counts["lfu"], 2)

    def test_m24_speculative_decoding_greedy_parity_and_lossless_sampling(self) -> None:
        # 1. Greedy parity with identical draft (100% accept) AND mismatched draft (low accept).
        mismatched_draft = MiniLLM(TINY_TEST_CONFIG, seed=99).to(
            device=self.device, dtype=torch.float32
        ).eval()

        res_same = speculative_generate(
            self.model, self.model, self.prompts[0], self.max_new, gamma=4, temperature=0.0
        )
        self.assertEqual(res_same.generated_ids, self.refs[0])
        self.assertAlmostEqual(res_same.accept_rate, 1.0, places=5)

        res_diff = speculative_generate(
            self.model, mismatched_draft, self.prompts[0], self.max_new, gamma=4, temperature=0.0
        )
        self.assertEqual(res_diff.generated_ids, self.refs[0])

        # 2. Lossless rejection sampling distribution invariance (empirical check over 12,000 draws).
        p_t = torch.tensor([0.10, 0.25, 0.45, 0.20], dtype=torch.float32)
        p_d = torch.tensor([0.40, 0.30, 0.15, 0.15], dtype=torch.float32)
        gen = torch.Generator().manual_seed(2026)
        counts = torch.zeros(4, dtype=torch.float32)
        trials = 12000
        for _ in range(trials):
            cand = int(torch.multinomial(p_d, 1, generator=gen).item())
            accept_p = min(1.0, (p_t[cand] / p_d[cand]).item())
            if float(torch.rand((), generator=gen).item()) <= accept_p:
                out = cand
            else:
                out = sample_residual_distribution(p_t, p_d, generator=gen)
            counts[out] += 1.0
        emp = counts / trials
        max_tv = (emp - p_t).abs().max().item()
        self.assertLess(max_tv, 0.02, f"Rejection sampling distribution drifted: {emp} vs {p_t}")


if __name__ == "__main__":
    unittest.main()
