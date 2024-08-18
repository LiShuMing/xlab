package com.alipay.tools.demo

import scala.util.Try

/**
  * @author shuming.lsm
  * @version 2018/07/03
  **/
object Demo {
  def demo1(): Unit = {
    val arr = Array(1, 2, 3, 4)
    arr.filter { p =>
     if (p % 2 == 0) {
       true
     } else {
       false
     }
    }. foreach(println(_))
  }

  def demo2(): Unit = {
    val a: Option[Map[String, String]] = None
    val m = Map[String, String]("a" -> "a")
    val a2: Option[Map[String, String]] = Some(m)
    println(a.size)
    println(a2.size)
  }

  def testMap(): Unit = {
    val m = Map("a" -> "1")
    val a = Array("a")
    val v = a.map(m)
    v.foreach(println(_))
  }

  def test1() = {
    println(10 / 1 << 10)
    println(10 / (1 << 10))
    val mb = 384 * 1024 * 1024
    println(mb / (1L << 20) / 3000 / 1000)
    println(mb.toDouble / (1L << 20) / (3000 / 1000))
  }

  case class BoundRange(low: Array[Byte], upper: Array[Byte])
  def test2() = {
    val ByteMax = -1.asInstanceOf[Byte]
    val ByteMin = 0.asInstanceOf[Byte]
    println(ByteMax)
    println(ByteMax.getClass)
    println(ByteMin)
    println(ByteMin.getClass)

    val bytesMax = null
    val x = BoundRange(bytesMax, bytesMax)
  }

  def test3() = {
        // testMap()
    val if1 = new If1Impl()
    if1.method1(1)
    if1.method1(1, true)
    if1.method1(1, false)

    // case class
    val c1 = Case1(1, true)
    c1.p()
    val c2 = Case1(1)
    c2.p()
    val c3 = Case1(1, false)
    c3.p()
  }

  def parseInt(value: String): Try[Int] = Try(value.toInt)

  def main(args: Array[String]): Unit = {
    val a = Array("a", "1", "2", "3")

    val xx = a.map(x => {
      println(s"x=${x}")
      parseInt(x)
    }).find(_.isSuccess).getOrElse("0")

    println(xx)
  }
}
