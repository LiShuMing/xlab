package com.starrocks.itest.mv.olap.singletable

import com.starrocks.itest.framework.utils.Util
import org.junit.jupiter.api.AfterAll
import org.junit.jupiter.api.BeforeAll

class PartialRefreshWithDateTypeSuite : PartialRefreshSuite() {

    @BeforeAll
    override fun before() {
        super.before()
        // use date column as partition column
        val createTableSql = Util.readContentFromResource("ssb/lineorder_date.sql")
        sql(createTableSql)
    }

    @AfterAll
    override fun after() {
        // super.after()
    }
}