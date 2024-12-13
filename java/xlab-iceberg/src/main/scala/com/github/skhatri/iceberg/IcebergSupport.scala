package com.github.skhatri.iceberg

import org.apache.spark.sql.SparkSession

trait IcebergSupport {
  private val warehouseLocation = Option(System.getenv("CATALOG_WAREHOUSE")) match {
    case Some(x: String) => x
    case None => "./tmp/warehouse"
  }

  private val uri = Option(System.getenv("CATALOG_URI")) match {
    case Some(x: String) => x
    case None => "jdbc:sqlite:file:./tmp/iceberg_rest_mode=memory"
  }

  private val sparkBuilder = SparkSession.builder()
    .appName("xlab-spark-iceberg")
    .master("local[2]")
    .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
    .config("spark.sql.catalog.spark_catalog", "org.apache.iceberg.spark.SparkCatalog")
    .config("spark.sql.catalog.spark_catalog.type", "hive")
//    .config("spark.sql.catalog.spark_catalog.warehouse", warehouseLocation)

  val sparkCatalogBuilder: SparkSession.Builder = System.getenv("CATALOG_URL") match {
    case _ => sparkBuilder
      .config("spark.sql.catalog.local", "org.apache.iceberg.spark.SparkCatalog")
      .config("spark.sql.catalog.local.warehouse", warehouseLocation)
      .config("spark.sql.catalog.local.type", "hive")
      .config("spark.sql.catalog.local.uri", "thrift://localhost:9083")

//      .config("spark.executor.extraJavaOptions", "--add-exports java.base/sun.nio.ch=ALL-UNNAMED")
//      .config("spark.driver.extraJavaOptions", "--add-exports java.base/sun.nio.ch=ALL-UNNAMED")
      //      .config("spark.sql.catalog.spark_catalog.uri", "http://localhost:8181")
    //      .config("spark.sql.catalog.spark_catalog.type", "hive")
    //      .config("spark.sql.catalog.iceberg.type", "jdbc")
    //      .config("spark.sql.catalog.iceberg.uri", uri)
    //      .config("spark.sql.catalog.spark_catalog.type", "jdbc")
    //      .config("spark.sql.catalog.spark_catalog.uri", uri.replaceAll("iceberg", "spark"))
  }
}
