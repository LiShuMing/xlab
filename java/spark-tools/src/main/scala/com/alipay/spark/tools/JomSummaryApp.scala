package com.alipay.spark.tools

import com.alipay.spark.tools.models.{AppInfoSummary, TableInput}
import org.json4s.DefaultFormats
import org.json4s.jackson.JsonMethods.{parse => parseJson}

import org.apache.spark.internal.Logging
import org.apache.spark.{SparkConf, SparkContext}

/**
 * @author shuming.lsm
 * @version 2018/11/28
 **/
object JomSummaryApp extends Logging {

  def parseSummaryJson(json: String): Unit = {
    try {
      implicit val formats = DefaultFormats
      val jValue = parseJson(json)
      (jValue \ "appInfo").extract[AppInfoSummary] match {
        case appInfo: AppInfoSummary =>
          println(appInfo)
        case _ => println("none")
      }

      val sql = jValue \ "summaries" \ "sql"
      println(sql)
      val submissionTime = jValue \ "summaries" \ "submissionTime"
      println(submissionTime)
      val completionTime = jValue \ "summaries" \ "completionTime"
      println(completionTime)
      val tableData = jValue \ "summaries" \ "tableData"
      println(tableData)
      val tableInputs = (tableData \ "input").extract[Seq[TableInput]]
      val names = (tableData \ "name").extract[Seq[String]]
      println(names)
      println(tableInputs)
      for (t <- tableInputs) {
        println(t)
      }
      println(tableData \ "output")
    } catch {
      case e: Exception => {logWarning(s"parse json failed: ${e}")}
    }
  }

  def main(args: Array[String]): Unit = {
    val path = if (args.length == 0) {
      // Just use for testing.
      "pangu://localcluster/spark/proxyserver/apps/14735990_summary"
    } else {
      args(0)
    }

    val sparkConf = new SparkConf()
    sparkConf.setAppName("JomSummary-V1")
    val sparkContext = new SparkContext(sparkConf)

    sparkContext.textFile(path).map { line =>
      logInfo(s"Read job summary: ${line}")

      try {
        logInfo(s"SUMMARY: ${line}")
        parseSummaryJson(line)
      } catch {
        case e: Exception => logWarning(s"Parse job summary failed: ${e}")
      }
    }

    sparkContext.stop()
  }
}
