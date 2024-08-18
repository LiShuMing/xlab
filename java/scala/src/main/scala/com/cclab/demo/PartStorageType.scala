package com.alipay.tools.demo

/**
 * Support different storage types, now kudu and hdfs type are supported.
 */
object PartStorageType extends Enumeration {
  type PartStorageType = Value
  val KUDU, HDFS = Value

  def isKuduStorageType(storageType: PartStorageType): Boolean = {
    storageType == KUDU
  }

  def isHdfsStorageType(storageType: PartStorageType): Boolean = {
    storageType == HDFS
  }
}
