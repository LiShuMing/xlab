package com.starrocks.itest.benchmark.tpcds

import com.starrocks.itest.framework.MVSuite
import com.starrocks.itest.framework.utils.Util
import org.junit.jupiter.api.AfterAll
import org.junit.jupiter.api.BeforeAll
import kotlin.test.Test

class TPCDSWithMVBench : MVSuite()  {
    @BeforeAll
    override fun before() {
        super.before()
        val createTableSql = Util.readContentFromResource("tpcds/create_table.sql")
        sql(createTableSql)
    }

    @AfterAll
    override fun after() {
//        super.after()
    }

    @Test
    fun testQueries() {
        val mv = "CREATE MATERIALIZED VIEW __mv (_ca0005, d_year, c_customer_id, c_first_name, c_last_name, c_preferred_cust_flag, c_birth_country, c_login, c_email_address)\n" +
                "DISTRIBUTED BY HASH (d_year, c_customer_id, c_first_name, c_last_name, c_preferred_cust_flag, c_birth_country, c_login, c_email_address)\n" +
                "REFRESH ASYNC START(\"2023-12-01 10:00:00\") EVERY(INTERVAL 1 DAY)\n" +
                "PROPERTIES (\n" +
                "  \"replicated_storage\" = \"true\",\n" +
                "  \"replication_num\" = \"1\",\n" +
                "  \"storage_medium\" = \"HDD\"\n" +
                ")\n" +
                "AS\n" +
                "SELECT\n" +
                "  (sum(_ta0001._ca0002)) AS _ca0005\n" +
                "  ,_ta0001.d_year\n" +
                "  ,_ta0001.c_customer_id\n" +
                "  ,_ta0001.c_first_name\n" +
                "  ,_ta0001.c_last_name\n" +
                "  ,_ta0001.c_preferred_cust_flag\n" +
                "  ,_ta0001.c_birth_country\n" +
                "  ,_ta0001.c_login\n" +
                "  ,_ta0001.c_email_address\n" +
                "FROM\n" +
                "  (\n" +
                "    SELECT\n" +
                "      customer.c_email_address\n" +
                "      ,customer.c_customer_id\n" +
                "      ,(((((store_sales.ss_ext_list_price - store_sales.ss_ext_wholesale_cost) - store_sales.ss_ext_discount_amt) + store_sales.ss_ext_sales_price) / 2)) AS _ca0002\n" +
                "      ,customer.c_first_name\n" +
                "      ,customer.c_last_name\n" +
                "      ,customer.c_preferred_cust_flag\n" +
                "      ,customer.c_birth_country\n" +
                "      ,date_dim.d_year\n" +
                "      ,customer.c_login\n" +
                "    FROM\n" +
                "      customer\n" +
                "      INNER JOIN\n" +
                "      store_sales\n" +
                "      ON (customer.c_customer_sk = store_sales.ss_customer_sk)\n" +
                "      INNER JOIN\n" +
                "      date_dim\n" +
                "      ON (store_sales.ss_sold_date_sk = date_dim.d_date_sk)\n" +
                "  ) _ta0001\n" +
                "GROUP BY\n" +
                "  _ta0001.d_year\n" +
                "  , _ta0001.c_customer_id\n" +
                "  , _ta0001.c_first_name\n" +
                "  , _ta0001.c_last_name\n" +
                "  , _ta0001.c_preferred_cust_flag\n" +
                "  , _ta0001.c_birth_country\n" +
                "  , _ta0001.c_login\n" +
                "  , _ta0001.c_email_address;"
        sql(mv)
    }
}