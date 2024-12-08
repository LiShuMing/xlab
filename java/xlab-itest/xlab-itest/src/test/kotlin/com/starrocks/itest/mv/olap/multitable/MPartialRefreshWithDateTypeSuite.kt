package com.starrocks.itest.mv.olap.multitable

import com.starrocks.itest.framework.utils.Util
import org.junit.jupiter.api.AfterAll
import org.junit.jupiter.api.BeforeAll

class MPartialRefreshWithDateTypeSuite : MPartialRefreshSuite() {

    @BeforeAll
    override fun before() {
        super.before()
        // use date column as partition column
        val createTableSql = Util.readContentFromResource("ssb/lineorder_date.sql")
        sql(createTableSql)
    }

    override fun withPartColumnType(): String {
        return "date"
    }

    override fun withMVPartColumn(basePartitionColumnName: String): String {
        return basePartitionColumnName
    }
}