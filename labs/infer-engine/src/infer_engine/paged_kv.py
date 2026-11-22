"""M2.2: BlockManager and PagedKVCache (OS virtual-memory paging for LLM KV cache).

Maintains strict conservation invariants:
  - len(free_blocks) + len(allocated_blocks) == num_blocks (where allocated = refcount > 0)
  - Supports Copy-on-Write (COW) / shared prefix blocks via reference counts
  - Supports CPU Swap-Out / Swap-In (CUDA <-> pinned/host RAM) for preemption benchmarks
"""

from __future__ import annotations

from dataclasses import dataclass, field
import torch


@dataclass
class SwapRecord:
    """Stores host-side swapped blocks for a preempted sequence."""

    num_tokens: int
    # Per-layer tuple of (k_cpu, v_cpu) each shaped [num_seq_blocks, num_kv_heads, block_size, head_dim]
    layers_kv: list[tuple[torch.Tensor, torch.Tensor]] = field(default_factory=list)


class BlockManager:
    """Manages fixed-size physical KV cache blocks, per-sequence page tables, and refcounts."""

    def __init__(self, num_blocks: int, block_size: int) -> None:
        if num_blocks <= 0 or block_size <= 0:
            raise ValueError("num_blocks and block_size must be positive.")
        self.num_blocks = num_blocks
        self.block_size = block_size
        self.free_blocks: list[int] = list(range(num_blocks - 1, -1, -1))
        self.refcounts: list[int] = [0] * num_blocks
        # seq_id -> list of physical block IDs in logical page order
        self.page_tables: dict[int, list[int]] = {}
        # seq_id -> current number of logical tokens stored in KV
        self.seq_lens: dict[int, int] = {}

    @property
    def num_free_blocks(self) -> int:
        return len(self.free_blocks)

    @property
    def num_used_blocks(self) -> int:
        return self.num_blocks - len(self.free_blocks)

    def check_invariants(self) -> None:
        """Assert strict physical block conservation and refcount sanity."""
        free_set = set(self.free_blocks)
        assert len(free_set) == len(self.free_blocks), "Duplicate block ID in free_blocks!"
        used_count = 0
        for bid, rc in enumerate(self.refcounts):
            assert rc >= 0, f"Negative refcount {rc} on block {bid}"
            if rc == 0:
                assert bid in free_set, f"Zero-refcount block {bid} leaked (not in free_blocks)!"
            else:
                assert bid not in free_set, f"Active block {bid} (rc={rc}) also in free_blocks!"
                used_count += 1
        assert used_count + len(self.free_blocks) == self.num_blocks, (
            f"Block conservation violated: used={used_count}, free={len(self.free_blocks)}, "
            f"total={self.num_blocks}"
        )

    def alloc_block(self) -> int:
        """Allocate a single fresh physical block with refcount=1."""
        if not self.free_blocks:
            raise MemoryError("KV cache out of physical blocks.")
        bid = self.free_blocks.pop()
        assert self.refcounts[bid] == 0
        self.refcounts[bid] = 1
        return bid

    def inc_ref(self, bid: int) -> None:
        """Increment reference count of an already-allocated physical block (prefix/COW sharing)."""
        assert self.refcounts[bid] > 0, f"Cannot inc_ref unallocated block {bid}"
        self.refcounts[bid] += 1

    def dec_ref(self, bid: int) -> bool:
        """Decrement reference count; returns block to free pool if refcount reaches 0."""
        assert self.refcounts[bid] > 0, f"Double-free on block {bid}"
        self.refcounts[bid] -= 1
        if self.refcounts[bid] == 0:
            self.free_blocks.append(bid)
            return True
        return False

    def blocks_needed_for_append(self, seq_id: int, num_new_tokens: int) -> int:
        """Return how many additional physical blocks are needed to append `num_new_tokens`."""
        cur_len = self.seq_lens.get(seq_id, 0)
        cur_blocks = len(self.page_tables.get(seq_id, []))
        target_blocks = (cur_len + num_new_tokens + self.block_size - 1) // self.block_size
        return max(0, target_blocks - cur_blocks)

    def can_append(self, seq_id: int, num_new_tokens: int) -> bool:
        return self.blocks_needed_for_append(seq_id, num_new_tokens) <= self.num_free_blocks

    def attach_prefix_blocks(self, seq_id: int, shared_blocks: list[int], prefix_len: int) -> None:
        """Attach existing cached prefix blocks to a new sequence (increments refcounts)."""
        assert seq_id not in self.page_tables
        assert prefix_len == len(shared_blocks) * self.block_size
        for bid in shared_blocks:
            self.inc_ref(bid)
        self.page_tables[seq_id] = list(shared_blocks)
        self.seq_lens[seq_id] = prefix_len

    def allocate_slots(self, seq_id: int, num_new_tokens: int) -> list[tuple[int, int]]:
        """Allocate physical (block_id, offset) slots for `num_new_tokens` appended to `seq_id`.

        Handles Copy-on-Write if the tail block is shared (refcount > 1) and partially filled.
        """
        if seq_id not in self.page_tables:
            self.page_tables[seq_id] = []
            self.seq_lens[seq_id] = 0

        cur_len = self.seq_lens[seq_id]
        table = self.page_tables[seq_id]
        slots: list[tuple[int, int]] = []

        for i in range(num_new_tokens):
            pos = cur_len + i
            logical_blk = pos // self.block_size
            offset = pos % self.block_size
            if logical_blk >= len(table):
                table.append(self.alloc_block())
            else:
                # Copy-on-write safety: if tail block is somehow shared, never mutate in place.
                bid = table[logical_blk]
                if self.refcounts[bid] > 1:
                    raise RuntimeError(
                        f"Attempted to write into shared block {bid} (rc={self.refcounts[bid]})"
                    )
            slots.append((table[logical_blk], offset))

        self.seq_lens[seq_id] = cur_len + num_new_tokens
        return slots

    def free_sequence(self, seq_id: int) -> None:
        """Release all physical blocks referenced by `seq_id`."""
        table = self.page_tables.pop(seq_id, [])
        self.seq_lens.pop(seq_id, None)
        for bid in table:
            self.dec_ref(bid)

    def internal_fragmentation_ratio(self) -> float:
        """Compute wasted slot fraction inside allocated per-sequence blocks."""
        total_slots = 0
        used_slots = 0
        for seq_id, table in self.page_tables.items():
            total_slots += len(table) * self.block_size
            used_slots += self.seq_lens[seq_id]
        if total_slots == 0:
            return 0.0
        return (total_slots - used_slots) / total_slots


class PagedKVCache:
    """Physical GPU block pool paired with a BlockManager."""

    def __init__(
        self,
        num_layers: int,
        num_blocks: int,
        num_kv_heads: int,
        block_size: int,
        head_dim: int,
        device: torch.device | str = "cuda",
        dtype: torch.dtype = torch.bfloat16,
    ) -> None:
        self.num_layers = num_layers
        self.num_blocks = num_blocks
        self.num_kv_heads = num_kv_heads
        self.block_size = block_size
        self.head_dim = head_dim
        self.device = torch.device(device)
        self.dtype = dtype

        self.manager = BlockManager(num_blocks=num_blocks, block_size=block_size)
        # Physical pool per layer: [num_blocks, num_kv_heads, block_size, head_dim]
        self.k_pools = [
            torch.empty(
                (num_blocks, num_kv_heads, block_size, head_dim),
                device=self.device,
                dtype=dtype,
            )
            for _ in range(num_layers)
        ]
        self.v_pools = [
            torch.empty(
                (num_blocks, num_kv_heads, block_size, head_dim),
                device=self.device,
                dtype=dtype,
            )
            for _ in range(num_layers)
        ]

    @property
    def pool_bytes(self) -> int:
        one = self.k_pools[0].numel() * self.k_pools[0].element_size()
        return 2 * self.num_layers * one

    def write_layer_kv(
        self,
        layer_idx: int,
        k_new: torch.Tensor,
        v_new: torch.Tensor,
        block_ids: torch.Tensor,
        block_offsets: torch.Tensor,
    ) -> None:
        """Scatter new K/V tokens [total_tokens, num_kv_heads, head_dim] into physical blocks."""
        self.k_pools[layer_idx][block_ids, :, block_offsets, :] = k_new
        self.v_pools[layer_idx][block_ids, :, block_offsets, :] = v_new

    def gather_sequence_kv(
        self,
        layer_idx: int,
        seq_id: int,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Gather ordered K/V [1, num_kv_heads, seq_len, head_dim] for a single sequence."""
        table = self.manager.page_tables[seq_id]
        seq_len = self.manager.seq_lens[seq_id]
        idx = torch.tensor(table, device=self.device, dtype=torch.long)
        # [num_seq_blocks, num_kv_heads, block_size, head_dim] -> [1, num_kv_heads, cap, head_dim]
        k = (
            self.k_pools[layer_idx]
            .index_select(0, idx)
            .permute(1, 0, 2, 3)
            .reshape(1, self.num_kv_heads, len(table) * self.block_size, self.head_dim)
        )
        v = (
            self.v_pools[layer_idx]
            .index_select(0, idx)
            .permute(1, 0, 2, 3)
            .reshape(1, self.num_kv_heads, len(table) * self.block_size, self.head_dim)
        )
        return k[:, :, :seq_len, :], v[:, :, :seq_len, :]

    def swap_out_sequence(self, seq_id: int) -> SwapRecord:
        """Copy all KV blocks of `seq_id` from GPU to CPU host memory and free GPU blocks."""
        table = self.manager.page_tables[seq_id]
        seq_len = self.manager.seq_lens[seq_id]
        idx = torch.tensor(table, device=self.device, dtype=torch.long)
        rec = SwapRecord(num_tokens=seq_len)
        for layer_idx in range(self.num_layers):
            k_cpu = self.k_pools[layer_idx].index_select(0, idx).to("cpu", non_blocking=False)
            v_cpu = self.v_pools[layer_idx].index_select(0, idx).to("cpu", non_blocking=False)
            rec.layers_kv.append((k_cpu, v_cpu))
        self.manager.free_sequence(seq_id)
        return rec

    def swap_in_sequence(self, seq_id: int, rec: SwapRecord) -> None:
        """Re-allocate GPU blocks for `seq_id` and copy KV blocks back from CPU host memory."""
        num_seq_blocks = len(rec.layers_kv[0][0])
        if num_seq_blocks > self.manager.num_free_blocks:
            raise MemoryError("Not enough free GPU blocks to swap sequence back in.")
        new_blocks = [self.manager.alloc_block() for _ in range(num_seq_blocks)]
        idx = torch.tensor(new_blocks, device=self.device, dtype=torch.long)
        for layer_idx, (k_cpu, v_cpu) in enumerate(rec.layers_kv):
            self.k_pools[layer_idx].index_copy_(0, idx, k_cpu.to(self.device))
            self.v_pools[layer_idx].index_copy_(0, idx, v_cpu.to(self.device))
        self.manager.page_tables[seq_id] = new_blocks
        self.manager.seq_lens[seq_id] = rec.num_tokens
