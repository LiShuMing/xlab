-- partsupp_mv
DROP materialized view IF EXISTS partsupp_mv;
create materialized view partsupp_mv
distributed by hash(ps_partkey, ps_suppkey) buckets 24
refresh async
properties (
    "replication_num" = "1"
)
as select
                   n_name,
                   p_mfgr,p_size,p_type,
                   ps_partkey, ps_suppkey,ps_supplycost,
                   r_name,
                   s_acctbal,s_address,s_comment,s_name,s_nationkey,s_phone,
                   ps_supplycost * ps_availqty as ps_partvalue
   from
                   <DB>.partsupp
                       inner join <DB>.supplier
                       inner join <DB>.part
                       inner join <DB>.nation
                       inner join <DB>.region
   where
                   partsupp.ps_suppkey = supplier.s_suppkey
     and partsupp.ps_partkey=part.p_partkey
     and supplier.s_nationkey=nation.n_nationkey
     and nation.n_regionkey=region.r_regionkey;

-- lineitem_mv
DROP materialized view IF EXISTS lineitem_mv;
create materialized view lineitem_mv
distributed by hash(l_shipdate, l_orderkey, l_linenumber) buckets 96
refresh async
properties (
    "replication_num" = "1"
)
as select  /*+ SET_VAR(query_timeout = 7200) */
                   c_address, c_acctbal,c_comment,c_mktsegment,c_name,c_nationkey,c_phone,
                   l_commitdate,l_linenumber,l_extendedprice,l_orderkey,l_partkey,l_quantity,l_receiptdate,l_returnflag,l_shipdate,l_shipinstruct,l_shipmode,l_suppkey,
                   o_custkey,o_orderdate,o_orderpriority,o_orderstatus,o_shippriority,o_totalprice,
                   p_brand,p_container,p_name,p_size,p_type,
                   s_name,s_nationkey,
                   extract(year from l_shipdate) as l_shipyear,
                   l_extendedprice * (1 - l_discount) as l_saleprice,
                   l_extendedprice * (1 - l_discount) - ps_supplycost * l_quantity as l_amount,
                   ps_supplycost * l_quantity as l_supplycost,
                   extract(year from o_orderdate) as o_orderyear,
                   s_nation.n_name as n_name1,
                   s_nation.n_regionkey as n_regionkey1,
                   c_nation.n_name as n_name2,
                   c_nation.n_regionkey as n_regionkey2,
                   s_region.r_name as r_name1,
                   c_region.r_name as r_name2
   from
           <DB>.lineitem
                       inner join <DB>.partsupp
                       inner join <DB>.orders
                       inner join <DB>.supplier
                       inner join <DB>.part
                       inner join <DB>.customer
                       inner join <DB>.nation as s_nation
                       inner join <DB>.nation as c_nation
                       inner join <DB>.region as s_region
                       inner join <DB>.region as c_region
   where
                   lineitem.l_partkey=partsupp.ps_partkey
     and lineitem.l_suppkey=partsupp.ps_suppkey
     and lineitem.l_orderkey=orders.o_orderkey
     and partsupp.ps_partkey=part.p_partkey
     and partsupp.ps_suppkey=supplier.s_suppkey
     and customer.c_custkey=orders.o_custkey
     and supplier.s_nationkey=s_nation.n_nationkey
     and customer.c_nationkey=c_nation.n_nationkey
     and s_region.r_regionkey=s_nation.n_regionkey
     and c_region.r_regionkey=c_nation.n_regionkey
;

-- query1
-- query9?
DROP materialized view IF EXISTS lineitem_agg_mv1;
create materialized view lineitem_agg_mv1
distributed by hash(l_orderkey,
               l_shipdate,
               l_returnflag,
               l_linestatus) buckets 96
refresh async
properties (
    "replication_num" = "1"
)
as select  /*+ SET_VAR(query_timeout = 7200) */
                   l_orderkey,
                   l_shipdate,
                   l_returnflag,
                   l_linestatus,
                   sum(l_quantity) as sum_qty,
                   count(l_quantity) as count_qty,
                   sum(l_extendedprice) as sum_base_price,
                   count(l_extendedprice) as count_base_price,
                   sum(l_discount) as sum_discount,
                   count(l_discount) as count_discount,
                   sum(l_extendedprice * (1 - l_discount)) as sum_disc_price,
                   sum(l_extendedprice * (1 - l_discount) * (1 + l_tax)) as sum_charge,
                   count(*) as count_order
   from
           <DB>.lineitem
   group by
       l_orderkey,
       l_shipdate,
       l_returnflag,
       l_linestatus
;

-- query 15,20
DROP materialized view IF EXISTS lineitem_agg_mv2;
create materialized view lineitem_agg_mv2
distributed by hash(l_suppkey, l_shipdate, l_partkey) buckets 96
refresh async
properties (
    "replication_num" = "1"
)
as select  /*+ SET_VAR(query_timeout = 7200) */
                   l_suppkey, l_shipdate, l_partkey,
                   sum(l_quantity) as sum_qty,
                   count(l_quantity) as count_qty,
                   sum(l_extendedprice) as sum_base_price,
                   count(l_extendedprice) as count_base_price,
                   sum(l_discount) as sum_discount,
                   count(l_discount) as count_discount,
                   sum(l_extendedprice * (1 - l_discount)) as sum_disc_price,
                   sum(l_extendedprice * (1 - l_discount) * (1 + l_tax)) as sum_charge
   from
           <DB>.lineitem
   group by
       l_suppkey, l_shipdate, l_partkey
;

DROP materialized view IF EXISTS lineitem_agg_mv3;
create materialized view lineitem_agg_mv3
distributed by hash(l_shipdate, l_discount, l_quantity) buckets 24
refresh async
properties (
    "replication_num" = "1"
)
as select  /*+ SET_VAR(query_timeout = 7200) */
                   l_shipdate, l_discount, l_quantity,
                   sum(l_extendedprice * l_discount) as revenue
   from
           <DB>.lineitem
   group by
       l_shipdate, l_discount, l_quantity
;


-- customer_order_mv (used to match query22)
-- query22 needs avg & rollup -> sum/count
DROP materialized view IF EXISTS customer_agg_mv1;
create materialized view customer_agg_mv1
distributed by hash(c_custkey) buckets 24
refresh async
properties (
    "replication_num" = "1"
)
as select
                   c_custkey,
                   c_phone,
                   c_acctbal,
                   substring(c_phone, 1  ,2) as substring_phone,
                   count(c_acctbal) as c_count,
                   sum(c_acctbal) as c_sum
   from
           <DB>.customer
   group by c_custkey, c_phone, c_acctbal, substring(c_phone, 1  ,2);

-- query13
DROP materialized view IF EXISTS customer_order_mv_agg_mv1;
create materialized view customer_order_mv_agg_mv1
distributed by hash( c_custkey,
       o_comment) buckets 24
refresh async
properties (
    "replication_num" = "1"
)
as select
                   c_custkey,
                   o_comment,
                   count(o_orderkey) as c_count,
                   count(1) as c_count_star
   from
                   (select
                        c_custkey,o_comment,o_orderkey
                    from
                            <DB>.customer
                            left outer join
                            <DB>.orders
                        on orders.o_custkey=customer.c_custkey) a
   group by
       c_custkey,
       o_comment
;

-- query9
DROP materialized view IF EXISTS lineitem_mv_agg_mv1;
create materialized view lineitem_mv_agg_mv1
 distributed by hash(p_name,
               o_orderyear,
               n_name1) buckets 96
 refresh async
 properties (
     "replication_num" = "1"
 )
 as select /*+ SET_VAR(query_timeout = 7200) */
                    p_name,
                    o_orderyear,
                    n_name1,
                    sum(l_amount) as sum_amount
    from
            lineitem_mv
    group by
        p_name,
        o_orderyear,
        n_name1
;

-- query7
DROP materialized view IF EXISTS lineitem_mv_agg_mv2;
create materialized view lineitem_mv_agg_mv2
 distributed by hash(l_shipdate,
        n_name1,
        n_name2,
        l_shipyear) buckets 96
 refresh async
 properties (
     "replication_num" = "1"
 )
 as select /*+ SET_VAR(query_timeout = 7200) */
                    l_shipdate,
                    n_name1,
                    n_name2,
                    l_shipyear,
                    sum(l_saleprice) as sum_saleprice
    from
            lineitem_mv
    group by
        l_shipdate,
        n_name1,
        n_name2,
        l_shipyear
;

-- query4
DROP materialized view IF EXISTS query4_mv;
create materialized view query4_mv
 distributed by hash(o_orderdate,
    o_orderpriority) buckets 24
 refresh async
 properties (
     "replication_num" = "1"
 )
as select
                   o_orderdate,
                   o_orderpriority,
                   count(*) as order_count
   from
           <DB>.orders
   where
                   exists (
                       select
                           *
                       from
                           <DB>.lineitem
                       where
                           l_orderkey = o_orderkey
                         and l_receiptdate > l_commitdate
                   )
   group by
       o_orderdate,
       o_orderpriority;

-- query21
DROP materialized view IF EXISTS query21_mv;
create materialized view query21_mv
distributed by hash(s_name,
              o_orderstatus,
              n_name) buckets 24
refresh async
properties (
    "replication_num" = "1"
)
as select
                   s_name,
                   o_orderstatus,
                   n_name,
                   count(*) as cnt_star
   from
           <DB>.supplier,
           <DB>.lineitem l1,
           <DB>.orders,
           <DB>.nation
   where
                   s_suppkey = l1.l_suppkey
     and o_orderkey = l1.l_orderkey
     and l1.l_receiptdate > l1.l_commitdate
     and exists (
       select
           *
       from
       <DB>.lineitem l2
       where
           l2.l_orderkey = l1.l_orderkey
         and l2.l_suppkey <> l1.l_suppkey
   )
     and not exists (
       select
           *
       from
       <DB>.lineitem l3
       where
           l3.l_orderkey = l1.l_orderkey
         and l3.l_suppkey <> l1.l_suppkey
         and l3.l_receiptdate > l3.l_commitdate
   )
     and s_nationkey = n_nationkey
   group by s_name,
            o_orderstatus,
            n_name;
