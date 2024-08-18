
import os

from pyspark import SparkConf
from pyspark.sql import SparkSession, DataFrame
import pyspark.sql.functions as F
from pyspark.sql import SparkSession

catalog_name = "local"
# warehouse_path = f"s3://{bucket_name}/iceberg"
warehouse_path = f"./tmp/iceberg"

spark = SparkSession.builder \
    .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
    .config(f"spark.sql.catalog.{catalog_name}", "org.apache.iceberg.spark.SparkCatalog") \
    .config(f"spark.sql.catalog.{catalog_name}.type", "hive") \
    .config(f"spark.sql.catalog.{catalog_name}.uri", "thrift://172.26.194.238:9083") \
    .config("spark.jars", "/home/disk1/lishuming/work/spark-3.5.1-bin-hadoop3/jars/iceberg-spark-runtime-3.5_2.12-1.5.1.jar") \
    .getOrCreate()
    # .config(f"spark.sql.catalog.{catalog_name}.warehouse", warehouse_path) \
    # .config(f"spark.sql.catalog.{catalog_name}.catalog-impl", "org.apache.iceberg.aws.glue.GlueCatalog") \
    # .config(f"spark.sql.catalog.{catalog_name}.io-impl", "org.apache.iceberg.aws.s3.S3FileIO") \

spark.sparkContext.setLogLevel('INFO')

spark.sql("use local.sql_test_db")
# spark.sql("show tables").show(truncate=False)

# Create an empty Iceberg table
# query = f"""
# CREATE TABLE {catalog_name}.lism.lineitem_days2 (
#                           l_orderkey    BIGINT,
#                           l_partkey     INT,
#                           l_suppkey     INT,
#                           l_linenumber  INT,
#                           l_quantity    DECIMAL(15, 2),
#                           l_extendedprice  DECIMAL(15, 2),
#                           l_discount    DECIMAL(15, 2),
#                           l_tax         DECIMAL(15, 2),
#                           l_returnflag  VARCHAR(1),
#                           l_linestatus  VARCHAR(1),
#                           l_shipdate    TIMESTAMP,
#                           l_commitdate  TIMESTAMP,
#                           l_receiptdate TIMESTAMP,
#                           l_shipinstruct VARCHAR(25),
#                           l_shipmode     VARCHAR(10),
#                           l_comment      VARCHAR(44)
# ) USING ICEBERG
# PARTITIONED BY (l_returnflag, l_linestatus, days(l_shipdate));
# """
# spark.sql(query)

# spark.sql(f"drop table if exists {catalog_name}.sql_test_db.test_iceberg_with_month")

query = f"""
CREATE TABLE IF NOT EXISTS {catalog_name}.sql_test_db.test_iceberg_with_month(
    prcdate date,
    price double,
    localcode string
) USING ICEBERG
PARTITIONED BY (months(prcdate));
"""
spark.sql(query)


# insert_query = f"""
# insert into test_iceberg_with_month values 
#     (to_date('2025-01-01'), 1.0, 'b'),
#     (to_date('2025-01-02'), 2.0, 'b'),
#     (to_date('2025-02-03'), 3.0, 'b'),
#     (to_date('2025-03-03'), 4.0, 'b'),
#     (to_date('2025-04-01'), 5.0, 'b');
# """
insert_query = f"""
insert into test_iceberg_with_month values 
    (date('2025-01-01'), 1.0, 'b'),
    (date('2025-01-02'), 2.0, 'b'),
    (date('2025-02-03'), 3.0, 'b'),
    (date('2025-03-03'), 4.0, 'b'),
    (date('2025-04-01'), 5.0, 'b');
"""
spark.sql(insert_query) 

# spark.sql("use local.lism")
# spark.sql("show tables").show(truncate=False)

# query_select_files = f"select file_path from {catalog_name}.lism.demo_target_iceberg_add_files.files"
# spark.sql(query_select_files).show(10, truncate=False)

# query_select_snapshots = f"select snapshot_id, manifest_list from {catalog_name}.lism.demo_target_iceberg_add_files.snapshots"
# spark.sql(query_select_snapshots).show(10, truncate=False)

# # Run the add_files procedure
# query = f"""
# call {catalog_name}.system.add_files(
#     table => 'lism.demo_target_iceberg_add_files',
#     source_table => 'lism.demo_source_parquet'
# )
# """
# spark.sql(query).show(truncate=False)

# spark.sql(query_select_files).show(10, truncate=False)
# spark.sql(query_select_snapshots).show(10, truncate=False)

# # add one record
# query = f"""
# insert into {catalog_name}.lism.demo_target_iceberg_add_files
#     select * from lism.demo_source_parquet LIMIT 1
# """
# spark.sql(query)

# spark.sql(query_select_files).show(10, truncate=False)
# spark.sql(query_select_snapshots).show(10, truncate=False)

spark.stop()