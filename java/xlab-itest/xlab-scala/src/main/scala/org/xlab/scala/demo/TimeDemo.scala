package org.xlab.scala.demo

import java.sql.Timestamp
import java.text.SimpleDateFormat

object TimeDemo {
  var sparkFormatter: SimpleDateFormat = new SimpleDateFormat("yyyyMMdd")

  def evaluate(timestamp: Int): String = {
    try {
      val ts = new Timestamp(timestamp * 1000L)
      return sparkFormatter.format(ts)
    } catch {
      case _: Throwable =>
        return null
    }
  }

  def main(args: Array[String]): Unit = {
    println(System.currentTimeMillis() / 1000)
    println(evaluate(1541602617 ))
  }
}
