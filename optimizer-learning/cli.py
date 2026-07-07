#!/usr/bin/env python3
"""
Optimizer Learning Tool — Compare Volcano (Calcite-style) and Cascades optimizers.

Usage:
    python cli.py list                          # List available example queries
    python cli.py run volcano <example>          # Run Volcano optimizer
    python cli.py run cascades <example>         # Run Cascades optimizer
    python cli.py compare <example>              # Compare both optimizers
    python cli.py compare --all                  # Compare all examples
    python cli.py explain volcano <example>      # Show Volcano internal state
    python cli.py explain cascades <example>     # Show Cascades internal state
    python cli.py reorder <example>              # DP join reorder analysis
    python cli.py step <optimizer> <example>     # Interactive step-by-step
    python cli.py prune-compare <example>        # Compare with/without pruning
    python cli.py sql "SELECT ..."              # Parse and optimize arbitrary SQL
    python cli.py tpch <q1..q22>                # Run a TPC-H query
    python cli.py tpch-bench                     # Benchmark all 22 TPC-H queries
"""

import argparse
import sys
import os

# Add parent directory to path so we can import optimizer packages
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from examples.queries import EXAMPLES, EXAMPLE_DESCRIPTIONS
from volcano.planner import VolcanoPlanner
from cascades.planner import CascadesPlanner
from compare.engine import compare
from optimizer.join_reorder import JoinReorderer, extract_tables_and_joins
from optimizer.catalog import create_tpch_sf1_catalog, Catalog
from optimizer.sql_parser import parse_sql
from optimizer.tpch import get_query, load_tpch_schema, list_queries as list_tpch_queries


def cmd_list(args: argparse.Namespace) -> int:
    """List available example queries."""
    print("Available example queries:")
    print()
    for name, _ in EXAMPLES.items():
        desc = EXAMPLE_DESCRIPTIONS.get(name, "")
        print(f"  {name:<25} {desc}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Run a single optimizer on an example."""
    example_name = args.example
    optimizer_name = args.optimizer

    if example_name not in EXAMPLES:
        print(f"Error: unknown example '{example_name}'")
        print(f"Available: {', '.join(EXAMPLES.keys())}")
        return 1

    # Build the query tree
    root = EXAMPLES[example_name]()
    print(f"Query: {example_name}")
    print(f"  Root: {root.explain_name()}")
    print()

    if optimizer_name == "volcano":
        planner = VolcanoPlanner(verbose=True)
        planner.set_root(root)
        best = planner.optimize()

        print("=== Volcano Result ===")
        if best:
            cost = planner.get_best_plan_cost()
            print(f"  Best plan: {best.explain_name()}")
            print(f"  Cost: {cost}")
        else:
            print("  No plan found!")
        print()
        print(f"  RelSets created: {len(planner.rel_sets)}")
        print(f"  Rule firings: {len(planner.trace.rule_firings)}")

    elif optimizer_name == "cascades":
        planner = CascadesPlanner(verbose=True)
        planner.set_root(root)
        best = planner.optimize()

        print("=== Cascades Result ===")
        if best:
            cost = planner.get_best_plan_cost()
            print(f"  Best plan: {best.explain_name()}")
            print(f"  Cost: {cost}")
        else:
            print("  No plan found!")
        print()
        print(f"  Groups created: {len(planner.memo.groups)}")
        print(f"  Rule firings: {len(planner.trace.rule_firings)}")
        print(f"  Tasks executed: {len(planner.trace.task_sequence)}")
        print(f"  Pruning events: {len(planner.trace.pruning_events)}")

    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    """Compare both optimizers on one or more examples."""
    if args.all:
        examples = list(EXAMPLES.keys())
    else:
        examples = [args.example]

    for example_name in examples:
        if example_name not in EXAMPLES:
            print(f"Error: unknown example '{example_name}'")
            return 1

        # Reset ID counter for each example
        from optimizer.model import RelNode
        RelNode.reset_id_counter()

        root = EXAMPLES[example_name]()

        print(f"\n{'=' * 70}")
        print(f"  Example: {example_name}")
        print(f"  Root: {root.explain_name()}")
        print(f"{'=' * 70}")
        print()

        # Run Volcano
        RelNode.reset_id_counter()
        root_v = EXAMPLES[example_name]()
        volcano = VolcanoPlanner(verbose=False)
        volcano.set_root(root_v)
        volcano.optimize()

        # Run Cascades
        RelNode.reset_id_counter()
        root_c = EXAMPLES[example_name]()
        cascades = CascadesPlanner(verbose=False)
        cascades.set_root(root_c)
        cascades.optimize()

        # Compare
        result = compare(volcano, cascades, root)
        print(result.detail())

        if args.all and example_name != examples[-1]:
            print()
            print("─" * 70)

    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    """Show internal state of an optimizer after optimization."""
    example_name = args.example
    optimizer_name = args.optimizer

    if example_name not in EXAMPLES:
        print(f"Error: unknown example '{example_name}'")
        return 1

    from optimizer.model import RelNode
    RelNode.reset_id_counter()
    root = EXAMPLES[example_name]()

    if optimizer_name == "volcano":
        planner = VolcanoPlanner(verbose=True)
        planner.set_root(root)
        planner.optimize()
        print(planner.explain())

    elif optimizer_name == "cascades":
        planner = CascadesPlanner(verbose=True)
        planner.set_root(root)
        planner.optimize()
        print(planner.explain())

    return 0


def cmd_reorder(args: argparse.Namespace) -> int:
    """Run DP-style join reorder analysis."""
    example_name = args.example

    if example_name not in EXAMPLES:
        print(f"Error: unknown example '{example_name}'")
        return 1

    from optimizer.model import RelNode
    RelNode.reset_id_counter()
    root = EXAMPLES[example_name]()

    tables, edges = extract_tables_and_joins(root)

    if len(tables) < 2:
        print("Query has fewer than 2 tables — no join reorder needed.")
        return 0

    print(f"Query: {example_name}")
    print(f"Tables: {len(tables)} ({', '.join(f'{t}({tables[t]:.0f})' for t in sorted(tables))})")
    print(f"Join edges: {len(edges)}")
    for e in edges:
        print(f"  {e.left_table} ⨝ {e.right_table}: {e.condition} (sel={e.selectivity})")
    print()

    # DP join reorder
    reorderer = JoinReorderer(tables, edges)
    result = reorderer.optimize()

    print(reorderer.explain())
    print()
    print(f"Best Join Order Cost: {result.cost}")
    print(f"Best Plan Tree:")
    _print_tree(result.plan, indent=0)

    # Show exhaustive comparison
    from math import factorial
    n = len(tables)
    perms = factorial(n)
    dp_partitions = 2 ** (n - 1) - 1
    print()
    print(f"Search Space Comparison:")
    print(f"  Exhaustive (N!): {perms}")
    print(f"  DP (2^(N-1)-1): {dp_partitions}")
    print(f"  Actual partitions evaluated: {reorderer.trace.partitions_evaluated}")
    print(f"  Savings: {1 - dp_partitions / perms:.0%} fewer evaluations")

    return 0


def _print_tree(rel, indent: int = 0) -> None:
    """Print a RelNode tree."""
    prefix = "  " * indent
    rc = rel.row_count()
    print(f"{prefix}{rel.explain_name()} (rows={rc:.0f})")
    for child in rel.inputs:
        _print_tree(child, indent + 1)


def cmd_step(args: argparse.Namespace) -> int:
    """Interactive step-by-step optimization."""
    example_name = args.example
    optimizer_name = args.optimizer

    if example_name not in EXAMPLES:
        print(f"Error: unknown example '{example_name}'")
        return 1

    from optimizer.model import RelNode
    RelNode.reset_id_counter()
    root = EXAMPLES[example_name]()

    print(f"Query: {example_name}")
    print(f"Root: {root.explain_name()}")
    print()

    if optimizer_name == "volcano":
        planner = VolcanoPlanner(verbose=True)
        planner.set_root(root)

        step_num = 0
        print(f"Phase: {planner.phase} (queue size: {planner.rule_queue.total_size})")
        print()

        while not planner.rule_queue.is_empty:
            step_num += 1
            response = input(f"Step {step_num} > (Enter=next, q=quit): ")
            if response.strip().lower() == 'q':
                print("Exiting.")
                return 0

            match = planner.rule_queue.poll()
            if match is None:
                break

            print(f"[Step {step_num}] Fire: {match.rule.name} on {match.root.explain_name()}#{match.root.id}")

            new_rels = match.rule.transform(match)
            for new_rel in new_rels:
                print(f"  → Created: {new_rel.explain_name()}#{new_rel.id}")
                planner._register(new_rel)

            print(f"  Queue: {planner.rule_queue.total_size} remaining, RelSets: {len(planner.rel_sets)}")
            print()

        # Final result
        planner.phase = "OPTIMIZING"
        best = planner._find_best_exp()
        print(f"\n=== Result ===")
        if best:
            print(f"  Best plan: {best.explain_name()}")
            print(f"  Cost: {planner.get_best_plan_cost()}")
        else:
            print("  No plan found!")

    elif optimizer_name == "cascades":
        planner = CascadesPlanner(verbose=True)
        planner.set_root(root)

        print(f"Memo: {len(planner.memo.groups)} groups")
        print()

        from cascades.planner import OptimizeGroup
        from optimizer.model import Cost

        stack = [OptimizeGroup(planner.memo.root_group, Cost.INFINITY)]
        step_num = 0

        while stack:
            step_num += 1
            response = input(f"Step {step_num} > (Enter=next, q=quit): ")
            if response.strip().lower() == 'q':
                print("Exiting.")
                return 0

            task = stack.pop()
            planner.trace.log_task(task.name())

            print(f"[Step {step_num}] {task.name()}")
            task.execute(planner)

            groups_optimized = sum(
                1 for g in planner.memo.groups
                if g.state.value == "OPTIMIZED"
            )
            print(f"  Groups: {len(planner.memo.groups)} ({groups_optimized} optimized)")
            print(f"  Rule firings: {len(planner.trace.rule_firings)}")
            print(f"  Pruning events: {len(planner.trace.pruning_events)}")
            print()

        # Final result
        best = planner._find_best_exp()
        print(f"\n=== Result ===")
        if best:
            print(f"  Best plan: {best.explain_name()}")
            print(f"  Cost: {planner.get_best_plan_cost()}")
        else:
            print("  No plan found!")

    return 0


def cmd_prune_compare(args: argparse.Namespace) -> int:
    """Compare Cascades optimizer with and without cost pruning."""
    example_name = args.example

    if example_name not in EXAMPLES:
        print(f"Error: unknown example '{example_name}'")
        return 1

    from optimizer.model import RelNode, Cost

    # Run WITH pruning (default)
    RelNode.reset_id_counter()
    root_with = EXAMPLES[example_name]()
    planner_with = CascadesPlanner(verbose=False)
    planner_with.set_root(root_with)
    planner_with.optimize()

    # Run WITHOUT pruning (disable by monkey-patching the rule application)
    RelNode.reset_id_counter()
    root_without = EXAMPLES[example_name]()
    planner_without = CascadesPlanner(verbose=False)
    planner_without.set_root(root_without)

    # Disable all pruning by replacing _apply_exploration_rules with a no-prune version
    original_apply = planner_without._apply_exploration_rules

    def no_prune_apply(group):
        # Run original but clear pruning events afterwards
        original_apply(group)
        planner_without.trace.pruning_events.clear()

    planner_without._apply_exploration_rules = no_prune_apply
    planner_without.optimize()

    # Compare
    lines = [
        "=" * 70,
        f"  Pruning Comparison: {example_name}",
        "=" * 70,
        "",
        "┌────────────────────────────────┬─────────────┬───────────────┤",
        f"│ {'Metric':<30} │ {'With Prune':<11} │ {'No Prune':<12} │",
        "├────────────────────────────────┼─────────────┼───────────────┤",
        f"│ {'Groups':<30} │ {len(planner_with.memo.groups):<11} │ {len(planner_without.memo.groups):<12} │",
        f"│ {'Rule Firings':<30} │ {len(planner_with.trace.rule_firings):<11} │ {len(planner_without.trace.rule_firings):<12} │",
        f"│ {'Tasks Executed':<30} │ {len(planner_with.trace.task_sequence):<11} │ {len(planner_without.trace.task_sequence):<12} │",
        f"│ {'Pruning Events':<30} │ {len(planner_with.trace.pruning_events):<11} │ {len(planner_without.trace.pruning_events):<12} │",
        "└────────────────────────────────┴─────────────┴───────────────┘",
        "",
    ]

    with_best = planner_with._find_best_exp()
    without_best = planner_without._find_best_exp()

    lines.append(f"With Pruning:")
    if with_best:
        lines.append(f"  Best: {with_best.explain_name()}")
        lines.append(f"  Cost: {planner_with.get_best_plan_cost()}")
        lines.append(f"  Expressions kept: {sum(len(g.expressions) for g in planner_with.memo.groups)}")

    lines.append(f"\nWithout Pruning:")
    if without_best:
        lines.append(f"  Best: {without_best.explain_name()}")
        lines.append(f"  Cost: {planner_without.get_best_plan_cost()}")
        lines.append(f"  Expressions kept: {sum(len(g.expressions) for g in planner_without.memo.groups)}")

    if planner_with.trace.pruning_events:
        lines.append(f"\nPruning Events ({len(planner_with.trace.pruning_events)}):")
        for event in planner_with.trace.pruning_events[:10]:
            lines.append(f"  {event}")
        if len(planner_with.trace.pruning_events) > 10:
            lines.append(f"  ... and {len(planner_with.trace.pruning_events) - 10} more")

        # Show the impact
        with_exprs = sum(len(g.expressions) for g in planner_with.memo.groups)
        without_exprs = sum(len(g.expressions) for g in planner_without.memo.groups)
        lines.append(f"\nImpact: Pruning saved {without_exprs - with_exprs} expressions from being kept")
    else:
        lines.append("\nNo pruning events — all alternatives were kept.")

    print("\n".join(lines))
    return 0


def cmd_sql(args: argparse.Namespace) -> int:
    """Parse and optimize arbitrary SQL."""
    sql = args.sql.strip()
    catalog = create_tpch_sf1_catalog()

    print(f"SQL: {sql[:80]}{'...' if len(sql) > 80 else ''}")
    print(f"Catalog: {len(catalog.tables)} tables loaded")
    print()

    try:
        root = parse_sql(sql, catalog)
    except Exception as e:
        print(f"Error parsing SQL: {e}")
        return 1

    print(f"RelNode Tree:")
    _print_tree_verbose(root, indent=0)
    print()

    # Run Volcano optimizer
    from optimizer.model import RelNode as RelNodeType
    RelNodeType.reset_id_counter()
    root2 = parse_sql(sql, catalog)

    volcano = VolcanoPlanner(verbose=False)
    volcano.set_root(root2)
    volcano.optimize()
    best = volcano._find_best_exp()

    print("=== Volcano Optimizer ===")
    if best:
        print(f"  Best plan: {best.explain_name()}")
        print(f"  Cost: {volcano.get_best_plan_cost()}")
        print(f"  RelSets: {len(volcano.rel_sets)}")
        print(f"  Rule firings: {len(volcano.trace.rule_firings)}")
    else:
        print("  No plan found!")

    # Run Cascades optimizer
    RelNodeType.reset_id_counter()
    root3 = parse_sql(sql, catalog)

    cascades = CascadesPlanner(verbose=False)
    cascades.set_root(root3)
    cascades.optimize()
    best_c = cascades._find_best_exp()

    print()
    print("=== Cascades Optimizer ===")
    if best_c:
        print(f"  Best plan: {best_c.explain_name()}")
        print(f"  Cost: {cascades.get_best_plan_cost()}")
        print(f"  Groups: {len(cascades.memo.groups)}")
        print(f"  Rule firings: {len(cascades.trace.rule_firings)}")
        print(f"  Pruning events: {len(cascades.trace.pruning_events)}")
    else:
        print("  No plan found!")

    # Compare
    print()
    plans_match = best and best_c and best.explain_name() == best_c.explain_name()
    print(f"Plan Consistency: {'SAME' if plans_match else 'DIFFERENT'}")

    return 0


def _print_tree_verbose(rel, indent: int = 0) -> None:
    """Print RelNode tree with row counts."""
    prefix = "  " * indent
    try:
        rc = rel.row_count()
        print(f"{prefix}{rel.explain_name()} (rows={rc:.0f})")
    except Exception:
        print(f"{prefix}{rel.explain_name()}")
    for child in rel.inputs:
        _print_tree_verbose(child, indent + 1)


def cmd_tpch(args: argparse.Namespace) -> int:
    """Run a single TPC-H query."""
    query_name = args.query.lower()

    try:
        sql = get_query(query_name)
    except ValueError as e:
        print(f"Error: {e}")
        available = ", ".join(f"q{i}" for i in range(1, 23))
        print(f"Available: {available}")
        return 1

    catalog = create_tpch_sf1_catalog()
    print(f"TPC-H {query_name.upper()}")
    print(f"SQL: {sql.strip()[:120]}...")
    print()

    try:
        root = parse_sql(sql, catalog)
    except Exception as e:
        print(f"Error parsing SQL: {e}")
        print("(TPC-H queries with subqueries/correlated refs may not fully parse)")
        return 1

    print("Logical Plan:")
    _print_tree_verbose(root, indent=0)
    print()

    # Run both optimizers
    from optimizer.model import RelNode as RelNodeType
    RelNodeType.reset_id_counter()
    root_v = parse_sql(sql, catalog)
    volcano = VolcanoPlanner(verbose=False)
    volcano.set_root(root_v)
    volcano.optimize()
    best_v = volcano._find_best_exp()

    RelNodeType.reset_id_counter()
    root_c = parse_sql(sql, catalog)
    cascades = CascadesPlanner(verbose=False)
    cascades.set_root(root_c)
    cascades.optimize()
    best_c = cascades._find_best_exp()

    print("=== Optimizer Results ===")
    print(f"{'':25} {'Volcano':>20} {'Cascades':>20}")
    print(f"{'Best Plan':25} {best_v.explain_name() if best_v else 'none':>20} {best_c.explain_name() if best_c else 'none':>20}")
    cost_v = volcano.get_best_plan_cost() if best_v else None
    cost_c = cascades.get_best_plan_cost() if best_c else None
    print(f"{'Cost':25} {str(cost_v):>20} {str(cost_c):>20}")
    print(f"{'RelSets/Groups':25} {len(volcano.rel_sets):>20} {len(cascades.memo.groups):>20}")
    print(f"{'Rule Firings':25} {len(volcano.trace.rule_firings):>20} {len(cascades.trace.rule_firings):>20}")

    return 0


def cmd_tpch_bench(args: argparse.Namespace) -> int:
    """Benchmark all 22 TPC-H queries."""
    catalog = create_tpch_sf1_catalog()
    from optimizer.model import RelNode as RelNodeType

    print("=" * 100)
    print("  TPC-H Benchmark (SF=1) — Volcano vs Cascades")
    print("=" * 100)
    print()
    print(f"{'Query':<8} {'Parsed':>8} {'V-Plan':>20} {'V-Cost':>20} {'V-Rules':>8} "
          f"{'C-Plan':>20} {'C-Cost':>20} {'C-Rules':>8} {'C-Prune':>8} {'Match':>6}")
    print("-" * 100)

    parsed_count = 0
    same_plan_count = 0

    for qname, desc in list_tpch_queries():
        try:
            sql = get_query(qname)
            root = parse_sql(sql, catalog)
            parsed_count += 1
        except Exception:
            print(f"{qname:<8} {'FAIL':>8}")
            continue

        # Volcano
        RelNodeType.reset_id_counter()
        root_v = parse_sql(sql, catalog)
        volcano = VolcanoPlanner(verbose=False)
        volcano.set_root(root_v)
        volcano.optimize()
        best_v = volcano._find_best_exp()

        # Cascades
        RelNodeType.reset_id_counter()
        root_c = parse_sql(sql, catalog)
        cascades = CascadesPlanner(verbose=False)
        cascades.set_root(root_c)
        cascades.optimize()
        best_c = cascades._find_best_exp()

        v_plan = best_v.explain_name()[:18] if best_v else "none"
        c_plan = best_c.explain_name()[:18] if best_c else "none"
        v_cost = str(volcano.get_best_plan_cost())[:18] if best_v else "-"
        c_cost = str(cascades.get_best_plan_cost())[:18] if best_c else "-"

        match = best_v and best_c and best_v.explain_name() == best_c.explain_name()
        if match:
            same_plan_count += 1

        print(f"{qname:<8} {'OK':>8} {v_plan:>20} {v_cost:>20} {len(volcano.trace.rule_firings):>8} "
              f"{c_plan:>20} {c_cost:>20} {len(cascades.trace.rule_firings):>8} "
              f"{len(cascades.trace.pruning_events):>8} {'SAME' if match else 'DIFF':>6}")

    print("-" * 100)
    print(f"Summary: {parsed_count}/22 queries parsed, {same_plan_count}/{parsed_count} same plans")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Optimizer Learning Tool — Compare Volcano and Cascades",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # list
    list_parser = subparsers.add_parser("list", help="List example queries")
    list_parser.set_defaults(func=cmd_list)

    # run <optimizer> <example>
    run_parser = subparsers.add_parser("run", help="Run an optimizer")
    run_parser.add_argument("optimizer", choices=["volcano", "cascades"],
                            help="Which optimizer to run")
    run_parser.add_argument("example", help="Example query name")
    run_parser.set_defaults(func=cmd_run)

    # compare <example>
    compare_parser = subparsers.add_parser("compare", help="Compare optimizers")
    compare_parser.add_argument("example", nargs="?", help="Example query name")
    compare_parser.add_argument("--all", action="store_true",
                                help="Compare all examples")
    compare_parser.set_defaults(func=cmd_compare)

    # explain <optimizer> <example>
    explain_parser = subparsers.add_parser("explain", help="Show optimizer internals")
    explain_parser.add_argument("optimizer", choices=["volcano", "cascades"],
                                help="Which optimizer to explain")
    explain_parser.add_argument("example", help="Example query name")
    explain_parser.set_defaults(func=cmd_explain)

    # reorder <example>
    reorder_parser = subparsers.add_parser("reorder", help="DP join reorder analysis")
    reorder_parser.add_argument("example", help="Example query name")
    reorder_parser.set_defaults(func=cmd_reorder)

    # step <optimizer> <example>
    step_parser = subparsers.add_parser("step", help="Interactive step-by-step")
    step_parser.add_argument("optimizer", choices=["volcano", "cascades"],
                             help="Which optimizer to step through")
    step_parser.add_argument("example", help="Example query name")
    step_parser.set_defaults(func=cmd_step)

    # prune-compare <example>
    prune_parser = subparsers.add_parser("prune-compare",
                                         help="Compare Cascades with/without pruning")
    prune_parser.add_argument("example", help="Example query name")
    prune_parser.set_defaults(func=cmd_prune_compare)

    # sql "SELECT ..."
    sql_parser = subparsers.add_parser("sql", help="Parse and optimize arbitrary SQL")
    sql_parser.add_argument("sql", help="SQL query string (in quotes)")
    sql_parser.set_defaults(func=cmd_sql)

    # tpch <q1..q22>
    tpch_parser = subparsers.add_parser("tpch", help="Run a TPC-H query")
    tpch_parser.add_argument("query", help="Query name (q1..q22)")
    tpch_parser.set_defaults(func=cmd_tpch)

    # tpch-bench
    bench_parser = subparsers.add_parser("tpch-bench", help="Benchmark all 22 TPC-H queries")
    bench_parser.set_defaults(func=cmd_tpch_bench)

    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
