
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
target_iceberg_table = f"{catalog_name}.sql_test_db.test_datetime_partitioned_table_with_null"

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
        StructField("l_returnflag", StringType(), False),
        StructField("l_linestatus", StringType(), False),
        StructField("l_shipdate", TimestampType(), False),
        StructField("l_commitdate", TimestampType(), False),
        StructField("l_receiptdate", TimestampType(), False),
        StructField("l_shipinstruct", StringType(), False),
        StructField("l_shipmode", StringType(), False),
        StructField("l_comment", StringType(), False)
    ])

    # write table into iceberg
    write_data(spark, data, schema, target_iceberg_table)

    spark.sql(f"""
    SELECT date_trunc('year', l_shipdate), COUNT(*) AS count FROM {target_iceberg_table} 
    GROUP BY date_trunc('year', l_shipdate)
    """).show()

def generate_1000_partition_tables():
    # create spark session
    spark = get_spark_session()
    for year in [2021, 2022, 2023]:
        is_drop_table = (year == 2021)
        create_table_and_generate_data(spark, year, is_drop_table)
    spark.stop()

def generate_data_with_null(year: int):
    start_date = datetime(year, 1, 1)  # 数据起始日期
    end_date = datetime(year, 12, 31)  # 数据结束日期
    add_days = 10
    data = []
    # for i in range(0, add_days):  
    #     ship_date = None
    #     commit_date = start_date + timedelta(days=i) + timedelta(days=random.randint(1, 10))
    #     receipt_date = commit_date + timedelta(days=random.randint(1, 5))
    #     data.append((
    #         random.randint(1, 1000000),   # l_orderkey
    #         random.randint(1, 100000),    # l_partkey
    #         random.randint(1, 50000),     # l_suppkey
    #         random.randint(1, 10),        # l_linenumber
    #         Decimal(round(random.uniform(1, 100), 2)),  # l_quantity
    #         Decimal(round(random.uniform(10, 1000), 2)),  # l_extendedprice
    #         Decimal(round(random.uniform(0, 0.1), 2)),   # l_discount
    #         Decimal(round(random.uniform(0, 0.2), 2)),   # l_tax
    #         random.choice(['A', 'B', 'C']),     # l_returnflag
    #         random.choice(['O', 'F']),          # l_linestatus
    #         None,                          # l_shipdate
    #         commit_date,                        # l_commitdate
    #         receipt_date,                       # l_receiptdate
    #         random.choice(['DELIVER IN PERSON', 'COLLECT FROM STORE']),  # l_shipinstruct
    #         random.choice(['AIR', 'RAIL', 'TRUCK']),                    # l_shipmode
    #         "Generated comment {}".format(i)    # l_comment
    #     ))
    for i in range(0, add_days):  
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

def create_and_generate_partition_tables_with_null(spark: SparkSession, year: int, is_drop_table: bool = True):
    # create table
    if is_drop_table:
        spark.sql(f"DROP TABLE IF EXISTS {target_iceberg_table}")
    create_table(spark, target_iceberg_table)

    # generate data
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

    data = generate_data_with_null(year)
    # write table into iceberg
    write_data(spark, data, schema, target_iceberg_table)

    spark.sql(f"""
    SELECT date_trunc('year', l_shipdate), COUNT(*) AS count FROM {target_iceberg_table} 
    GROUP BY date_trunc('year', l_shipdate)
    """).show()

def generate_partition_tables_with_null():
    # create spark session
    spark = get_spark_session()
    create_and_generate_partition_tables_with_null(spark, 2000, True)
    spark.stop() 

if __name__ == "__main__":
    # create spark session
    # generate_1000_partition_tables()
    generate_partition_tables_with_null()