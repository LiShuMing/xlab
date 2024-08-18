import duckdb
import pytest

def test_basic():
    r1 = duckdb.sql("SELECT 42 AS i")
    print(r1)
    duckdb.sql("SELECT i * 2 AS k FROM r1").show()
