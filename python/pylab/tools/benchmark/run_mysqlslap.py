import os
import subprocess
import sys

# MySQL 连接信息
HOST="172.26.81.63"
PORT="9030"
USER="root"
SCHEMA="db1"

def run_command(command, cwd=None):
    """
    Helper function to run a shell command and return its output.
    """
    try:
        print("Running command:", " ".join(command))
        result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e.stderr.strip()}")
    

def run_mysqlslap(concurrency: int = 1, query: str = "select 1", iterations: int = 3, number_of_queries: int = 30):
    """
    Run mysqlslap with the given parameters.
    """
    command = [
        "mysqlslap",
        f"--host={HOST}",
        f"--port={PORT}",
        f"--user={USER}",
        f"--concurrency={concurrency}",
        f"--iterations={iterations}",
        f"--number-of-queries={number_of_queries}",
        f"--create-schema={SCHEMA}",
        f"--query={query}",
    ]
    return run_command(command)

def run_mysql(sql: str):
    """
    Run a SQL query on MySQL.
    """
    command = [
        "mysql",
        f"-h{HOST}",
        f"-P{PORT}",
        f"-u{USER}",
        SCHEMA,
        "-e",
        sql,
    ]
    return run_command(command)

# CHECK_MODES = ["NOCHECK", "LOOSE", "FORCE_MV", "CHECKED"]
CHECK_MODES = ["FORCE_MV"]
def run_iceberg_tests_diable_mv1(sqls: list[str], mv_name: str, concurrency: int = 1):
    print(">>>>>>> mode: disable mv")
    run_mysql("set global enable_materialized_view_rewrite = false;")
    for sql in sqls:
        # run by without using mv
        result = run_mysqlslap(query=sql, concurrency=concurrency, number_of_queries=10*concurrency)
        print(result)

def run_iceberg_tests_diable_mv2(sqls: list[str], mv_name: str, concurrency: int = 1):
    print(">>>>>>> mode: disable mv")
    run_mysql("set global enable_materialized_view_rewrite = false;")
    for sql in sqls:
        # run by without using mv
        result = run_mysqlslap(query=sql, concurrency=concurrency, number_of_queries=10*concurrency)
        print(result)

def run_iceberg_tests_enable_mv(sqls: list[str], mv_name: str, concurrency: int = 1):
    run_mysql("set global enable_materialized_view_rewrite = true;")
    print(">>>>>>> mode: enable mv")
    for mode in CHECK_MODES:
        print("mode:", mode)
        run_mysql(f"alter materialized view {mv_name} set ('query_rewrite_consistency'='{mode}');")
        for sql in sqls:
            # run by using mv
            result = run_mysqlslap(query=sql, concurrency=concurrency, number_of_queries=10*concurrency)
            print(result)

def run_concurrency(concurrency: int = 1):
    # Run mysqlslap with the given parameters
    sqls = [
        "select count(1) from iceberg.sql_test_db.lineitem_days_1000 where l_shipdate > '2023-11-01';",
        "select count(1) from iceberg.sql_test_db.lineitem_days_1000 where l_shipdate > '2023-01-01';",
        "select count(1) from  iceberg.sql_test_db.lineitem_days_1000 where l_shipdate >= '2023-01-01' and l_shipdate < '2023-06-01';",
    ]
    run_iceberg_tests_diable_mv1(sqls, 'iceberg_lineitem_days_1000_mv', concurrency=concurrency)
    run_iceberg_tests_enable_mv(sqls, 'iceberg_lineitem_days_1000_mv', concurrency=concurrency)
    sqls = [
        "select count(1) from olap_lineitem_days_1000_tbl where l_shipdate > '2023-11-01';",
        "select count(1) from olap_lineitem_days_1000_tbl where l_shipdate > '2023-01-01';",
        "select count(1) from olap_lineitem_days_1000_tbl where l_shipdate >= '2023-01-01' and l_shipdate < '2023-06-01';",
    ]
    run_iceberg_tests_diable_mv2(sqls, 'iceberg_lineitem_days_1000_mv', concurrency=concurrency)

if __name__ == "__main__":
    # run_mysql("set global materialized_view_rewrite_mode='force';")
    run_mysql("set global materialized_view_rewrite_mode='default';")
    # cons = [1, 10, 20, 50, 100]
    cons = [100]
    for con in cons:
        run_concurrency(concurrency=con)