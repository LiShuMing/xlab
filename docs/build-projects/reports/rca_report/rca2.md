

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


请根据上述要求生成一份针对Harness用户的RCA报告。

已知的一些输入如下：


1. 用户测遇到的一些问题及反馈
```
 2026-03-15 00:00:01.365Z WARN (starrocks-taskrun-pool-7051|1277358) [CatalogUtils.checkPartitionNameExistForAddPartitions():93] Duplicate partition name peightfolddemohiringtest2ecom, existed partition:partition_id: 329131830; name: peightfolddemohiringtest2ecom; partition_stat.name: NORMAL; distribution_info.type: HASH; distribution_info: type: HASH; distribution columns: [profile_id,]; bucket num: 1; , current partition:PARTITION peightfolddemohiringtest2ecom VALUES IN (('eightfolddemo-hiring-test.com')) ("storage_medium" = "HDD", "replication_num" = "1")
 2026-03-15 00:00:01.365Z WARN (starrocks-taskrun-pool-7051|1277358) [PartitionBasedMvRefreshProcessor.doRefreshMaterializedView():461]  [employee_skill_gaps_test_debug_2025_03_14] failed to compute candidate partitions in sync partitions
 2026-03-15 00:00:01.366Z WARN (starrocks-taskrun-pool-7051|1277358) [PartitionBasedMvRefreshProcessor.doRefreshMaterializedViewWithRetry():419]  [employee_skill_gaps_test_debug_2025_03_14] refresh mv failed at 1th time: com.starrocks.common.DdlException: Duplicate partition nae peightfolddemohiringtest2ecom
        at com.starrocks.common.ErrorReport.reportDdlException(ErrorReport.java:96)
        at com.starrocks.common.ErrorReport.reportDdlException(ErrorReport.java:91)
        at com.starrocks.catalog.CatalogUtils.checkPartitionNameExistForAddPartitions(CatalogUtils.java:95)
        at com.starrocks.sql.analyzer.AlterTableClauseAnalyzer.analyzeAddPartition(AlterTableClauseAnalyzer.java:1262)
        at com.starrocks.sql.analyzer.AlterTableClauseAnalyzer.visitAddPartitionClause(AlterTableClauseAnalyzer.java:1225)
 [wrapped] com.starrocks.sql.analyzer.SemanticException: Getting analyzing error. Detail message: Duplicate partition name peightfolddemohiringtest2ecom.
        at com.starrocks.sql.analyzer.AlterTableClauseAnalyzer.visitAddPartitionClause(AlterTableClauseAnalyzer.java:1227)
        at com.starrocks.sql.analyzer.AlterTableClauseAnalyzer.visitAddPartitionClause(AlterTableClauseAnalyzer.java:130)
        at com.starrocks.sql.ast.AddPartitionClause.accept(AddPartitionClause.java:88)
        at com.starrocks.sql.ast.AstVisitor.visit(AstVisitor.java:101)
        at com.starrocks.sql.analyzer.AlterTableClauseAnalyzer.analyze(AlterTableClauseAnalyzer.java:138)
        at com.starrocks.scheduler.mv.MVPCTRefreshListPartitioner.addListPartitions(MVPCTRefreshListPartitioner.java:532)
        at com.starrocks.scheduler.mv.MVPCTRefreshListPartitioner.syncAddOrDropPartitions(MVPCTRefreshListPartitioner.java:152)
        at com.starrocks.scheduler.PartitionBasedMvRefreshProcessor.syncPartitions(PartitionBasedMvRefreshProcessor.java:1034)
        at com.starrocks.scheduler.PartitionBasedMvRefreshProcessor.doRefreshMaterializedView(PartitionBasedMvRefreshProcessor.java:454)
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

2. 分析employee_skill_gaps_test_debug_2025_03_14的定义，其基表有多个Olap表和嵌套MV。结合异常堆栈和之前修复类似问题的PR(https://github.com/StarRocks/starrocks/pull/62446)发现，之前的修复PR不够鲁棒。本地可以reproduce该问题:
```

CREATE MATERIALIZED VIEW `employee_skill_gaps_test_debug_2025_03_14` (`position_id`, `profile_id`, `employee_id`, `business_unit`, `location_country`, `level`, `lob`, `is_alumni`, `employee_email`, `manager_email`, `title`, `hiring_date`, `termination_date`, `is_profile_activated`, `group_id`, `skill_name`, `skill_benchmark`, `manager_rating`, `manager_rating_ts`, `self_rating`, `self_rating_ts`, `inferred_proficiency`, `inferred_proficiency_ts`, `is_highlighted`, `num_endorsements`, `employee_has_skill`, `is_role_approved`, `is_standard_skill`, `is_not_applicable`, `is_excluded`)
COMMENT "MATERIALIZED_VIEW"
PARTITION BY (`group_id`)
DISTRIBUTED BY HASH(`profile_id`) BUCKETS 1 
ORDER BY (employee_email)
REFRESH ASYNC START("2025-12-01 02:00:00") EVERY(INTERVAL 2 HOUR)
PROPERTIES (
"replicated_storage" = "true",
"replication_num" = "1",
"partition_refresh_number" = "50",
"query_rewrite_consistency" = "LOOSE",
"session.spill_mode" = "force",
"session.enable_spill" = "true",
"datacache.enable" = "true",
"enable_async_write_back" = "false",
"storage_volume" = "builtin_storage_volume",
"warehouse" = "default_warehouse"
)
AS SELECT `pos`.`position_id`, `pos`.`profile_id`, `pos`.`employee_id`, `pos`.`business_unit`, `pos`.`location_country`, `pos`.`level`, `pos`.`lob`, `pos`.`is_alumni`, `pos`.`employee_email`, `pos`.`manager_email`, `pos`.`title`, `pos`.`hiring_date`, `pos`.`termination_date`, `pos`.`is_profile_activated`, `pos`.`group_id`, `pos`.`skill_name`, `pos`.`skill_benchmark`, `pr`.`manager_rating`, `pr`.`manager_rating_ts`, `pr`.`self_rating`, `pr`.`self_rating_ts`, `pr`.`inferred_proficiency`, `pr`.`inferred_proficiency_ts`, `pr`.`is_highlighted`, `pr`.`num_endorsements`, `pr`.`original_skill_name` IS NOT NULL AS `employee_has_skill`, `pos`.`is_role_approved`, `pr`.`is_standard_skill`, `pr`.`is_not_applicable`, `pr`.`is_excluded`
FROM (SELECT `e`.`profile_id`, `e`.`employee_id`, `rs`.`position_id`, `rs`.`group_id`, `rs`.`skill_name`, `rs`.`skill_benchmark`, `e`.`business_unit`, `e`.`location_country`, `e`.`level`, `e`.`lob`, `e`.`is_alumni`, `e`.`employee_email`, `e`.`manager_email`, `e`.`title`, `e`.`hiring_date`, `e`.`termination_date`, `e`.`is_profile_activated`, `rs`.`is_role_approved`
FROM (SELECT `role_skills`.`position_id`, `role_skills`.`group_id`, `role_skills`.`skill_name`, `role_skills`.`skill_benchmark`, `role_skills`.`is_role_approved`
FROM `analytics`.`role_skills`) `rs` INNER JOIN (SELECT `employee`.`profile_id`, `employee`.`business_unit`, `employee`.`location_country`, `employee`.`employee_id`, `employee`.`level`, `employee`.`lob`, `employee`.`is_alumni`, `employee`.`employee_email`, `employee`.`manager_email`, `employee`.`title`, `employee`.`hiring_date`, `employee`.`termination_date`, `employee`.`is_profile_activated`, coalesce(`employee`.`role_variant_id`, `employee`.`jie_role_id`) AS `role_variant_id`
FROM `analytics`.`employee`) `e` ON `e`.`role_variant_id` = `rs`.`position_id`) `pos` LEFT OUTER JOIN `analytics`.`employee_skills_test_debug_2025_03_14` AS `pr` ON ((`pr`.`profile_id` = `pos`.`profile_id`) AND (`pr`.`group_id` = `pos`.`group_id`)) AND (`pr`.`original_skill_name` = `pos`.`skill_name`);


```
3. 最终修复PR: https://github.com/StarRocks/starrocks/pull/70328/ 。核心原因在于之前PR的修复逻辑存在漏洞，只能保障本轮次新增的分区内部不重复，但没有考虑跟原有MV已有的分区，导致有可能会触发`duplicate partition name"
4. 修复方法，需要apply上https://github.com/StarRocks/starrocks/pull/62446 PR，重新打包才可以。