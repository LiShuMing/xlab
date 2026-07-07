"""
Cascades Planner — top-down, Graefe 1995-style optimizer.

Architecture mirrors the Cascades algorithm:
  - Memo: explicit Group → GroupExpression structure
  - Task Stack: OptimizeGroup, OptimizeExpression, ExploreRules, EnforceProperties
  - Cost-based pruning: upper/lower bound comparison during recursion
  - Top-down exploration from root Group

Key differences from Volcano (Calcite default):
  - Top-down vs bottom-up
  - Explicit task stack vs flat FIFO queue
  - Online cost pruning vs exhaustive exploration
  - Promise-based lazy evaluation vs eager registration
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from optimizer.model import RelNode, Cost, Convention, TraitSet
from optimizer.rules import Rule, RuleMatch, default_rules
from optimizer.cost import compute_cost, get_lower_bound_cost


# ──────────────────────────────────────────────
# Memo Structure
# ──────────────────────────────────────────────

class GroupState(Enum):
    """State of a Group during optimization (like Cascades)."""
    UNOPTIMIZED = "UNOPTIMIZED"
    OPTIMIZING = "OPTIMIZING"
    OPTIMIZED = "OPTIMIZED"


@dataclass
class Group:
    """
    An equivalence class in the Memo.
    Like Cascades' Group — contains multiple GroupExpressions.
    """

    id: int
    expressions: list["GroupExpression"] = field(default_factory=list)
    state: GroupState = GroupState.UNOPTIMIZED
    upper_bound: Cost = Cost.INFINITY  # Current best known cost
    lower_bound: Cost = Cost()  # Minimum possible cost
    best_expr: "GroupExpression | None" = None
    required_traits: TraitSet = field(default_factory=TraitSet)

    def add_expression(self, expr: "GroupExpression") -> None:
        expr.group = self
        if expr not in self.expressions:
            self.expressions.append(expr)

    def update_best(self) -> None:
        """Update the best expression based on cost. Prefer physical when costs are equal."""
        best_cost = Cost.INFINITY
        best = None
        for expr in self.expressions:
            if expr.total_cost < best_cost:
                best_cost = expr.total_cost
                best = expr
            elif expr.total_cost == best_cost and best is not None:
                # Tie-breaker: prefer physical expressions
                if not expr.is_logical and best.is_logical:
                    best = expr
        self.best_expr = best
        if best_cost < Cost.INFINITY:
            self.upper_bound = best_cost

    def __repr__(self) -> str:
        return (f"Group#{self.id}({self.state.value}, "
                f"{len(self.expressions)} exprs, best={self.best_expr})")


@dataclass
class GroupExpression:
    """
    A RelNode placed in a Group, with children pointing to Groups.
    Like Cascades' GroupExpression.
    """

    rel: RelNode
    group: "Group | None" = None
    child_groups: list["Group"] = field(default_factory=list)
    local_cost: Cost = Cost()
    total_cost: Cost = Cost.INFINITY
    is_logical: bool = True  # Logical vs Physical

    def compute_total_cost(self) -> Cost:
        """
        Total cost = local cost + sum of children's best costs.
        This is the core of Cascades' bottom-up cost propagation.
        """
        child_sum = Cost()
        for cg in self.child_groups:
            if cg.best_expr is not None:
                child_sum += cg.best_expr.total_cost
            elif cg.upper_bound != Cost.INFINITY:
                child_sum += cg.upper_bound

        self.total_cost = self.local_cost + child_sum
        return self.total_cost

    def __repr__(self) -> str:
        tag = "L" if self.is_logical else "P"
        return f"GroupExpr#{id(self) % 1000}({tag} {self.rel.explain_name()}, cost={self.total_cost})"


# ──────────────────────────────────────────────
# Memo
# ──────────────────────────────────────────────

class Memo:
    """
    The Memo data structure: explicit tree of Groups and GroupExpressions.
    Like the Memo in Cascades (Graefe 1995).
    """

    def __init__(self):
        self.groups: list[Group] = []
        self._next_group_id = 0
        self.root_group: Group | None = None

    def add_group(self, rel: RelNode) -> Group:
        """Create a new Group containing a single GroupExpression."""
        group = Group(id=self._next_group_id)
        self._next_group_id += 1

        expr = GroupExpression(rel=rel)
        group.add_expression(expr)
        self.groups.append(group)

        return group

    def add_expression_to_group(self, group: Group, rel: RelNode,
                                 child_groups: list["Group"],
                                 is_logical: bool = True) -> GroupExpression:
        """Add a new GroupExpression to an existing Group."""
        expr = GroupExpression(
            rel=rel,
            child_groups=child_groups,
            local_cost=get_lower_bound_cost(rel),
            is_logical=is_logical,
        )
        group.add_expression(expr)
        return expr

    def __repr__(self) -> str:
        return f"Memo({len(self.groups)} groups)"

    def explain(self, indent: int = 0) -> str:
        lines = [f"{'  ' * indent}Memo ({len(self.groups)} groups):"]
        for group in self.groups:
            lines.append(self._explain_group(group, indent + 1))
        return "\n".join(lines)

    def _explain_group(self, group: Group, indent: int) -> str:
        prefix = "  " * indent
        marker = " ← best" if group.best_expr else ""
        lines = [f"{prefix}Group#{group.id} ({group.state.value}, "
                 f"{len(group.expressions)} exprs, ub={group.upper_bound}){marker}"]

        for expr in group.expressions:
            child_refs = ", ".join(f"G{g.id}" for g in expr.child_groups) if expr.child_groups else "leaf"
            best_mark = " ★" if expr is group.best_expr else ""
            lines.append(
                f"{prefix}  └─ {expr.rel.explain_name()}#{expr.rel.id} "
                f"[children: {child_refs}] {expr.total_cost}{best_mark}"
            )

        return "\n".join(lines)


# ──────────────────────────────────────────────
# Task System (Cascades-style)
# ──────────────────────────────────────────────

class Task(ABC):
    """Base class for Cascades optimization tasks."""

    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def execute(self, planner: "CascadesPlanner") -> None:
        ...


class OptimizeGroup(Task):
    """
    Find the best implementation of a Group.
    Like Cascades' OptimizeGroup task.
    Pushes OptimizeExpression tasks for each GroupExpression.
    """

    def __init__(self, group: Group, upper_bound: Cost = Cost.INFINITY):
        self.group = group
        self.upper_bound = upper_bound

    def name(self) -> str:
        return f"OptimizeGroup(G#{self.group.id}, ub={self.upper_bound})"

    def execute(self, planner: "CascadesPlanner") -> None:
        planner.trace.log(f"  Task: {self.name()}")

        # Check if already optimized within this bound
        if self.group.state == GroupState.OPTIMIZED:
            if self.upper_bound >= self.group.upper_bound:
                planner.trace.log(f"    → Already optimized, skip (ub={self.group.upper_bound})")
                return

        # Check upper bound for pruning
        if self.upper_bound <= self.group.lower_bound:
            planner.trace.log(f"    → PRUNED: lower_bound={self.group.lower_bound} >= upper_bound={self.upper_bound}")
            planner.trace.log_pruning(f"Group#{self.group.id} pruned (lb={self.group.lower_bound} >= ub={self.upper_bound})")
            return

        self.group.state = GroupState.OPTIMIZING
        self.group.required_traits = self._determine_required_traits(planner)

        # Phase 1: Recursively optimize children (bottom-up, like real Cascades)
        planner.trace.log(f"    → Recursively optimizing children...")
        self._optimize_children_recursive(planner)

        # Phase 2: Apply exploration/implementation rules (now children have physical exprs)
        planner.trace.log(f"    → Applying exploration rules...")
        planner._apply_exploration_rules(self.group)

        # Phase 3: Compute total costs and pick best
        for expr in self.group.expressions:
            expr.compute_total_cost()
        self.group.update_best()

        self.group.state = GroupState.OPTIMIZED
        planner.trace.log(f"    → Done. Best: {self.group.best_expr}")

    def _optimize_children_recursive(self, planner: "CascadesPlanner") -> None:
        """
        Recursively optimize child groups.
        Like Cascades' recursive OptimizeGroup → OptimizeGroup descent.
        """
        seen_groups = set()
        for expr in self.group.expressions:
            for child_group in expr.child_groups:
                if child_group.id in seen_groups:
                    continue
                seen_groups.add(child_group.id)

                # Compute upper bound for child
                partial_cost = expr.local_cost
                child_ub = self.upper_bound - partial_cost if self.upper_bound != Cost.INFINITY else Cost.INFINITY

                planner.trace.log(f"    → Recurse: OptimizeGroup(G#{child_group.id}, ub={child_ub})")
                planner.trace.log_task(f"OptimizeGroup(G#{child_group.id}, ub={child_ub})")

                # Recursive call (this is the Cascades recursive descent)
                child_task = OptimizeGroup(child_group, child_ub)
                child_task.execute(planner)

    def _determine_required_traits(self, planner: "CascadesPlanner") -> TraitSet:
        """Determine what traits this group needs to provide."""
        # Default: return Convention.NONE (any convention is fine)
        return TraitSet(convention=Convention.NONE)

    def _optimize_children(self, planner: "CascadesPlanner") -> None:
        """Push down optimization to child groups."""
        for expr in self.group.expressions:
            for child_group in expr.child_groups:
                # Check cost bound before recursing
                partial_cost = expr.local_cost
                if partial_cost >= self.upper_bound:
                    continue

                child_ub = self.upper_bound - partial_cost
                planner._task_stack.append(OptimizeGroup(child_group, child_ub))

                planner.trace.log(f"    → Push OptimizeGroup(G#{child_group.id}, ub={child_ub})")


class OptimizeExpression(Task):
    """
    Find the best implementation given a GroupExpression.
    Like Cascades' OptimizeExpression task.
    """

    def __init__(self, expr: GroupExpression, upper_bound: Cost):
        self.expr = expr
        self.upper_bound = upper_bound

    def name(self) -> str:
        return f"OptimizeExpression({self.expr})"

    def execute(self, planner: "CascadesPlanner") -> None:
        planner.trace.log(f"  Task: {self.name()}")

        # Lower bound check
        if self.expr.local_cost >= self.upper_bound:
            planner.trace.log(f"    → PRUNED: local_cost={self.expr.local_cost} >= ub={self.upper_bound}")
            return

        # Optimize each child
        for i, child_group in enumerate(self.expr.child_groups):
            planner._task_stack.append(OptimizeGroup(child_group, self.upper_bound))
            planner.trace.log(f"    → Push OptimizeGroup(G#{child_group.id})")

        # After children are done, compute total cost
        self.expr.compute_total_cost()


class EnforceProperties(Task):
    """
    Ensure that a Group can deliver the required properties.
    Like Cascades' Enforcer task.
    """

    def __init__(self, group: Group, required: TraitSet):
        self.group = group
        self.required = required

    def name(self) -> str:
        return f"EnforceProperties(G#{self.group.id}, need={self.required})"

    def execute(self, planner: "CascadesPlanner") -> None:
        planner.trace.log(f"  Task: {self.name()}")

        # Check if any existing expression already satisfies
        for expr in self.group.expressions:
            if expr.rel.trait_set.satisfies(self.required):
                planner.trace.log(f"    → Already satisfied by {expr}")
                return

        # Try to create enforcer expressions
        # In a full implementation, this would add Sort, Exchange, etc.
        planner.trace.log(f"    → Would add enforcer expressions (simplified)")


# ──────────────────────────────────────────────
# Trace
# ──────────────────────────────────────────────

@dataclass
class CascadesTrace:
    """Records the Cascades optimization process."""
    events: list[str] = field(default_factory=list)
    task_sequence: list[str] = field(default_factory=list)
    rule_firings: list[tuple[str, str]] = field(default_factory=list)  # (rule_name, rel_name)
    pruning_events: list[str] = field(default_factory=list)
    groups_created: list[Group] = field(default_factory=list)

    def log(self, msg: str) -> None:
        self.events.append(msg)

    def log_task(self, name: str) -> None:
        self.task_sequence.append(name)

    def log_rule(self, rule_name: str, rel_name: str) -> None:
        self.rule_firings.append((rule_name, rel_name))

    def log_pruning(self, msg: str) -> None:
        self.pruning_events.append(msg)


# ──────────────────────────────────────────────
# Cascades Planner
# ──────────────────────────────────────────────

class CascadesPlanner:
    """
    Cascades-style optimizer: top-down, task-stack driven, cost-pruned.
    """

    def __init__(self, rules: list[Rule] | None = None, verbose: bool = True):
        self.rules = rules or default_rules()
        self.verbose = verbose

        self.memo = Memo()
        self._task_stack: list[Task] = []

        self.trace = CascadesTrace()

    def set_root(self, root: RelNode) -> None:
        """
        Register the root RelNode and build the initial Memo.
        Unlike Volcano, this is top-down: we create Groups as we traverse down.
        """
        self.trace.log("Building initial Memo (top-down traversal)")
        self._build_memo(root)

        self.trace.log(f"Memo built: {len(self.memo.groups)} groups")

    def _build_memo(self, rel: RelNode) -> Group:
        """
        Build the Memo by traversing the RelNode tree top-down.
        Creates one Group per unique RelNode, with child references to Groups.
        """
        # Check if we already have a Group for this RelNode
        for g in self.memo.groups:
            for expr in g.expressions:
                if expr.rel is rel:
                    return g

        # First, recursively build child Groups (top-down order in creation)
        child_groups = []
        for child in rel.inputs:
            child_group = self._build_memo(child)
            child_groups.append(child_group)

        # Create a new Group for this RelNode (id assigned after children built)
        group = Group(id=len(self.memo.groups))

        # Create the GroupExpression
        expr = GroupExpression(
            rel=rel,
            child_groups=child_groups,
            local_cost=get_lower_bound_cost(rel),
            is_logical=True,
        )
        group.add_expression(expr)
        self.memo.groups.append(group)
        self.memo.root_group = group  # Always update root to the latest (topmost) Group
        self.trace.groups_created.append(group)
        self.trace.log(f"  Created Group#{group.id} for {rel.explain_name()}")

        return group

    def optimize(self) -> RelNode | None:
        """
        Run the Cascades optimization.
        1. Push OptimizeGroup task for root Group
        2. Process task stack (LIFO)
        3. Cost-based pruning during recursion
        """
        if self.memo.root_group is None:
            raise RuntimeError("Must call set_root() first")

        self.trace.log("Starting optimization (top-down, task-stack driven)")

        # Push initial task
        self._task_stack.append(OptimizeGroup(self.memo.root_group, Cost.INFINITY))

        # Process task stack
        iteration = 0
        while self._task_stack:
            iteration += 1
            task = self._task_stack.pop()  # LIFO

            self.trace.log(f"[Iter {iteration}] Pop: {task.name()}")
            self.trace.log_task(task.name())

            task.execute(self)

        self.trace.log(f"Optimization complete ({iteration} iterations)")
        return self._find_best_exp()

    def _apply_exploration_rules(self, group: Group) -> None:
        """
        Apply all exploration rules to expressions in this Group.
        Like Cascades' Explore rules — generates new equivalent expressions.
        Uses incremental pruning: as soon as a physical plan is found,
        use it as an upper bound for subsequent alternatives.
        """
        # Snapshot current expressions (rules may add new ones)
        initial_exprs = list(group.expressions)

        # Track the best physical cost found SO FAR for incremental pruning
        running_best: Cost = Cost.INFINITY

        for expr in initial_exprs:
            # Update the RelNode's inputs to use best physical children from child Groups
            # This is critical for rules that require physical children (like Join→Physical)
            self._update_rel_children(expr.rel)

            for rule in self.rules:
                if rule.matches(expr.rel):
                    # Create a RuleMatch and transform
                    match = RuleMatch(rule=rule, root=expr.rel, inputs=[])
                    new_rels = rule.transform(match)

                    for new_rel in new_rels:
                        # Check if we need to build child groups for the new RelNode
                        child_groups = []
                        for child in new_rel.inputs:
                            # Find or create group for child
                            child_group = self._find_or_build_group_for_rel(child)
                            child_groups.append(child_group)

                        # Check cost against running best BEFORE adding
                        temp_expr = GroupExpression(
                            rel=new_rel,
                            child_groups=child_groups,
                            local_cost=get_lower_bound_cost(new_rel),
                            is_logical=new_rel.trait_set.convention == Convention.NONE,
                        )
                        temp_expr.compute_total_cost()

                        if temp_expr.total_cost >= running_best:
                            self.trace.log_pruning(
                                f"    ✂ Pruned: {new_rel.explain_name()} "
                                f"(lb={temp_expr.total_cost} >= running_best={running_best})"
                            )
                            continue  # Skip this expensive alternative

                        # Add to group
                        new_expr = self.memo.add_expression_to_group(
                            group=group,
                            rel=new_rel,
                            child_groups=child_groups,
                            is_logical=new_rel.trait_set.convention == Convention.NONE
                        )
                        new_expr.total_cost = temp_expr.total_cost

                        self.trace.log(f"    → Rule {rule.name} added: {new_rel.explain_name()}")
                        self.trace.log_rule(rule.name, new_rel.explain_name())

                        # Update running best
                        if new_rel.trait_set.convention != Convention.NONE:
                            if temp_expr.total_cost < running_best:
                                running_best = temp_expr.total_cost

        # After all rules have fired, also check if any existing expressions
        # can now be pruned based on the new upper_bound
        for expr in group.expressions:
            if expr is group.best_expr:
                continue  # Don't prune the current best
            expr.compute_total_cost()
            if running_best != Cost.INFINITY and expr.total_cost >= running_best:
                self.trace.log_pruning(
                    f"    ✂ Pruned: {expr.rel.explain_name()} "
                    f"(cost={expr.total_cost} >= ub={running_best})"
                )

    def _update_rel_children(self, rel: RelNode) -> None:
        """
        Update a RelNode's inputs to use best physical children from their Groups.
        Like Cascades' GroupExpression child pointer update.
        """
        for i, child in enumerate(rel.inputs):
            child_group = self._find_group_for_rel(child)
            if child_group is not None:
                # Look for best physical expression in child Group
                best_physical = None
                best_cost = Cost.INFINITY
                for child_expr in child_group.expressions:
                    if not child_expr.is_logical and child_expr.total_cost < best_cost:
                        best_cost = child_expr.total_cost
                        best_physical = child_expr.rel

                if best_physical is not None:
                    rel.inputs[i] = best_physical

    def _find_group_for_rel(self, rel: RelNode) -> Group | None:
        """Find the Group containing a RelNode."""
        for g in self.memo.groups:
            for expr in g.expressions:
                if expr.rel is rel:
                    return g
        return None

    def _find_or_build_group_for_rel(self, rel: RelNode) -> Group:
        """Find an existing Group for a RelNode, or create a new one."""
        for g in self.memo.groups:
            for expr in g.expressions:
                if expr.rel is rel:
                    return g
        # Create new
        return self._build_memo(rel)

    def _find_best_exp(self) -> RelNode | None:
        """Extract the best plan from the Memo."""
        if self.memo.root_group is None:
            return None

        self.memo.root_group.update_best()

        if self.memo.root_group.best_expr:
            return self.memo.root_group.best_expr.rel
        return None

    def explain(self) -> str:
        """Explain the optimization state."""
        lines = [
            "=" * 60,
            "Cascades Planner State",
            "=" * 60,
            f"Groups: {len(self.memo.groups)}",
            f"Total tasks executed: {len(self.trace.task_sequence)}",
            f"Total rule firings: {len(self.trace.rule_firings)}",
            f"Pruning events: {len(self.trace.pruning_events)}",
            "",
            "Memo Structure:",
            self.memo.explain(1),
            "",
            "Task Sequence:",
        ]

        for i, task_name in enumerate(self.trace.task_sequence, 1):
            lines.append(f"  {i}. {task_name}")

        lines.append("")
        lines.append("Rule Firing Order:")
        for i, (rule, rel) in enumerate(self.trace.rule_firings, 1):
            lines.append(f"  {i}. {rule} on {rel}")

        if self.trace.pruning_events:
            lines.append("")
            lines.append("Pruning Events:")
            for event in self.trace.pruning_events:
                lines.append(f"  {event}")

        return "\n".join(lines)

    def get_best_plan_cost(self) -> Cost:
        """Get the cost of the best plan found."""
        if self.memo.root_group and self.memo.root_group.best_expr:
            return self.memo.root_group.best_expr.total_cost
        return Cost.INFINITY
