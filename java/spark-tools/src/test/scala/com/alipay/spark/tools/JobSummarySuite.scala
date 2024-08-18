package com.alipay.spark.tools


import com.alipay.spark.tools.models.{AppInfoSummary, TableInput}
import org.json4s.DefaultFormats
import org.json4s.jackson.JsonMethods.{parse => parseJson}
import org.apache.spark.internal.Logging
import org.scalatest.FunSuite

/**
 * @author shuming.lsm
 * @version 2018/12/17
 **/
class JobSummarySuite extends FunSuite with Logging {
  test ("test parse job summary") {
    val json: String = "{\"appInfo\":{\"id\":\"application_1542890886593_85207\",\"bizId\":\"\",\"duration\":-1}," +
      "\"summaries\":[{\"sql\":\"select * from antods.ods_kg_trade_quotation_delta where dt='20181123'\",\"submissionTime\":1543001049072,\"completionTime\":\"1543001050223\",\"tableData\":{\"input\":[{\"name\":\"antods.ods_kg_trade_quotation_delta/hash(0) range(VALUE = \\\"20181123\\\")\",\"records\":5399,\"bytes\":129576}],\"output\":[]},\"stages\":[{\"stageId\":1,\"duration\":275,\"status\":\"complete\",\"inputBytes\":129576,\"inputRecords\":5399,\"outputBytes\":0,\"outputRecords\":0,\"numTasks\":1,\"numRunningTasks\":0,\"numCompletedTasks\":1,\"numFailedTasks\":0,\"numKilledTasks\":0,\"taskRunTimeMin\":186.0,\"taskRunTimeAvg\":186.0,\"taskRunTimeMax\":186.0},{\"stageId\":2,\"duration\":197,\"status\":\"complete\",\"inputBytes\":0,\"inputRecords\":0,\"outputBytes\":0,\"outputRecords\":0,\"numTasks\":1,\"numRunningTasks\":0,\"numCompletedTasks\":1,\"numFailedTasks\":0,\"numKilledTasks\":0,\"taskRunTimeMin\":134.0,\"taskRunTimeAvg\":134.0,\"taskRunTimeMax\":134.0}]}]}"

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
      case e: Exception =>  logWarning(s"parse summary failed: ${e}")
    }
  }
}
