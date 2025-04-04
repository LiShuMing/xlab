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

CREATE TABLE IF NOT EXISTS `customer` (
    `c_custkey` int(11) NOT NULL COMMENT "",
    `c_name` varchar(26) NOT NULL COMMENT "",
    `c_address` varchar(41) NOT NULL COMMENT "",
    `c_city` varchar(11) NOT NULL COMMENT "",
    `c_nation` varchar(16) NOT NULL COMMENT "",
    `c_region` varchar(13) NOT NULL COMMENT "",
    `c_phone` varchar(16) NOT NULL COMMENT "",
    `c_mktsegment` varchar(11) NOT NULL COMMENT ""
) ENGINE=OLAP
DUPLICATE KEY(`c_custkey`)
COMMENT "OLAP"
DISTRIBUTED BY HASH(`c_custkey`) BUCKETS 12
PROPERTIES (
    "replication_num" = "1",
    "colocate_with" = "groupa2",
    "in_memory" = "false",
    "storage_format" = "DEFAULT"
);

CREATE TABLE IF NOT EXISTS `dates` (
    `d_datekey` int(11) NOT NULL COMMENT "",
    `d_date` varchar(20) NOT NULL COMMENT "",
    `d_dayofweek` varchar(10) NOT NULL COMMENT "",
    `d_month` varchar(11) NOT NULL COMMENT "",
    `d_year` int(11) NOT NULL COMMENT "",
    `d_yearmonthnum` int(11) NOT NULL COMMENT "",
    `d_yearmonth` varchar(9) NOT NULL COMMENT "",
    `d_daynuminweek` int(11) NOT NULL COMMENT "",
    `d_daynuminmonth` int(11) NOT NULL COMMENT "",
    `d_daynuminyear` int(11) NOT NULL COMMENT "",
    `d_monthnuminyear` int(11) NOT NULL COMMENT "",
    `d_weeknuminyear` int(11) NOT NULL COMMENT "",
    `d_sellingseason` varchar(14) NOT NULL COMMENT "",
    `d_lastdayinweekfl` int(11) NOT NULL COMMENT "",
    `d_lastdayinmonthfl` int(11) NOT NULL COMMENT "",
    `d_holidayfl` int(11) NOT NULL COMMENT "",
    `d_weekdayfl` int(11) NOT NULL COMMENT ""
) ENGINE=OLAP
DUPLICATE KEY(`d_datekey`)
COMMENT "OLAP"
DISTRIBUTED BY HASH(`d_datekey`) BUCKETS 1
PROPERTIES (
    "replication_num" = "1",
    "in_memory" = "false",
    "colocate_with" = "groupa3",
    "storage_format" = "DEFAULT"
);

 CREATE TABLE IF NOT EXISTS `supplier` (
    `s_suppkey` int(11) NOT NULL COMMENT "",
    `s_name` varchar(26) NOT NULL COMMENT "",
    `s_address` varchar(26) NOT NULL COMMENT "",
    `s_city` varchar(11) NOT NULL COMMENT "",
    `s_nation` varchar(16) NOT NULL COMMENT "",
    `s_region` varchar(13) NOT NULL COMMENT "",
    `s_phone` varchar(16) NOT NULL COMMENT ""
) ENGINE=OLAP
DUPLICATE KEY(`s_suppkey`)
COMMENT "OLAP"
DISTRIBUTED BY HASH(`s_suppkey`) BUCKETS 12
PROPERTIES (
    "replication_num" = "1",
    "colocate_with" = "groupa4",
    "in_memory" = "false",
    "storage_format" = "DEFAULT"
);

CREATE TABLE IF NOT EXISTS `part` (
    `p_partkey` int(11) NOT NULL COMMENT "",
    `p_name` varchar(23) NOT NULL COMMENT "",
    `p_mfgr` varchar(7) NOT NULL COMMENT "",
    `p_category` varchar(8) NOT NULL COMMENT "",
    `p_brand` varchar(10) NOT NULL COMMENT "",
    `p_color` varchar(12) NOT NULL COMMENT "",
    `p_type` varchar(26) NOT NULL COMMENT "",
    `p_size` int(11) NOT NULL COMMENT "",
    `p_container` varchar(11) NOT NULL COMMENT ""
) ENGINE=OLAP
DUPLICATE KEY(`p_partkey`)
COMMENT "OLAP"
DISTRIBUTED BY HASH(`p_partkey`) BUCKETS 12
PROPERTIES (
    "replication_num" = "1",
    "colocate_with" = "groupa5",
    "in_memory" = "false",
    "storage_format" = "DEFAULT"
);