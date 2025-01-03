CREATE TABLE orders (
                        o_orderkey       BIGINT NOT NULL,
                        o_orderdate      DATE NOT NULL,
                        o_custkey        INT NOT NULL,
                        o_orderstatus    VARCHAR(1) NOT NULL,
                        o_totalprice     DECIMAL(15, 2) NOT NULL,
                        o_orderpriority  VARCHAR(15) NOT NULL,
                        o_clerk          VARCHAR(15) NOT NULL,
                        o_shippriority   INT NOT NULL,
                        o_comment        VARCHAR(79) NOT NULL
) ENGINE=OLAP
DUPLICATE KEY(`o_orderkey`, `o_orderdate`)
PARTITION BY RANGE(`o_orderdate`)
(
   START ("1992-01-01") END ("1999-01-01") EVERY (INTERVAL 1 day)
)
DISTRIBUTED BY HASH(`o_orderkey`) BUCKETS 96
PROPERTIES (
    "replication_num" = "default_replication_num"
);