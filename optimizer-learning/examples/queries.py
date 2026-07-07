"""
Example query cases for optimizer comparison.

Each function builds a RelNode tree representing a SQL query.
These examples demonstrate:
  - JOIN reordering (two-table join)
  - Filter pushdown (three-table join with filter)
  - Aggregation (GROUP BY with aggregate functions)
"""

from optimizer.model import (
    RelNode, TableScan, LogicalFilter, LogicalProject,
    LogicalJoin, LogicalAggregate, Convention, TraitSet, RelNode
)


def two_table_join() -> RelNode:
    """
    SQL: SELECT * FROM orders o JOIN customer c ON o.cust_id = c.id

    Demonstrates:
      - Join commutativity (orders⨝customer vs customer⨝orders)
      - HashJoin vs NestedLoop join implementation choices
    """
    RelNode.reset_id_counter()

    orders = TableScan("orders", row_count=10000.0)
    customer = TableScan("customer", row_count=1000.0)

    join = LogicalJoin(
        left=orders, right=customer,
        condition="o.cust_id = c.id",
        selectivity=0.01,
    )

    return join


def three_table_join() -> RelNode:
    """
    SQL: SELECT *
         FROM orders o
         JOIN customer c ON o.cust_id = c.id
         JOIN product p ON o.prod_id = p.id
         WHERE c.country = 'US'

    Demonstrates:
      - Filter pushdown (country='US' should push into customer scan)
      - Join ordering with 3 tables (3! = 6 permutations, reduced by filter)
      - How Volcano vs Cascades handle search space differently
    """
    RelNode.reset_id_counter()

    orders = TableScan("orders", row_count=10000.0)
    customer = TableScan("customer", row_count=1000.0)
    product = TableScan("product", row_count=500.0)

    # o ⨝ c
    join1 = LogicalJoin(
        left=orders, right=customer,
        condition="o.cust_id = c.id",
        selectivity=0.01,
    )

    # (o ⨝ c) ⨝ p
    join2 = LogicalJoin(
        left=join1, right=product,
        condition="o.prod_id = p.id",
        selectivity=0.005,
    )

    # Filter on customer
    filter_rel = LogicalFilter(
        input=join2,
        condition="c.country = 'US'",
        selectivity=0.2,
    )

    return filter_rel


def join_with_filter() -> RelNode:
    """
    SQL: SELECT o.*, c.name
         FROM orders o
         JOIN customer c ON o.cust_id = c.id
         WHERE o.amount > 100

    Demonstrates:
      - Filter on join result (not pushable to single table)
      - Filter + Join → HashJoin transformation
      - Filter + Join → NestedLoop alternative
    """
    RelNode.reset_id_counter()

    orders = TableScan("orders", row_count=10000.0)
    customer = TableScan("customer", row_count=1000.0)

    join = LogicalJoin(
        left=orders, right=customer,
        condition="o.cust_id = c.id",
        selectivity=0.01,
    )

    filter_rel = LogicalFilter(
        input=join,
        condition="o.amount > 100",
        selectivity=0.3,
    )

    project = LogicalProject(
        input=filter_rel,
        columns=["o.*", "c.name"],
    )

    return project


def aggregation_query() -> RelNode:
    """
    SQL: SELECT c.country, COUNT(*), SUM(o.amount)
         FROM orders o
         JOIN customer c ON o.cust_id = c.id
         GROUP BY c.country

    Demonstrates:
      - Aggregate on top of Join
      - HashAggregate implementation
      - Filter pushdown before aggregation
    """
    RelNode.reset_id_counter()

    orders = TableScan("orders", row_count=10000.0)
    customer = TableScan("customer", row_count=1000.0)

    join = LogicalJoin(
        left=orders, right=customer,
        condition="o.cust_id = c.id",
        selectivity=0.01,
    )

    agg = LogicalAggregate(
        input=join,
        group_keys=["c.country"],
        agg_funcs=["COUNT(*)", "SUM(o.amount)"],
    )

    return agg


def star_schema_query() -> RelNode:
    """
    SQL: A 4-table star schema query (fact table + 3 dimensions)

         SELECT d.region, p.category, SUM(f.sales)
         FROM fact f
         JOIN date d ON f.date_id = d.id
         JOIN product p ON f.prod_id = p.id
         JOIN store s ON f.store_id = s.id
         WHERE d.year = 2024 AND p.category = 'Electronics'
         GROUP BY d.region, p.category

    Demonstrates:
      - Large search space (4! = 24 join orders)
      - Multiple filter pushdowns
      - How Cascades pruning compares to Volcano exhaustive search
    """
    RelNode.reset_id_counter()

    fact = TableScan("fact", row_count=100000.0)
    date_dim = TableScan("date_dim", row_count=365.0)
    product = TableScan("product", row_count=1000.0)
    store = TableScan("store", row_count=500.0)

    # f ⨝ date
    join1 = LogicalJoin(
        left=fact, right=date_dim,
        condition="f.date_id = d.id",
        selectivity=0.001,
    )

    # (f ⨝ d) ⨝ product
    join2 = LogicalJoin(
        left=join1, right=product,
        condition="f.prod_id = p.id",
        selectivity=0.001,
    )

    # ((f ⨝ d) ⨝ p) ⨝ store
    join3 = LogicalJoin(
        left=join2, right=store,
        condition="f.store_id = s.id",
        selectivity=0.001,
    )

    # Filters
    filter_date = LogicalFilter(
        input=join3,
        condition="d.year = 2024",
        selectivity=0.1,
    )

    filter_product = LogicalFilter(
        input=filter_date,
        condition="p.category = 'Electronics'",
        selectivity=0.2,
    )

    agg = LogicalAggregate(
        input=filter_product,
        group_keys=["d.region", "p.category"],
        agg_funcs=["SUM(f.sales)"],
    )

    return agg


def four_table_chain() -> RelNode:
    """
    SQL: SELECT *
         FROM a JOIN b ON a.id = b.a_id
         JOIN c ON b.id = c.b_id
         JOIN d ON c.id = d.c_id

    Demonstrates:
      - Linear chain join ordering (A⨝B⨝C⨝D)
      - DP join reorder: 2^3 = 8 partitions vs 4! = 24 permutations
      - Optimal order depends on table sizes (small tables first)
    """
    RelNode.reset_id_counter()

    a = TableScan("a", row_count=100.0)
    b = TableScan("b", row_count=1000.0)
    c = TableScan("c", row_count=10000.0)
    d = TableScan("d", row_count=100000.0)

    # a ⨝ b
    join1 = LogicalJoin(
        left=a, right=b,
        condition="a.id = b.a_id",
        selectivity=0.1,
    )

    # (a ⨝ b) ⨝ c
    join2 = LogicalJoin(
        left=join1, right=c,
        condition="b.id = c.b_id",
        selectivity=0.01,
    )

    # ((a ⨝ b) ⨝ c) ⨝ d
    join3 = LogicalJoin(
        left=join2, right=d,
        condition="c.id = d.c_id",
        selectivity=0.001,
    )

    return join3


def five_table_star() -> RelNode:
    """
    SQL: 5-table star schema (fact + 4 dimensions)

    Demonstrates:
      - DP join reorder with 5 tables (2^4 = 16 partitions vs 5! = 120)
      - Shows exponential advantage of DP over exhaustive enumeration
    """
    RelNode.reset_id_counter()

    fact = TableScan("fact", row_count=1000000.0)
    t1 = TableScan("dim1", row_count=100.0)
    t2 = TableScan("dim2", row_count=500.0)
    t3 = TableScan("dim3", row_count=1000.0)
    t4 = TableScan("dim4", row_count=2000.0)

    # fact ⨝ dim1
    join1 = LogicalJoin(
        left=fact, right=t1,
        condition="fact.t1_id = dim1.id",
        selectivity=0.0001,
    )

    # (fact ⨝ dim1) ⨝ dim2
    join2 = LogicalJoin(
        left=join1, right=t2,
        condition="fact.t2_id = dim2.id",
        selectivity=0.0001,
    )

    # ((fact ⨝ dim1) ⨝ dim2) ⨝ dim3
    join3 = LogicalJoin(
        left=join2, right=t3,
        condition="fact.t3_id = dim3.id",
        selectivity=0.0001,
    )

    # (((fact ⨝ dim1) ⨝ dim2) ⨝ dim3) ⨝ dim4
    join4 = LogicalJoin(
        left=join3, right=t4,
        condition="fact.t4_id = dim4.id",
        selectivity=0.0001,
    )

    return join4


# Registry of examples for CLI
EXAMPLES = {
    "two-table-join": two_table_join,
    "three-table-join": three_table_join,
    "join-with-filter": join_with_filter,
    "aggregation": aggregation_query,
    "star-schema": star_schema_query,
    "four-table-chain": four_table_chain,
    "five-table-star": five_table_star,
}

EXAMPLE_DESCRIPTIONS = {
    "two-table-join": "Simple 2-table JOIN — demonstrates join commutativity and implementation choice",
    "three-table-join": "3-table JOIN with filter — demonstrates filter pushdown and join ordering",
    "join-with-filter": "JOIN with filter + project — demonstrates Filter→HashJoin transformation",
    "aggregation": "JOIN + GROUP BY — demonstrates aggregation on top of joins",
    "star-schema": "4-table star schema with filters + aggregation — large search space, multiple pushdowns",
    "four-table-chain": "4-table linear chain join — DP reorder: 8 partitions vs 24 permutations",
    "five-table-star": "5-table star schema — DP reorder: 16 partitions vs 120 permutations",
}
