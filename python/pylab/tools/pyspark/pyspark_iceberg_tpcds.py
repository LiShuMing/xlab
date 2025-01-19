
import os

from datetime import datetime, timedelta
import random
from decimal import Decimal

from pyspark import SparkConf
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import lit

from pyspark.sql import SparkSession
from pyspark.sql.types import *

catalog_name = "local"
warehouse_path = f"./tmp/iceberg"
target_iceberg_table = f"{catalog_name}.sql_test_db.iceberg_lineitem_utc_1000"
target_database = f"{catalog_name}.iceberg_partitioned_tpcds_1g_sql_test_db"

tpcds_ddl = f"""
drop table if exists {target_database}.call_center;
create table if not exists {target_database}.call_center
(
    cc_call_center_sk         integer               not null,
    cc_call_center_id         char(16)              not null,
    cc_rec_start_date         date                          ,
    cc_rec_end_date           date                          ,
    cc_closed_date_sk         integer                       ,
    cc_open_date_sk           integer                       ,
    cc_name                   varchar(50)                   ,
    cc_class                  varchar(50)                   ,
    cc_employees              integer                       ,
    cc_sq_ft                  integer                       ,
    cc_hours                  char(20)                      ,
    cc_manager                varchar(40)                   ,
    cc_mkt_id                 integer                       ,
    cc_mkt_class              char(50)                      ,
    cc_mkt_desc               varchar(100)                  ,
    cc_market_manager         varchar(40)                   ,
    cc_division               integer                       ,
    cc_division_name          varchar(50)                   ,
    cc_company                integer                       ,
    cc_company_name           char(50)                      ,
    cc_street_number          char(10)                      ,
    cc_street_name            varchar(60)                   ,
    cc_street_type            char(15)                      ,
    cc_suite_number           char(10)                      ,
    cc_city                   varchar(60)                   ,
    cc_county                 varchar(30)                   ,
    cc_state                  char(2)                       ,
    cc_zip                    char(10)                      ,
    cc_country                varchar(20)                   ,
    cc_gmt_offset             decimal(5,2)                  ,
    cc_tax_percentage         decimal(5,2)
) USING ICEBERG;

create table if not exists {target_database}.catalog_page
(
    cp_catalog_page_sk        integer               not null,
    cp_catalog_page_id        char(16)              not null,
    cp_start_date_sk          integer                       ,
    cp_end_date_sk            integer                       ,
    cp_department             varchar(50)                   ,
    cp_catalog_number         integer                       ,
    cp_catalog_page_number    integer                       ,
    cp_description            varchar(100)                  ,
    cp_type                   varchar(100)
) USING ICEBERG;

create table  if not exists {target_database}.catalog_returns
(
    cr_item_sk                integer               not null,
    cr_order_number           integer               not null,
    cr_returned_date_sk       integer                       ,
    cr_returned_time_sk       integer                       ,
    cr_refunded_customer_sk   integer                       ,
    cr_refunded_cdemo_sk      integer                       ,
    cr_refunded_hdemo_sk      integer                       ,
    cr_refunded_addr_sk       integer                       ,
    cr_returning_customer_sk  integer                       ,
    cr_returning_cdemo_sk     integer                       ,
    cr_returning_hdemo_sk     integer                       ,
    cr_returning_addr_sk      integer                       ,
    cr_call_center_sk         integer                       ,
    cr_catalog_page_sk        integer                       ,
    cr_ship_mode_sk           integer                       ,
    cr_warehouse_sk           integer                       ,
    cr_reason_sk              integer                       ,
    cr_return_quantity        integer                       ,
    cr_return_amount          decimal(7,2)                  ,
    cr_return_tax             decimal(7,2)                  ,
    cr_return_amt_inc_tax     decimal(7,2)                  ,
    cr_fee                    decimal(7,2)                  ,
    cr_return_ship_cost       decimal(7,2)                  ,
    cr_refunded_cash          decimal(7,2)                  ,
    cr_reversed_charge        decimal(7,2)                  ,
    cr_store_credit           decimal(7,2)                  ,
    cr_net_loss               decimal(7,2)
) USING ICEBERG 
PARTITIONED BY (cr_returned_date_sk);

create table  if not exists {target_database}.catalog_sales
(
    cs_item_sk                integer               not null,
    cs_order_number           integer               not null,
    cs_sold_date_sk           integer                       ,
    cs_sold_time_sk           integer                       ,
    cs_ship_date_sk           integer                       ,
    cs_bill_customer_sk       integer                       ,
    cs_bill_cdemo_sk          integer                       ,
    cs_bill_hdemo_sk          integer                       ,
    cs_bill_addr_sk           integer                       ,
    cs_ship_customer_sk       integer                       ,
    cs_ship_cdemo_sk          integer                       ,
    cs_ship_hdemo_sk          integer                       ,
    cs_ship_addr_sk           integer                       ,
    cs_call_center_sk         integer                       ,
    cs_catalog_page_sk        integer                       ,
    cs_ship_mode_sk           integer                       ,
    cs_warehouse_sk           integer                       ,
    cs_promo_sk               integer                       ,
    cs_quantity               integer                       ,
    cs_wholesale_cost         decimal(7,2)                  ,
    cs_list_price             decimal(7,2)                  ,
    cs_sales_price            decimal(7,2)                  ,
    cs_ext_discount_amt       decimal(7,2)                  ,
    cs_ext_sales_price        decimal(7,2)                  ,
    cs_ext_wholesale_cost     decimal(7,2)                  ,
    cs_ext_list_price         decimal(7,2)                  ,
    cs_ext_tax                decimal(7,2)                  ,
    cs_coupon_amt             decimal(7,2)                  ,
    cs_ext_ship_cost          decimal(7,2)                  ,
    cs_net_paid               decimal(7,2)                  ,
    cs_net_paid_inc_tax       decimal(7,2)                  ,
    cs_net_paid_inc_ship      decimal(7,2)                  ,
    cs_net_paid_inc_ship_tax  decimal(7,2)                  ,
    cs_net_profit             decimal(7,2)
)USING ICEBERG 
PARTITIONED BY (cs_sold_date_sk);

create table  if not exists {target_database}.customer_address
(
    ca_address_sk             integer               not null,
    ca_address_id             char(16)              not null,
    ca_street_number          char(10)                      ,
    ca_street_name            varchar(60)                   ,
    ca_street_type            char(15)                      ,
    ca_suite_number           char(10)                      ,
    ca_city                   varchar(60)                   ,
    ca_county                 varchar(30)                   ,
    ca_state                  char(2)                       ,
    ca_zip                    char(10)                      ,
    ca_country                varchar(20)                   ,
    ca_gmt_offset             decimal(5,2)                  ,
    ca_location_type          char(20)
) USING ICEBERG;

create table  if not exists {target_database}.customer_demographics
(
    cd_demo_sk                integer  not null,
    cd_gender                 char(1)  not null,
    cd_marital_status         char(1)  not null,
    cd_education_status       char(20) not null,
    cd_purchase_estimate      integer  not null,
    cd_credit_rating          char(10) not null,
    cd_dep_count              integer  not null,
    cd_dep_employed_count     integer  not null,
    cd_dep_college_count      integer  not null
) USING ICEBERG;

create table  if not exists {target_database}.customer
(
    c_customer_sk             integer               not null,
    c_customer_id             char(16)              not null,
    c_current_cdemo_sk        integer                       ,
    c_current_hdemo_sk        integer                       ,
    c_current_addr_sk         integer                       ,
    c_first_shipto_date_sk    integer                       ,
    c_first_sales_date_sk     integer                       ,
    c_salutation              char(10)                      ,
    c_first_name              char(20)                      ,
    c_last_name               char(30)                      ,
    c_preferred_cust_flag     char(1)                       ,
    c_birth_day               integer                       ,
    c_birth_month             integer                       ,
    c_birth_year              integer                       ,
    c_birth_country           varchar(20)                   ,
    c_login                   char(13)                      ,
    c_email_address           char(50)                      ,
    c_last_review_date        char(10)
) USING ICEBERG;

create table  if not exists {target_database}.date_dim
(
    d_date_sk                 integer   not null,
    d_date_id                 char(16)  not null,
    d_date                    date      not null,
    d_month_seq               integer   not null,
    d_week_seq                integer   not null,
    d_quarter_seq             integer   not null,
    d_year                    integer   not null,
    d_dow                     integer   not null,
    d_moy                     integer   not null,
    d_dom                     integer   not null,
    d_qoy                     integer   not null,
    d_fy_year                 integer   not null,
    d_fy_quarter_seq          integer   not null,
    d_fy_week_seq             integer   not null,
    d_day_name                char(9)   not null,
    d_quarter_name            char(6)   not null,
    d_holiday                 char(1)   not null,
    d_weekend                 char(1)   not null,
    d_following_holiday       char(1)   not null,
    d_first_dom               integer   not null,
    d_last_dom                integer   not null,
    d_same_day_ly             integer   not null,
    d_same_day_lq             integer   not null,
    d_current_day             char(1)   not null,
    d_current_week            char(1)   not null,
    d_current_month           char(1)   not null,
    d_current_quarter         char(1)   not null,
    d_current_year            char(1)   not null
) USING ICEBERG;

create table  if not exists {target_database}.household_demographics
(
    hd_demo_sk                integer  not null,
    hd_income_band_sk         integer  not null,
    hd_buy_potential          char(15) not null,
    hd_dep_count              integer  not null,
    hd_vehicle_count          integer  not null
) USING ICEBERG;

create table  if not exists {target_database}.income_band
(
    ib_income_band_sk         integer               not null,
    ib_lower_bound            integer                       ,
    ib_upper_bound            integer
) USING ICEBERG;

create table  if not exists {target_database}.inventory
(
    inv_item_sk               integer               not null,
    inv_date_sk               integer               not null,
    inv_warehouse_sk          integer               not null,
    inv_quantity_on_hand      integer
) USING ICEBERG;

create table  if not exists {target_database}.item
(
    i_item_sk                 integer               not null,
    i_item_id                 char(16)              not null,
    i_rec_start_date          date                          ,
    i_rec_end_date            date                          ,
    i_item_desc               varchar(200)                  ,
    i_current_price           decimal(7,2)                  ,
    i_wholesale_cost          decimal(7,2)                  ,
    i_brand_id                integer                       ,
    i_brand                   char(50)                      ,
    i_class_id                integer                       ,
    i_class                   char(50)                      ,
    i_category_id             integer                       ,
    i_category                char(50)                      ,
    i_manufact_id             integer                       ,
    i_manufact                char(50)                      ,
    i_size                    char(20)                      ,
    i_formulation             char(20)                      ,
    i_color                   char(20)                      ,
    i_units                   char(10)                      ,
    i_container               char(10)                      ,
    i_manager_id              integer                       ,
    i_product_name            char(50)
) USING ICEBERG;

create table  if not exists {target_database}.promotion
(
    p_promo_sk                integer               not null,
    p_promo_id                char(16)              not null,
    p_start_date_sk           integer                       ,
    p_end_date_sk             integer                       ,
    p_item_sk                 integer                       ,
    p_cost                    decimal(15,2)                 ,
    p_response_target         integer                       ,
    p_promo_name              char(50)                      ,
    p_channel_dmail           char(1)                       ,
    p_channel_email           char(1)                       ,
    p_channel_catalog         char(1)                       ,
    p_channel_tv              char(1)                       ,
    p_channel_radio           char(1)                       ,
    p_channel_press           char(1)                       ,
    p_channel_event           char(1)                       ,
    p_channel_demo            char(1)                       ,
    p_channel_details         varchar(100)                  ,
    p_purpose                 char(15)                      ,
    p_discount_active         char(1)
) USING ICEBERG;

create table  if not exists {target_database}.reason
(
    r_reason_sk               integer               not null,
    r_reason_id               char(16)              not null,
    r_reason_desc             char(100)
) USING ICEBERG;

create table  if not exists {target_database}.ship_mode
(
    sm_ship_mode_sk           integer               not null,
    sm_ship_mode_id           char(16)              not null,
    sm_type                   char(30)                      ,
    sm_code                   char(10)                      ,
    sm_carrier                char(20)                      ,
    sm_contract               char(20)
) USING ICEBERG;

create table  if not exists {target_database}.store_returns
(
    sr_item_sk                integer               not null,
    sr_ticket_number          integer               not null,
    sr_returned_date_sk       integer                       ,
    sr_return_time_sk         integer                       ,
    sr_customer_sk            integer                       ,
    sr_cdemo_sk               integer                       ,
    sr_hdemo_sk               integer                       ,
    sr_addr_sk                integer                       ,
    sr_store_sk               integer                       ,
    sr_reason_sk              integer                       ,
    sr_return_quantity        integer                       ,
    sr_return_amt             decimal(7,2)                  ,
    sr_return_tax             decimal(7,2)                  ,
    sr_return_amt_inc_tax     decimal(7,2)                  ,
    sr_fee                    decimal(7,2)                  ,
    sr_return_ship_cost       decimal(7,2)                  ,
    sr_refunded_cash          decimal(7,2)                  ,
    sr_reversed_charge        decimal(7,2)                  ,
    sr_store_credit           decimal(7,2)                  ,
    sr_net_loss               decimal(7,2)
)USING ICEBERG 
PARTITIONED BY (sr_returned_date_sk);


create table  if not exists {target_database}.store_sales
(
    ss_item_sk                integer               not null,
    ss_ticket_number          integer               not null,
    ss_sold_date_sk           integer                       ,
    ss_sold_time_sk           integer                       ,
    ss_customer_sk            integer                       ,
    ss_cdemo_sk               integer                       ,
    ss_hdemo_sk               integer                       ,
    ss_addr_sk                integer                       ,
    ss_store_sk               integer                       ,
    ss_promo_sk               integer                       ,
    ss_quantity               integer                       ,
    ss_wholesale_cost         decimal(7,2)                  ,
    ss_list_price             decimal(7,2)                  ,
    ss_sales_price            decimal(7,2)                  ,
    ss_ext_discount_amt       decimal(7,2)                  ,
    ss_ext_sales_price        decimal(7,2)                  ,
    ss_ext_wholesale_cost     decimal(7,2)                  ,
    ss_ext_list_price         decimal(7,2)                  ,
    ss_ext_tax                decimal(7,2)                  ,
    ss_coupon_amt             decimal(7,2)                  ,
    ss_net_paid               decimal(7,2)                  ,
    ss_net_paid_inc_tax       decimal(7,2)                  ,
    ss_net_profit             decimal(7,2)
) USING ICEBERG 
PARTITIONED BY (ss_sold_date_sk);

create table  if not exists {target_database}.store
(
    s_store_sk                integer               not null,
    s_store_id                char(16)              not null,
    s_rec_start_date          date                          ,
    s_rec_end_date            date                          ,
    s_closed_date_sk          integer                       ,
    s_store_name              varchar(50)                   ,
    s_number_employees        integer                       ,
    s_floor_space             integer                       ,
    s_hours                   char(20)                      ,
    s_manager                 varchar(40)                   ,
    s_market_id               integer                       ,
    s_geography_class         varchar(100)                  ,
    s_market_desc             varchar(100)                  ,
    s_market_manager          varchar(40)                   ,
    s_division_id             integer                       ,
    s_division_name           varchar(50)                   ,
    s_company_id              integer                       ,
    s_company_name            varchar(50)                   ,
    s_street_number           varchar(10)                   ,
    s_street_name             varchar(60)                   ,
    s_street_type             char(15)                      ,
    s_suite_number            char(10)                      ,
    s_city                    varchar(60)                   ,
    s_county                  varchar(30)                   ,
    s_state                   char(2)                       ,
    s_zip                     char(10)                      ,
    s_country                 varchar(20)                   ,
    s_gmt_offset              decimal(5,2)                  ,
    s_tax_precentage          decimal(5,2)
) USING ICEBERG;

create table  if not exists {target_database}.time_dim
(
    t_time_sk                 integer               not null,
    t_time_id                 char(16)              not null,
    t_time                    integer               not null,
    t_hour                    integer               not null,
    t_minute                  integer               not null,
    t_second                  integer               not null,
    t_am_pm                   char(2)               not null,
    t_shift                   char(20)              not null,
    t_sub_shift               char(20)              not null,
    t_meal_time               char(20)
) USING ICEBERG;

create table  if not exists {target_database}.warehouse
(
    w_warehouse_sk            integer               not null,
    w_warehouse_id            char(16)              not null,
    w_warehouse_name          varchar(20)                   ,
    w_warehouse_sq_ft         integer                       ,
    w_street_number           char(10)                      ,
    w_street_name             varchar(60)                   ,
    w_street_type             char(15)                      ,
    w_suite_number            char(10)                      ,
    w_city                    varchar(60)                   ,
    w_county                  varchar(30)                   ,
    w_state                   char(2)                       ,
    w_zip                     char(10)                      ,
    w_country                 varchar(20)                   ,
    w_gmt_offset              decimal(5,2)
) USING ICEBERG;

create table  if not exists {target_database}.web_page
(
    wp_web_page_sk            integer               not null,
    wp_web_page_id            char(16)              not null,
    wp_rec_start_date         date                          ,
    wp_rec_end_date           date                          ,
    wp_creation_date_sk       integer                       ,
    wp_access_date_sk         integer                       ,
    wp_autogen_flag           char(1)                       ,
    wp_customer_sk            integer                       ,
    wp_url                    varchar(100)                  ,
    wp_type                   char(50)                      ,
    wp_char_count             integer                       ,
    wp_link_count             integer                       ,
    wp_image_count            integer                       ,
    wp_max_ad_count           integer
) USING ICEBERG;

create table  if not exists {target_database}.web_returns
(
    wr_item_sk                integer               not null,
    wr_order_number           integer               not null,
    wr_returned_date_sk       integer                       ,
    wr_returned_time_sk       integer                       ,
    wr_refunded_customer_sk   integer                       ,
    wr_refunded_cdemo_sk      integer                       ,
    wr_refunded_hdemo_sk      integer                       ,
    wr_refunded_addr_sk       integer                       ,
    wr_returning_customer_sk  integer                       ,
    wr_returning_cdemo_sk     integer                       ,
    wr_returning_hdemo_sk     integer                       ,
    wr_returning_addr_sk      integer                       ,
    wr_web_page_sk            integer                       ,
    wr_reason_sk              integer                       ,
    wr_return_quantity        integer                       ,
    wr_return_amt             decimal(7,2)                  ,
    wr_return_tax             decimal(7,2)                  ,
    wr_return_amt_inc_tax     decimal(7,2)                  ,
    wr_fee                    decimal(7,2)                  ,
    wr_return_ship_cost       decimal(7,2)                  ,
    wr_refunded_cash          decimal(7,2)                  ,
    wr_reversed_charge        decimal(7,2)                  ,
    wr_account_credit         decimal(7,2)                  ,
    wr_net_loss               decimal(7,2)
) USING ICEBERG 
PARTITIONED BY (wr_returned_date_sk);


create table  if not exists {target_database}.web_sales
(
    ws_item_sk                integer               not null,
    ws_order_number           integer               not null,
    ws_sold_date_sk           integer                       ,
    ws_sold_time_sk           integer                       ,
    ws_ship_date_sk           integer                       ,
    ws_bill_customer_sk       integer                       ,
    ws_bill_cdemo_sk          integer                       ,
    ws_bill_hdemo_sk          integer                       ,
    ws_bill_addr_sk           integer                       ,
    ws_ship_customer_sk       integer                       ,
    ws_ship_cdemo_sk          integer                       ,
    ws_ship_hdemo_sk          integer                       ,
    ws_ship_addr_sk           integer                       ,
    ws_web_page_sk            integer                       ,
    ws_web_site_sk            integer                       ,
    ws_ship_mode_sk           integer                       ,
    ws_warehouse_sk           integer                       ,
    ws_promo_sk               integer                       ,
    ws_quantity               integer                       ,
    ws_wholesale_cost         decimal(7,2)                  ,
    ws_list_price             decimal(7,2)                  ,
    ws_sales_price            decimal(7,2)                  ,
    ws_ext_discount_amt       decimal(7,2)                  ,
    ws_ext_sales_price        decimal(7,2)                  ,
    ws_ext_wholesale_cost     decimal(7,2)                  ,
    ws_ext_list_price         decimal(7,2)                  ,
    ws_ext_tax                decimal(7,2)                  ,
    ws_coupon_amt             decimal(7,2)                  ,
    ws_ext_ship_cost          decimal(7,2)                  ,
    ws_net_paid               decimal(7,2)                  ,
    ws_net_paid_inc_tax       decimal(7,2)                  ,
    ws_net_paid_inc_ship      decimal(7,2)                  ,
    ws_net_paid_inc_ship_tax  decimal(7,2)                  ,
    ws_net_profit             decimal(7,2)
)USING ICEBERG 
PARTITIONED BY (ws_sold_date_sk);


create table  if not exists {target_database}.web_site
(
    web_site_sk               integer               not null,
    web_site_id               char(16)              not null,
    web_rec_start_date        date                          ,
    web_rec_end_date          date                          ,
    web_name                  varchar(50)                   ,
    web_open_date_sk          integer                       ,
    web_close_date_sk         integer                       ,
    web_class                 varchar(50)                   ,
    web_manager               varchar(40)                   ,
    web_mkt_id                integer                       ,
    web_mkt_class             varchar(50)                   ,
    web_mkt_desc              varchar(100)                  ,
    web_market_manager        varchar(40)                   ,
    web_company_id            integer                       ,
    web_company_name          char(50)                      ,
    web_street_number         char(10)                      ,
    web_street_name           varchar(60)                   ,
    web_street_type           char(15)                      ,
    web_suite_number          char(10)                      ,
    web_city                  varchar(60)                   ,
    web_county                varchar(30)                   ,
    web_state                 char(2)                       ,
    web_zip                   char(10)                      ,
    web_country               varchar(20)                   ,
    web_gmt_offset            decimal(5,2)                  ,
    web_tax_percentage        decimal(5,2)
) USING ICEBERG;
"""
def get_spark_session():
    spark = SparkSession.builder \
        .appName("Large Dataset Processing") \
        .config("spark.executor.memory", "8g") \
        .config("spark.executor.cores", "4") \
        .config("spark.sql.shuffle.partitions", "50") \
        .config("spark.memory.fraction", "0.8") \
        .config("spark.memory.storageFraction", "0.6") \
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
        .config(f"spark.sql.catalog.{catalog_name}", "org.apache.iceberg.spark.SparkCatalog") \
        .config(f"spark.sql.catalog.{catalog_name}.type", "hive") \
        .config(f"spark.sql.catalog.{catalog_name}.uri", "thrift://172.26.194.238:9083") \
        .config("spark.sql.session.timeZone", "UTC") \
        .config("spark.jars", "/home/disk1/lishuming/work/spark-3.5.1-bin-hadoop3/jars/iceberg-spark-runtime-3.5_2.12-1.5.1.jar") \
        .getOrCreate()

    spark.conf.set("parquet.block.size", 128 * 1024 * 1024)  # 设置为 128MB
    spark.conf.set("parquet.page.size", 1 * 1024 * 1024)     # 设置为 1MB
    spark.conf.set("iceberg.write.target-file-size-bytes", 128 * 1024 * 1024)  # 每个文件最大128MB
    spark.conf.set("iceberg.write.parquet.row-group-size-bytes", 8 * 1024 * 1024)  # 每个RowGroup最大8MB
    spark.sparkContext.setLogLevel('INFO')
    return spark

'''
see issue: https://github.com/apache/iceberg/issues/3494
'''
def create_table(spark: SparkSession, table_name: str):
    query = f"""
    CREATE TABLE IF NOT EXISTS {table_name}(
                          l_orderkey    BIGINT,
                          l_partkey     INT,
                          l_suppkey     INT,
                          l_linenumber  INT,
                          l_quantity    DECIMAL(15, 2),
                          l_extendedprice  DECIMAL(15, 2),
                          l_discount    DECIMAL(15, 2),
                          l_tax         DECIMAL(15, 2),
                          l_commitdate  timestamp_ntz,
                          l_receiptdate timestamp_ntz,
                          l_shipinstruct VARCHAR(25),
                          l_shipmode     VARCHAR(10),
                          l_comment      VARCHAR(44),
                          l_returnflag  VARCHAR(1),
                          l_linestatus  VARCHAR(1),
                          l_shipdate    timestamp_ntz
    ) USING ICEBERG
    PARTITIONED BY (l_returnflag, l_linestatus, days(l_shipdate));
    """
    spark.sql(query)


# 定义表的架构
def generate_data(year: int):
    start_date = datetime(year, 1, 1)  # 数据起始日期
    end_date = datetime(year, 12, 31)  # 数据结束日期
    add_days = 370
    data = []
    for i in range(0, add_days):  # 生成10万条数据
        # ship_date = start_date + timedelta(days=random.randint(0, random_days))
        ship_date = start_date + timedelta(days=i)
        if ship_date > end_date:
            break
        commit_date = ship_date + timedelta(days=random.randint(1, 10))
        receipt_date = commit_date + timedelta(days=random.randint(1, 5))
        data.append((
            random.randint(1, 1000000),   # l_orderkey
            random.randint(1, 100000),    # l_partkey
            random.randint(1, 50000),     # l_suppkey
            random.randint(1, 10),        # l_linenumber
            Decimal(round(random.uniform(1, 100), 2)),  # l_quantity
            Decimal(round(random.uniform(10, 1000), 2)),  # l_extendedprice
            Decimal(round(random.uniform(0, 0.1), 2)),   # l_discount
            Decimal(round(random.uniform(0, 0.2), 2)),   # l_tax
            random.choice(['A', 'B', 'C']),     # l_returnflag
            random.choice(['O', 'F']),          # l_linestatus
            ship_date,                          # l_shipdate
            commit_date,                        # l_commitdate
            receipt_date,                       # l_receiptdate
            random.choice(['DELIVER IN PERSON', 'COLLECT FROM STORE']),  # l_shipinstruct
            random.choice(['AIR', 'RAIL', 'TRUCK']),                    # l_shipmode
            "Generated comment {}".format(i)    # l_comment
        ))
    return data

def write_data(spark: SparkSession, data: list, schema: StructType, table_name: str):
    df = spark.createDataFrame(data, schema)
    df.write \
        .format("iceberg") \
        .mode("append") \
        .option("iceberg.write.timezone", "UTC") \
        .save(f"{table_name}")

def create_table_and_generate_data(spark: SparkSession, year: int, is_drop_table: bool = True):
    # create table
    if is_drop_table:
        spark.sql(f"DROP TABLE IF EXISTS {target_iceberg_table}")
    create_table(spark, target_iceberg_table)

def create_tpch_tables(spark: SparkSession):
    for ddl in tpcds_ddl.split(";"):
        if ddl.strip() != "":
            print(ddl)
            spark.sql(ddl)
if __name__ == "__main__":
    # create spark session
    spark = get_spark_session()
    create_tpch_tables(spark)
    spark.stop()

    table_names = ["call_center", "catalog_page", "catalog_returns", "catalog_sales", "customer_address", "customer_demographics", "customer", "date_dim", "household_demographics", "income_band", "inventory", "item", "promotion", "reason", "ship_mode", "store_returns", "store_sales", "store", "time_dim", "warehouse", "web_page", "web_returns", "web_sales", "web_site"]  
    for table_name in table_names:
        sql = f"insert into iceberg.iceberg_partitioned_tpcds_1g_sql_test_db.{table_name} select * from iceberg.iceberg_tpcds_1g_parquet_snappy.{table_name};"
        print(sql)