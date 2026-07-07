"""
Transformation rules shared by both optimizers.

Each rule corresponds to a Calcite RelOptRule.
Rules define a pattern (what RelNode types to match) and a transform
(how to produce equivalent expressions).

Convention handling:
- Logical rules produce Logical nodes (Convention.NONE)
- Physical rules require physical children (same convention)
- Scan conversion rules are the "entry point" to physical plans
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Any

from optimizer.model import (
    RelNode, LogicalJoin, LogicalFilter, LogicalProject,
    LogicalAggregate, TableScan, PhysicalJoin, PhysicalFilter,
    PhysicalProject, PhysicalTableScan,
    Convention, TraitSet, Cost
)

if TYPE_CHECKING:
    from volcano.planner import VolcanoPlanner
    from cascades.planner import CascadesPlanner


def _has_physical_children(rel: RelNode) -> bool:
    """Check if all children are physical (non-NONE convention)."""
    return all(
        child.trait_set.convention != Convention.NONE
        for child in rel.inputs
    )


@dataclass
class RuleMatch:
    """A successful rule match, like Calcite's VolcanoRuleCall."""
    rule: "Rule"
    root: RelNode  # The RelNode that matched the root operand
    inputs: list[RelNode]  # Matched child inputs
    bindings: dict[str, Any] = field(default_factory=dict)


class Rule:
    """
    Base class for transformation rules.
    Like Calcite's RelOptRule.
    """

    def __init__(self, name: str, priority: int = 0):
        self.name = name
        self.priority = priority  # Higher = fire first

    def matches(self, rel: RelNode) -> bool:
        """Check if this rule matches the given RelNode."""
        raise NotImplementedError

    def transform(self, match: RuleMatch) -> list[RelNode]:
        """
        Given a successful match, produce new equivalent RelNode(s).
        Like Calcite's RelOptRuleCall.transformTo().
        """
        raise NotImplementedError

    def find_matches(self, rel: RelNode, planner: Any) -> list[RuleMatch]:
        """Find all matches for this rule given a root RelNode."""
        if not self.matches(rel):
            return []
        return self._find_matches_impl(rel, planner)

    def _find_matches_impl(self, rel: RelNode, planner: Any) -> list[RuleMatch]:
        return [RuleMatch(rule=self, root=rel, inputs=[])]


# ──────────────────────────────────────────────
# Concrete Rules
# ──────────────────────────────────────────────

class FilterToHashJoinRule(Rule):
    """
    Filter(LogicalJoin) → PhysicalHashJoin(physical_children).
    Only fires when children are already physical.
    Like Calcite's JoinToHashJoinRule with convention constraints.
    """

    def __init__(self):
        super().__init__("Filter→HashJoin", priority=10)

    def matches(self, rel: RelNode) -> bool:
        if not isinstance(rel, LogicalFilter):
            return False
        if not isinstance(rel.input, LogicalJoin):
            return False
        # Require physical children
        return _has_physical_children(rel.input)

    def transform(self, match: RuleMatch) -> list[RelNode]:
        filter_rel: LogicalFilter = match.root  # type: ignore
        join: LogicalJoin = filter_rel.input

        if "=" in filter_rel.condition:
            hash_join = PhysicalJoin(
                left=join.left, right=join.right,
                condition=join.condition,
                impl="HashJoin",
                trait_set=TraitSet(convention=Convention.ENUMERABLE),
                selectivity=join.selectivity * filter_rel.selectivity,
            )
            return [hash_join]
        return []


class FilterToNestedLoopRule(Rule):
    """
    Filter(LogicalJoin) → PhysicalNestedLoop(physical_children).
    """

    def __init__(self):
        super().__init__("Filter→NestedLoop", priority=5)

    def matches(self, rel: RelNode) -> bool:
        if not isinstance(rel, LogicalFilter):
            return False
        if not isinstance(rel.input, LogicalJoin):
            return False
        return _has_physical_children(rel.input)

    def transform(self, match: RuleMatch) -> list[RelNode]:
        filter_rel: LogicalFilter = match.root  # type: ignore
        join: LogicalJoin = filter_rel.input

        nl_join = PhysicalJoin(
            left=join.left, right=join.right,
            condition=join.condition,
            impl="NestedLoop",
            trait_set=TraitSet(convention=Convention.ENUMERABLE),
            selectivity=join.selectivity * filter_rel.selectivity,
        )
        return [nl_join]


class LogicalJoinToPhysicalRule(Rule):
    """
    LogicalJoin → HashJoin/NestedLoop (only when children are physical).
    This is the key convention enforcement rule.
    """

    def __init__(self):
        super().__init__("Join→Physical", priority=8)

    def matches(self, rel: RelNode) -> bool:
        if not isinstance(rel, LogicalJoin):
            return False
        # Only fire when children are physical
        return _has_physical_children(rel)

    def transform(self, match: RuleMatch) -> list[RelNode]:
        join: LogicalJoin = match.root  # type: ignore

        hash_join = PhysicalJoin(
            left=join.left, right=join.right,
            condition=join.condition,
            impl="HashJoin",
            trait_set=TraitSet(convention=Convention.ENUMERABLE),
            selectivity=join.selectivity,
        )
        nl_join = PhysicalJoin(
            left=join.left, right=join.right,
            condition=join.condition,
            impl="NestedLoop",
            trait_set=TraitSet(convention=Convention.ENUMERABLE),
            selectivity=join.selectivity,
        )
        return [hash_join, nl_join]


class LogicalScanToPhysicalRule(Rule):
    """
    TableScan(LOGICAL) → PhysicalTableScan(ENUMERABLE).
    This is the "leaf" conversion rule — the starting point for physical plans.
    """

    def __init__(self):
        super().__init__("Scan→PhysicalScan", priority=20)

    def matches(self, rel: RelNode) -> bool:
        return isinstance(rel, TableScan) and rel.trait_set.convention == Convention.NONE

    def transform(self, match: RuleMatch) -> list[RelNode]:
        scan: TableScan = match.root  # type: ignore

        pscan = PhysicalTableScan(
            table=scan.table,
            row_count=scan._rc,
            trait_set=TraitSet(convention=Convention.ENUMERABLE),
        )
        return [pscan]


class LogicalFilterToPhysicalRule(Rule):
    """
    LogicalFilter(physical_input) → PhysicalFilter(physical_input).
    """

    def __init__(self):
        super().__init__("Filter→PhysicalFilter", priority=7)

    def matches(self, rel: RelNode) -> bool:
        if not isinstance(rel, LogicalFilter):
            return False
        # Only fire when input is already physical
        return _has_physical_children(rel)

    def transform(self, match: RuleMatch) -> list[RelNode]:
        filt: LogicalFilter = match.root  # type: ignore

        pfilter = PhysicalFilter(
            input=filt.input,
            condition=filt.condition,
            trait_set=TraitSet(convention=Convention.ENUMERABLE),
            selectivity=filt.selectivity,
        )
        return [pfilter]


class LogicalProjectToPhysicalRule(Rule):
    """
    LogicalProject(physical_input) → PhysicalProject(physical_input).
    """

    def __init__(self):
        super().__init__("Project→PhysicalProject", priority=6)

    def matches(self, rel: RelNode) -> bool:
        if not isinstance(rel, LogicalProject):
            return False
        return _has_physical_children(rel)

    def transform(self, match: RuleMatch) -> list[RelNode]:
        proj: LogicalProject = match.root  # type: ignore

        pproj = PhysicalProject(
            input=proj.input,
            columns=proj.columns,
            trait_set=TraitSet(convention=Convention.ENUMERABLE),
        )
        return [pproj]


class JoinCommuteRule(Rule):
    """
    Join(A, B) → Join(B, A) — join commutativity.
    Only applies to LogicalJoins with leaf children (TableScans).
    Demonstrates how Volcano explores join reorderings.
    """

    def __init__(self):
        super().__init__("JoinCommute", priority=3)

    def matches(self, rel: RelNode) -> bool:
        return isinstance(rel, LogicalJoin)

    def transform(self, match: RuleMatch) -> list[RelNode]:
        join: LogicalJoin = match.root  # type: ignore

        # Only commute if both sides are scans (simple case to avoid infinite loops)
        if isinstance(join.left, TableScan) and isinstance(join.right, TableScan):
            swapped = LogicalJoin(
                left=join.right, right=join.left,
                condition=join.condition,
                join_type=join.join_type,
                selectivity=join.selectivity,
            )
            return [swapped]
        return []


class FilterPushDownRule(Rule):
    """
    Filter(Join(A, B)) → Join(Filter(A), B) — filter pushdown into join children.
    Simplified: only works when filter condition mentions a single table.
    """

    def __init__(self):
        super().__init__("FilterPushDown", priority=15)

    def matches(self, rel: RelNode) -> bool:
        if not isinstance(rel, LogicalFilter):
            return False
        return isinstance(rel.input, LogicalJoin)

    def transform(self, match: RuleMatch) -> list[RelNode]:
        filter_rel: LogicalFilter = match.root  # type: ignore
        join: LogicalJoin = filter_rel.input

        cond = filter_rel.condition.lower()
        # Check if condition can be pushed to left child (mentions 'a' but not 'b')
        if "a" in cond and "b" not in cond:
            pushed_filter = LogicalFilter(
                input=join.left,
                condition=filter_rel.condition,
                selectivity=filter_rel.selectivity,
            )
            new_join = LogicalJoin(
                left=pushed_filter, right=join.right,
                condition=join.condition,
                join_type=join.join_type,
                selectivity=join.selectivity,
            )
            return [new_join]
        elif "b" in cond and "a" not in cond:
            pushed_filter = LogicalFilter(
                input=join.right,
                condition=filter_rel.condition,
                selectivity=filter_rel.selectivity,
            )
            new_join = LogicalJoin(
                left=join.left, right=pushed_filter,
                condition=join.condition,
                join_type=join.join_type,
                selectivity=join.selectivity,
            )
            return [new_join]

        return []


class LogicalAggregateToPhysicalRule(Rule):
    """
    LogicalAggregate(physical_input) → PhysicalAggregate(physical_input).
    """

    def __init__(self):
        super().__init__("Agg→PhysicalAgg", priority=4)

    def matches(self, rel: RelNode) -> bool:
        if not isinstance(rel, LogicalAggregate):
            return False
        return _has_physical_children(rel)

    def transform(self, match: RuleMatch) -> list[RelNode]:
        agg: LogicalAggregate = match.root  # type: ignore

        class PhysicalAggregate(RelNode):
            def __init__(self, input_rel: RelNode, group_keys: list[str],
                         agg_funcs: list[str], trait_set: TraitSet):
                super().__init__([input_rel], trait_set)
                self.group_keys = group_keys
                self.agg_funcs = agg_funcs

            @property
            def input(self) -> RelNode:
                return self.inputs[0]

            def explain_name(self) -> str:
                aggs = ", ".join(self.agg_funcs) if self.agg_funcs else ""
                return f"HashAgg(group=[{', '.join(self.group_keys)}], {aggs})"

            def compute_row_count(self) -> float:
                return min(self.input.row_count(), 100.0)

        pagg = PhysicalAggregate(
            input_rel=agg.input,
            group_keys=agg.group_keys,
            agg_funcs=agg.agg_funcs,
            trait_set=TraitSet(convention=Convention.ENUMERABLE),
        )
        return [pagg]


# ──────────────────────────────────────────────
# Default rule set
# ──────────────────────────────────────────────

def default_rules() -> list[Rule]:
    """The default set of transformation rules."""
    return [
        LogicalScanToPhysicalRule(),
        FilterToHashJoinRule(),
        FilterToNestedLoopRule(),
        LogicalJoinToPhysicalRule(),
        LogicalFilterToPhysicalRule(),
        LogicalProjectToPhysicalRule(),
        JoinCommuteRule(),
        FilterPushDownRule(),
        LogicalAggregateToPhysicalRule(),
    ]
