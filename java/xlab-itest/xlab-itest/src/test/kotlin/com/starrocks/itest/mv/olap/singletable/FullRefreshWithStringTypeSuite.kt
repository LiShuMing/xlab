package com.starrocks.itest.mv.olap.singletable

import com.starrocks.itest.framework.utils.Util
import com.starrocks.schema.MMaterializedView
import org.junit.jupiter.api.AfterAll
import org.junit.jupiter.api.BeforeAll
import kotlin.test.Ignore

@Ignore
open class FullRefreshWithStringTypeSuite : FullRefreshSuite() {
    @BeforeAll
    override fun before() {
        super.before()
        val createTableSql = Util.readContentFromResource("ssb/lineorder_string.sql")
        sql(createTableSql)
    }

    @AfterAll
    override fun after() {
        // super.after()
    }

    override fun assertContainsWithMV(defineSql: String, vararg queries: String) {
        val mv = MMaterializedView(DEFAULT_MV_NAME, "str2date(lo_orderdate, '%Y-%m-%d')", defineSql)
            .withPartColumnType("string")
        withCompleteRefreshMV(mv) {
            for (query in queries) {
                assertContains(query, DEFAULT_MV_NAME)
                assertEqualsWithMV(query)
            }
        }
    }
}