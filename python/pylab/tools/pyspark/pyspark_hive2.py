
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
warehouse_path = f"./tmp/hive"
target_hive_table = f"sql_test_db.hive_lineitem_1000"

def get_spark_session():
    spark = SparkSession.builder \
        .appName("Large Dataset Processing") \
        .config("spark.executor.memory", "8g") \
        .config("spark.executor.cores", "4") \
        .config("spark.sql.shuffle.partitions", "50") \
        .config("spark.memory.fraction", "0.8") \
        .config("spark.memory.storageFraction", "0.6") \
        .config("spark.sql.catalogImplementation", "hive") \
        .config("hive.metastore.uris", "thrift://172.26.194.238:9083") \
        .enableHiveSupport() \
        .getOrCreate()

    spark.conf.set("parquet.block.size", 128 * 1024 * 1024)  # 设置为 128MB
    spark.conf.set("parquet.page.size", 1 * 1024 * 1024)     # 设置为 1MB
    spark.sparkContext.setLogLevel('INFO')
    spark.conf.set("hive.exec.dynamic.partition", "true")
    spark.conf.set("hive.exec.dynamic.partition.mode", "nonstrict")
    return spark

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
                            l_commitdate  TIMESTAMP,
                            l_receiptdate TIMESTAMP,
                            l_shipinstruct VARCHAR(25),
                            l_shipmode     VARCHAR(10),
                            l_comment      VARCHAR(44),
                            l_returnflag  VARCHAR(1),
                            l_linestatus  VARCHAR(1),
                            l_shipdate    TIMESTAMP
    ) USING HIVE
    PARTITIONED BY (l_returnflag, l_linestatus, l_shipdate)
    OPTIONS(fileFormat 'parquet');
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
            commit_date,                        # l_commitdate
            receipt_date,                       # l_receiptdate
            random.choice(['DELIVER IN PERSON', 'COLLECT FROM STORE']),  # l_shipinstruct
            random.choice(['AIR', 'RAIL', 'TRUCK']),                    # l_shipmode
            "Generated comment {}".format(i),    # l_comment
            random.choice(['A', 'B', 'C']),     # l_returnflag
            random.choice(['O', 'F']),          # l_linestatus
            ship_date                          # l_shipdate
        ))
    return data

def write_data(spark: SparkSession, data: list, schema: StructType, table_name: str):
    df = spark.createDataFrame(data, schema)
    df.write \
        .mode("append") \
        .insertInto(f"{table_name}")

def create_table_and_generate_data(spark: SparkSession, year: int, is_drop_table: bool = True):
    # create table
    if is_drop_table:
        spark.sql(f"DROP TABLE IF EXISTS {target_hive_table}")
    create_table(spark, target_hive_table)

    # generate data
    data = generate_data(year)
    schema = StructType([
        StructField("l_orderkey", LongType(), False),
        StructField("l_partkey", IntegerType(), False),
        StructField("l_suppkey", IntegerType(), False),
        StructField("l_linenumber", IntegerType(), False),
        StructField("l_quantity", DecimalType(15, 2), False),
        StructField("l_extendedprice", DecimalType(15, 2), False),
        StructField("l_discount", DecimalType(15, 2), False),
        StructField("l_tax", DecimalType(15, 2), False),
        StructField("l_receiptdate", TimestampType(), False),
        StructField("l_commitdate", TimestampType(), False),
        StructField("l_shipinstruct", StringType(), False),
        StructField("l_shipmode", StringType(), False),
        StructField("l_comment", StringType(), False),
        StructField("l_returnflag", StringType(), False),
        StructField("l_linestatus", StringType(), False),
        StructField("l_shipdate", TimestampType(), False)
    ])

    # write table into iceberg
    write_data(spark, data, schema, target_hive_table)

    spark.sql(f"""
    SELECT date_trunc('year', l_shipdate), COUNT(*) AS count FROM {target_hive_table} 
    GROUP BY date_trunc('year', l_shipdate)
    """).show()

if __name__ == "__main__":
    # create spark session
    spark = get_spark_session()
    for year in [2021, 2022, 2023]:
        is_drop_table = (year == 2021)
        create_table_and_generate_data(spark, year, is_drop_table)
    spark.stop()