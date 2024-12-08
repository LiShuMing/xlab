package com.starrocks.itest.mv.olap.singletable

import com.starrocks.itest.framework.utils.Util
import org.junit.jupiter.api.AfterAll
import org.junit.jupiter.api.BeforeAll
import kotlin.test.Ignore

class PartialRefreshWithIntSuite : PartialRefreshSuite() {

    @BeforeAll
    override fun before() {
        super.before()
        val createTableSql = Util.readContentFromResource("ssb/lineorder_int.sql")
        sql(createTableSql)
    }

    @AfterAll
    override fun after() {
        // super.after()
    }
}