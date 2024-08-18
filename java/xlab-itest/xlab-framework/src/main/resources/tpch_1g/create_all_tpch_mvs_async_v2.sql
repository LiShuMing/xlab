-- partsupp_mv_c0
DROP materialized view IF EXISTS partsupp_mv_c0;
create materialized view partsupp_mv_c0
distributed by random
refresh async
properties (
    "replication_num" = "1"
)
as select
                   n_name,
                   count(1) as cnt
   from
                   <DB>.partsupp_mv
   group by n_name;

DROP materialized view IF EXISTS partsupp_mv_c0_c0;
create materialized view partsupp_mv_c0_c0
distributed by random
refresh async
properties (
    "replication_num" = "1"
)
as select sum(1) as sum_cnt from <DB>.partsupp_mv;

DROP materialized view IF EXISTS lineitem_agg_mv1_c0;
create materialized view lineitem_agg_mv1_c0
distributed by random
refresh async
properties (
    "replication_num" = "1"
)
as select l_shipdate, count(1) as cnt from <DB>.lineitem_agg_mv1 group by l_shipdate;

-- query 15,20
DROP materialized view IF EXISTS lineitem_agg_mv2_c0;
create materialized view lineitem_agg_mv2_c0
distributed by random
refresh async
as select l_shipdate, count(1) as cnt from <DB>.lineitem_agg_mv2 group by l_shipdate;

DROP materialized view IF EXISTS lineitem_agg_mv3_c0;
create materialized view lineitem_agg_mv3_c0
distributed by random
refresh async
as select l_shipdate, count(1) as cnt from <DB>.lineitem_agg_mv2 group by l_shipdate
   union all
    select l_shipdate, count(1) as cnt from test_tpch_1g.lineitem group by l_shipdate;
