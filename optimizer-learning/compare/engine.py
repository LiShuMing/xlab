"""
Comparison engine: side-by-side analysis of Volcano and Cascades optimizers.

Compares:
  1. Equivalence class construction (RelSets vs Groups)
  2. Rule firing order
  3. Optimal plan consistency
  4. Cost model and pruning behavior
  5. Search space exploration
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from optimizer.model import RelNode, Cost
from optimizer.cost import compute_cost
from volcano.planner import VolcanoPlanner, VolcanoTrace
from cascades.planner import CascadesPlanner, CascadesTrace


@dataclass
class ComparisonResult:
    """Result of comparing Volcano and Cascades on the same query."""
    volcano_planner: VolcanoPlanner
    cascades_planner: CascadesPlanner

    # Equivalence class comparison
    volcano_rel_sets: int = 0
    cascades_groups: int = 0

    # Rule firing comparison
    volcano_rule_count: int = 0
    cascades_rule_count: int = 0
    volcano_rule_order: list[tuple[str, str]] = field(default_factory=list)
    cascades_rule_order: list[tuple[str, str]] = field(default_factory=list)

    # Plan comparison
    volcano_best: RelNode | None = None
    cascades_best: RelNode | None = None
    volcano_cost: Cost = Cost.INFINITY
    cascades_cost: Cost = Cost.INFINITY

    # Structural comparison
    pruning_count: int = 0  # Cascades pruning events
    tasks_executed: int = 0  # Cascades task count

    def summarize(self) -> str:
        lines = [
            "=" * 70,
            "  COMPARISON: Volcano (Calcite-style) vs Cascades (Graefe 1995)",
            "=" * 70,
            "",
            "┌──────────────────────────────────────────────────────────────┐",
            "│                    STRUCTURAL COMPARISON                      │",
            "├────────────────────────────────┬─────────────┬───────────────┤",
            f"│ {'Metric':<30} │ {'Volcano':<11} │ {'Cascades':<12} │",
            "├────────────────────────────────┼─────────────┼───────────────┤",
            f"│ {'Equivalence Classes':<30} │ {self.volcano_rel_sets:<11} │ {self.cascades_groups:<12} │",
            f"│ {'Rule Firings':<30} │ {self.volcano_rule_count:<11} │ {self.cascades_rule_count:<12} │",
            f"│ {'Tasks/Iterations':<30} │ {self.volcano_rule_count:<11} │ {self.tasks_executed:<12} │",
            f"│ {'Cost Prunings':<30} │ {'N/A (exhaustive)':<11} │ {self.pruning_count:<12} │",
            "└────────────────────────────────┴─────────────┴───────────────┘",
            "",
            "┌──────────────────────────────────────────────────────────────┐",
            "│                      PLAN COMPARISON                          │",
            "├────────────────────────────────┬─────────────────────────────┤",
            f"│ {'Optimizer':<30} │ {'Result':<27} │",
            "├────────────────────────────────┼─────────────────────────────┤",
            f"│ {'Volcano':<30} │ {self._volcano_plan_summary():<27} │",
            f"│ {'Cascades':<30} │ {self._cascades_plan_summary():<27} │",
            "└────────────────────────────────┴─────────────────────────────┘",
            "",
        ]

        # Check plan consistency
        plans_match = self._plans_match()
        lines.append(
            "Plan Consistency: " + ("✓ SAME PLAN" if plans_match else "✗ DIFFERENT PLANS")
        )

        if not plans_match:
            lines.append(f"  Volcano best: {self.volcano_best}")
            lines.append(f"  Volcano cost: {self.volcano_cost}")
            lines.append(f"  Cascades best: {self.cascades_best}")
            lines.append(f"  Cascades cost: {self.cascades_cost}")

        return "\n".join(lines)

    def _volcano_plan_summary(self) -> str:
        if self.volcano_best:
            cost_str = f"cost={self.volcano_cost}"
            return f"{self.volcano_best.explain_name()}"
        return "none"

    def _cascades_plan_summary(self) -> str:
        if self.cascades_best:
            return f"{self.cascades_best.explain_name()}"
        return "none"

    def _plans_match(self) -> bool:
        if self.volcano_best is None and self.cascades_best is None:
            return True
        if self.volcano_best is None or self.cascades_best is None:
            return False
        # Compare by explain_name (simplified)
        return self.volcano_best.explain_name() == self.cascades_best.explain_name()

    def detail(self) -> str:
        """Full detailed comparison."""
        lines = [self.summarize()]

        lines.append("")
        lines.append("=" * 70)
        lines.append("  VOLCANO RULE FIRING ORDER")
        lines.append("=" * 70)
        for i, (rule, rel) in enumerate(self.volcano_rule_order, 1):
            lines.append(f"  {i:>3}. {rule:<25} → {rel}")

        lines.append("")
        lines.append("=" * 70)
        lines.append("  CASCADES RULE FIRING ORDER")
        lines.append("=" * 70)
        for i, (rule, rel) in enumerate(self.cascades_rule_order, 1):
            lines.append(f"  {i:>3}. {rule:<25} → {rel}")

        lines.append("")
        lines.append("=" * 70)
        lines.append("  KEY DIFFERENCES")
        lines.append("=" * 70)
        lines.extend(self._key_differences())

        return "\n".join(lines)

    def _key_differences(self) -> list[str]:
        lines = []

        # 1. Algorithm direction
        lines.append("")
        lines.append("1. Algorithm Direction:")
        lines.append("   Volcano:  Bottom-up — children registered before parents")
        lines.append("   Cascades: Top-down — starts at root, pushes requirements down")

        # 2. Equivalence class structure
        lines.append("")
        lines.append("2. Equivalence Class Structure:")
        lines.append(f"   Volcano:  {self.volcano_rel_sets} RelSets (implicit memo via RelSet→RelSubset)")
        lines.append(f"   Cascades: {self.cascades_groups} Groups (explicit Memo with GroupExpression)")
        if self.volcano_rel_sets != self.cascades_groups:
            lines.append(f"   → Difference: {abs(self.volcano_rel_sets - self.cascades_groups)} classes")
            lines.append(f"   → Reason: Volcano merges equivalent nodes; Cascades creates per-RelNode")

        # 3. Rule execution model
        lines.append("")
        lines.append("3. Rule Execution Model:")
        lines.append("   Volcano:  Flat FIFO queue — all matches treated equally")
        lines.append("   Cascades: Task stack (LIFO) — OptimizeGroup → OptimizeExpression → ExploreRules")

        # 4. Cost pruning
        lines.append("")
        lines.append("4. Cost Pruning:")
        if self.pruning_count > 0:
            lines.append(f"   Volcano:  No cost-based pruning (exhaustive)")
            lines.append(f"   Cascades: {self.pruning_count} pruning events (upper/lower bound)")
        else:
            lines.append("   Neither optimizer performed cost-based pruning in this case")

        # 5. Rule firing count
        lines.append("")
        lines.append("5. Rule Firing Count:")
        lines.append(f"   Volcano:  {self.volcano_rule_count} firings")
        lines.append(f"   Cascades: {self.cascades_rule_count} firings")
        if self.volcano_rule_count != self.cascades_rule_count:
            diff = abs(self.volcano_rule_count - self.cascades_rule_count)
            lines.append(f"   → Cascades fired {diff} {'fewer' if self.cascades_rule_count < self.volcano_rule_count else 'more'} rules")
            if self.cascades_rule_count < self.volcano_rule_count:
                lines.append("   → Reason: Cascades prunes expensive branches early")

        return lines


def compare(volcano: VolcanoPlanner, cascades: CascadesPlanner,
            root: RelNode) -> ComparisonResult:
    """
    Run both optimizers on the same RelNode tree and compare.
    """
    result = ComparisonResult(
        volcano_planner=volcano,
        cascades_planner=cascades,
    )

    # Collect equivalence class counts
    result.volcano_rel_sets = len(volcano.rel_sets)
    result.cascades_groups = len(cascades.memo.groups)

    # Collect rule firing info
    result.volcano_rule_count = len(volcano.trace.rule_firings)
    result.cascades_rule_count = len(cascades.trace.rule_firings)
    result.volcano_rule_order = list(volcano.trace.rule_firings)
    result.cascades_rule_order = list(cascades.trace.rule_firings)

    # Collect best plans
    result.volcano_best = volcano._find_best_exp()
    result.cascades_best = cascades._find_best_exp()

    # Collect costs
    result.volcano_cost = volcano.get_best_plan_cost()
    result.cascades_cost = cascades.get_best_plan_cost()

    # Cascades-specific metrics
    result.pruning_count = len(cascades.trace.pruning_events)
    result.tasks_executed = len(cascades.trace.task_sequence)

    return result
