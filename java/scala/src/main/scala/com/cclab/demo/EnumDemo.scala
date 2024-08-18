package com.alipay.tools.demo

import scala.collection.mutable

/**
 * @author shuming.lsm
 * @version 2018/11/26
 **/
object EnumDemo {

  def main(args: Array[String]): Unit = {
    println(PartStorageType.HDFS.toString)
    println(PartStorageType.KUDU.toString)

    val m = new mutable.HashMap[String, String]()
    m += "a" -> "b"
    m += "a" -> "c"
    val m2 = new mutable.HashMap[String, String]()
    m2 += "a" -> "d"

    val m3 = m ++ m2
    val m4 = m2 ++ m
    println(m3)
    println(m4)
  }
}
