package com.starrocks.schema;

import java.util.List;

public class MSSBSchema {
    public static final MTable LINEORDER = new MTable("lineorder", "lo_orderkey",
            List.of(
                    "`lo_orderkey` int(11) NOT NULL",
                    "`lo_linenumber` int(11) NOT NULL",
                    "`lo_custkey` int(11) NOT NULL",
                    "`lo_partkey` int(11) NOT NULL",
                    "`lo_suppkey` int(11) NOT NULL",
                    "`lo_orderdate` int(11) NOT NULL",
                    "`lo_orderpriority` varchar(16) NOT NULL",
                    "`lo_shippriority` int(11) NOT NULL",
                    "`lo_quantity` int(11) NOT NULL",
                    "`lo_extendedprice` int(11) NOT NULL",
                    "`lo_ordtotalprice` int(11) NOT NULL",
                    "`lo_discount` int(11) NOT NULL",
                    "`lo_revenue` int(11) NOT NULL",
                    "`lo_supplycost` int(11) NOT NULL",
                    "`lo_tax` int(11) NOT NULL",
                    "`lo_commitdate` int(11) NOT NULL",
                    "`lo_shipmode` varchar(11) NOT NULL"
            ),
            "lo_orderdate",
            List.of(
                    "PARTITION p1 VALUES [('-2147483648'), ('19930101'))",
                    "PARTITION p2 VALUES [('19930101'), ('19940101'))",
                    "PARTITION p3 VALUES [('19940101'), ('19950101'))",
                    "PARTITION p4 VALUES [('19950101'), ('19960101'))",
                    "PARTITION p5 VALUES [('19960101'), ('19970101'))",
                    "PARTITION p6 VALUES [('19970101'), ('19980101'))",
                    "PARTITION p7 VALUES [('19980101'), ('19990101'))"
            ),
            "lo_orderkey"
    )
            .withProperties("\"foreign_key_constraints\" = \"(lo_custkey) REFERENCES customer(c_custkey);(lo_partkey) REFERENCES part(p_partkey);(lo_suppkey) REFERENCES supplier(s_suppkey);(lo_orderdate) REFERENCES dates(d_datekey)\"")
            .withValues("(1, 1, 101, 201, 301, 19930101, 'HIGH', 1, 10, 100, 90, 0, 90, 50, 5, 19930115, 'AIR'),\n" +
                    "(2, 2, 102, 202, 302, 19940101, 'MEDIUM', 2, 20, 200, 180, 5, 175, 75, 7, 19940116, 'SHIP')");

    public static final MTable CUSTOMER = new MTable("customer", "c_custkey",
            List.of(
                    "`c_custkey` int(11) NOT NULL",
                    "`c_name` varchar(26) NOT NULL",
                    "`c_address` varchar(41) NOT NULL",
                    "`c_city` varchar(11) NOT NULL",
                    "`c_nation` varchar(16) NOT NULL",
                    "`c_region` varchar(13) NOT NULL",
                    "`c_phone` varchar(16) NOT NULL",
                    "`c_mktsegment` varchar(11) NOT NULL "
            )
    ).withProperties("\"unique_constraints\" = \"c_custkey\"")
            .withValues("(101, 'Customer1', '123 Main St', 'City1', 'Nation1', 'Region1', '123-456-7890', 'Segment1'),\n" +
                    "(102, 'Customer2', '456 Oak St', 'City2', 'Nation2', 'Region2', '987-654-3210', 'Segment2'),\n" +
                    "(103, 'Customer3', '789 Pine St', 'City3', 'Nation3', 'Region3', '555-123-4567', 'Segment3')");

    public static final MTable DATES = new MTable("dates", "d_datekey",
            List.of(
                    "`d_datekey` int(11) NOT NULL",
                    "`d_date` varchar(20) NOT NULL",
                    "`d_dayofweek` varchar(10) NOT NULL",
                    "`d_month` varchar(11) NOT NULL",
                    "`d_year` int(11) NOT NULL",
                    "`d_yearmonthnum` int(11) NOT NULL",
                    "`d_yearmonth` varchar(9) NOT NULL",
                    "`d_daynuminweek` int(11) NOT NULL",
                    "`d_daynuminmonth` int(11) NOT NULL",
                    "`d_daynuminyear` int(11) NOT NULL",
                    "`d_monthnuminyear` int(11) NOT NULL",
                    "`d_weeknuminyear` int(11) NOT NULL",
                    "`d_sellingseason` varchar(14) NOT NULL",
                    "`d_lastdayinweekfl` int(11) NOT NULL",
                    "`d_lastdayinmonthfl` int(11) NOT NULL",
                    "`d_holidayfl` int(11) NOT NULL",
                    "`d_weekdayfl` int(11) NOT NULL"
            )
    )
            .withProperties("\"unique_constraints\" = \"d_datekey\"")
            .withValues(
                    "(19940101, '1994-01-01', 'Wednesday', 'December', 2023, 202312, '2023-12', 3, 7, 341, 12, 49, 'Holiday Season', 0, 0, 1, 1)," +
                    "(19930101, '1993-01-01', 'Wednesday', 'December', 2023, 202312, '2023-12', 3, 7, 341, 12, 49, 'Holiday Season', 0, 0, 1, 1)"
            );

    public static final MTable SUPPLIER = new MTable("supplier", "s_suppkey",
            List.of(
                    "`s_suppkey` int(11) NOT NULL",
                    "`s_name` varchar(26) NOT NULL",
                    "`s_address` varchar(26) NOT NULL",
                    "`s_city` varchar(11) NOT NULL",
                    "`s_nation` varchar(16) NOT NULL",
                    "`s_region` varchar(13) NOT NULL",
                    "`s_phone` varchar(16) NOT NULL"
            )
    ).withProperties("\"unique_constraints\" = \"s_suppkey\"")
            .withValues("(302, 'Supplier1', '123 Main St', 'City1', 'Nation1', 'Region1', '123-456-7890')");

    public static final MTable PART = new MTable("part", "p_partkey",
            List.of(
                    "`p_partkey` int(11) NOT NULL",
                    "`p_name` varchar(23) NOT NULL",
                    "`p_mfgr` varchar(7) NOT NULL",
                    "`p_category` varchar(8) NOT NULL",
                    "`p_brand` varchar(10) NOT NULL",
                    "`p_color` varchar(12) NOT NULL",
                    "`p_type` varchar(26) NOT NULL",
                    "`p_size` int(11) NOT NULL",
                    "`p_container` varchar(11) NOT NULL"
            )
    ).withProperties("\"unique_constraints\" = \"p_partkey\"")
            .withValues("(202, 'Part1', 'Manufr1', 'Catey1', 'Brand1', 'Red', 'Type1', 10, 'Container1')");
}

