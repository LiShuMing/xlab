package com.starrocks.itest.mv.olap.singletable

import com.starrocks.itest.framework.PartialRefreshParam
import com.starrocks.itest.framework.utils.Util
import com.starrocks.schema.MMaterializedView
import org.junit.jupiter.api.AfterAll
import org.junit.jupiter.api.BeforeAll

class PartialRefreshWithDatetimeSuite : PartialRefreshSuite() {
    @BeforeAll
    override fun before() {
        super.before()
        val createTableSql = Util.readContentFromResource("ssb/lineorder_datetime.sql")
        sql(createTableSql)
    }

    @AfterAll
    override fun after() {
        // super.after()
    }

    override fun assertContainsWithMV(defineSql: String, param: PartialRefreshParam, vararg queries: String) {
        val newDefineSql = defineSql.replace(PREDICATE_PLACEHOLDER, "true")
        val mv = MMaterializedView(DEFAULT_MV_NAME, "lo_orderdate", newDefineSql)
        withPartialRefreshMV(mv, param.start, param.end) {
            for (query in queries) {
                for (pred in param.predicates) {
                    val newQuery = query.replace(PREDICATE_PLACEHOLDER, pred)
                    assertContains(newQuery, DEFAULT_MV_NAME)
                    assertEqualsWithMV(newQuery)
                }
            }
        }
    }
}