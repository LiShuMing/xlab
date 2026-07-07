"""
DP-style Join Reordering algorithm (System R style).

Enumerates all join orderings for N tables using dynamic programming,
caching optimal sub-trees to avoid redundant computation.
Like Calcite's heuristic join reorder with DP.

Algorithm:
  dp(S) = best plan for table subset S
  For each proper partition (S1, S2) of S where S1 ∪ S2 = S:
    candidate = Join(dp(S1), dp(S2))
    if candidate.cost < best: best = candidate

Complexity: O(3^N) for N tables (much better than O(N!) exhaustive).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import FrozenSet

from optimizer.model import (
    RelNode, Cost, Convention, TraitSet,
    TableScan, LogicalJoin, PhysicalJoin, PhysicalTableScan,
)
from optimizer.cost import compute_cost, get_lower_bound_cost


@dataclass
class JoinEdge:
    """A join condition between two tables."""
    left_table: str
    right_table: str
    condition: str
    selectivity: float = 0.01


@dataclass
class JoinOrderingResult:
    """Result of join ordering for a table subset."""
    plan: RelNode
    cost: Cost
    tables: FrozenSet[str]


@dataclass
class JoinReorderTrace:
    """Records the join reorder process for learning."""
    partitions_evaluated: int = 0
    candidates_generated: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    all_plans: list[tuple[str, RelNode, Cost]] = field(default_factory=list)

    def log_plan(self, tables_str: str, plan: RelNode, cost: Cost) -> None:
        self.all_plans.append((tables_str, plan, cost))


class JoinReorderer:
    """
    DP-style join order optimizer.
    Like System R's join ordering algorithm.
    """

    def __init__(self, tables: dict[str, float], join_edges: list[JoinEdge]):
        """
        Args:
            tables: {table_name: row_count}
            join_edges: join conditions between tables
        """
        self.tables = tables
        self.join_edges = join_edges
        self.table_names = frozenset(tables.keys())
        self.cache: dict[FrozenSet[str], JoinOrderingResult] = {}
        self.trace = JoinReorderTrace()

    def optimize(self) -> JoinOrderingResult:
        """Find the optimal join order for all tables."""
        self.cache.clear()
        result = self._dp(self.table_names)
        return result

    def _dp(self, subset: FrozenSet[str]) -> JoinOrderingResult:
        """
        Find the best plan for a subset of tables using DP.
        Like Calcite's findBestJoinOrder().
        """
        # Cache hit
        if subset in self.cache:
            self.trace.cache_hits += 1
            return self.cache[subset]

        self.trace.cache_misses += 1

        # Base case: single table
        if len(subset) == 1:
            table_name = next(iter(subset))
            scan = PhysicalTableScan(
                table=table_name,
                row_count=self.tables[table_name],
                trait_set=TraitSet(convention=Convention.ENUMERABLE),
            )
            result = JoinOrderingResult(
                plan=scan,
                cost=compute_cost(scan),
                tables=subset,
            )
            self.cache[subset] = result
            self.trace.log_plan(
                table_name, scan, result.cost
            )
            return result

        # DP: enumerate all proper partitions (S1, S2) where S1 ∪ S2 = subset
        best_result: JoinOrderingResult | None = None

        tables_list = sorted(subset)
        # Generate partitions: for each split point, S1 = first k tables, S2 = rest
        # For N tables, we consider all 2^(N-1) - 1 valid partitions
        # Simplified: only consider contiguous partitions for learning
        for k in range(1, len(tables_list)):
            s1 = frozenset(tables_list[:k])
            s2 = frozenset(tables_list[k:])

            self.trace.partitions_evaluated += 1

            # Recursive calls
            left_result = self._dp(s1)
            right_result = self._dp(s2)

            # Find join condition between S1 and S2
            join_edges = self._find_join_edges(s1, s2)

            for edge in join_edges:
                self.trace.candidates_generated += 1

                # Create PhysicalJoin
                join = PhysicalJoin(
                    left=left_result.plan,
                    right=right_result.plan,
                    condition=edge.condition,
                    impl="HashJoin",
                    trait_set=TraitSet(convention=Convention.ENUMERABLE),
                    selectivity=edge.selectivity,
                )

                # Compute cost
                cost = compute_cost(join)

                self.trace.log_plan(
                    f"({','.join(sorted(s1))}) ⨝ ({','.join(sorted(s2))})",
                    join,
                    cost,
                )

                if best_result is None or cost < best_result.cost:
                    best_result = JoinOrderingResult(
                        plan=join,
                        cost=cost,
                        tables=subset,
                    )

            # Also try swapped order (right, left) — join commutativity
            for edge in join_edges:
                self.trace.candidates_generated += 1

                join = PhysicalJoin(
                    left=right_result.plan,
                    right=left_result.plan,
                    condition=edge.condition,
                    impl="HashJoin",
                    trait_set=TraitSet(convention=Convention.ENUMERABLE),
                    selectivity=edge.selectivity,
                )

                cost = compute_cost(join)

                self.trace.log_plan(
                    f"({','.join(sorted(s2))}) ⨝ ({','.join(sorted(s1))})",
                    join,
                    cost,
                )

                if best_result is None or cost < best_result.cost:
                    best_result = JoinOrderingResult(
                        plan=join,
                        cost=cost,
                        tables=subset,
                    )

        # If no join edges found, create a cross join as fallback
        if best_result is None and len(subset) > 1:
            s1 = frozenset(tables_list[:len(tables_list) // 2])
            s2 = frozenset(tables_list[len(tables_list) // 2:])
            left_result = self._dp(s1)
            right_result = self._dp(s2)

            join = PhysicalJoin(
                left=left_result.plan,
                right=right_result.plan,
                condition="CROSS JOIN",
                impl="NestedLoop",
                trait_set=TraitSet(convention=Convention.ENUMERABLE),
                selectivity=1.0,
            )
            best_result = JoinOrderingResult(
                plan=join,
                cost=compute_cost(join),
                tables=subset,
            )

        self.cache[subset] = best_result  # type: ignore
        return best_result  # type: ignore

    def _find_join_edges(self, s1: FrozenSet[str], s2: FrozenSet[str]) -> list[JoinEdge]:
        """Find join conditions that connect tables in S1 with tables in S2."""
        edges = []
        for edge in self.join_edges:
            if (edge.left_table in s1 and edge.right_table in s2) or \
               (edge.left_table in s2 and edge.right_table in s1):
                edges.append(edge)
        return edges

    def get_all_table_permutations(self) -> list[list[str]]:
        """Get all valid table orderings (for display purposes)."""
        tables = sorted(self.tables.keys())
        return list(combinations_generator(tables))

    def explain(self) -> str:
        """Explain the join reorder results."""
        lines = [
            "=" * 70,
            f"  Join Reorder Results (DP, {len(self.tables)} tables)",
            "=" * 70,
            f"Tables: {', '.join(sorted(self.tables.keys()))}",
            f"Join edges: {len(self.join_edges)}",
            "",
            f"Partitions evaluated: {self.trace.partitions_evaluated}",
            f"Candidates generated: {self.trace.candidates_generated}",
            f"Cache hits: {self.trace.cache_hits}",
            f"Cache misses: {self.trace.cache_misses}",
            f"Total plans considered: {len(self.trace.all_plans)}",
            "",
            "Top 5 Plans by Cost:",
            "-" * 70,
        ]

        # Sort by cost
        sorted_plans = sorted(self.trace.all_plans, key=lambda x: x[2])

        for i, (tables_str, plan, cost) in enumerate(sorted_plans[:5], 1):
            lines.append(f"  {i}. [{tables_str}]")
            lines.append(f"     Plan: {plan.explain_name()}")
            lines.append(f"     Cost: {cost}")
            lines.append("")

        if sorted_plans:
            lines.append(f"Best Plan: {sorted_plans[0][1].explain_name()}")
            lines.append(f"Best Cost: {sorted_plans[0][2]}")

        return "\n".join(lines)


def combinations_generator(tables: list[str]) -> list[list[str]]:
    """Generate all permutations of tables (for display)."""
    if len(tables) <= 1:
        return [tables[:]]

    result = []
    for i, t in enumerate(tables):
        rest = tables[:i] + tables[i + 1:]
        for perm in combinations_generator(rest):
            result.append([t] + perm)
    return result


def extract_tables_and_joins(root: RelNode) -> tuple[dict[str, float], list[JoinEdge]]:
    """
    Extract table info and join conditions from a RelNode tree.
    For nested joins, picks the rightmost table from the left subtree
    and leftmost from the right subtree to match chain join patterns.
    """
    tables: dict[str, float] = {}
    edges: list[JoinEdge] = []
    seen_conditions: set[tuple[str, str]] = set()

    def visit(rel: RelNode) -> None:
        if isinstance(rel, TableScan):
            tables[rel.table] = rel._rc
        elif isinstance(rel, LogicalJoin):
            left_tables = _collect_tables(rel.left)
            right_tables = _collect_tables(rel.right)

            # For chain joins: pick rightmost of left and leftmost of right
            if left_tables and right_tables:
                lt = left_tables[-1]  # rightmost from left subtree
                rt = right_tables[0]  # leftmost from right subtree
                key = (lt, rt) if lt < rt else (rt, lt)
                if key not in seen_conditions:
                    seen_conditions.add(key)
                    edges.append(JoinEdge(
                        left_table=lt,
                        right_table=rt,
                        condition=rel.condition,
                        selectivity=rel.selectivity,
                    ))

        for child in rel.inputs:
            visit(child)

    visit(root)
    return tables, edges


def _collect_tables(rel: RelNode) -> list[str]:
    """Collect all table names from a RelNode subtree."""
    result = []
    if isinstance(rel, TableScan):
        result.append(rel.table)
    else:
        for child in rel.inputs:
            result.extend(_collect_tables(child))
    return result
