CREATE TABLE lineitem (
    l_shipdate      DATE NOT NULL,
    l_orderkey      INT NOT NULL,
    l_linenumber    INT not null,
    l_partkey       INT NOT NULL,
    l_suppkey       INT not null,
    l_quantity      DECIMAL(15, 2) NOT NULL,
    l_extendedprice DECIMAL(15, 2) NOT NULL,
    l_discount      DECIMAL(15, 2) NOT NULL,
    l_tax           DECIMAL(15, 2) NOT NULL,
    l_returnflag    VARCHAR(1) NOT NULL,
    l_linestatus    VARCHAR(1) NOT NULL,
    l_commitdate    DATE NOT NULL,
    l_receiptdate   DATE NOT NULL,
    l_shipinstruct  VARCHAR(25) NOT NULL,
    l_shipmode      VARCHAR(10) NOT NULL,
    l_comment       VARCHAR(44) NOT NULL
) ENGINE=OLAP
DUPLICATE KEY(`l_shipdate`, `l_orderkey`)
COMMENT "OLAP"
DISTRIBUTED BY HASH(`l_orderkey`) BUCKETS 96
PROPERTIES (
    "replication_num" = "default_replication_num",
    "in_memory" = "false",
    "storage_format" = "DEFAULT",
    "colocate_with" = "group_tpch_100"
);
