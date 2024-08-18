CREATE TABLE IF NOT EXISTS `lineorder` (
     `lo_orderkey` int(11) NOT NULL COMMENT "",
    `lo_linenumber` int(11) NOT NULL COMMENT "",
    `lo_custkey` int(11) NOT NULL COMMENT "",
    `lo_partkey` int(11) NOT NULL COMMENT "",
    `lo_suppkey` int(11) NOT NULL COMMENT "",
    `lo_orderdate` date NOT NULL COMMENT "",
    `lo_orderpriority` varchar(16) NOT NULL COMMENT "",
    `lo_shippriority` int(11) NOT NULL COMMENT "",
    `lo_quantity` int(11) NOT NULL COMMENT "",
    `lo_extendedprice` int(11) NOT NULL COMMENT "",
    `lo_ordtotalprice` int(11) NOT NULL COMMENT "",
    `lo_discount` int(11) NOT NULL COMMENT "",
    `lo_revenue` int(11) NOT NULL COMMENT "",
    `lo_supplycost` int(11) NOT NULL COMMENT "",
    `lo_tax` int(11) NOT NULL COMMENT "",
    `lo_commitdate` int(11) NOT NULL COMMENT "",
    `lo_shipmode` varchar(11) NOT NULL COMMENT ""
    ) ENGINE=OLAP
    DUPLICATE KEY(`lo_orderkey`)
    COMMENT "OLAP"
    PARTITION BY RANGE(`lo_orderdate`)
(
    PARTITION p1 VALUES [("1992-01-01"), ("1993-01-01")),
    PARTITION p2 VALUES [("1993-01-01"), ("1994-01-01")),
    PARTITION p3 VALUES [("1994-01-01"), ("1995-01-01")),
    PARTITION p4 VALUES [("1995-01-01"), ("1996-01-01")),
    PARTITION p5 VALUES [("1996-01-01"), ("1997-01-01")),
    PARTITION p6 VALUES [("1997-01-01"), ("1998-01-01")),
    PARTITION p7 VALUES [("1998-01-01"), ("1999-01-01")))
    DISTRIBUTED BY HASH(`lo_orderkey`) BUCKETS 48
    PROPERTIES (
                   "replication_num" = "1",
                   "colocate_with" = "groupa1",
                   "in_memory" = "false",
                   "storage_format" = "DEFAULT"
               );

INSERT INTO lineorder (lo_orderkey, lo_linenumber, lo_custkey, lo_partkey, lo_suppkey
                      , lo_orderdate, lo_orderpriority, lo_shippriority, lo_quantity, lo_extendedprice
                      , lo_ordtotalprice, lo_discount, lo_revenue, lo_supplycost, lo_tax
                      , lo_commitdate, lo_shipmode)
VALUES
    (1, 1, 101, 201, 301, '1993-01-01', 'HIGH', 1, 10, 100, 90, 0, 90, 50, 5, 19930115, 'AIR'),
    (1, 1, 101, 201, 301, '1993-01-01', 'MEDIUM', 1, 10, 100, 90, 0, 90, 50, 5, 19930115, 'AIR'),
    (2, 2, 102, 202, 302, '1994-01-01', 'MEDIUM', 2, 20, 200, 180, 5, 175, 75, 7, 19940116, 'SHIP'),
    (3, 3, 103, 203, 302, '1995-01-01', 'MEDIUM', 2, 20, 200, 180, 5, 175, 75, 7, 19940116, 'SHIP')
    ;