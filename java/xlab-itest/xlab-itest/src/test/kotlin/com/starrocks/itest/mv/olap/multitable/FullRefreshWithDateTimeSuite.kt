package com.starrocks.itest.mv.olap.multitable

import com.starrocks.itest.framework.MVSuite
import com.starrocks.itest.framework.utils.Util
import org.junit.jupiter.api.BeforeAll
import kotlin.test.Test

class FullRefreshWithDateTimeSuite : MVSuite() {
    @BeforeAll
    override fun before() {
        super.before()

        // create base tables
        val createTableSql = Util.readContentFromResource("ssb/create_table.sql")
        sql(createTableSql)

        // add constraints
        val addConstraintsSql = Util.readContentFromResource("ssb/add_constraints.sql")
        sql(addConstraintsSql)

        // mock data
        val insertDataSql = Util.readContentFromResource("ssb/insert.sql")
        sql(insertDataSql)
    }

    @Test
    fun testSubQuery() {
        val sql = """
            create materialized view mv0
            distributed by random
            partition by lo_orderdate
            as
            select
                p_brand,
                LO_ORDERDATE,
                sum(LO_REVENUE) as revenue_sum
                from
                    lineorder l
                 left join part p on l.LO_PARTKEY = p.P_PARTKEY
                group by
                 p_brand,
         LO_ORDERDATE;
        """.trimIndent()
        sql(sql)
        refreshMV("mv0")

        val query = """
            select
            t1.p_brand as p_brand,
            t1.LO_ORDERDATE as LO_ORDERDATE,
            SUM(revenue_sum) + SUM(supplycost_sum) as revenue_and_supplycost_sum
            from
            (
            select
            p_brand,
            LO_ORDERDATE,
            sum(LO_REVENUE) as revenue_sum
            from
            lineorder l
            left join part p on l.LO_PARTKEY = p.P_PARTKEY
            group by
            p_brand,
            LO_ORDERDATE
            ) t1
            inner join (
            select
            p_brand,
            LO_ORDERDATE,
            sum(LO_SUPPLYCOST) as supplycost_sum
            from
            lineorder l
            left join part p on l.LO_PARTKEY = p.P_PARTKEY
            group by
            p_brand,
            LO_ORDERDATE
            ) t2 on t1.p_brand = t2.p_brand
            and t1.LO_ORDERDATE = t2.LO_ORDERDATE
            group by
            t1.p_brand,
            t1.LO_ORDERDATE;
        """.trimIndent()
        assertContains(query, "mv0")
    }

    @Test
    fun testMvOnMv() {
        val mv1 = """
        CREATE MATERIALIZED VIEW mv2_subquery_1 REFRESH ASYNC every (interval 10 minute) AS
        select lo_orderkey, lo_custkey, p_partkey, p_name
        from lineorder join part on lo_partkey = p_partkey;
    """.trimIndent()

        val mv2 = """
           CREATE MATERIALIZED VIEW mv2_subquery_2 REFRESH ASYNC every (interval 10 minute) AS
           select c_custkey from customer group by c_custkey; 
        """.trimIndent()

        sql(mv1)
        sql(mv2)
        refreshMV("mv2_subquery_1")
        refreshMV("mv2_subquery_2")

        val mv3 = """
            CREATE MATERIALIZED VIEW mv2_2 REFRESH ASYNC every (interval 10 minute) AS
            select *
            from mv2_subquery_1 lo
            join mv2_subquery_2 cust
            on lo.lo_custkey = cust.c_custkey;
        """.trimIndent()
        sql(mv3)
        refreshMV("mv2_2")

        assertContains("select *\n" +
                "from (\n" +
                "    select lo_orderkey, lo_custkey, p_partkey, p_name\n" +
                "    from lineorder\n" +
                "    join part on lo_partkey = p_partkey\n" +
                ") lo\n" +
                "join (\n" +
                "    select c_custkey\n" +
                "    from customer\n" +
                "    group by c_custkey\n" +
                ") cust\n" +
                "on lo.lo_custkey = cust.c_custkey;", "mv2_2")
    }
}