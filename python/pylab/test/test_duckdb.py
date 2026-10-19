import duckdb
def test_basic():
    with duckdb.connect(":memory:") as conn:
        r1 = conn.sql("SELECT 42 AS i")
        assert r1.fetchall() == [(42,)]
        assert conn.sql("SELECT i * 2 AS k FROM r1").fetchall() == [(84,)]
