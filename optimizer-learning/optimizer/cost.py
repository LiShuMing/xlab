"""
Cost computation utilities.

Computes Cost for a RelNode by recursively summing up child costs
and adding the node's own cost contribution.
"""

from __future__ import annotations

from optimizer.model import (
    RelNode, Cost, Convention,
    PhysicalJoin, PhysicalFilter, PhysicalProject, PhysicalTableScan,
    TableScan, LogicalFilter, LogicalProject, LogicalJoin, LogicalAggregate,
)


def compute_cost(rel: RelNode, depth: int = 0) -> Cost:
    """
    Compute the total cost of a RelNode tree.
    Like Calcite's VolcanoPlanner.computeCost().
    """
    # Cost of children
    child_cost = Cost()
    for child in rel.inputs:
        child_cost += compute_cost(child, depth + 1)

    # This node's own cost
    node_cost = _node_cost(rel)

    return child_cost + node_cost


def _node_cost(rel: RelNode) -> Cost:
    """Compute the intrinsic cost of a single RelNode."""
    rc = rel.row_count()

    if isinstance(rel, PhysicalTableScan):
        # Scan: IO dominated
        return Cost(rows=rc, cpu=rc * 0.1, io=rc * 1.0)

    elif isinstance(rel, PhysicalJoin):
        if rel.impl == "HashJoin":
            # Hash join: build + probe
            left_rc = rel.left.row_count()
            right_rc = rel.right.row_count()
            build_cost = left_rc * 0.5  # build hash table
            probe_cost = right_rc * 0.3  # probe
            return Cost(rows=rc, cpu=build_cost + probe_cost, io=0.1 * rc)
        elif rel.impl == "NestedLoop":
            # Nested loop: O(M*N)
            left_rc = rel.left.row_count()
            right_rc = rel.right.row_count()
            return Cost(rows=rc, cpu=left_rc * right_rc * 0.01, io=rc * 0.5)
        else:
            return Cost(rows=rc, cpu=rc * 2.0, io=rc * 0.5)

    elif isinstance(rel, PhysicalFilter):
        return Cost(rows=rc, cpu=rc * 0.2, io=0)

    elif isinstance(rel, PhysicalProject):
        return Cost(rows=rc, cpu=rc * 0.1, io=0)

    elif isinstance(rel, TableScan):
        return Cost(rows=rc, cpu=rc * 0.1, io=rc * 1.0)

    elif isinstance(rel, LogicalFilter):
        return Cost(rows=rc, cpu=rc * 0.2, io=0)

    elif isinstance(rel, LogicalProject):
        return Cost(rows=rc, cpu=rc * 0.1, io=0)

    elif isinstance(rel, LogicalJoin):
        left_rc = rel.left.row_count()
        right_rc = rel.right.row_count()
        return Cost(rows=rc, cpu=left_rc * right_rc * 0.005, io=rc * 0.3)

    elif isinstance(rel, LogicalAggregate):
        return Cost(rows=rc, cpu=rc * 0.5, io=rc * 0.1)

    else:
        return Cost(rows=rc, cpu=rc, io=rc * 0.1)


def get_lower_bound_cost(rel: RelNode) -> Cost:
    """
    Get a lower bound cost for a RelNode.
    Like Calcite's RelMetadataQuery.getLowerBoundCost().

    This is a TIGHTER bound that enables actual pruning:
    - For Scan: at least read the table (rows * 0.5 IO)
    - For Filter: at least scan all input rows
    - For Join: at least min(left * right * selectivity) — can't be cheaper than output
    - For Aggregate: at least scan all input rows
    """
    rc = rel.row_count()

    if isinstance(rel, (TableScan, PhysicalTableScan)):
        # Must read the table — tight lower bound
        return Cost(rows=rc, cpu=rc * 0.5, io=rc * 0.5)

    elif isinstance(rel, (LogicalFilter, PhysicalFilter)):
        # Must scan all input rows
        if rel.inputs:
            return get_lower_bound_cost(rel.inputs[0])
        return Cost(rows=rc, cpu=rc * 0.5, io=rc * 0.5)

    elif isinstance(rel, (LogicalProject, PhysicalProject)):
        # Project just passes through
        if rel.inputs:
            return get_lower_bound_cost(rel.inputs[0])
        return Cost(rows=rc, cpu=rc * 0.1, io=0)

    elif isinstance(rel, (LogicalJoin, PhysicalJoin)):
        # Lower bound: at least the cost of producing the output rows
        # Plus at least one child's lower bound
        if len(rel.inputs) >= 2:
            lb_left = get_lower_bound_cost(rel.inputs[0])
            lb_right = get_lower_bound_cost(rel.inputs[1])
            # Must at least scan one side fully
            min_child = lb_left if lb_left < lb_right else lb_right
            return Cost(rows=rc, cpu=rc * 0.5, io=rc * 0.5) + min_child
        return Cost(rows=rc, cpu=rc * 0.5, io=rc * 0.5)

    elif isinstance(rel, LogicalAggregate):
        # Must scan all input rows
        if rel.inputs:
            return get_lower_bound_cost(rel.inputs[0])
        return Cost(rows=rc, cpu=rc * 0.5, io=rc * 0.1)

    else:
        return Cost(rows=rc, cpu=rc * 0.5, io=rc * 0.3)
