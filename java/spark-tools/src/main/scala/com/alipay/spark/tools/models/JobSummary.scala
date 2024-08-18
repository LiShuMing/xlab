package com.alipay.spark.tools.models

import org.apache.spark.JobExecutionStatus
import org.apache.spark.status.api.v1.{StageStatus, TableData}

import scala.beans.BeanProperty

/**
 * @author shuming.lsm
 * @version 2018/11/28
 **/
case class SQLAppSummaryV2 (
                             @BeanProperty val appInfo: AppInfoSummary,
                             @BeanProperty val summaries: Seq[SQLExecuteSummary])

case class SQLExecuteSummary(@BeanProperty val sql: String,
                             @BeanProperty val submissionTime: Long,
                             @BeanProperty val completionTime: Option[Long],
                             @BeanProperty val tableData: TableSummary,
                             @BeanProperty val stages: Seq[JobSummary])


case class TableOutput(name: String, records: Long, bytes: Long)

case class TableInput(name: String, records: Long, bytes: Long)

case class TableSummary (
                          @BeanProperty val input: Map[String, TableInput],
                          @BeanProperty val output: Map[String, TableOutput])

case class AppSummaryV2 (
                          @BeanProperty val appInfo: AppInfoSummary,
                          @BeanProperty val table: TableData,
                          @BeanProperty val resourceSummary: ResourceSummary,
                          @BeanProperty val jobSummaries: Seq[JobSummary])

case class ResourceSummary(
                            @BeanProperty cpuRunTime: Long,
                            @BeanProperty memoryRunTime: Long)

case class AppInfoSummary(
                           @BeanProperty id: String,
                           @BeanProperty bizId: String,
                           @BeanProperty duration: Int)

case class JobSummary(
                       @BeanProperty val jobId: Int,
                       @BeanProperty val submissionTime: Option[Long],
                       @BeanProperty val completionTime: Option[Long],
                       @BeanProperty val status: JobExecutionStatus,
                       @BeanProperty val stageIds: Seq[Int],
                       @BeanProperty val numActiveStages: Int,
                       @BeanProperty val numCompletedStages: Int,
                       @BeanProperty val numSkippedStages: Int,
                       @BeanProperty val numFailedStages: Int,
                       @BeanProperty val stageSummaries: Seq[StageSummary])

case class StageSummary (
                          @BeanProperty val status: StageStatus,
                          @BeanProperty val stageId: Int,
                          @BeanProperty val attemptId: Int,

                          @BeanProperty val duration: Option[Long],

                          @BeanProperty val numTasks: Int,
                          @BeanProperty val numActiveTasks: Int,
                          @BeanProperty val numCompleteTasks: Int,
                          @BeanProperty val numFailedTasks: Int,
                          @BeanProperty val numKilledTasks: Int,

                          @BeanProperty val inputBytes: Long,
                          @BeanProperty val inputRecords: Long,
                          @BeanProperty val outputBytes: Long,
                          @BeanProperty val outputRecords: Long,
                          @BeanProperty val inputTables: Option[Map[String, TableInput]],
                          @BeanProperty val outputTables: Option[Map[String, TableOutput]],
                          @BeanProperty val executorRunTimeMin: Option[Double],
                          @BeanProperty val executorRunTimeAvg: Option[Double],
                          @BeanProperty val executorRunTimeMax: Option[Double])
