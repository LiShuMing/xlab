package com.starrocks.itest.mv.olap.multitable

import com.starrocks.itest.framework.utils.Util
import org.junit.jupiter.api.BeforeAll

class MFullRefreshWithDateTypeSuite : MFullRefreshSuite() {
    @BeforeAll
    override fun before() {
        super.before()
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