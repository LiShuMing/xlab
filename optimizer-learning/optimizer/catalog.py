"""
Catalog: table metadata and column statistics.

Provides the optimizer with information about:
- Table schemas (column names, types)
- Row counts (for cost estimation)
- Column statistics (NDV, null fraction, min/max for selectivity)

Includes built-in TPC-H SF=1 statistics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ColumnStats:
    """Statistics for a single column."""
    ndv: int = 1000              # Number of distinct values
    null_frac: float = 0.0       # Fraction of nulls (0.0 - 1.0)
    avg_width: int = 8           # Average width in bytes
    min_val: Any = None
    max_val: Any = None


@dataclass
class TableMetadata:
    """Metadata for a single table."""
    name: str
    columns: list[str]
    row_count: float
    column_stats: dict[str, ColumnStats] = field(default_factory=dict)

    def get_column(self, name: str) -> ColumnStats:
        """Get stats for a column, returns default if not found."""
        return self.column_stats.get(name, ColumnStats())


class Catalog:
    """
    Schema catalog — stores table metadata for SQL parsing and optimization.
    Like Calcite's Schema/SchemaPlus.
    """

    def __init__(self):
        self.tables: dict[str, TableMetadata] = {}

    def add_table(self, name: str, columns: list[str],
                  row_count: float, stats: dict[str, ColumnStats] | None = None) -> None:
        """Register a table with its metadata."""
        self.tables[name.lower()] = TableMetadata(
            name=name.lower(),
            columns=[c.lower() for c in columns],
            row_count=row_count,
            column_stats=stats or {},
        )

    def get_table(self, name: str) -> TableMetadata | None:
        """Look up a table by name (case-insensitive)."""
        return self.tables.get(name.lower())

    def has_table(self, name: str) -> bool:
        return name.lower() in self.tables

    def explain(self) -> str:
        lines = ["Catalog Tables:"]
        for name, meta in sorted(self.tables.items()):
            lines.append(f"  {name}: {meta.row_count:.0f} rows, columns: {', '.join(meta.columns)}")
        return "\n".join(lines)


# ──────────────────────────────────────────────
# TPC-H SF=1 Statistics
# ──────────────────────────────────────────────

def create_tpch_sf1_catalog() -> Catalog:
    """
    Create a Catalog with TPC-H Scale Factor 1 statistics.
    Row counts are from the TPC-H specification for SF=1.
    """
    catalog = Catalog()

    # REGION (5 rows, tiny table)
    catalog.add_table("region",
        columns=["r_regionkey", "r_name", "r_comment"],
        row_count=5,
        stats={
            "r_regionkey": ColumnStats(ndv=5, null_frac=0.0),
            "r_name": ColumnStats(ndv=5, null_frac=0.0),
        })

    # NATION (25 rows, tiny table)
    catalog.add_table("nation",
        columns=["n_nationkey", "n_name", "n_regionkey", "n_comment"],
        row_count=25,
        stats={
            "n_nationkey": ColumnStats(ndv=25, null_frac=0.0),
            "n_name": ColumnStats(ndv=25, null_frac=0.0),
            "n_regionkey": ColumnStats(ndv=5, null_frac=0.0),
        })

    # SUPPLIER (10,000 rows)
    catalog.add_table("supplier",
        columns=["s_suppkey", "s_name", "s_address", "s_nationkey",
                  "s_phone", "s_acctbal", "s_comment"],
        row_count=10_000,
        stats={
            "s_suppkey": ColumnStats(ndv=10000, null_frac=0.0),
            "s_nationkey": ColumnStats(ndv=25, null_frac=0.0),
            "s_acctbal": ColumnStats(ndv=10000, null_frac=0.0),
        })

    # PART (200,000 rows)
    catalog.add_table("part",
        columns=["p_partkey", "p_name", "p_mfgr", "p_brand", "p_type",
                  "p_size", "p_container", "p_retailprice", "p_comment"],
        row_count=200_000,
        stats={
            "p_partkey": ColumnStats(ndv=200000, null_frac=0.0),
            "p_brand": ColumnStats(ndv=2500, null_frac=0.0),
            "p_size": ColumnStats(ndv=50, null_frac=0.0),
            "p_type": ColumnStats(ndv=150, null_frac=0.0),
        })

    # PARTSUPP (800,000 rows)
    catalog.add_table("partsupp",
        columns=["ps_partkey", "ps_suppkey", "ps_availqty", "ps_supplycost",
                  "ps_comment"],
        row_count=800_000,
        stats={
            "ps_partkey": ColumnStats(ndv=200000, null_frac=0.0),
            "ps_suppkey": ColumnStats(ndv=10000, null_frac=0.0),
            "ps_supplycost": ColumnStats(ndv=10000, null_frac=0.0),
        })

    # CUSTOMER (150,000 rows)
    catalog.add_table("customer",
        columns=["c_custkey", "c_name", "c_address", "c_nationkey",
                  "c_phone", "c_acctbal", "c_mktsegment", "c_comment"],
        row_count=150_000,
        stats={
            "c_custkey": ColumnStats(ndv=150000, null_frac=0.0),
            "c_nationkey": ColumnStats(ndv=25, null_frac=0.0),
            "c_mktsegment": ColumnStats(ndv=5, null_frac=0.0),
            "c_acctbal": ColumnStats(ndv=150000, null_frac=0.0),
        })

    # ORDERS (1,500,000 rows)
    catalog.add_table("orders",
        columns=["o_orderkey", "o_custkey", "o_orderstatus", "o_totalprice",
                  "o_orderdate", "o_orderpriority", "o_clerk", "o_shippriority",
                  "o_comment"],
        row_count=1_500_000,
        stats={
            "o_orderkey": ColumnStats(ndv=1500000, null_frac=0.0),
            "o_custkey": ColumnStats(ndv=150000, null_frac=0.0),
            "o_orderstatus": ColumnStats(ndv=3, null_frac=0.0),
            "o_orderpriority": ColumnStats(ndv=5, null_frac=0.0),
            "o_orderdate": ColumnStats(ndv=2406, null_frac=0.0),  # ~7 years of dates
        })

    # LINEITEM (6,001,215 rows for SF=1)
    catalog.add_table("lineitem",
        columns=["l_orderkey", "l_partkey", "l_suppkey", "l_linenumber",
                  "l_quantity", "l_extendedprice", "l_discount", "l_tax",
                  "l_returnflag", "l_linestatus", "l_shipdate", "l_commitdate",
                  "l_receiptdate", "l_shipinstruct", "l_shipmode", "l_comment"],
        row_count=6_001_215,
        stats={
            "l_orderkey": ColumnStats(ndv=1500000, null_frac=0.0),
            "l_partkey": ColumnStats(ndv=200000, null_frac=0.0),
            "l_suppkey": ColumnStats(ndv=10000, null_frac=0.0),
            "l_quantity": ColumnStats(ndv=50, null_frac=0.0),
            "l_extendedprice": ColumnStats(ndv=100000, null_frac=0.0),
            "l_discount": ColumnStats(ndv=11, null_frac=0.0),
            "l_returnflag": ColumnStats(ndv=3, null_frac=0.0),
            "l_linestatus": ColumnStats(ndv=2, null_frac=0.0),
            "l_shipdate": ColumnStats(ndv=2406, null_frac=0.0),
            "l_shipmode": ColumnStats(ndv=7, null_frac=0.0),
        })

    # VIEW placeholder (q15: CREATE VIEW revenue0 AS ...)
    catalog.add_table("revenue0",
        columns=["supplier_no", "total_revenue"],
        row_count=10_000,
        stats={
            "supplier_no": ColumnStats(ndv=10000, null_frac=0.0),
            "total_revenue": ColumnStats(ndv=10000, null_frac=0.0),
        })

    return catalog
