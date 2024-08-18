
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
target_iceberg_table = f"{catalog_name}.iceberg_partitioned_tpch_1g_sql_test_db.iceberg_lineitem_utc_1000"
target_database = f"{catalog_name}.iceberg_partitioned_tpch_1g_sql_test_db"

tpch_ddl = f"""
CREATE TABLE  IF NOT EXISTS  {target_database}.supplier (
    s_suppkey INTEGER,
    s_name STRING,
    s_address STRING,
    s_nationkey INTEGER,
    s_phone STRING,
    s_acctbal NUMERIC,
    s_comment STRING
) USING ICEBERG;

CREATE TABLE  IF NOT EXISTS  {target_database}.part (
    p_partkey INTEGER,
    p_name STRING,
    p_mfgr STRING,
    p_brand STRING,
    p_type STRING,
    p_size INTEGER,
    p_container STRING,
    p_retailprice NUMERIC,
    p_comment STRING
) USING ICEBERG;

CREATE TABLE  IF NOT EXISTS  {target_database}.partsupp (
    ps_partkey INTEGER,
    ps_suppkey INTEGER,
    ps_availqty INTEGER,
    ps_supplycost NUMERIC,
    ps_comment STRING
);

CREATE TABLE  IF NOT EXISTS  {target_database}.customer (
    c_custkey INTEGER,
    c_name STRING,
    c_address STRING,
    c_nationkey INTEGER,
    c_phone STRING,
    c_acctbal NUMERIC,
    c_mktsegment STRING,
    c_comment STRING
) USING ICEBERG;

CREATE TABLE  IF NOT EXISTS  {target_database}.orders (
    o_orderkey BIGINT,
    o_custkey INTEGER,
    o_orderstatus STRING,
    o_totalprice NUMERIC,
    o_orderdate DATE,
    o_orderpriority STRING,
    o_clerk STRING,
    o_shippriority INTEGER,
    o_comment STRING
) USING ICEBERG 
PARTITIONED BY (o_orderdate);

CREATE TABLE  IF NOT EXISTS {target_database}.lineitem (
    l_orderkey BIGINT,
    l_partkey INTEGER,
    l_suppkey INTEGER,
    l_linenumber INTEGER,
    l_quantity NUMERIC,
    l_extendedprice NUMERIC,
    l_discount NUMERIC,
    l_tax NUMERIC,
    l_returnflag STRING,
    l_linestatus STRING,
    l_shipdate DATE,
    l_commitdate DATE,
    l_receiptdate DATE,
    l_shipinstruct STRING,
    l_shipmode STRING,
    l_comment STRING
) USING ICEBERG 
PARTITIONED BY (l_shipdate);

CREATE TABLE  IF NOT EXISTS  {target_database}.nation (
    n_nationkey INTEGER,
    n_name STRING,
    n_regionkey INTEGER,
    n_comment STRING
) USING ICEBERG;

CREATE TABLE  IF NOT EXISTS  {target_database}.region (
    r_regionkey INTEGER,
    r_name STRING,
    r_comment STRING
) USING ICEBERG;
"""

# INSERT INTO {target_database}.supplier select * from local.iceberg_tpch_1g_parquet_lz4.supplier;
# INSERT INTO {target_database}.part select * from local.iceberg_tpch_1g_parquet_lz4.part;
# INSERT INTO {target_database}.partsupp select * from local.iceberg_tpch_1g_parquet_lz4.partsupp;
# INSERT INTO {target_database}.customer select * from local.iceberg_tpch_1g_parquet_lz4.customer;
# INSERT INTO {target_database}.orders select * from local.iceberg_tpch_1g_parquet_lz4.orders;
dml_sql = f"""
INSERT INTO {target_database}.lineitem select * from local.iceberg_tpch_1g_parquet_lz4.lineitem;
INSERT INTO {target_database}.nation select * from local.iceberg_tpch_1g_parquet_lz4.nation;
INSERT INTO {target_database}.region select * from local.iceberg_tpch_1g_parquet_lz4.region;
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
        # .config("spark.master", "yarn") \
        # .config("spark.submit.deployMode", "cluster") \
        # .config("spark.hadoop.yarn.resourcemanager.address", "172.26.194.238:8032") \
        # .config("spark.hadoop.fs.defaultFS", "hdfs://172.26.194.238:9000") \


    spark.conf.set("parquet.block.size", 128 * 1024 * 1024)  # 设置为 128MB
    spark.conf.set("parquet.page.size", 1 * 1024 * 1024)     # 设置为 1MB
    spark.conf.set("iceberg.write.target-file-size-bytes", 128 * 1024 * 1024)  # 每个文件最大128MB
    spark.conf.set("iceberg.write.parquet.row-group-size-bytes", 8 * 1024 * 1024)  # 每个RowGroup最大8MB
    spark.sparkContext.setLogLevel('INFO')
    return spark

def create_tpch_tables(spark: SparkSession):
    for ddl in tpch_ddl.split(";"):
        if ddl.strip() != "":
            print(ddl)
            spark.sql(ddl)
def write_tpch_tables(spark: SparkSession):
    for ddl in dml_sql.split(";"):
        if ddl.strip() != "":
            print(ddl)
            spark.sql(ddl)
if __name__ == "__main__":
    # create spark session
    spark = get_spark_session()
    # write_tpch_tables(spark)
    create_tpch_tables(spark)

    table_names = ["supplier", "part", "partsupp", "customer", "orders", "lineitem", "nation", "region"]
    for table_name in table_names:
        sql = f"insert into iceberg.iceberg_partitioned_tpch_1g_sql_test_db.{table_name} select * from iceberg.iceberg_tpch_1g_parquet_snappy.{table_name};"
        print(sql)
    # spark.stop()