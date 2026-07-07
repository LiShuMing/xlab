"""
SQL Parser: sqlglot AST → RelNode tree.

Converts parsed SQL into a logical RelNode tree that can be fed
into the Volcano or Cascades optimizer.

Supported SQL features:
  - SELECT with column expressions
  - FROM with single/multiple tables
  - FROM subqueries (derived tables / inline views)
  - INNER/LEFT/RIGHT/FULL OUTER JOIN with ON clause
  - WHERE with simple conditions + subqueries (EXISTS, IN, comparison)
  - GROUP BY / HAVING with aggregate functions
  - ORDER BY, LIMIT
  - CASE expressions, SUBSTRING, EXTRACT functions
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlglot
from sqlglot import exp

from optimizer.model import (
    RelNode, TableScan, LogicalFilter, LogicalProject,
    LogicalJoin, LogicalAggregate, Convention, TraitSet,
)
from optimizer.catalog import Catalog


if TYPE_CHECKING:
    pass


class SqlToRelConverter:
    """
    Converts sqlglot AST to RelNode tree.
    Like Calcite's SqlToRelConverter.
    """

    def __init__(self, catalog: Catalog):
        self.catalog = catalog
        self._table_aliases: dict[str, str] = {}  # alias → table_name
        self._subquery_counter = 0

    def convert(self, sql: str) -> RelNode:
        """Parse SQL string and return RelNode tree."""
        stmt = sqlglot.parse_one(sql, dialect="mysql")
        if not isinstance(stmt, exp.Select):
            raise ValueError(f"Only SELECT statements are supported, got {type(stmt)}")
        return self._visit_select(stmt)

    def _visit_select(self, stmt: exp.Select) -> RelNode:
        """Convert a SELECT statement into a RelNode tree."""
        # Step 1: Build FROM clause (base tables + joins + derived tables)
        from_clause = stmt.args.get("from_") or stmt.args.get("from")
        if not from_clause:
            raise ValueError("SELECT must have a FROM clause")

        root = self._visit_from(from_clause)

        # Also check for joins at the Select level (comma-separated tables: FROM a, b)
        select_joins = stmt.args.get("joins", [])
        for join in select_joins:
            root = self._visit_join(root, join)

        # Step 2: Apply WHERE filter (including subqueries)
        where = stmt.args.get("where")
        if where:
            root = self._visit_where(root, where)

        # Step 3: Apply GROUP BY / aggregates
        group = stmt.args.get("group")
        select_exprs = stmt.expressions  # SELECT columns

        has_agg = self._has_aggregates(select_exprs)
        if group or has_agg:
            root = self._visit_aggregate(root, select_exprs, group)

        # Step 4: Apply HAVING
        having = stmt.args.get("having")
        if having:
            root = self._visit_where(root, having)

        # Step 5: Apply SELECT projection (if no aggregates, or for non-agg columns)
        if not has_agg and not group:
            root = self._visit_select_exprs(root, select_exprs)

        # Step 6: Apply ORDER BY
        order = stmt.args.get("order")
        if order:
            root = self._visit_order(root, order)

        # Step 7: Apply LIMIT
        limit = stmt.args.get("limit")
        if limit:
            root = self._visit_limit(root, limit)

        return root

    def _visit_from(self, from_clause: exp.From) -> RelNode:
        """Convert FROM clause into RelNode tree (tables + joins)."""
        this = from_clause.this
        root = self._visit_relation(this)

        # Process JOINs in the FROM clause
        for join in from_clause.args.get("joins", []):
            root = self._visit_join(root, join)

        return root

    def _visit_relation(self, node: exp.Expression) -> RelNode:
        """
        Visit a FROM relation — can be a Table or a Subquery (derived table).
        """
        if isinstance(node, exp.Table):
            return self._visit_table(node)
        elif isinstance(node, exp.Subquery):
            return self._visit_subquery(node)
        else:
            raise ValueError(f"Unsupported FROM relation type: {type(node)}")

    def _visit_table(self, table: exp.Table) -> RelNode:
        """Convert a table reference to TableScan."""
        table_name = table.name.lower()
        alias = table.alias or table_name

        # Register alias mapping
        self._table_aliases[alias.lower()] = table_name

        # Look up in catalog
        meta = self.catalog.get_table(table_name)
        if meta is None:
            raise ValueError(f"Table '{table_name}' not found in catalog. "
                             f"Available: {', '.join(self.catalog.tables.keys())}")

        return TableScan(table=table_name, row_count=meta.row_count)

    def _visit_subquery(self, subquery: exp.Subquery) -> RelNode:
        """
        Convert a subquery (derived table) to a RelNode tree.
        FROM (SELECT ...) AS alias
        """
        self._subquery_counter += 1
        alias = subquery.alias or f"sub{self._subquery_counter}"

        # Push current alias context, process subquery
        old_aliases = dict(self._table_aliases)
        self._table_aliases = {}

        inner_select = subquery.this
        if isinstance(inner_select, exp.Select):
            inner_rel = self._visit_select(inner_select)
        else:
            raise ValueError(f"Unsupported subquery type: {type(inner_select)}")

        # Pop alias context
        self._table_aliases = old_aliases

        return inner_rel

    def _visit_join(self, left_rel: RelNode, join: exp.Join) -> RelNode:
        """Convert a JOIN clause to LogicalJoin."""
        right_rel = self._visit_relation(join.this)

        # Extract join condition
        on = join.args.get("on")
        if on:
            condition = str(on.this)
        else:
            # Check for USING clause
            using = join.args.get("using")
            if using:
                cols = ", ".join(str(c) for c in using)
                condition = f"USING ({cols})"
            else:
                condition = "TRUE"

        # Determine join type
        side = join.args.get("side")
        if side:
            side_val = side.value.lower() if hasattr(side, 'value') else str(side).lower()
            if side_val == 'left':
                join_type = 'left'
            elif side_val == 'right':
                join_type = 'right'
            elif side_val == 'full':
                join_type = 'full'
            else:
                join_type = 'inner'
        else:
            join_type = 'inner'

        # Selectivity estimation based on join type
        selectivity_map = {
            'inner': 0.01,
            'left': 0.1,
            'right': 0.1,
            'full': 0.5,
        }

        return LogicalJoin(
            left=left_rel, right=right_rel,
            condition=condition,
            join_type=join_type,
            selectivity=selectivity_map.get(join_type, 0.01),
        )

    def _visit_where(self, input_rel: RelNode, where: exp.Where | exp.Having) -> RelNode:
        """Convert WHERE/HAVING clause to LogicalFilter."""
        condition = where.this
        selectivity = self._estimate_selectivity(condition, input_rel)
        condition_str = self._format_condition(condition)
        return LogicalFilter(
            input=input_rel,
            condition=condition_str,
            selectivity=selectivity,
        )

    def _visit_select_exprs(self, input_rel: RelNode,
                             exprs: list[exp.Expression]) -> RelNode:
        """Convert SELECT column list to LogicalProject."""
        columns = []
        for e in exprs:
            if isinstance(e, exp.Alias):
                columns.append(e.alias)
            elif isinstance(e, exp.Column):
                col_name = e.name.lower()
                table = e.table.lower() if e.table else ""
                columns.append(f"{table}.{col_name}" if table else col_name)
            elif isinstance(e, exp.Star):
                columns.append("*")
            else:
                columns.append(str(e))
        return LogicalProject(input=input_rel, columns=columns)

    def _visit_aggregate(self, input_rel: RelNode,
                          select_exprs: list[exp.Expression],
                          group: exp.Group | None) -> RelNode:
        """Convert GROUP BY + aggregates to LogicalAggregate."""
        group_keys = []
        agg_funcs = []

        if group:
            for e in group.expressions:
                if isinstance(e, exp.Column):
                    col_name = e.name.lower()
                    table = e.table.lower() if e.table else ""
                    group_keys.append(f"{table}.{col_name}" if table else col_name)
                else:
                    group_keys.append(str(e))

        for e in select_exprs:
            if self._is_aggregate(e):
                agg_funcs.append(self._format_agg_expr(e))

        return LogicalAggregate(
            input=input_rel,
            group_keys=group_keys,
            agg_funcs=agg_funcs,
        )

    def _visit_order(self, input_rel: RelNode, order: exp.Order) -> RelNode:
        """Convert ORDER BY (simplified — just returns input)."""
        return input_rel

    def _visit_limit(self, input_rel: RelNode, limit: exp.Limit) -> RelNode:
        """Convert LIMIT (simplified — just returns input)."""
        return input_rel

    # ── Helpers ──

    def _has_aggregates(self, exprs: list[exp.Expression]) -> bool:
        return any(self._is_aggregate(e) for e in exprs)

    def _is_aggregate(self, e: exp.Expression) -> bool:
        return isinstance(e, (exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max)) or \
               (isinstance(e, exp.Alias) and
                isinstance(e.this, (exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max)))

    def _format_agg_expr(self, e: exp.Expression) -> str:
        if isinstance(e, exp.Alias):
            return str(e.this)
        return str(e)

    def _format_condition(self, cond: exp.Expression) -> str:
        """Format a condition expression into a readable string."""
        if isinstance(cond, exp.Exists):
            return f"EXISTS ({str(cond.this)[:60]}...)"
        elif isinstance(cond, exp.In):
            return str(cond)[:80]
        elif isinstance(cond, exp.Not):
            inner = cond.this
            if isinstance(inner, exp.Exists):
                return f"NOT EXISTS ({str(inner.this)[:60]}...)"
            return f"NOT ({str(inner)[:80]})"
        return str(cond)

    def _estimate_selectivity(self, condition: exp.Expression,
                               rel: RelNode) -> float:
        """
        Estimate the selectivity of a WHERE condition.
        Handles subqueries (EXISTS, IN, comparison with subquery).
        """
        if isinstance(condition, exp.Exists):
            # EXISTS typically filters to 10-30% of rows
            return 0.2

        elif isinstance(condition, exp.Not):
            inner = condition.this
            if isinstance(inner, exp.Exists):
                return 0.8  # NOT EXISTS keeps most rows

        elif isinstance(condition, exp.In):
            # IN with values: 1/NDV * count_of_values
            if isinstance(condition.expression, exp.Tuple):
                count = len(condition.expression.expressions)
                return min(count * 0.01, 0.5)
            # IN with subquery
            if isinstance(condition.expression, exp.Select):
                return 0.1

        elif isinstance(condition, exp.EQ):
            left = condition.this
            if isinstance(left, exp.Column):
                table_name = self._resolve_table(left)
                col_name = left.name.lower()
                meta = self.catalog.get_table(table_name) if table_name else None
                if meta:
                    ndv = meta.get_column(col_name).ndv
                    return max(1.0 / ndv, 0.0001)
            return 0.01

        elif isinstance(condition, (exp.GT, exp.LT, exp.GTE, exp.LTE)):
            return 0.33

        elif isinstance(condition, exp.Between):
            return 0.05

        elif isinstance(condition, exp.Like):
            return 0.1

        elif isinstance(condition, exp.And):
            left_sel = self._estimate_selectivity(condition.this, rel)
            right_sel = self._estimate_selectivity(condition.expression, rel)
            return left_sel * right_sel

        elif isinstance(condition, exp.Or):
            left_sel = self._estimate_selectivity(condition.this, rel)
            right_sel = self._estimate_selectivity(condition.expression, rel)
            return min(left_sel + right_sel, 1.0)

        elif isinstance(condition, exp.Is):
            return 0.01

        elif isinstance(condition, exp.Select):
            # Comparison with scalar subquery
            return 0.1

        return 0.1  # Default fallback

    def _resolve_table(self, col: exp.Column) -> str:
        """Resolve a column's table name from alias or direct reference."""
        if col.table:
            alias = col.table.lower()
            return self._table_aliases.get(alias, alias)
        return self._find_table_from_rel(col.name.lower())

    def _find_table_from_rel(self, col_name: str) -> str:
        """Try to find which table a column belongs to."""
        for table_name, meta in self.catalog.tables.items():
            if col_name in meta.columns:
                return table_name
        return ""


def parse_sql(sql: str, catalog: Catalog) -> RelNode:
    """
    Convenience function: parse SQL and return RelNode tree.

    Usage:
        catalog = create_tpch_sf1_catalog()
        tree = parse_sql("SELECT * FROM lineitem WHERE l_quantity > 10", catalog)
    """
    converter = SqlToRelConverter(catalog)
    return converter.convert(sql)
