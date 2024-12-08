package com.starrocks.itest.mv.olap.singletable

import com.starrocks.itest.framework.utils.Util
import com.starrocks.schema.MMaterializedView
import org.junit.jupiter.api.BeforeAll

class FullRefreshWithDateTypeSuite : FullRefreshSuite() {
    @BeforeAll
    override fun before() {
        super.before()
        val createTableSql = Util.readContentFromResource("ssb/lineorder_date.sql")
        sql(createTableSql)
    }
    override fun assertContainsWithMV(defineSql: String, vararg queries: String) {
        val mv = MMaterializedView(DEFAULT_MV_NAME, "lo_orderdate", defineSql)
            .withPartColumnType("date")

        withCompleteRefreshMV(mv) {
            for (query in queries) {
                assertContains(query, DEFAULT_MV_NAME)
                assertEqualsWithMV(query)
            }
        }
    }
}