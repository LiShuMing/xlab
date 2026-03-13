

按照如下格式输出发送给北美用户的Root Cause Anlaysise报告：
```
# Conclusion
# Problem Statement
# Analysis
# Solution
```

根据下文的一些输入，按照上述格式输出一份RCA报告。注意输出格式：
- 使用英文，语言尽量使用书面报告形式;
- 根据输入的日志填充、佐证RCA报告；


请根据上述要求生成一份针对EightFold用户的RCA报告。

已知的一些输入如下：


1. 用户测遇到的一些问题及反馈

用户遇到了 `ta_source_activity_log_employee_mv` 这个mv的刷新失败，以为是刷新失败导致偶发MV返回的结果为0；同时以为是事务没有保障原子性导致的。

There is also a problem with transaction rollback implementation. When an MV refresh fails, it is ending up with 0 rows. We should be retaining the last successful refresh state. Attached screenshot to show the state.

These are data loss events in production, and we expect a detailed RCA of the issues. Please prioritize the fixes as well.
```
Refresh mv ta_source_activity_log_employee_mv failed after 1 times, try lock failed: 0, error-msg : com.starrocks.common.DdlException: 172.31.162.127: starlet err [RequestID=WXRCQ7VF4GDN7Z3X][StatusCode=503]Put object error: Please reduce your request rate.
	at com.starrocks.common.ErrorReport.reportDdlException(ErrorReport.java:96)
	at com.starrocks.qe.StmtExecutor.handleDMLStmt(StmtExecutor.java:2730)
 [wrapped] com.starrocks.common.StarRocksException: 172.31.162.127: starlet err [RequestID=WXRCQ7VF4GDN7Z3X][StatusCode=503]Put object s3://ef-starrocks-data-us-west-2/ktbz1vr2e-starrocks-prod-cluste00000000233534B.log error: Please reduce your request rate.
	at com.starrocks.qe.StmtExecutor.handleDMLStmt(StmtExecutor.java:2969)
	at com.starrocks.load.InsertOverwriteJobRunner.executeInsert(InsertOverwriteJobRunner.java:409)
	at com.starrocks.load.InsertOverwriteJobRunner.doLoad(InsertOverwriteJobRunner.java:178)
	at com.starrocks.load.InsertOverwriteJobRunner.handle(InsertOverwriteJobRunner.java:158)
	at com.starrocks.load.InsertOverwriteJobRunner.transferTo(InsertOverwriteJobRunner.java:224)
	at com.starrocks.load.InsertOverwriteJobRunner.prepare(InsertOverwriteJobRunner.java:277)
	at com.starrocks.load.InsertOverwriteJobRunner.handle(InsertOverwriteJobRunner.java:155)
	at com.starrocks.load.InsertOverwriteJobRunner.run(InsertOverwriteJobRunner.java:143)
	at com.starrocks.load.InsertOverwriteJobMgr.executeJob(InsertOverwriteJobMgr.java:90)
	at com.starrocks.qe.StmtExecutor.handleInsertOverwrite(StmtExecutor.java:2481)
	at com.starrocks.qe.StmtExecutor.handleDMLStmt(StmtExecutor.java:2574)
	at com.starrocks.qe.StmtExecutor.handleDMLStmtWithProfile(StmtExecutor.java:2490)
	at com.starrocks.scheduler.PartitionBasedMvRefreshProcessor.refreshMaterializedView(PartitionBasedMvRefreshProcessor.java:1222)
	at com.starrocks.scheduler.PartitionBasedMvRefreshProcessor.doRefreshMaterializedView(PartitionBasedMvRefreshProcessor.java:504)
	at com.starrocks.scheduler.PartitionBasedMvRefreshProcessor.doRefreshMaterializedViewWithRetry(PartitionBasedMvRefreshProcessor.java:410)
	at com.starrocks.scheduler.PartitionBasedMvRefreshProcessor.doMvRefresh(PartitionBasedMvRefreshProcessor.java:344)
	at com.starrocks.scheduler.PartitionBasedMvRefreshProcessor.processTaskRun(PartitionBasedMvRefreshProcessor.java:197)
	at com.starrocks.scheduler.TaskRun.executeTaskRun(TaskRun.java:383)
	at com.starrocks.scheduler.TaskRunExecutor.lambda$executeTaskRun$0(TaskRunExecutor.java:60)
	at java.base/java.util.concurrent.CompletableFuture$AsyncSupply.run(CompletableFuture.java:1768)
	at java.base/java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:1136)
	at java.base/java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:635)
	at java.base/java.lang.Thread.run(Thread.java:840)
```


2. 分析用户日志发现， `ta_source_activity_log_employee_mv`这个mv刷新最近一直都没有成功过。
```
ubuntu@ip-172-31-182-192:/data1/log$ grep "\[ta_source_activity_log_employee_mv\]" fe.log.202603*|grep "finished to refresh mv in DML" |wc -l
67

ubuntu@ip-172-31-182-192:/data1/log$ grep "\[ta_source_activity_log_employee_mv\]" fe.log.202603*|grep " refresh mv failed at 1th time:" |wc -l
```

而且总结起来该MV刷新失败有两大类：
- 刷新过程中遇到S3限流或者spill时候no spill导致的运行时错误；
- 在写入mv的时候，由于3.5版本MV开启了strict insert，在写入MV时会检查varchar数据写入的data length同Schema的data length是否对齐，如果有超过schema的data length，就会抛异常。
```
2026-03-10 11:00:31.175Z INFO (starrocks-taskrun-pool-23951|3538852) [DatabaseTransactionMgr.beginTransaction():189] begin transaction: txn_id: 36892768 with label insert_2df69121-1c6e-11f1-87aa-0a71f84af585 from coordinator FE: 172.31.182.192, listner id: -1 
2026-03-10 11:01:51.393Z INFO (starrocks-taskrun-pool-23951|3538852) [DatabaseTransactionMgr.abortTransaction():634] transaction:[TransactionState. txn_id: 36892768, label: insert_2df69121-1c6e-11f1-87aa-0a71f84af585, db id: 24407, table id list: 55882444, callback id: [-1, 298565208], coordinator: FE: 172.31.182.192, transaction status: ABORTED, error replicas num: 0, unknown replicas num: 0, prepare time: 1773140431175, write end time: -1, allow commit time: -1, commit time: -1, finish time: 1773140511386, total cost: 80211ms, reason: Insert has filtered data, tracking sql = select tracking_log from information_schema.load_tracking_logs where job_id=298565208, partition commit info:[]] successfully rollback 
2026-03-10 11:01:51.445Z WARN (starrocks-taskrun-pool-23951|3538852) [InsertOverwriteJobRunner.executeInsert():413] insert overwrite failed. error message:Insert has filtered data, txn_id = 36892768, tracking sql = select tracking_log from information_schema.load_tracking_logs where job_id=298565208 
com.starrocks.sql.common.DmlException: Insert has filtered data, txn_id = 36892768, tracking sql = select tracking_log from information_schema.load_tracking_logs where job_id=298565208 
2026-03-10 11:01:51.662Z WARN (starrocks-taskrun-pool-23951|3538852) [PartitionBasedMvRefreshProcessor.refreshMaterializedView():1224]  [ta_source_activity_log_employee_mv] [QueryId:2df69121-1c6e-11f1-87aa-0a71f84af585] refresh mv com.starrocks.sql.common.DmlException: Insert has filtered data, txn_id = 36892768, tracking sql = select tracking_log from information_schema.load_tracking_logs where job_id=298565208 failed in DML 
2026-03-10 11:01:51.662Z WARN (starrocks-taskrun-pool-23951|3538852) [PartitionBasedMvRefreshProcessor.doRefreshMaterializedViewWithRetry():419]  [ta_source_activity_log_employee_mv] refresh mv failed at 1th time: com.starrocks.sql.common.DmlException: Insert has filtered data, txn_id = 36892768, tracking sql = select tracking_log from information_schema.load_tracking_logs where job_id=298565208 
com.starrocks.sql.common.DmlException: Refresh mv ta_source_activity_log_employee_mv failed after 1 times, try lock failed: 0, error-msg : com.starrocks.sql.common.DmlException: Insert has filtered data, txn_id = 36892768, tracking sql = select tracking_log from information_schema.load_tracking_logs where job_id=298565208 
Caused by: com.starrocks.sql.common.DmlException: Insert has filtered data, txn_id = 36892768, tracking sql = select tracking_log from information_schema.load_tracking_logs where job_id=298565208
```
3. 看到了mv的定义schema，因为mv定义中包含case when，怀疑跟一直修复过的问题有关系（https://github.com/StarRocks/starrocks/pull/62476）。
```
CREATE MATERIALIZED VIEW `ta_source_activity_log_employee_mv` (`group_id`, `employee_email`, `manager_email`, `manager_name`, `active_user_name`, `employee_title`, `employee_level`, `employee_seniority`, `employee_line_of_business`, `employee_business_unit`, `is_alumni`, `employee_location`, `employee_location_country`, `is_recruiter`, `is_hm`, `is_sourcer`, `is_event_team_external`, `race`, `gender`, `ef_gender`, `ef_race`, `transformed_employee_email`)
COMMENT ""MATERIALIZED_VIEW""
PARTITION BY (`group_id`)
DISTRIBUTED BY HASH(`group_id`)
ORDER BY (group_id)
REFRESH ASYNC
PROPERTIES (
""replicated_storage"" = ""true"",
""replication_num"" = ""1"",
""query_rewrite_consistency"" = ""LOOSE"",
""session.spill_mode"" = ""force"",
""session.enable_spill"" = ""true"",
""datacache.enable"" = ""true"",
""enable_async_write_back"" = ""false"",
""storage_volume"" = ""builtin_storage_volume"",
""warehouse"" = ""default_warehouse""
)
AS SELECT `employee`.`group_id`, `employee`.`employee_email`, `employee`.`manager_email`, `employee`.`manager_name`, concat(`employee`.`first_name`, concat(' ', `employee`.`last_name`)) AS `active_user_name`, CASE WHEN (`employee`.`title` IS NULL) THEN 'Title not assigned' ELSE `employee`.`title` END AS `employee_title`, CASE WHEN (`employee`.`level` IS NULL) THEN 'Level not assigned' ELSE `employee`.`level` END AS `employee_level`, CASE WHEN (`employee`.`seniority` IS NULL) THEN 'Seniority not assigned' ELSE `employee`.`seniority` END AS `employee_seniority`, CASE WHEN (`employee`.`lob` IS NULL) THEN 'Level of Business not assigned' ELSE `employee`.`lob` END AS `employee_line_of_business`, CASE WHEN (`employee`.`business_unit` IS NULL) THEN 'Business unit not assigned' ELSE `employee`.`business_unit` END AS `employee_business_unit`, `employee`.`is_alumni`, CASE WHEN (`employee`.`location` IS NULL) THEN 'Location not found' ELSE `employee`.`location` END AS `employee_location`, CASE WHEN (`employee`.`location_country` IS NULL) THEN 'Location Country not found' ELSE `employee`.`location_country` END AS `employee_location_country`, `employee`.`is_recruiter`, `employee`.`is_hm`, `employee`.`is_sourcer`, `employee`.`is_event_team_external`, `employee`.`race`, `employee`.`gender`, `employee`.`ef_gender`, `employee`.`ef_race`, lower(trim(`employee`.`employee_email`)) AS `transformed_employee_email`
FROM `analytics`.`employee`;"
```

```
Field	Type
group_id	varchar(100)
employee_email	varchar(200)
manager_email	varchar(200)
manager_name	varchar(100)
active_user_name	varchar(1048576)
employee_title	varchar(200)
employee_level	varchar(50)
employee_seniority	varchar(20)
employee_line_of_business	varchar(100)
employee_business_unit	varchar(100)
is_alumni	boolean
employee_location	varchar(200)
employee_location_country	varchar(100)
is_recruiter	boolean
is_hm	boolean
is_sourcer	boolean
is_event_team_external	boolean
race	varchar(255)
gender	varchar(20)
ef_gender	varchar(200)
ef_race	varchar(200)
transformed_employee_email	varchar(1048576)
```
4. 修复手段

因为https://github.com/StarRocks/starrocks/pull/62476 只能对新创建的MV生效，开启`transform_type_prefer_string_for_varchar` 后MV默认不再使用推导的定长varchar作为MV结果的schema，以防止filtered data导致的问题；而且该参数在后面版本中会默认开启。


所以建议用户在开启该参数的情况下，通过`SWAP MV`方式替换掉原来的MV；
```
ADMIN SET FRONTEND CONFIG('transform_type_prefer_string_for_varchar' = 'true');

-- create a new mv with the same schema of ta_source_activity_log_employee_mv，and check the mv's schema, its varchar length should be 1048576(default string's length)
create materialized view ta_source_activity_log_employee_mv_new xxx

-- refresh & check the result of the new mv 
refresh materialized view ta_source_activity_log_employee_mv_new;

-- if it's ok
alter materialized view ta_source_activity_log_employee_mv swap with ta_source_activity_log_employee_mv_new;
```