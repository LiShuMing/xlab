
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
# warehouse_path = f"s3://{bucket_name}/iceberg"
warehouse_path = f"./tmp/iceberg"

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
    .config("spark.jars", "/home/disk1/lishuming/work/spark-3.5.1-bin-hadoop3/jars/iceberg-spark-runtime-3.5_2.12-1.5.1.jar") \
    .getOrCreate()
    # .config("spark.jars", "/root/work/spark-3.5.1-bin-hadoop3/jars/iceberg-spark-runtime-3.5_2.12-1.5.1.jar") \
    # .config(f"spark.sql.catalog.{catalog_name}.warehouse", warehouse_path) \
    # .config(f"spark.sql.catalog.{catalog_name}.catalog-impl", "org.apache.iceberg.aws.glue.GlueCatalog") \
    # .config(f"spark.sql.catalog.{catalog_name}.io-impl", "org.apache.iceberg.aws.s3.S3FileIO") \

spark.conf.set("parquet.block.size", 128 * 1024 * 1024)  # 设置为 128MB
spark.conf.set("parquet.page.size", 1 * 1024 * 1024)     # 设置为 1MB
spark.conf.set("iceberg.write.target-file-size-bytes", 128 * 1024 * 1024)  # 每个文件最大128MB
spark.conf.set("iceberg.write.parquet.row-group-size-bytes", 8 * 1024 * 1024)  # 每个RowGroup最大8MB
# spark.conf.set("spark.executor.extraJavaOptions", "-Xmx4g")  
spark.sparkContext.setLogLevel('INFO')

spark.sql("use local.lism")
spark.sql("show tables").show(truncate=False)

# Create an empty Iceberg table
query = f"""
CREATE TABLE IF NOT EXISTS {catalog_name}.lism.lineitem_days1 (
                          l_orderkey    BIGINT,
                          l_partkey     INT,
                          l_suppkey     INT,
                          l_linenumber  INT,
                          l_quantity    DECIMAL(15, 2),
                          l_extendedprice  DECIMAL(15, 2),
                          l_discount    DECIMAL(15, 2),
                          l_tax         DECIMAL(15, 2),
                          l_returnflag  VARCHAR(1),
                          l_linestatus  VARCHAR(1),
                          l_shipdate    TIMESTAMP,
                          l_commitdate  TIMESTAMP,
                          l_receiptdate TIMESTAMP,
                          l_shipinstruct VARCHAR(25),
                          l_shipmode     VARCHAR(10),
                          l_comment      VARCHAR(44)
) USING ICEBERG
PARTITIONED BY (l_returnflag, l_linestatus, days(l_shipdate));
"""
spark.sql(query)

# 定义表的架构
schema = StructType([
    StructField("l_orderkey", LongType(), False),
    StructField("l_partkey", IntegerType(), False),
    StructField("l_suppkey", IntegerType(), False),
    StructField("l_linenumber", IntegerType(), False),
    StructField("l_quantity", DecimalType(15, 2), False),
    StructField("l_extendedprice", DecimalType(15, 2), False),
    StructField("l_discount", DecimalType(15, 2), False),
    StructField("l_tax", DecimalType(15, 2), False),
    StructField("l_returnflag", StringType(), False),
    StructField("l_linestatus", StringType(), False),
    StructField("l_shipdate", TimestampType(), False),
    StructField("l_commitdate", TimestampType(), False),
    StructField("l_receiptdate", TimestampType(), False),
    StructField("l_shipinstruct", StringType(), False),
    StructField("l_shipmode", StringType(), False),
    StructField("l_comment", StringType(), False)
])

def generate_data():
    data = []
    start_date = datetime(2023, 1, 1)  # 数据起始日期
    end_date = datetime(2023, 12, 31)  # 数据结束日期

    for i in range(1, 10):  # 生成10万条数据
        ship_date = start_date + timedelta(days=random.randint(0, 364))
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

data = generate_data()
df = spark.createDataFrame(data, schema)

df.write \
    .format("iceberg") \
    .mode("append") \
    .save("local.lism.lineitem_days1")

spark.sql("""
SELECT COUNT(*) AS total_rows FROM local.lism.lineitem_days1
""").show()

spark.sql("""
SELECT l_returnflag, COUNT(*) AS count FROM local.lism.lineitem_days1
GROUP BY l_returnflag
""").show()
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