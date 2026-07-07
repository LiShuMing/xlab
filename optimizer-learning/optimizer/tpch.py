"""
TPC-H benchmark queries (SF=1).

Contains all 22 TPC-H query definitions and schema loading.
Queries are from the TPC-H specification v2.18.0.
"""

from __future__ import annotations

from optimizer.catalog import Catalog, create_tpch_sf1_catalog


# ──────────────────────────────────────────────
# TPC-H Queries (simplified for learning)
# ──────────────────────────────────────────────

TPCH_QUERIES: dict[str, str] = {
    "q1": """
        SELECT
            l_returnflag,
            l_linestatus,
            SUM(l_quantity) AS sum_qty,
            SUM(l_extendedprice) AS sum_base_price,
            SUM(l_extendedprice * (1 - l_discount)) AS sum_disc_price,
            SUM(l_extendedprice * (1 - l_discount) * (1 + l_tax)) AS sum_charge,
            AVG(l_quantity) AS avg_qty,
            AVG(l_extendedprice) AS avg_price,
            AVG(l_discount) AS avg_disc,
            COUNT(*) AS count_order
        FROM lineitem
        WHERE l_shipdate <= '1998-09-02'
        GROUP BY l_returnflag, l_linestatus
    """,

    "q2": """
        SELECT
            s_acctbal, s_name, n_name,
            p_partkey, p_mfgr,
            s_address, s_phone, s_comment
        FROM part, supplier, partsupp, nation, region
        WHERE p_partkey = ps_partkey
          AND s_suppkey = ps_suppkey
          AND p_size = 15
          AND p_type LIKE '%BRASS'
          AND s_nationkey = n_nationkey
          AND n_regionkey = r_regionkey
          AND r_name = 'EUROPE'
          AND ps_supplycost = (
              SELECT MIN(ps_supplycost)
              FROM partsupp, supplier, nation, region
              WHERE p_partkey = ps_partkey
                AND s_suppkey = ps_suppkey
                AND s_nationkey = n_nationkey
                AND n_regionkey = r_regionkey
                AND r_name = 'EUROPE'
          )
    """,

    "q3": """
        SELECT
            l_orderkey,
            SUM(l_extendedprice * (1 - l_discount)) AS revenue,
            o_orderdate,
            o_shippriority
        FROM customer, orders, lineitem
        WHERE c_mktsegment = 'BUILDING'
          AND c_custkey = o_custkey
          AND l_orderkey = o_orderkey
          AND o_orderdate < '1995-03-15'
          AND l_shipdate > '1995-03-15'
        GROUP BY l_orderkey, o_orderdate, o_shippriority
    """,

    "q4": """
        SELECT
            o_orderpriority,
            COUNT(*) AS order_count
        FROM orders
        WHERE o_orderdate >= '1993-07-01'
          AND o_orderdate < '1993-10-01'
          AND EXISTS (
              SELECT *
              FROM lineitem
              WHERE l_orderkey = o_orderkey
                AND l_commitdate < l_receiptdate
          )
        GROUP BY o_orderpriority
    """,

    "q5": """
        SELECT
            n_name,
            SUM(l_extendedprice * (1 - l_discount)) AS revenue
        FROM customer, orders, lineitem, supplier, nation, region
        WHERE c_custkey = o_custkey
          AND l_orderkey = o_orderkey
          AND l_suppkey = s_suppkey
          AND c_nationkey = s_nationkey
          AND s_nationkey = n_nationkey
          AND n_regionkey = r_regionkey
          AND r_name = 'ASIA'
          AND o_orderdate >= '1994-01-01'
          AND o_orderdate < '1995-01-01'
        GROUP BY n_name
    """,

    "q6": """
        SELECT
            SUM(l_extendedprice * l_discount) AS revenue
        FROM lineitem
        WHERE l_shipdate >= '1994-01-01'
          AND l_shipdate < '1995-01-01'
          AND l_discount BETWEEN 0.06 - 0.01 AND 0.06 + 0.01
          AND l_quantity < 24
    """,

    "q7": """
        SELECT
            supp_nation, cust_nation, l_year,
            SUM(volume) AS revenue
        FROM (
            SELECT
                n1.n_name AS supp_nation,
                n2.n_name AS cust_nation,
                EXTRACT(YEAR FROM l_shipdate) AS l_year,
                l_extendedprice * (1 - l_discount) AS volume
            FROM supplier, lineitem, orders, customer, nation n1, nation n2
            WHERE s_suppkey = l_suppkey
              AND o_orderkey = l_orderkey
              AND c_custkey = o_custkey
              AND s_nationkey = n1.n_nationkey
              AND c_nationkey = n2.n_nationkey
              AND (
                  (n1.n_name = 'FRANCE' AND n2.n_name = 'GERMANY')
                  OR (n1.n_name = 'GERMANY' AND n2.n_name = 'FRANCE')
              )
              AND l_shipdate BETWEEN '1995-01-01' AND '1996-12-31'
        ) AS shipping
        GROUP BY supp_nation, cust_nation, l_year
    """,

    "q8": """
        SELECT
            o_year,
            SUM(CASE WHEN nation = 'BRAZIL' THEN volume ELSE 0 END)
                / SUM(volume) AS mkt_share
        FROM (
            SELECT
                EXTRACT(YEAR FROM o_orderdate) AS o_year,
                l_extendedprice * (1 - l_discount) AS volume,
                n2.n_name AS nation
            FROM part, supplier, lineitem, orders, customer, nation n1, nation n2, region
            WHERE p_partkey = l_partkey
              AND s_suppkey = l_suppkey
              AND l_orderkey = o_orderkey
              AND o_custkey = c_custkey
              AND c_nationkey = n1.n_nationkey
              AND n1.n_regionkey = r_regionkey
              AND r_name = 'AMERICA'
              AND s_nationkey = n2.n_nationkey
              AND o_orderdate BETWEEN '1995-01-01' AND '1996-12-31'
              AND p_type = 'ECONOMY ANODIZED STEEL'
        ) AS all_nations
        GROUP BY o_year
    """,

    "q9": """
        SELECT
            nation, o_year,
            SUM(amount) AS sum_profit
        FROM (
            SELECT
                n_name AS nation,
                EXTRACT(YEAR FROM o_orderdate) AS o_year,
                l_extendedprice * (1 - l_discount) - ps_supplycost * l_quantity AS amount
            FROM part, supplier, lineitem, partsupp, orders, nation
            WHERE s_suppkey = l_suppkey
              AND ps_suppkey = l_suppkey
              AND ps_partkey = l_partkey
              AND p_partkey = l_partkey
              AND o_orderkey = l_orderkey
              AND s_nationkey = n_nationkey
              AND p_name LIKE '%green%'
        ) AS profit
        GROUP BY nation, o_year
    """,

    "q10": """
        SELECT
            c_custkey, c_name,
            SUM(l_extendedprice * (1 - l_discount)) AS revenue,
            c_acctbal, n_name,
            c_address, c_phone, c_comment
        FROM customer, orders, lineitem, nation
        WHERE c_custkey = o_custkey
          AND l_orderkey = o_orderkey
          AND o_orderdate >= '1993-10-01'
          AND o_orderdate < '1994-01-01'
          AND l_returnflag = 'R'
          AND c_nationkey = n_nationkey
        GROUP BY c_custkey, c_name, c_acctbal, c_phone,
                 n_name, c_address, c_comment
    """,

    "q11": """
        SELECT
            ps_partkey,
            SUM(ps_supplycost * ps_availqty) AS value
        FROM partsupp, supplier, nation
        WHERE ps_suppkey = s_suppkey
          AND s_nationkey = n_nationkey
          AND n_name = 'GERMANY'
        GROUP BY ps_partkey
        HAVING SUM(ps_supplycost * ps_availqty) > (
            SELECT SUM(ps_supplycost * ps_availqty) * 0.0001
            FROM partsupp, supplier, nation
            WHERE ps_suppkey = s_suppkey
              AND s_nationkey = n_nationkey
              AND n_name = 'GERMANY'
        )
    """,

    "q12": """
        SELECT
            l_shipmode,
            SUM(CASE WHEN o_orderpriority = '1-URGENT'
                      OR o_orderpriority = '2-HIGH'
                     THEN 1 ELSE 0 END) AS high_line_count,
            SUM(CASE WHEN o_orderpriority <> '1-URGENT'
                      AND o_orderpriority <> '2-HIGH'
                     THEN 1 ELSE 0 END) AS low_line_count
        FROM orders, lineitem
        WHERE o_orderkey = l_orderkey
          AND l_shipmode IN ('MAIL', 'SHIP')
          AND l_commitdate < l_receiptdate
          AND l_shipdate < l_commitdate
          AND l_receiptdate >= '1994-01-01'
          AND l_receiptdate < '1995-01-01'
        GROUP BY l_shipmode
    """,

    "q13": """
        SELECT
            c_count, COUNT(*) AS custdist
        FROM (
            SELECT
                c_custkey,
                COUNT(o_orderkey) AS c_count
            FROM customer
            LEFT OUTER JOIN orders ON c_custkey = o_custkey
                AND o_comment NOT LIKE '%special%requests%'
            GROUP BY c_custkey
        ) AS c_orders
        GROUP BY c_count
    """,

    "q14": """
        SELECT
            100.00 * SUM(CASE WHEN p_type LIKE 'PROMO%'
                              THEN l_extendedprice * (1 - l_discount)
                              ELSE 0 END)
                   / SUM(l_extendedprice * (1 - l_discount)) AS promo_revenue
        FROM lineitem, part
        WHERE l_partkey = p_partkey
          AND l_shipdate >= '1995-09-01'
          AND l_shipdate < '1995-10-01'
    """,

    "q15": """
        SELECT
            s_suppkey, s_name, s_address, s_phone, total_revenue
        FROM supplier, revenue0
        WHERE s_suppkey = supplier_no
          AND total_revenue = (SELECT MAX(total_revenue) FROM revenue0)
    """,

    "q16": """
        SELECT
            p_brand, p_type, p_size,
            COUNT(DISTINCT ps_suppkey) AS supplier_cnt
        FROM partsupp, part
        WHERE p_partkey = ps_partkey
          AND p_brand <> 'Brand#45'
          AND p_type NOT LIKE 'MEDIUM POLISHED%'
          AND p_size IN (49, 14, 23, 45, 19, 3, 36, 9)
          AND ps_suppkey NOT IN (
              SELECT s_suppkey
              FROM supplier
              WHERE s_comment LIKE '%Customer%Complaints%'
          )
        GROUP BY p_brand, p_type, p_size
    """,

    "q17": """
        SELECT
            SUM(l_extendedprice) / 7.0 AS avg_yearly
        FROM lineitem, part
        WHERE p_partkey = l_partkey
          AND p_brand = 'Brand#23'
          AND p_container = 'MED BOX'
          AND l_quantity < (
              SELECT 0.2 * AVG(l_quantity)
              FROM lineitem
              WHERE l_partkey = p_partkey
          )
    """,

    "q18": """
        SELECT
            c_name, c_custkey, o_orderkey, o_orderdate,
            o_totalprice, SUM(l_quantity)
        FROM customer, orders, lineitem
        WHERE o_orderkey IN (
            SELECT l_orderkey
            FROM lineitem
            GROUP BY l_orderkey
            HAVING SUM(l_quantity) > 300
        )
          AND c_custkey = o_custkey
          AND o_orderkey = l_orderkey
        GROUP BY c_name, c_custkey, o_orderkey,
                 o_orderdate, o_totalprice
    """,

    "q19": """
        SELECT
            SUM(l_extendedprice * (1 - l_discount)) AS revenue
        FROM lineitem, part
        WHERE (
            p_partkey = l_partkey
            AND p_brand = 'Brand#12'
            AND p_container IN ('SM CASE', 'SM BOX', 'SM PACK', 'SM PKG')
            AND l_quantity >= 1 AND l_quantity <= 11
            AND p_size BETWEEN 1 AND 5
            AND l_shipmode IN ('AIR', 'AIR REG')
            AND l_shipinstruct = 'DELIVER IN PERSON'
        )
        OR (
            p_partkey = l_partkey
            AND p_brand = 'Brand#23'
            AND p_container IN ('MED BAG', 'MED BOX', 'MED PKG', 'MED PACK')
            AND l_quantity >= 10 AND l_quantity <= 20
            AND p_size BETWEEN 1 AND 10
            AND l_shipmode IN ('AIR', 'AIR REG')
            AND l_shipinstruct = 'DELIVER IN PERSON'
        )
        OR (
            p_partkey = l_partkey
            AND p_brand = 'Brand#34'
            AND p_container IN ('LG CASE', 'LG BOX', 'LG PACK', 'LG PKG')
            AND l_quantity >= 20 AND l_quantity <= 30
            AND p_size BETWEEN 1 AND 15
            AND l_shipmode IN ('AIR', 'AIR REG')
            AND l_shipinstruct = 'DELIVER IN PERSON'
        )
    """,

    "q20": """
        SELECT
            s_name, s_address
        FROM supplier, nation
        WHERE s_suppkey IN (
            SELECT ps_suppkey
            FROM partsupp
            WHERE ps_partkey IN (
                SELECT p_partkey
                FROM part
                WHERE p_name LIKE 'forest%'
            )
              AND ps_availqty > (
                  SELECT 0.5 * SUM(l_quantity)
                  FROM lineitem
                  WHERE l_partkey = ps_partkey
                    AND l_suppkey = ps_suppkey
                    AND l_shipdate >= '1994-01-01'
                    AND l_shipdate < '1995-01-01'
              )
        )
          AND s_nationkey = n_nationkey
          AND n_name = 'CANADA'
    """,

    "q21": """
        SELECT
            s_name, COUNT(*) AS numwait
        FROM supplier, lineitem l1, orders, nation
        WHERE s_suppkey = l1.l_suppkey
          AND o_orderkey = l1.l_orderkey
          AND o_orderstatus = 'F'
          AND l1.l_receiptdate > l1.l_commitdate
          AND EXISTS (
              SELECT * FROM lineitem l2
              WHERE l2.l_orderkey = l1.l_orderkey
                AND l2.l_suppkey <> l1.l_suppkey
          )
          AND NOT EXISTS (
              SELECT * FROM lineitem l3
              WHERE l3.l_orderkey = l1.l_orderkey
                AND l3.l_suppkey <> l1.l_suppkey
                AND l3.l_receiptdate > l3.l_commitdate
          )
          AND s_nationkey = n_nationkey
          AND n_name = 'SAUDI ARABIA'
        GROUP BY s_name
    """,

    "q22": """
        SELECT
            cntrycode,
            COUNT(*) AS numcust,
            SUM(c_acctbal) AS totacctbal
        FROM (
            SELECT
                SUBSTRING(c_phone FROM 1 FOR 2) AS cntrycode,
                c_acctbal
            FROM customer
            WHERE SUBSTRING(c_phone FROM 1 FOR 2) IN
                ('13', '31', '23', '29', '30', '18', '17')
              AND c_acctbal > (
                  SELECT AVG(c_acctbal)
                  FROM customer
                  WHERE c_acctbal > 0.00
                    AND SUBSTRING(c_phone FROM 1 FOR 2) IN
                        ('13', '31', '23', '29', '30', '18', '17')
              )
              AND NOT EXISTS (
                  SELECT * FROM orders
                  WHERE o_custkey = c_custkey
              )
        ) AS custsale
        GROUP BY cntrycode
    """,
}


def get_query(name: str) -> str:
    """Get a TPC-H query by name (q1..q22)."""
    name = name.lower().strip()
    if name not in TPCH_QUERIES:
        raise ValueError(f"Unknown TPC-H query: {name}. Available: q1..q22")
    return TPCH_QUERIES[name]


def load_tpch_schema(catalog: Catalog | None = None) -> Catalog:
    """Load TPC-H SF=1 schema into a catalog."""
    if catalog is None:
        return create_tpch_sf1_catalog()
    # Merge TPC-H tables into existing catalog
    tpch = create_tpch_sf1_catalog()
    for name, meta in tpch.tables.items():
        catalog.add_table(
            name=name,
            columns=meta.columns,
            row_count=meta.row_count,
            stats=meta.column_stats,
        )
    return catalog


def list_queries() -> list[tuple[str, str]]:
    """List all TPC-H queries with a brief description."""
    descriptions = {
        "q1": "Pricing summary report (lineitem aggregation)",
        "q2": "Minimum cost supplier (multi-table join + subquery)",
        "q3": "Shipping priority (customer/orders/lineitem join)",
        "q4": "Order priority check (exists subquery)",
        "q5": "Local supplier volume (6-table join)",
        "q6": "Forecasting revenue change (single table filter)",
        "q7": "Volume shipping (self-join pattern)",
        "q8": "National market share (correlated calculation)",
        "q9": "Product type profit measure (inline view)",
        "q10": "Returned item reporting (4-table join + agg)",
        "q11": "Important stock identification (having subquery)",
        "q12": "Ship mode and order priority (case expression)",
        "q13": "Customer distribution (left outer join)",
        "q14": "Promotion effect (single calculation)",
        "q15": "Top supplier (view-based)",
        "q16": "Parts/supplier relationship (not in subquery)",
        "q17": "Small-quantity-order revenue (correlated subquery)",
        "q18": "Big order customer (in subquery + group by)",
        "q19": "Discounted revenue (complex OR conditions)",
        "q20": "Potential part promotion (nested subqueries)",
        "q21": "Suppliers who kept orders waiting (exists + not exists)",
        "q22": "Global sales opportunity (substring + avg subquery)",
    }
    return [(name, descriptions.get(name, "")) for name in sorted(TPCH_QUERIES.keys())]
