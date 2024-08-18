package com.alipay.tools.cases

import scala.collection.mutable
import scala.util.Try

object FindCase {
  def parseInt(value: String): Try[Int] = Try(value.toInt)
  def main(args: Array[String]): Unit = {

    val a = Array("a", "1", "2", "3")

    val xx = a.toStream.map(x => {
      println(s"x=${x}")
      parseInt(x)
    }).find(_.isSuccess).getOrElse("0")

    println(xx)


    val m = Seq("a", "b", "c").zipWithIndex.map { case (item, id) =>
        item -> id
    }.toMap
    val mm = mutable.Buffer[Map[String, Int]](m)
    println(mm.size)
    println(mm)
  }
}
