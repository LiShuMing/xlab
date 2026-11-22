"""M2.4: Block-aligned Radix Tree Prefix Cache with pluggable eviction (LRU vs LFU-Freq).

Caches full physical KV blocks keyed by token-block tuples along a prefix tree:
  - While cached, the RadixTree holds 1 extra refcount on every cached physical block.
  - Active sequences using a cached block also hold their own refcount (rc >= 2), making
    active blocks PINNED (non-evictable).
  - Only leaf nodes with refcount == 1 (held solely by the prefix cache) are evictable
    candidates when the BlockManager runs low on free blocks!
  - Directly transfers the cache eviction methodology from `labs/cache/`: compares pure
    LRU vs frequency-aware LFU under shared-prompt + one-hit scan workloads.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from infer_engine.paged_kv import BlockManager


@dataclass
class RadixNode:
    """One full block_size chunk of tokens mapped to a physical KV block."""

    block_tokens: tuple[int, ...]
    block_id: int
    parent: RadixNode | None = None
    children: dict[tuple[int, ...], RadixNode] = field(default_factory=dict)
    last_access_step: int = 0
    hit_count: int = 1


class RadixPrefixCache:
    """Radix tree indexing full KV blocks with LRU or LFU (frequency-aware) leaf eviction."""

    def __init__(
        self,
        block_manager: BlockManager,
        eviction_policy: str = "lru",
    ) -> None:
        if eviction_policy not in ("lru", "lfu"):
            raise ValueError(f"Unsupported eviction policy: {eviction_policy}")
        self.manager = block_manager
        self.eviction_policy = eviction_policy
        self.root = RadixNode(block_tokens=(), block_id=-1, parent=None)
        self._step = 0
        self.total_lookup_blocks = 0
        self.total_hit_blocks = 0
        self.total_evictions = 0

    def match_prefix(self, token_ids: list[int]) -> tuple[list[int], int]:
        """Return (matched_physical_block_ids, matched_token_count) aligned to block_size.

        Leaves at least 1 token uncached if the entire prompt matches so the model still
        produces logits for the last prompt token without changing engine semantics.
        """
        self._step += 1
        bs = self.manager.block_size
        # At most floor((len - 1) / bs) full prefix blocks so final token still runs forward.
        max_blocks = max(0, (len(token_ids) - 1) // bs)
        self.total_lookup_blocks += max_blocks

        node = self.root
        matched_blocks: list[int] = []
        for blk_idx in range(max_blocks):
            chunk = tuple(token_ids[blk_idx * bs : (blk_idx + 1) * bs])
            child = node.children.get(chunk)
            if child is None:
                break
            child.last_access_step = self._step
            child.hit_count += 1
            matched_blocks.append(child.block_id)
            node = child

        self.total_hit_blocks += len(matched_blocks)
        return matched_blocks, len(matched_blocks) * bs

    def insert_sequence_blocks(
        self,
        token_ids: list[int],
        physical_blocks: list[int],
    ) -> int:
        """Insert all full blocks of a completed/prefilled sequence into the radix tree.

        Returns the number of newly cached blocks (each gets +1 refcount owned by the tree).
        """
        self._step += 1
        bs = self.manager.block_size
        num_full = min(len(physical_blocks), len(token_ids) // bs)
        node = self.root
        inserted = 0

        for blk_idx in range(num_full):
            chunk = tuple(token_ids[blk_idx * bs : (blk_idx + 1) * bs])
            bid = physical_blocks[blk_idx]
            existing = node.children.get(chunk)
            if existing is not None:
                existing.last_access_step = self._step
                existing.hit_count += 1
                node = existing
            else:
                self.manager.inc_ref(bid)
                child = RadixNode(
                    block_tokens=chunk,
                    block_id=bid,
                    parent=node,
                    last_access_step=self._step,
                    hit_count=1,
                )
                node.children[chunk] = child
                node = child
                inserted += 1
        return inserted

    def _collect_evictable_leaves(self) -> list[RadixNode]:
        leaves: list[RadixNode] = []
        stack = list(self.root.children.values())
        while stack:
            node = stack.pop()
            if not node.children:
                # Only evict leaves not currently pinned by any active sequence (rc == 1).
                if self.manager.refcounts[node.block_id] == 1:
                    leaves.append(node)
            else:
                stack.extend(node.children.values())
        return leaves

    def evict(self, num_blocks_needed: int) -> int:
        """Evict up to `num_blocks_needed` unpinned leaf blocks to free GPU memory."""
        evicted = 0
        while evicted < num_blocks_needed:
            candidates = self._collect_evictable_leaves()
            if not candidates:
                break
            if self.eviction_policy == "lru":
                victim = min(candidates, key=lambda n: n.last_access_step)
            else:
                # Frequency-aware LFU with LRU tie-breaker (protects hot system prompts from scan pollution)
                victim = min(candidates, key=lambda n: (n.hit_count, n.last_access_step))

            assert victim.parent is not None
            del victim.parent.children[victim.block_tokens]
            freed = self.manager.dec_ref(victim.block_id)
            assert freed, f"Expected victim block {victim.block_id} to be freed on eviction"
            evicted += 1
            self.total_evictions += 1
        return evicted

    def clear(self) -> None:
        """Evict all unpinned cached blocks (used at end of run to assert zero block leaks)."""
        while self.evict(10_000) > 0:
            pass

    @property
    def hit_rate(self) -> float:
        if self.total_lookup_blocks == 0:
            return 0.0
        return self.total_hit_blocks / self.total_lookup_blocks
