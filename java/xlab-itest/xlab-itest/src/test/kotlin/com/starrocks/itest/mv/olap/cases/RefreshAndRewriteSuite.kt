package com.starrocks.itest.mv.olap.cases

import com.starrocks.itest.framework.MVSuite
import com.starrocks.itest.framework.utils.Util
import com.starrocks.schema.MMaterializedView
import org.junit.jupiter.api.BeforeAll
import kotlin.concurrent.thread
import kotlin.test.Test

class RefreshAndRewriteSuite: MVSuite() {
    @BeforeAll
    override fun before() {
        super.before()
        val createTableSql = Util.readContentFromResource("ssb/lineorder_datetime.sql")
        sql(createTableSql)
    }

    @Test
    fun testMVRewriteWithRefresh() {
        val mvName = DEFAULT_MV_NAME

        val sql = """
            select lo_orderdate, count(1), 
            bitmap_union(to_bitmap(lo_orderkey)), 
            bitmap_union(to_bitmap(lo_linenumber)), 
            bitmap_union(to_bitmap(lo_custkey)), 
            bitmap_union(to_bitmap(lo_suppkey)) 
            from lineorder 
            group by lo_orderdate
        """.trimIndent()
        val mv = MMaterializedView(mvName, "lo_orderdate", sql)
        sql(mv.createTableSql)
        refreshMV(mvName)
        sql("ALTER MATERIALIZED VIEW ${mvName} SET (\"mv_rewrite_staleness_second\" = \"120\");\n")
        sql("ALTER MATERIALIZED VIEW ${mvName} SET (\"query_rewrite_consistency\" = \"LOOSE\");")

        sql("set cbo_cte_reuse=false;")

        var query = """
            select lo_orderdate, count(1), count(distinct lo_orderkey), count(distinct lo_linenumber), 
            count(distinct lo_custkey), count(distinct lo_suppkey)
            from lineorder group by lo_orderdate
        """.trimIndent()
        assertContains(query, mvName)
        query = """
            select lo_orderdate, count(1), count(distinct lo_orderkey), count(distinct lo_linenumber), 
            count(distinct lo_custkey), count(distinct lo_suppkey)
            from lineorder  where lo_orderdate = '1993-01-01' group by lo_orderdate;
        """.trimIndent()
        assertContains(query, mvName)
    }

    @Test
    fun testPrimaryKey() {
       sql("""
           CREATE TABLE `test_realtime_operation_venue_detail_metrics_hour` (
             `venue_id` bigint(20) NOT NULL COMMENT "会场id",
             `spu_id` bigint(20) NOT NULL COMMENT "商品id",
             `user_id` bigint(20) NOT NULL COMMENT "用户id",
             `component_id` bigint(20) NOT NULL COMMENT "组件id",
             `component_type_desc` varchar(128) NOT NULL COMMENT "组件类型名称",
             `url_source_name` varchar(128) NOT NULL COMMENT "渠道名称",
             `channel_type` varchar(128) NOT NULL COMMENT "渠道类型",
             `date` date NOT NULL COMMENT "日期[2023-08-15]",
             `hour` varchar(128) NOT NULL COMMENT "小时[09]",
             `pt` date NOT NULL COMMENT "时间分区yyyyMMdd",
             `venue_title` varchar(128) NULL COMMENT "会场title",
             `spu_title` varchar(128) NULL COMMENT "spu名称",
             `brand_name` varchar(128) NULL COMMENT "品牌",
             `category_lv1_name` varchar(128) NULL COMMENT "商品类目1级",
             `gender` varchar(128) NULL COMMENT "性别",
             `city_level` varchar(128) NULL COMMENT "城市等级",
             `user_type` varchar(128) NULL COMMENT "用户类型",
             `access_pv` bigint(20) NULL COMMENT "访问PV",
             `clk_pv` bigint(20) NULL COMMENT "点击PV",
             `exp_pv` bigint(20) NULL COMMENT "曝光PV",
             `duration` bigint(20) NULL COMMENT "时长/毫秒",
             `detail_access_pv` bigint(20) NULL COMMENT "商详PV",
             `collect_success_pv` bigint(20) NULL COMMENT "收藏成功PV",
             `direct_gmv` bigint(20) NULL COMMENT "直接GMV/分",
             `update_time` bigint(20) NULL COMMENT "更新时间"
           ) ENGINE=OLAP 
           PRIMARY KEY(`venue_id`, `spu_id`, `user_id`, `component_id`, `component_type_desc`, `url_source_name`, `channel_type`, `date`, `hour`, `pt`)
           COMMENT "会场测试表"
           PARTITION BY RANGE(`pt`)
           (PARTITION p20240120 VALUES [("2024-01-20"), ("2024-01-21")),
           PARTITION p20240121 VALUES [("2024-01-21"), ("2024-01-22")),
           PARTITION p20240122 VALUES [("2024-01-22"), ("2024-01-23")),
           PARTITION p20240123 VALUES [("2024-01-23"), ("2024-01-24")),
           PARTITION p20240124 VALUES [("2024-01-24"), ("2024-01-25")),
           PARTITION p20240125 VALUES [("2024-01-25"), ("2024-01-26")),
           PARTITION p20240126 VALUES [("2024-01-26"), ("2024-01-27")),
           PARTITION p20240127 VALUES [("2024-01-27"), ("2024-01-28")),
           PARTITION p20240128 VALUES [("2024-01-28"), ("2024-01-29")),
           PARTITION p20240129 VALUES [("2024-01-29"), ("2024-01-30")),
           PARTITION p20240130 VALUES [("2024-01-30"), ("2024-01-31")),
           PARTITION p20240131 VALUES [("2024-01-31"), ("2024-02-01")),
           PARTITION p20240201 VALUES [("2024-02-01"), ("2024-02-02")))
           DISTRIBUTED BY HASH(`venue_id`, `spu_id`, `user_id`, `component_id`, `component_type_desc`, `url_source_name`, `channel_type`, `date`, `hour`, `pt`) BUCKETS 3 
           PROPERTIES (
           "replication_num" = "1",
           "compression" = "LZ4"
           );
       """.trimIndent())

        sql("""
            INSERT INTO test_realtime_operation_venue_detail_metrics_hour (venue_id, spu_id, user_id, component_id, component_type_desc, url_source_name, channel_type, date, hour, pt, venue_title, spu_title, brand_name, category_lv1_name, gender, city_level, user_type, access_pv, clk_pv, exp_pv, duration, detail_access_pv, collect_success_pv, direct_gmv, update_time)
            VALUES (1, 101, 1001, 201, 'ComponentA', 'SourceA', 'ChannelA', '2023-08-15', '09', '2024-01-20', 'VenueA', 'SpuA', 'BrandA', 'CategoryA', 'Male', 'Tier1', 'Registered', 500, 100, 200, 5000, 50, 10, 200, 1643445600000);

            -- Sample 2
            INSERT INTO test_realtime_operation_venue_detail_metrics_hour (venue_id, spu_id, user_id, component_id, component_type_desc, url_source_name, channel_type, date, hour, pt, venue_title, spu_title, brand_name, category_lv1_name, gender, city_level, user_type, access_pv, clk_pv, exp_pv, duration, detail_access_pv, collect_success_pv, direct_gmv, update_time)
            VALUES (2, 102, 1002, 202, 'ComponentB', 'SourceB', 'ChannelB', '2023-08-15', '10', '2024-01-20', 'VenueB', 'SpuB', 'BrandB', 'CategoryB', 'Female', 'Tier2', 'Guest', 600, 120, 220, 6000, 60, 12, 220, 1643449200000);

            -- Sample 3
            INSERT INTO test_realtime_operation_venue_detail_metrics_hour (venue_id, spu_id, user_id, component_id, component_type_desc, url_source_name, channel_type, date, hour, pt, venue_title, spu_title, brand_name, category_lv1_name, gender, city_level, user_type, access_pv, clk_pv, exp_pv, duration, detail_access_pv, collect_success_pv, direct_gmv, update_time)
            VALUES (3, 103, 1003, 203, 'ComponentC', 'SourceC', 'ChannelC', '2023-08-15', '11', '2024-01-20', 'VenueC', 'SpuC', 'BrandC', 'CategoryC', 'Male', 'Tier3', 'Registered', 700, 140, 240, 7000, 70, 14, 240, 1643452800000);
        """.trimIndent())

        sql("""
             CREATE MATERIALIZED VIEW `test_realtime_operation_venue_detail_metrics_hour_mv` (`pt`, `channel_type`, `user_type`, `hour`, `count_distinct_im_uv`, `count_distinct_im_uv_OverTime60`, `count_distinct_im_uv_im_user_online`, `count_distinct_im_uv_im_user_drill`, `count_distinct_im_uv_im_user_rest`, `count_distinct_im_uv_im_user_eat`, `count_distinct_im_uv_im_user_busy`, `count_distinct_im_uv_im_user_offline`, `count_distinct_im_uv_overTime15`, `count_distinct_im_repc_cnt`, `sum_im_relation_sum`, `sum_im_work_time_sum`, `count_distinct_im_avg_qps`, `count_distinct_im_conversation_cnt`, `sum_im_relation_sum_im_user_oarticipation_evaluation`)
COMMENT "MATERIALIZED_VIEW"
PARTITION BY (`pt`)
DISTRIBUTED BY HASH(`hour`)
REFRESH ASYNC START("2024-01-27 10:00:00") EVERY(INTERVAL 60 MINUTE)
PROPERTIES (
"replicated_storage" = "true",
"replication_num" = "1"
)
AS SELECT  `test_realtime_operation_venue_detail_metrics_hour`.`pt`
       ,`test_realtime_operation_venue_detail_metrics_hour`.`channel_type`
       ,`test_realtime_operation_venue_detail_metrics_hour`.`user_type`
       ,`test_realtime_operation_venue_detail_metrics_hour`.`hour`
       ,bitmap_union(to_bitmap(`test_realtime_operation_venue_detail_metrics_hour`.`user_id`))      AS `count_distinct_im_uv`
       ,bitmap_union(to_bitmap(CASE WHEN (`test_realtime_operation_venue_detail_metrics_hour`.`hour` >= '01') THEN `test_realtime_operation_venue_detail_metrics_hour`.`user_id` ELSE NULL END)) AS `count_distinct_im_uv_OverTime60`
       ,bitmap_union(to_bitmap(CASE WHEN (`test_realtime_operation_venue_detail_metrics_hour`.`user_type` = '新客') THEN `test_realtime_operation_venue_detail_metrics_hour`.`user_id` ELSE NULL END)) AS `count_distinct_im_uv_im_user_online`
       ,bitmap_union(to_bitmap(CASE WHEN (`test_realtime_operation_venue_detail_metrics_hour`.`user_type` = '高频人群') THEN `test_realtime_operation_venue_detail_metrics_hour`.`user_id` ELSE NULL END)) AS `count_distinct_im_uv_im_user_drill`
       ,bitmap_union(to_bitmap(CASE WHEN (`test_realtime_operation_venue_detail_metrics_hour`.`user_type` = '低频人群') THEN `test_realtime_operation_venue_detail_metrics_hour`.`user_id` ELSE NULL END)) AS `count_distinct_im_uv_im_user_rest`
       ,bitmap_union(to_bitmap(CASE WHEN (`test_realtime_operation_venue_detail_metrics_hour`.`user_type` = '中频人群') THEN `test_realtime_operation_venue_detail_metrics_hour`.`user_id` ELSE NULL END)) AS `count_distinct_im_uv_im_user_eat`
       ,bitmap_union(to_bitmap(CASE WHEN (`test_realtime_operation_venue_detail_metrics_hour`.`user_type` = '流失人群') THEN `test_realtime_operation_venue_detail_metrics_hour`.`user_id` ELSE NULL END)) AS `count_distinct_im_uv_im_user_busy`
       ,bitmap_union(to_bitmap(CASE WHEN (`test_realtime_operation_venue_detail_metrics_hour`.`user_type` = '0单-非濒临流失') THEN `test_realtime_operation_venue_detail_metrics_hour`.`user_id` ELSE NULL END)) AS `count_distinct_im_uv_im_user_offline`
       ,bitmap_union(to_bitmap(CASE WHEN (`test_realtime_operation_venue_detail_metrics_hour`.`hour` >= '02') THEN `test_realtime_operation_venue_detail_metrics_hour`.`user_id` ELSE NULL END)) AS `count_distinct_im_uv_overTime15`
       ,bitmap_union(to_bitmap(`test_realtime_operation_venue_detail_metrics_hour`.`component_id`)) AS `count_distinct_im_repc_cnt`
       ,SUM(`test_realtime_operation_venue_detail_metrics_hour`.`access_pv`)                        AS `sum_im_relation_sum`
       ,SUM(`test_realtime_operation_venue_detail_metrics_hour`.`duration`)                         AS `sum_im_work_time_sum`
       ,bitmap_union(to_bitmap(`test_realtime_operation_venue_detail_metrics_hour`.`spu_id`))       AS `count_distinct_im_avg_qps`
       ,bitmap_union(to_bitmap(`test_realtime_operation_venue_detail_metrics_hour`.`venue_id`))     AS `count_distinct_im_conversation_cnt`
       ,SUM(CASE WHEN (`test_realtime_operation_venue_detail_metrics_hour`.`channel_type` = '站内') THEN `test_realtime_operation_venue_detail_metrics_hour`.`access_pv` ELSE NULL END) AS `sum_im_relation_sum_im_user_oarticipation_evaluation`
FROM `test_realtime_operation_venue_detail_metrics_hour`
GROUP BY `test_realtime_operation_venue_detail_metrics_hour`.`pt`, `test_realtime_operation_venue_detail_metrics_hour`.`channel_type`, `test_realtime_operation_venue_detail_metrics_hour`.`user_type`, `test_realtime_operation_venue_detail_metrics_hour`.`hour`;
        """.trimIndent())

        sql("""
            ALTER MATERIALIZED VIEW test_realtime_operation_venue_detail_metrics_hour_mv SET ("mv_rewrite_staleness_second" = "120");
        """.trimIndent())
        sql("""
            ALTER MATERIALIZED VIEW test_realtime_operation_venue_detail_metrics_hour_mv SET ("query_rewrite_consistency" = "LOOSE");
        """.trimIndent())
        sql("""
            ALTER MATERIALIZED VIEW test_realtime_operation_venue_detail_metrics_hour_mv REFRESH ASYNC START('2024-01-27 10:00:00') EVERY (interval 1 minute);
        """.trimIndent())

        val mvName = "test_realtime_operation_venue_detail_metrics_hour_mv"
        val thread1 = thread(true) {
            var i = 0L
            while (i < 200) {
                assertContains("select channel_type ,count(distinct user_id) as count_distinct_im_uv\n" +
                        "from test_realtime_operation_venue_detail_metrics_hour \n" +
                        "where pt = '20240120'\n" +
                        "group by channel_type", mvName)
                Thread.sleep(1000)
                i++
            }
        }

        val thread2 = thread(true) {
            var i = 0L
            while (i < 100) {
                sql("""
INSERT INTO test_realtime_operation_venue_detail_metrics_hour (venue_id, spu_id, user_id, component_id, component_type_desc, url_source_name, channel_type, date, hour, pt, venue_title, spu_title, brand_name, category_lv1_name, gender, city_level, user_type, access_pv, clk_pv, exp_pv, duration, detail_access_pv, collect_success_pv, direct_gmv, update_time)
VALUES (1, 101, 1001, 201, 'ComponentA', 'SourceA', 'ChannelA', '2023-08-15', '09', '2024-01-30', 'VenueA', 'SpuA', 'BrandA', 'CategoryA', 'Male', 'Tier1', 'Registered', 500, 100, 200, 5000, 50, 10, 200, 1643445600000);

INSERT INTO test_realtime_operation_venue_detail_metrics_hour (venue_id, spu_id, user_id, component_id, component_type_desc, url_source_name, channel_type, date, hour, pt, venue_title, spu_title, brand_name, category_lv1_name, gender, city_level, user_type, access_pv, clk_pv, exp_pv, duration, detail_access_pv, collect_success_pv, direct_gmv, update_time)
VALUES (2, 102, 1002, 202, 'ComponentB', 'SourceB', 'ChannelB', '2023-08-15', '10', '2024-01-20', 'VenueB', 'SpuB', 'BrandB', 'CategoryB', 'Female', 'Tier2', 'Guest', 600, 120, 220, 6000, 60, 12, 220, 1643449200000);

INSERT INTO test_realtime_operation_venue_detail_metrics_hour (venue_id, spu_id, user_id, component_id, component_type_desc, url_source_name, channel_type, date, hour, pt, venue_title, spu_title, brand_name, category_lv1_name, gender, city_level, user_type, access_pv, clk_pv, exp_pv, duration, detail_access_pv, collect_success_pv, direct_gmv, update_time)
VALUES (3, 103, 1003, 203, 'ComponentC', 'SourceC', 'ChannelC', '2023-08-15', '11', '2024-01-20', 'VenueC', 'SpuC', 'BrandC', 'CategoryC', 'Male', 'Tier3', 'Registered', 700, 140, 240, 7000, 70, 14, 240, 1643452800000);
        """.trimIndent())
                Thread.sleep(2000)
                i++
            }
        }
        val threads = arrayOf(thread1, thread2)
        for (thread in threads) {
            thread.join()
        }
    }
}