"""
Volcano Planner — bottom-up, Calcite-style optimizer.

Architecture mirrors Calcite's VolcanoPlanner:
  - RelSet  = equivalence class (like Calcite's RelSet)
  - RelSubset = trait-constrained subset (like Calcite's RelSubset)
  - RuleQueue = FIFO queue of rule matches (like IterativeRuleQueue)
  - Two phases: BUILDING → OPTIMIZING

Key difference from Cascades:
  - Bottom-up registration (children before parents)
  - No task stack, no cost-based pruning during exploration
  - Exhaustive rule firing until queue is empty
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from optimizer.model import RelNode, Cost, Convention, TraitSet
from optimizer.rules import Rule, RuleMatch, default_rules
from optimizer.cost import compute_cost


# ──────────────────────────────────────────────
# RelSet & RelSubset
# ──────────────────────────────────────────────

class RelSubset:
    """
    A trait-constrained subset of a RelSet.
    Like Calcite's RelSubset — groups RelNodes with the same traits.
    """

    def __init__(self, trait_set: TraitSet, rel_set: "RelSet"):
        self.trait_set = trait_set
        self.rel_set = rel_set
        self.rels: list[RelNode] = []
        self.best: RelNode | None = None
        self.best_cost: Cost = Cost.INFINITY

    def add(self, rel: RelNode) -> None:
        if rel not in self.rels:
            self.rels.append(rel)
            rel.rel_subset_key = str(self.trait_set)

    def update_best(self) -> None:
        """Recompute the best RelNode in this subset."""
        for rel in self.rels:
            try:
                cost = compute_cost(rel)
                if cost < self.best_cost:
                    self.best_cost = cost
                    self.best = rel
            except RecursionError:
                pass

    def __repr__(self) -> str:
        best_name = self.best.explain_name() if self.best else "none"
        return f"RelSubset({self.trait_set}, best={best_name}, cost={self.best_cost})"

    def explain(self, indent: int = 0) -> str:
        lines = [f"{'  ' * indent}RelSubset({self.trait_set}):"]
        for rel in self.rels:
            marker = " ← best" if rel is self.best else ""
            try:
                cost = compute_cost(rel)
                lines.append(f"{'  ' * (indent + 1)}{rel.explain_name()}#{rel.id}  {cost}{marker}")
            except RecursionError:
                lines.append(f"{'  ' * (indent + 1)}{rel.explain_name()}#{rel.id}  (cycle){marker}")
        return "\n".join(lines)


class RelSet:
    """
    An equivalence class of RelNodes.
    Like Calcite's RelSet — all RelNodes in a RelSet produce the same result.
    """

    _next_id = 0

    def __init__(self):
        self.id = RelSet._next_id
        RelSet._next_id += 1

        self.rels: list[RelNode] = []
        self.subsets: list[RelSubset] = []
        self.parents: list[RelNode] = []  # RelNodes that reference this set

    def add(self, rel: RelNode) -> RelSubset:
        """Add a RelNode to this set, creating a subset if needed."""
        self.rels.append(rel)
        rel.rel_set_id = self.id

        key = str(rel.trait_set)
        subset = self._find_subset(key)
        if subset is None:
            subset = RelSubset(rel.trait_set, self)
            self.subsets.append(subset)
        subset.add(rel)

        return subset

    def _find_subset(self, trait_key: str) -> RelSubset | None:
        for s in self.subsets:
            if str(s.trait_set) == trait_key:
                return s
        return None

    def __repr__(self) -> str:
        return f"RelSet#{self.id}({len(self.rels)} rels, {len(self.subsets)} subsets)"

    def explain(self, indent: int = 0) -> str:
        lines = [f"{'  ' * indent}RelSet#{self.id} ({len(self.rels)} rels, {len(self.subsets)} subsets):"]
        for subset in self.subsets:
            lines.append(subset.explain(indent + 1))
        return "\n".join(lines)


# ──────────────────────────────────────────────
# Rule Queue
# ──────────────────────────────────────────────

class IterativeRuleQueue:
    """
    FIFO queue of rule matches, with SubstitutionRule priority.
    Like Calcite's IterativeRuleQueue.
    """

    def __init__(self):
        self.queue: list[RuleMatch] = []
        self.pre_queue: list[RuleMatch] = []  # High-priority matches

    def add(self, match: RuleMatch) -> None:
        if match.rule.priority >= 15:
            self.pre_queue.append(match)
        else:
            self.queue.append(match)

    def poll(self) -> RuleMatch | None:
        if self.pre_queue:
            return self.pre_queue.pop(0)
        if self.queue:
            return self.queue.pop(0)
        return None

    @property
    def is_empty(self) -> bool:
        return not self.pre_queue and not self.queue

    @property
    def total_size(self) -> int:
        return len(self.pre_queue) + len(self.queue)


# ──────────────────────────────────────────────
# Volcano Planner
# ──────────────────────────────────────────────

class Phase:
    NONE = "NONE"
    BUILDING = "BUILDING_EQUIVALENCE_CLASSES"
    OPTIMIZING = "OPTIMIZING"


@dataclass
class VolcanoTrace:
    """Records the optimization process for later comparison."""
    events: list[str] = field(default_factory=list)
    rule_firings: list[tuple[str, str]] = field(default_factory=list)  # (rule_name, rel_name)
    rel_sets_created: list[RelSet] = field(default_factory=list)
    phases: list[str] = field(default_factory=list)

    def log(self, msg: str) -> None:
        self.events.append(msg)

    def log_rule(self, rule_name: str, rel_name: str) -> None:
        self.rule_firings.append((rule_name, rel_name))


class VolcanoPlanner:
    """
    Volcano-style optimizer, bottom-up, exhaustive.
    Mirrors Calcite's VolcanoPlanner with IterativeRuleDriver.
    """

    def __init__(self, rules: list[Rule] | None = None, verbose: bool = True):
        self.rules = rules or default_rules()
        self.verbose = verbose

        # Equivalence classes
        self.rel_sets: list[RelSet] = []
        self.map_rel_to_subset: dict[int, RelSubset] = {}  # rel.id → subset

        # Digest-based canonicalization (like Calcite's mapDigestToRel)
        # Prevents duplicate RelNodes with identical structure
        self._digest_map: dict[str, RelNode] = {}

        # Rule queue
        self.rule_queue = IterativeRuleQueue()

        # Track which (rule, rel_id) pairs have been processed to prevent infinite loops
        self._fired_rules: set[tuple[str, int]] = set()

        # State
        self.phase: str = Phase.NONE
        self.root_set: RelSet | None = None
        self.root_subset: RelSubset | None = None
        self.pruned_nodes: set[int] = set()

        # Trace
        self.trace = VolcanoTrace()

    def set_root(self, root: RelNode) -> None:
        """Register the root RelNode and build equivalence classes bottom-up."""
        self.phase = Phase.BUILDING
        self.trace.phases.append(Phase.BUILDING)
        self.trace.log(f"Phase: BUILDING_EQUIVALENCE_CLASSES")
        self.trace.log(f"Registering root: {root.explain_name()}#{root.id}")

        root_subset = self._register(root)

        # Track the root subset for findBestExp
        self.root_subset = root_subset

        self.trace.log(f"Rule queue size after registration: {self.rule_queue.total_size}")

    def _compute_digest(self, rel: RelNode) -> str:
        """
        Compute a structural digest for a RelNode.
        Like Calcite's RelDigest — identical structures produce identical digests.
        Children are referenced by their canonical digest, not by object identity.
        """
        # First, get canonical child digests
        child_digests = []
        for child in rel.inputs:
            cd = self._digest_map.get(child.id)
            if cd is not None:
                # Use the canonical version's digest
                for d, canonical in self._digest_map.items():
                    if canonical is cd:
                        child_digests.append(d)
                        break
            else:
                # Fall back to the child's own digest computation
                child_digests.append(f"#{child.id}")

        # Build digest from type, name, children, and key attributes
        parts = [type(rel).__name__]
        parts.extend(child_digests)

        # Add type-specific attributes
        if hasattr(rel, 'table'):
            parts.append(f"table={rel.table}")
        if hasattr(rel, 'condition'):
            parts.append(f"cond={rel.condition}")
        if hasattr(rel, 'impl'):
            parts.append(f"impl={rel.impl}")
        if hasattr(rel, 'columns'):
            parts.append(f"cols={','.join(rel.columns)}")
        if hasattr(rel, 'group_keys'):
            parts.append(f"grp={','.join(rel.group_keys)}")
        if hasattr(rel, 'selectivity'):
            parts.append(f"sel={rel.selectivity}")

        return "|".join(parts)

    def _register(self, rel: RelNode) -> RelSubset:
        """
        Register a RelNode into the planner.
        Like Calcite's VolcanoPlanner.registerImpl().
        Bottom-up: children are registered first.
        Uses digest-based canonicalization to prevent duplicates.
        """
        # Check if already registered
        if rel.id in self.map_rel_to_subset:
            return self.map_rel_to_subset[rel.id]

        # Register children first (bottom-up) and replace with canonical versions
        canonical_inputs = []
        for child in rel.inputs:
            child_subset = self._register(child)
            # Use the canonical (best) child if available
            if child_subset.best is not None:
                canonical_inputs.append(child_subset.best)
            else:
                canonical_inputs.append(child)

        # Replace inputs with canonical versions
        rel.inputs = canonical_inputs

        # Compute digest and check for existing canonical RelNode
        digest = self._compute_digest(rel)

        # Check if we already have a canonical RelNode with this digest
        for existing_digest, canonical_rel in self._digest_map.items():
            if existing_digest == digest:
                # Already exists — return its subset
                if canonical_rel.id in self.map_rel_to_subset:
                    return self.map_rel_to_subset[canonical_rel.id]

        # Store in digest map
        self._digest_map[digest] = rel

        # Find or create RelSet
        rel_set = self._find_or_create_set(rel)

        # Add to set
        subset = rel_set.add(rel)
        self.map_rel_to_subset[rel.id] = subset

        # Record parent relationships
        for child in rel.inputs:
            child_subset = self.map_rel_to_subset.get(child.id)
            if child_subset:
                if rel not in child_subset.rel_set.parents:
                    child_subset.rel_set.parents.append(rel)

        # Update best costs
        self._update_best_costs()

        # Fire rules (only if not already fired)
        self._fire_rules(rel)

        # IMPORTANT: When a new physical node is registered:
        # 1. Update parent inputs to use this canonical version
        # 2. Re-fire rules on parents (they may now have physical children)
        if rel.trait_set.convention != Convention.NONE:
            for parent_rel in rel_set.parents:
                # Update parent's inputs to use canonical version
                self._update_parent_inputs(parent_rel)
                # Re-fire rules on parent
                self._fire_rules(parent_rel)

        return subset

    def _update_parent_inputs(self, parent_rel: RelNode) -> None:
        """
        Update a parent RelNode's inputs to use canonical (physical) child versions.
        Called when a new physical child becomes available.
        Looks across ALL subsets in a child's RelSet to find a physical implementation.
        """
        for i, child in enumerate(parent_rel.inputs):
            child_subset = self.map_rel_to_subset.get(child.id)
            if child_subset is None:
                continue

            # Look across all subsets in the child's RelSet for a physical best
            best_physical = None
            best_physical_cost = Cost.INFINITY

            for subset in child_subset.rel_set.subsets:
                if subset.trait_set.convention != Convention.NONE:
                    if subset.best is not None and subset.best_cost < best_physical_cost:
                        best_physical_cost = subset.best_cost
                        best_physical = subset.best

            if best_physical is not None:
                parent_rel.inputs[i] = best_physical

    def _find_or_create_set(self, rel: RelNode) -> RelSet:
        """Find or create a RelSet for the given RelNode."""
        # Try to find an existing set this RelNode should belong to
        for s in self.rel_sets:
            if s.rels and self._are_equivalent(s.rels[0], rel):
                return s

        # Create new set
        rel_set = RelSet()
        self.rel_sets.append(rel_set)
        self.trace.rel_sets_created.append(rel_set)
        self.trace.log(f"Created RelSet#{rel_set.id} for {rel.explain_name()}")
        return rel_set

    def _are_equivalent(self, a: RelNode, b: RelNode) -> bool:
        """
        Check if two RelNodes are semantically equivalent.
        Like Calcite's RelSet equivalence — based on result, not type.
        Physical and Logical implementations of the same operation ARE equivalent.
        """
        # Map physical types to their logical counterparts for equivalence
        type_map = {
            "PhysicalJoin": "LogicalJoin",
            "PhysicalFilter": "LogicalFilter",
            "PhysicalProject": "LogicalProject",
            "PhysicalTableScan": "TableScan",
        }

        a_type = type(a).__name__
        b_type = type(b).__name__

        # Normalize types
        a_logical = type_map.get(a_type, a_type)
        b_logical = type_map.get(b_type, b_type)

        if a_logical != b_logical:
            return False

        # Type-specific equivalence checks
        if a_logical in ("LogicalJoin", "PhysicalJoin"):
            # Compare by condition (join_type may not exist on PhysicalJoin)
            eq = a.condition == b.condition  # type: ignore
            if hasattr(a, 'join_type') and hasattr(b, 'join_type'):
                eq = eq and a.join_type == b.join_type  # type: ignore
            return eq
        elif a_logical == "TableScan":
            return a.table == b.table  # type: ignore
        elif a_logical in ("LogicalFilter", "PhysicalFilter"):
            return a.condition == b.condition  # type: ignore
        elif a_logical in ("LogicalProject", "PhysicalProject"):
            return a.columns == b.columns  # type: ignore

        return False

    def _fire_rules(self, rel: RelNode) -> None:
        """
        Fire all rules that match this RelNode.
        Like Calcite's VolcanoPlanner.fireRules().
        Only fires each rule once per RelNode to prevent infinite loops.
        """
        for rule in self.rules:
            key = (rule.name, rel.id)
            if key in self._fired_rules:
                continue

            if rule.matches(rel):
                self._fired_rules.add(key)
                matches = rule.find_matches(rel, self)
                for match in matches:
                    self.trace.log(f"  Match: {rule.name} on {rel.explain_name()}#{rel.id}")
                    self.rule_queue.add(match)

    def optimize(self) -> RelNode | None:
        """
        Run the optimization loop.
        Phase 1: BUILDING (done in set_root)
        Phase 2: Process rule queue (like IterativeRuleDriver.drive())
        Phase 3: OPTIMIZING — find best plan
        """
        if self.phase != Phase.BUILDING:
            raise RuntimeError("Must call set_root() first")

        self.trace.log(f"Processing rule queue ({self.rule_queue.total_size} matches)")

        # Process rule matches
        iteration = 0
        while not self.rule_queue.is_empty:
            iteration += 1
            match = self.rule_queue.poll()
            if match is None:
                break

            self.trace.log(f"[Iter {iteration}] Fire: {match.rule.name} on {match.root.explain_name()}")
            self.trace.log_rule(match.rule.name, match.root.explain_name())

            # Transform: produce new equivalent RelNodes
            new_rels = match.rule.transform(match)

            for new_rel in new_rels:
                self.trace.log(f"  → Created: {new_rel.explain_name()}#{new_rel.id}")
                # Register the new RelNode (may produce more rule matches)
                self._register(new_rel)

            # Safety valve: prevent runaway optimization
            if iteration > 1000:
                self.trace.log(f"Safety valve: stopping after 1000 iterations")
                break

        # Phase 3: OPTIMIZING
        self.phase = Phase.OPTIMIZING
        self.trace.phases.append(Phase.OPTIMIZING)
        self.trace.log(f"Phase: OPTIMIZING")

        return self._find_best_exp()

    def _update_best_costs(self) -> None:
        """Update best costs for all RelSubsets."""
        for rel_set in self.rel_sets:
            for subset in rel_set.subsets:
                subset.update_best()

    def _find_best_exp(self) -> RelNode | None:
        """
        Find the best expression from the root RelSubset.
        Like Calcite's VolcanoPlanner.findBestExp().
        Looks for the best physical implementation in the root's equivalence class.
        """
        if self.root_subset is None:
            return None

        # Find the best physical implementation in the root's RelSet
        best_rel = None
        best_cost = Cost.INFINITY

        for subset in self.root_subset.rel_set.subsets:
            # Prefer physical conventions
            if subset.trait_set.convention == Convention.NONE:
                continue
            if subset.best is not None and subset.best_cost < best_cost:
                best_cost = subset.best_cost
                best_rel = subset.best

        # Fallback: if no physical plan found, return logical best
        if best_rel is None:
            for subset in self.root_subset.rel_set.subsets:
                if subset.best is not None and subset.best_cost < best_cost:
                    best_cost = subset.best_cost
                    best_rel = subset.best

        self.trace.log(f"Best plan: {best_rel.explain_name() if best_rel else 'none'}")

        return best_rel

    def explain(self) -> str:
        """Explain the optimization state."""
        lines = [
            "=" * 60,
            "Volcano Planner State",
            "=" * 60,
            f"Phase: {self.phase}",
            f"RelSets: {len(self.rel_sets)}",
            f"Total rule firings: {len(self.trace.rule_firings)}",
            "",
            "RelSets:",
        ]

        for rel_set in self.rel_sets:
            lines.append(rel_set.explain(1))

        lines.append("")
        lines.append("Rule Firing Order:")
        for i, (rule, rel) in enumerate(self.trace.rule_firings, 1):
            lines.append(f"  {i}. {rule} on {rel}")

        lines.append("")
        lines.append("Trace Events:")
        for event in self.trace.events:
            lines.append(f"  {event}")

        return "\n".join(lines)

    def get_best_plan_cost(self) -> Cost:
        """Get the cost of the best plan found."""
        best_cost = Cost.INFINITY
        for rel_set in self.rel_sets:
            for subset in rel_set.subsets:
                if subset.best is not None and subset.best_cost < best_cost:
                    best_cost = subset.best_cost
        return best_cost
