"""M2.3: Continuous Batching, Chunked Prefill, and Preemption (Recompute vs CPU Swap) Scheduler.

Models a vLLM-style iteration-level serving loop:
  - Queues: Waiting -> Running <-> Swapped -> Finished
  - Token budget (`max_num_batched_tokens`): limits total tokens per iteration so a long
    prefill is chunked across steps instead of causing head-of-line P99 ITL spikes for
    in-flight decode requests.
  - Preemption when GPU KV blocks run out: evicts newest running request via either
    `recompute` (free GPU KV blocks, re-queue into Waiting) or `swap` (copy KV blocks
    to CPU host memory, re-queue into Swapped and swap back in when blocks free up).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import time
import torch

from infer_engine.model import MiniLLM, PagedSequenceBatchItem
from infer_engine.paged_kv import PagedKVCache, SwapRecord
from infer_engine.prefix_cache import RadixPrefixCache


@dataclass
class SequenceRequest:
    """State of one inference request flowing through the continuous-batching engine."""

    seq_id: int
    prompt_ids: list[int]
    max_new_tokens: int
    arrival_step: int = 0
    generated_ids: list[int] = field(default_factory=list)
    # Number of tokens (prompt + generated) whose KV has already been computed & stored
    num_computed_tokens: int = 0
    # Timing metrics recorded in wall-clock ms
    arrival_time_s: float = 0.0
    first_token_time_s: float = 0.0
    finish_time_s: float = 0.0
    itl_ms: list[float] = field(default_factory=list)
    last_token_time_s: float = 0.0
    preempt_count: int = 0
    prefix_hit_tokens: int = 0

    @property
    def all_tokens(self) -> list[int]:
        return self.prompt_ids + self.generated_ids

    @property
    def total_len(self) -> int:
        return len(self.prompt_ids) + len(self.generated_ids)

    @property
    def is_prefill_done(self) -> bool:
        return self.num_computed_tokens >= len(self.prompt_ids)

    @property
    def is_finished(self) -> bool:
        return len(self.generated_ids) >= self.max_new_tokens


class ContinuousBatchingEngine:
    """Single-GPU mini-vLLM engine with Paged KV, Chunked Prefill, Preemption & Prefix Cache."""

    def __init__(
        self,
        model: MiniLLM,
        paged_kv: PagedKVCache,
        *,
        max_num_batched_tokens: int = 256,
        max_running_seqs: int = 32,
        preemption_mode: str = "recompute",
        prefix_cache: RadixPrefixCache | None = None,
    ) -> None:
        if preemption_mode not in ("recompute", "swap"):
            raise ValueError(f"Unsupported preemption_mode: {preemption_mode}")
        self.model = model
        self.paged_kv = paged_kv
        self.manager = paged_kv.manager
        self.max_num_batched_tokens = max_num_batched_tokens
        self.max_running_seqs = max_running_seqs
        self.preemption_mode = preemption_mode
        self.prefix_cache = prefix_cache

        self.waiting: deque[SequenceRequest] = deque()
        self.running: list[SequenceRequest] = []
        self.swapped: deque[tuple[SequenceRequest, SwapRecord]] = deque()
        self.finished: list[SequenceRequest] = []

        self.step_count = 0
        self.total_preemptions = 0
        self.total_swap_out_ms = 0.0
        self.total_swap_in_ms = 0.0
        self.total_recomputed_tokens = 0
        self.step_latencies_ms: list[float] = []

    def add_request(self, req: SequenceRequest) -> None:
        req.arrival_time_s = time.perf_counter()
        self.waiting.append(req)

    def _ensure_free_blocks(self, needed: int) -> bool:
        """Try to secure `needed` free GPU blocks, evicting unpinned prefix cache first."""
        if self.manager.num_free_blocks >= needed:
            return True
        if self.prefix_cache is not None:
            deficit = needed - self.manager.num_free_blocks
            self.prefix_cache.evict(deficit)
        return self.manager.num_free_blocks >= needed

    def _preempt_one(self, victim: SequenceRequest) -> None:
        """Preempt a running sequence via Recompute or CPU Swap."""
        victim.preempt_count += 1
        self.total_preemptions += 1
        if self.preemption_mode == "swap":
            t0 = time.perf_counter()
            rec = self.paged_kv.swap_out_sequence(victim.seq_id)
            if self.paged_kv.device.type == "cuda":
                torch.cuda.synchronize()
            self.total_swap_out_ms += (time.perf_counter() - t0) * 1000.0
            self.swapped.appendleft((victim, rec))
        else:
            self.total_recomputed_tokens += victim.num_computed_tokens
            self.manager.free_sequence(victim.seq_id)
            victim.num_computed_tokens = 0
            self.waiting.appendleft(victim)

    @torch.no_grad()
    def step(self) -> int:
        """Execute one continuous-batching iteration. Returns total tokens processed."""
        self.step_count += 1
        token_budget = self.max_num_batched_tokens
        reserved_blocks = 0
        scheduled: list[tuple[SequenceRequest, list[int], int]] = []  # (req, new_tokens, past_len)

        # 1. Schedule already-running sequences first (decode or continuing chunked prefill).
        i = 0
        while i < len(self.running) and token_budget > 0:
            req = self.running[i]
            all_toks = req.all_tokens
            remaining = len(all_toks) - req.num_computed_tokens
            assert remaining > 0
            chunk_len = min(remaining, token_budget)

            needed_blocks = self.manager.blocks_needed_for_append(req.seq_id, chunk_len)
            while not self._ensure_free_blocks(reserved_blocks + needed_blocks):
                # Preempt the newest running request (LIFO victim) to guarantee forward progress.
                if len(self.running) <= 1:
                    raise MemoryError(
                        f"Single sequence seq_id={req.seq_id} exceeds entire KV block pool!"
                    )
                victim = self.running.pop()
                # If victim was already scheduled earlier in this step, remove it & release its reservation.
                if any(s_req.seq_id == victim.seq_id for s_req, _, _ in scheduled):
                    new_sched = []
                    for s_req, s_toks, s_past in scheduled:
                        if s_req.seq_id == victim.seq_id:
                            reserved_blocks -= self.manager.blocks_needed_for_append(
                                s_req.seq_id, len(s_toks)
                            )
                            token_budget += len(s_toks)
                        else:
                            new_sched.append((s_req, s_toks, s_past))
                    scheduled = new_sched
                self._preempt_one(victim)
                if i >= len(self.running):
                    break
            if i >= len(self.running):
                break

            past_len = req.num_computed_tokens
            new_tokens = all_toks[past_len : past_len + chunk_len]
            scheduled.append((req, new_tokens, past_len))
            reserved_blocks += needed_blocks
            token_budget -= chunk_len
            i += 1

        # 2. Swap back in preempted sequences if blocks and slots allow (priority over new waiting).
        while self.swapped and len(self.running) < self.max_running_seqs and token_budget > 0:
            req, rec = self.swapped[0]
            blocks_for_swap = len(rec.layers_kv[0][0])
            all_toks = req.all_tokens
            remaining = len(all_toks) - req.num_computed_tokens
            chunk_len = min(remaining, token_budget)
            cur_cap_tokens = blocks_for_swap * self.manager.block_size
            extra_blocks = max(
                0,
                (req.num_computed_tokens + chunk_len - cur_cap_tokens + self.manager.block_size - 1)
                // self.manager.block_size,
            )
            if not self._ensure_free_blocks(reserved_blocks + blocks_for_swap + extra_blocks):
                break
            self.swapped.popleft()
            t0 = time.perf_counter()
            self.paged_kv.swap_in_sequence(req.seq_id, rec)
            if self.paged_kv.device.type == "cuda":
                torch.cuda.synchronize()
            self.total_swap_in_ms += (time.perf_counter() - t0) * 1000.0
            self.running.append(req)
            past_len = req.num_computed_tokens
            new_tokens = all_toks[past_len : past_len + chunk_len]
            scheduled.append((req, new_tokens, past_len))
            reserved_blocks += extra_blocks
            token_budget -= chunk_len

        # 3. Admit waiting requests (with optional Radix Prefix Cache lookup).
        while self.waiting and len(self.running) < self.max_running_seqs and token_budget > 0:
            req = self.waiting[0]
            all_toks = req.all_tokens

            matched_blocks: list[int] = []
            matched_len = 0
            if self.prefix_cache is not None and req.num_computed_tokens == 0:
                matched_blocks, matched_len = self.prefix_cache.match_prefix(all_toks)

            remaining = len(all_toks) - matched_len
            chunk_len = min(remaining, token_budget)
            needed_blocks = (chunk_len + self.manager.block_size - 1) // self.manager.block_size
            if not self._ensure_free_blocks(reserved_blocks + needed_blocks):
                break

            self.waiting.popleft()
            if matched_blocks:
                self.manager.attach_prefix_blocks(req.seq_id, matched_blocks, matched_len)
                req.num_computed_tokens = matched_len
                req.prefix_hit_tokens = matched_len

            self.running.append(req)
            past_len = req.num_computed_tokens
            new_tokens = all_toks[past_len : past_len + chunk_len]
            scheduled.append((req, new_tokens, past_len))
            reserved_blocks += needed_blocks
            token_budget -= chunk_len

        if not scheduled:
            return 0

        # 4. Build flattened token batch & allocate physical KV slots.
        flat_input_ids: list[int] = []
        flat_positions: list[int] = []
        flat_block_ids: list[int] = []
        flat_block_offsets: list[int] = []
        batch_items: list[PagedSequenceBatchItem] = []

        cursor = 0
        for req, new_tokens, past_len in scheduled:
            slots = self.manager.allocate_slots(req.seq_id, len(new_tokens))
            flat_input_ids.extend(new_tokens)
            flat_positions.extend(range(past_len, past_len + len(new_tokens)))
            for bid, off in slots:
                flat_block_ids.append(bid)
                flat_block_offsets.append(off)
            batch_items.append(
                PagedSequenceBatchItem(
                    seq_id=req.seq_id,
                    start_token_idx=cursor,
                    num_new_tokens=len(new_tokens),
                    past_len=past_len,
                )
            )
            cursor += len(new_tokens)

        device = self.paged_kv.device
        t_step0 = time.perf_counter()
        logits = self.model.forward_paged(
            input_ids_flat=torch.tensor(flat_input_ids, device=device, dtype=torch.long),
            positions_flat=torch.tensor(flat_positions, device=device, dtype=torch.long),
            paged_kv=self.paged_kv,
            block_ids=torch.tensor(flat_block_ids, device=device, dtype=torch.long),
            block_offsets=torch.tensor(flat_block_offsets, device=device, dtype=torch.long),
            batch_items=batch_items,
        )
        # Extract last-token logits for every sequence that finished its prompt/step.
        next_tokens_gpu = torch.argmax(
            logits[[item.start_token_idx + item.num_new_tokens - 1 for item in batch_items]],
            dim=-1,
        )
        next_tokens = next_tokens_gpu.tolist()
        if device.type == "cuda":
            torch.cuda.synchronize()
        now_s = time.perf_counter()
        self.step_latencies_ms.append((now_s - t_step0) * 1000.0)

        # 5. Advance sequence states, insert full prefix blocks, and release finished requests.
        still_running: list[SequenceRequest] = []
        scheduled_ids = {req.seq_id for req, _, _ in scheduled}
        for (req, new_tokens, _), next_tok in zip(scheduled, next_tokens):
            req.num_computed_tokens += len(new_tokens)
            # Only emit a generated token once the full prompt has been prefilled!
            if req.num_computed_tokens >= len(req.prompt_ids):
                req.generated_ids.append(int(next_tok))
                if len(req.generated_ids) == 1:
                    req.first_token_time_s = now_s
                    req.last_token_time_s = now_s
                else:
                    req.itl_ms.append((now_s - req.last_token_time_s) * 1000.0)
                    req.last_token_time_s = now_s

                if req.is_finished:
                    req.finish_time_s = now_s
                    if self.prefix_cache is not None:
                        self.prefix_cache.insert_sequence_blocks(
                            req.prompt_ids, self.manager.page_tables[req.seq_id]
                        )
                    self.manager.free_sequence(req.seq_id)
                    self.finished.append(req)
                else:
                    still_running.append(req)
            else:
                still_running.append(req)

        # Keep any running requests that were not scheduled this step due to token budget.
        for req in self.running:
            if req.seq_id not in scheduled_ids:
                still_running.append(req)
        self.running = still_running
        return cursor

    def run_until_complete(self) -> list[SequenceRequest]:
        """Drain all waiting, running, and swapped requests until finished."""
        while self.waiting or self.running or self.swapped:
            self.step()
        return self.finished
