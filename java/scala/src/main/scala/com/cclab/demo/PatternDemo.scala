package com.alipay.tools.demo

import java.util.regex.Pattern

import scala.collection.mutable.ArrayBuffer

/**
 * @author shuming.lsm
 * @version 2018/10/23
 **/
object PatternDemo {
  //val p = Pattern.compile("\\((?<lowerRange>[\\w,]*)\\),\\s*\\((?<highRange>[\\w,]*)\\)*")
  val p = Pattern.compile(
    "\\((?<lowerRange>[\\w,]*)\\),\\s*\\((?<highRange>[\\w,]*)\\)*")

  def findRegexp(s: String) = {
    val m = p.matcher(s)
    while (m.find()) {
      val lower = m.group("lowerRange").replace(",", "/")
      val higher = m.group("highRange").replace(",", "/")
      println(lower + "-" + higher)
    }
  }

  def partValues(partition: String) = {
    val matcher = p.matcher(partition)

    var lowHighRange: Array[(String, String)] = Array.empty
    while (matcher.find()) {
      val lowerRange = matcher.group("lowerRange")
      val highRange = matcher.group("highRange")
      lowHighRange = lowerRange.split(",").zip(highRange.split(","))
    }

    val lowHighs = lowHighRange.map(range =>
      Array(range._1, range._2).mkString("--")
    )
    println(lowHighs.length)
  }

  def test1(): Unit = {
    val a = Array(1)
    val b = Array("a", "b", "c")

    a.zip(b).toSeq.foreach(println(_))
  }

  def test2(): Unit = {
    val a = new ArrayBuffer[(String, String)]()
    val tmp = ("a", "b")
    a += tmp
    val tmp2 = ("c", "d")
    a += tmp2
    val m = a.toMap

    m.map { case (x, y) =>
      println(s"x: ${x}, y: ${y}")
    }
  }

  def test3(): Unit = {
    Some(null).filter(_ != null).map(println)
  }

  def main(args: Array[String]): Unit = {
    // "dt=20180915","(20180914),(20180914)","(20180913),(20180914)","(20180912),(20180913)"
    // val arr = Array("(#1,#1), (=1, =2)", "(1,2)", "(1, 2), (1, 2), (a, b)")
    val arr = Array("(1), (3)", "(1,2)", "(1,2),(1,2)", "(1,1),(1,1)", "(20181106),(20181106)")
    arr.map(findRegexp(_))

    partValues("(20181106),(20181106)")
    //test1()
    //test2()
    //test3()
  }
}
