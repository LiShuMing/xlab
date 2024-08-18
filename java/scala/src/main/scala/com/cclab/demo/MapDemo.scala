package com.alipay.tools.demo

import java.util.concurrent.ConcurrentHashMap

import scala.collection.mutable
import scala.collection.mutable.HashMap

/**
  * @author shuming.lsm
  * @version 2018/07/19
  **/
object MapDemo {
  def main(args: Array[String]): Unit = {

    // val op = immutable.Map.newBuilder[String, String]

    val op = new mutable.HashMap[String, String]()
    op + ("a" -> "b")
    op + ("a2" -> "b2")

    op.foreach(x => println(s"k:${x._1}, v: ${x._2}"))

    val set1 = Set(Map(1 -> 2), Map(1 -> 2, 2 -> 3), Map.empty)
    val set2 = Set(Map(1 -> 2), Map(3 -> 4))
    val set3 = (set1 ++ set2).filterNot(_.isEmpty)

    println(set3)

    val map = new ConcurrentHashMap[TablePartitionId, Boolean]()
    val partSpec1 = Map("a" -> "a", "b" -> "b")
    val partSpec2 = Map("a" -> "a", "b" -> "b")

    val v1 = TablePartitionId("a", partSpec1)
//    map(v1) = true
    val ret = map.put(v1, true)

    println(map)
    println(v1 == TablePartitionId("a", partSpec1))

    if (map.containsKey(v1)) {
      println("contains v1")
    }

    if (map.containsKey(TablePartitionId("a", partSpec1))) {
      println("contains partSpec1")
    }

    if (map.containsKey(TablePartitionId("a", partSpec2))) {
      println("contains partSpec2")
    }
  }

  def testHashMap(): Unit = {
    val map = new HashMap[TablePartitionId, Boolean]()
    val partSpec1 = Map("a" -> "a", "b" -> "b")
    val partSpec2 = Map("a" -> "a", "b" -> "b")

    val v1 = TablePartitionId("a", partSpec1)
    map(v1) = true
    println(map)

    if (map.contains(v1)) {
      println("contains v1")
    }

    if (map.contains(TablePartitionId("a", partSpec1))) {
      println("contains partSpec1")
    }

    if (map.contains(TablePartitionId("a", partSpec2))) {
      println("contains partSpec2")

    }
  }
}
case class TablePartitionId(tableName: String, partSpec: Map[String, String]) {
//  override def equals(that: Any): Boolean = that match {
//    case that: TablePartitionId =>
//      this.tableName.equalsIgnoreCase(that.tableName) && this.partSpec.equals(that.partSpec)
//    case _ =>
//      false
//  }
//
//  override def hashCode(): Int = {
//    println("hash:" + this)
//    this.tableName.hashCode ^ this.partSpec.hashCode()
//  }
//
//  override def toString: String = {
//    s"tableName=${tableName}, partSpec=${partSpec}"
//  }
}
